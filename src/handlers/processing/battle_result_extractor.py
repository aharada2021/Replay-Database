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
    extract_hidden_data,
    get_win_loss_clan_battle,
    get_win_loss_from_hidden,
    get_experience_earned,
    get_arena_unique_id,
)
from parsers.battlestats_parser import BattleStatsParser
from utils import dynamodb
from utils.match_key import generate_match_key, format_sortable_datetime
from utils.captain_skills import (
    map_player_to_skills,
    get_ship_class_from_params_id,
    get_ship_name_from_params_id,
)
from utils.upgrades import map_player_to_upgrades
from utils.dual_render import are_opposing_teams
from core.replay_metadata import ReplayMetadataParser

# S3クライアント
s3_client = boto3.client("s3")
lambda_client = boto3.client("lambda")


def extract_players_info_from_metadata(metadata: dict) -> dict:
    """
    リプレイメタデータからプレイヤー情報を抽出（API呼び出しなし）

    Args:
        metadata: リプレイメタデータ

    Returns:
        {
            'own': [{'name': str, 'shipId': int, 'shipName': str}, ...],
            'allies': [{'name': str, 'shipId': int, 'shipName': str}, ...],
            'enemies': [{'name': str, 'shipId': int, 'shipName': str}, ...]
        }
    """
    players_info = {"own": [], "allies": [], "enemies": []}

    try:
        vehicles = metadata.get("vehicles", [])

        for player in vehicles:
            ship_id = player.get("shipId", 0)
            player_name = player.get("name", "Unknown")

            # ships.jsonから艦艇名を取得（見つからない場合は空文字）
            ship_name = get_ship_name_from_params_id(ship_id) or ""

            player_data = {
                "name": player_name,
                "shipId": ship_id,
                "shipName": ship_name,
            }

            relation = player.get("relation", 2)

            if relation == 0:
                players_info["own"].append(player_data)
            elif relation == 1:
                players_info["allies"].append(player_data)
            else:
                players_info["enemies"].append(player_data)

        print(
            f"Extracted players info: own={len(players_info['own'])}, "
            f"allies={len(players_info['allies'])}, enemies={len(players_info['enemies'])}"
        )

    except Exception as e:
        print(f"Error extracting players info: {e}")

    return players_info


