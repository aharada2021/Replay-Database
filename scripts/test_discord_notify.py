#!/usr/bin/env python3
"""
Discord通知のテストスクリプト

使用方法:
    export DISCORD_BOT_TOKEN="your_bot_token"
    export NOTIFICATION_CHANNEL_ID="your_channel_id"
    python3 scripts/test_discord_notify.py
"""

import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from utils.discord_notify import send_replay_notification

# テスト用のクラン戦レコード
TEST_RECORD = {
    "arenaUniqueID": "3487309050689265",
    "playerID": 0,
    "playerName": "_meteor0090",
    "mapId": "spaces/53_Shoreside",
    "gameType": "clan",
    "winLoss": "win",
    "dateTime": "03.12.2025 22:11:20",
    "ownPlayer": {
        "name": "_meteor0090",
        "clanTag": "OZEKI",
        "shipName": "Neustrashimy",
    },
    "allyClanTag": "OZEKI",
    "enemyClanTag": "CLS",
    "allies": [
        {"name": "MCTK", "clanTag": "OZEKI", "shipName": "Adatara"},
        {"name": "TOKIWA_Tachyon", "clanTag": "OZEKI", "shipName": "Kitakaze"},
        {"name": "Fallens_Mostima", "clanTag": "APCG", "shipName": "Alaska"},
        {"name": "ClyneLacus", "clanTag": "OZEKI", "shipName": "Mogador"},
        {"name": "Burikazu_HNKD", "clanTag": "OZEKI", "shipName": "Menno van Coehoorn"},
        {"name": "EvolTRx0UC_HivNexusZZ", "clanTag": "OZEKI", "shipName": "Kitakaze"},
    ],
    "enemies": [
        {"name": "XueNong", "clanTag": "AOBA", "shipName": "Alaska"},
        {"name": "AGI_Takao", "clanTag": "CLS", "shipName": "Błyskawica '52"},
        {"name": "Whert_haoxuan", "clanTag": "CLS", "shipName": "Manteuffel"},
        {"name": "drangon_steel", "clanTag": "CLS", "shipName": "Somme"},
        {"name": "xiaogete", "clanTag": "CLS", "shipName": "Menno van Coehoorn"},
        {"name": "Blue_gel", "clanTag": "CLS", "shipName": "Encounter"},
        {"name": "Ying_tu", "clanTag": "CLS", "shipName": "Valparaíso"},
    ],
}


def main():
    channel_id = os.environ.get("NOTIFICATION_CHANNEL_ID")
    bot_token = os.environ.get("DISCORD_BOT_TOKEN")

    if not channel_id:
        print("Error: NOTIFICATION_CHANNEL_ID environment variable not set")
        sys.exit(1)

    if not bot_token:
        print("Error: DISCORD_BOT_TOKEN environment variable not set")
        sys.exit(1)

    print(f"Sending test notification to channel {channel_id}...")
    print(f"Record: {TEST_RECORD['playerName']} - {TEST_RECORD['gameType']}")

    success = send_replay_notification(
        channel_id=channel_id,
        bot_token=bot_token,
        record=TEST_RECORD,
    )

    if success:
        print("Test notification sent successfully!")
    else:
        print("Failed to send test notification")
        sys.exit(1)


if __name__ == "__main__":
    main()
