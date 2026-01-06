#!/usr/bin/env python3
"""
BattleStatsパケットの配列インデックスを既知の値から特定するツール

使用方法:
    python3 scripts/analyze_battlestats_indices.py <battlestats.json> <player_name> <known_values>
"""

import sys
import json
from pathlib import Path

def find_player_data(battlestats, player_name):
    """プレイヤー名からplayersPublicInfoのデータを取得"""
    players_info = battlestats.get('playersPublicInfo', {})

    for player_id, data in players_info.items():
        if isinstance(data, list) and len(data) > 1:
            # インデックス1にプレイヤー名があると仮定
            if data[1] == player_name:
                return player_id, data

    return None, None

def analyze_indices(data, known_values):
    """既知の値から配列インデックスを特定"""
    results = {}

    for value_name, value in known_values.items():
        matches = []
        for idx, item in enumerate(data):
            if item == value:
                matches.append(idx)

        if matches:
            results[value_name] = matches

    return results

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n例:")
        print('  python3 scripts/analyze_battlestats_indices.py data/replays/14.11.0.0/replay_battlestats.json "_meteor0090" \'{"damage": 57320, "received_damage": 3630}\'')
        sys.exit(1)

    battlestats_path = Path(sys.argv[1])

    if not battlestats_path.exists():
        print(f"❌ ファイルが見つかりません: {battlestats_path}")
        sys.exit(1)

    # BattleStatsデータを読み込み
    with open(battlestats_path, 'r', encoding='utf-8') as f:
        battlestats = json.load(f)

    print(f"\n{'='*80}")
    print(f"BattleStats配列インデックス解析")
    print(f"{'='*80}\n")

    # playersPublicInfoの全プレイヤーを表示
    players_info = battlestats.get('playersPublicInfo', {})

    print(f"📋 プレイヤー一覧 (全{len(players_info)}名):\n")

    for player_id, data in players_info.items():
        if isinstance(data, list) and len(data) > 1:
            name = data[1] if len(data) > 1 else "Unknown"
            team_id = "?"
            # チームIDを探す（一般的に低いインデックスにある）
            for idx in range(min(20, len(data))):
                if isinstance(data[idx], int) and data[idx] in [0, 1]:
                    team_id = data[idx]
                    break

            print(f"  Player ID: {player_id:>12} | Name: {name:<30} | Data Length: {len(data)}")

    # プレイヤー名が指定されている場合
    if len(sys.argv) >= 3:
        player_name = sys.argv[2]

        print(f"\n{'='*80}")
        print(f"プレイヤー '{player_name}' のデータ解析")
        print(f"{'='*80}\n")

        player_id, player_data = find_player_data(battlestats, player_name)

        if player_data is None:
            print(f"❌ プレイヤー '{player_name}' が見つかりませんでした")
            sys.exit(1)

        print(f"✅ プレイヤー発見: ID={player_id}\n")
        print(f"配列長: {len(player_data)}\n")

        # 既知の値が指定されている場合
        if len(sys.argv) >= 4:
            known_values = json.loads(sys.argv[3])

            print(f"🔍 既知の値から配列インデックスを特定:\n")

            matches = analyze_indices(player_data, known_values)

            for value_name, indices in matches.items():
                value = known_values[value_name]
                if indices:
                    print(f"  {value_name:<20} = {value:<10} → インデックス: {indices}")
                else:
                    print(f"  {value_name:<20} = {value:<10} → ❌ 見つかりませんでした")

            # 見つからなかった値
            not_found = [k for k, v in known_values.items() if k not in matches or not matches[k]]
            if not_found:
                print(f"\n⚠️  以下の値は配列内に見つかりませんでした:")
                for value_name in not_found:
                    print(f"    - {value_name}: {known_values[value_name]}")

        # 配列の全要素を表示（デバッグ用）
        print(f"\n{'='*80}")
        print(f"配列データの詳細 (最初の200項目)")
        print(f"{'='*80}\n")

        for idx, value in enumerate(player_data[:200]):
            value_type = type(value).__name__

            # 値の表示を整形
            if isinstance(value, str):
                display_value = f'"{value}"'
            elif isinstance(value, (list, dict)):
                display_value = f"{value_type}({len(value)} items)"
            elif isinstance(value, float):
                display_value = f"{value:.2f}"
            else:
                display_value = str(value)

            print(f"  [{idx:>3}] {value_type:<8} = {display_value}")

if __name__ == '__main__':
    main()
