"""
試合詳細APIハンドラー

特定の試合IDに対する全リプレイを取得
"""

import json
from decimal import Decimal

from utils import dynamodb
from utils.match_key import generate_match_key


class DecimalEncoder(json.JSONEncoder):
    """DynamoDB Decimalオブジェクトをシリアライズするカスタムエンコーダー"""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)


def handle(event, context):
    """
    試合詳細APIのハンドラー

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
        http_method = event.get("httpMethod") or event.get(
            "requestContext", {}
        ).get("http", {}).get("method")
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
                item["ownPlayer"] = (
                    item["ownPlayer"][0] if item["ownPlayer"] else {}
                )

        # 最初のレコードからmatch_keyを生成
        seed_item = seed_items[0]
        target_match_key = generate_match_key(seed_item)

        print(f"Target match_key: {target_match_key}")

        # 全リプレイをスキャンして同じmatch_keyを持つものを探す
        # 小規模データベースの場合はScanで十分
        # 大規模な場合はGameTypeSortableIndexを使って絞り込む
        game_type = seed_item.get("gameType")

        # GameTypeSortableIndexで同じゲームタイプのリプレイを取得
        all_response = table.query(
            IndexName="GameTypeSortableIndex",
            KeyConditionExpression="gameType = :gt",
            ExpressionAttributeValues={":gt": game_type},
        )

        all_items = all_response.get("Items", [])

        # ownPlayerが配列の場合、単一オブジェクトに変換
        for item in all_items:
            if "ownPlayer" in item and isinstance(item["ownPlayer"], list):
                item["ownPlayer"] = (
                    item["ownPlayer"][0] if item["ownPlayer"] else {}
                )

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
                    "arenaUniqueID": item.get(
                        "arenaUniqueID"
                    ),  # 元のarenaUniqueIDも保存
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
