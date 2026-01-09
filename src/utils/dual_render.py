"""
Dual Render ユーティリティ

同一試合で敵味方両チームのリプレイが存在するかを判定し、
RenderDualを使用した両陣営視点動画の生成をサポートするユーティリティ
"""

from typing import Dict, Any, List, Optional, Tuple


def are_opposing_teams(replay_a: Dict[str, Any], replay_b: Dict[str, Any]) -> bool:
    """
    2つのリプレイが敵味方関係かを判定

    Args:
        replay_a: リプレイAのデータ（ownPlayer, enemies等を含む）
        replay_b: リプレイBのデータ（ownPlayer, enemies等を含む）

    Returns:
        True if the two replays are from opposing teams
    """
    # プレイヤーAの名前を取得
    player_a_name = replay_a.get("ownPlayer", {}).get("name")
    if not player_a_name:
        return False

    # プレイヤーBの敵リストを取得
    enemies_b = replay_b.get("enemies", [])
    enemy_names_b = [e.get("name") for e in enemies_b if e.get("name")]

    # プレイヤーAがBの敵リストに含まれていれば敵味方関係
    return player_a_name in enemy_names_b


def find_opposing_replay_pair(replays: List[Dict[str, Any]]) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
    """
    リプレイリストから敵味方ペアを検出

    Args:
        replays: 同一試合のリプレイリスト

    Returns:
        敵味方ペア（green_replay, red_replay）のタプル、なければNone
        green_replayは最初に見つかった方、red_replayはその敵チーム
    """
    if len(replays) < 2:
        return None

    for i, replay_a in enumerate(replays):
        for replay_b in replays[i + 1:]:
            if are_opposing_teams(replay_a, replay_b):
                # replay_aをgreen（味方視点）、replay_bをred（敵視点）として返す
                return (replay_a, replay_b)

    return None


def get_team_clan_tag(replay_data: Dict[str, Any], team: str = "ally") -> Optional[str]:
    """
    リプレイデータからチームのクランタグを取得

    Args:
        replay_data: リプレイデータ
        team: "ally" または "enemy"

    Returns:
        クランタグ（見つからない場合はNone）
    """
    if team == "ally":
        # まずownPlayerのクランタグを確認
        own_clan = replay_data.get("ownPlayer", {}).get("clanTag")
        if own_clan:
            return own_clan
        # alliesからクランタグを探す
        allies = replay_data.get("allies", [])
        for ally in allies:
            clan_tag = ally.get("clanTag")
            if clan_tag:
                return clan_tag
    else:
        # enemiesからクランタグを探す
        enemies = replay_data.get("enemies", [])
        for enemy in enemies:
            clan_tag = enemy.get("clanTag")
            if clan_tag:
                return clan_tag

    return None


def get_dual_render_tags(
    green_replay: Dict[str, Any],
    red_replay: Dict[str, Any]
) -> Tuple[Optional[str], Optional[str]]:
    """
    Dual Render用のgreen_tag/red_tagを取得

    Args:
        green_replay: green（味方）視点のリプレイデータ
        red_replay: red（敵）視点のリプレイデータ

    Returns:
        (green_tag, red_tag) のタプル
    """
    # green側のクランタグ（green_replayの味方クラン）
    green_tag = get_team_clan_tag(green_replay, "ally")

    # red側のクランタグ（red_replayの味方クラン = green視点での敵クラン）
    red_tag = get_team_clan_tag(red_replay, "ally")

    return (green_tag, red_tag)


def generate_dual_s3_key(arena_unique_id: str) -> str:
    """
    Dual動画用のS3キーを生成

    Args:
        arena_unique_id: 試合のarenaUniqueID

    Returns:
        S3キー（例: videos/dual/1234567890.mp4）
    """
    return f"videos/dual/{arena_unique_id}.mp4"
