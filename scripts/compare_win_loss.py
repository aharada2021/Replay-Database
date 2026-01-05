#!/usr/bin/env python3
"""
複数のリプレイファイルでprivateDataList[4]の値を比較し、勝敗判定フィールドを特定する

使用方法:
    python3 scripts/compare_win_loss.py <replay1.wowsreplay> <replay2.wowsreplay> ...

例:
    # 複数のリプレイを比較
    python3 scripts/compare_win_loss.py replays/*.wowsreplay

    # 勝利と敗北のリプレイを明示的に比較
    python3 scripts/compare_win_loss.py \
        replays/victory1.wowsreplay \
        replays/victory2.wowsreplay \
        replays/defeat1.wowsreplay \
        replays/defeat2.wowsreplay
"""

import sys
import json
from pathlib import Path

# replays_unpackライブラリのパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent / 'replays_unpack_upstream'))

from replay_unpack.replay_reader import ReplayReader
from replay_unpack.clients.wows.network.packets import BattleStats
from replay_unpack.clients.wows.player import ReplayPlayer as WoWSReplayPlayer


class BattleResultExtractor(WoWSReplayPlayer):
    """バトル結果を抽出するカスタムReplayPlayer"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.battle_results = None

    def _process_packet(self, time, packet):
        """パケットを処理（BattleStatsパケットをキャプチャ）"""
        if isinstance(packet, BattleStats):
            self.battle_results = packet.serverData

        # 親クラスの処理を呼び出す
        super()._process_packet(time, packet)


def extract_battle_result(replay_path: Path) -> dict:
    """リプレイファイルからバトル結果を抽出"""

    try:
        # リプレイファイルを読み込み
        reader = ReplayReader(str(replay_path))
        replay = reader.get_replay_data()

        # メタデータ
        metadata = replay.engine_data

        # バージョン
        version = metadata.get('clientVersionFromXml', '').replace(' ', '').split(',')

        # バトル結果抽出プレイヤーを作成
        extractor = BattleResultExtractor(version)

        # リプレイを再生
        extractor.play(replay.decrypted_data, strict_mode=False)

        return {
            'metadata': metadata,
            'battle_results': extractor.battle_results
        }

    except Exception as e:
        print(f"⚠️  エラー ({replay_path.name}): {e}")
        return None


def compare_replays(replay_paths: list[Path]):
    """複数のリプレイファイルを比較分析"""

    print(f"\n{'='*80}")
    print(f"勝敗判定フィールドの比較分析")
    print(f"{'='*80}\n")

    print(f"分析対象: {len(replay_paths)}個のリプレイファイル\n")

    # 各リプレイを分析
    results = []
    for i, replay_path in enumerate(replay_paths, 1):
        print(f"[{i}/{len(replay_paths)}] 解析中: {replay_path.name}...", end=" ")

        data = extract_battle_result(replay_path)

        if data and data['battle_results']:
            metadata = data['metadata']
            battle_results = data['battle_results']
            private_data = battle_results.get('privateDataList', [])

            # 主要なフィールドを抽出
            result_info = {
                'file': replay_path.name,
                'player': metadata.get('playerName', 'Unknown'),
                'map': metadata.get('mapDisplayName', 'Unknown'),
                'game_type': metadata.get('matchGroup', 'Unknown'),
                'date': metadata.get('dateTime', 'Unknown'),

                # 勝敗候補フィールド
                'private_4': private_data[4] if len(private_data) > 4 else None,
                'private_5': private_data[5] if len(private_data) > 5 else None,
                'private_6': private_data[6] if len(private_data) > 6 else None,

                # 統計情報
                'exp': private_data[7][0] if len(private_data) > 7 and isinstance(private_data[7], list) else None,
                'exp_array': private_data[7] if len(private_data) > 7 else None,
            }

            results.append(result_info)
            print("✅")
        else:
            print("❌ バトル結果なし")

    if not results:
        print("\n⚠️  分析可能なリプレイが見つかりませんでした")
        return

    # 結果を表示
    print(f"\n{'='*80}")
    print("分析結果")
    print(f"{'='*80}\n")

    # テーブル形式で表示
    print(f"{'ファイル名':<30} {'プレイヤー':<15} {'[4]':>5} {'[5]':>5} {'[6]':>8} {'経験値':>8}")
    print("-" * 80)

    for r in results:
        print(f"{r['file']:<30} {r['player']:<15} {r['private_4']:>5} {r['private_5']:>5} {r['private_6']:>8} {r['exp']:>8}")

    # privateDataList[4]の値ごとにグループ化
    print(f"\n{'='*80}")
    print("privateDataList[4] の値による分類")
    print(f"{'='*80}\n")

    grouped = {}
    for r in results:
        value = r['private_4']
        if value not in grouped:
            grouped[value] = []
        grouped[value].append(r)

    for value, items in sorted(grouped.items()):
        print(f"📊 値 = {value} ({len(items)}個のリプレイ)")

        # 統計情報
        avg_exp = sum(r['exp'] for r in items if r['exp']) / len(items) if items else 0
        avg_kills = sum(r['private_5'] for r in items if r['private_5']) / len(items) if items else 0

        print(f"   平均経験値: {avg_exp:.0f}")
        print(f"   平均撃沈数: {avg_kills:.1f}")
        print(f"   サンプル:")

        for r in items[:3]:  # 最初の3つを表示
            print(f"     - {r['file']}: {r['player']} @ {r['map']}")

        if len(items) > 3:
            print(f"     ... 他 {len(items) - 3}個")
        print()

    # 推測
    print(f"{'='*80}")
    print("🎯 勝敗判定の推測")
    print(f"{'='*80}\n")

    if len(grouped) == 2:
        # 2つの値がある場合
        values = sorted(grouped.keys())
        group1 = grouped[values[0]]
        group2 = grouped[values[1]]

        avg_exp1 = sum(r['exp'] for r in group1 if r['exp']) / len(group1)
        avg_exp2 = sum(r['exp'] for r in group2 if r['exp']) / len(group2)

        print(f"privateDataList[4] に2つの異なる値が見つかりました:")
        print(f"  値 {values[0]}: {len(group1)}個のリプレイ（平均経験値: {avg_exp1:.0f}）")
        print(f"  値 {values[1]}: {len(group2)}個のリプレイ（平均経験値: {avg_exp2:.0f}）")
        print()

        if avg_exp1 > avg_exp2:
            print(f"推測: 値 {values[0]} = 勝利, 値 {values[1]} = 敗北")
            print(f"（経験値が高い方を勝利と推測）")
        else:
            print(f"推測: 値 {values[0]} = 敗北, 値 {values[1]} = 勝利")
            print(f"（経験値が高い方を勝利と推測）")

    elif len(grouped) == 3:
        print("privateDataList[4] に3つの異なる値が見つかりました:")
        print("可能性: 勝利 / 敗北 / 引き分け")

    else:
        print(f"⚠️  予想外のパターン: {len(grouped)}個の異なる値")

    # 詳細情報をJSONで出力
    print(f"\n{'='*80}")
    print("詳細データ（JSON）")
    print(f"{'='*80}\n")

    # 最初の1つだけprivateDataListを完全表示
    if results:
        print(f"サンプル: {results[0]['file']}")
        print(f"privateDataList の内容:")

        data = extract_battle_result(Path(results[0]['file']))
        if data and data['battle_results']:
            private_data = data['battle_results'].get('privateDataList', [])

            for i, value in enumerate(private_data[:20]):  # 最初の20要素
                value_str = str(value)[:100] if not isinstance(value, (dict, list)) else f"{type(value).__name__}({len(value)} items)"
                print(f"  [{i}] = {value_str}")

            if len(private_data) > 20:
                print(f"  ... 他 {len(private_data) - 20}個の要素")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        print("\n⚠️  少なくとも2つのリプレイファイルが必要です")
        sys.exit(1)

    replay_paths = [Path(arg) for arg in sys.argv[1:]]

    # 存在確認
    valid_paths = []
    for path in replay_paths:
        if path.exists():
            valid_paths.append(path)
        else:
            print(f"⚠️  ファイルが見つかりません: {path}")

    if len(valid_paths) < 2:
        print("\n❌ 有効なリプレイファイルが2つ未満です")
        sys.exit(1)

    compare_replays(valid_paths)


if __name__ == '__main__':
    main()
