"""
Claude AI データ分析APIハンドラー

DynamoDBの戦闘データについてClaude AIに自然言語で質問できるAPI。

Version: 2026-01-23 - Initial implementation
"""

import json
import os
import time
import traceback
from decimal import Decimal

import boto3

from utils.rate_limiter import (
    check_rate_limit,
    record_usage,
    get_usage_summary,
)
from utils.data_aggregator import get_aggregated_data_for_analysis
from utils.claude_client import analyze_battles

# 環境変数
SESSIONS_TABLE = os.environ.get("SESSIONS_TABLE", "wows-sessions-dev")
FRONTEND_URL = os.environ.get("FRONTEND_URL", "http://localhost:3000")

# DynamoDB
dynamodb = boto3.resource("dynamodb")
sessions_table = dynamodb.Table(SESSIONS_TABLE)


class DecimalEncoder(json.JSONEncoder):
    """DynamoDB Decimal型をJSON化するためのエンコーダー"""

    def default(self, obj):
        if isinstance(obj, Decimal):
            if obj % 1 == 0:
                return int(obj)
            return float(obj)
        return super().default(obj)


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
            "Access-Control-Allow-Headers": "Content-Type, Cookie",
            "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
        }

    return {
        "Access-Control-Allow-Origin": allowed_origins[0] if allowed_origins else "*",
        "Access-Control-Allow-Credentials": "true",
        "Access-Control-Allow-Headers": "Content-Type, Cookie",
        "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    }


def get_cookie(event, name):
    """CookieからセッションIDを取得"""
    cookies = event.get("cookies", [])
    for cookie in cookies:
        if cookie.startswith(f"{name}="):
            return cookie.split("=", 1)[1].split(";")[0]

    # headers から取得（HTTP API v2）
    headers = event.get("headers", {})
    cookie_header = headers.get("cookie") or headers.get("Cookie", "")
    for part in cookie_header.split(";"):
        part = part.strip()
        if part.startswith(f"{name}="):
            return part.split("=", 1)[1]

    return None


def get_authenticated_user(event):
    """
    セッションから認証済みユーザー情報を取得

    Args:
        event: Lambda event

    Returns:
        Tuple of (user_info, error_response)
        - user_info: ユーザー情報dict（認証成功時）
        - error_response: エラーレスポンスdict（認証失敗時）
    """
    origin = event.get("headers", {}).get("origin") or event.get("headers", {}).get("Origin")
    cors_headers = get_cors_headers(origin)

    # セッションID取得
    session_id = get_cookie(event, "session_id")

    if not session_id:
        return None, {
            "statusCode": 401,
            "headers": cors_headers,
            "body": json.dumps({"error": "ログインが必要です"}),
        }

    # セッション取得
    try:
        response = sessions_table.get_item(Key={"sessionId": session_id})
        session = response.get("Item")
    except Exception as e:
        print(f"Session lookup error: {e}")
        return None, {
            "statusCode": 401,
            "headers": cors_headers,
            "body": json.dumps({"error": "セッションエラー"}),
        }

    if not session:
        return None, {
            "statusCode": 401,
            "headers": cors_headers,
            "body": json.dumps({"error": "セッションが見つかりません"}),
        }

    # 有効期限チェック
    if session.get("expiresAt", 0) < int(time.time()):
        sessions_table.delete_item(Key={"sessionId": session_id})
        return None, {
            "statusCode": 401,
            "headers": cors_headers,
            "body": json.dumps({"error": "セッションが期限切れです"}),
        }

    # ユーザー情報を返す
    user_info = {
        "discordUserId": session.get("discordUserId"),
        "discordUsername": session.get("discordUsername"),
        "discordGlobalName": session.get("discordGlobalName"),
    }

    return user_info, None


def handle(event, context):
    """
    Claude AI データ分析API

    POST /api/analyze
    Request body:
    {
        "query": "最近負けが多いのはなぜ？",
        "gameType": "clan",  // optional
        "dateRange": {  // optional
            "from": "2026-01-01",
            "to": "2026-01-22"
        },
        "limit": 50  // optional
    }

    Response:
    {
        "analysis": "## 分析結果\n\n最近10試合の勝率は40%で...",
        "dataUsed": {
            "totalBattles": 50,
            "dateRange": {"from": "2026-01-01", "to": "2026-01-22"}
        },
        "tokensUsed": 5200,
        "remainingQueries": 4
    }
    """
    try:
        origin = event.get("headers", {}).get("origin") or event.get("headers", {}).get("Origin")
        cors_headers = get_cors_headers(origin)

        # OPTIONSリクエスト（CORS preflight）
        http_method = event.get("requestContext", {}).get("http", {}).get("method")
        if http_method == "OPTIONS":
            return {"statusCode": 200, "headers": cors_headers, "body": ""}

        # 認証チェック
        user_info, error_response = get_authenticated_user(event)
        if error_response:
            return error_response

        discord_user_id = user_info["discordUserId"]

        # リクエストボディをパース
        body = event.get("body", "{}")
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except json.JSONDecodeError:
                return {
                    "statusCode": 400,
                    "headers": cors_headers,
                    "body": json.dumps({"error": "無効なリクエストボディです"}),
                }

        # パラメータ取得
        query = body.get("query", "").strip()
        game_type = body.get("gameType")
        date_range = body.get("dateRange", {})
        limit = min(int(body.get("limit", 50)), 100)  # 最大100

        # クエリバリデーション
        if not query:
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": "クエリを入力してください"}),
            }

        if len(query) > 500:
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": "クエリは500文字以内で入力してください"}),
            }

        # レート制限チェック
        is_allowed, error_msg, usage_info = check_rate_limit(discord_user_id)
        if not is_allowed:
            return {
                "statusCode": 429,
                "headers": cors_headers,
                "body": json.dumps({
                    "error": error_msg,
                    "usageInfo": usage_info,
                }),
            }

        # 日付範囲を取得
        date_from = date_range.get("from") if date_range else None
        date_to = date_range.get("to") if date_range else None

        # 戦闘データを集計
        battle_data = get_aggregated_data_for_analysis(
            game_type=game_type,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
        )

        # データが空の場合
        if battle_data.get("summary", {}).get("totalBattles", 0) == 0:
            return {
                "statusCode": 200,
                "headers": {**cors_headers, "Content-Type": "application/json"},
                "body": json.dumps({
                    "analysis": "指定された条件に該当する試合データが見つかりませんでした。\n\n日付範囲やゲームタイプを変更してお試しください。",
                    "dataUsed": {
                        "totalBattles": 0,
                        "dateRange": {"from": date_from, "to": date_to},
                        "gameType": game_type,
                    },
                    "tokensUsed": 0,
                    "remainingQueries": usage_info.get("remainingQueries", 0),
                }),
            }

        # Claude AIで分析
        result = analyze_battles(query, battle_data)

        if not result.get("success"):
            return {
                "statusCode": 500,
                "headers": cors_headers,
                "body": json.dumps({
                    "error": result.get("error", "分析中にエラーが発生しました"),
                }),
            }

        # 使用量を記録
        tokens_used = result.get("tokensUsed", 0)
        updated_usage = record_usage(discord_user_id, tokens_used)

        # レスポンス
        response_data = {
            "analysis": result.get("analysis", ""),
            "dataUsed": {
                "totalBattles": battle_data.get("summary", {}).get("totalBattles", 0),
                "dateRange": {
                    "from": battle_data.get("metadata", {}).get("dateRange", {}).get("from"),
                    "to": battle_data.get("metadata", {}).get("dateRange", {}).get("to"),
                },
                "gameType": game_type,
            },
            "tokensUsed": tokens_used,
            "remainingQueries": updated_usage.get("remainingQueries", 0),
            "remainingTokens": updated_usage.get("remainingTokens", 0),
        }

        return {
            "statusCode": 200,
            "headers": {**cors_headers, "Content-Type": "application/json"},
            "body": json.dumps(response_data, cls=DecimalEncoder, ensure_ascii=False),
        }

    except Exception as e:
        print(f"Error in analyze handler: {e}")
        traceback.print_exc()

        origin = event.get("headers", {}).get("origin") or event.get("headers", {}).get("Origin")
        return {
            "statusCode": 500,
            "headers": get_cors_headers(origin),
            "body": json.dumps({"error": f"サーバーエラーが発生しました: {str(e)}"}),
        }
