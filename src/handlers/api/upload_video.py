"""
ゲームプレイ動画アップロードAPIハンドラー

動画ファイルをS3の一時パスにアップロードするためのPresigned URL生成と
マルチパートアップロード管理を提供する。

フロー:
1. クライアント → presign: アップロード用URL取得（小ファイルはPUT URL、大ファイルはマルチパート）
2. クライアント → S3: 動画ファイルをアップロード
3. （大ファイルのみ）クライアント → complete: マルチパートアップロード完了
4. クライアント → /api/upload: リプレイ送信時にvideoS3Keyをヘッダーで渡す
"""

import json
import logging
import os
import re
import uuid

import boto3

logger = logging.getLogger(__name__)

# 環境変数
REPLAYS_BUCKET = os.environ.get("REPLAYS_BUCKET", "wows-replay-bot-dev-temp")
UPLOAD_API_KEY = os.environ.get("UPLOAD_API_KEY", "")
# Presigned URL有効期限（秒）
PRESIGN_URL_EXPIRY = int(os.environ.get("PRESIGN_URL_EXPIRY", "3600"))
# パートサイズ（バイト） - 10MB
PART_SIZE = 10 * 1024 * 1024
# 最大ファイルサイズ（バイト） - 2GB
MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024
# 最大パート数（S3の制限）
MAX_PARTS = 10000
# マルチパートアップロード閾値（10MB）
MULTIPART_THRESHOLD = 10 * 1024 * 1024

# S3クライアント
s3_client = boto3.client("s3")


def _verify_api_key(headers: dict) -> bool:
    """API Keyを検証"""
    api_key = headers.get("x-api-key") or headers.get("X-Api-Key")
    return api_key and api_key == UPLOAD_API_KEY


def _error_response(status_code: int, message: str):
    """エラーレスポンス"""
    return {"statusCode": status_code, "body": json.dumps({"error": message})}


def _parse_json_body(event: dict) -> dict:
    """リクエストボディをJSONとしてパース"""
    body = event.get("body", "")
    if event.get("isBase64Encoded", False):
        import base64

        body = base64.b64decode(body).decode("utf-8")
    return json.loads(body) if isinstance(body, str) else body


def handle_presign(event, context):
    """
    動画アップロード用Presigned URLを生成

    小ファイル（< 10MB）: 単一PUT用Presigned URL
    大ファイル（≥ 10MB）: マルチパートアップロード開始 + パートURL一覧

    リクエスト:
    {
        "fileSize": 123456789,
        "contentType": "video/mp4"  (オプション)
    }

    レスポンス（小ファイル）:
    {
        "method": "single",
        "uploadUrl": "https://...",
        "s3Key": "pending-videos/{uuid}/capture.mp4"
    }

    レスポンス（大ファイル）:
    {
        "method": "multipart",
        "uploadId": "xxx",
        "s3Key": "pending-videos/{uuid}/capture.mp4",
        "partUrls": [{"partNumber": 1, "url": "https://..."}, ...],
        "partSize": 10485760
    }
    """
    try:
        headers = event.get("headers", {})
        if not _verify_api_key(headers):
            return {"statusCode": 401, "body": json.dumps({"error": "Unauthorized"})}

        data = _parse_json_body(event)

        file_size = data.get("fileSize", 0)
        content_type = data.get("contentType", "video/mp4")

        if not file_size or file_size <= 0:
            return _error_response(400, "Valid fileSize is required")

        if file_size > MAX_FILE_SIZE:
            max_mb = MAX_FILE_SIZE // (1024 * 1024)
            return _error_response(400, f"File size exceeds maximum allowed ({max_mb}MB)")

        # 一意なS3キーを生成（UUIDベース）
        upload_uuid = uuid.uuid4().hex[:16]
        s3_key = f"pending-videos/{upload_uuid}/capture.mp4"

        if file_size < MULTIPART_THRESHOLD:
            # 小ファイル: 単一PUT用Presigned URL
            presigned_url = s3_client.generate_presigned_url(
                "put_object",
                Params={
                    "Bucket": REPLAYS_BUCKET,
                    "Key": s3_key,
                    "ContentType": content_type,
                },
                ExpiresIn=PRESIGN_URL_EXPIRY,
            )

            logger.info(f"Single upload presigned URL generated: {s3_key}")

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "method": "single",
                        "uploadUrl": presigned_url,
                        "s3Key": s3_key,
                    }
                ),
            }
        else:
            # 大ファイル: マルチパートアップロード開始
            response = s3_client.create_multipart_upload(
                Bucket=REPLAYS_BUCKET,
                Key=s3_key,
                ContentType=content_type,
            )
            upload_id = response["UploadId"]

            # パート数を計算
            num_parts = (file_size + PART_SIZE - 1) // PART_SIZE

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
                    ExpiresIn=PRESIGN_URL_EXPIRY,
                )
                part_urls.append(
                    {
                        "partNumber": part_number,
                        "url": presigned_url,
                    }
                )

            logger.info(f"Multipart upload initiated: {s3_key} ({num_parts} parts)")

            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "method": "multipart",
                        "uploadId": upload_id,
                        "s3Key": s3_key,
                        "partUrls": part_urls,
                        "partSize": PART_SIZE,
                    }
                ),
            }

    except Exception as e:
        print(f"Error in handle_presign: {e}")
        import traceback

        traceback.print_exc()
        return _error_response(500, "Internal server error")


