# BattleStats パーサー利用ガイド

## 概要

`src/utils/battlestats_parser.py`は、WoWSリプレイファイルの`BattleStats`パケットから各プレイヤーの詳細統計を抽出するユーティリティです。

## 抽出可能な統計データ

以下の11種類の統計値が抽出できます:

| 項目 | 説明 | データ型 |
|------|------|---------|
| `player_name` | プレイヤー名 | str |
| `clan_tag` | クランタグ | str |
| `damage` | 与ダメージ | int |
| `received_damage` | 被ダメージ | int |
| `spotting_damage` | 偵察ダメージ | int |
| `potential_damage` | 潜在ダメージ | int |
| `kills` | 撃沈数 | int |
| `hits` | 命中数 | int |
| `fires` | 火災発生数 | int |
| `floods` | 浸水発生数 | int |
| `base_xp` | 基礎経験値 | int |

## 基本的な使い方

### 1. BattleStatsパケットの抽出

まず、リプレイファイルから`BattleStats`パケットを抽出します:

```bash
python3 scripts/extract_damage_stats.py <replay.wowsreplay>
```

これにより、`<replay>_battlestats.json` が生成されます。

### 2. 統計データのパース

生成されたJSONファイルをパースします:

```bash
python3 src/utils/battlestats_parser.py <replay>_battlestats.json
```

**出力例**:
```
全プレイヤーの統計 (14名):

bomuhei001                     | ダメージ:  122,918 | 撃沈: 2
Noumi_Kudryavka_Wafu           | ダメージ:   97,113 | 撃沈: 2
MCTK                           | ダメージ:   90,089 | 撃沈: 2
_meteor0090                    | ダメージ:   57,320 | 撃沈: 2
...

詳細（トッププレイヤー）:
プレイヤー: XXXXX
与ダメージ: 122,918
被ダメージ: 2,838
偵察ダメージ: 0
潜在ダメージ: 130,500
撃沈数: 2
命中数: 0
火災: 4 / 浸水: 0
基礎経験値: 2,500
```

## Pythonコードでの利用

### リプレイファイルから直接抽出

```python
import sys
sys.path.insert(0, 'replays_unpack_upstream')

from replay_unpack.replay_reader import ReplayReader
from replay_unpack.clients.wows.network.packets import BattleStats
from replay_unpack.clients.wows.player import ReplayPlayer as WoWSReplayPlayer
from src.utils.battlestats_parser import BattleStatsParser

# カスタムReplayPlayer
class StatsExtractor(WoWSReplayPlayer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.battle_results = None

    def _process_packet(self, time, packet):
        if isinstance(packet, BattleStats):
            self.battle_results = packet.serverData
        super()._process_packet(time, packet)

# リプレイ読み込み
reader = ReplayReader("replay.wowsreplay")
replay = reader.get_replay_data()
version = replay.engine_data.get('clientVersionFromXml', '').replace(' ', '').split(',')

# パケット抽出
extractor = StatsExtractor(version)
extractor.play(replay.decrypted_data, strict_mode=False)

# 統計データをパース
players_public_info = extractor.battle_results.get('playersPublicInfo', {})
all_stats = BattleStatsParser.parse_all_players(players_public_info)

# 表示
for player_id, stats in all_stats.items():
    print(f"{stats['player_name']}: {stats['damage']:,} damage")
```

### JSONファイルから読み込み

```python
import json
from src.utils.battlestats_parser import BattleStatsParser

# BattleStatsデータを読み込み
with open('replay_battlestats.json', 'r', encoding='utf-8') as f:
    battlestats = json.load(f)

# パース
players_public_info = battlestats.get('playersPublicInfo', {})
all_stats = BattleStatsParser.parse_all_players(players_public_info)

# 特定プレイヤーの統計を取得
for player_id, stats in all_stats.items():
    if stats['player_name'] == '_meteor0090':
        print(BattleStatsParser.format_stats_for_display(stats))
        break
```

### DynamoDB保存用フォーマット

```python
from src.utils.battlestats_parser import BattleStatsParser

# 統計を取得
stats = BattleStatsParser.parse_player_stats(player_data)

# DynamoDB用にフォーマット
dynamodb_item = BattleStatsParser.to_dynamodb_format(stats)

# DynamoDBに保存
import boto3
dynamodb = boto3.resource('dynamodb')
table = dynamodb.Table('wows-replays-dev')

table.update_item(
    Key={
        'arenaUniqueID': arena_id,
        'playerID': player_id
    },
    UpdateExpression='SET damage = :d, receivedDamage = :r, kills = :k',
    ExpressionAttributeValues={
        ':d': dynamodb_item['damage'],
        ':r': dynamodb_item['receivedDamage'],
        ':k': dynamodb_item['kills'],
    }
)
```

