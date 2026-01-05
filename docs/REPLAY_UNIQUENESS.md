# リプレイファイルの一意性識別ガイド

## 概要

WoWSのリプレイファイル（.wowsreplay）には、同じゲーム（対戦）を識別できるメタデータが含まれています。複数の参加者のリプレイファイルが同じゲームのものかを判定する方法を説明します。

## 調査結果

### リプレイファイルに含まれるメタデータ

各リプレイファイルには、以下のようなJSONメタデータが含まれています：

```json
{
  "dateTime": "09.07.2025 20:32:25",
  "mapName": "spaces/51_Greece",
  "mapDisplayName": "51_Greece",
  "matchGroup": "event",
  "gameType": "EventBattle",
  "gameTypeGameParamId": 4254968752,
  "scenarioConfigId": 421,
  "duration": 720,
  "battleDuration": 720,
  "teamsCount": 2,
  "playersPerTeam": 7,
  "playerName": "JustDodge",
  "playerID": 0,
  "vehicles": [ ... 14人のプレイヤー情報 ... ],
  ...
}
```

### 同じゲームを識別するための推奨フィールド

以下のフィールドの組み合わせで、同じゲームかどうかを判定できます：

#### 🎯 主要な識別子（必須）

1. **`dateTime`** - 対戦開始時刻
   - 形式: `DD.MM.YYYY HH:MM:SS`
   - 例: `09.07.2025 20:32:25`
   - **注意**: 秒単位まで一致する必要があります
   - タイムゾーンの影響を受ける可能性があるため、単独では不十分

2. **`mapName`** - マップ名
   - 形式: `spaces/<map_id>`
   - 例: `spaces/51_Greece`

3. **`matchGroup`** - マッチグループ
   - 例: `clan`, `pvp`, `ranked`, `event`

#### 🔒 補助的な識別子（推奨）

4. **`scenarioConfigId`** - シナリオ設定ID
   - 整数値
   - 例: `421`

5. **`gameTypeGameParamId`** - ゲームタイプパラメータID
   - 整数値
   - 例: `4254968752`

6. **`duration`** または `battleDuration`** - 対戦時間（秒）
   - 例: `720` (12分)

#### 👥 確実な識別（最も信頼性が高い）

7. **`vehicles`** - 参加プレイヤーリスト
   - 全プレイヤーの名前とShip IDのリスト
   - 同じゲームであれば、全プレイヤーが一致します

## 判定アルゴリズム

### 方法1: 複合キーによる判定（推奨）

以下のフィールドを組み合わせた複合キーを作成：

```python
def get_game_identifier(metadata: dict) -> str:
    """リプレイのゲーム識別子を生成"""
    import hashlib

    # 複合キーの要素
    elements = [
        metadata.get('dateTime', ''),
        metadata.get('mapName', ''),
        metadata.get('matchGroup', ''),
        str(metadata.get('scenarioConfigId', '')),
        str(metadata.get('duration', '')),
    ]

    # ハッシュ化して識別子を生成
    key = '|'.join(elements)
    return hashlib.sha256(key.encode()).hexdigest()
```

**使用例:**
```python
# 複数のリプレイファイルを比較
metadata1 = parse_replay_metadata('player1.wowsreplay')
metadata2 = parse_replay_metadata('player2.wowsreplay')

game_id1 = get_game_identifier(metadata1)
game_id2 = get_game_identifier(metadata2)

if game_id1 == game_id2:
    print("同じゲームのリプレイです")
else:
    print("異なるゲームのリプレイです")
```

### 方法2: プレイヤーリストによる判定（最も確実）

参加プレイヤーのセットを比較：

```python
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

# 使用例
players1 = get_player_set(metadata1)
players2 = get_player_set(metadata2)

if players1 == players2:
    print("同じゲームのリプレイです（全プレイヤーが一致）")
else:
    print("異なるゲームのリプレイです")
```

### 方法3: 複合判定（最も堅牢）

両方の方法を組み合わせ：

```python
def is_same_game(metadata1: dict, metadata2: dict) -> bool:
    """2つのリプレイが同じゲームかを判定"""

    # 1. dateTimeチェック（±5秒の誤差を許容）
    dt1 = parse_datetime(metadata1.get('dateTime'))
    dt2 = parse_datetime(metadata2.get('dateTime'))
    if abs((dt1 - dt2).total_seconds()) > 5:
        return False

    # 2. mapNameチェック
    if metadata1.get('mapName') != metadata2.get('mapName'):
        return False

    # 3. matchGroupチェック
    if metadata1.get('matchGroup') != metadata2.get('matchGroup'):
        return False

    # 4. プレイヤーセットチェック
    players1 = get_player_set(metadata1)
    players2 = get_player_set(metadata2)

    # 同じプレイヤーが70%以上一致すれば同じゲーム
    common_players = players1 & players2
    if len(common_players) / max(len(players1), len(players2)) < 0.7:
        return False

    return True
```

## 注意事項

### タイムゾーンの問題

`dateTime`フィールドは、プレイヤーのローカルタイムゾーンで記録されている可能性があります。異なるタイムゾーンのプレイヤーの場合、時刻がずれる可能性があるため、以下の対策が必要です：

- ±数分（推奨: ±5秒〜1分）の誤差を許容する
- 他のフィールド（マップ、プレイヤーリストなど）と組み合わせて判定する

### プレイヤー名の変更

プレイヤーが対戦中に名前を変更することはできないため、`vehicles`の`name`フィールドは信頼できます。

### 推奨される実装

**最も堅牢な方法:**
1. `dateTime` + `mapName` + `matchGroup` の複合キーで初期フィルタリング
2. プレイヤーリストの一致度で最終判定（70%以上の一致）

**軽量な方法:**
- `dateTime` (±5秒) + `mapName` + `scenarioConfigId` の完全一致

## 実装例

完全な実装例は `scripts/investigate_replay_metadata.py` を参照してください。

## ユースケース

### 1. 重複リプレイの除外

同じゲームのリプレイを複数の参加者がアップロードした場合、重複を検出して1つだけ保存する。

### 2. 複数視点の統合

同じゲームの異なるプレイヤーのリプレイを統合して、多視点リプレイを作成する。

### 3. クラン戦の記録管理

クランメンバー全員のリプレイから、同じクラン戦のリプレイをグループ化する。

## メタデータの取得方法

```python
import struct
import json
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
```

## まとめ

✅ **同じゲームの判定は可能です**

以下の組み合わせで高精度に判定できます：
- `dateTime` + `mapName` + `matchGroup` + `scenarioConfigId`
- または、`vehicles`（プレイヤーリスト）の一致度チェック

推奨実装は、複数のフィールドを組み合わせた堅牢な判定アルゴリズムです。
