"""
バトル結果抽出ハンドラー

S3にリプレイファイルがアップロードされた時にトリガーされ、
Rust wows-replay-toolでリプレイを解析しDynamoDBを更新
"""

import json
import boto3
import tempfile
from pathlib import Path
import os
from urllib.parse import unquote_plus

from utils import dynamodb
from utils.dynamodb import calculate_main_clan_tag
from utils.dynamodb_tables import (
    BattleTableClient,
    IndexTableClient,
    normalize_game_type,
    parse_datetime_to_unix,
)
from utils.match_key import generate_match_key, format_sortable_datetime
from utils.dual_render import are_opposing_teams
from utils.rust_replay_tool import (
    extract_replay,
    build_players_info_from_rust,
    build_all_players_stats_from_rust,
    get_own_player_stats,
)

# S3クライアント
s3_client = boto3.client("s3")
lambda_client = boto3.client("lambda")


def save_to_new_tables(old_record: dict, all_players_stats: list) -> None:
    """
    新テーブル構造にデータを保存

    Args:
        old_record: 既存レコード（旧形式）
        all_players_stats: 全プレイヤー統計情報
    """
    try:
        raw_game_type = old_record.get("gameType", "other")
        game_type = normalize_game_type(raw_game_type)
        arena_unique_id = str(old_record.get("arenaUniqueID", ""))
        date_time = old_record.get("dateTime", "")
        unix_time = parse_datetime_to_unix(date_time)
        player_id = old_record.get("playerID", 0)
        player_name = old_record.get("playerName", "")

        # BattleTableClient を使用
        battle_client = BattleTableClient(game_type)

        # ownPlayer の処理
        own_player = old_record.get("ownPlayer", {})
        if isinstance(own_player, list):
            own_player = own_player[0] if own_player else {}

        # 既存のMATCHレコードをチェック
        existing_match = battle_client.get_match(arena_unique_id)

        if existing_match:
            # 既存の試合にアップローダーを追加
            # 既存のアップローダーに含まれていないか確認
            existing_uploaders = existing_match.get("uploaders", [])
            already_uploaded = any(u.get("playerID") == player_id for u in existing_uploaders)

            if not already_uploaded:
                # このプレイヤーのチームを判定
                # ownPlayerの名前が既存のalliesに含まれていればally、そうでなければenemy
                existing_allies = [a.get("name") for a in existing_match.get("allies", [])]
                team = "ally" if own_player.get("name") in existing_allies else "enemy"

                battle_client.add_uploader(arena_unique_id, player_id, player_name, team)
                print(f"Added uploader to existing MATCH: player {player_id} as {team}")

                # dualRendererAvailableを更新（敵味方両方のリプレイがある場合）
                if team == "enemy":
                    battle_client.update_dual_renderer_available(arena_unique_id, True)
                    print("Updated dualRendererAvailable to True")
        else:
            # allies/enemies のフォーマット
            allies = []
            for player in old_record.get("allies", []):
                allies.append(
                    {
                        "name": player.get("name", ""),
                        "clanTag": player.get("clanTag", ""),
                        "shipName": player.get("shipName", ""),
                        "shipId": player.get("shipId", 0),
                    }
                )

            enemies = []
            for player in old_record.get("enemies", []):
                enemies.append(
                    {
                        "name": player.get("name", ""),
                        "clanTag": player.get("clanTag", ""),
                        "shipName": player.get("shipName", ""),
                        "shipId": player.get("shipId", 0),
                    }
                )

            # MATCH レコードを作成
            match_record = {
                "arenaUniqueID": arena_unique_id,
                "recordType": "MATCH",
                "listingKey": "ACTIVE",
                "unixTime": unix_time,
                "dateTime": date_time,
                "mapId": old_record.get("mapId", ""),
                "mapDisplayName": old_record.get("mapDisplayName", ""),
                "clientVersion": old_record.get("clientVersion", ""),
                "allyPerspectivePlayerID": player_id,
                "allyPerspectivePlayerName": player_name,
                "winLoss": old_record.get("winLoss", "unknown"),
                "allyMainClanTag": old_record.get("allyMainClanTag", ""),
                "enemyMainClanTag": old_record.get("enemyMainClanTag", ""),
                "allies": allies,
                "enemies": enemies,
                "mp4S3Key": old_record.get("mp4S3Key"),
                "mp4GeneratedAt": None,
                "dualRendererAvailable": old_record.get("hasDualReplay", False),
                "commentCount": 0,
                "uploaders": [
                    {
                        "playerID": player_id,
                        "playerName": player_name,
                        "team": "ally",
                    }
                ],
            }
            battle_client.put_match(match_record)
            print(f"Saved MATCH record to {game_type} table")

            # STATS レコードを保存（新規MATCHの場合のみ）
            if all_players_stats:
                battle_client.put_stats(arena_unique_id, all_players_stats)
                print(f"Saved STATS record with {len(all_players_stats)} players")

            # インデックステーブルを更新（新規MATCHの場合のみ）
            index_client = IndexTableClient()

            # Ship index
            ship_counts = {}
            for player in allies + [own_player]:
                ship_name = player.get("shipName", "")
                if ship_name:
                    ship_name_upper = ship_name.upper()
                    if ship_name_upper not in ship_counts:
                        ship_counts[ship_name_upper] = {"ally": 0, "enemy": 0}
                    ship_counts[ship_name_upper]["ally"] += 1

            for player in enemies:
                ship_name = player.get("shipName", "")
                if ship_name:
                    ship_name_upper = ship_name.upper()
                    if ship_name_upper not in ship_counts:
                        ship_counts[ship_name_upper] = {"ally": 0, "enemy": 0}
                    ship_counts[ship_name_upper]["enemy"] += 1

            for ship_name, counts in ship_counts.items():
                index_client.put_ship_index(
                    ship_name=ship_name,
                    game_type=game_type,
                    unix_time=unix_time,
                    arena_unique_id=arena_unique_id,
                    ally_count=counts["ally"],
                    enemy_count=counts["enemy"],
                )
            print(f"Saved {len(ship_counts)} ship index entries")

            # Player index
            player_count = 0
            for player in allies + [own_player]:
                p_name = player.get("name", "")
                if p_name:
                    index_client.put_player_index(
                        player_name=p_name,
                        game_type=game_type,
                        unix_time=unix_time,
                        arena_unique_id=arena_unique_id,
                        team="ally",
                        clan_tag=player.get("clanTag", ""),
                        ship_name=player.get("shipName", ""),
                    )
                    player_count += 1

            for player in enemies:
                p_name = player.get("name", "")
                if p_name:
                    index_client.put_player_index(
                        player_name=p_name,
                        game_type=game_type,
                        unix_time=unix_time,
                        arena_unique_id=arena_unique_id,
                        team="enemy",
                        clan_tag=player.get("clanTag", ""),
                        ship_name=player.get("shipName", ""),
                    )
                    player_count += 1
            print(f"Saved {player_count} player index entries")

            # Clan index
            clan_counts = {}
            ally_main_clan = old_record.get("allyMainClanTag", "")
            enemy_main_clan = old_record.get("enemyMainClanTag", "")

            for player in allies + [own_player]:
                clan_tag = player.get("clanTag", "")
                if clan_tag:
                    if clan_tag not in clan_counts:
                        clan_counts[clan_tag] = {"ally": 0, "enemy": 0}
                    clan_counts[clan_tag]["ally"] += 1

            for player in enemies:
                clan_tag = player.get("clanTag", "")
                if clan_tag:
                    if clan_tag not in clan_counts:
                        clan_counts[clan_tag] = {"ally": 0, "enemy": 0}
                    clan_counts[clan_tag]["enemy"] += 1

            for clan_tag, counts in clan_counts.items():
                is_main = clan_tag in [ally_main_clan, enemy_main_clan]
                team = "ally" if counts["ally"] > counts["enemy"] else "enemy"
                index_client.put_clan_index(
                    clan_tag=clan_tag,
                    game_type=game_type,
                    unix_time=unix_time,
                    arena_unique_id=arena_unique_id,
                    team=team,
                    member_count=counts["ally"] + counts["enemy"],
                    is_main_clan=is_main,
                )
            print(f"Saved {len(clan_counts)} clan index entries")

        # UPLOAD レコードを保存（新規・既存どちらの場合も）
        # 既存MATCHの場合、このプレイヤーのチームを判定
        upload_team = "ally"
        if existing_match:
            existing_allies = [a.get("name") for a in existing_match.get("allies", [])]
            upload_team = "ally" if own_player.get("name") in existing_allies else "enemy"

        upload_record = {
            "arenaUniqueID": arena_unique_id,
            "playerID": player_id,
            "playerName": player_name,
            "team": upload_team,
            "s3Key": old_record.get("s3Key", ""),
            "fileName": old_record.get("fileName", ""),
            "fileSize": old_record.get("fileSize", 0),
            "uploadedAt": unix_time,
            "uploadedBy": old_record.get("uploadedBy", ""),
            "ownPlayer": {
                "name": own_player.get("name", ""),
                "clanTag": own_player.get("clanTag", ""),
                "shipName": own_player.get("shipName", ""),
                "shipId": own_player.get("shipId", 0),
            },
            # 戦闘統計
            "damage": old_record.get("damage", 0),
            "kills": old_record.get("kills", 0),
            "spottingDamage": old_record.get("spottingDamage", 0),
            "potentialDamage": old_record.get("potentialDamage", 0),
            "receivedDamage": old_record.get("receivedDamage", 0),
            "baseXP": old_record.get("baseXP", 0),
            "experienceEarned": old_record.get("experienceEarned", 0),
            "citadels": old_record.get("citadels", 0),
            "fires": old_record.get("fires", 0),
            "floods": old_record.get("floods", 0),
            "damageAP": old_record.get("damageAP", 0),
            "damageHE": old_record.get("damageHE", 0),
            "damageTorps": old_record.get("damageTorps", 0),
            "damageFire": old_record.get("damageFire", 0),
            "damageFlooding": old_record.get("damageFlooding", 0),
            "hitsAP": old_record.get("hitsAP", 0),
            "hitsHE": old_record.get("hitsHE", 0),
        }
        battle_client.put_upload(upload_record)
        print(f"Saved UPLOAD record for player {player_id} as {upload_team}")

    except Exception as e:
        print(f"Warning: Failed to save to new tables: {e}")
        import traceback

        traceback.print_exc()


