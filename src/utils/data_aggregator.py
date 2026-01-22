"""
データ集計ユーティリティ

Claude API分析用にDynamoDBから戦闘データを集計。

Version: 2026-01-23 - Initial implementation
"""

import os
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, Optional, List
from collections import defaultdict
import boto3

from utils.dynamodb_tables import (
    BattleTableClient,
    decimal_to_python,
    normalize_game_type,
)

# 定数
DEFAULT_PERIOD_DAYS = 30
MAX_RECENT_BATTLES = 20
MAX_BATTLES_TOTAL = 100


def _parse_datetime(dt_str: str) -> Optional[datetime]:
    """
    DD.MM.YYYY HH:MM:SS 形式の日時をdatetimeに変換

    Args:
        dt_str: 日時文字列

    Returns:
        datetime オブジェクト、またはパース失敗時は None
    """
    try:
        return datetime.strptime(dt_str, "%d.%m.%Y %H:%M:%S")
    except (ValueError, TypeError):
        return None


def _datetime_to_iso(dt: datetime) -> str:
    """datetimeをISO形式文字列に変換"""
    return dt.strftime("%Y-%m-%d")


def _safe_avg(values: List[float]) -> float:
    """安全な平均計算（空リストは0を返す）"""
    return sum(values) / len(values) if values else 0.0


def _safe_win_rate(wins: int, total: int) -> float:
    """勝率計算（0除算防止）"""
    return wins / total if total > 0 else 0.0


def _extract_ship_class(ship_name: str, players_info: List[Dict]) -> Optional[str]:
    """
    プレイヤー情報から艦種を抽出（将来的にはSTATSレコードから取得）
    """
    # 現状はshipClassが直接取れないケースが多いため、None返す
    # STATSレコードがある場合はそこから取得
    return None


def fetch_battles_for_analysis(
    game_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = MAX_BATTLES_TOTAL,
) -> List[Dict[str, Any]]:
    """
    分析用に戦闘データを取得

    Args:
        game_type: ゲームタイプ（clan, ranked, random, other）
        date_from: 開始日（YYYY-MM-DD）
        date_to: 終了日（YYYY-MM-DD）
        limit: 取得件数上限

    Returns:
        戦闘レコードのリスト
    """
    # 日付範囲のデフォルト設定
    now = datetime.now(timezone.utc)
    if not date_to:
        date_to = _datetime_to_iso(now)
    if not date_from:
        date_from = _datetime_to_iso(now - timedelta(days=DEFAULT_PERIOD_DAYS))

    # date_from/date_to を datetime に変換
    try:
        dt_from = datetime.strptime(date_from, "%Y-%m-%d")
        dt_to = datetime.strptime(date_to, "%Y-%m-%d") + timedelta(days=1)  # 終了日を含める
    except ValueError:
        dt_from = now - timedelta(days=DEFAULT_PERIOD_DAYS)
        dt_to = now

    all_battles = []

    # クエリ対象のgameType決定
    if game_type:
        game_types = [normalize_game_type(game_type)]
    else:
        game_types = ["clan", "ranked", "random", "other"]

    for gt in game_types:
        try:
            client = BattleTableClient(gt)
            # ListingIndexを使って最新順に取得
            result = client.list_matches(limit=limit)
            items = result.get("items", [])

            for item in items:
                # 日付フィルタリング（DynamoDB側で絞れない場合はPython側で）
                dt_str = item.get("dateTime")
                if dt_str:
                    item_dt = _parse_datetime(dt_str)
                    if item_dt and not (dt_from <= item_dt <= dt_to):
                        continue

                # 必要なフィールドを抽出
                battle = {
                    "arenaUniqueID": item.get("arenaUniqueID"),
                    "dateTime": dt_str,
                    "gameType": gt,
                    "mapId": item.get("mapId"),
                    "mapDisplayName": item.get("mapDisplayName"),
                    "winLoss": item.get("winLoss", "unknown"),
                    # 自分の統計
                    "damage": item.get("damage"),
                    "kills": item.get("kills"),
                    "spottingDamage": item.get("spottingDamage"),
                    "potentialDamage": item.get("potentialDamage"),
                    "receivedDamage": item.get("receivedDamage"),
                    "baseXP": item.get("baseXP"),
                    "citadels": item.get("citadels"),
                    "fires": item.get("fires"),
                    "floods": item.get("floods"),
                    # プレイヤー情報
                    "ownPlayer": item.get("ownPlayer"),
                    "allyMainClanTag": item.get("allyMainClanTag"),
                    "enemyMainClanTag": item.get("enemyMainClanTag"),
                }
                all_battles.append(battle)

                if len(all_battles) >= limit:
                    break

        except Exception as e:
            print(f"Error fetching battles for gameType={gt}: {e}")
            continue

        if len(all_battles) >= limit:
            break

    # 日付でソート（新しい順）
    all_battles.sort(
        key=lambda x: _parse_datetime(x.get("dateTime", "")) or datetime.min,
        reverse=True,
    )

    return all_battles[:limit]


