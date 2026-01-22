"""
データ集計ユーティリティのテスト

Version: 2026-01-23 - Initial implementation
"""

import pytest
from datetime import datetime
from unittest.mock import patch, MagicMock

# テスト対象モジュールをインポート
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from utils.data_aggregator import (
    _parse_datetime,
    _datetime_to_iso,
    _safe_avg,
    _safe_win_rate,
    aggregate_battle_data,
)


class TestParseDateTime:
    """_parse_datetime関数のテスト"""

    def test_valid_datetime(self):
        """正しい形式の日時をパースできる"""
        result = _parse_datetime("15.01.2026 14:30:00")
        assert result is not None
        assert result.year == 2026
        assert result.month == 1
        assert result.day == 15
        assert result.hour == 14
        assert result.minute == 30

    def test_invalid_datetime(self):
        """不正な形式の場合Noneを返す"""
        assert _parse_datetime("invalid") is None
        assert _parse_datetime("2026-01-15") is None
        assert _parse_datetime("") is None
        assert _parse_datetime(None) is None


class TestDatetimeToIso:
    """_datetime_to_iso関数のテスト"""

    def test_conversion(self):
        """datetimeをISO形式に変換できる"""
        dt = datetime(2026, 1, 15)
        assert _datetime_to_iso(dt) == "2026-01-15"


class TestSafeAvg:
    """_safe_avg関数のテスト"""

    def test_normal_list(self):
        """通常のリストの平均を計算できる"""
        assert _safe_avg([1, 2, 3, 4, 5]) == 3.0

    def test_empty_list(self):
        """空リストの場合0を返す"""
        assert _safe_avg([]) == 0.0

    def test_single_element(self):
        """単一要素のリスト"""
        assert _safe_avg([10]) == 10.0

    def test_decimal_values(self):
        """小数値を含むリスト"""
        result = _safe_avg([1.5, 2.5])
        assert result == 2.0


class TestSafeWinRate:
    """_safe_win_rate関数のテスト"""

    def test_normal_calculation(self):
        """通常の勝率計算"""
        assert _safe_win_rate(6, 10) == 0.6

    def test_zero_total(self):
        """総数が0の場合は0を返す"""
        assert _safe_win_rate(0, 0) == 0.0

    def test_all_wins(self):
        """全勝の場合"""
        assert _safe_win_rate(10, 10) == 1.0


class TestAggregateBattleData:
    """aggregate_battle_data関数のテスト"""

    def test_empty_battles(self):
        """空の戦闘リストの場合"""
        result = aggregate_battle_data([])
        assert result["summary"]["totalBattles"] == 0
        assert result["summary"]["winRate"] == 0.0
        assert result["byGameType"] == {}
        assert result["byMap"] == {}

    def test_single_battle(self):
        """単一の戦闘データ"""
        battles = [
            {
                "arenaUniqueID": "123",
                "dateTime": "15.01.2026 14:30:00",
                "gameType": "clan",
                "mapId": "01_solomon_islands",
                "mapDisplayName": "Solomon Islands",
                "winLoss": "win",
                "damage": 100000,
                "kills": 2,
                "spottingDamage": 50000,
                "potentialDamage": 200000,
                "receivedDamage": 30000,
                "baseXP": 2000,
                "ownPlayer": {"shipName": "Montana"},
            }
        ]
        result = aggregate_battle_data(battles)

        assert result["summary"]["totalBattles"] == 1
        assert result["summary"]["wins"] == 1
        assert result["summary"]["winRate"] == 1.0
        assert result["summary"]["avgDamage"] == 100000
        assert result["summary"]["avgKills"] == 2.0

        assert "clan" in result["byGameType"]
        assert result["byGameType"]["clan"]["battles"] == 1

        assert "Solomon Islands" in result["byMap"]
        assert result["byMap"]["Solomon Islands"]["battles"] == 1

    def test_multiple_battles(self):
        """複数の戦闘データ"""
        battles = [
            {
                "arenaUniqueID": "1",
                "dateTime": "15.01.2026 14:30:00",
                "gameType": "clan",
                "mapDisplayName": "Map A",
                "winLoss": "win",
                "damage": 80000,
                "kills": 1,
                "ownPlayer": {"shipName": "Montana"},
            },
            {
                "arenaUniqueID": "2",
                "dateTime": "15.01.2026 15:30:00",
                "gameType": "clan",
                "mapDisplayName": "Map A",
                "winLoss": "loss",
                "damage": 60000,
                "kills": 0,
                "ownPlayer": {"shipName": "Montana"},
            },
            {
                "arenaUniqueID": "3",
                "dateTime": "15.01.2026 16:30:00",
                "gameType": "ranked",
                "mapDisplayName": "Map B",
                "winLoss": "win",
                "damage": 100000,
                "kills": 2,
                "ownPlayer": {"shipName": "Yamato"},
            },
        ]
        result = aggregate_battle_data(battles)

        assert result["summary"]["totalBattles"] == 3
        assert result["summary"]["wins"] == 2
        assert result["summary"]["losses"] == 1
        # 勝率: 2/3 = 0.6667
        assert abs(result["summary"]["winRate"] - 0.6667) < 0.01
        # 平均ダメージ: (80000 + 60000 + 100000) / 3 = 80000
        assert result["summary"]["avgDamage"] == 80000

        # ゲームタイプ別
        assert result["byGameType"]["clan"]["battles"] == 2
        assert result["byGameType"]["ranked"]["battles"] == 1

        # マップ別
        assert result["byMap"]["Map A"]["battles"] == 2
        assert result["byMap"]["Map B"]["battles"] == 1

        # 艦別
        assert result["byShip"]["Montana"]["battles"] == 2
        assert result["byShip"]["Yamato"]["battles"] == 1

    def test_recent_trend(self):
        """最近のトレンド計算"""
        # 20試合分のデータを作成（直近10勝、その前10敗）
        battles = []
        for i in range(20):
            battles.append({
                "arenaUniqueID": str(i),
                "dateTime": f"15.01.2026 {14 + i}:30:00",
                "gameType": "clan",
                "mapDisplayName": "Map A",
                "winLoss": "win" if i < 10 else "loss",
                "damage": 80000,
                "kills": 1,
                "ownPlayer": {"shipName": "Montana"},
            })

        result = aggregate_battle_data(battles)

        # 直近10戦は全勝
        assert result["recentTrend"]["last10"]["battles"] == 10
        assert result["recentTrend"]["last10"]["winRate"] == 1.0

        # その前10戦は全敗
        assert result["recentTrend"]["previous10"]["battles"] == 10
        assert result["recentTrend"]["previous10"]["winRate"] == 0.0

    def test_recent_battles_limit(self):
        """最近の試合詳細は最大20件"""
        battles = [
            {
                "arenaUniqueID": str(i),
                "dateTime": f"15.01.2026 {i % 24}:30:00",
                "gameType": "clan",
                "mapDisplayName": f"Map {i}",
                "winLoss": "win",
                "damage": 80000,
                "kills": 1,
                "ownPlayer": {"shipName": "Montana"},
            }
            for i in range(30)
        ]
        result = aggregate_battle_data(battles)

        assert len(result["recentBattles"]) == 20


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
