"""
Discord通知ユーティリティ

Auto-uploader経由でアップロードされたリプレイの処理完了時に
Discordへ通知を送信する
"""

import os
import requests
import yaml
from pathlib import Path

DISCORD_API_BASE = "https://discord.com/api/v10"
FRONTEND_URL = os.environ.get("FRONTEND_URL")  # serverless.ymlから設定される

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
    """勝敗の日本語表記を取得（絵文字付き）"""
    if win_loss == "win":
        return "🎉 勝利 🎉"
    elif win_loss == "lose":
        return "💀 敗北 💀"
    elif win_loss == "draw":
        return "🤝 引き分け"
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
    web_ui_base_url: str = None,
    is_dual: bool = False,
) -> bool:
    """
    リプレイ処理完了通知を送信

    Args:
        channel_id: 通知先DiscordチャンネルID
        bot_token: Discord Bot Token
        record: DynamoDBレコード
        mp4_url: 動画のPresigned URL（オプション）
        web_ui_base_url: Web UIのベースURL
        is_dual: Dual Render動画かどうか

    Returns:
        送信成功/失敗
    """
    if not channel_id or not bot_token:
        print("Discord notification skipped: missing channel_id or bot_token")
        return False

    # 環境変数からFRONTEND_URLを使用（引数で上書き可能）
    if web_ui_base_url is None:
        web_ui_base_url = FRONTEND_URL

    try:
        # レコードから情報を抽出
        arena_unique_id = record.get("arenaUniqueID", "")
        map_id = record.get("mapId", "")
        game_type = record.get("gameType", "")
        win_loss = record.get("winLoss", "")
        date_time = record.get("dateTime", "")

        # クラン情報
        ally_clan = record.get("allyClanTag", "")
        enemy_clan = record.get("enemyClanTag", "")

        # メンバーリスト
        allies = record.get("allies", [])
        enemies = record.get("enemies", [])

        # 自分のプレイヤー情報を味方リストに追加
        own_player = record.get("ownPlayer", {})
        if isinstance(own_player, list):
            own_player = own_player[0] if own_player else {}

        # 日本語変換
        map_name_ja = get_map_name_ja(map_id)
        game_type_ja = get_game_type_ja(game_type)
        win_loss_ja = get_win_loss_ja(win_loss)
        embed_color = get_win_loss_color(win_loss)

        # メンバーリストをフォーマット（名前 - 艦艇名）
        def format_member_list(members):
            lines = []
            for member in members:
                name = member.get("name", "Unknown")
                ship = member.get("shipName", "不明")
                lines.append(f"**{name}** - {ship}")
            return "\n".join(lines) if lines else "なし"

        own_player_name = own_player.get("name", "")

        # 自分を味方リストに含める（alliesに自分が含まれていない場合）
        ally_names = [m.get("name") for m in allies]
        if own_player_name and own_player_name not in ally_names:
            allies = [own_player] + allies

        ally_list = format_member_list(allies)
        enemy_list = format_member_list(enemies)

        # クラン対戦テキスト
        clan_text = ""
        if ally_clan or enemy_clan:
            clan_text = f"[{ally_clan}]" if ally_clan else "???"
            clan_text += f" vs [{enemy_clan}]" if enemy_clan else " vs ???"

        # 1つのEmbedにまとめる
        title = f"{win_loss_ja} - {map_name_ja}"
        if is_dual:
            title = f"👁 両陣営視点 - {title}"

        embed = {
            "title": title,
            "color": embed_color,
            "fields": [
                {
                    "name": "ゲームタイプ",
                    "value": game_type_ja,
                    "inline": True,
                },
                {"name": "マップ", "value": map_name_ja, "inline": True},
            ],
            "footer": {"text": f"日時: {date_time}"},
        }

        # クラン情報
        if clan_text:
            embed["fields"].append({"name": "クラン", "value": clan_text, "inline": False})

        # 味方・敵メンバーを横並びで表示
        embed["fields"].append({"name": "🔵 味方", "value": ally_list, "inline": True})
        embed["fields"].append({"name": "🔴 敵", "value": enemy_list, "inline": True})

        # 詳細リンク（FRONTEND_URL未設定時は壊れたリンクを出さない）
        if web_ui_base_url:
            detail_url = f"{web_ui_base_url.rstrip('/')}/match/{arena_unique_id}"
            embed["fields"].append(
                {
                    "name": "📊 詳細",
                    "value": f"[Web UIで見る]({detail_url})",
                    "inline": False,
                }
            )
        else:
            print("Discord notification: FRONTEND_URL not set, skipping detail link")

        embeds = [embed]

        # メッセージを送信
        url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages"
        headers = {
            "Authorization": f"Bot {bot_token}",
        }

        # MP4動画がある場合はファイルとして添付
        if mp4_url:
            try:
                # Presigned URLから動画をダウンロード
                print("Downloading MP4 from presigned URL...")
                video_response = requests.get(mp4_url, timeout=60)
                video_response.raise_for_status()

                # multipart/form-dataでファイルを添付して送信
                import json

                files = {
                    "files[0]": (
                        "minimap.mp4",
                        video_response.content,
                        "video/mp4",
                    ),
                }
                data = {
                    "payload_json": json.dumps({"embeds": embeds}),
                }
                response = requests.post(url, headers=headers, files=files, data=data, timeout=120)
            except Exception as e:
                print(f"Failed to attach MP4, sending without video: {e}")
                # 動画添付に失敗した場合はテキストのみ送信
                headers["Content-Type"] = "application/json"
                response = requests.post(url, headers=headers, json={"embeds": embeds}, timeout=30)
        else:
            # 動画なしの場合
            headers["Content-Type"] = "application/json"
            response = requests.post(url, headers=headers, json={"embeds": embeds}, timeout=30)

        response.raise_for_status()

        print(f"Discord notification sent successfully to channel {channel_id}")
        return True

    except Exception as e:
        print(f"Failed to send Discord notification: {e}")
        import traceback

        traceback.print_exc()
        return False
