"""
動画生成APIハンドラー

オンデマンドでMP4動画を生成
Dual Render対応: 敵味方リプレイが存在する場合は両陣営視点動画を生成
"""

import json
import os
import boto3
import tempfile
from pathlib import Path

from core.replay_processor import ReplayProcessor
from utils import dynamodb
from utils.discord_notify import send_replay_notification
from utils.dual_render import (
    are_opposing_teams,
    get_dual_render_tags,
    generate_dual_s3_key,
)

# 環境変数
REPLAYS_BUCKET = os.environ.get("REPLAYS_BUCKET", "wows-replay-bot-dev-temp")
DISCORD_BOT_TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
NOTIFICATION_CHANNEL_ID = os.environ.get("NOTIFICATION_CHANNEL_ID", "")

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
            return {
                "statusCode": 404,
                "headers": cors_headers,
                "body": json.dumps({"error": "Record not found"}),
            }

        # Dual動画が既に生成されているかチェック
        if record.get("dualMp4S3Key"):
            presigned_url = s3_client.generate_presigned_url(
                "get_object",
                Params={
                    "Bucket": REPLAYS_BUCKET,
                    "Key": record["dualMp4S3Key"],
                },
                ExpiresIn=86400,  # 24時間
            )
            return {
                "statusCode": 200,
                "headers": cors_headers,
                "body": json.dumps(
                    {
                        "status": "already_exists",
                        "mp4Url": presigned_url,
                        "mp4S3Key": record["dualMp4S3Key"],
                        "isDual": True,
                    }
                ),
            }

        # 既にMP4が生成されているかチェック（Dualではない通常動画）
        if record.get("mp4S3Key"):
            # 既に存在する場合は署名付きURLを返す
            presigned_url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": REPLAYS_BUCKET, "Key": record["mp4S3Key"]},
                ExpiresIn=86400,  # 24時間
            )

            return {
                "statusCode": 200,
                "headers": cors_headers,
                "body": json.dumps(
                    {
                        "status": "already_exists",
                        "mp4Url": presigned_url,
                        "mp4S3Key": record["mp4S3Key"],
                        "isDual": False,
                    }
                ),
            }

        # 同一arenaの全リプレイを取得して敵味方ペアを探す
        all_replays = dynamodb.get_replays_for_arena(str(arena_unique_id))
        opposing_replay = None

        for other_replay in all_replays:
            if other_replay.get("playerID") == int(player_id):
                continue  # 自分自身はスキップ
            if are_opposing_teams(record, other_replay):
                opposing_replay = other_replay
                break

        # Dual動画生成可能かどうか
        can_generate_dual = opposing_replay is not None and opposing_replay.get("s3Key")

        if can_generate_dual:
            print(f"Opposing replay found: playerID={opposing_replay.get('playerID')}")
            return generate_dual_video(arena_unique_id, record, opposing_replay, cors_headers)
        else:
            # 通常の単一動画生成
            return generate_single_video(arena_unique_id, player_id, record, cors_headers)

    except Exception as e:
        print(f"Error in generate_video_api_handler: {e}")
        import traceback

        traceback.print_exc()

        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)}),
        }


def generate_single_video(arena_unique_id, player_id, record, cors_headers):
    """
    単一のリプレイから動画を生成

    Args:
        arena_unique_id: arenaUniqueID
        player_id: プレイヤーID
        record: DynamoDBレコード
        cors_headers: CORSヘッダー

    Returns:
        APIレスポンス
    """
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
                s3_client.put_object(
                    Bucket=REPLAYS_BUCKET,
                    Key=mp4_s3_key,
                    Body=f.read(),
                    ContentType="video/mp4",
                )

            # DynamoDBを更新
            dynamodb.update_video_info(
                arena_unique_id=int(arena_unique_id),
                player_id=int(player_id),
                mp4_s3_key=mp4_s3_key,
            )

            # 署名付きURLを生成
            presigned_url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": REPLAYS_BUCKET, "Key": mp4_s3_key},
                ExpiresIn=86400,  # 24時間
            )

            # Discord通知を送信（Auto-uploader経由のアップロード時、クラン戦のみ）
            if NOTIFICATION_CHANNEL_ID and DISCORD_BOT_TOKEN:
                # 最新のレコードを取得（統計情報が含まれている）
                updated_record = dynamodb.get_replay_record(str(arena_unique_id), int(player_id))
                if updated_record and updated_record.get("gameType") == "clan":
                    send_replay_notification(
                        channel_id=NOTIFICATION_CHANNEL_ID,
                        bot_token=DISCORD_BOT_TOKEN,
                        record=updated_record,
                        mp4_url=presigned_url,
                    )

            return {
                "statusCode": 200,
                "headers": cors_headers,
                "body": json.dumps(
                    {
                        "status": "generated",
                        "mp4Url": presigned_url,
                        "mp4S3Key": mp4_s3_key,
                        "isDual": False,
                    }
                ),
            }

    finally:
        # 一時ファイルを削除
        if replay_path.exists():
            replay_path.unlink()


