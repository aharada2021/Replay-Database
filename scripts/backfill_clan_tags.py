#!/usr/bin/env python3
"""
クランタグのバックフィルスクリプト

クラン戦のリプレイファイルからクランタグを抽出し、
DynamoDBのallyMainClanTagとenemyMainClanTagを更新する
"""

import os
import sys
import tempfile
from pathlib import Path
from collections import Counter

import boto3
from botocore.exceptions import ClientError

# replays_unpack_upstreamをパスに追加
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
UNPACK_PATH = PROJECT_ROOT / "replays_unpack_upstream"
SRC_PATH = PROJECT_ROOT / "src"

sys.path.insert(0, str(UNPACK_PATH))
sys.path.insert(0, str(SRC_PATH))

from parsers.battle_stats_extractor import extract_hidden_data
from core.replay_metadata import ReplayMetadataParser

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


def calculate_main_clan_tag(players):
    """
    プレイヤーリストから最も多いクランタグを計算

    Args:
        players: プレイヤー情報のリスト

    Returns:
        最も多いクランタグ、またはNone
    """
    if not players:
        return None

    # クランタグを持つプレイヤーのみを抽出
    clan_tags = [p.get("clanTag") for p in players if p.get("clanTag")]

    if not clan_tags:
        return None

    # 最も多いクランタグを取得
    counter = Counter(clan_tags)
    most_common = counter.most_common(1)

    return most_common[0][0] if most_common else None


def scan_clan_battles(table):
    """クラン戦のみをスキャン（GameTypeSortableIndexを使用）"""
    items = []

    # GSIを使用してクラン戦のみを取得
    response = table.query(
        IndexName="GameTypeSortableIndex",
        KeyConditionExpression="gameType = :gt",
        ExpressionAttributeValues={":gt": "clan"},
    )
    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.query(
            IndexName="GameTypeSortableIndex",
            KeyConditionExpression="gameType = :gt",
            ExpressionAttributeValues={":gt": "clan"},
            ExclusiveStartKey=response["LastEvaluatedKey"],
        )
        items.extend(response.get("Items", []))
        print(f"  Scanned {len(items)} clan battle items...")

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


def extract_players_info_from_metadata(metadata):
    """
    リプレイメタデータからプレイヤー情報を抽出

    Args:
        metadata: リプレイメタデータ

    Returns:
        {
            'own': [{'name': str}, ...],
            'allies': [{'name': str}, ...],
            'enemies': [{'name': str}, ...]
        }
    """
    players_info = {"own": [], "allies": [], "enemies": []}

    try:
        vehicles = metadata.get("vehicles", [])

        for player in vehicles:
            player_data = {
                "name": player.get("name", "Unknown"),
            }

            relation = player.get("relation", 2)

            if relation == 0:
                players_info["own"].append(player_data)
            elif relation == 1:
                players_info["allies"].append(player_data)
            else:
                players_info["enemies"].append(player_data)

    except Exception as e:
        print(f"Error extracting players info: {e}")

    return players_info


def enrich_players_with_clan_tags(players_info, hidden_data):
    """
    hidden_dataからクランタグを抽出してプレイヤー情報に追加

    Args:
        players_info: プレイヤー情報 {'own': [...], 'allies': [...], 'enemies': [...]}
        hidden_data: リプレイのhiddenデータ

    Returns:
        クランタグが追加されたプレイヤー情報
    """
    if not hidden_data:
        return players_info

    # hidden_dataからプレイヤー名→クランタグのマップを作成
    clan_tag_map = {}
    players_data = hidden_data.get("players", {})
    for player_id, player_info in players_data.items():
        player_name = player_info.get("name", "")
        clan_tag = player_info.get("clanTag", "")
        if player_name and clan_tag:
            clan_tag_map[player_name] = clan_tag

    # 各プレイヤーにクランタグを追加
    for category in ["own", "allies", "enemies"]:
        for player in players_info.get(category, []):
            player_name = player.get("name", "")
            if player_name in clan_tag_map:
                player["clanTag"] = clan_tag_map[player_name]

    return players_info


