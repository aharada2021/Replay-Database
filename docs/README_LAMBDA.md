# AWS Lambda デプロイガイド

このガイドでは、WoWS Replay Classification BotをAWS Lambdaにデプロイする手順を説明します。

## 📋 前提条件

- AWS アカウント
- AWS CLI がインストール・設定済み
- Docker がインストール済み
- Node.js (Serverless Framework用)
- Python 3.10以上

## 🏗️ アーキテクチャ

```
Discord User
    ↓ /upload_replay コマンド
API Gateway
    ↓
Lambda Function (Container Image)
    ├─ リプレイファイルをダウンロード
    ├─ メタデータ解析
    ├─ MP4動画生成 (minimap_renderer)
    ├─ クラン情報取得 (WoWS API)
    └─ Discord チャンネルに投稿
```

## 🚀 デプロイ手順

### 1. Serverless Frameworkのインストール

```bash
npm install -g serverless
npm install --save-dev serverless-python-requirements
```

### 2. AWS認証情報の設定

```bash
aws configure
# AWS Access Key ID: YOUR_ACCESS_KEY
# AWS Secret Access Key: YOUR_SECRET_KEY
# Default region name: ap-northeast-1
# Default output format: json
```

### 3. 環境変数の設定

`.env`ファイルを作成し、必要な値を設定：

```bash
cp .env.example .env
```

`.env`を編集：

```env
# Discord設定
DISCORD_APPLICATION_ID=your_application_id
DISCORD_PUBLIC_KEY=your_public_key
DISCORD_BOT_TOKEN=your_bot_token

# AWS設定（オプション）
AWS_REGION=ap-northeast-1
DEPLOY_STAGE=dev
```

⚠️ **注意**: `GUILD_ID`と`INPUT_CHANNEL_ID`は不要です（複数サーバー対応のため）

**Discord設定の取得方法：**

