#!/usr/bin/env python3
"""
艦長スキル・艦艇コンポーネントのバックフィルスクリプト

既存のリプレイファイルから艦長スキルと艦艇コンポーネント情報を抽出し、
DynamoDBのallPlayersStatsを更新する
"""

import os
import sys
import tempfile
from pathlib import Path

import boto3
from botocore.exceptions import ClientError

# replays_unpack_upstreamをパスに追加
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
UNPACK_PATH = PROJECT_ROOT / "replays_unpack_upstream"
SRC_PATH = PROJECT_ROOT / "src"

sys.path.insert(0, str(UNPACK_PATH))
sys.path.insert(0, str(SRC_PATH))

from utils.captain_skills import map_player_to_skills
from parsers.battle_stats_extractor import extract_hidden_data
from parsers.battlestats_parser import BattleStatsParser

# 環境変数
REPLAYS_TABLE = os.environ.get("REPLAYS_TABLE", "wows-replays-dev")
REPLAY_BUCKET = os.environ.get("REPLAY_BUCKET", "wows-replay-bot-dev-temp")
REGION = os.environ.get("AWS_REGION", "ap-northeast-1")

# ドライラン（Trueの場合はDynamoDB更新をスキップ）
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"


def get_dynamodb():
    return boto3.resource("dynamodb", region_name=REGION)


def get_s3():
    return boto3.client("s3", region_name=REGION)


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


def download_replay(s3_client, s3_key, local_path):
    """S3からリプレイファイルをダウンロード"""
    try:
        s3_client.download_file(REPLAY_BUCKET, s3_key, local_path)
        return True
    except ClientError as e:
        print(f"    S3ダウンロードエラー: {e}")
        return False


def build_all_players_stats_with_skills(existing_stats, hidden_data):
    """
    既存のallPlayersStatsに艦長スキルと艦艇コンポーネントを追加

    Args:
        existing_stats: 既存のallPlayersStats
        hidden_data: リプレイのhiddenデータ

    Returns:
        更新されたallPlayersStats
    """
    if not existing_stats or not hidden_data:
        return existing_stats

    # プレイヤー名 -> スキルのマッピングを作成
    player_skills_map = {}

    try:
        player_skills_map = map_player_to_skills(hidden_data)
    except Exception as e:
        print(f"    スキルマッピングエラー: {e}")

    # 既存のstatsを更新
    updated_stats = []
    skills_added = 0

    for stats in existing_stats:
        player_name = stats.get("playerName", "")
        updated = dict(stats)

        # 艦長スキルを追加
        if player_name in player_skills_map and player_skills_map[player_name]:
            updated["captainSkills"] = player_skills_map[player_name]
            skills_added += 1

        updated_stats.append(updated)

    return updated_stats, skills_added, 0


def process_match(s3_client, table, arena_id, records):
    """
    1つの試合を処理

    Args:
        s3_client: S3クライアント
        table: DynamoDBテーブル
        arena_id: 試合ID
        records: この試合のDynamoDBレコード
    """
    # 既存のallPlayersStatsを確認
    first_record = records[0]
    existing_stats = first_record.get("allPlayersStats", [])

    # 既にスキル情報がある場合はスキップ
    if existing_stats:
        has_skills = any(p.get("captainSkills") for p in existing_stats)
        if has_skills:
            return {"status": "skipped", "reason": "already_has_skills"}

    # S3キーを持つレコードを探す
    s3_key = None
    for record in records:
        if record.get("s3Key"):
            s3_key = record.get("s3Key")
            break

    if not s3_key:
        return {"status": "skipped", "reason": "no_s3_key"}

    # リプレイファイルをダウンロード
    with tempfile.NamedTemporaryFile(suffix=".wowsreplay", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        if not download_replay(s3_client, s3_key, tmp_path):
            return {"status": "error", "reason": "download_failed"}

        # hiddenデータを抽出
        hidden_data = extract_hidden_data(tmp_path)
        if not hidden_data:
            return {"status": "skipped", "reason": "no_hidden_data"}

        # allPlayersStatsがない場合は処理できない
        if not existing_stats:
            return {"status": "skipped", "reason": "no_existing_stats"}

        # スキルとモジュール情報を追加
        updated_stats, skills_count, modules_count = build_all_players_stats_with_skills(
            existing_stats, hidden_data
        )

        if skills_count == 0 and modules_count == 0:
            return {"status": "skipped", "reason": "no_skills_found"}

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
            "skills_count": skills_count,
            "modules_count": modules_count,
        }

    except Exception as e:
        return {"status": "error", "reason": str(e)}

    finally:
        # 一時ファイルを削除
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def main():
    print("艦長スキル・艦艇コンポーネントのバックフィルを開始...")
    print(f"DRY_RUN: {DRY_RUN}")
    print(f"リプレイテーブル: {REPLAYS_TABLE}")
    print(f"S3バケット: {REPLAY_BUCKET}")

    dynamodb = get_dynamodb()
    s3_client = get_s3()
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
        "total_skills": 0,
        "total_modules": 0,
    }

    for i, (arena_id, records) in enumerate(matches.items()):
        if (i + 1) % 10 == 0:
            print(f"   処理中: {i + 1}/{len(matches)}")

        result = process_match(s3_client, table, arena_id, records)

        if result["status"] == "updated":
            stats["updated"] += 1
            stats["total_skills"] += result.get("skills_count", 0)
            stats["total_modules"] += result.get("modules_count", 0)
            print(f"   [更新] {arena_id}: スキル={result['skills_count']}, モジュール={result['modules_count']}")
        elif result["status"] == "error":
            stats["error"] += 1
            print(f"   [エラー] {arena_id}: {result['reason']}")
        else:
            stats["skipped"] += 1

    # 結果を表示
    print("\n" + "=" * 50)
    print("処理完了!")
    print(f"  更新: {stats['updated']} 件")
    print(f"  スキップ: {stats['skipped']} 件")
    print(f"  エラー: {stats['error']} 件")
    print(f"  追加されたスキル情報: {stats['total_skills']} 件")
    print(f"  追加されたモジュール情報: {stats['total_modules']} 件")

    if DRY_RUN:
        print("\n[注意] DRY_RUNモードのため、DynamoDBは更新されていません。")
        print("実際に更新するには: DRY_RUN=false python scripts/backfill_captain_skills.py")


if __name__ == "__main__":
    main()
