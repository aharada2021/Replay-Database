"""
Discord通知ユーティリティ

Auto-uploader経由でアップロードされたリプレイの処理完了時に
Discordへ通知を送信する
"""

import requests
import yaml
from pathlib import Path


DISCORD_API_BASE = "https://discord.com/api/v10"

# マップ名設定ファイルを読み込み
_map_config = None


def _load_map_config():
    """マップ名設定を読み込む"""
    global _map_config
    if _map_config is None:
        config_path = Path(__file__).parent.parent.parent / "config" / "map_names.yaml"
        if config_path.exists():
            with open(config_path, "r", encoding="utf-8") as f:
                _map_config = yaml.safe_load(f)
        else:
            _map_config = {"maps": {}, "default_map_name": "不明"}
    return _map_config


def get_map_name_ja(map_id: str) -> str:
    """マップIDから日本語名を取得"""
    config = _load_map_config()
    return config.get("maps", {}).get(map_id, config.get("default_map_name", map_id))


def get_game_type_ja(game_type: str) -> str:
    """ゲームタイプの日本語名を取得"""
    game_type_names = {
        "clan": "クラン戦",
        "pvp": "ランダム戦",
        "ranked": "ランク戦",
    }
    return game_type_names.get(game_type, game_type)


def get_win_loss_ja(win_loss: str) -> str:
    """勝敗の日本語表記を取得"""
    if win_loss == "win":
        return "勝利"
    elif win_loss == "lose":
        return "敗北"
    elif win_loss == "draw":
        return "引き分け"
    return win_loss or "不明"


def get_win_loss_color(win_loss: str) -> int:
    """勝敗に応じたEmbed色を取得"""
    if win_loss == "win":
        return 0x00FF00  # 緑
    elif win_loss == "lose":
        return 0xFF0000  # 赤
    return 0x808080  # グレー


def send_replay_notification(
    channel_id: str,
    bot_token: str,
    record: dict,
    mp4_url: str = None,
    web_ui_base_url: str = "https://wows-replay.mirage0926.com",
) -> bool:
    """
    リプレイ処理完了通知を送信

    Args:
        channel_id: 通知先DiscordチャンネルID
        bot_token: Discord Bot Token
        record: DynamoDBレコード
        mp4_url: 動画のPresigned URL（オプション）
        web_ui_base_url: Web UIのベースURL

    Returns:
        送信成功/失敗
    """
    if not channel_id or not bot_token:
        print("Discord notification skipped: missing channel_id or bot_token")
        return False

    try:
        # レコードから情報を抽出
        arena_unique_id = record.get("arenaUniqueID", "")
        player_id = record.get("playerID", 0)
        player_name = record.get("playerName", "Unknown")
        map_id = record.get("mapId", "")
        game_type = record.get("gameType", "")
        win_loss = record.get("winLoss", "")
        date_time = record.get("dateTime", "")

        # 自分の艦艇情報
        own_player = record.get("ownPlayer", {})
        if isinstance(own_player, list):
            own_player = own_player[0] if own_player else {}
        ship_name = own_player.get("shipName", "不明")

        # 統計情報
        damage = record.get("damage", 0)
        kills = record.get("kills", 0)

        # クラン情報
        ally_clan = record.get("allyClanTag", "")
        enemy_clan = record.get("enemyClanTag", "")

        # 日本語変換
        map_name_ja = get_map_name_ja(map_id)
        game_type_ja = get_game_type_ja(game_type)
        win_loss_ja = get_win_loss_ja(win_loss)
        embed_color = get_win_loss_color(win_loss)

        # Web UI詳細ページURL
        detail_url = f"{web_ui_base_url}/match/{arena_unique_id}"

        # Embedを作成
        embed = {
            "title": f"{win_loss_ja} - {map_name_ja}",
            "color": embed_color,
            "fields": [
                {"name": "ゲームタイプ", "value": game_type_ja, "inline": True},
                {"name": "マップ", "value": map_name_ja, "inline": True},
                {"name": "プレイヤー", "value": player_name, "inline": True},
                {"name": "艦艇", "value": ship_name, "inline": True},
                {"name": "ダメージ", "value": f"{damage:,}", "inline": True},
                {"name": "撃沈", "value": str(kills), "inline": True},
            ],
            "footer": {"text": f"日時: {date_time}"},
        }

        # クラン情報があれば追加
        if ally_clan or enemy_clan:
            clan_text = f"味方: [{ally_clan}]" if ally_clan else ""
            if enemy_clan:
                clan_text += (
                    f" vs 敵: [{enemy_clan}]" if clan_text else f"敵: [{enemy_clan}]"
                )
            embed["fields"].insert(
                2, {"name": "クラン", "value": clan_text, "inline": False}
            )

        # 詳細リンクを追加
        embed["fields"].append(
            {"name": "詳細", "value": f"[Web UIで見る]({detail_url})", "inline": False}
        )

        # メッセージを送信
        url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages"
        headers = {
            "Authorization": f"Bot {bot_token}",
            "Content-Type": "application/json",
        }
        payload = {"embeds": [embed]}

        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()

        print(f"Discord notification sent successfully to channel {channel_id}")
        return True

    except Exception as e:
        print(f"Failed to send Discord notification: {e}")
        import traceback

        traceback.print_exc()
        return False
