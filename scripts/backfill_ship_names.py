#!/usr/bin/env python3
"""
艦艇名をRust版 localized_name_from_param 形式（UPPERCASE）に統一するバックフィルスクリプト

対象テーブル:
  1. wows-ship-match-index-{stage}: PKがshipNameのため delete + put
  2. wows-{type}-battles-{stage}: MATCH/STATS/UPLOADレコード内のshipName
  3. wows-replays-{stage}: allies/enemies/ownPlayer/allPlayersStats内のshipName

使い方:
  python3 scripts/backfill_ship_names.py [--dry-run] [--stage prod] [--target all|ship-index|battles|replays]
  DRY_RUN=true でも可
"""

import argparse
import json
import os
import sys
import time
from decimal import Decimal

import boto3

# マッピングファイルのパス
MAPPING_PATH = os.path.join(os.path.dirname(__file__), "..", "config", "ship_name_mapping.json")


def load_mapping():
    """マッピングファイルを読み込む"""
    with open(MAPPING_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)

    ship_id_to_upper = data["shipIdToNameUpper"]  # str(shipId) -> UPPERCASE name (for ship-index)
    ship_id_to_display = data["shipIdToName"]  # str(shipId) -> Title Case name (for display)
    old_to_upper = data["oldNameToNewName"]  # oldName -> UPPERCASE new name (for ship-index)
    old_to_display = data.get("oldNameToDisplayName", {})  # oldName -> Title Case (for display)

    return ship_id_to_upper, ship_id_to_display, old_to_upper, old_to_display


def resolve_new_name(ship_name, ship_id, ship_id_to_name, old_to_new):
    """shipIdベースで新名を解決。shipIdがなければ旧名→新名マッピングで解決。"""
    if ship_id:
        sid_str = str(int(ship_id) if isinstance(ship_id, Decimal) else ship_id)
        new_name = ship_id_to_name.get(sid_str)
        if new_name:
            return new_name

    # shipIdで解決できない場合、旧名マッピングを使用
    if ship_name and ship_name in old_to_new:
        return old_to_new[ship_name]

    return None


def backfill_ship_index(stage, dry_run, ship_id_to_name, old_to_new):
    """wows-ship-match-index テーブルのshipName（PK）を更新"""
    dynamodb = boto3.resource("dynamodb")
    table_name = f"wows-ship-match-index-{stage}"
    table = dynamodb.Table(table_name)

    print(f"\n=== Ship Index: {table_name} ===")

    # 全スキャン
    items = []
    params = {}
    while True:
        resp = table.scan(**params)
        items.extend(resp.get("Items", []))
        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        params["ExclusiveStartKey"] = lek

    print(f"  Total records: {len(items)}")

    # グループ化: 更新が必要なレコードを収集
    updates = []
    for item in items:
        old_name = item.get("shipName", "")
        new_name = old_to_new.get(old_name)

        if not new_name:
            # マッピングにない場合、単純にUPPERCASE化（ケース統一のみ）
            upper_name = old_name.upper()
            if upper_name != old_name:
                new_name = upper_name

        if not new_name:
            continue

        updates.append({"old_item": item, "new_name": new_name})

    print(f"  Records to update: {len(updates)}")

    if dry_run:
        for u in updates[:10]:
            old_name = u["old_item"]["shipName"]
            print(f"    {old_name} -> {u['new_name']}")
        if len(updates) > 10:
            print(f"    ... and {len(updates) - 10} more")
        return len(updates)

    # Detect key schema
    desc = boto3.client("dynamodb").describe_table(TableName=table_name)
    key_schema = {k["KeyType"]: k["AttributeName"] for k in desc["Table"]["KeySchema"]}
    pk_attr = key_schema["HASH"]
    sk_attr = key_schema.get("RANGE")
    print(f"  Key schema: PK={pk_attr}, SK={sk_attr}")

    # Use resource-level delete + put (simpler, handles all DynamoDB types correctly)
    updated = 0
    errors = 0

    for u in updates:
        old_item = u["old_item"]
        new_name = u["new_name"]
        old_name = old_item[pk_attr]

        # Build key for delete
        delete_key = {pk_attr: old_name}
        if sk_attr:
            delete_key[sk_attr] = old_item[sk_attr]

        # Build new record
        new_record = dict(old_item)
        new_record[pk_attr] = new_name

        try:
            table.delete_item(Key=delete_key)
            table.put_item(Item=new_record)
            updated += 1
            if updated % 100 == 0:
                print(f"    Updated {updated}/{len(updates)}")
                time.sleep(0.2)
        except Exception as e:
            errors += 1
            if errors <= 5:
                print(f"    Error: {old_name} -> {new_name}: {e}")

    if errors > 5:
        print(f"    ... {errors} total errors")

    print(f"  Updated: {updated}")
    return updated