def generate_dual_video(arena_unique_id, green_record, red_record, cors_headers):
    """
    2つのリプレイからDual動画を生成

    Args:
        arena_unique_id: arenaUniqueID
        green_record: 味方視点（リクエスト元）のDynamoDBレコード
        red_record: 敵視点のDynamoDBレコード
        cors_headers: CORSヘッダー

    Returns:
        APIレスポンス
    """
    green_s3_key = green_record["s3Key"]
    red_s3_key = red_record["s3Key"]
    green_player_id = green_record["playerID"]
    red_player_id = red_record["playerID"]

    print(f"Generating Dual video: green={green_s3_key}, red={red_s3_key}")

    # 両方のリプレイをダウンロード
    with tempfile.NamedTemporaryFile(suffix=".wowsreplay", delete=False) as tmp_green:
        green_path = Path(tmp_green.name)
        s3_client.download_fileobj(REPLAYS_BUCKET, green_s3_key, tmp_green)

    with tempfile.NamedTemporaryFile(suffix=".wowsreplay", delete=False) as tmp_red:
        red_path = Path(tmp_red.name)
        s3_client.download_fileobj(REPLAYS_BUCKET, red_s3_key, tmp_red)

    try:
        with tempfile.TemporaryDirectory() as tmp_output_dir:
            output_dir = Path(tmp_output_dir)
            output_dir.mkdir(parents=True, exist_ok=True)

            # クランタグを取得
            green_tag, red_tag = get_dual_render_tags(green_record, red_record)
            print(f"Dual tags: green={green_tag}, red={red_tag}")

            # Dual MP4を生成
            dual_mp4_path = output_dir / f"dual_{arena_unique_id}.mp4"
            success = ReplayProcessor.generate_dual_minimap_video(
                green_path,
                red_path,
                dual_mp4_path,
                green_tag=green_tag,
                red_tag=red_tag,
            )

            if not success or not dual_mp4_path.exists():
                raise Exception("Dual MP4 generation failed")

            # S3にアップロード
            dual_s3_key = generate_dual_s3_key(str(arena_unique_id))
            print(f"Uploading Dual MP4 to s3://{REPLAYS_BUCKET}/{dual_s3_key}")

            with open(dual_mp4_path, "rb") as f:
                s3_client.put_object(
                    Bucket=REPLAYS_BUCKET,
                    Key=dual_s3_key,
                    Body=f.read(),
                    ContentType="video/mp4",
                )

            # 両方のレコードにDual動画情報を更新
            dynamodb.batch_update_dual_video_info(
                arena_unique_id=str(arena_unique_id),
                player_ids=[int(green_player_id), int(red_player_id)],
                dual_mp4_s3_key=dual_s3_key,
            )

            # 署名付きURLを生成
            presigned_url = s3_client.generate_presigned_url(
                "get_object",
                Params={"Bucket": REPLAYS_BUCKET, "Key": dual_s3_key},
                ExpiresIn=86400,  # 24時間
            )

            # Discord通知を送信（クラン戦のみ）
            if NOTIFICATION_CHANNEL_ID and DISCORD_BOT_TOKEN:
                updated_record = dynamodb.get_replay_record(str(arena_unique_id), int(green_player_id))
                if updated_record and updated_record.get("gameType") == "clan":
                    send_replay_notification(
                        channel_id=NOTIFICATION_CHANNEL_ID,
                        bot_token=DISCORD_BOT_TOKEN,
                        record=updated_record,
                        mp4_url=presigned_url,
                        is_dual=True,
                    )

            return {
                "statusCode": 200,
                "headers": cors_headers,
                "body": json.dumps(
                    {
                        "status": "generated",
                        "mp4Url": presigned_url,
                        "mp4S3Key": dual_s3_key,
                        "isDual": True,
                    }
                ),
            }

    finally:
        # 一時ファイルを削除
        if green_path.exists():
            green_path.unlink()
        if red_path.exists():
            red_path.unlink()
