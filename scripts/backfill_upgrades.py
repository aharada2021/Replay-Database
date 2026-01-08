#!/usr/bin/env python3
"""
アップグレード（近代化改修）バックフィルスクリプト

既存のallPlayersStatsレコードにupgradesフィールドを追加する。
リプレイファイルをS3からダウンロードしてhiddenデータから抽出する。
"""

import os
import sys
import tempfile
from pathlib import Path

import boto3

# srcをパスに追加
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_PATH = PROJECT_ROOT / "src"
REPLAYS_UNPACK_PATH = PROJECT_ROOT / "replays_unpack_upstream"

sys.path.insert(0, str(SRC_PATH))
sys.path.insert(0, str(REPLAYS_UNPACK_PATH))

from parsers.battle_stats_extractor import extract_hidden_data
from utils.upgrades import map_player_to_upgrades

# 環境変数
REPLAYS_TABLE = os.environ.get("REPLAYS_TABLE", "wows-replays-dev")
TEMP_BUCKET = os.environ.get("TEMP_BUCKET", "wows-replay-bot-dev-temp")
REGION = os.environ.get("AWS_REGION", "ap-northeast-1")

# ドライラン（Trueの場合はDynamoDB更新をスキップ）
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"


def get_dynamodb():
    return boto3.resource("dynamodb", region_name=REGION)


def get_s3_client():
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


def download_replay_file(s3_client, s3_key):
    """S3からリプレイファイルをダウンロード"""
    tmp_path = None
    with tempfile.NamedTemporaryFile(suffix=".wowsreplay", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)
        s3_client.download_fileobj(TEMP_BUCKET, s3_key, tmp_file)
    return tmp_path


def add_upgrades_to_stats(existing_stats, player_upgrades_map):
    """
    既存のallPlayersStatsにupgradesを追加

    Args:
        existing_stats: 既存のallPlayersStats
        player_upgrades_map: プレイヤー名 -> upgradesリストのマップ

    Returns:
        (updated_stats, upgrade_count): 更新されたstatsと追加されたupgrades数
    """
    if not existing_stats:
        return existing_stats, 0

    updated_stats = []
    upgrade_count = 0

    for stats in existing_stats:
        updated = dict(stats)
        player_name = stats.get("playerName", "")

        # 既にupgradesがある場合はスキップ
        if stats.get("upgrades"):
            updated_stats.append(updated)
            continue

        # プレイヤー名でアップグレードを検索
        if player_name and player_name in player_upgrades_map:
            upgrades = player_upgrades_map[player_name]
            if upgrades:
                updated["upgrades"] = upgrades
                upgrade_count += 1

        updated_stats.append(updated)

    return updated_stats, upgrade_count


def process_match(table, s3_client, arena_id, records):
    """
    1つの試合を処理

    Args:
        table: DynamoDBテーブル
        s3_client: S3クライアント
        arena_id: 試合ID
        records: この試合のDynamoDBレコード
    """
    # 既存のallPlayersStatsを確認
    first_record = records[0]
    existing_stats = first_record.get("allPlayersStats", [])

    if not existing_stats:
        return {"status": "skipped", "reason": "no_existing_stats"}

    # 既に全員にupgradesがある場合はスキップ
    all_have_upgrades = all(p.get("upgrades") for p in existing_stats)
    if all_have_upgrades:
        return {"status": "skipped", "reason": "already_has_upgrades"}

    # S3キーを取得（最初のレコードを使用）
    s3_key = first_record.get("s3Key")
    if not s3_key:
        return {"status": "skipped", "reason": "no_s3_key"}

    # リプレイファイルをダウンロード
    tmp_path = None
    try:
        tmp_path = download_replay_file(s3_client, s3_key)

        # hiddenデータを抽出
        hidden_data = extract_hidden_data(str(tmp_path))
        if not hidden_data:
            return {"status": "skipped", "reason": "no_hidden_data"}

        # アップグレードを抽出
        player_upgrades_map = map_player_to_upgrades(hidden_data)
        if not player_upgrades_map:
            return {"status": "skipped", "reason": "no_upgrades_found"}

        # allPlayersStatsにアップグレードを追加
        updated_stats, upgrade_count = add_upgrades_to_stats(existing_stats, player_upgrades_map)

        if upgrade_count == 0:
            return {"status": "skipped", "reason": "no_upgrades_added"}

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
            "upgrade_count": upgrade_count,
        }

    except Exception as e:
        return {"status": "error", "reason": str(e)}

    finally:
        # 一時ファイルを削除
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


def main():
    print("アップグレードのバックフィルを開始...")
    print(f"DRY_RUN: {DRY_RUN}")
    print(f"リプレイテーブル: {REPLAYS_TABLE}")
    print(f"S3バケット: {TEMP_BUCKET}")

    dynamodb = get_dynamodb()
    table = dynamodb.Table(REPLAYS_TABLE)
    s3_client = get_s3_client()

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
        "total_upgrades": 0,
    }

    for i, (arena_id, records) in enumerate(matches.items()):
        if (i + 1) % 10 == 0:
            print(f"   処理中: {i + 1}/{len(matches)}")

        try:
            result = process_match(table, s3_client, arena_id, records)

            if result["status"] == "updated":
                stats["updated"] += 1
                stats["total_upgrades"] += result.get("upgrade_count", 0)
                print(f"   [更新] {arena_id}: upgrades={result['upgrade_count']}名分追加")
            elif result["status"] == "error":
                stats["error"] += 1
                print(f"   [エラー] {arena_id}: {result['reason']}")
            else:
                stats["skipped"] += 1
                if result.get("reason") not in ["already_has_upgrades", "no_existing_stats"]:
                    print(f"   [スキップ] {arena_id}: {result['reason']}")
        except Exception as e:
            stats["error"] += 1
            print(f"   [エラー] {arena_id}: {e}")

    # 結果を表示
    print("\n" + "=" * 50)
    print("処理完了!")
    print(f"  更新: {stats['updated']} 件")
    print(f"  スキップ: {stats['skipped']} 件")
    print(f"  エラー: {stats['error']} 件")
    print(f"  追加されたプレイヤーアップグレード: {stats['total_upgrades']} 件")

    if DRY_RUN:
        print("\n[注意] DRY_RUNモードのため、DynamoDBは更新されていません。")
        print("実際に更新するには: DRY_RUN=false python scripts/backfill_upgrades.py")


if __name__ == "__main__":
    main()
