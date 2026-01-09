# WoWS Replay Classification Bot

World of Warshipsのリプレイファイルを自動分類し、マップ別のDiscordチャンネルに投稿するボットです。

## プロジェクト構成

```
project/
├── src/                          # ソースコード
│   ├── lambda_handler.py         # Discord Interactions受信用Lambda
│   ├── replay_processor_handler.py  # リプレイ処理用Lambda
│   ├── replay_processor.py       # リプレイ処理ロジック
│   ├── register_commands.py      # Discordスラッシュコマンド登録
│   └── setup_channels.py         # Discordチャンネル自動作成
│
├── deploy/                       # デプロイ関連
│   ├── Dockerfile                # Lambda用Dockerイメージ定義
│   └── serverless.yml            # Serverless Framework設定
│
├── .github/workflows/            # GitHub Actions
│   ├── ci.yml                    # Linting
│   ├── deploy-lambda.yml         # Lambda自動デプロイ
│   └── deploy-web-ui.yml         # Web UI自動デプロイ
│
├── docs/                         # ドキュメント
│   ├── README.md                 # プロジェクト概要
│   ├── DISCORD_SETUP.md          # Discord Bot設定ガイド
│   ├── QUICKSTART_LAMBDA.md      # Lambda クイックスタート
│   ├── README_LAMBDA.md          # Lambda詳細ドキュメント
│   └── MULTI_SERVER_SETUP.md     # 複数サーバー対応ガイド
│
├── config/                       # 設定ファイル
│   ├── map_names.yaml            # マップ名マッピング
│   ├── .env.example              # 環境変数テンプレート
│   ├── requirements.txt          # Python依存関係
│   └── requirements_lambda.txt   # Python依存関係（Lambda）
│
├── scripts/                      # ユーティリティスクリプト
│   ├── deploy_lambda.sh          # Lambdaデプロイスクリプト
│   ├── setup_lambda.sh           # Lambda初期セットアップ
│   ├── install_aws_cli.sh        # AWS CLI インストール
│   └── backfill_ship_index.py    # 艦艇インデックス再構築
│
├── minimap_renderer/             # WoWS Minimap Renderer（サブモジュール）
├── replays_unpack_upstream/      # リプレイアンパックライブラリ
├── data/                         # データディレクトリ
└── .env                          # 環境変数（Git管理外）
```

## 機能

### Discord Bot機能
- ✅ Discord `/upload_replay`コマンドでリプレイファイルをアップロード
- ✅ **ゲームタイプの自動判定**（Clan Battle / Random Battle / Ranked Battle）
- ✅ リプレイファイルからマップIDを自動抽出
- ✅ **ゲームタイプとマップ名に対応するDiscordチャンネルに自動投稿**
  - Clan Battle → `clan_<マップ名>` チャンネル
  - Random Battle → `random_<マップ名>` チャンネル
  - Ranked Battle → `rank_<マップ名>` チャンネル
- ✅ minimap_rendererでMP4動画を自動生成
- ✅ 対戦相手のクラン名、対戦時間を表示
- ✅ プレイヤー情報（自分、味方、敵）を表示
- ✅ **勝敗判定**（全ゲームタイプ対応）
- ✅ AWS Lambda + Docker コンテナで実行（非同期処理対応）
- ✅ **複数Discordサーバー対応**（Lambda版）

### CI/CD
- ✅ **GitHub Actions自動デプロイ**
  - mainブランチへのプッシュで自動的にdev環境へデプロイ
  - 手動トリガーでproduction環境へデプロイ（承認必須）
- ✅ **Linting & フォーマット**（flake8, black）
- ✅ **ARM64アーキテクチャ対応**（Lambda最適化）
- ✅ **Git Submodules管理**（minimap_renderer, replays_unpack_upstream）

## デプロイ

### GitHub Actions（推奨）

mainブランチへのプッシュで自動的にdev環境にデプロイされます。

#### 必要な設定

**1. Repository Secrets** (`Settings > Secrets and variables > Actions`)
```
AWS_ACCESS_KEY_ID         # AWSアクセスキー
AWS_SECRET_ACCESS_KEY     # AWSシークレットキー
```

**2. Environment Secrets** (`Settings > Environments`)

**development環境:**
```
DISCORD_PUBLIC_KEY
DISCORD_APPLICATION_ID
DISCORD_BOT_TOKEN
INPUT_CHANNEL_ID
GUILD_ID
UPLOAD_API_KEY
```

**production環境:** （オプション）
- 上記と同じsecretsを設定
- **Required reviewers**を有効化して承認者を設定

#### デプロイフロー

- **自動デプロイ（dev）**: `main`ブランチへのプッシュ/マージで自動実行
- **手動デプロイ（prod）**: Actions タブから`Deploy Lambda Backend`ワークフローを手動実行

### 手動デプロイ（ローカル）

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

## アーキテクチャ

### DynamoDBテーブル構成

| テーブル名 | 用途 |
|-----------|------|
| `wows-replays-{stage}` | リプレイデータ本体（試合情報、プレイヤー情報） |
| `wows-ship-match-index-{stage}` | 艦艇検索用インデックス（艦艇名→試合ID） |
| `wows-sessions-{stage}` | ユーザーセッション管理 |

**バックフィルスクリプト:**

既存データの更新・再構築用スクリプト:

```bash
python3 scripts/backfill_ship_index.py       # 艦艇インデックス再構築
python3 scripts/backfill_winloss.py          # 勝敗情報追加（全ゲームタイプ対応）
python3 scripts/backfill_upgrades.py         # アップグレード情報追加
python3 scripts/backfill_skills_japanese.py  # 艦長スキル日本語化
# DRY_RUN=true で実行すると、書き込みなしで対象レコードを確認可能
```

