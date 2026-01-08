#!/usr/bin/env python3
"""
BattleStats詳細フィールドのバックフィルスクリプト

既存のリプレイファイルから被ダメ内訳、潜在ダメ内訳、critsなどの
詳細統計情報を抽出し、DynamoDBのallPlayersStatsを更新する
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

from parsers.battle_stats_extractor import extract_battle_stats, extract_hidden_data
from parsers.battlestats_parser import BattleStatsParser
from utils.captain_skills import map_player_to_skills
from utils.ship_modules import map_player_to_modules

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


def build_all_players_stats(all_stats: dict, record: dict, hidden_data: dict = None) -> list:
    """
    全プレイヤーの統計情報をチーム情報と紐付けて配列で返す
    """
    # プレイヤー名からチーム情報と艦船情報をマッピング
    player_team_map = {}

    # ownPlayer
    own_player = record.get("ownPlayer", {})
    if isinstance(own_player, list):
        own_player = own_player[0] if own_player else {}
    if own_player and own_player.get("name"):
        player_team_map[own_player["name"]] = {
            "team": "ally",
            "shipId": own_player.get("shipId", 0),
            "shipName": own_player.get("shipName", ""),
            "isOwn": True,
        }

    # allies
    for ally in record.get("allies", []):
        if ally.get("name"):
            player_team_map[ally["name"]] = {
                "team": "ally",
                "shipId": ally.get("shipId", 0),
                "shipName": ally.get("shipName", ""),
                "isOwn": False,
            }

    # enemies
    for enemy in record.get("enemies", []):
        if enemy.get("name"):
            player_team_map[enemy["name"]] = {
                "team": "enemy",
                "shipId": enemy.get("shipId", 0),
                "shipName": enemy.get("shipName", ""),
                "isOwn": False,
            }

    # hiddenデータから艦長スキルと艦艇コンポーネントを抽出
    player_skills_map = {}
    player_modules_map = {}
    if hidden_data:
        try:
            player_skills_map = map_player_to_skills(hidden_data)
        except Exception as e:
            print(f"    Warning: Failed to extract captain skills: {e}")

        try:
            player_modules_map = map_player_to_modules(hidden_data)
        except Exception as e:
            print(f"    Warning: Failed to extract ship modules: {e}")

    # 全プレイヤーの統計を作成
    result = []
    for player_id, stats in all_stats.items():
        player_name = stats.get("player_name", "")
        team_info = player_team_map.get(player_name, {"team": "unknown", "shipId": 0, "shipName": ""})

        # DynamoDB形式に変換（全フィールド含む）
        stats_data = BattleStatsParser.to_dynamodb_format(stats)

        # チーム情報と艦船情報を追加
        stats_data["team"] = team_info["team"]
        stats_data["shipId"] = team_info.get("shipId", 0)
        stats_data["shipName"] = team_info.get("shipName", "")
        stats_data["isOwn"] = team_info.get("isOwn", False)

        # 艦長スキルを追加
        if player_name in player_skills_map:
            stats_data["captainSkills"] = player_skills_map[player_name]

        # 艦艇コンポーネントを追加
        if player_name in player_modules_map:
            modules_info = player_modules_map[player_name]
            stats_data["shipComponents"] = modules_info.get("components", {})

        result.append(stats_data)

    # ダメージ降順でソート
    result.sort(key=lambda x: x.get("damage", 0), reverse=True)

    return result


def check_needs_update(existing_stats: list) -> bool:
    """
    allPlayersStatsが更新が必要かチェック

    新しいフィールド（被ダメ内訳、潜在ダメ内訳、crits）がないかチェック
    """
    if not existing_stats:
        return False  # allPlayersStatsがない場合はスキップ（別の問題）

    # 最初のプレイヤーの統計をチェック
    first_player = existing_stats[0]

    # 新しいフィールドが存在するかチェック
    new_fields = [
        "receivedDamageAP",
        "receivedDamageHE",
        "potentialDamageArt",
        "potentialDamageTpd",
        "crits",
    ]

    # いずれかの新フィールドがなければ更新が必要
    for field in new_fields:
        if field not in first_player:
            return True

    return False


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

    # 更新が必要かチェック
    if not check_needs_update(existing_stats):
        return {"status": "skipped", "reason": "already_has_new_fields"}

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

        # BattleStatsを抽出
        battle_results = extract_battle_stats(tmp_path)
        if not battle_results:
            return {"status": "skipped", "reason": "no_battle_results"}

        # hiddenデータを抽出
        hidden_data = None
        try:
            hidden_data = extract_hidden_data(tmp_path)
        except Exception:
            pass

        # playersPublicInfoを取得
        players_public_info = battle_results.get("playersPublicInfo", {})
        if not players_public_info:
            return {"status": "skipped", "reason": "no_players_public_info"}

        # 全プレイヤーの統計を解析
        all_stats = BattleStatsParser.parse_all_players(players_public_info)

        # allPlayersStatsを再構築
        updated_stats = build_all_players_stats(all_stats, first_record, hidden_data)

        if not updated_stats:
            return {"status": "skipped", "reason": "no_updated_stats"}

        # 追加されたフィールド数をカウント
        new_fields_count = 0
        if updated_stats:
            first_player = updated_stats[0]
            for field in ["receivedDamageAP", "potentialDamageArt", "crits"]:
                if field in first_player:
                    new_fields_count += 1

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
            "players_count": len(updated_stats),
            "new_fields_count": new_fields_count,
        }

    except Exception as e:
        return {"status": "error", "reason": str(e)}

    finally:
        # 一時ファイルを削除
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def main():
    print("BattleStats詳細フィールドのバックフィルを開始...")
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
        "total_players": 0,
    }

    for i, (arena_id, records) in enumerate(matches.items()):
        if (i + 1) % 10 == 0:
            print(f"   処理中: {i + 1}/{len(matches)}")

        result = process_match(s3_client, table, arena_id, records)

        if result["status"] == "updated":
            stats["updated"] += 1
            stats["total_players"] += result.get("players_count", 0)
            print(f"   [更新] {arena_id}: {result['players_count']}名のプレイヤー")
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
    print(f"  更新されたプレイヤー統計: {stats['total_players']} 件")

    if DRY_RUN:
        print("\n[注意] DRY_RUNモードのため、DynamoDBは更新されていません。")
        print("実際に更新するには: DRY_RUN=false python scripts/backfill_battlestats.py")


if __name__ == "__main__":
    main()
