#!/usr/bin/env python3
"""
リプレイファイルから各味方プレイヤーのダメージ量・被ダメージ量を抽出するツール

使用方法:
    python3 scripts/extract_damage_stats.py <replay.wowsreplay>
"""

import sys
import json
from pathlib import Path

# replays_unpackライブラリのパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent / 'replays_unpack_upstream'))

from replay_unpack.replay_reader import ReplayReader
from replay_unpack.clients.wows.network.packets import BattleStats
from replay_unpack.clients.wows.player import ReplayPlayer as WoWSReplayPlayer


class DamageStatsExtractor(WoWSReplayPlayer):
    """ダメージ統計を抽出するカスタムReplayPlayer"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.battle_results = None

    def _process_packet(self, time, packet):
        """パケットを処理"""
        # BattleStatsパケット（最終結果）
        if isinstance(packet, BattleStats):
            self.battle_results = packet.serverData

        # 親クラスの処理を呼び出す
        super()._process_packet(time, packet)


def find_player_data_recursive(data, depth=0, max_depth=10):
    """
    ネストされた辞書から 'vehicles' フィールドを再帰的に探索
    """
    if depth > max_depth:
        return None

    if isinstance(data, dict):
        # vehiclesフィールドが見つかった場合
        if 'vehicles' in data:
            return data['vehicles']

        # 他のフィールドを再帰的に探索
        for key, value in data.items():
            result = find_player_data_recursive(value, depth + 1, max_depth)
            if result is not None:
                return result

    elif isinstance(data, list):
        # リストの各要素を探索
        for item in data:
            result = find_player_data_recursive(item, depth + 1, max_depth)
            if result is not None:
                return result

    return None


def extract_damage_stats(replay_path: Path):
    """リプレイファイルからダメージ統計を抽出"""

    print(f"\n{'='*80}")
    print(f"ダメージ統計解析: {replay_path.name}")
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

    # ダメージ統計抽出プレイヤーを作成
    version = metadata.get('clientVersionFromXml', '').replace(' ', '').split(',')
    print(f"\n🔍 リプレイデータを解析中...")
    print(f"   クライアントバージョン: {'.'.join(version)}")

    extractor = DamageStatsExtractor(version)

    try:
        # リプレイを再生してパケットを収集
        extractor.play(replay.decrypted_data, strict_mode=False)
    except Exception as e:
        print(f"\n⚠️  リプレイ再生中にエラー: {e}")

    print(f"\n{'='*80}")
    print("解析結果")
    print(f"{'='*80}\n")

    # BattleStatsからの最終結果
    if extractor.battle_results:
        print("✅ BattleStatsパケットを取得しました\n")

        # vehicles フィールドを再帰的に探索
        print("🔍 プレイヤーデータを探索中...")
        players_data = find_player_data_recursive(extractor.battle_results)

        if players_data:
            print(f"✅ プレイヤーデータを発見: {len(players_data)}名\n")

            # 自分のチームIDを取得
            own_team_id = None
            for p_id, p_data in players_data.items():
                if isinstance(p_data, dict):
                    if str(p_id) == str(player_id) or p_data.get('name') == player_name:
                        own_team_id = p_data.get('teamId')
                        break

            print(f"自チームID: {own_team_id}\n")

            # 味方プレイヤーのダメージ統計を表示
            print(f"{'プレイヤー名':<25} {'艦艇':<30} {'与ダメージ':<12} {'被ダメージ':<12} {'撃沈数':<8}")
            print("-" * 100)

            ally_stats = []

            for p_id, p_data in players_data.items():
                if not isinstance(p_data, dict):
                    continue

                # 味方プレイヤーのみ（自分含む）
                if p_data.get('teamId') == own_team_id:
                    name = p_data.get('name', 'Unknown')
                    ship_name = p_data.get('shipName', 'Unknown')

                    # ダメージ関連の情報を探す
                    damage_dealt = 0
                    damage_received = 0
                    kills = 0

                    # よくあるフィールド名をチェック
                    damage_dealt = (
                        p_data.get('damageDealt', 0) or
                        p_data.get('damage', 0) or
                        p_data.get('totalDamage', 0) or
                        0
                    )

                    damage_received = (
                        p_data.get('damageReceived', 0) or
                        p_data.get('damageTaken', 0) or
                        0
                    )

                    kills = p_data.get('kills', 0) or p_data.get('killsCount', 0) or 0

                    ally_stats.append({
                        'name': name,
                        'ship': ship_name,
                        'damage_dealt': damage_dealt,
                        'damage_received': damage_received,
                        'kills': kills,
                        'is_own': str(p_id) == str(player_id) or name == player_name,
                        'raw_data': p_data
                    })

            # 与ダメージでソート
            ally_stats.sort(key=lambda x: x['damage_dealt'], reverse=True)

            # 表示
            for stat in ally_stats:
                marker = "👤" if stat['is_own'] else "  "
                print(f"{marker} {stat['name']:<23} {stat['ship']:<30} {stat['damage_dealt']:>10,}  {stat['damage_received']:>10,}  {stat['kills']:>6}")

            print()

            # 詳細なフィールドを確認（デバッグ用）
            print(f"\n{'='*80}")
            print("🔍 利用可能なフィールド一覧（サンプルプレイヤー）")
            print(f"{'='*80}\n")

            # 最初の味方プレイヤーのフィールドを表示
            if ally_stats:
                sample_player = ally_stats[0]['raw_data']
                print(f"サンプルプレイヤー: {ally_stats[0]['name']}\n")

                # フィールドをアルファベット順にソート
                for key in sorted(sample_player.keys()):
                    value = sample_player[key]
                    # 大きなデータ構造は省略
                    if isinstance(value, (dict, list)):
                        value_str = f"{type(value).__name__}({len(value)} items)"
                    else:
                        value_str = str(value)
                    print(f"  {key:35s} = {value_str}")

        else:
            print("❌ プレイヤーデータ（vehicles）が見つかりませんでした")

            # BattleStatsの構造を詳しく表示
            print("\n📋 BattleStatsパケットの構造を表示します:")
            print(f"トップレベルのキー: {list(extractor.battle_results.keys())}\n")

            # 各キーの内容を簡単に表示
            for key in extractor.battle_results.keys():
                value = extractor.battle_results[key]
                if isinstance(value, (dict, list)):
                    print(f"  {key:30s} : {type(value).__name__}({len(value)} items)")
                else:
                    value_str = str(value)[:100]
                    print(f"  {key:30s} : {value_str}")

            # より詳細な構造をJSON形式で保存
            output_path = replay_path.parent / f"{replay_path.stem}_battlestats.json"
            print(f"\n詳細な構造を {output_path.name} に保存します...")
            with open(output_path, 'w', encoding='utf-8') as f:
                json.dump(extractor.battle_results, f, indent=2, ensure_ascii=False, default=str)
            print(f"✅ 保存完了: {output_path}")

    else:
        print("❌ BattleStatsパケットが見つかりませんでした")
        print("\n可能性:")
        print("  - リプレイが途中で終わっている（戦闘が完了していない）")
        print("  - replays_unpackライブラリが対応していないバージョン")


def main():
    if len(sys.argv) < 2:
        print(__doc__)
        print("\n例:")
        print("  python3 scripts/extract_damage_stats.py data/replays/14.11.0.0/20251127_210139_PISD710-Alberico-da-Barbiano_50_Gold_harbor.wowsreplay")
        sys.exit(1)

    replay_path = Path(sys.argv[1])

    if not replay_path.exists():
        print(f"❌ ファイルが見つかりません: {replay_path}")
        sys.exit(1)

    extract_damage_stats(replay_path)


if __name__ == '__main__':
    main()