def update_players_array(players, ship_id_to_name, old_to_new):
    """プレイヤー配列内のshipNameを更新。変更があればTrueを返す。"""
    changed = False
    for player in players:
        old_name = player.get("shipName", "")
        ship_id = player.get("shipId", 0)

        new_name = resolve_new_name(old_name, ship_id, ship_id_to_name, old_to_new)
        if new_name and new_name != old_name:
            player["shipName"] = new_name
            changed = True

    return changed


def backfill_battle_tables(stage, dry_run, ship_id_to_display, old_to_new):
    """バトルテーブル群のMATCH/STATS/UPLOADレコードを更新（Title Case表示名に統一）"""
    dynamodb = boto3.resource("dynamodb")
    total_updated = 0

    for game_type in ["clan", "ranked", "random", "other"]:
        table_name = f"wows-{game_type}-battles-{stage}"
        table = dynamodb.Table(table_name)
        print(f"\n=== Battle Table: {table_name} ===")

        params = {}
        scanned = 0
        updated = 0

        while True:
            resp = table.scan(**params)
            for item in resp.get("Items", []):
                scanned += 1
                record_type = item.get("recordType", "")
                arena_id = item.get("arenaUniqueID", "")
                changed = False

                if record_type == "MATCH":
                    allies = item.get("allies", [])
                    enemies = item.get("enemies", [])
                    c1 = update_players_array(allies, ship_id_to_display, old_to_new)
                    c2 = update_players_array(enemies, ship_id_to_display, old_to_new)
                    changed = c1 or c2

                    if changed and not dry_run:
                        table.update_item(
                            Key={"arenaUniqueID": arena_id, "recordType": record_type},
                            UpdateExpression="SET allies = :a, enemies = :e",
                            ExpressionAttributeValues={":a": allies, ":e": enemies},
                        )

                elif record_type == "STATS":
                    stats = item.get("allPlayersStats", [])
                    changed = update_players_array(stats, ship_id_to_display, old_to_new)

                    if changed and not dry_run:
                        table.update_item(
                            Key={"arenaUniqueID": arena_id, "recordType": record_type},
                            UpdateExpression="SET allPlayersStats = :s",
                            ExpressionAttributeValues={":s": stats},
                        )

                elif record_type.startswith("UPLOAD#"):
                    own = item.get("ownPlayer", {})
                    if own:
                        old_name = own.get("shipName", "")
                        ship_id = own.get("shipId", 0)
                        new_name = resolve_new_name(old_name, ship_id, ship_id_to_display, old_to_new)
                        if new_name and new_name != old_name:
                            own["shipName"] = new_name
                            changed = True

                            if not dry_run:
                                table.update_item(
                                    Key={"arenaUniqueID": arena_id, "recordType": record_type},
                                    UpdateExpression="SET ownPlayer = :op",
                                    ExpressionAttributeValues={":op": own},
                                )

                if changed:
                    updated += 1

            lek = resp.get("LastEvaluatedKey")
            if not lek:
                break
            params["ExclusiveStartKey"] = lek

        print(f"  Scanned: {scanned}, Updated: {updated}")
        total_updated += updated

    return total_updated


