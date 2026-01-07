"""
バトル結果抽出ハンドラー

S3にリプレイファイルがアップロードされた時にトリガーされ、
BattleStatsパケットから勝敗情報を抽出してDynamoDBを更新
"""

import json
import boto3
import tempfile
from pathlib import Path
import os
from urllib.parse import unquote_plus

from parsers.battle_stats_extractor import (
    extract_battle_stats,
    get_win_loss_clan_battle,
    get_experience_earned,
    get_arena_unique_id,
)
from parsers.battlestats_parser import BattleStatsParser
from utils import dynamodb
from utils.match_key import generate_match_key

# S3クライアント
s3_client = boto3.client("s3")
lambda_client = boto3.client("lambda")


def build_all_players_stats(all_stats: dict, record: dict) -> list:
    """
    全プレイヤーの統計情報をチーム情報と紐付けて配列で返す

    Args:
        all_stats: BattleStatsParser.parse_all_players()の結果
        record: DynamoDBレコード（allies, enemies, ownPlayerを含む）

    Returns:
        全プレイヤーの統計情報リスト（チーム、艦船情報付き）
    """
    # プレイヤー名からチーム情報と艦船情報をマッピング
    player_team_map = {}  # player_name -> {"team": str, "shipId": int, "shipName": str}

    # ownPlayer
    own_player = record.get("ownPlayer", {})
    if isinstance(own_player, list):
        own_player = own_player[0] if own_player else {}
    if own_player and own_player.get("name"):
        player_team_map[own_player["name"]] = {
            "team": "ally",  # 自分は味方チーム
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

    # 全プレイヤーの統計を作成
    result = []
    for player_id, stats in all_stats.items():
        player_name = stats.get("player_name", "")
        team_info = player_team_map.get(player_name, {"team": "unknown", "shipId": 0, "shipName": ""})

        # DynamoDB形式に変換
        stats_data = BattleStatsParser.to_dynamodb_format(stats)

        # チーム情報と艦船情報を追加
        stats_data["team"] = team_info["team"]
        stats_data["shipId"] = team_info.get("shipId", 0)
        stats_data["shipName"] = team_info.get("shipName", "")
        stats_data["isOwn"] = team_info.get("isOwn", False)

        result.append(stats_data)

    # ダメージ降順でソート
    result.sort(key=lambda x: x.get("damage", 0), reverse=True)

    return result


def handle(event, context):
    """
    S3イベントハンドラー

    Args:
        event: S3イベント
        context: Lambdaコンテキスト

    Returns:
        処理結果
    """
    try:
        # S3イベントから情報を取得
        for record in event.get("Records", []):
            bucket = record["s3"]["bucket"]["name"]
            key = unquote_plus(record["s3"]["object"]["key"])  # URLデコード

            print(f"Processing: s3://{bucket}/{key}")

            # .wowsreplayファイルのみ処理
            if not key.endswith(".wowsreplay"):
                print(f"Skipping non-replay file: {key}")
                continue

            # S3からファイルをダウンロード
            tmp_path = None
            with tempfile.NamedTemporaryFile(suffix=".wowsreplay", delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
                s3_client.download_fileobj(bucket, key, tmp_file)
            # with文を抜けてファイルが完全に閉じられる

            try:
                # BattleStatsパケットを抽出
                battle_results = extract_battle_stats(str(tmp_path))

                if not battle_results:
                    print(f"No battle results found in {key}")
                    continue

                # arenaUniqueIDを取得
                arena_unique_id = get_arena_unique_id(battle_results)

                if not arena_unique_id:
                    print(f"No arenaUniqueID found in {key}")
                    continue

                # 勝敗情報を取得
                win_loss = get_win_loss_clan_battle(battle_results)
                experience_earned = get_experience_earned(battle_results)

                print(f"Arena ID: {arena_unique_id}, Win/Loss: {win_loss}, Exp: {experience_earned}")

                # S3キーからtemp_arena_idとplayerIDを抽出
                # S3キー形式: replays/{temp_arena_id}/{playerID}/{filename}
                key_parts = key.split("/")
                if len(key_parts) >= 3:
                    temp_arena_id = key_parts[1]
                    try:
                        player_id = int(key_parts[2])
                    except ValueError:
                        print(f"Failed to extract playerID from key: {key}")
                        continue
                else:
                    print(f"Invalid S3 key format: {key}")
                    continue

                # 一時IDで保存されたレコードを取得
                old_record = dynamodb.get_replay_record(temp_arena_id, player_id)

                if not old_record:
                    print(f"No record found for temp_arena_id: {temp_arena_id}, player_id: {player_id}")
                    continue

                # 正しいarenaUniqueIDで新しいレコードを作成
                print(f"Migrating record from temp_id {temp_arena_id} to arena_id {arena_unique_id}")

                # 既存データに勝敗情報を追加
                old_record["arenaUniqueID"] = str(arena_unique_id)
                old_record["winLoss"] = win_loss
                old_record["experienceEarned"] = experience_earned

                # BattleStatsから詳細統計を抽出
                players_public_info = battle_results.get("playersPublicInfo", {})
                if players_public_info:
                    all_stats = BattleStatsParser.parse_all_players(players_public_info)

                    # 自分のプレイヤー統計を特定（playerIDで検索）
                    own_stats = None
                    player_name = old_record.get("playerName", "")

                    for pid, stats in all_stats.items():
                        if stats.get("player_name") == player_name:
                            own_stats = stats
                            break

                    # 統計情報をレコードに追加
                    if own_stats:
                        stats_data = BattleStatsParser.to_dynamodb_format(own_stats)
                        # 基本統計
                        old_record["damage"] = stats_data.get("damage", 0)
                        old_record["receivedDamage"] = stats_data.get("receivedDamage", 0)
                        old_record["spottingDamage"] = stats_data.get("spottingDamage", 0)
                        old_record["potentialDamage"] = stats_data.get("potentialDamage", 0)
                        old_record["kills"] = stats_data.get("kills", 0)
                        old_record["fires"] = stats_data.get("fires", 0)
                        old_record["floods"] = stats_data.get("floods", 0)
                        old_record["baseXP"] = stats_data.get("baseXP", 0)
                        # 命中数内訳
                        old_record["hitsAP"] = stats_data.get("hitsAP", 0)
                        old_record["hitsHE"] = stats_data.get("hitsHE", 0)
                        old_record["hitsSecondaries"] = stats_data.get("hitsSecondaries", 0)
                        # ダメージ内訳
                        old_record["damageAP"] = stats_data.get("damageAP", 0)
                        old_record["damageHE"] = stats_data.get("damageHE", 0)
                        old_record["damageHESecondaries"] = stats_data.get("damageHESecondaries", 0)
                        old_record["damageTorps"] = stats_data.get("damageTorps", 0)
                        old_record["damageDeepWaterTorps"] = stats_data.get("damageDeepWaterTorps", 0)
                        old_record["damageOther"] = stats_data.get("damageOther", 0)
                        old_record["damageFire"] = stats_data.get("damageFire", 0)
                        old_record["damageFlooding"] = stats_data.get("damageFlooding", 0)

                        dmg = stats_data.get("damage")
                        kls = stats_data.get("kills")
                        print(f"Added battle stats for {player_name}: damage={dmg}, kills={kls}")

                    # 全プレイヤーの統計情報を作成
                    all_players_stats = build_all_players_stats(all_stats, old_record)
                    if all_players_stats:
                        old_record["allPlayersStats"] = all_players_stats
                        print(f"Added all players stats: {len(all_players_stats)} players")

                # 新しいレコードを作成
                dynamodb_table = dynamodb.get_table()
                dynamodb_table.put_item(Item=old_record)

                # 古いレコード（一時ID）を削除
                dynamodb_table.delete_item(Key={"arenaUniqueID": temp_arena_id, "playerID": player_id})

                print(f"Successfully migrated and updated record: arena {arena_unique_id}, player {player_id}")

                # 動画生成チェック: 同じ試合の既存リプレイで動画があるかチェック
                check_and_trigger_video_generation(arena_unique_id, player_id)

            finally:
                # 一時ファイルを削除
                if tmp_path.exists():
                    tmp_path.unlink()

        return {
            "statusCode": 200,
            "body": json.dumps({"message": "Battle results extracted successfully"}),
        }

    except Exception as e:
        print(f"Error in battle_result_extractor_handler: {e}")
        import traceback

        traceback.print_exc()

        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}


def check_and_trigger_video_generation(arena_unique_id: int, player_id: int):
    """
    同じ試合の既存リプレイで動画があるかチェックし、なければ動画生成をトリガー

    arenaUniqueIDは各プレイヤーごとに異なるため、match_key（プレイヤーセット）で同一試合を判定

    Args:
        arena_unique_id: arenaUniqueID
        player_id: プレイヤーID
    """
    try:
        table = dynamodb.get_table()

        # 現在のレコードを取得してmatch_keyを生成
        current_record = dynamodb.get_replay_record(arena_unique_id, player_id)
        if not current_record:
            print(f"No record found for arena {arena_unique_id}, player {player_id}")
            return

        # ownPlayerが配列の場合、単一オブジェクトに変換
        if "ownPlayer" in current_record and isinstance(current_record["ownPlayer"], list):
            current_record["ownPlayer"] = current_record["ownPlayer"][0] if current_record["ownPlayer"] else {}

        # 現在の試合のmatch_keyを生成
        current_match_key = generate_match_key(current_record)
        game_type = current_record.get("gameType")

        print(f"Checking for existing video in match: {current_match_key}")

        # 同じgameTypeの全リプレイを取得（効率化のため）
        response = table.query(
            IndexName="GameTypeIndex",
            KeyConditionExpression="gameType = :gt",
            ExpressionAttributeValues={":gt": game_type},
        )

        all_items = response.get("Items", [])
        print(f"Found {len(all_items)} items with gameType={game_type}")

        # ownPlayerが配列の場合、単一オブジェクトに変換
        for item in all_items:
            if "ownPlayer" in item and isinstance(item["ownPlayer"], list):
                item["ownPlayer"] = item["ownPlayer"][0] if item["ownPlayer"] else {}

        # match_keyが一致するリプレイをフィルタリング
        same_match_items = []
        for item in all_items:
            if generate_match_key(item) == current_match_key:
                same_match_items.append(item)

        print(f"Found {len(same_match_items)} replays for the same match")

        # 既に動画があるリプレイがあるかチェック
        has_video = any(item.get("mp4S3Key") for item in same_match_items)

        if has_video:
            print("Match already has video, skipping generation")
            return

        # 動画がない場合、生成をトリガー
        print(f"No video found for match, triggering video generation for arena {arena_unique_id}, player {player_id}")

        # 環境変数から関数名を取得
        stage = os.environ.get("STAGE", "dev")
        function_name = f"wows-replay-bot-{stage}-generate-video-api"

        # Lambda非同期呼び出し
        payload = {
            "body": json.dumps({"arenaUniqueID": str(arena_unique_id), "playerID": player_id}),
            "httpMethod": "POST",
        }

        lambda_client.invoke(
            FunctionName=function_name,
            InvocationType="Event",
            Payload=json.dumps(payload),  # 非同期呼び出し
        )

        print(f"Video generation triggered successfully for arena {arena_unique_id}, player {player_id}")

    except Exception as e:
        # エラーが発生しても、メインの処理は継続させる
        print(f"Error checking/triggering video generation: {e}")
        import traceback

        traceback.print_exc()