### Lambda関数構成

1. **interactions** (256MB, 30秒)
   - Discord Interactionsを受信
   - 即座にDeferred Responseを返却
   - processor Lambdaを非同期呼び出し

2. **processor** (1024MB, 15分)
   - リプレイファイルを処理
   - ゲームタイプとマップを判定
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
  → ゲームタイプ判定（Clan/Random/Ranked）
  → マップ判定
  → MP4生成（minimap_renderer）
  → ゲームタイプ+マップ別チャンネルに投稿
    (例: clan_罠, random_戦士の道)
  → Webhook で完了通知
```

### CI/CDパイプライン

```
git push origin main
         ↓
[GitHub Actions: CI - Linting]
  → flake8 (src/)
  → black --check (src/)
         ↓
[GitHub Actions: Deploy Lambda Backend]
  → Build Docker Image (ARM64)
    ├─ Install FFmpeg (BtbN/FFmpeg-Builds)
    ├─ Install Python dependencies
    ├─ Copy application code
    └─ Build for linux/arm64
  → Push to ECR (dev tag)
  → Deploy to Lambda (dev)
    ├─ interactions function
    ├─ processor function
    ├─ upload-api function
    ├─ search-api function
    ├─ battle-result-extractor function
    └─ generate-video-api function
         ↓
✅ Development環境デプロイ完了
```

**手動トリガー（Production）:**
```
Actions > Deploy Lambda Backend > Run workflow
  → environment: production を選択
  → Required reviewers による承認
  → 上記と同じフロー (prod tag)
         ↓
✅ Production環境デプロイ完了
```

## Web UI インフラ構成

### 本番環境

| コンポーネント | 詳細 |
|---------------|------|
| URL | https://wows-replay.mirage0926.com |
| S3バケット | `wows-replay-web-ui-prod` |
| CloudFront | `E312DFOIWOIX5S` |
| ACM証明書 | us-east-1 (CloudFront用) |
| Route53 | `mirage0926.com` Zone |
| Basic認証 | CloudFront Functions |

### URL構成

```
https://wows-replay.mirage0926.com/
├── /              → S3 (フロントエンド) [Discord OAuth2認証]
└── /api/*         → API Gateway (Lambda)
```

### 認証

- **Discord OAuth2認証**: 特定のDiscordサーバー・ロールを持つユーザーのみアクセス可能
- **セッション有効期限**: 1ヶ月（30日）

### API エンドポイント

| メソッド | パス | 説明 |
|---------|------|------|
| GET | `/api/search` | リプレイ検索 |
| GET | `/api/match/{arenaUniqueID}` | 試合詳細取得 |
| POST | `/api/upload` | リプレイアップロード |
| POST | `/api/generate-video` | 動画生成 |

### 戦闘統計スコアボード

Web UIの試合詳細ページでは、全プレイヤーの戦闘統計を表示:

| 表示項目 | 説明 |
|---------|------|
| 撃沈 / 与ダメ / 観測 | 基本統計（ダメージ内訳はツールチップで表示） |
| 被ダメ / 潜在 | 被ダメージ・潜在ダメージ（内訳はツールチップで表示） |
| 命中 / 火 / 浸 / 貫通 | 命中数・火災・浸水・貫通数 |
| 艦長スキル | プレイヤー名ホバーで表示（日本語） |
| アップグレード | プレイヤー名ホバーで表示（日本語） |

**デフォルトソート順**: 味方→敵 → 艦種順(CV→BB→CA→DD→SS) → XP順 → ダメージ順

### 検索機能

Web UIでは以下の検索フィルターをサポート:

| フィルター | 説明 |
|-----------|------|
| ゲームタイプ | クラン戦 / ランダム戦 / ランク戦 |
| マップ | マップ名で絞り込み |
| 味方クラン / 敵クラン | クランタグで絞り込み |
| 艦艇名 | 試合に参加した艦艇で検索（大文字小文字区別なし） |
| 日付範囲 | 開始日〜終了日で絞り込み |
| 勝敗 | 勝ち / 負けで絞り込み |

**技術的な実装:**
- カーソルベースのページネーション（30件/ページ）
- 艦艇検索は専用インデックステーブル（`wows-ship-match-index-*`）を使用
- 日付検索はPython側でフィルタリング（DynamoDBの日付形式との互換性のため）

### CloudFront設定

- **オリジン1**: S3バケット（OAC使用）
- **オリジン2**: API Gateway（HTTPS）
- **キャッシュビヘイビア**:
  - デフォルト（`/*`）: S3、Basic認証あり、キャッシュ有効
  - `/api/*`: API Gateway、認証なし、キャッシュ無効

### デプロイ

GitHub Actions (`deploy-web-ui.yml`) で自動デプロイ:
- `main`ブランチへのpushで自動実行
- S3へファイル同期
- CloudFrontキャッシュ無効化

## ドキュメント

- **クイックスタート**
  - [Lambda クイックスタートガイド](docs/QUICKSTART_LAMBDA.md) - 初回セットアップ（推奨）

- **詳細ガイド**
  - [Lambda デプロイガイド](docs/README_LAMBDA.md) - 詳細な手順
  - [複数サーバー対応ガイド](docs/MULTI_SERVER_SETUP.md) - 複数Discordサーバーでの運用
  - [Discord Bot設定](docs/DISCORD_SETUP.md) - Discord側の設定

## ライセンス

このプロジェクトは、minimap_rendererを使用しており、AGPL 3.0ライセンスに従います。
