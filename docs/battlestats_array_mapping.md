# BattleStats playersPublicInfo 配列マッピング

## 概要

WoWSリプレイファイルの`BattleStats`パケットに含まれる`playersPublicInfo`は、各プレイヤーのIDをキーとした辞書で、値は**位置ベースの配列**（506要素）です。

このドキュメントは、クライアントバージョン **14.11.0** における配列インデックスと統計値の対応関係をまとめたものです。

## 検証方法

### 使用したリプレイファイル
- ファイル名: `20260103_232822_PZSD109-Chung-Mu_19_OC_prey.wowsreplay`
- プレイヤー: `_meteor0090`
- クライアントバージョン: 14.11.0.11189791

### 既知の値（ゲーム内統計）
| 統計項目 | 値 |
|---------|-----|
| Actual Damage | 57,320 |
| Received Damage | 3,630 |
| Spotting Damage | 43,341 |
| Potential Damage | 162,450 |
| Hits | 23 |
| Kills | 1 |
| Base XP | 2,500 |
| Fires | 1 |
| Floods | 3 |

### 検証結果

全14名のプレイヤーで一貫してデータが取得できることを確認しました。

## 確定済みインデックスマッピング

**注**: インデックス[5]は全プレイヤーで値が2となっており、killsではありませんでした。正しいkillsのインデックスは[32]です。

### 基本情報 (0-100)

| インデックス | データ型 | 項目名 | 説明 | サンプル値 |
|------------|---------|--------|------|-----------|
| **[0]** | `int` | `player_id` | プレイヤーID（アカウントID） | 2021730053 |
| **[1]** | `str` | `player_name` | プレイヤー名 | "_meteor0090" |
| **[2]** | `int` | `account_db_id` | データベースID? | 2000016598 |
| **[3]** | `str` | `clan_tag` | クランタグ | "OZEKI" |
| **[4]** | `int` | `clan_id` | クランID | 14931616 |
| **[5]** | `int` | `?` | 不明（全プレイヤーで2） | 2 |
| **[6]** | `int` | `?` | 不明（値=1） | 1 |
| **[9]** | `str` | `realm` | サーバーリージョン | "ASIA" |
| **[15]** | `int` | `?` | 不明 | 21300 |
| **[22]** | `int` | `survival_time` | 生存時間（秒）? | 626 |
| **[23]** | `float` | `survival_percentage` | 生存率（%）? | 52.45 |
| **[32]** | `int` | **`kills`** | **撃沈数** | **1** ✅ |
| **[66]** | `int` | **`hits_ap`** | **AP弾命中数** | **0** ✅ |
| **[68]** | `int` | **`hits_he`** | **HE弾命中数（主砲のみ）** | **23** ✅ |
| **[71]** | `int` | **`hits_secondaries`** | **副砲HE弾命中数** | **0** ✅ |
| **[75]** | `int` | **`floods`** | **浸水発生数** | **3** ✅ |
| **[86]** | `int` | **`fires`** | **火災発生数** | **1** ✅ |
| **[87]** | `int` | `?` | 不明（floods関連?） | 3 |

### 主砲・魚雷ダメージ内訳 (155-185)

| インデックス | データ型 | 項目名 | 説明 | サンプル値 |
|------------|---------|--------|------|-----------|
| **[157]** | `int` | **`damage_ap`** | **AP弾ダメージ（主砲）** | **0** ✅ |
| **[159]** | `int` | **`damage_he`** | **HE弾ダメージ（主砲）** | **6,471** ✅ |
| **[162]** | `int` | **`damage_he_secondaries`** | **副砲HE弾ダメージ** | **0** ✅ |
| **[166]** | `int` | **`damage_torps`** | **魚雷ダメージ（通常魚雷）** | **0** ✅ |
| **[167]** | `int` | **`damage_deep_water_torps`** | **深水魚雷ダメージ（パンアジア駆逐艦）** | **41,332** ✅ |
| **[178]** | `int` | **`damage_other`** | **その他ダメージ（主砲AP+副砲AP等の合計）** | **0** ⚠️ |
| **[179]** | `int` | **`damage_fire`** | **火災ダメージ** | **535** ✅ |
| **[180]** | `int` | **`damage_flooding`** | **浸水ダメージ** | **8,982** ✅ |

### ダメージ統計 (200-250)

| インデックス | データ型 | 項目名 | 説明 | サンプル値 |
|------------|---------|--------|------|-----------|
| **[204]** | `int` | **`received_damage`** | **被ダメージ** | **3,630** ✅ |

### 経験値・ダメージ統計 (400-450)

| インデックス | データ型 | 項目名 | 説明 | サンプル値 |
|------------|---------|--------|------|-----------|
| **[406]** | `int` | **`base_xp`** | **基礎経験値** | **2,500** ✅ |
| **[407]** | `int` | **`base_xp_duplicate`** | **基礎経験値（重複）** | **2,500** ✅ |
| **[415]** | `int` | **`spotting_damage`** | **偵察ダメージ** | **43,341** ✅ |
| **[417]** | `float` | `?` | 不明 | 60.00 |
| **[418]** | `float` | `?` | 不明 | 11.00 |
| **[419]** | `float` | **`potential_damage`** | **潜在ダメージ** | **162,450.0** ✅ |
| **[423]** | `float` | `?` | 不明 | 60.00 |
| **[424]** | `float` | `?` | 不明 | 188.00 |
| **[429]** | `int` | **`damage`** | **与ダメージ** | **57,320** ✅ |
| **[432]** | `int` | `?` | 不明（fires関連?） | 1 |