def migrate_gameplay_video(
    pending_video_s3_key: str,
    arena_unique_id: str,
    player_id: int,
    game_type: str,
) -> bool:
    """
    ゲームプレイ動画をpendingパスから正式パスに移行

    クライアントはリプレイアップロード前に動画をpending-videos/にアップロードする。
    正式なarenaUniqueIDはリプレイ解析後に判明するため、この関数で正しいパスに移動する。

    Args:
        pending_video_s3_key: 一時パスのS3キー（pending-videos/{uuid}/capture.mp4）
        arena_unique_id: 正式なアリーナユニークID
        player_id: プレイヤーID
        game_type: ゲームタイプ（clan, ranked, random, other）

    Returns:
        移行が成功した場合True
    """
    bucket = os.environ.get("REPLAYS_BUCKET", "wows-replay-bot-dev-temp")

    # 新しい動画S3キー（正式ID）
    new_s3_key = f"gameplay-videos/{arena_unique_id}/{player_id}/capture.mp4"

    try:
        # 元の動画が存在するか確認
        try:
            s3_client.head_object(Bucket=bucket, Key=pending_video_s3_key)
        except s3_client.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                print(
                    f"Warning: Pending video not found at {pending_video_s3_key}. " "Video may have failed to upload."
                )
                return False
            raise

        print(f"Found gameplay video at {pending_video_s3_key}, migrating to {new_s3_key}")

        # S3オブジェクトをコピー
        s3_client.copy_object(
            Bucket=bucket,
            CopySource={"Bucket": bucket, "Key": pending_video_s3_key},
            Key=new_s3_key,
            ContentType="video/mp4",
        )

        # ファイルサイズを取得
        head_response = s3_client.head_object(Bucket=bucket, Key=new_s3_key)
        file_size = head_response.get("ContentLength", 0)

        # 元のオブジェクトを削除
        s3_client.delete_object(Bucket=bucket, Key=pending_video_s3_key)

        print(f"Gameplay video migrated: {pending_video_s3_key} -> {new_s3_key}")

        # DynamoDBを更新
        import time

        battle_client = BattleTableClient(game_type)
        uploaded_at = int(time.time())

        battle_client.update_gameplay_video_info(
            arena_unique_id=arena_unique_id,
            player_id=player_id,
            gameplay_video_s3_key=new_s3_key,
            file_size=file_size,
            uploaded_at=uploaded_at,
        )

        battle_client.update_match_has_gameplay_video(arena_unique_id, True)
        print(f"Gameplay video info updated in DynamoDB: {arena_unique_id}/{player_id}")

        return True

    except Exception as e:
        print(f"Warning: Failed to migrate gameplay video: {e}")
        import traceback

        traceback.print_exc()
        return False