def process_match(s3_client, table, arena_id, records):
    """
    1つの試合を処理

    Args:
        s3_client: S3クライアント
        table: DynamoDBテーブル
        arena_id: 試合ID
        records: この試合のDynamoDBレコード
    """
    # 既存のクランタグを確認
    first_record = records[0]
    ally_tag = first_record.get("allyMainClanTag")
    enemy_tag = first_record.get("enemyMainClanTag")

    # 既にクランタグがある場合はスキップ
    if ally_tag or enemy_tag:
        return {"status": "skipped", "reason": "already_has_clan_tags"}

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

        # メタデータを解析
        metadata = ReplayMetadataParser.parse_replay_metadata(Path(tmp_path))
        if not metadata:
            return {"status": "error", "reason": "no_metadata"}

        # プレイヤー情報を抽出
        players_info = extract_players_info_from_metadata(metadata)

        # hiddenデータを抽出
        hidden_data = extract_hidden_data(tmp_path)
        if not hidden_data:
            return {"status": "skipped", "reason": "no_hidden_data"}

        # クランタグを追加
        players_info = enrich_players_with_clan_tags(players_info, hidden_data)

        # クランタグを計算
        own_player = players_info["own"][0] if players_info["own"] else {}
        ally_players = [own_player] + players_info.get("allies", []) if own_player else players_info.get("allies", [])
        ally_main_clan = calculate_main_clan_tag(ally_players)
        enemy_main_clan = calculate_main_clan_tag(players_info.get("enemies", []))

        if not ally_main_clan and not enemy_main_clan:
            return {"status": "skipped", "reason": "no_clan_tags_found"}

        # DynamoDBを更新
        if not DRY_RUN:
            for record in records:
                update_expr_parts = []
                expr_values = {}

                if ally_main_clan:
                    update_expr_parts.append("allyMainClanTag = :ally")
                    expr_values[":ally"] = ally_main_clan
                if enemy_main_clan:
                    update_expr_parts.append("enemyMainClanTag = :enemy")
                    expr_values[":enemy"] = enemy_main_clan

                if update_expr_parts:
                    table.update_item(
                        Key={
                            "arenaUniqueID": record["arenaUniqueID"],
                            "playerID": record["playerID"],
                        },
                        UpdateExpression="SET " + ", ".join(update_expr_parts),
                        ExpressionAttributeValues=expr_values,
                    )

        return {
            "status": "updated",
            "ally_clan": ally_main_clan,
            "enemy_clan": enemy_main_clan,
        }

    except Exception as e:
        return {"status": "error", "reason": str(e)}

    finally:
        # 一時ファイルを削除
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)


def main():
    print("クランタグのバックフィルを開始...")
    print(f"DRY_RUN: {DRY_RUN}")
    print(f"リプレイテーブル: {REPLAYS_TABLE}")
    print(f"S3バケット: {REPLAY_BUCKET}")

    dynamodb = get_dynamodb()
    s3_client = get_s3()
    table = dynamodb.Table(REPLAYS_TABLE)

    # クラン戦のみをスキャン
    print("\n1. クラン戦データをスキャン中...")
    replays = scan_clan_battles(table)
    print(f"   {len(replays)} 件のクラン戦レコードを取得")

    # arenaUniqueIDでグループ化
    matches = group_by_match(replays)
    print(f"   {len(matches)} 件のユニークなクラン戦")

    # 各試合を処理
    print("\n2. 各試合を処理中...")
    stats = {
        "updated": 0,
        "skipped": 0,
        "error": 0,
    }

    for i, (arena_id, records) in enumerate(matches.items()):
        if (i + 1) % 10 == 0:
            print(f"   処理中: {i + 1}/{len(matches)}")

        result = process_match(s3_client, table, arena_id, records)

        if result["status"] == "updated":
            stats["updated"] += 1
            print(f"   [更新] {arena_id}: ally={result['ally_clan']}, enemy={result['enemy_clan']}")
        elif result["status"] == "error":
            stats["error"] += 1
            print(f"   [エラー] {arena_id}: {result['reason']}")
        else:
            stats["skipped"] += 1
            if result["reason"] != "already_has_clan_tags":
                print(f"   [スキップ] {arena_id}: {result['reason']}")

    # 結果を表示
    print("\n" + "=" * 50)
    print("処理完了!")
    print(f"  更新: {stats['updated']} 件")
    print(f"  スキップ: {stats['skipped']} 件")
    print(f"  エラー: {stats['error']} 件")

    if DRY_RUN:
        print("\n[注意] DRY_RUNモードのため、DynamoDBは更新されていません。")
        print("実際に更新するには: DRY_RUN=false python scripts/backfill_clan_tags.py")


if __name__ == "__main__":
    main()
