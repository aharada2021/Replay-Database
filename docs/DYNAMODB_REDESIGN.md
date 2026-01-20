# DynamoDB 再設計ドキュメント

## 概要

アプリケーションの要件に基づき、DynamoDBテーブル構造を再設計する。

### 設計方針

1. **gameType別テーブル分離**: ClanBattle, RankedBattle, RandomBattle, Other
2. **試合単位のデータモデル**: arenaUniqueID をパーティションキーに
3. **RCU最適化**: allPlayersStats を別レコードに分離
4. **Unix timestamp**: 年またぎを考慮し、時刻はUnix timestampで管理
5. **検索用インデックステーブル**: Ship, Player, Clan 別に用意

---

## テーブル一覧

| テーブル名 | 用途 |
|-----------|------|
| `wows-clan-battles-{stage}` | クラン戦データ |
| `wows-ranked-battles-{stage}` | ランク戦データ |
| `wows-random-battles-{stage}` | ランダム戦データ |
| `wows-other-battles-{stage}` | その他の戦闘データ |
| `wows-ship-index-{stage}` | 艦艇検索インデックス |
| `wows-player-index-{stage}` | プレイヤー検索インデックス |
| `wows-clan-index-{stage}` | クラン検索インデックス |
| `wows-sessions-{stage}` | ユーザーセッション |
| `wows-comments-{stage}` | コメント |

---

## 1. バトルテーブル（gameType別）

### テーブル名
- `wows-clan-battles-{stage}`
- `wows-ranked-battles-{stage}`
- `wows-random-battles-{stage}`
- `wows-other-battles-{stage}`

### キースキーマ

| キー | 属性名 | 型 |
|------|--------|-----|
| Partition Key | `arenaUniqueID` | String |
| Sort Key | `recordType` | String |

### recordType の値

| recordType | 説明 | 1試合あたり |
|------------|------|------------|
| `MATCH` | 試合基本情報 | 1件 |
| `STATS` | 全プレイヤー統計 | 1件 |
| `UPLOAD#{playerID}` | アップロード情報 | N件 |

### GSI

#### ListingIndex（ページネーション用）

| 項目 | 値 |
|------|-----|
| Partition Key | `listingKey` (String) |
| Sort Key | `unixTime` (Number) |
| Projection | INCLUDE |
| NonKeyAttributes | arenaUniqueID, dateTime, mapId, mapDisplayName, winLoss, allyMainClanTag, enemyMainClanTag, uploaders, commentCount, dualRendererAvailable |

#### MapIndex（マップ検索用）

| 項目 | 値 |
|------|-----|
| Partition Key | `mapId` (String) |
| Sort Key | `unixTime` (Number) |
| Projection | KEYS_ONLY |

### レコード構造

#### MATCH レコード

```json
{
  "arenaUniqueID": "3487309050689265",
  "recordType": "MATCH",

  "listingKey": "ACTIVE",
  "unixTime": 1737230673,
  "dateTime": "18.01.2026 22:04:33",

  "mapId": "spaces/53_Shoreside",
  "mapDisplayName": "53_Shoreside",
  "clientVersion": "14,11,0,11189791",

  "allyPerspectivePlayerID": 12345,
  "allyPerspectivePlayerName": "ClyneLacus",
  "winLoss": "loss",

  "allyMainClanTag": "OZEKI",
  "enemyMainClanTag": "ANZIO",
  "allies": [
    {"name": "ClyneLacus", "clanTag": "OZEKI", "shipName": "SIBIR", "shipId": 123456}
  ],
  "enemies": [
    {"name": "EnemyPlayer1", "clanTag": "ANZIO", "shipName": "PETROPAVLOVSK", "shipId": 345678}
  ],

  "mp4S3Key": "videos/3487309050689265/tmp.mp4",
  "mp4GeneratedAt": 1737231000,
  "dualRendererAvailable": false,

  "commentCount": 3,

  "uploaders": [
    {"playerID": 12345, "playerName": "ClyneLacus", "team": "ally"}
  ]
}
```

**サイズ目安**: ~2KB

#### STATS レコード

