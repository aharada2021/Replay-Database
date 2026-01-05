#!/usr/bin/env python3
"""
リプレイファイルのメタデータを調査し、同じゲームを識別できるフィールドを探す
"""

import json
import struct
import sys
from pathlib import Path

def parse_replay_metadata(replay_path: Path) -> dict:
    """リプレイファイルからメタデータを抽出"""
    with open(replay_path, 'rb') as f:
        # ヘッダー読み取り
        header = f.read(12)
        magic = struct.unpack('<I', header[0:4])[0]
        block1_size = struct.unpack('<I', header[4:8])[0]
        json_size = struct.unpack('<I', header[8:12])[0]

        # JSONブロック読み取り
        json_data = f.read(json_size)
        metadata = json.loads(json_data.decode('utf-8'))

        return metadata

def analyze_metadata(replay_path: Path):
    """メタデータを分析して表示"""
    print(f"\n{'='*80}")
    print(f"ファイル: {replay_path.name}")
    print(f"{'='*80}")

    metadata = parse_replay_metadata(replay_path)

    # 同じゲームを識別できそうなフィールドを探す
    important_fields = [
        'clientVersionFromExe',  # クライアントバージョン
        'gameLogic',             # ゲームロジック
        'mapDisplayName',        # マップ名
        'mapName',               # マップID
        'matchGroup',            # マッチグループ
        'playerName',            # プレイヤー名
        'playerID',              # プレイヤーID
        'dateTime',              # 日時
        'duration',              # 対戦時間
        'gameType',              # ゲームタイプ
        'battleType',            # 戦闘タイプ
        'scenarioConfigId',      # シナリオID
        'teamsCount',            # チーム数
        'playersPerTeam',        # チームごとのプレイヤー数
    ]

    print("\n🔍 主要フィールド:")
    for field in important_fields:
        if field in metadata:
            value = metadata[field]
            print(f"  {field:25s} = {value}")

    # ゲームを一意に識別できそうなフィールドを探す
    print("\n🎯 同じゲームの識別に使えそうなフィールド:")

    # 戦闘ID、セッションIDなどを探す
    potential_ids = []
    for key, value in metadata.items():
        if any(keyword in key.lower() for keyword in ['id', 'session', 'battle', 'arena', 'match']):
            if isinstance(value, (int, str)) and value:
                potential_ids.append((key, value))

    for key, value in potential_ids:
        print(f"  {key:25s} = {value}")

    # vehicles（参加プレイヤー情報）を確認
    if 'vehicles' in metadata:
        vehicles = metadata['vehicles']
        print(f"\n👥 参加プレイヤー数: {len(vehicles)}")

        # 最初の3人を表示
        print("  サンプル（最初の3人）:")
        if isinstance(vehicles, dict):
            for i, (avatar_id, player_data) in enumerate(list(vehicles.items())[:3]):
                name = player_data.get('name', 'Unknown')
                ship_id = player_data.get('shipId', 'Unknown')
                relation = player_data.get('relation', 'Unknown')
                print(f"    [{i+1}] Avatar ID: {avatar_id}, Name: {name}, Ship: {ship_id}, Relation: {relation}")
        elif isinstance(vehicles, list):
            for i, player_data in enumerate(vehicles[:3]):
                name = player_data.get('name', 'Unknown')
                ship_id = player_data.get('shipId', 'Unknown')
                relation = player_data.get('relation', 'Unknown')
                avatar_id = player_data.get('avatarId', 'Unknown')
                print(f"    [{i+1}] Avatar ID: {avatar_id}, Name: {name}, Ship: {ship_id}, Relation: {relation}")

    # dateTimeフィールドの詳細
    if 'dateTime' in metadata:
        date_time = metadata['dateTime']
        print(f"\n📅 dateTime: {date_time}")
        try:
            from datetime import datetime
            # Try different date formats
            if 'T' in date_time or 'Z' in date_time:
                dt = datetime.fromisoformat(date_time.replace('Z', '+00:00'))
            else:
                # Try DD.MM.YYYY HH:MM:SS format
                dt = datetime.strptime(date_time, '%d.%m.%Y %H:%M:%S')
            print(f"  タイムスタンプ: {int(dt.timestamp())}")
        except Exception as e:
            print(f"  タイムスタンプ変換エラー: {e}")

    # すべてのトップレベルキーを表示
    print(f"\n📋 すべてのメタデータキー ({len(metadata)}個):")
    for key in sorted(metadata.keys()):
        value = metadata[key]
        value_type = type(value).__name__
        if isinstance(value, (dict, list)):
            value_preview = f"{value_type}({len(value)} items)"
        else:
            value_preview = str(value)[:50]
        print(f"  {key:30s} : {value_type:12s} = {value_preview}")

def compare_replays(replay_paths: list):
    """複数のリプレイファイルを比較"""
    print("\n" + "="*80)
    print("複数リプレイの比較分析")
    print("="*80)

    metadatas = []
    for path in replay_paths:
        metadata = parse_replay_metadata(path)
        metadatas.append((path.name, metadata))

    # 共通のフィールドを確認
    if len(metadatas) >= 2:
        print("\n🔄 フィールド値の比較:")

        fields_to_compare = [
            'dateTime', 'mapName', 'matchGroup', 'gameLogic',
            'duration', 'teamsCount', 'playersPerTeam'
        ]

        for field in fields_to_compare:
            values = []
            for name, metadata in metadatas:
                value = metadata.get(field, 'N/A')
                values.append((name, value))

            print(f"\n  {field}:")
            for name, value in values:
                print(f"    {name:30s} = {value}")

            # 値が同じかチェック
            unique_values = set(v for _, v in values if v != 'N/A')
            if len(unique_values) == 1:
                print(f"    ✅ すべて同じ値")
            else:
                print(f"    ⚠️  値が異なる")

if __name__ == '__main__':
    if len(sys.argv) < 2:
        print("使用方法: python investigate_replay_metadata.py <replay_file1> [replay_file2] ...")
        print("\n例:")
        print("  python scripts/investigate_replay_metadata.py minimap_renderer/replays/146.wowsreplay")
        print("  python scripts/investigate_replay_metadata.py minimap_renderer/replays/*.wowsreplay")
        sys.exit(1)

    replay_paths = [Path(arg) for arg in sys.argv[1:]]

    # 各リプレイファイルを分析
    for replay_path in replay_paths:
        if replay_path.exists():
            analyze_metadata(replay_path)
        else:
            print(f"❌ ファイルが見つかりません: {replay_path}")

    # 複数ファイルがある場合は比較
    if len(replay_paths) >= 2:
        existing_paths = [p for p in replay_paths if p.exists()]
        if len(existing_paths) >= 2:
            compare_replays(existing_paths)
