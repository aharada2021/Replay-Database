"""
リプレイアップロードAPIハンドラー

クライアント常駐ツールからのリプレイファイルアップロードを受け付ける
ゲームプレイ動画のアップロード用Presigned URLも生成
動画アップロード完了通知も処理
"""

import json
import os
import base64
import time
import boto3
from pathlib import Path
import tempfile

from core.replay_metadata import ReplayMetadataParser
from utils import dynamodb
from utils.dynamodb_tables import BattleTableClient, find_match_game_type

# 環境変数
REPLAYS_BUCKET = os.environ.get("REPLAYS_BUCKET", "wows-replay-bot-dev-temp")
UPLOAD_API_KEY = os.environ.get("UPLOAD_API_KEY", "")
# ゲームプレイ動画のPresigned URL有効期限（秒）
VIDEO_UPLOAD_URL_EXPIRY = int(os.environ.get("VIDEO_UPLOAD_URL_EXPIRY", "3600"))

# S3クライアント
s3_client = boto3.client("s3")


def generate_video_upload_url(arena_unique_id: str, player_id: int) -> dict:
    """
    ゲームプレイ動画アップロード用のPresigned URLを生成

    Args:
        arena_unique_id: アリーナユニークID
        player_id: プレイヤーID

    Returns:
        {
            "uploadUrl": Presigned PUT URL,
            "s3Key": S3キー
        }
    """
    s3_key = f"gameplay-videos/{arena_unique_id}/{player_id}/capture.mp4"

    presigned_url = s3_client.generate_presigned_url(
        "put_object",
        Params={
            "Bucket": REPLAYS_BUCKET,
            "Key": s3_key,
            "ContentType": "video/mp4",
        },
        ExpiresIn=VIDEO_UPLOAD_URL_EXPIRY,
    )

    return {
        "uploadUrl": presigned_url,
        "s3Key": s3_key,
    }


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
            # メタデータのplayerIDは常に0なので、vehicles配列から自分のプレイヤーIDを取得
            player_id = 0
            vehicles = metadata.get("vehicles", [])
            for vehicle in vehicles:
                if vehicle.get("relation") == 0:  # relation=0 は自分
                    player_id = vehicle.get("id", 0)
                    break
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

            # ゲームプレイ動画アップロード用Presigned URLを生成
            video_upload_info = generate_video_upload_url(temp_arena_id, player_id)

            # 成功レスポンス
            return {
                "statusCode": 200,
                "body": json.dumps(
                    {
                        "status": "uploaded",
                        "tempArenaID": temp_arena_id,
                        "playerID": player_id,
                        "message": "Uploaded successfully. ArenaUniqueID will be extracted asynchronously.",
                        "s3Key": s3_key,
                        # ゲームプレイ動画アップロード用
                        "videoUploadUrl": video_upload_info["uploadUrl"],
                        "videoS3Key": video_upload_info["s3Key"],
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

        # 内部エラーの詳細は隠蔽
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error"})}


def handle_video_complete(event, context):
    """
    ゲームプレイ動画アップロード完了通知のハンドラー

    クライアントがS3への動画アップロード完了後に呼び出す

    Args:
        event: APIイベント
        context: Lambdaコンテキスト

    Returns:
        APIレスポンス
    """
    import re

    try:
        # API Key認証
        headers = event.get("headers", {})
        api_key = headers.get("x-api-key") or headers.get("X-Api-Key")

        if not api_key or api_key != UPLOAD_API_KEY:
            return {"statusCode": 401, "body": json.dumps({"error": "Unauthorized"})}

        # リクエストボディ解析
        body = event.get("body", "")
        if event.get("isBase64Encoded", False):
            body = base64.b64decode(body).decode("utf-8")

        data = json.loads(body) if isinstance(body, str) else body

        arena_unique_id = data.get("arenaUniqueID")
        player_id = data.get("playerID")
        video_s3_key = data.get("videoS3Key")
        file_size = data.get("fileSize", 0)

        if not arena_unique_id or player_id is None or not video_s3_key:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "arenaUniqueID, playerID, and videoS3Key are required"}),
            }

        # player_idの型検証
        try:
            player_id_int = int(player_id)
        except (TypeError, ValueError):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "playerID must be a valid integer"}),
            }

        # S3キーの形式を検証（セキュリティ対策）
        expected_pattern = rf"^gameplay-videos/{re.escape(arena_unique_id)}/{player_id_int}/capture\.mp4$"
        if not re.match(expected_pattern, video_s3_key):
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Invalid videoS3Key format"}),
            }

        # S3にファイルが存在するか確認
        try:
            s3_client.head_object(Bucket=REPLAYS_BUCKET, Key=video_s3_key)
        except s3_client.exceptions.NoSuchKey:
            return {
                "statusCode": 400,
                "body": json.dumps({"error": "Video file not found in S3"}),
            }
        except Exception as e:
            # ClientErrorの場合は404チェック
            error_code = getattr(e, "response", {}).get("Error", {}).get("Code", "")
            if error_code == "404":
                return {
                    "statusCode": 400,
                    "body": json.dumps({"error": "Video file not found in S3"}),
                }
            raise

        # gameTypeを特定
        game_type = find_match_game_type(arena_unique_id)

        if not game_type:
            # arenaUniqueIDがまだ更新されていない可能性があるため、警告のみ
            print(f"Warning: Match not found for arenaUniqueID: {arena_unique_id}")
            return {
                "statusCode": 202,
                "body": json.dumps(
                    {
                        "status": "pending",
                        "message": "Match not found yet, video info will be updated when match is processed",
                    }
                ),
            }

        # DynamoDBを更新
        battle_client = BattleTableClient(game_type)
        uploaded_at = int(time.time())

        battle_client.update_gameplay_video_info(
            arena_unique_id=arena_unique_id,
            player_id=player_id_int,
            gameplay_video_s3_key=video_s3_key,
            file_size=file_size,
            uploaded_at=uploaded_at,
        )

        # MATCHレコードにフラグを設定
        battle_client.update_match_has_gameplay_video(arena_unique_id, True)

        print(f"Gameplay video info updated: {arena_unique_id}/{player_id_int} -> {video_s3_key}")

        return {
            "statusCode": 200,
            "body": json.dumps(
                {
                    "status": "success",
                    "message": "Gameplay video info updated",
                    "arenaUniqueID": arena_unique_id,
                    "playerID": player_id_int,
                    "videoS3Key": video_s3_key,
                }
            ),
        }

    except Exception as e:
        print(f"Error in handle_video_complete: {e}")
        import traceback

        traceback.print_exc()

        # 内部エラーの詳細は隠蔽
        return {"statusCode": 500, "body": json.dumps({"error": "Internal server error"})}
