"""
マルチパートアップロードAPIハンドラー

大容量ゲームプレイ動画ファイルのアップロードをS3マルチパートアップロードで処理する。
100MB以上のファイルでも安定してアップロードできる。

ワークフロー:
1. クライアント → init-multipart: アップロード開始（UploadIdと各パートのPresigned URLを取得）
2. クライアント → S3: 各パートを並列でアップロード
3. クライアント → complete-multipart: アップロード完了（S3でパートを結合）
"""

import json
import logging
import os
import re
import time

import boto3

from utils.dynamodb_tables import BattleTableClient, find_match_game_type

logger = logging.getLogger(__name__)

# 環境変数
REPLAYS_BUCKET = os.environ.get("REPLAYS_BUCKET", "wows-replay-bot-dev-temp")
UPLOAD_API_KEY = os.environ.get("UPLOAD_API_KEY", "")
# Presigned URL有効期限（秒）
MULTIPART_URL_EXPIRY = int(os.environ.get("MULTIPART_URL_EXPIRY", "3600"))
# パートサイズ（バイト） - 10MB
PART_SIZE = 10 * 1024 * 1024
# 最小パートサイズ（バイト） - 5MB（S3の制限）
MIN_PART_SIZE = 5 * 1024 * 1024
# 最大ファイルサイズ（バイト） - 2GB
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024
# 最大パート数（S3の制限）
MAX_PARTS = 10000

# S3クライアント
s3_client = boto3.client("s3")

# ArenaUniqueIDの有効パターン（英数字、ハイフン、アンダースコアのみ許可）
ARENA_ID_PATTERN = re.compile(r'^[a-zA-Z0-9_-]+$')
def _verify_api_key(headers: dict) -> bool:
    """API Keyを検証"""
    api_key = headers.get("x-api-key") or headers.get("X-Api-Key")
    return api_key and api_key == UPLOAD_API_KEY
def _unauthorized_response():
    """認証エラーレスポンス"""
    return {"statusCode": 401, "body": json.dumps({"error": "Unauthorized"})}
def _error_response(status_code: int, message: str):
    """エラーレスポンス"""
    return {"statusCode": status_code, "body": json.dumps({"error": message})}
def _validate_arena_unique_id(arena_unique_id: str) -> bool:
    """
    ArenaUniqueIDの形式を検証

    セキュリティ対策：パストラバーサル防止のため、
    英数字、ハイフン、アンダースコアのみを許可

    Args:
        arena_unique_id: 検証対象のID

    Returns:
        有効な形式の場合True
    """
    if not arena_unique_id:
        return False
    return bool(ARENA_ID_PATTERN.match(arena_unique_id))
