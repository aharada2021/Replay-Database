"""
試合詳細APIハンドラー

特定の試合IDに対する全リプレイを取得

新テーブル構造対応版:
- /api/match/{arenaUniqueID} - 試合基本情報を取得
- /api/match/{arenaUniqueID}/stats - 全プレイヤー統計を取得
"""

import json
from decimal import Decimal

from utils import dynamodb
from utils.match_key import generate_match_key
from utils.dynamodb_tables import (
    BattleTableClient,
    find_match_game_type,
)


class DecimalEncoder(json.JSONEncoder):
    """DynamoDB Decimalオブジェクトをシリアライズするカスタムエンコーダー"""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)


def handle(event, context):
    """
    試合詳細APIのハンドラー

    ルーティング:
    - /api/match/{arenaUniqueID} -> 試合詳細
    - /api/match/{arenaUniqueID}/stats -> 試合統計

    Args:
        event: APIイベント
        context: Lambdaコンテキスト

    Returns:
        APIレスポンス
    """
    # パスを確認してルーティング
    raw_path = event.get("rawPath", "") or event.get("path", "")
    if raw_path.endswith("/stats"):
        return handle_stats(event, context)

    try:
        # CORS headers
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
        }

        # OPTIONS request (preflight)
        http_method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
        if http_method == "OPTIONS":
            return {"statusCode": 200, "headers": cors_headers, "body": ""}

        # パスパラメータからarenaUniqueIDを取得
        path_parameters = event.get("pathParameters", {})
        arena_unique_id = path_parameters.get("arenaUniqueID")

        if not arena_unique_id:
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": "arenaUniqueID is required"}),
            }

        # まず指定されたarenaUniqueIDのレコードを取得してmatch_keyを生成
        table = dynamodb.get_table()
        response = table.query(
            KeyConditionExpression="arenaUniqueID = :aid",
            ExpressionAttributeValues={":aid": str(arena_unique_id)},
        )

        seed_items = response.get("Items", [])

        if not seed_items:
            return {
                "statusCode": 404,
                "headers": cors_headers,
                "body": json.dumps({"error": "Match not found"}),
            }

        # ownPlayerが配列の場合、単一オブジェクトに変換
        for item in seed_items:
            if "ownPlayer" in item and isinstance(item["ownPlayer"], list):
                item["ownPlayer"] = item["ownPlayer"][0] if item["ownPlayer"] else {}

        # 最初のレコードからmatch_keyを生成
        seed_item = seed_items[0]
        target_match_key = generate_match_key(seed_item)

        print(f"Target match_key: {target_match_key}")

        # 全リプレイをスキャンして同じmatch_keyを持つものを探す
        # GameTypeSortableIndexを使って同じ日時範囲のリプレイを取得
        game_type = seed_item.get("gameType")
        date_time_sortable = seed_item.get("dateTimeSortable", "")

        # 同じ日のデータに絞り込む（日付範囲: 当日の00:00:00〜23:59:59）
        # dateTimeSortableは YYYYMMDDHHMMSS 形式
        if date_time_sortable and len(date_time_sortable) >= 8:
            date_prefix = date_time_sortable[:8]  # YYYYMMDD
            date_start = date_prefix + "000000"
            date_end = date_prefix + "235959"
        else:
            # フォールバック: 全データを取得（ページネーション対応）
            date_start = "00000000000000"
            date_end = "99999999999999"

        # GameTypeSortableIndexで同じゲームタイプ・同日のリプレイを取得
        all_items = []
        last_evaluated_key = None

        while True:
            query_kwargs = {
                "IndexName": "GameTypeSortableIndex",
                "KeyConditionExpression": "gameType = :gt AND dateTimeSortable BETWEEN :start AND :end",
                "ExpressionAttributeValues": {
                    ":gt": game_type,
                    ":start": date_start,
                    ":end": date_end,
                },
            }
            if last_evaluated_key:
                query_kwargs["ExclusiveStartKey"] = last_evaluated_key

            all_response = table.query(**query_kwargs)
            all_items.extend(all_response.get("Items", []))

            last_evaluated_key = all_response.get("LastEvaluatedKey")
            if not last_evaluated_key:
                break

        # ownPlayerが配列の場合、単一オブジェクトに変換
        for item in all_items:
            if "ownPlayer" in item and isinstance(item["ownPlayer"], list):
                item["ownPlayer"] = item["ownPlayer"][0] if item["ownPlayer"] else {}

        # match_keyが一致するアイテムをフィルタリング
        items = []
        for item in all_items:
            if generate_match_key(item) == target_match_key:
                items.append(item)

        print(f"Found {len(items)} replays for the same match")

        # hasDualReplayフラグ（いずれかのリプレイがDual可能な場合）
        has_dual_replay = any(item.get("hasDualReplay") for item in items)

        # 試合情報を構築（最初のリプレイから共通情報を取得）
        first_replay = items[0]
        match_info = {
            "arenaUniqueID": arena_unique_id,
            "dateTime": first_replay.get("dateTime"),
            "mapId": first_replay.get("mapId"),
            "mapDisplayName": first_replay.get("mapDisplayName"),
            "gameType": first_replay.get("gameType"),
            "clientVersion": first_replay.get("clientVersion"),
            "winLoss": first_replay.get("winLoss"),
            "experienceEarned": first_replay.get("experienceEarned"),
            "ownPlayer": first_replay.get("ownPlayer"),
            "allies": first_replay.get("allies", []),
            "enemies": first_replay.get("enemies", []),
            "allyMainClanTag": first_replay.get("allyMainClanTag"),
            "enemyMainClanTag": first_replay.get("enemyMainClanTag"),
            "allPlayersStats": first_replay.get("allPlayersStats", []),
            # Dual Render
            "hasDualReplay": has_dual_replay,
            "replays": [],
        }

        # 全リプレイ情報を追加（BattleStatsを含む）
        for item in items:
            match_info["replays"].append(
                {
                    "arenaUniqueID": item.get("arenaUniqueID"),  # 元のarenaUniqueIDも保存
                    "playerID": item.get("playerID"),
                    "playerName": item.get("playerName"),
                    "uploadedBy": item.get("uploadedBy"),
                    "uploadedAt": item.get("uploadedAt"),
                    "s3Key": item.get("s3Key"),
                    "fileName": item.get("fileName"),
                    "fileSize": item.get("fileSize"),
                    "mp4S3Key": item.get("mp4S3Key"),
                    "mp4GeneratedAt": item.get("mp4GeneratedAt"),
                    # Dual Render
                    "dualMp4S3Key": item.get("dualMp4S3Key"),
                    "dualMp4GeneratedAt": item.get("dualMp4GeneratedAt"),
                    "hasDualReplay": item.get("hasDualReplay", False),
                    "ownPlayer": item.get("ownPlayer"),
                    # BattleStats - 基本統計
                    "damage": item.get("damage"),
                    "receivedDamage": item.get("receivedDamage"),
                    "spottingDamage": item.get("spottingDamage"),
                    "potentialDamage": item.get("potentialDamage"),
                    "kills": item.get("kills"),
                    "fires": item.get("fires"),
                    "floods": item.get("floods"),
                    "baseXP": item.get("baseXP"),
                    # BattleStats - 命中数内訳
                    "hitsAP": item.get("hitsAP"),
                    "hitsHE": item.get("hitsHE"),
                    "hitsSecondaries": item.get("hitsSecondaries"),
                    # BattleStats - ダメージ内訳
                    "damageAP": item.get("damageAP"),
                    "damageHE": item.get("damageHE"),
                    "damageHESecondaries": item.get("damageHESecondaries"),
                    "damageTorps": item.get("damageTorps"),
                    "damageDeepWaterTorps": item.get("damageDeepWaterTorps"),
                    "damageOther": item.get("damageOther"),
                    "damageFire": item.get("damageFire"),
                    "damageFlooding": item.get("damageFlooding"),
                    # Citadel
                    "citadels": item.get("citadels"),
                }
            )

        # レスポンス
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps(match_info, cls=DecimalEncoder),
        }

    except Exception as e:
        print(f"Error in match_detail_api_handler: {e}")
        import traceback

        traceback.print_exc()

        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)}),
        }


