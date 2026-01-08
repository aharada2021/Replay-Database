#!/usr/bin/env python3
"""
艦長スキル日本語化バックフィルスクリプト

既存のallPlayersStatsに含まれる英語スキル名を日本語に変換する
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

from utils.captain_skills import SKILL_DISPLAY_TO_JAPANESE

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


def translate_skill_to_japanese(skill_name: str) -> str:
    """英語スキル名を日本語に変換"""
    return SKILL_DISPLAY_TO_JAPANESE.get(skill_name, skill_name)


def convert_skills_to_japanese(existing_stats):
    """
    既存のallPlayersStatsのcaptainSkillsを日本語に変換

    Args:
        existing_stats: 既存のallPlayersStats

    Returns:
        (updated_stats, converted_count): 更新されたstatsと変換されたスキル数
    """
    if not existing_stats:
        return existing_stats, 0

    updated_stats = []
    converted_count = 0

    for stats in existing_stats:
        updated = dict(stats)
        captain_skills = stats.get("captainSkills", [])

        if captain_skills:
            # 既に日本語の場合はスキップ（日本語かどうかの判定）
            # 最初のスキルがASCII文字のみなら英語と判断
            first_skill = captain_skills[0] if captain_skills else ""
            is_english = first_skill.isascii() if first_skill else True

            if is_english:
                # 英語スキル名を日本語に変換
                japanese_skills = [translate_skill_to_japanese(s) for s in captain_skills]
                updated["captainSkills"] = japanese_skills
                converted_count += len([s for s, j in zip(captain_skills, japanese_skills) if s != j])

        updated_stats.append(updated)

    return updated_stats, converted_count


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

    # captainSkillsがないレコードはスキップ
    has_skills = any(p.get("captainSkills") for p in existing_stats)
    if not has_skills:
        return {"status": "skipped", "reason": "no_captain_skills"}

    # 日本語に変換
    updated_stats, converted_count = convert_skills_to_japanese(existing_stats)

    if converted_count == 0:
        return {"status": "skipped", "reason": "already_japanese_or_no_mapping"}

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
        "converted_count": converted_count,
    }


def main():
    print("艦長スキル日本語化バックフィルを開始...")
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
        "total_converted": 0,
    }

    for i, (arena_id, records) in enumerate(matches.items()):
        if (i + 1) % 50 == 0:
            print(f"   処理中: {i + 1}/{len(matches)}")

        try:
            result = process_match(table, arena_id, records)

            if result["status"] == "updated":
                stats["updated"] += 1
                stats["total_converted"] += result.get("converted_count", 0)
                print(f"   [更新] {arena_id}: {result['converted_count']}件のスキルを日本語化")
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
    print(f"  日本語化されたスキル: {stats['total_converted']} 件")

    if DRY_RUN:
        print("\n[注意] DRY_RUNモードのため、DynamoDBは更新されていません。")
        print("実際に更新するには: DRY_RUN=false python scripts/backfill_skills_japanese.py")


if __name__ == "__main__":
    main()
