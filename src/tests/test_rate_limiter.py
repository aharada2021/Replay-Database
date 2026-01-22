"""
レート制限ユーティリティのテスト

Version: 2026-01-23 - Initial implementation
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import patch, MagicMock
import time

# テスト対象モジュールをインポート
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.rate_limiter import (
    DAILY_QUERY_LIMIT,
    DAILY_TOKEN_LIMIT,
    COOLDOWN_SECONDS,
    _get_today_date,
    _get_ttl_expiry,
    check_rate_limit,
)


class TestGetTodayDate:
    """_get_today_date関数のテスト"""

    def test_returns_correct_format(self):
        """YYYY-MM-DD形式の日付を返す"""
        result = _get_today_date()
        # フォーマットチェック
        assert len(result) == 10
        assert result[4] == "-"
        assert result[7] == "-"

        # 有効な日付かチェック
        parsed = datetime.strptime(result, "%Y-%m-%d")
        assert parsed is not None


class TestGetTtlExpiry:
    """_get_ttl_expiry関数のテスト"""

    def test_returns_future_timestamp(self):
        """7日後のタイムスタンプを返す"""
        current_time = int(time.time())
        result = _get_ttl_expiry()

        # 7日 = 7 * 24 * 60 * 60 = 604800秒
        expected_min = current_time + 604800 - 1
        expected_max = current_time + 604800 + 1

        assert expected_min <= result <= expected_max


class TestCheckRateLimit:
    """check_rate_limit関数のテスト"""

    @patch("utils.rate_limiter.get_usage")
    def test_first_request_allowed(self, mock_get_usage):
        """初回リクエストは許可される"""
        mock_get_usage.return_value = None

        is_allowed, error_msg, usage_info = check_rate_limit("user123")

        assert is_allowed is True
        assert error_msg == ""
        assert usage_info["queryCount"] == 0
        assert usage_info["remainingQueries"] == DAILY_QUERY_LIMIT

    @patch("utils.rate_limiter.get_usage")
    def test_query_limit_exceeded(self, mock_get_usage):
        """クエリ上限に達した場合は拒否"""
        mock_get_usage.return_value = {
            "queryCount": DAILY_QUERY_LIMIT,
            "tokensUsed": 1000,
            "lastQueryAt": int(time.time()) - 60,
        }

        is_allowed, error_msg, usage_info = check_rate_limit("user123")

        assert is_allowed is False
        assert "上限" in error_msg
        assert usage_info["remainingQueries"] == 0

    @patch("utils.rate_limiter.get_usage")
    def test_token_limit_exceeded(self, mock_get_usage):
        """トークン上限に達した場合は拒否"""
        mock_get_usage.return_value = {
            "queryCount": 2,
            "tokensUsed": DAILY_TOKEN_LIMIT,
            "lastQueryAt": int(time.time()) - 60,
        }

        is_allowed, error_msg, usage_info = check_rate_limit("user123")

        assert is_allowed is False
        assert "トークン" in error_msg
        assert usage_info["remainingTokens"] == 0

    @patch("utils.rate_limiter.get_usage")
    def test_cooldown_in_progress(self, mock_get_usage):
        """クールダウン中は拒否"""
        mock_get_usage.return_value = {
            "queryCount": 1,
            "tokensUsed": 1000,
            "lastQueryAt": int(time.time()) - 10,  # 10秒前
        }

        is_allowed, error_msg, usage_info = check_rate_limit("user123")

        assert is_allowed is False
        assert "間隔" in error_msg or "秒" in error_msg
        assert "cooldownRemaining" in usage_info

    @patch("utils.rate_limiter.get_usage")
    def test_cooldown_completed(self, mock_get_usage):
        """クールダウン終了後は許可"""
        mock_get_usage.return_value = {
            "queryCount": 1,
            "tokensUsed": 1000,
            "lastQueryAt": int(time.time()) - COOLDOWN_SECONDS - 1,  # クールダウン終了
        }

        is_allowed, error_msg, usage_info = check_rate_limit("user123")

        assert is_allowed is True
        assert error_msg == ""
        assert usage_info["queryCount"] == 1
        assert usage_info["remainingQueries"] == DAILY_QUERY_LIMIT - 1

    @patch("utils.rate_limiter.get_usage")
    def test_partial_usage(self, mock_get_usage):
        """部分的な使用量の場合の残り計算"""
        mock_get_usage.return_value = {
            "queryCount": 3,
            "tokensUsed": 20000,
            "lastQueryAt": int(time.time()) - 60,
        }

        is_allowed, error_msg, usage_info = check_rate_limit("user123")

        assert is_allowed is True
        assert usage_info["queryCount"] == 3
        assert usage_info["remainingQueries"] == DAILY_QUERY_LIMIT - 3
        assert usage_info["tokensUsed"] == 20000
        assert usage_info["remainingTokens"] == DAILY_TOKEN_LIMIT - 20000


class TestRateLimitConstants:
    """レート制限定数のテスト"""

    def test_daily_query_limit(self):
        """日次クエリ上限が妥当な値"""
        assert DAILY_QUERY_LIMIT > 0
        assert DAILY_QUERY_LIMIT <= 100  # 上限は100以下

    def test_daily_token_limit(self):
        """日次トークン上限が妥当な値"""
        assert DAILY_TOKEN_LIMIT > 0
        assert DAILY_TOKEN_LIMIT >= 10000  # 最低1万トークン

    def test_cooldown_seconds(self):
        """クールダウン秒数が妥当な値"""
        assert COOLDOWN_SECONDS > 0
        assert COOLDOWN_SECONDS <= 300  # 最大5分


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
