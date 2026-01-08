"""
試合識別キー生成ユーティリティ

同一試合を識別するためのキーを生成する
arenaUniqueIDは各プレイヤーごとに異なるため、プレイヤーセットで識別する
"""

from datetime import datetime
from functools import lru_cache


def format_sortable_datetime(date_str: str) -> str:
    """
    日時文字列をソート可能な形式に変換

    DynamoDB保存用：DD.MM.YYYY HH:MM:SS → YYYYMMDDHHMMSS
    この形式なら文字列ソートで正しい時系列順になる

    Args:
        date_str: "DD.MM.YYYY HH:MM:SS" 形式の日時文字列

    Returns:
        "YYYYMMDDHHMMSS" 形式の文字列（パース失敗時は"00000000000000"）
    """
    if not date_str:
        return "00000000000000"

    try:
        dt = datetime.strptime(date_str, "%d.%m.%Y %H:%M:%S")
        return dt.strftime("%Y%m%d%H%M%S")
    except ValueError:
        return "00000000000000"


@lru_cache(maxsize=1024)
def round_datetime_to_5min(date_time_str):
    """
    日時を5分単位に丸める

    Args:
        date_time_str: "04.01.2026 21:56:55" 形式の日時文字列

    Returns:
        5分単位に丸めた日時文字列 (例: "04.01.2026 21:55:00")
    """
    try:
        # フォーマット例: "04.01.2026 21:56:55"
        dt = datetime.strptime(date_time_str, "%d.%m.%Y %H:%M:%S")

        # 分を5分単位に切り捨て
        rounded_minute = (dt.minute // 5) * 5

        # 丸めた日時を返す
        rounded_dt = dt.replace(minute=rounded_minute, second=0)
        return rounded_dt.strftime("%d.%m.%Y %H:%M:00")
    except Exception as e:
        print(f"Error rounding datetime: {e}, returning original: {date_time_str}")
        return date_time_str


def generate_match_key(item):
    """
    同一試合を識別するためのキーを生成

    Args:
        item: DynamoDBアイテム

    Returns:
        マッチキー文字列
    """
    # 全プレイヤー名を収集
    players = set()

    # ownPlayerを追加
    own_player = item.get("ownPlayer", {})
    if isinstance(own_player, dict) and own_player.get("name"):
        players.add(own_player["name"])

    # alliesを追加
    for ally in item.get("allies", []):
        if ally.get("name"):
            players.add(ally["name"])

    # enemiesを追加
    for enemy in item.get("enemies", []):
        if enemy.get("name"):
            players.add(enemy["name"])

    # プレイヤーリストをソート（安定したキーのため）
    player_list = sorted(players)

    # 日時を5分単位に丸める
    date_time = item.get("dateTime", "")
    rounded_date_time = round_datetime_to_5min(date_time)

    # マップとゲームタイプ
    map_id = item.get("mapId", "")
    game_type = item.get("gameType", "")

    # マッチキーを生成
    # フォーマット: "日時(5分丸め)|マップ|ゲームタイプ|プレイヤー1|プレイヤー2|..."
    match_key = f"{rounded_date_time}|{map_id}|{game_type}|{'|'.join(player_list)}"

    return match_key