def aggregate_battle_data(
    battles: List[Dict[str, Any]],
    period_days: int = DEFAULT_PERIOD_DAYS,
) -> Dict[str, Any]:
    """
    戦闘データを集計してClaudeに渡す構造に変換

    Args:
        battles: 戦闘レコードのリスト
        period_days: 集計期間（日数）

    Returns:
        集計データ構造
    """
    if not battles:
        return {
            "summary": {
                "totalBattles": 0,
                "winRate": 0.0,
                "avgDamage": 0.0,
                "avgKills": 0.0,
                "periodDays": period_days,
            },
            "byShipClass": {},
            "byMap": {},
            "byGameType": {},
            "recentTrend": {
                "last10": {"winRate": 0.0, "avgDamage": 0.0},
                "previous10": {"winRate": 0.0, "avgDamage": 0.0},
            },
            "recentBattles": [],
        }

    # 全体統計
    total_battles = len(battles)
    wins = sum(1 for b in battles if b.get("winLoss") == "win")
    losses = sum(1 for b in battles if b.get("winLoss") == "loss")
    draws = sum(1 for b in battles if b.get("winLoss") == "draw")

    damages = [b.get("damage", 0) or 0 for b in battles]
    kills = [b.get("kills", 0) or 0 for b in battles]
    spotting = [b.get("spottingDamage", 0) or 0 for b in battles]
    potential = [b.get("potentialDamage", 0) or 0 for b in battles]
    received = [b.get("receivedDamage", 0) or 0 for b in battles]
    base_xp = [b.get("baseXP", 0) or 0 for b in battles]

    summary = {
        "totalBattles": total_battles,
        "wins": wins,
        "losses": losses,
        "draws": draws,
        "winRate": round(_safe_win_rate(wins, wins + losses), 4),
        "avgDamage": round(_safe_avg(damages)),
        "avgKills": round(_safe_avg(kills), 2),
        "avgSpottingDamage": round(_safe_avg(spotting)),
        "avgPotentialDamage": round(_safe_avg(potential)),
        "avgReceivedDamage": round(_safe_avg(received)),
        "avgBaseXP": round(_safe_avg(base_xp)),
        "periodDays": period_days,
    }

    # ゲームタイプ別統計
    by_game_type = defaultdict(lambda: {"battles": 0, "wins": 0, "damages": []})
    for b in battles:
        gt = b.get("gameType", "unknown")
        by_game_type[gt]["battles"] += 1
        if b.get("winLoss") == "win":
            by_game_type[gt]["wins"] += 1
        by_game_type[gt]["damages"].append(b.get("damage", 0) or 0)

    by_game_type_result = {}
    for gt, data in by_game_type.items():
        by_game_type_result[gt] = {
            "battles": data["battles"],
            "winRate": round(_safe_win_rate(data["wins"], data["battles"]), 4),
            "avgDamage": round(_safe_avg(data["damages"])),
        }

    # マップ別統計
    by_map = defaultdict(lambda: {"battles": 0, "wins": 0, "damages": []})
    for b in battles:
        map_name = b.get("mapDisplayName") or b.get("mapId", "Unknown")
        by_map[map_name]["battles"] += 1
        if b.get("winLoss") == "win":
            by_map[map_name]["wins"] += 1
        by_map[map_name]["damages"].append(b.get("damage", 0) or 0)

    by_map_result = {}
    for map_name, data in by_map.items():
        by_map_result[map_name] = {
            "battles": data["battles"],
            "winRate": round(_safe_win_rate(data["wins"], data["battles"]), 4),
            "avgDamage": round(_safe_avg(data["damages"])),
        }

    # 艦種別統計（艦名から推定）
    by_ship = defaultdict(lambda: {"battles": 0, "wins": 0, "damages": []})
    for b in battles:
        own = b.get("ownPlayer") or {}
        ship_name = own.get("shipName", "Unknown")
        if ship_name:
            by_ship[ship_name]["battles"] += 1
            if b.get("winLoss") == "win":
                by_ship[ship_name]["wins"] += 1
            by_ship[ship_name]["damages"].append(b.get("damage", 0) or 0)

    by_ship_result = {}
    for ship_name, data in by_ship.items():
        by_ship_result[ship_name] = {
            "battles": data["battles"],
            "winRate": round(_safe_win_rate(data["wins"], data["battles"]), 4),
            "avgDamage": round(_safe_avg(data["damages"])),
        }

    # 最近のトレンド（直近10戦 vs その前10戦）
    last_10 = battles[:10]
    previous_10 = battles[10:20]

    def calc_trend(battle_list):
        if not battle_list:
            return {"winRate": 0.0, "avgDamage": 0.0, "battles": 0}
        wins = sum(1 for b in battle_list if b.get("winLoss") == "win")
        total = len(battle_list)
        dmgs = [b.get("damage", 0) or 0 for b in battle_list]
        return {
            "winRate": round(_safe_win_rate(wins, total), 4),
            "avgDamage": round(_safe_avg(dmgs)),
            "battles": total,
        }

    recent_trend = {
        "last10": calc_trend(last_10),
        "previous10": calc_trend(previous_10),
    }

    # 最近の戦闘詳細（最大20件）
    recent_battles = []
    for b in battles[:MAX_RECENT_BATTLES]:
        own = b.get("ownPlayer") or {}
        recent_battles.append({
            "dateTime": b.get("dateTime"),
            "gameType": b.get("gameType"),
            "mapDisplayName": b.get("mapDisplayName") or b.get("mapId"),
            "shipName": own.get("shipName"),
            "winLoss": b.get("winLoss"),
            "damage": b.get("damage"),
            "kills": b.get("kills"),
            "spottingDamage": b.get("spottingDamage"),
            "baseXP": b.get("baseXP"),
        })

    return {
        "summary": summary,
        "byGameType": by_game_type_result,
        "byMap": by_map_result,
        "byShip": by_ship_result,
        "recentTrend": recent_trend,
        "recentBattles": recent_battles,
    }


