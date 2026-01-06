"""
試合詳細APIハンドラー

特定の試合IDに対する全リプレイを取得
"""

import json
from decimal import Decimal

from utils import dynamodb


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

        # DynamoDBから該当する全リプレイを取得
        table = dynamodb.get_table()
        response = table.query(
            KeyConditionExpression="arenaUniqueID = :aid", ExpressionAttributeValues={":aid": str(arena_unique_id)}
        )

        items = response.get("Items", [])

        if not items:
            return {
                "statusCode": 404,
                "headers": cors_headers,
                "body": json.dumps({"error": "Match not found"}),
            }

        # ownPlayerが配列の場合、単一オブジェクトに変換
        for item in items:
            if "ownPlayer" in item and isinstance(item["ownPlayer"], list):
                item["ownPlayer"] = item["ownPlayer"][0] if item["ownPlayer"] else {}

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
            "replays": [],
        }

        # 全リプレイ情報を追加
        for item in items:
            match_info["replays"].append(
                {
                    "playerID": item.get("playerID"),
                    "playerName": item.get("playerName"),
                    "uploadedBy": item.get("uploadedBy"),
                    "uploadedAt": item.get("uploadedAt"),
                    "s3Key": item.get("s3Key"),
                    "fileName": item.get("fileName"),
                    "fileSize": item.get("fileSize"),
                    "mp4S3Key": item.get("mp4S3Key"),
                    "mp4GeneratedAt": item.get("mp4GeneratedAt"),
                    "ownPlayer": item.get("ownPlayer"),
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
