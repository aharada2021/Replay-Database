"""
分析APIレート制限ユーティリティ

Claude API呼び出しのコスト管理のため、ユーザーごとの日次制限を実装。

Version: 2026-01-23 - Initial implementation
"""

import os
import time
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Tuple
import boto3
from botocore.exceptions import ClientError

# レート制限設定
DAILY_QUERY_LIMIT = 5  # 1日5クエリ
DAILY_TOKEN_LIMIT = 50000  # 1日50,000トークン
COOLDOWN_SECONDS = 30  # 30秒クールダウン

# DynamoDBクライアント（遅延初期化）
_dynamodb = None
ANALYSIS_USAGE_TABLE_NAME = os.environ.get(
    "ANALYSIS_USAGE_TABLE", "wows-analysis-usage-dev"
)


def get_dynamodb_resource():
    """DynamoDBリソースを取得（遅延初期化）"""
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource(
            "dynamodb",
            region_name=os.environ.get("AWS_REGION", "ap-northeast-1"),
        )
    return _dynamodb


def get_usage_table():
    """使用量テーブルを取得"""
    return get_dynamodb_resource().Table(ANALYSIS_USAGE_TABLE_NAME)


def _get_today_date() -> str:
    """今日の日付をYYYY-MM-DD形式で取得（UTC）"""
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _get_ttl_expiry() -> int:
    """TTL有効期限を計算（7日後のUNIXタイムスタンプ）"""
    return int(time.time()) + (7 * 24 * 60 * 60)


def get_usage(discord_user_id: str) -> Optional[Dict[str, Any]]:
    """
    ユーザーの今日の使用量を取得

    Args:
        discord_user_id: DiscordユーザーID

    Returns:
        使用量レコード、または None（今日の使用がない場合）
    """
    table = get_usage_table()
    today = _get_today_date()

    try:
        response = table.get_item(
            Key={
                "discordUserId": discord_user_id,
                "date": today,
            }
        )
        return response.get("Item")
    except ClientError as e:
        print(f"Error getting usage for {discord_user_id}: {e}")
        return None


def check_rate_limit(discord_user_id: str) -> Tuple[bool, str, Dict[str, Any]]:
    """
    レート制限をチェック

    Args:
        discord_user_id: DiscordユーザーID

    Returns:
        Tuple of (is_allowed, error_message, usage_info)
        - is_allowed: True if request is allowed
        - error_message: Error message if not allowed, empty string otherwise
        - usage_info: Current usage information
    """
    usage = get_usage(discord_user_id)

    if usage is None:
        # 今日初めての使用
        return True, "", {
            "queryCount": 0,
            "tokensUsed": 0,
            "remainingQueries": DAILY_QUERY_LIMIT,
            "remainingTokens": DAILY_TOKEN_LIMIT,
        }

    query_count = int(usage.get("queryCount", 0))
    tokens_used = int(usage.get("tokensUsed", 0))
    last_query_at = usage.get("lastQueryAt")

    # クエリ数制限チェック
    if query_count >= DAILY_QUERY_LIMIT:
        return False, f"本日のクエリ上限（{DAILY_QUERY_LIMIT}回）に達しました。明日またお試しください。", {
            "queryCount": query_count,
            "tokensUsed": tokens_used,
            "remainingQueries": 0,
            "remainingTokens": max(0, DAILY_TOKEN_LIMIT - tokens_used),
        }

    # トークン制限チェック
    if tokens_used >= DAILY_TOKEN_LIMIT:
        return False, f"本日のトークン上限（{DAILY_TOKEN_LIMIT:,}トークン）に達しました。明日またお試しください。", {
            "queryCount": query_count,
            "tokensUsed": tokens_used,
            "remainingQueries": max(0, DAILY_QUERY_LIMIT - query_count),
            "remainingTokens": 0,
        }

    # クールダウンチェック
    if last_query_at:
        last_query_time = int(last_query_at)
        current_time = int(time.time())
        elapsed = current_time - last_query_time

        if elapsed < COOLDOWN_SECONDS:
            wait_time = COOLDOWN_SECONDS - elapsed
            return False, f"連続クエリは{COOLDOWN_SECONDS}秒の間隔が必要です。あと{wait_time}秒お待ちください。", {
                "queryCount": query_count,
                "tokensUsed": tokens_used,
                "remainingQueries": DAILY_QUERY_LIMIT - query_count,
                "remainingTokens": DAILY_TOKEN_LIMIT - tokens_used,
                "cooldownRemaining": wait_time,
            }

    return True, "", {
        "queryCount": query_count,
        "tokensUsed": tokens_used,
        "remainingQueries": DAILY_QUERY_LIMIT - query_count,
        "remainingTokens": DAILY_TOKEN_LIMIT - tokens_used,
    }


def record_usage(
    discord_user_id: str,
    tokens_used: int,
) -> Dict[str, Any]:
    """
    使用量を記録

    Args:
        discord_user_id: DiscordユーザーID
        tokens_used: 使用したトークン数

    Returns:
        更新後の使用量情報
    """
    table = get_usage_table()
    today = _get_today_date()
    current_time = int(time.time())
    ttl_expiry = _get_ttl_expiry()

    try:
        response = table.update_item(
            Key={
                "discordUserId": discord_user_id,
                "date": today,
            },
            UpdateExpression="""
                SET queryCount = if_not_exists(queryCount, :zero) + :inc,
                    tokensUsed = if_not_exists(tokensUsed, :zero) + :tokens,
                    lastQueryAt = :now,
                    expiresAt = :ttl
            """,
            ExpressionAttributeValues={
                ":zero": 0,
                ":inc": 1,
                ":tokens": tokens_used,
                ":now": current_time,
                ":ttl": ttl_expiry,
            },
            ReturnValues="ALL_NEW",
        )

        updated = response.get("Attributes", {})
        query_count = int(updated.get("queryCount", 0))
        total_tokens = int(updated.get("tokensUsed", 0))

        return {
            "queryCount": query_count,
            "tokensUsed": total_tokens,
            "remainingQueries": max(0, DAILY_QUERY_LIMIT - query_count),
            "remainingTokens": max(0, DAILY_TOKEN_LIMIT - total_tokens),
        }

    except ClientError as e:
        print(f"Error recording usage for {discord_user_id}: {e}")
        raise


def get_usage_summary(discord_user_id: str) -> Dict[str, Any]:
    """
    ユーザーの使用量サマリーを取得

    Args:
        discord_user_id: DiscordユーザーID

    Returns:
        使用量サマリー
    """
    usage = get_usage(discord_user_id)

    if usage is None:
        return {
            "date": _get_today_date(),
            "queryCount": 0,
            "tokensUsed": 0,
            "remainingQueries": DAILY_QUERY_LIMIT,
            "remainingTokens": DAILY_TOKEN_LIMIT,
            "dailyQueryLimit": DAILY_QUERY_LIMIT,
            "dailyTokenLimit": DAILY_TOKEN_LIMIT,
            "cooldownSeconds": COOLDOWN_SECONDS,
        }

    query_count = int(usage.get("queryCount", 0))
    tokens_used = int(usage.get("tokensUsed", 0))

    return {
        "date": _get_today_date(),
        "queryCount": query_count,
        "tokensUsed": tokens_used,
        "remainingQueries": max(0, DAILY_QUERY_LIMIT - query_count),
        "remainingTokens": max(0, DAILY_TOKEN_LIMIT - tokens_used),
        "dailyQueryLimit": DAILY_QUERY_LIMIT,
        "dailyTokenLimit": DAILY_TOKEN_LIMIT,
        "cooldownSeconds": COOLDOWN_SECONDS,
    }
