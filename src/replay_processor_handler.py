import os
import json
import logging
import tempfile
from pathlib import Path
from typing import Optional
import requests

from replay_processor import ReplayProcessor

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# 環境変数
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
DISCORD_API_BASE = "https://discord.com/api/v10"


def load_map_config() -> tuple:
    """マップ設定を読み込む"""
    import yaml

    map_file = Path(__file__).parent / "map_names.yaml"
    try:
        with open(map_file, 'r', encoding='utf-8') as f:
            data = yaml.safe_load(f)
            maps = data.get('maps', {})
            game_type_prefixes = data.get('game_type_prefixes', {})
            default_map_name = data.get('default_map_name', 'その他のマップ')
            return maps, game_type_prefixes, default_map_name
    except Exception as e:
        logger.error(f"マップ名マッピングファイルの読み込みエラー: {e}")
        return {}, {}, 'その他のマップ'


def extract_map_id_from_filename(filename: str) -> Optional[str]:
    """リプレイファイル名からマップIDを抽出"""
    if not filename.endswith('.wowsreplay'):
        return None

    name_without_ext = filename.replace('.wowsreplay', '')
    parts = name_without_ext.split('_')

    if len(parts) >= 4:
        for i in range(len(parts) - 1, -1, -1):
            if parts[i].isdigit():
                if i + 1 < len(parts):
                    map_id = '_'.join(parts[i + 1:])
                    return map_id
                break

    return None


def get_opponent_clan(players_info: dict) -> str:
    """敵プレイヤーの過半数のクランタグを取得"""
    enemies = players_info.get('enemies', [])

    if not enemies:
        return "不明"

    clan_counts = {}
    for player in enemies:
        clan_tag = player.get('clanTag')
        if clan_tag:
            clan_counts[clan_tag] = clan_counts.get(clan_tag, 0) + 1

    if not clan_counts:
        return "クランなし"

    max_clan_tag = max(clan_counts.items(), key=lambda x: x[1])
    tag, count = max_clan_tag

    total_enemies = len(enemies)
    if count >= total_enemies / 2:
        return f"{tag} ({count}名)"
    else:
        return f"混成 (最多: {tag} {count}名)"