def handle_init_multipart(event, context):
    """
    マルチパートアップロード開始

    リクエスト:
    {
        "arenaUniqueID": "xxx",
        "playerID": 12345,
        "fileSize": 123456789,
        "contentType": "video/mp4"
    }

    レスポンス:
    {
        "uploadId": "xxx",
        "s3Key": "gameplay-videos/xxx/12345/capture.mp4",
        "partUrls": [
            {"partNumber": 1, "url": "https://..."},
            {"partNumber": 2, "url": "https://..."},
            ...
        ],
        "partSize": 10485760
    }
    """
    try:
        headers = event.get("headers", {})
        if not _verify_api_key(headers):
            return _unauthorized_response()

        # リクエストボディ解析
        body = event.get("body", "")
        if event.get("isBase64Encoded", False):
            import base64
            body = base64.b64decode(body).decode("utf-8")

        data = json.loads(body) if isinstance(body, str) else body

        arena_unique_id = data.get("arenaUniqueID")
        player_id = data.get("playerID")
        file_size = data.get("fileSize", 0)
        content_type = data.get("contentType", "video/mp4")

        if not arena_unique_id or player_id is None:
            return _error_response(400, "arenaUniqueID and playerID are required")

        # ArenaUniqueIDの形式を検証（パストラバーサル防止）
        if not _validate_arena_unique_id(arena_unique_id):
            return _error_response(400, "Invalid arenaUniqueID format")

        if not file_size or file_size <= 0:
            return _error_response(400, "Valid fileSize is required")

        # ファイルサイズ上限チェック
        if file_size > MAX_FILE_SIZE:
            max_mb = MAX_FILE_SIZE // (1024 * 1024)
            return _error_response(400, f"File size exceeds maximum allowed ({max_mb}MB)")

        try:
            player_id_int = int(player_id)
        except (TypeError, ValueError):
            return _error_response(400, "playerID must be a valid integer")

        # S3キーを生成
        s3_key = f"gameplay-videos/{arena_unique_id}/{player_id_int}/capture.mp4"

        # マルチパートアップロードを開始
        response = s3_client.create_multipart_upload(
            Bucket=REPLAYS_BUCKET,
            Key=s3_key,
            ContentType=content_type,
        )
        upload_id = response["UploadId"]

        # パート数を計算
        num_parts = (file_size + PART_SIZE - 1) // PART_SIZE

        # パート数上限チェック（S3の制限）
        if num_parts > MAX_PARTS:
            return _error_response(400, f"File too large: exceeds {MAX_PARTS} parts limit")

        # 各パートのPresigned URLを生成
        part_urls = []
        for part_number in range(1, num_parts + 1):
            presigned_url = s3_client.generate_presigned_url(
                "upload_part",
                Params={
                    "Bucket": REPLAYS_BUCKET,
                    "Key": s3_key,
                    "UploadId": upload_id,
                    "PartNumber": part_number,
                },
                ExpiresIn=MULTIPART_URL_EXPIRY,
            )
            part_urls.append({
                "partNumber": part_number,
                "url": presigned_url,
            })

        logger.info(f"Multipart upload initiated: {s3_key} ({num_parts} parts)")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "uploadId": upload_id,
                "s3Key": s3_key,
                "partUrls": part_urls,
                "partSize": PART_SIZE,
            }),
        }

    except Exception as e:
        print(f"Error in handle_init_multipart: {e}")
        import traceback
        traceback.print_exc()
        return _error_response(500, "Internal server error")
def handle_complete_multipart(event, context):
    """
    マルチパートアップロード完了

    リクエスト:
    {
        "arenaUniqueID": "xxx",
        "playerID": 12345,
        "uploadId": "xxx",
        "parts": [
            {"PartNumber": 1, "ETag": "\"xxx\""},
            {"PartNumber": 2, "ETag": "\"xxx\""},
            ...
        ]
    }

    レスポンス:
    {
        "status": "success",
        "s3Key": "gameplay-videos/xxx/12345/capture.mp4",
        "location": "https://..."
    }
    """
    try:
        headers = event.get("headers", {})
        if not _verify_api_key(headers):
            return _unauthorized_response()

        # リクエストボディ解析
        body = event.get("body", "")
        if event.get("isBase64Encoded", False):
            import base64
            body = base64.b64decode(body).decode("utf-8")

        data = json.loads(body) if isinstance(body, str) else body

        arena_unique_id = data.get("arenaUniqueID")
        player_id = data.get("playerID")
        upload_id = data.get("uploadId")
        parts = data.get("parts", [])

        if not arena_unique_id or player_id is None:
            return _error_response(400, "arenaUniqueID and playerID are required")

        # ArenaUniqueIDの形式を検証（パストラバーサル防止）
        if not _validate_arena_unique_id(arena_unique_id):
            return _error_response(400, "Invalid arenaUniqueID format")

        if not upload_id:
            return _error_response(400, "uploadId is required")

        if not parts:
            return _error_response(400, "parts array is required")

        try:
            player_id_int = int(player_id)
        except (TypeError, ValueError):
            return _error_response(400, "playerID must be a valid integer")

        # S3キー
        s3_key = f"gameplay-videos/{arena_unique_id}/{player_id_int}/capture.mp4"

        # パート情報を正規化
        normalized_parts = []
        for part in parts:
            part_number = part.get("PartNumber") or part.get("partNumber")
            etag = part.get("ETag") or part.get("etag")
            if part_number and etag:
                normalized_parts.append({
                    "PartNumber": int(part_number),
                    "ETag": etag,
                })

        # パート番号でソート
        normalized_parts.sort(key=lambda x: x["PartNumber"])

        # マルチパートアップロードを完了
        response = s3_client.complete_multipart_upload(
            Bucket=REPLAYS_BUCKET,
            Key=s3_key,
            UploadId=upload_id,
            MultipartUpload={"Parts": normalized_parts},
        )

        logger.info(f"Multipart upload completed: {s3_key}")

        # ファイルサイズを取得
        head_response = s3_client.head_object(Bucket=REPLAYS_BUCKET, Key=s3_key)
        file_size = head_response.get("ContentLength", 0)

        # DynamoDBを更新
        game_type = find_match_game_type(arena_unique_id)
        if game_type:
            battle_client = BattleTableClient(game_type)
            uploaded_at = int(time.time())

            battle_client.update_gameplay_video_info(
                arena_unique_id=arena_unique_id,
                player_id=player_id_int,
                gameplay_video_s3_key=s3_key,
                file_size=file_size,
                uploaded_at=uploaded_at,
            )

            battle_client.update_match_has_gameplay_video(arena_unique_id, True)
            logger.info(f"Gameplay video info updated: {arena_unique_id}/{player_id_int}")
        else:
            logger.warning(f"Match not found for arenaUniqueID: {arena_unique_id}")

        return {
            "statusCode": 200,
            "body": json.dumps({
                "status": "success",
                "s3Key": s3_key,
                "location": response.get("Location", ""),
                "fileSize": file_size,
            }),
        }

    except s3_client.exceptions.NoSuchUpload:
        return _error_response(400, "Upload not found or already completed")
    except Exception as e:
        print(f"Error in handle_complete_multipart: {e}")
        import traceback
        traceback.print_exc()
        return _error_response(500, "Internal server error")