```json
{
  "arenaUniqueID": "3487309050689265",
  "recordType": "STATS",

  "allPlayersStats": [
    {
      "playerName": "ClyneLacus",
      "clanTag": "OZEKI",
      "shipName": "SIBIR",
      "shipId": 123456,
      "shipClass": "Cruiser",
      "team": "ally",
      "damage": 120107,
      "kills": 0,
      "spottingDamage": 34333,
      "potentialDamage": 1261250,
      "receivedDamage": 45000,
      "baseXP": 1500,
      "citadels": 2,
      "fires": 3,
      "floods": 0,
      "crits": 5,
      "damageAP": 80000,
      "damageHE": 20107,
      "damageTorps": 0,
      "damageFire": 15000,
      "damageFlooding": 0,
      "damageOther": 0,
      "damageDeepWaterTorps": 0,
      "damageHESecondaries": 0,
      "hitsAP": 45,
      "hitsHE": 32,
      "hitsSecondaries": 0,
      "receivedDamageAP": 20000,
      "receivedDamageHE": 15000,
      "receivedDamageTorps": 10000,
      "receivedDamageFire": 0,
      "receivedDamageFlood": 0,
      "receivedDamageHESecondaries": 0,
      "potentialDamageArt": 1000000,
      "potentialDamageTpd": 261250,
      "upgrades": ["主砲改良1", "照準システム改良1"],
      "captainSkills": ["隠蔽処理専門家", "アドレナリン・ラッシュ"],
      "shipComponents": {"hull": "B", "artillery": "AB"}
    }
  ]
}
```

**サイズ目安**: ~10-15KB（14プレイヤー分）

#### UPLOAD レコード

```json
{
  "arenaUniqueID": "3487309050689265",
  "recordType": "UPLOAD#12345",

  "playerID": 12345,
  "playerName": "ClyneLacus",
  "team": "ally",

  "s3Key": "replays/abc123/ClyneLacus.wowsreplay",
  "fileName": "18.01.2026 22-04-33_ClyneLacus.wowsreplay",
  "fileSize": 1429059,
  "uploadedAt": 1737230800,
  "uploadedBy": "135178817575714816",

  "ownPlayer": {
    "name": "ClyneLacus",
    "clanTag": "OZEKI",
    "shipName": "SIBIR",
    "shipId": 123456
  },

  "damage": 120107,
  "kills": 0,
  "spottingDamage": 34333,
  "potentialDamage": 1261250,
  "receivedDamage": 45000,
  "baseXP": 1500,
  "experienceEarned": 2500,
  "citadels": 2,
  "fires": 3,
  "floods": 0,
  "damageAP": 80000,
  "damageHE": 20107,
  "damageTorps": 0,
  "damageFire": 15000,
  "damageFlooding": 0,
  "hitsAP": 45,
  "hitsHE": 32
}
```

**サイズ目安**: ~1KB

---

## 2. ShipIndexTable

### テーブル名
`wows-ship-index-{stage}`

### キースキーマ

| キー | 属性名 | 型 |
|------|--------|-----|
| Partition Key | `shipName` | String |
| Sort Key | `SK` | String |

### SK フォーマット
`{gameType}#{unixTime}#{arenaUniqueID}`

例: `clan#1737230673#3487309050689265`

### レコード構造

```json
{
  "shipName": "MOGADOR",
  "SK": "clan#1737230673#3487309050689265",

  "allyCount": 1,
  "enemyCount": 2,
  "totalCount": 3
}
```

### クエリ例

```python
# クラン戦でMOGADORが味方に2隻以上いた試合
table.query(
    KeyConditionExpression='shipName = :sn AND begins_with(SK, :prefix)',
    FilterExpression='allyCount >= :count',
    ExpressionAttributeValues={
        ':sn': 'MOGADOR',
        ':prefix': 'clan#',
        ':count': 2
    },
    ScanIndexForward=False
)
```

---

## 3. PlayerIndexTable

### テーブル名
`wows-player-index-{stage}`

### キースキーマ

| キー | 属性名 | 型 |
|------|--------|-----|
| Partition Key | `playerName` | String |
| Sort Key | `SK` | String |

### SK フォーマット
`{gameType}#{unixTime}#{arenaUniqueID}`

### レコード構造

```json
{
  "playerName": "ClyneLacus",
  "SK": "clan#1737230673#3487309050689265",

  "team": "ally",
  "clanTag": "OZEKI",
  "shipName": "SIBIR"
}
```

