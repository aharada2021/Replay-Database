# WoWS Replay Classification Bot

World of Warshipsのリプレイファイルを自動分類し、マップ別のDiscordチャンネルに投稿するボットです。

## プロジェクト構成

```
project/
├── src/                          # ソースコード
│   ├── lambda_handler.py         # Discord Interactions受信用Lambda
│   ├── replay_processor_handler.py  # リプレイ処理用Lambda
│   ├── replay_processor.py       # リプレイ処理ロジック
│   ├── bot.py                    # Discord Bot（ローカル実行用）
│   └── register_commands.py      # Discordスラッシュコマンド登録
│
├── deploy/                       # デプロイ関連
│   ├── Dockerfile                # Lambda用Dockerイメージ定義
│   └── serverless.yml            # Serverless Framework設定
│
├── docs/                         # ドキュメント
│   ├── README.md                 # プロジェクト概要
│   ├── DISCORD_SETUP.md          # Discord Bot設定ガイド
│   ├── QUICKSTART_LAMBDA.md      # Lambda クイックスタート
│   ├── README_LAMBDA.md          # Lambda詳細ドキュメント
│   └── specification.md          # 仕様書・残タスク
│
├── config/                       # 設定ファイル
│   ├── map_names.yaml            # マップ名マッピング
│   ├── .env.example              # 環境変数テンプレート
│   ├── requirements.txt          # Python依存関係（ローカル）
│   └── requirements_lambda.txt   # Python依存関係（Lambda）
│
├── scripts/                      # ユーティリティスクリプト
│   ├── deploy_lambda.sh          # Lambdaデプロイスクリプト
│   ├── setup_lambda.sh           # Lambda初期セットアップ
│   ├── install_aws_cli.sh        # AWS CLI インストール
│   └── restart_bot.sh            # Bot再起動スクリプト
│
├── minimap_renderer/             # WoWS Minimap Renderer（サブモジュール）
├── replays_unpack_upstream/      # リプレイアンパックライブラリ
├── data/                         # データディレクトリ
└── .env                          # 環境変数（Git管理外）
```

## 機能

- ✅ Discord `/upload_replay`コマンドでリプレイファイルをアップロード
- ✅ リプレイファイルからマップIDを自動抽出
- ✅ マップ名に対応するDiscordチャンネルに自動投稿
- ✅ minimap_rendererでMP4動画を自動生成
- ✅ 対戦相手のクラン名、対戦時間を表示
- ✅ プレイヤー情報（自分、味方、敵）を表示
- ✅ AWS Lambda + Docker コンテナで実行（非同期処理対応）

## デプロイ

### Lambda環境

```bash
# 1. 環境変数を設定
cp config/.env.example .env
# .env を編集して必要な値を設定

# 2. AWSにログイン
aws sso login

# 3. デプロイスクリプトを実行
cd scripts
./deploy_lambda.sh
```

詳細は [docs/QUICKSTART_LAMBDA.md](docs/QUICKSTART_LAMBDA.md) を参照してください。

### ローカル環境

```bash
# 1. 依存関係をインストール
pip install -r config/requirements.txt

# 2. 環境変数を設定
cp config/.env.example .env
# .env を編集

# 3. Botを起動
python src/bot.py
```

## アーキテクチャ

### Lambda関数構成

1. **interactions** (256MB, 30秒)
   - Discord Interactionsを受信
   - 即座にDeferred Responseを返却
   - processor Lambdaを非同期呼び出し

2. **processor** (3008MB, 15分)
   - リプレイファイルを処理
   - MP4動画を生成
   - Discord Webhookで結果を通知

### 処理フロー

```
Discord /upload_replay
         ↓
[interactions Lambda]
  → Deferred Response (3秒以内)
  → processor Lambda 非同期呼び出し
         ↓
[processor Lambda]
  → リプレイ解析
  → MP4生成（minimap_renderer）
  → マップ別チャンネルに投稿
  → Webhook で完了通知
```

## ドキュメント

- [仕様書・残タスク](docs/specification.md)
- [Discord Bot設定](docs/DISCORD_SETUP.md)
- [Lambda デプロイガイド](docs/README_LAMBDA.md)

## ライセンス

このプロジェクトは、minimap_rendererを使用しており、AGPL 3.0ライセンスに従います。