def process_replay_with_rust(tmp_path: str, key: str) -> dict:
    """
    Rustバイナリでリプレイを処理し、DynamoDBレコード更新に必要なデータを返す。

    Returns:
        {
            "arena_unique_id": int,
            "win_loss": str,
            "experience_earned": int,
            "players_info": {"own": [...], "allies": [...], "enemies": [...]},
            "own_stats": dict or None,
            "all_players_stats": list,
        }
    """
    rust_output = extract_replay(str(tmp_path))

    arena_unique_id = rust_output.get("arenaUniqueId")
    if not arena_unique_id:
        raise ValueError(f"No arenaUniqueID in Rust output for {key}")

    players_info = build_players_info_from_rust(rust_output)
    own_stats = get_own_player_stats(rust_output)
    all_players_stats = build_all_players_stats_from_rust(rust_output)

    skills_count = sum(1 for p in all_players_stats if p.get("captainSkills"))
    print(
        f"Rust extraction: arena={arena_unique_id}, "
        f"win={rust_output.get('winLoss')}, exp={rust_output.get('experienceEarned')}, "
        f"players={len(all_players_stats)}, skills={skills_count}"
    )

    metadata = rust_output.get("metadata", {})

    return {
        "arena_unique_id": arena_unique_id,
        "win_loss": rust_output.get("winLoss", "unknown"),
        "experience_earned": rust_output.get("experienceEarned", 0),
        "players_info": players_info,
        "own_stats": own_stats,
        "all_players_stats": all_players_stats,
        "map_display_name": metadata.get("mapDisplayName", ""),
    }


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

            try:
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

                # Rustでリプレイを解析
                extraction = process_replay_with_rust(tmp_path, key)
                arena_unique_id = extraction["arena_unique_id"]
                win_loss = extraction["win_loss"]
                experience_earned = extraction["experience_earned"]
                players_info = extraction["players_info"]
                own_stats = extraction["own_stats"]
                all_players_stats = extraction["all_players_stats"]
                if extraction.get("map_display_name"):
                    old_record["mapDisplayName"] = extraction["map_display_name"]

                print(f"Arena ID: {arena_unique_id}, Win/Loss: {win_loss}, Exp: {experience_earned}")

                # 正しいarenaUniqueIDで新しいレコードを作成
                print(f"Migrating record from temp_id {temp_arena_id} to arena_id {arena_unique_id}")

                # 既存データに勝敗情報を追加
                old_record["arenaUniqueID"] = str(arena_unique_id)
                old_record["winLoss"] = win_loss
                old_record["experienceEarned"] = experience_earned

                # プレイヤー情報を追加
                if players_info.get("own"):
                    own_player = players_info["own"][0]
                    old_record["ownPlayer"] = own_player
                    old_record["playerShip"] = own_player.get("shipName", "")
                    old_record["playerShipId"] = own_player.get("shipId", 0)
                if players_info.get("allies"):
                    old_record["allies"] = players_info["allies"]
                if players_info.get("enemies"):
                    old_record["enemies"] = players_info["enemies"]

                # クラン戦の場合、クランタグを計算
                game_type = old_record.get("gameType", "")
                if game_type == "clan":
                    own_player = old_record.get("ownPlayer", {})
                    if isinstance(own_player, list):
                        own_player = own_player[0] if own_player else {}
                    ally_players = (
                        [own_player] + old_record.get("allies", []) if own_player else old_record.get("allies", [])
                    )
                    old_record["allyMainClanTag"] = calculate_main_clan_tag(ally_players)
                    old_record["enemyMainClanTag"] = calculate_main_clan_tag(old_record.get("enemies", []))
                    print(
                        f"Calculated clan tags: ally={old_record.get('allyMainClanTag')}, "
                        f"enemy={old_record.get('enemyMainClanTag')}"
                    )

                # 統計情報をレコードに追加
                if own_stats:
                    old_record.update(own_stats)
                    print(f"Added battle stats: damage={own_stats.get('damage')}, kills={own_stats.get('kills')}")

                if all_players_stats:
                    old_record["allPlayersStats"] = all_players_stats
                    skills_count = sum(1 for p in all_players_stats if p.get("captainSkills"))
                    print(f"Added all players stats: {len(all_players_stats)} players, {skills_count} with skills")

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

                # 新テーブル構造にも保存（移行期間中は両方に保存）
                all_players_stats = old_record.get("allPlayersStats", [])
                save_to_new_tables(old_record, all_players_stats)

                # ゲームプレイ動画のS3キーを移行（pending-videos/ → gameplay-videos/）
                pending_video_s3_key = old_record.get("pendingVideoS3Key")
                if pending_video_s3_key:
                    migrate_gameplay_video(
                        pending_video_s3_key=pending_video_s3_key,
                        arena_unique_id=str(arena_unique_id),
                        player_id=player_id,
                        game_type=normalize_game_type(old_record.get("gameType", "other")),
                    )

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