def build_all_players_stats(
    all_stats: dict,
    record: dict,
    hidden_data: dict = None,
) -> list:
    """
    全プレイヤーの統計情報をチーム情報と紐付けて配列で返す

    Args:
        all_stats: BattleStatsParser.parse_all_players()の結果
        record: DynamoDBレコード（allies, enemies, ownPlayerを含む）
        hidden_data: リプレイのhiddenデータ（艦長スキル用）

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

    # hiddenデータから艦長スキルとアップグレードを抽出
    player_skills_map = {}
    player_skills_raw_map = {}  # 生データ用
    player_upgrades_map = {}
    # 環境変数でデバッグモードを制御
    debug_skills = os.environ.get("DEBUG_CAPTAIN_SKILLS", "").lower() == "true"
    if hidden_data:
        try:
            # デバッグモードの場合は生データも取得
            if debug_skills:
                skills_result = map_player_to_skills(hidden_data, debug=True, include_raw=True)
                # include_raw=Trueの場合、{player_name: {"skills": [...], "raw": {...}}}
                for pn, data in skills_result.items():
                    player_skills_map[pn] = data["skills"]
                    player_skills_raw_map[pn] = data["raw"]
            else:
                player_skills_map = map_player_to_skills(hidden_data, debug=False)
        except Exception as e:
            print(f"Warning: Failed to extract captain skills: {e}")

        try:
            player_upgrades_map = map_player_to_upgrades(hidden_data)
        except Exception as e:
            print(f"Warning: Failed to extract upgrades: {e}")

    # 全プレイヤーの統計を作成
    result = []
    for player_id, stats in all_stats.items():
        player_name = stats.get("player_name", "")
        team_info = player_team_map.get(player_name, {"team": "unknown", "shipId": 0, "shipName": ""})

        # DynamoDB形式に変換
        stats_data = BattleStatsParser.to_dynamodb_format(stats)

        # チーム情報と艦船情報を追加
        stats_data["team"] = team_info["team"]
        ship_id = team_info.get("shipId", 0)
        stats_data["shipId"] = ship_id
        stats_data["shipName"] = team_info.get("shipName", "")
        stats_data["isOwn"] = team_info.get("isOwn", False)

        # 艦種を追加（shipParamsIdから取得）
        if ship_id:
            ship_class = get_ship_class_from_params_id(ship_id)
            if ship_class:
                stats_data["shipClass"] = ship_class

        # 艦長スキルを追加（味方のみ利用可能）
        if player_name in player_skills_map:
            stats_data["captainSkills"] = player_skills_map[player_name]
            # デバッグモードの場合、生データも追加
            if player_name in player_skills_raw_map:
                stats_data["captainSkillsRaw"] = player_skills_raw_map[player_name]

        # アップグレードを追加（味方のみ利用可能）
        if player_name in player_upgrades_map:
            stats_data["upgrades"] = player_upgrades_map[player_name]

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
                # リプレイメタデータを解析してプレイヤー情報を取得
                metadata = ReplayMetadataParser.parse_replay_metadata(tmp_path)
                players_info = {"own": [], "allies": [], "enemies": []}
                if metadata:
                    players_info = extract_players_info_from_metadata(metadata)

                # BattleStatsパケットを抽出
                battle_results = extract_battle_stats(str(tmp_path))

                if not battle_results:
                    print(f"No battle results found in {key}")
                    continue

                # hiddenデータを抽出（艦長スキル、艦艇コンポーネント用）
                hidden_data = None
                try:
                    hidden_data = extract_hidden_data(str(tmp_path))
                    if hidden_data:
                        print("Hidden data extracted successfully")
                except Exception as hidden_err:
                    print(f"Warning: Failed to extract hidden data: {hidden_err}")

                # arenaUniqueIDを取得
                arena_unique_id = get_arena_unique_id(battle_results)

                if not arena_unique_id:
                    print(f"No arenaUniqueID found in {key}")
                    continue

                # 勝敗情報を取得（hiddenデータから取得、利用不可の場合はクラン戦用のXP判定を使用）
                win_loss = "unknown"
                if hidden_data:
                    win_loss = get_win_loss_from_hidden(hidden_data)
                    if win_loss != "unknown":
                        print(f"Win/Loss detected from hidden data: {win_loss}")

                # hiddenデータから取得できない場合、クラン戦用のXP判定を試行
                if win_loss == "unknown":
                    win_loss = get_win_loss_clan_battle(battle_results)
                    if win_loss != "unknown":
                        print(f"Win/Loss detected from clan battle XP: {win_loss}")

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

                # プレイヤー情報を追加（upload APIで省略されたデータを補完）
                if players_info.get("own"):
                    own_player = players_info["own"][0]
                    old_record["ownPlayer"] = own_player
                    old_record["playerShip"] = own_player.get("shipName", "")
                    old_record["playerShipId"] = own_player.get("shipId", 0)
                if players_info.get("allies"):
                    old_record["allies"] = players_info["allies"]
                if players_info.get("enemies"):
                    old_record["enemies"] = players_info["enemies"]

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
                        # Citadel
                        old_record["citadels"] = stats_data.get("citadels", 0)

                        dmg = stats_data.get("damage")
                        kls = stats_data.get("kills")
                        print(f"Added battle stats for {player_name}: damage={dmg}, kills={kls}")

                    # 全プレイヤーの統計情報を作成（艦長スキル、艦艇コンポーネント付き）
                    all_players_stats = build_all_players_stats(all_stats, old_record, hidden_data)
                    if all_players_stats:
                        old_record["allPlayersStats"] = all_players_stats
                        # 艦長スキルが含まれているプレイヤー数をカウント
                        skills_count = sum(1 for p in all_players_stats if p.get("captainSkills"))
                        print(
                            f"Added all players stats: {len(all_players_stats)} players, "
                            f"{skills_count} with captain skills"
                        )

                # 検索最適化用フィールドを事前計算
                # matchKey: 試合グループ化に使用（検索時の計算を省略）
                # dateTimeSortable: ソート可能な日時形式（YYYYMMDDHHMMSS）
                old_record["matchKey"] = generate_match_key(old_record)
                old_record["dateTimeSortable"] = format_sortable_datetime(old_record.get("dateTime", ""))
                print("Added search optimization fields: matchKey, dateTimeSortable")

                # 新しいレコードを作成
                dynamodb_table = dynamodb.get_table()
                dynamodb_table.put_item(Item=old_record)

                # 古いレコード（一時ID）を削除
                dynamodb_table.delete_item(Key={"arenaUniqueID": temp_arena_id, "playerID": player_id})

                print(f"Successfully migrated and updated record: arena {arena_unique_id}, player {player_id}")

                # 艦艇-試合インデックスを作成
                own_player = old_record.get("ownPlayer", {})
                if isinstance(own_player, list):
                    own_player = own_player[0] if own_player else {}

                try:
                    dynamodb.put_ship_match_index_entries(
                        arena_unique_id=str(arena_unique_id),
                        date_time=old_record.get("dateTime", ""),
                        game_type=old_record.get("gameType", ""),
                        map_id=old_record.get("mapId", ""),
                        allies=old_record.get("allies", []),
                        enemies=old_record.get("enemies", []),
                        own_player=own_player,
                    )
                except Exception as ship_idx_err:
                    print(f"Warning: Failed to create ship index entries: {ship_idx_err}")

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
    敵味方リプレイが揃っている場合はhasDualReplayフラグを設定

    arenaUniqueIDは同一試合で共通のため、同一arenaの全リプレイを検索して敵味方を判定

    Args:
        arena_unique_id: arenaUniqueID
        player_id: プレイヤーID
    """
    try:
        # 現在のレコードを取得
        current_record = dynamodb.get_replay_record(arena_unique_id, player_id)
        if not current_record:
            print(f"No record found for arena {arena_unique_id}, player {player_id}")
            return

        # ownPlayerが配列の場合、単一オブジェクトに変換
        if "ownPlayer" in current_record and isinstance(current_record["ownPlayer"], list):
            current_record["ownPlayer"] = current_record["ownPlayer"][0] if current_record["ownPlayer"] else {}

        # 現在の試合のmatch_keyを生成
        current_match_key = generate_match_key(current_record)

        print(f"Checking for existing video in match: {current_match_key}")

        # 同一arenaUniqueIDの全リプレイを取得（敵味方判定用）
        same_arena_items = dynamodb.get_replays_for_arena(str(arena_unique_id))
        print(f"Found {len(same_arena_items)} replays for arena {arena_unique_id}")

        # ownPlayerが配列の場合、単一オブジェクトに変換
        for item in same_arena_items:
            if "ownPlayer" in item and isinstance(item["ownPlayer"], list):
                item["ownPlayer"] = item["ownPlayer"][0] if item["ownPlayer"] else {}

        # 敵味方リプレイがあるかチェック
        opposing_replay = None
        for other_replay in same_arena_items:
            if other_replay.get("playerID") == int(player_id):
                continue  # 自分自身はスキップ
            if are_opposing_teams(current_record, other_replay):
                opposing_replay = other_replay
                break

        has_dual = opposing_replay is not None
        print(f"Dual replay available: {has_dual}")

        # Dual可能な場合、両方のレコードにhasDualReplayを設定
        if has_dual:
            try:
                dynamodb.update_has_dual_replay(str(arena_unique_id), int(player_id), True)
                dynamodb.update_has_dual_replay(
                    str(arena_unique_id),
                    int(opposing_replay["playerID"]),
                    True,
                )
                print("Updated hasDualReplay flag for both replays")
            except Exception as dual_err:
                print(f"Warning: Failed to update hasDualReplay: {dual_err}")

        # 既にDual動画があるかチェック
        has_dual_video = any(item.get("dualMp4S3Key") for item in same_arena_items)
        if has_dual_video:
            print("Match already has dual video, skipping generation")
            return

        # 既に通常動画があるかチェック（Dualがない場合は通常動画でOK）
        has_video = any(item.get("mp4S3Key") for item in same_arena_items)

        if has_video and not has_dual:
            print("Match already has video and no dual available, skipping generation")
            return

        # 動画がない、またはDualが可能になった場合は生成をトリガー
        print(f"Triggering video generation for arena {arena_unique_id}, player {player_id} (dual={has_dual})")

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
