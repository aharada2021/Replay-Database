# リプレイファイルからのダメージデータ抽出 - 検証レポート

## 概要

`replays_unpack_upstream` ライブラリを使用して、WoWSリプレイファイルから各味方プレイヤーのダメージ量と被ダメージ量を抽出できるかを検証しました。

## 検証環境

- **パーサー**: replays_unpack_upstream (Python実装)
- **対象バージョン**: 14.11.0
- **テストファイル**: 複数のリプレイファイル（data/replays/14.11.0.0/配下）

## 検証結果

### ✅ 抽出可能なダメージデータ

以下のダメージ統計データが抽出可能であることを確認しました:

#### 1. BattleStatsパケットから（最終結果）

`BattleStats`パケットには、試合終了時の最終統計が含まれています。ただし、データ構造は以下の特徴があります:

- **構造**: 位置ベースの配列形式（フィールド名なし）
- **アクセス**: `playersPublicInfo` 辞書経由
- **フォーマット**: `{player_id: [data1, data2, data3, ...]}`

**利点**:
- 試合終了後の確定データ
- すべてのプレイヤー分のデータを一度に取得可能

**欠点**:
- 配列のインデックス位置がゲームバージョンによって変わる可能性
- ドキュメント化されていない
- パース処理が複雑

#### 2. EntityMethodパケットから（リアルタイム）

リプレイ再生中に発生する `receiveDamageStat` メソッド呼び出しを監視することで、以下のダメージ統計を抽出できます:

| 統計種類 | 説明 |
|---------|------|
| **DAMAGE** | プレイヤーが与えたダメージ |
| **POTENTIAL** | 潜在ダメージ（受けたがブロック/回避したダメージ） |
| **SPOTTING** | 偵察アシストダメージ |

**利点**:
- リアルタイムでダメージ推移を追跡可能
- minimap_rendererで実装済み
- ダメージタイプごとに分離されている

**欠点**:
- リプレイ全体を再生する必要がある
- パケット処理のオーバーヘッド

## 実装例

### BattleStatsパケットからの抽出（簡易版）

```python
from replay_unpack.replay_reader import ReplayReader
from replay_unpack.clients.wows.network.packets import BattleStats
from replay_unpack.clients.wows.player import ReplayPlayer as WoWSReplayPlayer

class DamageExtractor(WoWSReplayPlayer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.battle_results = None

    def _process_packet(self, time, packet):
        if isinstance(packet, BattleStats):
            self.battle_results = packet.serverData
        super()._process_packet(time, packet)

# 使用例
reader = ReplayReader("replay.wowsreplay")
replay = reader.get_replay_data()
version = replay.engine_data.get('clientVersionFromXml', '').replace(' ', '').split(',')

extractor = DamageExtractor(version)
extractor.play(replay.decrypted_data, strict_mode=False)

# playersPublicInfo にプレイヤー統計が含まれる
players_info = extractor.battle_results.get('playersPublicInfo', {})
```

### EntityMethodパケットからの抽出（高度版）

minimap_rendererの実装を参考:

```python
# minimap_renderer/src/replay_unpack/clients/wows/versions/14_11_0/battle_controller.py

def receiveDamageStat(self, avatar, blob):
    """ダメージ統計を受信"""
    normalized_map = {}

    for (type_, bool_), value in restricted_loads(blob).items():
        if (name := DamageStatsType.names[bool_]) not in normalized_map:
            normalized_map[name] = {}

        normalized_map[name].setdefault(type_, {})
        normalized_map[name][type_] = tuple(value)

    for name, normalized in normalized_map.items():
        self._damage_maps[name].update(normalized)
```

## 推奨アプローチ

### 現在のプロジェクトでの利用方法

1. **既存の実装を活用**: minimap_rendererが既にダメージデータ抽出機能を実装しています

2. **BattleStatsベースの実装**（シンプル）:
   - 試合終了時の最終統計のみが必要な場合
   - データベース保存用の軽量な処理

3. **EntityMethodベースの実装**（高度）:
   - ダメージ推移をグラフ表示したい場合
   - 動画生成と連携する場合

## BattleStatsデータ構造の課題

`playersPublicInfo` の配列データは位置ベースであり、各インデックスが何を意味するかが明示されていません。

**調査したサンプルデータ**:
```json
{
  "-268494432": [
    -268494432,      // [0] player_id
    ":Lee:",         // [1] name
    0,               // [2] ?
    "",              // [3] clan_tag?
    ...              // 以降200項目以上の配列
  ]
}
```

この構造を完全に解析するには:
- 各バージョンごとのリバースエンジニアリング
- または、Wargaming公式のドキュメント

が必要です。

## 検証用スクリプト

`scripts/extract_damage_stats.py` を作成し、以下の機能を実装:

- リプレイファイルからBattleStatsパケットを抽出
- playersPublicInfoの構造を解析
- JSON形式で詳細データを出力

**使用方法**:
```bash
python3 scripts/extract_damage_stats.py data/replays/14.11.0.0/replay.wowsreplay
```

**出力例**:
- コンソールにプレイヤー一覧表示
- `*_battlestats.json` に詳細データを保存

## 結論

### ✅ 可能なこと

1. **BattleStatsパケット**から最終統計を抽出
   - プレイヤー名、艦艇名、チームIDなどは確実に取得可能
   - ダメージデータも含まれているが、配列インデックス位置の特定が必要

2. **EntityMethodパケット**（minimap_renderer実装）からリアルタイムダメージ統計を抽出
   - DAMAGE（与ダメージ）
   - POTENTIAL（潜在ダメージ）
   - SPOTTING（偵察ダメージ）

### ⚠️ 制限事項

1. BattleStatsの配列データ構造はドキュメント化されていない
2. 被ダメージ量は明示的なフィールドとして確認できなかった
   - 間接的に算出可能（初期HP - 残HP）
   - または個別のダメージイベントパケットから集計

### 📝 推奨事項

**プロジェクトでの実装**:

1. **Phase 3 (Web UI) での表示用**:
   - BattleStatsから基本情報（プレイヤー名、艦艇、チーム）を抽出
   - EntityMethodベースの実装は見送り（複雑度が高い）
   - minimap_rendererの既存実装を活用した動画生成で代替

2. **将来的な拡張**:
   - ダメージグラフ表示が必要になったら、minimap_rendererのロジックを再利用
   - BattleStatsの配列構造を完全解析（時間がかかる）

## 関連ファイル

- `scripts/extract_damage_stats.py` - 検証用スクリプト
- `minimap_renderer/src/replay_unpack/clients/wows/versions/14_11_0/battle_controller.py` - 実装参考
- `minimap_renderer/src/renderer/layers/counter.py` - ダメージ表示実装

## 補足: 既存プロジェクトでの対応状況

現在のプロジェクト（wows-reploy-classfication-bot）では:

- **メタデータ抽出**: ✅ 実装済み（プレイヤー、マップ、日時など）
- **勝敗判定**: ✅ 実装済み（BattleStatsパケットから）
- **ダメージ統計**: ❌ 未実装 → 今回の検証で実装方法を確認

次のステップとして、必要に応じてダメージデータをDynamoDBスキーマに追加することを検討できます。
