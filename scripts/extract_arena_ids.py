#!/usr/bin/env python3
"""
リプレイファイルからarenaUniqueIDを抽出するツール

使用方法:
    python3 scripts/extract_arena_ids.py <replay1.wowsreplay> [replay2.wowsreplay ...]
    python3 scripts/extract_arena_ids.py data/replays/14.11.0.0/*.wowsreplay
"""

import sys
import csv
from pathlib import Path
from datetime import datetime

# replays_unpackライブラリのパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent / 'replays_unpack_upstream'))

from replay_unpack.replay_reader import ReplayReader
from replay_unpack.clients.wows.network.packets import BattleStats
from replay_unpack.clients.wows.player import ReplayPlayer as WoWSReplayPlayer


class ArenaIDExtractor(WoWSReplayPlayer):
    """arenaUniqueIDを抽出するカスタムReplayPlayer"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.battle_results = None

    def _process_packet(self, time, packet):
        """BattleStatsパケットをキャプチャ"""
        if isinstance(packet, BattleStats):
            self.battle_results = packet.serverData

        super()._process_packet(time, packet)


def extract_arena_id(replay_path: Path) -> dict:
    """リプレイファイルからarenaUniqueIDと基本情報を抽出"""

    try:
        # リプレイファイルを読み込み
        reader = ReplayReader(str(replay_path))
        replay = reader.get_replay_data()

        # メタデータ
        metadata = replay.engine_data

        # バージョン
        version = metadata.get('clientVersionFromXml', '').replace(' ', '').split(',')

        # arenaUniqueID抽出プレイヤーを作成
        extractor = ArenaIDExtractor(version)

        # リプレイを再生
        extractor.play(replay.decrypted_data, strict_mode=False)

        # 結果を返す
        result = {
            'file': replay_path.name,
            'player': metadata.get('playerName', 'Unknown'),
            'date': metadata.get('dateTime', 'Unknown'),
            'map': metadata.get('mapDisplayName', 'Unknown'),
            'game_type': metadata.get('matchGroup', 'Unknown'),
            'arena_id': None,
            'status': 'success'
        }

        if extractor.battle_results:
            result['arena_id'] = extractor.battle_results.get('arenaUniqueID')

        return result

    except Exception as e:
        return {
            'file': replay_path.name,
            'player': 'Error',
            'date': 'Error',
            'map': 'Error',
            'game_type': 'Error',
            'arena_id': None,
            'status': f'error: {e}'
        }


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n例:")
        print("  python3 scripts/extract_arena_ids.py data/replays/14.11.0.0/*.wowsreplay")
        print("  python3 scripts/extract_arena_ids.py minimap_renderer/replays/*.wowsreplay")
        sys.exit(1)

    replay_paths = [Path(arg) for arg in sys.argv[1:]]

    print(f"arenaUniqueID抽出ツール")
    print(f"{'='*80}\n")
    print(f"処理対象: {len(replay_paths)}個のリプレイファイル\n")

    # 各リプレイを処理
    results = []
    for i, replay_path in enumerate(replay_paths, 1):
        if not replay_path.exists():
            print(f"[{i}/{len(replay_paths)}] ⚠️  ファイルが見つかりません: {replay_path.name}")
            continue

        print(f"[{i}/{len(replay_paths)}] 処理中: {replay_path.name}...", end=" ")

        result = extract_arena_id(replay_path)
        results.append(result)

        if result['status'] == 'success':
            if result['arena_id']:
                print(f"✅ {result['arena_id']}")
            else:
                print(f"⚠️  arenaUniqueIDなし")
        else:
            print(f"❌ {result['status']}")

    # 結果をまとめて表示
    print(f"\n{'='*80}")
    print("抽出結果")
    print(f"{'='*80}\n")

    # テーブル形式で表示
    print(f"{'ファイル名':<50} {'Arena ID':<20} {'日時':<20}")
    print("-" * 90)

    for r in results:
        arena_id_str = str(r['arena_id']) if r['arena_id'] else 'N/A'
        print(f"{r['file']:<50} {arena_id_str:<20} {r['date']:<20}")

    # 統計情報
    print(f"\n{'='*80}")
    print("統計")
    print(f"{'='*80}\n")

    total = len(results)
    success = len([r for r in results if r['arena_id'] is not None])
    unique_arenas = len(set(r['arena_id'] for r in results if r['arena_id'] is not None))

    print(f"総リプレイ数: {total}")
    print(f"arenaUniqueID取得成功: {success}")
    print(f"ユニークなアリーナ数: {unique_arenas}")

    if unique_arenas < success:
        print(f"\n⚠️  {success - unique_arenas}個の重複ゲームが検出されました")

        # 重複を探す
        arena_groups = {}
        for r in results:
            if r['arena_id']:
                arena_id = r['arena_id']
                if arena_id not in arena_groups:
                    arena_groups[arena_id] = []
                arena_groups[arena_id].append(r)

        duplicates = {aid: files for aid, files in arena_groups.items() if len(files) > 1}

        if duplicates:
            print(f"\n同じゲームのリプレイ:")
            for arena_id, files in duplicates.items():
                print(f"\n  Arena ID: {arena_id}")
                for f in files:
                    print(f"    - {f['file']}")

    # CSV出力オプション
    if '--csv' in sys.argv:
        csv_path = Path('arena_ids.csv')
        with open(csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=['file', 'player', 'date', 'map', 'game_type', 'arena_id', 'status'])
            writer.writeheader()
            writer.writerows(results)
        print(f"\n✅ CSV出力: {csv_path}")

    # Arena IDのみのリスト出力オプション
    if '--list' in sys.argv:
        print(f"\n{'='*80}")
        print("Arena ID リスト")
        print(f"{'='*80}\n")
        for r in results:
            if r['arena_id']:
                print(r['arena_id'])


if __name__ == '__main__':
    main()
