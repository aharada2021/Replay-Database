# 複数サーバー対応セットアップガイド

このボットは複数のDiscordサーバーで同時に稼働できます。

## 前提条件

- ボットが既にAWS Lambdaにデプロイされている
- Discord Developer Portalで Interactions Endpoint URL が設定されている
- `.env`ファイルに必要な環境変数が設定されている

## セットアップ手順

### 1. グローバルコマンドの登録

ボットを追加した**すべてのサーバー**でSlash Commandを使用できるようにします。

#### 方法A: グローバル登録（全サーバー対応）

```bash
# グローバルコマンドを登録
python3 src/register_commands.py --global

# または引数なしでも可
python3 src/register_commands.py
```

**注意：** グローバルコマンドの反映には最大1時間かかる場合があります。

#### 方法B: 特定サーバーに登録（即座に反映）

開発・テスト用に特定のサーバーのみ登録する場合：

```bash
# サーバーのGUILD_IDを確認
# Discord開発者モードを有効にして、サーバー名を右クリック → IDをコピー

# 特定のサーバーに登録（即座に使用可能）
python3 src/register_commands.py <GUILD_ID>

# 例
python3 src/register_commands.py 123456789012345678
```

**メリット：** 登録後すぐにコマンドが使用可能になります。

### 2. 各サーバーでチャンネルを作成

各Discordサーバーで、リプレイファイルを投稿するためのチャンネルを作成します。

#### 方法1: 自動作成スクリプトを使用（推奨）

```bash
# サーバーのGUILD_IDを確認
# Discord開発者モードを有効にして、サーバー名を右クリック → IDをコピー

# チャンネル自動作成スクリプトを実行
python3 src/setup_channels.py <GUILD_ID>

# カテゴリなしでチャンネルを作成する場合
python3 src/setup_channels.py <GUILD_ID> --no-categories
```

このスクリプトは以下を自動的に作成します：

**Clan Battle用カテゴリ（🏴 Clan Battle Replays）**
- `clan_罠`
- `clan_ソロモン諸島`
- `clan_諸島`
- （全33マップ）

**Random Battle用カテゴリ（⚔️ Random Battle Replays）**
- `random_罠`
- `random_ソロモン諸島`
- （全33マップ）

**Ranked Battle用カテゴリ（🎖️ Ranked Battle Replays）**
- `rank_罠`
- `rank_ソロモン諸島`
- （全33マップ）

#### 方法2: 手動でチャンネルを作成

必要に応じて、以下の命名規則でチャンネルを手動作成できます：

```
<game_type_prefix><map_name>
```

例：
- Clan Battle: `clan_罠`, `clan_戦士の道`, `clan_北極光`
- Random Battle: `random_罠`, `random_戦士の道`, `random_北極光`
- Ranked Battle: `rank_罠`, `rank_戦士の道`, `rank_北極光`

### 3. ボットを各サーバーに追加

Discord Developer Portalから、ボットの招待リンクを生成して各サーバーに追加します。

1. https://discord.com/developers/applications にアクセス
2. アプリケーションを選択
3. 「OAuth2」→「URL Generator」を選択
4. **SCOPES**:
   - `bot`
   - `applications.commands`
5. **BOT PERMISSIONS**:
   - `Read Messages/View Channels`
   - `Send Messages`
   - `Attach Files`
   - `Embed Links`
   - `Read Message History`
6. 生成されたURLをコピーして、各サーバーの管理者に共有

### 4. 動作確認

各サーバーで以下をテスト：

1. `/upload_replay` コマンドが表示されることを確認
2. リプレイファイル（.wowsreplay）をアップロード
3. 正しいチャンネルに投稿されることを確認
   - Clan Battleのリプレイ → `clan_<マップ名>` チャンネル
   - Random Battleのリプレイ → `random_<マップ名>` チャンネル
   - Ranked Battleのリプレイ → `rank_<マップ名>` チャンネル

## チャンネル名のカスタマイズ

すべてのサーバーで同じチャンネル名を使用する必要があります。チャンネル名を変更したい場合：

1. `config/map_names.yaml` を編集
2. Dockerイメージを再ビルド
3. AWS Lambdaに再デプロイ

```bash
bash scripts/deploy_lambda.sh
```

4. すべてのサーバーで新しいチャンネル名に合わせてチャンネルを作成

## トラブルシューティング

### コマンドが表示されない

- グローバルコマンドの反映には最大1時間かかります
- Discordアプリを再起動してみてください
- 特定のサーバーのみで使いたい場合は、`.env`に`GUILD_ID`を設定して`register_commands.py`を実行

### チャンネルが見つからないエラー

- チャンネル名が正確に一致しているか確認
- `setup_channels.py`を実行してチャンネルを作成
- CloudWatch Logsで実際のチャンネル名を確認：
  ```bash
  aws logs tail /aws/lambda/wows-replay-bot-dev-processor --region ap-northeast-1 --since 10m
  ```

### 特定のサーバーでのみ動作させたい

`.env`ファイルに許可するサーバーのIDを設定（カンマ区切り）：

```bash
ALLOWED_GUILD_IDS=123456789012345678,987654321098765432
```

そして、`src/lambda_handler.py`に以下のチェックを追加：

```python
ALLOWED_GUILD_IDS = os.getenv('ALLOWED_GUILD_IDS', '').split(',')

def handle_interaction(event, context):
    # ...
    data = json.loads(body)
    guild_id = data.get('guild_id')

    # ホワイトリストチェック
    if ALLOWED_GUILD_IDS and guild_id not in ALLOWED_GUILD_IDS:
        return {
            'statusCode': 200,
            'headers': {'Content-Type': 'application/json'},
            'body': json.dumps({
                "type": 4,
                "data": {
                    "content": "このサーバーではボットを使用できません。",
                    "flags": 64
                }
            })
        }
```

## サポートされているマップとゲームタイプ

### ゲームタイプ

- **Clan Battle** (`clan`) → `clan_` prefix
- **Random Battle** (`pvp`) → `random_` prefix
- **Ranked Battle** (`ranked`) → `rank_` prefix

### マップ一覧

全33マップをサポート（`config/map_names.yaml`参照）：

- 罠、ソロモン諸島、諸島、リング、北極光、氷の島々
- 新たなる夜明け、大西洋、北方、ホットスポット、断層線
- 氷の島々(冬)、二人の兄弟、火の地、破片、ギリシャ
- 海戦、新ティエラ、島嶼、北方(冬)、海嶺、カナダ
- 沖縄、征服、隣人、戦士の道、ジグザグ、河口
- 眠れる巨人、安息の地、北方海域、幸運の海

## 料金について

複数サーバーで稼働させても、AWS Lambda の料金は実際の使用量に応じて課金されます：

- **無料枠**: 月間100万リクエスト、40万GB秒の計算時間
- リプレイ処理1回あたりの目安コスト: $0.001〜0.003（使用量による）

通常の使用では、無料枠内で運用可能です。
