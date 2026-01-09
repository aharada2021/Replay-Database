"""
リプレイアップロードAPIハンドラー

クライアント常駐ツールからのリプレイファイルアップロードを受け付ける
"""

import json
import os
import base64
import boto3
from pathlib import Path
import tempfile

from core.replay_metadata import ReplayMetadataParser
from utils import dynamodb

# 環境変数
REPLAYS_BUCKET = os.environ.get("REPLAYS_BUCKET", "wows-replay-bot-dev-temp")
UPLOAD_API_KEY = os.environ.get("UPLOAD_API_KEY", "")

# S3クライアント
s3_client = boto3.client("s3")


def handle(event, context):
    """
    アップロードAPIのハンドラー

    Args:
        event: APIイベント
        context: Lambdaコンテキスト

    Returns:
        APIレスポンス
    """
    try:
        # API Key認証
        headers = event.get("headers", {})
        api_key = headers.get("x-api-key") or headers.get("X-Api-Key")

        if not api_key or api_key != UPLOAD_API_KEY:
            return {"statusCode": 401, "body": json.dumps({"error": "Unauthorized"})}

        # リクエストボディ解析
        body = event.get("body", "")
        if event.get("isBase64Encoded", False):
            body = base64.b64decode(body)

        # マルチパートデータの解析
        content_type = headers.get("content-type") or headers.get("Content-Type", "")

        if "multipart/form-data" not in content_type:
            return {"statusCode": 400, "body": json.dumps({"error": "Content-Type must be multipart/form-data"})}

        if not isinstance(body, bytes):
            return {"statusCode": 400, "body": json.dumps({"error": "Invalid request body"})}

        # バウンダリーを抽出
        boundary_match = content_type.split("boundary=")
        if len(boundary_match) < 2:
            return {"statusCode": 400, "body": json.dumps({"error": "No boundary in Content-Type"})}

        boundary = boundary_match[1].strip()
        boundary_bytes = f"--{boundary}".encode()

        # マルチパートデータからファイル部分を抽出
        parts = body.split(boundary_bytes)
        file_data = None

        for part in parts:
            if b"Content-Disposition" in part and b"filename=" in part:
                # ヘッダーとボディを分離
                header_end = part.find(b"\r\n\r\n")
                if header_end == -1:
                    header_end = part.find(b"\n\n")

                if header_end != -1:
                    # ファイルデータを抽出
                    file_start = header_end + 4 if b"\r\n\r\n" in part[: header_end + 4] else header_end + 2
                    file_data = part[file_start:].rstrip(b"\r\n").rstrip(b"--")
                    break

        if not file_data:
            return {"statusCode": 400, "body": json.dumps({"error": "No file found in multipart data"})}

        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(suffix=".wowsreplay", delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)
            tmp_file.write(file_data)

        try:
            # メタデータ解析（API呼び出しなし、ファイル解析のみ）
            metadata = ReplayMetadataParser.parse_replay_metadata(tmp_path)

            if not metadata:
                return {"statusCode": 400, "body": json.dumps({"error": "Invalid replay file"})}

            # ゲームタイプのみ抽出（API呼び出しなし）
            game_type = ReplayMetadataParser.extract_game_type(metadata)

            # プレイヤー情報は最小限のみ（API呼び出しをスキップ）
            # 詳細情報はS3トリガー（battle-result-extractor）で後から取得
            players_info = {"own": [], "allies": [], "enemies": []}

            # プレイヤーIDとプレイヤー名を取得
            player_id = metadata.get("playerID", 0)
            player_name = metadata.get("playerName", "Unknown")

            # 一時的なIDを生成（日時+プレイヤーID+マップ名のハッシュ）
            # arenaUniqueIDはbattle-result-extractorで後から抽出して更新
            import hashlib

            temp_id_source = f"{metadata.get('dateTime', '')}_{player_id}_{metadata.get('mapName', '')}"
            temp_arena_id = hashlib.md5(temp_id_source.encode()).hexdigest()[:16]

            print(f"一時的なID生成: {temp_arena_id} (後でarenaUniqueIDに更新されます)")

            # S3にアップロード（一時IDを使用）
            file_name = f"{metadata.get('dateTime', 'unknown').replace(':', '-')}_{player_name}.wowsreplay"
            s3_key = f"replays/{temp_arena_id}/{player_id}/{file_name}"

            with open(tmp_path, "rb") as f:
                s3_client.put_object(
                    Bucket=REPLAYS_BUCKET, Key=s3_key, Body=f.read(), ContentType="application/octet-stream"
                )

            # ファイルサイズを取得
            file_size = tmp_path.stat().st_size

            # DynamoDBに保存
            # uploadedByは将来的にDiscord User IDなどを設定
            uploaded_by = headers.get("x-user-id", "client-tool")

            dynamodb.put_replay_record(
                arena_unique_id=temp_arena_id,  # 一時ID、後でbattle-result-extractorが更新
                player_id=player_id,
                player_name=player_name,
                uploaded_by=uploaded_by,
                metadata=metadata,
                players_info=players_info,
                s3_key=s3_key,
                file_name=file_name,
                file_size=file_size,
                game_type=game_type,
            )

            # 成功レスポンス
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "status": "uploaded",
                        "tempArenaID": temp_arena_id,
                        "message": "Uploaded successfully. ArenaUniqueID will be extracted asynchronously.",
                        "s3Key": s3_key,
                    }
                ),
            }

        finally:
            # 一時ファイルを削除
            if tmp_path.exists():
                tmp_path.unlink()

    except Exception as e:
        print(f"Error in upload_api_handler: {e}")
        import traceback

        traceback.print_exc()

        return {"statusCode": 500, "body": json.dumps({"error": str(e)})}