## 使用例

### Pythonでのデータ抽出

```python
import json
from replay_unpack.replay_reader import ReplayReader
from replay_unpack.clients.wows.network.packets import BattleStats
from replay_unpack.clients.wows.player import ReplayPlayer as WoWSReplayPlayer

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

# 解析
extractor = StatsExtractor(version)
extractor.play(replay.decrypted_data, strict_mode=False)

# プレイヤー統計の取得
players_info = extractor.battle_results.get('playersPublicInfo', {})

for player_id, player_data in players_info.items():
    if isinstance(player_data, list) and len(player_data) > 429:
        stats = {
            'player_id': player_data[0],
            'player_name': player_data[1],
            'clan_tag': player_data[3],
            'kills': player_data[5],
            'hits': player_data[68],
            'floods': player_data[75],
            'fires': player_data[86],
            'received_damage': player_data[204],
            'base_xp': player_data[406],
            'spotting_damage': player_data[415],
            'potential_damage': int(player_data[419]),
            'damage': player_data[429],
        }
        print(f"{stats['player_name']}: {stats['damage']:,} damage")
```

### 出力例

```
全プレイヤーの主要統計値:

プレイヤー名                         与ダメ[429]     被ダメ[204]     偵察[415]      潜在[419]      命中[68]   撃沈[5]
--------------------------------------------------------------------------------------------------------------
   JWBMSC                       74,920       40,565       0            644,000.0    20       2
   Liquid_Oxygen_304            9,198        31,488       12,662       343,800.0    9        2
👤 _meteor0090                  57,320       3,630        43,341       162,450.0    23       2
   Oversized_Slime              21,247       16,714       7,095        133,800.0    12       2
   LovEveRv                     29,199       27,541       20,164       430,200.0    17       2
   purominennsu                 63,403       43,468       2,178        1,506,400.0  46       2
   EvolTRx0UC_HivNexusZZ        72,452       12,144       34,698       374,150.0    0        2
   MCTK                         90,089       430          12,720       388,100.0    253      2
   ao09___                      76,625       1,419        5,394        411,500.0    208      2
   TachibanaHikariMywaifu       43,933       46,838       21,674       1,282,400.0  20       2
   bomuhei001                   122,918      2,838        0            130,500.0    0        2
   ClyneLacus                   78,972       12,201       0            526,450.0    38       2
   Noumi_Kudryavka_Wafu         97,113       1,980        14,386       208,800.0    0        2
   wowoshi_chitong              24,571       25,023       16,422       973,700.0    13       2
```

## 未確定・調査中の項目

### スキル情報
- **Skills (21pts, 8skills)**: 配列内で直接的な値が見つからず
- 可能性: `privateDataList` または `commonList` に含まれている
- 継続調査が必要

### その他の統計
以下の統計値も配列内に存在する可能性があります:
- リボン数（各種）
- アチーブメント
- 航空機撃墜数
- 魚雷命中数
- 主砲/副砲の命中率
- 占領ポイント貢献度
- 防衛ポイント貢献度

## 注意事項

### バージョン依存性
- **このマッピングは 14.11.0 でのみ検証済み**
- ゲームバージョンが更新されると配列構造が変わる可能性があります
- 新しいバージョンでは必ず再検証が必要です

### 重複値の扱い
一部の統計（fires, floods, base_xpなど）は複数のインデックスに同じ値が存在します。
- **推奨**: 最も確実性の高いインデックスを使用
  - kills: `[32]`
  - fires: `[86]`
  - floods: `[75]`
  - base_xp: `[406]`

### データ型
- `potential_damage` は `float` 型で保存されている
- 他のダメージ統計は `int` 型
- 使用時は適切な型変換を行うこと

## 関連ファイル

- `scripts/analyze_battlestats_indices.py` - インデックス解析ツール
- `scripts/extract_damage_stats.py` - ダメージ統計抽出ツール
- `docs/damage_extraction_report.md` - ダメージ抽出の詳細レポート

## 更新履歴

- **2026-01-06 (第3版)**: 副砲ダメージとその他ダメージを追加
  - 新たに2個のインデックスを確定:
    - [162] 副砲HE弾ダメージ
    - [178] その他ダメージ（主砲AP+副砲AP等の残差）
  - 合計23個のインデックスを確定（基本11 + 拡張12）
  - 全14名のプレイヤーでダメージ内訳の合計=総ダメージを検証

- **2026-01-06 (第2版)**: ダメージ・命中数内訳を追加
  - エクスポートファイルを使用して詳細なマッピングを実施
  - 新たに10個のインデックスを確定:
    - 命中数内訳: [66] AP弾, [68] HE弾, [71] 副砲
    - ダメージ内訳: [157] AP, [159] HE, [166] 通常魚雷, [167] 深水魚雷, [179] 火災, [180] 浸水
  - 全14名のプレイヤーで検証完了

- **2026-01-06 (初版)**: 基本統計値のマッピング
  - 主要な11個の統計値のインデックスを確定
  - 全14名のプレイヤーで一貫性を確認
  - **修正**: killsのインデックスを[5]→[32]に訂正（実際のゲーム統計と照合）