1. [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
2. アプリケーションを選択
3. **General Information**タブ:
   - `APPLICATION ID` → `DISCORD_APPLICATION_ID`
   - `PUBLIC KEY` → `DISCORD_PUBLIC_KEY`
4. **Bot**タブ:
   - `TOKEN` → `DISCORD_BOT_TOKEN`

### 4. 自動デプロイ（推奨）

自動デプロイスクリプトを使用すると、すべての手順が自動化されます：

```bash
bash scripts/deploy_lambda.sh
```

このスクリプトは以下を自動実行します：
1. ECRリポジトリの作成（存在しない場合）
2. Dockerイメージのビルド
3. ECRへのプッシュ
4. serverless.ymlの更新
5. Lambda関数とAPI Gatewayのデプロイ

デプロイが成功すると、Interactions Endpoint URLが表示されます：

```
https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/interactions
```

⚠️ **このURLをコピーしてください。次のステップで使用します。**

---

### 手動デプロイ（上級者向け）

<details>
<summary>手動でデプロイする場合はこちらをクリック</summary>

#### 4.1. ECRリポジトリの作成

```bash
aws ecr create-repository \
  --repository-name wows-replay-bot \
  --region ap-northeast-1
```

#### 4.2. Dockerイメージのビルドとプッシュ

```bash
# ECRにログイン
aws ecr get-login-password --region ap-northeast-1 | \
  docker login --username AWS --password-stdin <YOUR_ACCOUNT_ID>.dkr.ecr.ap-northeast-1.amazonaws.com

# イメージをビルド
docker build -f deploy/Dockerfile -t wows-replay-bot:latest .

# タグ付け
docker tag wows-replay-bot:latest <YOUR_ACCOUNT_ID>.dkr.ecr.ap-northeast-1.amazonaws.com/wows-replay-bot:dev

# プッシュ
docker push <YOUR_ACCOUNT_ID>.dkr.ecr.ap-northeast-1.amazonaws.com/wows-replay-bot:dev
```

#### 4.3. デプロイ

```bash
cd deploy
npx serverless deploy --stage dev --region ap-northeast-1
cd ..
```

</details>

### 5. Discord Interactions Endpointの設定

1. [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
2. アプリケーションを選択
3. **General Information**タブ
4. **INTERACTIONS ENDPOINT URL**に、デプロイ時に出力されたURLを設定
5. **Save Changes**をクリック

Discordが自動的にエンドポイントを検証します（PINGリクエストを送信）。

### 6. Slash Commandの登録

#### 特定のサーバーに登録（推奨：即座に反映）

```bash
# サーバーのGUILD_IDを確認（Discord開発者モードを有効にして、サーバー右クリック → IDをコピー）
python3 src/register_commands.py <GUILD_ID>

# 例
python3 src/register_commands.py 1433102839651242140
```

#### グローバル登録（全サーバー：反映に最大1時間）

```bash
python3 src/register_commands.py --global
```

### 7. チャンネルの作成

各サーバーで必要なチャンネルを自動作成：

```bash
# カテゴリ付きで作成（推奨）
python3 src/setup_channels.py <GUILD_ID>

# カテゴリなしで作成
python3 src/setup_channels.py <GUILD_ID> --no-categories
```

このスクリプトは以下のチャンネルを自動作成します：
- **Clan Battle用**: `clan_罠`, `clan_戦士の道`, など（全33マップ）
- **Random Battle用**: `random_罠`, `random_戦士の道`, など（全33マップ）
- **Ranked Battle用**: `rank_罠`, `rank_戦士の道`, など（全33マップ）

詳細は `docs/MULTI_SERVER_SETUP.md` を参照してください。

## 📝 使い方

1. Discordサーバーで `/upload_replay` コマンドを実行
2. `file` パラメータでリプレイファイル（.wowsreplay）を選択
3. Botが自動的に:
   - ファイルを解析
   - **ゲームタイプを判定**（Clan Battle / Random Battle / Ranked Battle）
   - マップを判定
   - MP4動画を生成
   - クラン情報を取得
   - **該当するチャンネルに投稿**
     - Clan Battle → `clan_<マップ名>` チャンネル
     - Random Battle → `random_<マップ名>` チャンネル
     - Ranked Battle → `rank_<マップ名>` チャンネル

## 🌐 複数サーバー対応

このボットは複数のDiscordサーバーで同時に稼働できます。

- すべてのサーバーで同じチャンネル名構造を使用
- サーバーごとにチャンネルを自動作成可能
- グローバルコマンド登録で全サーバー対応

詳細は `docs/MULTI_SERVER_SETUP.md` を参照してください。

## 🔧 トラブルシューティング

### Interactions Endpointの検証が失敗する

- Lambda関数が正しくデプロイされているか確認
- `DISCORD_PUBLIC_KEY`が正しく設定されているか確認
- CloudWatch Logsでエラーを確認

```bash
serverless logs -f interactions --stage dev --tail
```

### MP4生成が失敗する

- Lambda関数のメモリとタイムアウトを確認
- `serverless.yml`で`memorySize: 3008`、`timeout: 900`に設定

### ファイルサイズ制限

- Lambda: 最大10GB (Container Image)
- API Gateway: リクエストボディ最大10MB
- Discord: ファイル添付最大25MB (Nitroユーザーは100MB)

大きなMP4ファイルの場合、S3 Presigned URLを使用する必要があります。

## 💰 コスト見積もり

**月間100リプレイ処理の場合:**

- Lambda実行時間: 100リプレイ × 30秒 × $0.0000166667/GB秒 × 3GB = $0.15
- API Gateway: 100リクエスト × $0.0000035 = $0.0004
- S3ストレージ: 一時ファイル（1日で削除） = $0.01
- データ転送: $0.05

**合計: 約$0.21/月**

## 🔄 更新方法

コードを更新した場合：

```bash
# Dockerイメージを再ビルド・プッシュ
docker build -t wows-replay-bot .
docker tag wows-replay-bot:latest YOUR_ECR_URI:latest
docker push YOUR_ECR_URI:latest

# Lambda関数を更新
serverless deploy --stage dev
```

## 🗑️ 削除方法

```bash
# Serverless Frameworkでリソースを削除
serverless remove --stage dev

# ECRリポジトリを削除
aws ecr delete-repository \
  --repository-name wows-replay-bot \
  --region ap-northeast-1 \
  --force
```

## ⚠️ 重要な注意事項

### ローカルBot（bot.py）との違い

| 機能 | ローカルBot | Lambda Bot |
|------|------------|------------|
| ファイルアップロード検出 | ✅ 自動 | ❌ `/upload_replay`コマンドが必要 |
| 常時接続 | ✅ | ❌ |
| コスト | サーバー費用 | 従量課金 |
| スケーラビリティ | 制限あり | 自動スケール |

### 制限事項

1. **自動ファイル検出不可**: 特定チャンネルへのファイルアップロードを自動検出できません
2. **Slash Command必須**: ユーザーが明示的に`/upload_replay`コマンドを実行する必要があります
3. **タイムアウト**: Lambda最大15分のタイムアウトあり

## 📚 参考資料

- [Discord Interactions](https://discord.com/developers/docs/interactions/receiving-and-responding)
- [AWS Lambda Container Images](https://docs.aws.amazon.com/lambda/latest/dg/images-create.html)
- [Serverless Framework](https://www.serverless.com/framework/docs)