def handle_abort_multipart(event, context):
    """
    マルチパートアップロード中止

    リクエスト:
    {
        "arenaUniqueID": "xxx",
        "playerID": 12345,
        "uploadId": "xxx"
    }

    レスポンス:
    {
        "status": "aborted"
    }
    """
    try:
        headers = event.get("headers", {})
        if not _verify_api_key(headers):
            return _unauthorized_response()

        # リクエストボディ解析
        body = event.get("body", "")
        if event.get("isBase64Encoded", False):
            import base64
            body = base64.b64decode(body).decode("utf-8")

        data = json.loads(body) if isinstance(body, str) else body

        arena_unique_id = data.get("arenaUniqueID")
        player_id = data.get("playerID")
        upload_id = data.get("uploadId")

        if not arena_unique_id or player_id is None:
            return _error_response(400, "arenaUniqueID and playerID are required")

        # ArenaUniqueIDの形式を検証（パストラバーサル防止）
        if not _validate_arena_unique_id(arena_unique_id):
            return _error_response(400, "Invalid arenaUniqueID format")

        if not upload_id:
            return _error_response(400, "uploadId is required")

        try:
            player_id_int = int(player_id)
        except (TypeError, ValueError):
            return _error_response(400, "playerID must be a valid integer")

        # S3キー
        s3_key = f"gameplay-videos/{arena_unique_id}/{player_id_int}/capture.mp4"

        # マルチパートアップロードを中止
        s3_client.abort_multipart_upload(
            Bucket=REPLAYS_BUCKET,
            Key=s3_key,
            UploadId=upload_id,
        )

        logger.info(f"Multipart upload aborted: {s3_key}")

        return {
            "statusCode": 200,
            "body": json.dumps({"status": "aborted"}),
        }

    except s3_client.exceptions.NoSuchUpload:
        # 既に完了または中止済み
        return {
            "statusCode": 200,
            "body": json.dumps({"status": "already_aborted_or_completed"}),
        }
    except Exception as e:
        print(f"Error in handle_abort_multipart: {e}")
        import traceback
        traceback.print_exc()
        return _error_response(500, "Internal server error")