# S3キーの検証パターン（pending-videos/{hex16}/capture.mp4）
PENDING_VIDEO_KEY_PATTERN = re.compile(r"^pending-videos/[a-f0-9]{16}/capture\.mp4$")


def handle_complete_multipart(event, context):
    """
    マルチパートアップロード完了（S3操作のみ、DB更新なし）

    リクエスト:
    {
        "s3Key": "pending-videos/{uuid}/capture.mp4",
        "uploadId": "xxx",
        "parts": [
            {"PartNumber": 1, "ETag": "\"xxx\""},
            ...
        ]
    }

    レスポンス:
    {
        "status": "success",
        "s3Key": "pending-videos/{uuid}/capture.mp4"
    }
    """
    try:
        headers = event.get("headers", {})
        if not _verify_api_key(headers):
            return {"statusCode": 401, "body": json.dumps({"error": "Unauthorized"})}

        data = _parse_json_body(event)

        s3_key = data.get("s3Key")
        upload_id = data.get("uploadId")
        parts = data.get("parts", [])

        if not s3_key or not upload_id or not parts:
            return _error_response(400, "s3Key, uploadId, and parts are required")

        # S3キーの形式を検証（セキュリティ対策）
        if not PENDING_VIDEO_KEY_PATTERN.match(s3_key):
            return _error_response(400, "Invalid s3Key format")

        # パート情報を正規化
        normalized_parts = []
        for part in parts:
            part_number = part.get("PartNumber") or part.get("partNumber")
            etag = part.get("ETag") or part.get("etag")
            if part_number and etag:
                normalized_parts.append(
                    {
                        "PartNumber": int(part_number),
                        "ETag": etag,
                    }
                )

        normalized_parts.sort(key=lambda x: x["PartNumber"])

        # マルチパートアップロードを完了
        s3_client.complete_multipart_upload(
            Bucket=REPLAYS_BUCKET,
            Key=s3_key,
            UploadId=upload_id,
            MultipartUpload={"Parts": normalized_parts},
        )

        logger.info(f"Multipart upload completed: {s3_key}")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "status": "success",
                    "s3Key": s3_key,
                }
            ),
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
        "s3Key": "pending-videos/{uuid}/capture.mp4",
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
            return {"statusCode": 401, "body": json.dumps({"error": "Unauthorized"})}

        data = _parse_json_body(event)

        s3_key = data.get("s3Key")
        upload_id = data.get("uploadId")

        if not s3_key or not upload_id:
            return _error_response(400, "s3Key and uploadId are required")

        # S3キーの形式を検証
        if not PENDING_VIDEO_KEY_PATTERN.match(s3_key):
            return _error_response(400, "Invalid s3Key format")

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
        return {
            "statusCode": 200,
            "body": json.dumps({"status": "already_aborted_or_completed"}),
        }
    except Exception as e:
        print(f"Error in handle_abort_multipart: {e}")
        import traceback

        traceback.print_exc()
        return _error_response(500, "Internal server error")