def handle_stats(event, context):
    """
    試合統計APIのハンドラー

    新テーブル構造からSTATSレコードを取得

    Args:
        event: APIイベント
        context: Lambdaコンテキスト

    Returns:
        APIレスポンス
    """
    try:
        # CORS headers
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
        }

        # OPTIONS request (preflight)
        http_method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
        if http_method == "OPTIONS":
            return {"statusCode": 200, "headers": cors_headers, "body": ""}

        # パスパラメータからarenaUniqueIDを取得
        path_parameters = event.get("pathParameters", {})
        arena_unique_id = path_parameters.get("arenaUniqueID")

        if not arena_unique_id:
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": "arenaUniqueID is required"}),
            }

        # gameTypeを特定
        game_type = find_match_game_type(arena_unique_id)

        if not game_type:
            return {
                "statusCode": 404,
                "headers": cors_headers,
                "body": json.dumps({"error": "Match not found"}),
            }

        # STATSレコードを取得
        battle_client = BattleTableClient(game_type)
        stats = battle_client.get_stats(arena_unique_id)

        if not stats:
            return {
                "statusCode": 404,
                "headers": cors_headers,
                "body": json.dumps({"error": "Stats not found"}),
            }

        # レスポンス
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps(
                {
                    "arenaUniqueID": arena_unique_id,
                    "allPlayersStats": stats.get("allPlayersStats", []),
                },
                cls=DecimalEncoder,
            ),
        }

    except Exception as e:
        print(f"Error in match_stats_api_handler: {e}")
        import traceback

        traceback.print_exc()

        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)}),
        }


