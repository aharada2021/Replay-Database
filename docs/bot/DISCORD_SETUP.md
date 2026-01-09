# Discord Application設定ガイド

AWS Lambdaにデプロイするには、Discord Developer Portalから以下の設定値を取得する必要があります。

## 📋 必要な設定値

1. **DISCORD_APPLICATION_ID** - アプリケーションID
2. **DISCORD_PUBLIC_KEY** - 公開鍵
3. **DISCORD_BOT_TOKEN** - Botトークン
4. **GUILD_ID** - サーバーID
5. **INPUT_CHANNEL_ID** - チャンネルID（参考用）

## 🔧 設定値の取得方法

### 1. Discord Developer Portalにアクセス

https://discord.com/developers/applications

### 2. アプリケーションを選択

既存のアプリケーションを選択するか、新規作成します。

### 3. General Informationタブ

**APPLICATION ID**と**PUBLIC KEY**を取得します。

```
General Information
├── APPLICATION ID: 1234567890123456789  ← コピー
└── PUBLIC KEY: abc123def456...          ← コピー
```

これらを`.env`ファイルに設定：

```env
DISCORD_APPLICATION_ID=1234567890123456789
DISCORD_PUBLIC_KEY=abc123def456...
```

### 4. Botタブ

**TOKEN**を取得します。

```
Bot
└── TOKEN
    └── [Reset Token] または [Copy]ボタン
```

`.env`ファイルに設定：

```env
DISCORD_BOT_TOKEN=your_bot_token_here
```

**重要**: Botトークンは一度しか表示されません。必ずコピーして保存してください。

### 5. Bot Permissionsの設定

**Bot**タブの下部で、以下の権限を有効化：

#### General Permissions
- なし（必要に応じて）

#### Text Permissions
- ✅ Send Messages
- ✅ Send Messages in Threads
- ✅ Embed Links
- ✅ Attach Files
- ✅ Read Message History
- ✅ Add Reactions

これらの権限を組み合わせると、**Permissions Integer**が生成されます（例: 52224）

### 6. OAuth2 URL Generatorで招待リンクを生成

**OAuth2** → **URL Generator**タブ

#### Scopes
- ✅ bot
- ✅ applications.commands

#### Bot Permissions（上記と同じ）
- ✅ Send Messages
- ✅ Embed Links
- ✅ Attach Files
- など

生成されたURLをブラウザで開き、Botをサーバーに招待します。

### 7. Guild ID（サーバーID）の取得

Discordアプリで：

1. **ユーザー設定** → **詳細設定** → **開発者モード**を有効化
2. サーバーアイコンを右クリック → **IDをコピー**

`.env`ファイルに設定：

```env
GUILD_ID=1234567890123456789
```

### 8. Channel ID（チャンネルID）の取得

1. 開発者モードを有効化（上記参照）
2. チャンネルを右クリック → **IDをコピー**

`.env`ファイルに設定：

```env
INPUT_CHANNEL_ID=1234567890123456789
```

**注意**: Lambda版では、INPUT_CHANNEL_IDは参考値です。実際にはSlash Commandでファイルをアップロードします。

## 📝 .envファイルの例

最終的な`.env`ファイルは以下のようになります：

```env
# ローカル実行用（bot.py）
DISCORD_TOKEN=MTIzNDU2Nzg5MDEyMzQ1Njc4OQ.GaBcDe.FgHiJkLmNoPqRsTuVwXyZ123456789

# AWS Lambda実行用（lambda_handler.py）
DISCORD_APPLICATION_ID=1234567890123456789
DISCORD_PUBLIC_KEY=abc123def456ghi789jkl012mno345pqr678stu901vwx234yz
DISCORD_BOT_TOKEN=MTIzNDU2Nzg5MDEyMzQ1Njc4OQ.GaBcDe.FgHiJkLmNoPqRsTuVwXyZ123456789

# サーバー設定
GUILD_ID=9876543210987654321
INPUT_CHANNEL_ID=1122334455667788990
```

## ✅ 設定の確認

設定が完了したら、以下のコマンドで確認できます：

```bash
./setup_lambda.sh
```

すべての環境変数が設定されていれば、「✅ 必須環境変数が全て設定されています」と表示されます。

## 🚀 次のステップ

1. AWS CLIをインストール: `./install_aws_cli.sh`
2. AWS認証情報を設定: `aws configure`
3. デプロイを実行: `./deploy_lambda.sh`

詳細は`README_LAMBDA.md`を参照してください。
