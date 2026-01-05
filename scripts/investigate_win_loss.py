#!/usr/bin/env python3
"""
リプレイファイルから勝敗情報を取得できるか調査

使用方法:
    python3 scripts/investigate_win_loss.py <replay_file.wowsreplay>
"""

import json
import struct
import sys
from pathlib import Path

def parse_replay_metadata(replay_path: Path) -> dict:
    """リプレイファイルからメタデータを抽出"""
    with open(replay_path, 'rb') as f:
        # ヘッダー読み取り（12バイト）
        header = f.read(12)
        magic = struct.unpack('<I', header[0:4])[0]
        block1_size = struct.unpack('<I', header[4:8])[0]
        json_size = struct.unpack('<I', header[8:12])[0]

        # JSONブロック読み取り
        json_data = f.read(json_size)
        metadata = json.loads(json_data.decode('utf-8'))

        return metadata

def investigate_win_loss(replay_path: Path):
    """勝敗情報を調査"""
    print(f"\n{'='*80}")
    print(f"勝敗情報の調査: {replay_path.name}")
    print(f"{'='*80}\n")

    metadata = parse_replay_metadata(replay_path)

    # プレイヤー名とIDを取得
    player_name = metadata.get('playerName', 'Unknown')
    player_id = metadata.get('playerID', -1)
    print(f"📝 プレイヤー: {player_name}")
    print(f"   Player ID: {player_id}\n")

    # 勝敗に関連しそうなキーワード
    win_loss_keywords = [
        'win', 'winner', 'victory', 'defeat', 'loss', 'loser',
        'result', 'outcome', 'finish', 'end',
        'team', 'score', 'point', 'kill', 'death',
        'damage', 'exp', 'credit', 'battle'
    ]

    print("🔍 勝敗に関連しそうなフィールド:\n")

    # すべてのキーを検索
    found_fields = []
    for key in metadata.keys():
        key_lower = key.lower()
        for keyword in win_loss_keywords:
            if keyword in key_lower:
                value = metadata[key]
                value_type = type(value).__name__

                if isinstance(value, (dict, list)):
                    value_preview = f"{value_type}({len(value)} items)"
                else:
                    value_preview = str(value)[:100]

                found_fields.append((key, value_type, value_preview, value))
                break

    # 見つかったフィールドを表示
    if found_fields:
        for key, value_type, value_preview, _ in found_fields:
            print(f"  {key:30s} : {value_type:12s} = {value_preview}")
    else:
        print("  該当するフィールドが見つかりませんでした")

    # vehicles（プレイヤー情報）を詳細調査
    print(f"\n{'='*80}")
    print("👥 Vehicles（プレイヤー情報）の詳細調査")
    print(f"{'='*80}\n")

    if 'vehicles' in metadata:
        vehicles = metadata['vehicles']
        print(f"参加プレイヤー数: {len(vehicles)}\n")

        # 自分のプレイヤー情報を探す
        own_vehicle = None
        if isinstance(vehicles, list):
            for vehicle in vehicles:
                if vehicle.get('name') == player_name:
                    own_vehicle = vehicle
                    break
        elif isinstance(vehicles, dict):
            # playerIDで検索
            for vid, vehicle in vehicles.items():
                if vehicle.get('name') == player_name:
                    own_vehicle = vehicle
                    break

        if own_vehicle:
            print(f"🎯 自分のプレイヤー情報 ({player_name}):")
            for key, value in sorted(own_vehicle.items()):
                value_type = type(value).__name__
                if isinstance(value, (dict, list)):
                    value_preview = f"{value_type}({len(value)} items)"
                else:
                    value_preview = str(value)[:100]
                print(f"  {key:25s} : {value_type:12s} = {value_preview}")
        else:
            print(f"⚠️  自分のプレイヤー情報が見つかりませんでした")

        # チーム情報を調査
        print(f"\n📊 チーム分析:")

        team_counts = {}
        relation_counts = {}

        vehicle_list = vehicles if isinstance(vehicles, list) else vehicles.values()

        for vehicle in vehicle_list:
            team_id = vehicle.get('teamId', 'Unknown')
            relation = vehicle.get('relation', 'Unknown')

            team_counts[team_id] = team_counts.get(team_id, 0) + 1
            relation_counts[relation] = relation_counts.get(relation, 0) + 1

        print(f"\nチームID別人数:")
        for team_id, count in sorted(team_counts.items()):
            print(f"  Team {team_id}: {count}人")

        print(f"\nRelation別人数:")
        relation_labels = {
            0: "自分",
            1: "味方",
            2: "敵"
        }
        for relation, count in sorted(relation_counts.items()):
            label = relation_labels.get(relation, f"Unknown({relation})")
            print(f"  {label}: {count}人")

    # すべてのトップレベルキーを表示（勝敗関連を強調）
    print(f"\n{'='*80}")
    print(f"📋 すべてのメタデータキー ({len(metadata)}個)")
    print(f"{'='*80}\n")

    for key in sorted(metadata.keys()):
        value = metadata[key]
        value_type = type(value).__name__

        # 勝敗関連キーワードが含まれているかチェック
        is_win_loss_related = any(kw in key.lower() for kw in win_loss_keywords)
        marker = "🎯 " if is_win_loss_related else "   "

        if isinstance(value, (dict, list)):
            value_preview = f"{value_type}({len(value)} items)"
        else:
            value_preview = str(value)[:60]

        print(f"{marker}{key:30s} : {value_type:12s} = {value_preview}")

    # 特定のフィールドの詳細調査
    print(f"\n{'='*80}")
    print("🔬 特定フィールドの詳細")
    print(f"{'='*80}\n")

    # battleResultが存在する場合
    if 'battleResult' in metadata:
        print("✅ battleResult フィールドが見つかりました:")
        print(json.dumps(metadata['battleResult'], indent=2, ensure_ascii=False))

    # playerVehicleが存在する場合
    if 'playerVehicle' in metadata:
        print(f"\n📌 playerVehicle: {metadata['playerVehicle']}")

    # scenarioが存在する場合
    if 'scenario' in metadata:
        print(f"\n📌 scenario: {metadata['scenario']}")

def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n例:")
        print("  python3 scripts/investigate_win_loss.py minimap_renderer/replays/146.wowsreplay")
        sys.exit(1)

    replay_path = Path(sys.argv[1])

    if not replay_path.exists():
        print(f"❌ ファイルが見つかりません: {replay_path}")
        sys.exit(1)

    investigate_win_loss(replay_path)

    # 複数ファイルがある場合は比較
    if len(sys.argv) > 2:
        print(f"\n{'='*80}")
        print("複数リプレイファイルの比較")
        print(f"{'='*80}\n")

        for i, replay_arg in enumerate(sys.argv[1:], 1):
            replay_path = Path(replay_arg)
            if replay_path.exists():
                metadata = parse_replay_metadata(replay_path)
                player_name = metadata.get('playerName', 'Unknown')

                print(f"\n[{i}] {replay_path.name}")
                print(f"    プレイヤー: {player_name}")

                # 勝敗関連フィールドを探す
                if 'battleResult' in metadata:
                    print(f"    battleResult: あり")
                    print(f"    詳細: {metadata['battleResult']}")
                else:
                    print(f"    battleResult: なし")

if __name__ == '__main__':
    main()
