"""
Discord Slash Commandsを登録するスクリプト

デプロイ後に一度実行してください：
python register_commands.py
"""

import os
import requests
from dotenv import load_dotenv

# .envファイルから環境変数を読み込み
load_dotenv()

DISCORD_APPLICATION_ID = os.getenv('DISCORD_APPLICATION_ID')
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')
GUILD_ID = os.getenv('GUILD_ID')  # オプション：特定のサーバーのみに登録する場合

# Discord API Base URL
DISCORD_API_BASE = "https://discord.com/api/v10"


def register_guild_command(application_id: str, guild_id: str, bot_token: str):
    """特定のサーバーにSlash Commandを登録（即座に反映）"""
    url = f"{DISCORD_API_BASE}/applications/{application_id}/guilds/{guild_id}/commands"
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json"
    }

    # コマンド定義
    command = {
        "name": "upload_replay",
        "description": "WoWSリプレイファイルをアップロードして自動分類",
        "options": [
            {
                "name": "file",
                "description": "リプレイファイル (.wowsreplay)",
                "type": 11,  # ATTACHMENT type
                "required": True
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=command, timeout=30)
        response.raise_for_status()
        print(f"✅ Slash Commandを登録しました（サーバーID: {guild_id}）")
        print(f"コマンド: /{command['name']}")
        return response.json()
    except Exception as e:
        print(f"❌ エラー: {e}")
        if hasattr(e, 'response'):
            print(f"レスポンス: {e.response.text}")
        return None


def register_global_command(application_id: str, bot_token: str):
    """グローバルにSlash Commandを登録（反映に最大1時間かかる）"""
    url = f"{DISCORD_API_BASE}/applications/{application_id}/commands"
    headers = {
        "Authorization": f"Bot {bot_token}",
        "Content-Type": "application/json"
    }

    # コマンド定義
    command = {
        "name": "upload_replay",
        "description": "WoWSリプレイファイルをアップロードして自動分類",
        "options": [
            {
                "name": "file",
                "description": "リプレイファイル (.wowsreplay)",
                "type": 11,  # ATTACHMENT type
                "required": True
            }
        ]
    }

    try:
        response = requests.post(url, headers=headers, json=command, timeout=30)
        response.raise_for_status()
        print("✅ Slash Commandをグローバルに登録しました")
        print(f"コマンド: /{command['name']}")
        print("⚠️  反映には最大1時間かかる場合があります")
        return response.json()
    except Exception as e:
        print(f"❌ エラー: {e}")
        if hasattr(e, 'response'):
            print(f"レスポンス: {e.response.text}")
        return None


if __name__ == '__main__':
    if not DISCORD_APPLICATION_ID or not DISCORD_BOT_TOKEN:
        print("❌ 環境変数 DISCORD_APPLICATION_ID と DISCORD_BOT_TOKEN を設定してください")
        exit(1)

    print("Discord Slash Commandsを登録します...")
    print(f"Application ID: {DISCORD_APPLICATION_ID}")

    # GUILD_IDが設定されている場合は特定のサーバーに登録（即座に反映）
    if GUILD_ID:
        print(f"\n特定のサーバーに登録します（Guild ID: {GUILD_ID}）")
        register_guild_command(DISCORD_APPLICATION_ID, GUILD_ID, DISCORD_BOT_TOKEN)
    else:
        print("\nグローバルに登録します（全てのサーバー）")
        register_global_command(DISCORD_APPLICATION_ID, DISCORD_BOT_TOKEN)

    print("\n完了しました！")