## Lambda関数での利用例

### battle_result_extractor_handlerでの統合

```python
# src/battle_result_extractor_handler.py

from utils.battlestats_parser import BattleStatsParser

def handle(event, context):
    # ... (既存のBattleStats抽出処理)

    if battle_results:
        players_public_info = battle_results.get('playersPublicInfo', {})

        # 全プレイヤーの統計を抽出
        all_stats = BattleStatsParser.parse_all_players(players_public_info)

        # 自分のプレイヤー統計を取得
        own_stats = None
        for player_id, stats in all_stats.items():
            if stats['player_name'] == metadata.get('playerName'):
                own_stats = stats
                break

        # DynamoDBに保存
        if own_stats:
            table.update_item(
                Key={
                    'arenaUniqueID': arena_unique_id,
                    'playerID': player_id
                },
                UpdateExpression='''
                    SET damage = :damage,
                        receivedDamage = :received,
                        spottingDamage = :spotting,
                        potentialDamage = :potential,
                        kills = :kills,
                        hits = :hits,
                        fires = :fires,
                        floods = :floods,
                        baseXP = :xp
                ''',
                ExpressionAttributeValues={
                    ':damage': own_stats['damage'],
                    ':received': own_stats['received_damage'],
                    ':spotting': own_stats['spotting_damage'],
                    ':potential': own_stats['potential_damage'],
                    ':kills': own_stats['kills'],
                    ':hits': own_stats['hits'],
                    ':fires': own_stats['fires'],
                    ':floods': own_stats['floods'],
                    ':xp': own_stats['base_xp'],
                }
            )
```

## APIクラス

### BattleStatsParser

#### parse_player_stats(player_data: List[Any]) -> Dict[str, Any]

単一プレイヤーの配列データから統計を抽出します。

**引数**:
- `player_data`: playersPublicInfoの配列データ（506要素）

**返り値**:
- プレイヤー統計の辞書

**例外**:
- `ValueError`: 配列が不正な場合

#### parse_all_players(players_public_info: Dict[str, List[Any]]) -> Dict[str, Dict[str, Any]]

全プレイヤーの統計を抽出します。

**引数**:
- `players_public_info`: BattleStatsのplayersPublicInfo辞書

**返り値**:
- プレイヤーID -> 統計情報のマッピング

#### format_stats_for_display(stats: Dict[str, Any]) -> str

統計を人間が読める形式にフォーマットします。

**引数**:
- `stats`: プレイヤー統計辞書

**返り値**:
- フォーマット済み文字列

#### to_dynamodb_format(stats: Dict[str, Any]) -> Dict[str, Any]

DynamoDB保存用にフォーマットします（Noneをデフォルト値に変換）。

**引数**:
- `stats`: プレイヤー統計辞書

**返り値**:
- DynamoDB保存用の辞書

## 注意事項

### バージョン依存性

このパーサーは **クライアントバージョン 14.11.0** でのみ検証済みです。

- 配列インデックスはゲームバージョンによって変わる可能性があります
- 新しいバージョンでは `scripts/analyze_battlestats_indices.py` で再検証が必要です

### データの信頼性

- 一部の統計（kills, firesなど）は複数のインデックスに重複して存在します
- パーサーは最も確実性の高いインデックスを使用しています

### データ型

- `potential_damage` は元データでは `float` 型ですが、自動的に `int` に変換されます
- DynamoDB保存時は `Decimal` 型への変換も検討してください

## トラブルシューティング

### ValueError: Invalid player_data

配列の長さが430要素未満の場合に発生します。

**原因**:
- リプレイファイルが不完全（途中で終了）
- 対応していないゲームバージョン

**解決策**:
- 完全なリプレイファイルを使用する
- バージョン番号を確認する

### 統計値がすべて0またはNone

**原因**:
- BattleStatsパケットが見つからなかった
- strict_mode=Trueで解析エラーが発生した

**解決策**:
- `strict_mode=False` で再試行
- リプレイファイルが戦闘終了まで記録されているか確認

## 関連ドキュメント

- [配列インデックスマッピング](./battlestats_array_mapping.md) - 詳細なインデックス定義
- [ダメージ抽出レポート](./damage_extraction_report.md) - 実装方法の詳細
- [インデックス解析ツール](../scripts/analyze_battlestats_indices.py) - 新バージョンでの再検証用

## 更新履歴

- **2026-01-06**: 初版作成
  - 14.11.0での検証完了
  - 11種類の統計値をサポート
