#!/usr/bin/env python3
"""
複数のリプレイファイルが同じゲーム（対戦）のものかを判定するツール

使用方法:
    python3 scripts/check_same_game.py replay1.wowsreplay replay2.wowsreplay [replay3.wowsreplay ...]
"""

import sys
import json
import struct
import hashlib
from pathlib import Path
from datetime import datetime
from typing import Optional

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

def parse_datetime(date_str: str) -> Optional[datetime]:
    """dateTime文字列をdatetimeオブジェクトに変換"""
    try:
        if 'T' in date_str or 'Z' in date_str:
            return datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        else:
            # DD.MM.YYYY HH:MM:SS format
            return datetime.strptime(date_str, '%d.%m.%Y %H:%M:%S')
    except Exception as e:
        print(f"⚠️  日時の解析エラー: {e}")
        return None

def get_game_identifier(metadata: dict) -> str:
    """リプレイのゲーム識別子を生成（複合キー）"""
    elements = [
        metadata.get('dateTime', ''),
        metadata.get('mapName', ''),
        metadata.get('matchGroup', ''),
        str(metadata.get('scenarioConfigId', '')),
        str(metadata.get('duration', '')),
    ]

    key = '|'.join(elements)
    return hashlib.sha256(key.encode()).hexdigest()[:16]

def get_player_set(metadata: dict) -> set:
    """リプレイの参加プレイヤーセットを取得"""
    vehicles = metadata.get('vehicles', [])

    player_set = set()
    for vehicle in vehicles:
        name = vehicle.get('name', '')
        ship_id = vehicle.get('shipId', '')
        if name and ship_id:
            player_set.add((name, ship_id))

    return player_set

def is_same_game(metadata1: dict, metadata2: dict, verbose: bool = False) -> tuple[bool, str]:
    """2つのリプレイが同じゲームかを判定（詳細な理由を返す）"""

    # 1. dateTimeチェック
    dt1 = parse_datetime(metadata1.get('dateTime', ''))
    dt2 = parse_datetime(metadata2.get('dateTime', ''))

    if dt1 and dt2:
        time_diff = abs((dt1 - dt2).total_seconds())
        if time_diff > 60:  # 1分以上の差がある場合
            return False, f"開始時刻が異なる（{time_diff:.0f}秒の差）"
    else:
        if verbose:
            print(f"  ⚠️  dateTimeの解析に失敗")

    # 2. mapNameチェック
    map1 = metadata1.get('mapName', '')
    map2 = metadata2.get('mapName', '')
    if map1 != map2:
        return False, f"マップが異なる（{map1} vs {map2}）"

    # 3. matchGroupチェック
    mg1 = metadata1.get('matchGroup', '')
    mg2 = metadata2.get('matchGroup', '')
    if mg1 != mg2:
        return False, f"マッチグループが異なる（{mg1} vs {mg2}）"

    # 4. プレイヤーセットチェック
    players1 = get_player_set(metadata1)
    players2 = get_player_set(metadata2)

    if not players1 or not players2:
        return False, "プレイヤー情報が不足"

    common_players = players1 & players2
    total_unique = len(players1 | players2)
    match_ratio = len(common_players) / total_unique if total_unique > 0 else 0

    if verbose:
        print(f"  プレイヤー一致率: {match_ratio*100:.1f}% ({len(common_players)}/{total_unique}人)")

    # 70%以上一致すれば同じゲーム
    if match_ratio < 0.7:
        return False, f"プレイヤーの一致率が低い（{match_ratio*100:.1f}%）"

    # すべてのチェックをパス
    return True, f"同じゲームと判定（一致率: {match_ratio*100:.1f}%）"

