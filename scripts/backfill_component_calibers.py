#!/usr/bin/env python3
"""
艦艇コンポーネント口径バックフィルスクリプト

既存のallPlayersStatsに含まれるshipComponentsの主砲・魚雷を
口径表示（例: "460mm"）に更新する
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

from utils.ship_modules import get_component_caliber

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


def is_caliber_format(value):
    """既に口径形式（例: "460mm"）かどうかを判定"""
    if not value:
        return False
    return value.endswith("mm")


def update_components_with_caliber(existing_stats):
    """
    既存のallPlayersStatsのshipComponentsを口径表示に更新

    Args:
        existing_stats: 既存のallPlayersStats

    Returns:
        (updated_stats, updated_count): 更新されたstatsと更新されたコンポーネント数
    """
    if not existing_stats:
        return existing_stats, 0

    updated_stats = []
    updated_count = 0

    for stats in existing_stats:
        updated = dict(stats)
        ship_components = stats.get("shipComponents", {})
        ship_id = stats.get("shipId", 0)

        if not ship_components or not ship_id:
            updated_stats.append(updated)
            continue

        new_components = dict(ship_components)
        modified = False

        # 主砲を口径に更新
        if "artillery" in ship_components:
            current_value = ship_components["artillery"]
            if current_value and not is_caliber_format(current_value):
                caliber = get_component_caliber(ship_id, "artillery", current_value)
                if caliber:
                    new_components["artillery"] = caliber
                    modified = True
                    updated_count += 1

        # 魚雷を口径に更新
        if "torpedoes" in ship_components:
            current_value = ship_components["torpedoes"]
            if current_value and not is_caliber_format(current_value):
                caliber = get_component_caliber(ship_id, "torpedoes", current_value)
                if caliber:
                    new_components["torpedoes"] = caliber
                    modified = True
                    updated_count += 1

        if modified:
            updated["shipComponents"] = new_components

        updated_stats.append(updated)

    return updated_stats, updated_count


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

    # shipComponentsがないレコードはスキップ
    has_components = any(p.get("shipComponents") for p in existing_stats)
    if not has_components:
        return {"status": "skipped", "reason": "no_ship_components"}

    # 口径に更新
    updated_stats, updated_count = update_components_with_caliber(existing_stats)

    if updated_count == 0:
        return {"status": "skipped", "reason": "already_caliber_or_no_mapping"}

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
        "updated_count": updated_count,
    }


def main():
    print("艦艇コンポーネント口径バックフィルを開始...")
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
        "total_updated": 0,
    }

    for i, (arena_id, records) in enumerate(matches.items()):
        if (i + 1) % 50 == 0:
            print(f"   処理中: {i + 1}/{len(matches)}")

        try:
            result = process_match(table, arena_id, records)

            if result["status"] == "updated":
                stats["updated"] += 1
                stats["total_updated"] += result.get("updated_count", 0)
                print(f"   [更新] {arena_id}: {result['updated_count']}件のコンポーネントを口径に更新")
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
    print(f"  口径更新されたコンポーネント: {stats['total_updated']} 件")

    if DRY_RUN:
        print("\n[注意] DRY_RUNモードのため、DynamoDBは更新されていません。")
        print("実際に更新するには: DRY_RUN=false python scripts/backfill_component_calibers.py")


if __name__ == "__main__":
    main()
