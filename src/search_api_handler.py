"""
検索APIハンドラー

Web UIからの検索リクエストを処理
"""

import json
import os
from typing import Dict, Any
from decimal import Decimal

from utils import dynamodb


class DecimalEncoder(json.JSONEncoder):
    """DynamoDB Decimalオブジェクトをシリアライズするカスタムエンコーダー"""
    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)


def handle(event, context):
    """
    検索APIのハンドラー

    Args:
        event: APIイベント
        context: Lambdaコンテキスト

    Returns:
        APIレスポンス
    """
    try:
        # CORS headers
        cors_headers = {
            'Access-Control-Allow-Origin': '*',
            'Access-Control-Allow-Headers': 'Content-Type',
            'Access-Control-Allow-Methods': 'POST, OPTIONS'
        }

        # OPTIONS request (preflight)
        http_method = event.get('httpMethod') or event.get('requestContext', {}).get('http', {}).get('method')
        if http_method == 'OPTIONS':
            return {
                'statusCode': 200,
                'headers': cors_headers,
                'body': ''
            }

        # リクエストボディ解析
        body = event.get('body', '{}')
        if isinstance(body, str):
            params = json.loads(body)
        else:
            params = body

        # 検索パラメータ
        game_type = params.get('gameType')
        map_id = params.get('mapId')
        player_name = params.get('playerName')
        win_loss = params.get('winLoss')
        date_from = params.get('dateFrom')
        date_to = params.get('dateTo')
        limit = params.get('limit', 50)
        last_evaluated_key = params.get('lastEvaluatedKey')

        # 検索実行
        result = dynamodb.search_replays(
            game_type=game_type,
            map_id=map_id,
            player_name=player_name,
            win_loss=win_loss,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            last_evaluated_key=last_evaluated_key
        )

        # 既存レコードのownPlayerが配列の場合、単一オブジェクトに変換
        items = result['items']
        for item in items:
            if 'ownPlayer' in item and isinstance(item['ownPlayer'], list):
                item['ownPlayer'] = item['ownPlayer'][0] if item['ownPlayer'] else {}

        # レスポンス
        return {
            'statusCode': 200,
            'headers': cors_headers,
            'body': json.dumps({
                'items': items,
                'lastEvaluatedKey': result['last_evaluated_key'],
                'count': len(items)
            }, cls=DecimalEncoder)
        }

    except Exception as e:
        print(f"Error in search_api_handler: {e}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'headers': {
                'Access-Control-Allow-Origin': '*'
            },
            'body': json.dumps({'error': str(e)})
        }
