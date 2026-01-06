"""
動画生成APIハンドラー

オンデマンドでMP4動画を生成
"""

import json
import os
import boto3
import tempfile
from pathlib import Path

from core.replay_processor import ReplayProcessor
from utils import dynamodb

# 環境変数
REPLAYS_BUCKET = os.environ.get("REPLAYS_BUCKET", "wows-replay-bot-dev-temp")

# S3クライアント
s3_client = boto3.client("s3")


def handle(event, context):
    """
    動画生成APIのハンドラー

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
            "Access-Control-Allow-Methods": "POST, OPTIONS",
        }

        # OPTIONS request (preflight)
        http_method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
        if http_method == "OPTIONS":
            return {"statusCode": 200, "headers": cors_headers, "body": ""}

        # リクエストボディ解析
        body = event.get("body", "{}")
        if isinstance(body, str):
            params = json.loads(body)
        else:
            params = body

        # パラメータ
        arena_unique_id = params.get("arenaUniqueID")
        player_id = params.get("playerID")

        if arena_unique_id is None or player_id is None:
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": "arenaUniqueID and playerID are required"}),
            }

        # DynamoDBからレコードを取得
        record = dynamodb.get_replay_record(str(arena_unique_id), int(player_id))

        if not record:
            return {"statusCode": 404, "headers": cors_headers, "body": json.dumps({"error": "Record not found"})}

        # 既にMP4が生成されているかチェック
        if record.get("mp4S3Key"):
            # 既に存在する場合は署名付きURLを返す
            presigned_url = s3_client.generate_presigned_url(
                "get_object", Params={"Bucket": REPLAYS_BUCKET, "Key": record["mp4S3Key"]}, ExpiresIn=86400  # 24時間
            )

            return {
                "statusCode": 200,
                "headers": cors_headers,
                "body": json.dumps(
                    {"status": "already_exists", "mp4Url": presigned_url, "mp4S3Key": record["mp4S3Key"]}
                ),
            }

        # S3からリプレイファイルをダウンロード
        s3_key = record["s3Key"]
        print(f"Downloading replay from s3://{REPLAYS_BUCKET}/{s3_key}")

        with tempfile.NamedTemporaryFile(suffix=".wowsreplay", delete=False) as tmp_replay:
            replay_path = Path(tmp_replay.name)
            s3_client.download_fileobj(REPLAYS_BUCKET, s3_key, tmp_replay)

        try:
            # 一時出力ディレクトリ
            with tempfile.TemporaryDirectory() as tmp_output_dir:
                output_dir = Path(tmp_output_dir)
                output_dir.mkdir(parents=True, exist_ok=True)

                # MP4を生成
                print(f"Generating MP4 for {replay_path.name}")
                mp4_path = output_dir / f"{replay_path.stem}.mp4"
                success = ReplayProcessor.generate_minimap_video(replay_path, mp4_path)

                if not success or not mp4_path.exists():
                    raise Exception("MP4 generation failed")

                # S3にアップロード
                mp4_s3_key = f"videos/{arena_unique_id}/{player_id}/{replay_path.stem}.mp4"
                print(f"Uploading MP4 to s3://{REPLAYS_BUCKET}/{mp4_s3_key}")

                with open(mp4_path, "rb") as f:
                    s3_client.put_object(Bucket=REPLAYS_BUCKET, Key=mp4_s3_key, Body=f.read(), ContentType="video/mp4")

                # DynamoDBを更新
                dynamodb.update_video_info(
                    arena_unique_id=int(arena_unique_id), player_id=int(player_id), mp4_s3_key=mp4_s3_key
                )

                # 署名付きURLを生成
                presigned_url = s3_client.generate_presigned_url(
                    "get_object", Params={"Bucket": REPLAYS_BUCKET, "Key": mp4_s3_key}, ExpiresIn=86400  # 24時間
                )

                return {
                    "statusCode": 200,
                    "headers": cors_headers,
                    "body": json.dumps({"status": "generated", "mp4Url": presigned_url, "mp4S3Key": mp4_s3_key}),
                }

        finally:
            # 一時ファイルを削除
            if replay_path.exists():
                replay_path.unlink()

    except Exception as e:
        print(f"Error in generate_video_api_handler: {e}")
        import traceback

        traceback.print_exc()

        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)}),
        }
