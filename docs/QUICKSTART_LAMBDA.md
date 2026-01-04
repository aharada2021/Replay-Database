# AWS Lambda クイックスタートガイド

このガイドに従って、WoWS Replay BotをAWS Lambdaにデプロイします。

## 🎯 デプロイの流れ（5ステップ）

```
1. AWS CLIインストール (5分)
   ↓
2. Discord設定取得 (5分)
   ↓
3. 環境変数設定 (2分)
   ↓
4. デプロイ実行 (10分)
   ↓
5. Discord設定 (3分)
```

**合計所要時間: 約25分**

---

## ステップ1️⃣: AWS CLIのインストール

```bash
./install_aws_cli.sh
```

インストール後、AWS認証情報を設定：

```bash
aws configure
```

入力が必要な情報：
- **AWS Access Key ID**: IAMユーザーのアクセスキー
- **AWS Secret Access Key**: IAMユーザーのシークレットキー
- **Default region name**: `ap-northeast-1`
- **Default output format**: `json`

### AWSアクセスキーの取得方法

1. [AWS Console](https://console.aws.amazon.com/)にログイン
2. **IAM** サービスに移動
3. **ユーザー** → 自分のユーザー名を選択
4. **セキュリティ認証情報** タブ
5. **アクセスキーを作成**ボタンをクリック

⚠️ **重要**: アクセスキーは一度しか表示されません。必ず保存してください。

---

## ステップ2️⃣: Discord設定の取得

詳細は `DISCORD_SETUP.md` を参照してください。

### 取得する情報

1. **APPLICATION_ID** - [Discord Developer Portal](https://discord.com/developers/applications) > General Information
2. **PUBLIC_KEY** - 同上
3. **BOT_TOKEN** - Bot タブ

⚠️ **注意**: Lambda版では`GUILD_ID`と`INPUT_CHANNEL_ID`は不要です（複数サーバー対応のため）

---

## ステップ3️⃣: 環境変数の設定

### .envファイルを作成

```bash
cp .env.example .env
```

### .envファイルを編集

```bash
vi .env
# または
code .env
```

以下のように設定：

```env
# Discord設定
DISCORD_APPLICATION_ID=あなたのアプリケーションID
DISCORD_PUBLIC_KEY=あなたの公開鍵
DISCORD_BOT_TOKEN=あなたのBotトークン

# AWS設定（オプション）
AWS_REGION=ap-northeast-1
DEPLOY_STAGE=dev
```

⚠️ `GUILD_ID`と`INPUT_CHANNEL_ID`は**不要**です（複数サーバー対応）

### セットアップスクリプトで確認

```bash
./setup_lambda.sh
```

「✅ 必須環境変数が全て設定されています」と表示されればOK。

このスクリプトは以下も実行します：
- Node.js依存関係のインストール (`npm install`)
- 環境の前提条件チェック

---

## ステップ4️⃣: AWS Lambdaにデプロイ

```bash
bash scripts/deploy_lambda.sh
```

このスクリプトが自動的に以下を実行します：

1. ✅ ECRリポジトリの作成
2. ✅ Dockerイメージのビルド（数分かかります）
3. ✅ ECRへのプッシュ
4. ✅ Lambda関数のデプロイ
5. ✅ API Gatewayの作成

デプロイが完了すると、**Interactions Endpoint URL**が表示されます：

```
https://xxxxxxxxxx.execute-api.ap-northeast-1.amazonaws.com/dev/interactions
```

⚠️ **このURLをコピーしてください。次のステップで使用します。**

---

## ステップ5️⃣: Discord設定の完了

### 5-1. Interactions Endpointの設定

1. [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
2. アプリケーションを選択
3. **General Information**タブ
4. **INTERACTIONS ENDPOINT URL**に、コピーしたURLを貼り付け
5. **Save Changes**をクリック

Discordが自動的にエンドポイントを検証します（PINGリクエスト）。

✅ 「All your edits have been carefully recorded.」と表示されれば成功！

### 5-2. Slash Commandsの登録

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

「✅ Slash Commandを登録しました」と表示されればOK。

### 5-3. チャンネルの作成

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

---

## 🎉 完了！テストしてみましょう

1. Discordサーバーで `/upload_replay` と入力
2. `file` パラメータでリプレイファイル（.wowsreplay）を選択
3. 送信

Botが自動的に：
- リプレイファイルを解析
- **ゲームタイプを判定**（Clan Battle / Random Battle / Ranked Battle）
- マップを判定
- MP4動画を生成
- クラン情報を取得
- **該当するチャンネルに投稿**
  - Clan Battle → `clan_<マップ名>` チャンネル
  - Random Battle → `random_<マップ名>` チャンネル
  - Ranked Battle → `rank_<マップ名>` チャンネル

---

## 🔧 トラブルシューティング

### Interactions Endpointの検証が失敗する

**原因**: Lambda関数がデプロイされていない、またはPUBLIC_KEYが間違っている

**解決方法**:
```bash
# Lambda関数のログを確認
npx serverless logs -f interactions --stage dev --tail

# .envのDISCORD_PUBLIC_KEYが正しいか確認
cat .env | grep PUBLIC_KEY
```

### `/upload_replay`コマンドが表示されない

**原因**: Slash Commandsの登録に失敗している、または反映待ち

**解決方法**:
```bash
# 特定のサーバーに登録（即座に反映）
python3 src/register_commands.py <GUILD_ID>

# グローバル登録（反映に最大1時間）
python3 src/register_commands.py --global

# Discordアプリを再起動してみる
```

### MP4生成が失敗する

**原因**: Lambda関数のメモリまたはタイムアウト不足

**解決方法**:
- `deploy/serverless.yml`の`processor`関数の設定を確認
  - `memorySize: 1024` (1GB) - 必要に応じて増やす
  - `timeout: 900` (15分)
- 設定を変更したら再デプロイ: `bash scripts/deploy_lambda.sh`

### ファイルサイズが大きすぎる

**制限**:
- API Gateway: 10MB
- Discord添付ファイル: 25MB (Nitroは100MB)
- Lambda: 10GB (Container Image)

**解決方法**:
- 大きなMP4ファイルはS3 Presigned URLを使用（実装が必要）

---

## 📊 コスト見積もり

**月間100リプレイ処理の場合: 約$0.21**

内訳：
- Lambda実行: $0.15
- API Gateway: $0.0004
- S3ストレージ: $0.01
- データ転送: $0.05

**無料枠**:
- Lambda: 月100万リクエスト、40万GB秒まで無料
- API Gateway: 月100万リクエストまで無料（12ヶ月間）

---

## 🔄 更新方法

コードを変更した場合：

```bash
bash scripts/deploy_lambda.sh
```

自動的にDockerイメージを再ビルドしてデプロイします。

### マップ名やチャンネル設定を変更した場合

1. `config/map_names.yaml`を編集
2. 再デプロイ: `bash scripts/deploy_lambda.sh`
3. 各サーバーでチャンネルを更新（既存のチャンネルをリネーム、または新規作成）

---

## 🗑️ 削除方法

すべてのAWSリソースを削除：

```bash
# Lambda、API Gateway、S3バケットを削除
npx serverless remove --stage dev

# ECRリポジトリを削除
aws ecr delete-repository \
  --repository-name wows-replay-bot \
  --region ap-northeast-1 \
  --force
```

---

## 📚 参考資料

- **詳細デプロイガイド**: `README_LAMBDA.md`
- **Discord設定ガイド**: `DISCORD_SETUP.md`
- **ローカルBotとの比較**: `README_LAMBDA.md`の「重要な注意事項」セクション

---

## 💬 サポート

問題が発生した場合は、以下を確認してください：

1. CloudWatch Logsでエラーを確認
   ```bash
   npx serverless logs -f interactions --stage dev --tail
   ```

2. 環境変数が正しく設定されているか確認
   ```bash
   cat .env
   ```

3. Discord Developer Portalの設定を再確認
   - APPLICATION_ID
   - PUBLIC_KEY
   - BOT_TOKEN

4. AWS認証情報を確認
   ```bash
   aws sts get-caller-identity
   ```