---

## 4. ClanIndexTable

### テーブル名
`wows-clan-index-{stage}`

### キースキーマ

| キー | 属性名 | 型 |
|------|--------|-----|
| Partition Key | `clanTag` | String |
| Sort Key | `SK` | String |

### SK フォーマット
`{gameType}#{unixTime}#{arenaUniqueID}`

### レコード構造

```json
{
  "clanTag": "OZEKI",
  "SK": "clan#1737230673#3487309050689265",

  "team": "ally",
  "memberCount": 6,
  "isMainClan": true
}
```

---

## 5. SessionsTable

### テーブル名
`wows-sessions-{stage}`

### キースキーマ

| キー | 属性名 | 型 |
|------|--------|-----|
| Partition Key | `sessionId` | String |

### TTL
`expiresAt` 属性で自動削除

### レコード構造

```json
{
  "sessionId": "iVdz2clEzI-abc123def456",

  "discordUserId": "135178817575714816",
  "discordUsername": "meteor0090",
  "discordGlobalName": "たこ（meteor0090）",
  "discordAvatar": "https://cdn.discordapp.com/avatars/...",

  "createdAt": 1737230000,
  "expiresAt": 1739822000
}
```

---

## 6. CommentsTable

### テーブル名
`wows-comments-{stage}`

### キースキーマ

| キー | 属性名 | 型 |
|------|--------|-----|
| Partition Key | `arenaUniqueID` | String |
| Sort Key | `commentId` | String |

### レコード構造

```json
{
  "arenaUniqueID": "3487309050689265",
  "commentId": "2d059bca-1a7e-42bb-950c-f18bd9b1b132",

  "discordUserId": "233474196456341504",
  "discordUsername": "7373cv",
  "discordGlobalName": "なみなみ",
  "discordAvatar": "https://cdn.discordapp.com/avatars/...",

  "content": "敵初手：均等、レーダーチュンム",

  "createdAt": 1736775640,
  "updatedAt": null,

  "likes": ["135178817575714816", "987654321"],
  "likeCount": 2
}
```

---

## API変更

### 新規API

| エンドポイント | メソッド | 説明 |
|---------------|---------|------|
| `/api/match/{arenaUniqueID}/stats` | GET | allPlayersStats を取得 |

### 変更API

| エンドポイント | 変更内容 |
|---------------|---------|
| `/api/search` | gameType パラメータでテーブル切り替え |
| `/api/match/{arenaUniqueID}` | MATCH + UPLOAD レコードのみ返却 |

---

## 移行計画

### Phase 1: 新テーブル作成
1. serverless.yml に新テーブル定義を追加
2. デプロイして空テーブルを作成

### Phase 2: データ移行
1. 移行スクリプトで既存データを新形式に変換
2. 新テーブルにデータ投入

### Phase 3: バックエンド更新
1. battle_result_extractor.py を新テーブルに対応
2. search.py を新テーブルに対応
3. match_detail.py に stats API 追加

### Phase 4: フロントエンド更新
1. expand 時に stats API を呼び出すよう変更
2. 新しいレスポンス形式に対応

### Phase 5: 旧テーブル削除
1. 旧テーブルへのアクセスがないことを確認
2. 旧テーブルを削除

---

## RCU見積もり

| 操作 | 旧設計 | 新設計 |
|------|--------|--------|
| 一覧20件取得 | ~75 RCU | ~5 RCU |
| 試合詳細（基本情報） | ~4 RCU | ~1 RCU |
| 試合詳細（+ 統計） | - | ~4 RCU |
| 検索（10件） | ~40 RCU | ~3 RCU |

---

## 補足: gameType の判定

```python
def get_game_type(raw_game_type: str) -> str:
    """
    リプレイファイルの gameType を正規化
    """
    game_type_map = {
        'clan': 'clan',
        'ranked': 'ranked',
        'pvp': 'random',
        'pve': 'other',
        'cooperative': 'other',
        'event': 'other',
    }
    return game_type_map.get(raw_game_type.lower(), 'other')

def get_table_name(game_type: str, stage: str) -> str:
    """
    gameType に対応するテーブル名を返す
    """
    return f'wows-{game_type}-battles-{stage}'
```
