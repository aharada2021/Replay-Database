import os
import json
import logging
import boto3
from typing import Optional
import requests
from nacl.signing import VerifyKey
from nacl.exceptions import BadSignatureError

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 環境変数
DISCORD_PUBLIC_KEY = os.getenv('DISCORD_PUBLIC_KEY')
PROCESSOR_FUNCTION_NAME = os.getenv('PROCESSOR_FUNCTION_NAME', 'wows-replay-bot-dev-processor')

# Discord API Base URL
DISCORD_API_BASE = "https://discord.com/api/v10"

# Lambda client
lambda_client = boto3.client('lambda')


def verify_discord_signature(signature: str, timestamp: str, body: str) -> bool:
    """
    Discord Interactionsの署名を検証

    Args:
        signature: X-Signature-Ed25519 ヘッダー
        timestamp: X-Signature-Timestamp ヘッダー
        body: リクエストボディ

    Returns:
        検証結果
    """
    try:
        verify_key = VerifyKey(bytes.fromhex(DISCORD_PUBLIC_KEY))
        verify_key.verify(f"{timestamp}{body}".encode(), bytes.fromhex(signature))
        return True
    except BadSignatureError:
        return False




def handle_interaction(event, context):
    """
    Lambda関数のメインハンドラー

    Args:
        event: API Gateway event
        context: Lambda context

    Returns:
        API Gateway response
    """
    try:
        # 署名検証
        signature = event['headers'].get('x-signature-ed25519')
        timestamp = event['headers'].get('x-signature-timestamp')
        body = event['body']

        if not verify_discord_signature(signature, timestamp, body):
            logger.warning("Invalid signature")
            return {
                'statusCode': 401,
                'body': json.dumps({'error': 'Invalid signature'})
            }

        # リクエストボディをパース
        data = json.loads(body)
        interaction_type = data.get('type')

        # PING (type 1)
        if interaction_type == 1:
            return {
                'statusCode': 200,
                'body': json.dumps({'type': 1})
            }

        # Application Command (type 2)
        if interaction_type == 2:
            command_name = data['data']['name']

            if command_name == 'upload_replay':
                # 添付ファイルを取得
                attachments = data['data'].get('resolved', {}).get('attachments', {})

                if not attachments:
                    return {
                        'statusCode': 200,
                        'body': json.dumps({
                            "type": 4,
                            "data": {
                                "content": "❌ ファイルが添付されていません。",
                                "flags": 64
                            }
                        })
                    }

                # 最初の添付ファイルを処理
                attachment = list(attachments.values())[0]
                guild_id = data.get('guild_id')

                # Webhook URLを構築
                webhook_url = f"{DISCORD_API_BASE}/webhooks/{data['application_id']}/{data['token']}"

                # 処理用Lambda関数を非同期呼び出し
                payload = {
                    'attachment': attachment,
                    'guild_id': guild_id,
                    'webhook_url': webhook_url
                }

                try:
                    lambda_client.invoke(
                        FunctionName=PROCESSOR_FUNCTION_NAME,
                        InvocationType='Event',  # 非同期呼び出し
                        Payload=json.dumps(payload)
                    )
                    logger.info(f"処理用Lambda関数を呼び出しました: {PROCESSOR_FUNCTION_NAME}")
                except Exception as e:
                    logger.error(f"Lambda呼び出しエラー: {e}", exc_info=True)
                    return {
                        'statusCode': 200,
                        'body': json.dumps({
                            "type": 4,
                            "data": {
                                "content": f"❌ 処理の開始に失敗しました: {str(e)}",
                                "flags": 64
                            }
                        })
                    }

                # すぐにDeferred Responseを返す（処理中...）
                return {
                    'statusCode': 200,
                    'body': json.dumps({
                        "type": 5,  # Deferred response
                        "data": {
                            "flags": 64  # Ephemeral
                        }
                    })
                }

        # その他のInteraction
        return {
            'statusCode': 200,
            'body': json.dumps({
                "type": 4,
                "data": {
                    "content": "不明なコマンドです。",
                    "flags": 64
                }
            })
        }

    except Exception as e:
        logger.error(f"エラーが発生しました: {e}", exc_info=True)
        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