def handle_new(event, context):
    """
    試合詳細APIのハンドラー（新テーブル構造）

    新テーブル構造からMATCH + UPLOADSを取得

    Args:
        event: APIイベント
        context: Lambdaコンテキスト

    Returns:
        APIレスポンス
    """
    try:
        # CORS headers
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
        }

        # OPTIONS request (preflight)
        http_method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
        if http_method == "OPTIONS":
            return {"statusCode": 200, "headers": cors_headers, "body": ""}

        # パスパラメータからarenaUniqueIDを取得
        path_parameters = event.get("pathParameters", {})
        arena_unique_id = path_parameters.get("arenaUniqueID")

        if not arena_unique_id:
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": "arenaUniqueID is required"}),
            }

        # gameTypeを特定
        game_type = find_match_game_type(arena_unique_id)

        if not game_type:
            return {
                "statusCode": 404,
                "headers": cors_headers,
                "body": json.dumps({"error": "Match not found"}),
            }

        # MATCH + UPLOADSを取得
        battle_client = BattleTableClient(game_type)
        full_match = battle_client.get_full_match(arena_unique_id)

        if not full_match or not full_match.get("match"):
            return {
                "statusCode": 404,
                "headers": cors_headers,
                "body": json.dumps({"error": "Match not found"}),
            }

        match_data = full_match["match"]
        uploads = full_match.get("uploads", [])

        # レスポンス形式に変換（旧形式との互換性）
        match_info = {
            "arenaUniqueID": arena_unique_id,
            "dateTime": match_data.get("dateTime"),
            "unixTime": match_data.get("unixTime"),
            "mapId": match_data.get("mapId"),
            "mapDisplayName": match_data.get("mapDisplayName"),
            "gameType": game_type,
            "clientVersion": match_data.get("clientVersion"),
            "winLoss": match_data.get("winLoss"),
            "ownPlayer": {
                "name": match_data.get("allyPerspectivePlayerName"),
            },
            "allies": match_data.get("allies", []),
            "enemies": match_data.get("enemies", []),
            "allyMainClanTag": match_data.get("allyMainClanTag"),
            "enemyMainClanTag": match_data.get("enemyMainClanTag"),
            "hasDualReplay": match_data.get("dualRendererAvailable", False),
            "commentCount": match_data.get("commentCount", 0),
            "mp4S3Key": match_data.get("mp4S3Key"),
            # allPlayersStatsは別APIで取得（RCU最適化のため）
            "allPlayersStats": [],
            "replays": [],
        }

        # UPLOADレコードをreplays配列に変換
        for upload in uploads:
            match_info["replays"].append(
                {
                    "arenaUniqueID": arena_unique_id,
                    "playerID": upload.get("playerID"),
                    "playerName": upload.get("playerName"),
                    "team": upload.get("team"),
                    "uploadedBy": upload.get("uploadedBy"),
                    "uploadedAt": upload.get("uploadedAt"),
                    "s3Key": upload.get("s3Key"),
                    "fileName": upload.get("fileName"),
                    "fileSize": upload.get("fileSize"),
                    "ownPlayer": upload.get("ownPlayer"),
                    # 戦闘統計
                    "damage": upload.get("damage"),
                    "kills": upload.get("kills"),
                    "spottingDamage": upload.get("spottingDamage"),
                    "potentialDamage": upload.get("potentialDamage"),
                    "receivedDamage": upload.get("receivedDamage"),
                    "baseXP": upload.get("baseXP"),
                    "citadels": upload.get("citadels"),
                    "fires": upload.get("fires"),
                    "floods": upload.get("floods"),
                }
            )

        # レスポンス
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps(match_info, cls=DecimalEncoder),
        }

    except Exception as e:
        print(f"Error in match_detail_new_api_handler: {e}")
        import traceback

        traceback.print_exc()

        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)}),
        }
