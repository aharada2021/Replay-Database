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
GUILD_ID=your_guild_id
INPUT_CHANNEL_ID=your_input_channel_id
```

**Discord設定の取得方法：**

1. [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
2. アプリケーションを選択
3. **General Information**タブ:
   - `APPLICATION ID` → `DISCORD_APPLICATION_ID`
   - `PUBLIC KEY` → `DISCORD_PUBLIC_KEY`
4. **Bot**タブ:
   - `TOKEN` → `DISCORD_BOT_TOKEN`

### 4. ECRリポジトリの作成

Lambdaコンテナイメージ用のECRリポジトリを作成：

```bash
aws ecr create-repository \
  --repository-name wows-replay-bot \
  --region ap-northeast-1
```

出力されたリポジトリURIをメモしてください（例: `123456789012.dkr.ecr.ap-northeast-1.amazonaws.com/wows-replay-bot`）

### 5. Dockerイメージのビルドとプッシュ

```bash
# ECRにログイン
aws ecr get-login-password --region ap-northeast-1 | \
  docker login --username AWS --password-stdin YOUR_ECR_URI

# イメージをビルド
docker build -t wows-replay-bot .

# タグ付け
docker tag wows-replay-bot:latest YOUR_ECR_URI:latest

# プッシュ
docker push YOUR_ECR_URI:latest
```

### 6. serverless.ymlの更新

`serverless.yml`の`functions.interactions.image`セクションを更新：

```yaml
functions:
  interactions:
    image: YOUR_ECR_URI:latest
```

### 7. デプロイ

```bash
# 開発環境にデプロイ
serverless deploy --stage dev

# 本番環境にデプロイ
serverless deploy --stage prod
```

デプロイが成功すると、Interactions Endpoint URLが出力されます：

```
endpoints:
  POST - https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/dev/interactions
```

### 8. Discord Interactions Endpointの設定

1. [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
2. アプリケーションを選択
3. **General Information**タブ
4. **INTERACTIONS ENDPOINT URL**に、デプロイ時に出力されたURLを設定
5. **Save Changes**をクリック

Discordが自動的にエンドポイントを検証します（PINGリクエストを送信）。

### 9. Slash Commandの登録

```bash
python register_commands.py
```

これにより、`/upload_replay`コマンドがDiscordに登録されます。

## 📝 使い方

1. Discordサーバーで `/upload_replay` コマンドを実行
2. `file` パラメータでリプレイファイル（.wowsreplay）を選択
3. Botが自動的に:
   - ファイルを解析
   - マップを判定
   - MP4動画を生成
   - クラン情報を取得
   - 該当するマップチャンネルに投稿

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
