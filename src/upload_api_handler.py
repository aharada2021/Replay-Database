"""
リプレイアップロードAPIハンドラー

クライアント常駐ツールからのリプレイファイルアップロードを受け付ける
"""

import json
import os
import base64
import boto3
from pathlib import Path
from typing import Dict, Any
from datetime import datetime
import tempfile

from replay_processor import ReplayProcessor
from utils.arena_id_extractor import extract_arena_unique_id
from utils import dynamodb

# 環境変数
REPLAYS_BUCKET = os.environ.get('REPLAYS_BUCKET', 'wows-replay-bot-dev-temp')
UPLOAD_API_KEY = os.environ.get('UPLOAD_API_KEY', '')

# S3クライアント
s3_client = boto3.client('s3')


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
        headers = event.get('headers', {})
        api_key = headers.get('x-api-key') or headers.get('X-Api-Key')

        if not api_key or api_key != UPLOAD_API_KEY:
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Unauthorized'})
            }

        # リクエストボディ解析
        body = event.get('body', '')
        if event.get('isBase64Encoded', False):
            body = base64.b64decode(body)

        # マルチパートデータの解析（簡易実装）
        # 本番環境ではpython-multipartなどを使用
        content_type = headers.get('content-type') or headers.get('Content-Type', '')

        if 'multipart/form-data' not in content_type:
            return {
                'statusCode': 400,
                'body': json.dumps({'error': 'Content-Type must be multipart/form-data'})
            }

        # 一時ファイルに保存
        with tempfile.NamedTemporaryFile(suffix='.wowsreplay', delete=False) as tmp_file:
            tmp_path = Path(tmp_file.name)

            # ファイルデータを抽出（簡易実装）
            # 実際のマルチパートパーサーを使用する必要がある
            if isinstance(body, bytes):
                # バイナリデータから.wowsreplayファイルを抽出
                # 実装の簡略化のため、bodyがファイルそのものと仮定
                tmp_file.write(body)
            else:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Invalid file data'})
                }

        try:
            # メタデータ解析
            metadata = ReplayProcessor.parse_replay_metadata(tmp_path)

            if not metadata:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Invalid replay file'})
                }

            # プレイヤー情報取得
            players_info = ReplayProcessor.extract_players_info(metadata)
            game_type = ReplayProcessor.extract_game_type(metadata)

            # プレイヤーIDとプレイヤー名を取得
            player_id = metadata.get('playerID', 0)
            player_name = metadata.get('playerName', 'Unknown')

            # arenaUniqueIDを抽出
            try:
                arena_unique_id = extract_arena_unique_id(str(tmp_path))
            except Exception as e:
                print(f"arenaUniqueID extraction failed: {e}")
                arena_unique_id = None

            # arenaUniqueIDが取得できない場合はエラー
            if not arena_unique_id:
                return {
                    'statusCode': 400,
                    'body': json.dumps({'error': 'Failed to extract arenaUniqueID'})
                }

            # 重複チェック
            existing_record = dynamodb.check_duplicate_by_arena_id(arena_unique_id)

            if existing_record:
                # 重複している場合
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        'status': 'duplicate',
                        'arenaUniqueID': arena_unique_id,
                        'originalUploader': existing_record.get('uploadedBy', 'Unknown'),
                        'uploadedAt': existing_record.get('uploadedAt', 'Unknown')
                    })
                }

            # S3にアップロード
            file_name = f"{metadata.get('dateTime', 'unknown').replace(':', '-')}_{player_name}.wowsreplay"
            s3_key = f"replays/{arena_unique_id}/{player_id}/{file_name}"

            with open(tmp_path, 'rb') as f:
                s3_client.put_object(
                    Bucket=REPLAYS_BUCKET,
                    Key=s3_key,
                    Body=f.read(),
                    ContentType='application/octet-stream'
                )

            # ファイルサイズを取得
            file_size = tmp_path.stat().st_size

            # DynamoDBに保存
            # uploadedByは将来的にDiscord User IDなどを設定
            uploaded_by = headers.get('x-user-id', 'client-tool')

            dynamodb.put_replay_record(
                arena_unique_id=arena_unique_id,
                player_id=player_id,
                player_name=player_name,
                uploaded_by=uploaded_by,
                metadata=metadata,
                players_info=players_info,
                s3_key=s3_key,
                file_name=file_name,
                file_size=file_size,
                game_type=game_type
            )

            # 成功レスポンス
            return {
                'statusCode': 200,
                'body': json.dumps({
                    'status': 'uploaded',
                    'arenaUniqueID': arena_unique_id,
                    'isDuplicate': False,
                    's3Key': s3_key
                })
            }

        finally:
            # 一時ファイルを削除
            if tmp_path.exists():
                tmp_path.unlink()

    except Exception as e:
        print(f"Error in upload_api_handler: {e}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
