"""
試合詳細APIハンドラー

エンドポイント:
- /api/match/{arenaUniqueID} - 試合基本情報を取得
- /api/match/{arenaUniqueID}/stats - 全プレイヤー統計を取得
"""

import json
from datetime import datetime
from decimal import Decimal

from utils.dynamodb_tables import (
    BattleTableClient,
    find_match_game_type,
)


def format_uploaded_at(unix_time):
    """
    Unix timestampをISO 8601形式の文字列に変換

    Args:
        unix_time: Unix timestamp (int or str) or None

    Returns:
        ISO形式の日時文字列、またはNone
    """
    if unix_time is None:
        return None
    try:
        ts = int(unix_time) if isinstance(unix_time, (int, float, str)) else None
        if ts:
            return datetime.fromtimestamp(ts).isoformat()
    except (ValueError, TypeError, OSError):
        pass
    return str(unix_time) if unix_time else None


class DecimalEncoder(json.JSONEncoder):
    """DynamoDB Decimalオブジェクトをシリアライズするカスタムエンコーダー"""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)


# CORS headers
CORS_HEADERS = {
    "Access-Control-Allow-Origin": "*",
    "Access-Control-Allow-Headers": "Content-Type",
    "Access-Control-Allow-Methods": "GET, OPTIONS",
}


def handle(event, context):
    """
    試合詳細APIのハンドラー

    ルーティング:
    - /api/match/{arenaUniqueID} -> 試合詳細
    - /api/match/{arenaUniqueID}/stats -> 試合統計
    """
    raw_path = event.get("rawPath", "") or event.get("path", "")
    if raw_path.endswith("/stats"):
        return handle_stats(event, context)
    return handle_match(event, context)


def handle_match(event, context):
    """
    試合詳細を取得

    MATCH + UPLOADレコードから試合情報を構築
    """
    try:
        # OPTIONS request (preflight)
        http_method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
        if http_method == "OPTIONS":
            return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

        # パスパラメータからarenaUniqueIDを取得
        path_parameters = event.get("pathParameters", {})
        arena_unique_id = path_parameters.get("arenaUniqueID")

        if not arena_unique_id:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "arenaUniqueID is required"}),
            }

        # gameTypeを特定
        game_type = find_match_game_type(arena_unique_id)

        if not game_type:
            return {
                "statusCode": 404,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Match not found"}),
            }

        # MATCH + UPLOADSを取得
        battle_client = BattleTableClient(game_type)
        full_match = battle_client.get_full_match(arena_unique_id)

        if not full_match or not full_match.get("match"):
            return {
                "statusCode": 404,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Match not found"}),
            }

        match_data = full_match["match"]
        uploads = full_match.get("uploads", [])

        # 動画情報
        mp4_s3_key = match_data.get("mp4S3Key")
        mp4_generated_at = match_data.get("mp4GeneratedAt")
        dual_mp4_s3_key = match_data.get("dualMp4S3Key")
        dual_mp4_generated_at = match_data.get("dualMp4GeneratedAt")
        has_dual_replay = match_data.get("dualRendererAvailable", False)
        has_gameplay_video = match_data.get("hasGameplayVideo", False)

        # レスポンス構築
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
            "hasDualReplay": has_dual_replay,
            "hasGameplayVideo": has_gameplay_video,
            "commentCount": match_data.get("commentCount", 0),
            # 動画情報
            "mp4S3Key": mp4_s3_key,
            "mp4GeneratedAt": mp4_generated_at,
            "dualMp4S3Key": dual_mp4_s3_key,
            "dualMp4GeneratedAt": dual_mp4_generated_at,
            # allPlayersStatsは /stats エンドポイントで取得
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
                    "uploadedAt": format_uploaded_at(upload.get("uploadedAt")),
                    "s3Key": upload.get("s3Key"),
                    "fileName": upload.get("fileName"),
                    "fileSize": upload.get("fileSize"),
                    "ownPlayer": upload.get("ownPlayer"),
                    # 動画情報（フロントエンド互換性のためreplaysにも含める）
                    "mp4S3Key": mp4_s3_key,
                    "mp4GeneratedAt": mp4_generated_at,
                    "dualMp4S3Key": dual_mp4_s3_key,
                    "dualMp4GeneratedAt": dual_mp4_generated_at,
                    "hasDualReplay": has_dual_replay,
                    # ゲームプレイ動画情報
                    "gameplayVideoS3Key": upload.get("gameplayVideoS3Key"),
                    "gameplayVideoSize": upload.get("gameplayVideoSize"),
                    "gameplayVideoUploadedAt": format_uploaded_at(upload.get("gameplayVideoUploadedAt")),
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

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps(match_info, cls=DecimalEncoder),
        }

    except Exception as e:
        print(f"Error in handle_match: {e}")
        import traceback

        traceback.print_exc()

        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": str(e)}),
        }


def handle_stats(event, context):
    """
    試合統計を取得

    STATSレコードからallPlayersStatsを返す
    """
    try:
        # OPTIONS request (preflight)
        http_method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
        if http_method == "OPTIONS":
            return {"statusCode": 200, "headers": CORS_HEADERS, "body": ""}

        # パスパラメータからarenaUniqueIDを取得
        path_parameters = event.get("pathParameters", {})
        arena_unique_id = path_parameters.get("arenaUniqueID")

        if not arena_unique_id:
            return {
                "statusCode": 400,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "arenaUniqueID is required"}),
            }

        # gameTypeを特定
        game_type = find_match_game_type(arena_unique_id)

        if not game_type:
            return {
                "statusCode": 404,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Match not found"}),
            }

        # STATSレコードを取得
        battle_client = BattleTableClient(game_type)
        stats = battle_client.get_stats(arena_unique_id)

        if not stats:
            return {
                "statusCode": 404,
                "headers": CORS_HEADERS,
                "body": json.dumps({"error": "Stats not found"}),
            }

        return {
            "statusCode": 200,
            "headers": CORS_HEADERS,
            "body": json.dumps(
                {
                    "arenaUniqueID": arena_unique_id,
                    "allPlayersStats": stats.get("allPlayersStats", []),
                },
                cls=DecimalEncoder,
            ),
        }

    except Exception as e:
        print(f"Error in handle_stats: {e}")
        import traceback

        traceback.print_exc()

        return {
            "statusCode": 500,
            "headers": CORS_HEADERS,
            "body": json.dumps({"error": str(e)}),
        }