def download_file(url: str, dest_path: Path) -> bool:
    """URLからファイルをダウンロード"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        with open(dest_path, 'wb') as f:
            f.write(response.content)

        logger.info(f"ファイルをダウンロード: {dest_path}")
        return True
    except Exception as e:
        logger.error(f"ファイルダウンロードエラー: {e}")
        return False


def send_channel_message(channel_id: str, content: str = None, embed: dict = None, files: list = None) -> bool:
    """Discordチャンネルにメッセージを送信"""
    url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}"
    }

    payload = {}
    if content:
        payload['content'] = content
    if embed:
        payload['embeds'] = [embed]

    try:
        if files:
            # ファイル添付付きの場合
            files_payload = []
            for i, file_path in enumerate(files):
                with open(file_path, 'rb') as f:
                    files_payload.append((f'files[{i}]', (Path(file_path).name, f.read())))

            response = requests.post(
                url,
                headers=headers,
                data={'payload_json': json.dumps(payload)},
                files=files_payload,
                timeout=60
            )
        else:
            # テキストのみ
            headers['Content-Type'] = 'application/json'
            response = requests.post(url, headers=headers, json=payload, timeout=30)

        response.raise_for_status()
        logger.info("メッセージを送信しました")
        return True
    except Exception as e:
        logger.error(f"メッセージ送信エラー: {e}")
        return False


def get_channel_by_name(guild_id: str, channel_name: str) -> Optional[str]:
    """チャンネル名からチャンネルIDを取得"""
    url = f"{DISCORD_API_BASE}/guilds/{guild_id}/channels"
    headers = {
        "Authorization": f"Bot {DISCORD_BOT_TOKEN}"
    }

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        channels = response.json()

        for channel in channels:
            if channel.get('name') == channel_name and channel.get('type') == 0:  # Text channel
                return channel['id']

        return None
    except Exception as e:
        logger.error(f"チャンネル取得エラー: {e}")
        return None


def send_followup_message(webhook_url: str, content: str, flags: int = 64):
    """Discord Webhookでフォローアップメッセージを送信"""
    try:
        response = requests.post(
            webhook_url,
            json={
                "content": content,
                "flags": flags
            },
            timeout=30
        )
        response.raise_for_status()
        logger.info("フォローアップメッセージを送信しました")
    except Exception as e:
        logger.error(f"フォローアップメッセージ送信エラー: {e}")


def handle_replay_processing(event, context):
    """
    リプレイファイル処理用Lambda関数

    Args:
        event: {
            'attachment': Discord添付ファイル情報,
            'guild_id': DiscordサーバーID,
            'webhook_url': Discord Webhook URL
        }
        context: Lambda context
    """
    try:
        attachment = event['attachment']
        guild_id = event['guild_id']
        webhook_url = event['webhook_url']

        filename = attachment['filename']
        file_url = attachment['url']

        # マップ設定を読み込み
        MAPS, GAME_TYPE_PREFIXES, DEFAULT_MAP_NAME = load_map_config()

        # 一時ディレクトリでファイルを処理
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            replay_path = temp_path / filename

            # ファイルをダウンロード
            if not download_file(file_url, replay_path):
                send_followup_message(
                    webhook_url,
                    "❌ ファイルのダウンロードに失敗しました。"
                )
                return

            # リプレイファイルを処理
            output_dir = temp_path / "videos"
            battle_time, game_type, mp4_path, players_info = ReplayProcessor.process_replay(
                replay_path,
                output_dir
            )

            # マップIDを取得
            map_id = extract_map_id_from_filename(filename)
            if not map_id:
                send_followup_message(
                    webhook_url,
                    "❌ リプレイファイル名からマップ情報を取得できませんでした。"
                )
                return

            # 日本語マップ名を取得
            japanese_map_name = MAPS.get(map_id, DEFAULT_MAP_NAME)

            # ゲームタイプに基づいてprefixを取得
            prefix = ""
            if game_type and game_type in GAME_TYPE_PREFIXES:
                prefix = GAME_TYPE_PREFIXES[game_type]
                logger.info(f"ゲームタイプ: {game_type}, prefix: {prefix}")
            else:
                logger.warning(f"不明なゲームタイプ: {game_type}, prefixなしで投稿します")

            # チャンネル名を構築
            target_channel_name = f"{prefix}{japanese_map_name}"
            logger.info(f"マップID: {map_id} → 日本語名: {japanese_map_name} → チャンネル: {target_channel_name}")

            # チャンネルIDを取得
            target_channel_id = get_channel_by_name(guild_id, target_channel_name)
            if not target_channel_id:
                send_followup_message(
                    webhook_url,
                    f"❌ チャンネル「{target_channel_name}」が見つかりませんでした。"
                )
                return

            if not battle_time:
                battle_time = "取得失敗"

            # 対戦クランを決定
            clan_name = get_opponent_clan(players_info)

            # Embedを作成
            embed = {
                "title": f"🎮 リプレイ: {target_channel_name}",
                "color": 3447003,  # Blue
                "fields": [
                    {"name": "🏴 対戦クラン", "value": clan_name, "inline": True},
                    {"name": "⏰ 対戦時間", "value": battle_time, "inline": True},
                ]
            }

            # ゲームタイプを表示
            if game_type:
                embed["fields"].append({"name": "🎯 ゲームタイプ", "value": game_type, "inline": True})

            # ファイル名を追加
            embed["fields"].append({"name": "📁 ファイル名", "value": filename, "inline": False})

            # プレイヤー情報を追加
            if players_info:
                if players_info['own']:
                    own_text = '\n'.join([
                        f"• [{p['clanTag']}] {p['name']} ({p['shipName']})" if p['clanTag']
                        else f"• {p['name']} ({p['shipName']})"
                        for p in players_info['own']
                    ])
                    embed['fields'].append({"name": "👤 自分", "value": own_text, "inline": False})

                if players_info['allies']:
                    allies_list = [
                        f"• [{p['clanTag']}] {p['name']} ({p['shipName']})" if p['clanTag']
                        else f"• {p['name']} ({p['shipName']})"
                        for p in players_info['allies']
                    ]
                    allies_text = '\n'.join(allies_list)
                    if len(allies_text) > 1024:
                        allies_text = '\n'.join(allies_list[:15]) + f"\n... 他 {len(allies_list) - 15} 名"
                    embed['fields'].append({"name": "🤝 味方", "value": allies_text, "inline": True})

                if players_info['enemies']:
                    enemies_list = [
                        f"• [{p['clanTag']}] {p['name']} ({p['shipName']})" if p['clanTag']
                        else f"• {p['name']} ({p['shipName']})"
                        for p in players_info['enemies']
                    ]
                    enemies_text = '\n'.join(enemies_list)
                    if len(enemies_text) > 1024:
                        enemies_text = '\n'.join(enemies_list[:15]) + f"\n... 他 {len(enemies_list) - 15} 名"
                    embed['fields'].append({"name": "⚔️ 敵", "value": enemies_text, "inline": True})

            # ファイルを準備
            files = []
            if mp4_path and mp4_path.exists():
                files.append(str(mp4_path))
            else:
                files.append(str(replay_path))

            # チャンネルに投稿
            success = send_channel_message(target_channel_id, embed=embed, files=files)

            if success:
                send_followup_message(
                    webhook_url,
                    f"✅ リプレイファイルを <#{target_channel_id}> に投稿しました！"
                )
            else:
                send_followup_message(
                    webhook_url,
                    "❌ メッセージの投稿に失敗しました。"
                )

    except Exception as e:
        logger.error(f"リプレイ処理エラー: {e}", exc_info=True)
        try:
            send_followup_message(
                event.get('webhook_url'),
                f"❌ 処理中にエラーが発生しました: {str(e)}"
            )
        except:
            pass
