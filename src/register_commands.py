"""
Discord Slash Commandsを登録するスクリプト

使用方法：
  python register_commands.py                    # グローバルに登録（全サーバー）
  python register_commands.py <GUILD_ID>         # 特定のサーバーに登録
  python register_commands.py --global           # グローバルに登録（明示的）
"""

import os
import sys
import requests
from dotenv import load_dotenv

# .envファイルから環境変数を読み込み
load_dotenv()

DISCORD_APPLICATION_ID = os.getenv('DISCORD_APPLICATION_ID')
DISCORD_BOT_TOKEN = os.getenv('DISCORD_BOT_TOKEN')

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
        sys.exit(1)

    print("Discord Slash Commandsを登録します...")
    print(f"Application ID: {DISCORD_APPLICATION_ID}")

    # コマンドライン引数からGUILD_IDを取得
    guild_id = None
    if len(sys.argv) > 1:
        if sys.argv[1] == '--global':
            # 明示的にグローバル登録
            guild_id = None
        elif sys.argv[1] in ['--help', '-h']:
            print(__doc__)
            sys.exit(0)
        else:
            # 引数をGUILD_IDとして使用
            guild_id = sys.argv[1]

    # 特定のサーバーまたはグローバルに登録
    if guild_id:
        print(f"\n特定のサーバーに登録します（Guild ID: {guild_id}）")
        result = register_guild_command(DISCORD_APPLICATION_ID, guild_id, DISCORD_BOT_TOKEN)
        if result:
            print("\n✅ 登録が完了しました！")
            print("コマンドは即座に使用可能です。")
    else:
        print("\nグローバルに登録します（全てのサーバー）")
        result = register_global_command(DISCORD_APPLICATION_ID, DISCORD_BOT_TOKEN)
        if result:
            print("\n✅ 登録が完了しました！")
            print("⚠️  反映には最大1時間かかる場合があります。")

    print("\n完了しました！")