def get_aggregated_data_for_analysis(
    game_type: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = MAX_BATTLES_TOTAL,
) -> Dict[str, Any]:
    """
    分析用の集計データを取得（メイン関数）

    Args:
        game_type: ゲームタイプフィルタ
        date_from: 開始日（YYYY-MM-DD）
        date_to: 終了日（YYYY-MM-DD）
        limit: 取得件数上限

    Returns:
        集計データ
    """
    # 戦闘データを取得
    battles = fetch_battles_for_analysis(
        game_type=game_type,
        date_from=date_from,
        date_to=date_to,
        limit=limit,
    )

    # 期間日数を計算
    if date_from and date_to:
        try:
            dt_from = datetime.strptime(date_from, "%Y-%m-%d")
            dt_to = datetime.strptime(date_to, "%Y-%m-%d")
            period_days = (dt_to - dt_from).days + 1
        except ValueError:
            period_days = DEFAULT_PERIOD_DAYS
    else:
        period_days = DEFAULT_PERIOD_DAYS

    # データを集計
    aggregated = aggregate_battle_data(battles, period_days=period_days)

    # メタデータを追加
    aggregated["metadata"] = {
        "gameTypeFilter": game_type,
        "dateRange": {
            "from": date_from,
            "to": date_to,
        },
        "totalBattlesFetched": len(battles),
        "generatedAt": datetime.now(timezone.utc).isoformat(),
    }

    return aggregated
