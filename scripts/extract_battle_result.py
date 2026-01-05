#!/usr/bin/env python3
"""
リプレイファイルからバトル結果（勝敗情報）を抽出するツール

使用方法:
    python3 scripts/extract_battle_result.py <replay.wowsreplay>
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
            print(f"\n✅ BattleStatsパケットを発見！")
            self.battle_results = packet.serverData

        # 親クラスの処理を呼び出す
        super()._process_packet(time, packet)


def extract_battle_result(replay_path: Path):
    """リプレイファイルからバトル結果を抽出"""

    print(f"\n{'='*80}")
    print(f"リプレイファイル解析: {replay_path.name}")
    print(f"{'='*80}\n")

    # リプレイファイルを読み込み
    reader = ReplayReader(str(replay_path))
    replay = reader.get_replay_data()

    # メタデータから基本情報を取得
    metadata = replay.engine_data
    player_name = metadata.get('playerName', 'Unknown')
    player_id = metadata.get('playerID', -1)
    map_name = metadata.get('mapDisplayName', 'Unknown')

    print(f"📝 基本情報:")
    print(f"   プレイヤー: {player_name} (ID: {player_id})")
    print(f"   マップ: {map_name}")
    print(f"   日時: {metadata.get('dateTime', 'Unknown')}")
    print(f"   ゲームタイプ: {metadata.get('matchGroup', 'Unknown')}")

    # バトル結果抽出プレイヤーを作成
    version = metadata.get('clientVersionFromXml', '').replace(' ', '').split(',')
    print(f"\n🔍 バイナリデータを解析中...")
    print(f"   クライアントバージョン: {'.'.join(version)}")

    extractor = BattleResultExtractor(version)

    try:
        # リプレイを再生してBattleStatsパケットを探す
        extractor.play(replay.decrypted_data, strict_mode=False)
    except Exception as e:
        print(f"\n⚠️  リプレイ再生中にエラー: {e}")

    # バトル結果を表示
    print(f"\n{'='*80}")
    print("バトル結果")
    print(f"{'='*80}\n")

    if extractor.battle_results:
        print("✅ バトル結果を取得しました！\n")

        # JSON形式で整形して表示
        print("📊 完全なバトル結果データ:")
        print(json.dumps(extractor.battle_results, indent=2, ensure_ascii=False))

        # 勝敗情報を探す
        print(f"\n{'='*80}")
        print("🎯 勝敗情報の分析")
        print(f"{'='*80}\n")

        # 一般的な勝敗フィールドを探す
        win_loss_fields = []

        def search_dict(d, prefix=''):
            """ネストされた辞書から勝敗関連フィールドを再帰的に探す"""
            for key, value in d.items():
                full_key = f"{prefix}.{key}" if prefix else key

                # 勝敗関連キーワード
                keywords = ['win', 'winner', 'victory', 'defeat', 'loss', 'result', 'team']
                if any(kw in key.lower() for kw in keywords):
                    win_loss_fields.append((full_key, value))

                # ネストされた辞書を再帰的に探索
                if isinstance(value, dict):
                    search_dict(value, full_key)

        search_dict(extractor.battle_results)

        if win_loss_fields:
            print("勝敗に関連するフィールド:")
            for key, value in win_loss_fields:
                # 値が大きすぎる場合は短縮
                if isinstance(value, (dict, list)):
                    value_str = f"{type(value).__name__}({len(value)} items)"
                else:
                    value_str = str(value)[:100]
                print(f"  {key:40s} = {value_str}")
        else:
            print("⚠️  明示的な勝敗フィールドが見つかりませんでした")

        # プレイヤー情報から勝敗を推測
        print(f"\n{'='*80}")
        print("👥 プレイヤー別の統計情報")
        print(f"{'='*80}\n")

        # players や vehicles フィールドを探す
        if 'players' in extractor.battle_results:
            players = extractor.battle_results['players']
            print(f"プレイヤー数: {len(players)}")

            # 自分のプレイヤーを探す
            for p_id, p_data in players.items():
                if isinstance(p_data, dict):
                    # 名前またはIDで自分を特定
                    if p_data.get('name') == player_name or str(player_id) == str(p_id):
                        print(f"\n🎯 自分の結果 ({player_name}):")
                        for key, value in sorted(p_data.items()):
                            print(f"  {key:30s} = {value}")
                        break

    else:
        print("❌ バトル結果を取得できませんでした")
        print("\n可能性:")
        print("  - リプレイが途中で終わっている（戦闘が完了していない）")
        print("  - replays_unpackライブラリが対応していないバージョン")
        print("  - バトル結果がこのリプレイファイルに含まれていない")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n例:")
        print("  python3 scripts/extract_battle_result.py minimap_renderer/replays/146.wowsreplay")
        sys.exit(1)

    replay_path = Path(sys.argv[1])

    if not replay_path.exists():
        print(f"❌ ファイルが見つかりません: {replay_path}")
        sys.exit(1)

    extract_battle_result(replay_path)


if __name__ == '__main__':
    main()
