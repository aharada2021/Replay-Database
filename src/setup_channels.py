"""
Discordサーバーに必要なチャンネルを自動作成するスクリプト

使用方法：
1. .envファイルにDISCORD_BOT_TOKENを設定
2. python setup_channels.py <GUILD_ID>
"""

import os
import sys
import requests
import yaml
from pathlib import Path
from dotenv import load_dotenv

# .envファイルから環境変数を読み込み
load_dotenv()

DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_API_BASE = "https://discord.com/api/v10"


def load_map_config() -> tuple:
    """マップ設定を読み込む"""
    map_file = Path(__file__).parent.parent / "config" / "map_names.yaml"
    try:
        with open(map_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            maps = data.get("maps", {})
            game_type_prefixes = data.get("game_type_prefixes", {})
            return maps, game_type_prefixes
    except Exception as e:
        print(f"❌ マップ設定の読み込みエラー: {e}")
        return {}, {}


def get_existing_channels(guild_id: str) -> dict:
    """サーバーの既存チャンネルを取得"""
    url = f"{DISCORD_API_BASE}/guilds/{guild_id}/channels"
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        channels = response.json()

        # テキストチャンネル（type=0）のみを名前でマッピング
        return {ch["name"]: ch for ch in channels if ch.get("type") == 0}
    except Exception as e:
        print(f"❌ チャンネル取得エラー: {e}")
        return {}


def create_channel(guild_id: str, channel_name: str, category_id: str = None) -> bool:
    """チャンネルを作成"""
    url = f"{DISCORD_API_BASE}/guilds/{guild_id}/channels"
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}", "Content-Type": "application/json"}

    payload = {"name": channel_name, "type": 0}  # テキストチャンネル

    if category_id:
        payload["parent_id"] = category_id

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        print(f"  ✅ 作成: #{channel_name}")
        return True
    except Exception as e:
        print(f"  ❌ 作成失敗: #{channel_name} - {e}")
        return False


def create_category(guild_id: str, category_name: str) -> str:
    """カテゴリを作成"""
    url = f"{DISCORD_API_BASE}/guilds/{guild_id}/channels"
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}", "Content-Type": "application/json"}

    payload = {"name": category_name, "type": 4}  # カテゴリ

    try:
        response = requests.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        category = response.json()
        print(f"✅ カテゴリ作成: {category_name}")
        return category["id"]
    except Exception as e:
        print(f"❌ カテゴリ作成失敗: {category_name} - {e}")
        return None


def setup_channels(guild_id: str, create_categories: bool = True):
    """サーバーにチャンネルをセットアップ"""
    print(f"\n🚀 サーバー（Guild ID: {guild_id}）にチャンネルをセットアップします\n")

    # マップ設定を読み込み
    maps, game_type_prefixes = load_map_config()
    if not maps or not game_type_prefixes:
        print("❌ マップ設定の読み込みに失敗しました")
        return

    print(f"📋 {len(maps)}個のマップ, {len(game_type_prefixes)}個のゲームタイプを検出")

    # 既存チャンネルを取得
    existing_channels = get_existing_channels(guild_id)
    print(f"📊 既存チャンネル数: {len(existing_channels)}")

    # 必要なチャンネル名のリストを生成
    required_channels = []
    for game_type, prefix in game_type_prefixes.items():
        for map_id, map_name in maps.items():
            channel_name = f"{prefix}{map_name}"
            required_channels.append((game_type, channel_name))

    print(f"📝 必要なチャンネル数: {len(required_channels)}\n")

    # カテゴリごとにチャンネルを作成
    if create_categories:
        category_ids = {}
        for game_type, prefix in game_type_prefixes.items():
            # カテゴリ名を決定
            if game_type == "clan":
                category_name = "🏴 Clan Battle Replays"
            elif game_type == "pvp":
                category_name = "⚔️ Random Battle Replays"
            elif game_type == "ranked":
                category_name = "🎖️ Ranked Battle Replays"
            else:
                category_name = f"{game_type.upper()} Replays"

            # カテゴリを作成（既存の場合はスキップ）
            category_id = create_category(guild_id, category_name)
            category_ids[game_type] = category_id

            print(f"\n📁 {category_name}")

            # カテゴリ内にチャンネルを作成
            for map_id, map_name in maps.items():
                channel_name = f"{prefix}{map_name}"
                if channel_name in existing_channels:
                    print(f"  ⏭️  スキップ: #{channel_name} (既存)")
                else:
                    create_channel(guild_id, channel_name, category_id)
    else:
        # カテゴリなしで作成
        created = 0
        skipped = 0

        for game_type, channel_name in required_channels:
            if channel_name in existing_channels:
                skipped += 1
            else:
                if create_channel(guild_id, channel_name):
                    created += 1

        print(f"\n📊 結果: {created}個作成, {skipped}個スキップ")

    print("\n✅ チャンネルセットアップが完了しました！")


if __name__ == "__main__":
    if not DISCORD_BOT_TOKEN:
        print("❌ 環境変数 DISCORD_BOT_TOKEN を設定してください")
        sys.exit(1)

    if len(sys.argv) < 2:
        print("使用方法: python setup_channels.py <GUILD_ID> [--no-categories]")
        print("\n例:")
        print("  python setup_channels.py 123456789012345678")
        print("  python setup_channels.py 123456789012345678 --no-categories")
        sys.exit(1)

    guild_id = sys.argv[1]
    create_categories = "--no-categories" not in sys.argv

    setup_channels(guild_id, create_categories)