def analyze_replays(replay_paths: list[Path]):
    """複数のリプレイファイルを分析"""

    print(f"\n{'='*80}")
    print(f"リプレイファイルのゲーム一致判定")
    print(f"{'='*80}\n")

    # メタデータを読み込み
    replays = []
    for path in replay_paths:
        if not path.exists():
            print(f"❌ ファイルが見つかりません: {path}")
            continue

        try:
            metadata = parse_replay_metadata(path)
            replays.append({
                'path': path,
                'name': path.name,
                'metadata': metadata,
                'game_id': get_game_identifier(metadata),
                'player_name': metadata.get('playerName', 'Unknown'),
                'date_time': metadata.get('dateTime', ''),
                'map': metadata.get('mapDisplayName', ''),
                'players': get_player_set(metadata),
            })
            print(f"✅ 読み込み成功: {path.name}")
            print(f"   プレイヤー: {metadata.get('playerName', 'Unknown')}")
            print(f"   日時: {metadata.get('dateTime', '')}")
            print(f"   マップ: {metadata.get('mapDisplayName', '')}")
            print(f"   参加人数: {len(metadata.get('vehicles', []))}人")
        except Exception as e:
            print(f"❌ 読み込みエラー: {path.name} - {e}")

    if len(replays) < 2:
        print("\n⚠️  比較するには最低2つのリプレイファイルが必要です")
        return

    # ゲーム識別子でグループ化
    print(f"\n{'='*80}")
    print("ゲーム識別子による分析")
    print(f"{'='*80}\n")

    game_groups = {}
    for replay in replays:
        game_id = replay['game_id']
        if game_id not in game_groups:
            game_groups[game_id] = []
        game_groups[game_id].append(replay)

    print(f"検出されたゲーム数: {len(game_groups)}")

    for i, (game_id, group) in enumerate(game_groups.items(), 1):
        print(f"\n📊 ゲームグループ {i} (ID: {game_id})")
        print(f"   リプレイ数: {len(group)}")
        for replay in group:
            print(f"   - {replay['name']} (プレイヤー: {replay['player_name']})")

    # ペアワイズ比較
    print(f"\n{'='*80}")
    print("詳細比較（ペアワイズ）")
    print(f"{'='*80}\n")

    for i in range(len(replays)):
        for j in range(i + 1, len(replays)):
            replay1 = replays[i]
            replay2 = replays[j]

            print(f"\n🔍 比較: {replay1['name']} vs {replay2['name']}")
            print(f"   {replay1['name']}: {replay1['player_name']} @ {replay1['date_time']}")
            print(f"   {replay2['name']}: {replay2['player_name']} @ {replay2['date_time']}")

            is_same, reason = is_same_game(replay1['metadata'], replay2['metadata'], verbose=True)

            if is_same:
                print(f"   ✅ {reason}")
            else:
                print(f"   ❌ {reason}")

    # 最終結論
    print(f"\n{'='*80}")
    print("最終結論")
    print(f"{'='*80}\n")

    if len(game_groups) == 1:
        print("🎉 すべてのリプレイファイルは同じゲーム（対戦）のものです！")

        # プレイヤーリストを表示
        all_players = set()
        for replay in replays:
            all_players.update(replay['players'])

        print(f"\n参加プレイヤー（合計{len(all_players)}人）:")
        for name, ship_id in sorted(all_players, key=lambda x: x[0]):
            print(f"  - {name} (Ship ID: {ship_id})")

    else:
        print(f"⚠️  {len(game_groups)}つの異なるゲームが検出されました")

        for i, (game_id, group) in enumerate(game_groups.items(), 1):
            print(f"\nゲーム {i}:")
            for replay in group:
                print(f"  - {replay['name']}")

if __name__ == '__main__':
    if len(sys.argv) < 3:
        print(__doc__)
        print("\n例:")
        print("  python3 scripts/check_same_game.py player1.wowsreplay player2.wowsreplay")
        print("  python3 scripts/check_same_game.py replays/*.wowsreplay")
        sys.exit(1)

    replay_paths = [Path(arg) for arg in sys.argv[1:]]
    analyze_replays(replay_paths)