def backfill_replays_table(stage, dry_run, ship_id_to_display, old_to_new):
    """wows-replays テーブルのshipNameを更新（Title Case表示名に統一）"""
    dynamodb = boto3.resource("dynamodb")
    table_name = f"wows-replays-{stage}"
    table = dynamodb.Table(table_name)

    print(f"\n=== Replays Table: {table_name} ===")

    params = {}
    scanned = 0
    updated = 0

    while True:
        resp = table.scan(**params)
        for item in resp.get("Items", []):
            scanned += 1
            arena_id = item.get("arenaUniqueID", "")
            changed = False
            update_expr_parts = []
            expr_values = {}

            # allies / enemies
            allies = item.get("allies", [])
            enemies = item.get("enemies", [])
            c1 = update_players_array(allies, ship_id_to_display, old_to_new)
            c2 = update_players_array(enemies, ship_id_to_display, old_to_new)
            if c1:
                update_expr_parts.append("allies = :a")
                expr_values[":a"] = allies
                changed = True
            if c2:
                update_expr_parts.append("enemies = :e")
                expr_values[":e"] = enemies
                changed = True

            # ownPlayer
            own = item.get("ownPlayer", {})
            if own:
                old_name = own.get("shipName", "")
                ship_id = own.get("shipId", 0)
                new_name = resolve_new_name(old_name, ship_id, ship_id_to_display, old_to_new)
                if new_name and new_name != old_name:
                    own["shipName"] = new_name
                    update_expr_parts.append("ownPlayer = :op")
                    expr_values[":op"] = own
                    changed = True

            # allPlayersStats
            stats = item.get("allPlayersStats", [])
            if stats:
                c3 = update_players_array(stats, ship_id_to_display, old_to_new)
                if c3:
                    update_expr_parts.append("allPlayersStats = :s")
                    expr_values[":s"] = stats
                    changed = True

            # playerShip (top-level field)
            player_ship = item.get("playerShip", "")
            player_ship_id = item.get("playerShipId", 0)
            if player_ship:
                new_name = resolve_new_name(
                    player_ship, player_ship_id, ship_id_to_display, old_to_new
                )
                if new_name and new_name != player_ship:
                    update_expr_parts.append("playerShip = :ps")
                    expr_values[":ps"] = new_name
                    changed = True

            if changed and not dry_run and update_expr_parts:
                key = {
                    "arenaUniqueID": arena_id,
                    "playerID": item.get("playerID"),
                }
                try:
                    table.update_item(
                        Key=key,
                        UpdateExpression="SET " + ", ".join(update_expr_parts),
                        ExpressionAttributeValues=expr_values,
                    )
                except Exception as e:
                    print(f"    Error updating {arena_id}: {e}")

            if changed:
                updated += 1

        lek = resp.get("LastEvaluatedKey")
        if not lek:
            break
        params["ExclusiveStartKey"] = lek

    print(f"  Scanned: {scanned}, Updated: {updated}")
    return updated


def main():
    parser = argparse.ArgumentParser(description="Backfill ship names to Rust localized format (UPPERCASE)")
    parser.add_argument("--dry-run", action="store_true", default=os.environ.get("DRY_RUN", "").lower() == "true")
    parser.add_argument("--stage", default="prod", choices=["dev", "prod"])
    parser.add_argument("--target", default="all", choices=["all", "ship-index", "battles", "replays"])
    args = parser.parse_args()

    dry_run = args.dry_run
    stage = args.stage

    if dry_run:
        print("*** DRY RUN MODE ***")
    print(f"Stage: {stage}")
    print(f"Target: {args.target}")

    ship_id_to_upper, ship_id_to_display, old_to_upper, old_to_display = load_mapping()
    print(f"Mapping loaded: {len(ship_id_to_upper)} shipId entries, {len(old_to_upper)} index changes, {len(old_to_display)} display changes")

    total = 0

    if args.target in ("all", "ship-index"):
        # Ship index uses UPPERCASE for search
        total += backfill_ship_index(stage, dry_run, ship_id_to_upper, old_to_upper)

    if args.target in ("all", "battles"):
        # Battle tables use Title Case for display
        total += backfill_battle_tables(stage, dry_run, ship_id_to_display, old_to_display)

    if args.target in ("all", "replays"):
        # Replays table uses Title Case for display
        total += backfill_replays_table(stage, dry_run, ship_id_to_display, old_to_display)

    action = "would update" if dry_run else "updated"
    print(f"\n=== Total {action}: {total} records ===")


if __name__ == "__main__":
    main()
