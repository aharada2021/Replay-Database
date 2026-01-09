"""
ダウンロードAPIハンドラー

クライアントツールなどのダウンロードリンクを署名付きURLで提供
"""

import json
import os

import boto3
from botocore.config import Config

# 環境変数
TEMP_BUCKET = os.environ.get("TEMP_BUCKET")  # serverless.ymlから設定される
FRONTEND_URL = os.environ.get("FRONTEND_URL")  # serverless.ymlから設定される

# S3クライアント（署名付きURL用に署名バージョンを指定）
s3_client = boto3.client(
    "s3",
    config=Config(signature_version="s3v4"),
    region_name="ap-northeast-1",
)

# 署名付きURLの有効期限（1時間）
URL_EXPIRATION = 3600


def get_cors_headers(origin=None):
    """CORS ヘッダーを取得"""
    allowed_origins = [
        FRONTEND_URL,
        "http://localhost:3000",
    ]

    if origin and origin in allowed_origins:
        return {
            "Access-Control-Allow-Origin": origin,
            "Access-Control-Allow-Credentials": "true",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
        }

    return {
        "Access-Control-Allow-Origin": allowed_origins[0],
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Headers": "Content-Type",
        "Access-Control-Allow-Methods": "GET, OPTIONS",
    }


def handle(event, context):
    """
    ダウンロードURL取得API

    GET /api/download?file=uploader
    → クライアントツールのダウンロード用署名付きURLを返す
    """
    try:
        origin = event.get("headers", {}).get("origin") or event.get("headers", {}).get("Origin")
        cors_headers = get_cors_headers(origin)

        # OPTIONSリクエスト
        http_method = event.get("requestContext", {}).get("http", {}).get("method")
        if http_method == "OPTIONS":
            return {"statusCode": 200, "headers": cors_headers, "body": ""}

        # クエリパラメータ取得
        query_params = event.get("queryStringParameters", {}) or {}
        file_type = query_params.get("file", "uploader")

        # ファイルタイプに応じたS3キーを決定
        file_mapping = {
            "uploader": "downloads/wows_replay_uploader.zip",
        }

        s3_key = file_mapping.get(file_type)
        if not s3_key:
            return {
                "statusCode": 400,
                "headers": {**cors_headers, "Content-Type": "application/json"},
                "body": json.dumps({"error": "Invalid file type"}),
            }

        # ファイルの存在確認
        try:
            s3_client.head_object(Bucket=TEMP_BUCKET, Key=s3_key)
        except s3_client.exceptions.ClientError as e:
            if e.response["Error"]["Code"] == "404":
                return {
                    "statusCode": 404,
                    "headers": {**cors_headers, "Content-Type": "application/json"},
                    "body": json.dumps({"error": "File not found"}),
                }
            raise

        # 署名付きURLを生成
        presigned_url = s3_client.generate_presigned_url(
            "get_object",
            Params={
                "Bucket": TEMP_BUCKET,
                "Key": s3_key,
                "ResponseContentDisposition": f'attachment; filename="{os.path.basename(s3_key)}"',
            },
            ExpiresIn=URL_EXPIRATION,
        )

        return {
            "statusCode": 200,
            "headers": {**cors_headers, "Content-Type": "application/json"},
            "body": json.dumps(
                {
                    "url": presigned_url,
                    "filename": os.path.basename(s3_key),
                    "expiresIn": URL_EXPIRATION,
                }
            ),
        }

    except Exception as e:
        print(f"Error in handle_download: {e}")
        return {
            "statusCode": 500,
            "headers": get_cors_headers(),
            "body": json.dumps({"error": str(e)}),
        }
