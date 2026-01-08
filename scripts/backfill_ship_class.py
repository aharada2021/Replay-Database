#!/usr/bin/env python3
"""
艦種（shipClass）のバックフィルスクリプト

既存のallPlayersStatsレコードにshipClassフィールドを追加する。
shipIdから ships.json を参照して艦種を特定する。
"""

import os
import sys
from pathlib import Path

import boto3

# srcをパスに追加
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_PATH = PROJECT_ROOT / "src"

sys.path.insert(0, str(SRC_PATH))

from utils.captain_skills import get_ship_class_from_params_id

# 環境変数
REPLAYS_TABLE = os.environ.get("REPLAYS_TABLE", "wows-replays-dev")
REGION = os.environ.get("AWS_REGION", "ap-northeast-1")

# ドライラン（Trueの場合はDynamoDB更新をスキップ）
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"


def get_dynamodb():
    return boto3.resource("dynamodb", region_name=REGION)


def scan_all_replays(table):
    """全リプレイをスキャン"""
    items = []
    response = table.scan()
    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))
        print(f"  Scanned {len(items)} items...")

    return items


def group_by_match(replays):
    """arenaUniqueIDでグループ化"""
    matches = {}
    for item in replays:
        arena_id = item.get("arenaUniqueID", "")
        if not arena_id:
            continue
        if arena_id not in matches:
            matches[arena_id] = []
        matches[arena_id].append(item)
    return matches


def add_ship_class_to_stats(existing_stats):
    """
    既存のallPlayersStatsにshipClassを追加

    Args:
        existing_stats: 既存のallPlayersStats

    Returns:
        (updated_stats, ship_class_count): 更新されたstatsと追加されたshipClass数
    """
    if not existing_stats:
        return existing_stats, 0

    updated_stats = []
    ship_class_count = 0

    for stats in existing_stats:
        updated = dict(stats)
        ship_id = stats.get("shipId", 0)

        # 既にshipClassがある場合はスキップ
        if stats.get("shipClass"):
            updated_stats.append(updated)
            continue

        # shipIdから艦種を取得
        if ship_id:
            ship_class = get_ship_class_from_params_id(ship_id)
            if ship_class:
                updated["shipClass"] = ship_class
                ship_class_count += 1

        updated_stats.append(updated)

    return updated_stats, ship_class_count


def process_match(table, arena_id, records):
    """
    1つの試合を処理

    Args:
        table: DynamoDBテーブル
        arena_id: 試合ID
        records: この試合のDynamoDBレコード
    """
    # 既存のallPlayersStatsを確認
    first_record = records[0]
    existing_stats = first_record.get("allPlayersStats", [])

    if not existing_stats:
        return {"status": "skipped", "reason": "no_existing_stats"}

    # 既に全員にshipClassがある場合はスキップ
    all_have_ship_class = all(p.get("shipClass") for p in existing_stats)
    if all_have_ship_class:
        return {"status": "skipped", "reason": "already_has_ship_class"}

    # shipClassを追加
    updated_stats, ship_class_count = add_ship_class_to_stats(existing_stats)

    if ship_class_count == 0:
        return {"status": "skipped", "reason": "no_ship_class_added"}

    # DynamoDBを更新
    if not DRY_RUN:
        for record in records:
            table.update_item(
                Key={
                    "arenaUniqueID": record["arenaUniqueID"],
                    "playerID": record["playerID"],
                },
                UpdateExpression="SET allPlayersStats = :stats",
                ExpressionAttributeValues={":stats": updated_stats},
            )

    return {
        "status": "updated",
        "ship_class_count": ship_class_count,
    }


def main():
    print("艦種（shipClass）のバックフィルを開始...")
    print(f"DRY_RUN: {DRY_RUN}")
    print(f"リプレイテーブル: {REPLAYS_TABLE}")

    dynamodb = get_dynamodb()
    table = dynamodb.Table(REPLAYS_TABLE)

    # 全リプレイをスキャン
    print("\n1. リプレイデータをスキャン中...")
    replays = scan_all_replays(table)
    print(f"   {len(replays)} 件のリプレイレコードを取得")

    # arenaUniqueIDでグループ化
    matches = group_by_match(replays)
    print(f"   {len(matches)} 件のユニークな試合")

    # 各試合を処理
    print("\n2. 各試合を処理中...")
    stats = {
        "updated": 0,
        "skipped": 0,
        "error": 0,
        "total_ship_class": 0,
    }

    for i, (arena_id, records) in enumerate(matches.items()):
        if (i + 1) % 50 == 0:
            print(f"   処理中: {i + 1}/{len(matches)}")

        try:
            result = process_match(table, arena_id, records)

            if result["status"] == "updated":
                stats["updated"] += 1
                stats["total_ship_class"] += result.get("ship_class_count", 0)
                print(f"   [更新] {arena_id}: shipClass={result['ship_class_count']}件追加")
            elif result["status"] == "error":
                stats["error"] += 1
                print(f"   [エラー] {arena_id}: {result['reason']}")
            else:
                stats["skipped"] += 1
        except Exception as e:
            stats["error"] += 1
            print(f"   [エラー] {arena_id}: {e}")

    # 結果を表示
    print("\n" + "=" * 50)
    print("処理完了!")
    print(f"  更新: {stats['updated']} 件")
    print(f"  スキップ: {stats['skipped']} 件")
    print(f"  エラー: {stats['error']} 件")
    print(f"  追加されたshipClass: {stats['total_ship_class']} 件")

    if DRY_RUN:
        print("\n[注意] DRY_RUNモードのため、DynamoDBは更新されていません。")
        print("実際に更新するには: DRY_RUN=false python scripts/backfill_ship_class.py")


if __name__ == "__main__":
    main()
