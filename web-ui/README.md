# WoWS Replay Web UI

World of Warships リプレイデータベースのWeb UIです。

## 技術スタック

- **Nuxt 4**: Vue.js フレームワーク
- **Vue 3**: リアクティブUIフレームワーク
- **Vuetify 3**: マテリアルデザインUIコンポーネント
- **Pinia**: 状態管理
- **TypeScript**: 型安全性

## セットアップ

### 前提条件

- Node.js 18以上
- npm または yarn

### インストール

```bash
npm install
```

### 環境変数設定

`.env.example`を`.env`にコピーして、必要に応じて編集してください。

```bash
cp .env.example .env
```

### 開発サーバー起動

```bash
npm run dev
```

ブラウザで http://localhost:3000 にアクセスしてください。

## ビルド

### 静的サイト生成（SSG）

```bash
npm run generate
```

出力ディレクトリ: `.output/public/`

### プレビュー

```bash
npm run preview
```

## デプロイ

### 本番環境インフラ構成

| コンポーネント | 詳細 |
|---------------|------|
| URL | https://wows-replay.mirage0926.com |
| S3バケット | `wows-replay-web-ui-prod` |
| CloudFront | `E312DFOIWOIX5S` |
| ACM証明書 | us-east-1 (CloudFront用) |
| Route53 | `mirage0926.com` Zone |
| Basic認証 | CloudFront Functions (`wows-replay-basic-auth`) |

### URL構成

```
https://wows-replay.mirage0926.com/
├── /              → S3 (フロントエンド) [Basic認証あり]
└── /api/*         → API Gateway (Lambda) [認証なし]
```

### GitHub Actions 自動デプロイ

`main`ブランチへのpushで自動的にデプロイされます。

ワークフロー: `.github/workflows/deploy-web-ui.yml`

```yaml
# 実行される処理:
1. npm ci                    # 依存関係インストール
2. npm run generate          # 静的ファイル生成
3. aws s3 sync               # S3へアップロード
4. aws cloudfront create-invalidation  # キャッシュ無効化
```

### 手動デプロイ

```bash
# 1. ビルド
npm run generate

# 2. S3へアップロード
aws s3 sync .output/public/ s3://wows-replay-web-ui-prod --delete

# 3. CloudFrontキャッシュ無効化
aws cloudfront create-invalidation --distribution-id E312DFOIWOIX5S --paths "/*"
```

### CloudFront設定詳細

**オリジン構成:**
- **S3オリジン**: OAC (Origin Access Control) 使用、パブリックアクセス無効
- **API Gatewayオリジン**: HTTPS-only、キャッシュ無効

**キャッシュビヘイビア:**
| パス | オリジン | キャッシュ | 認証 |
|------|---------|-----------|------|
| `/*` (デフォルト) | S3 | Managed-CachingOptimized | Basic認証 |
| `/api/*` | API Gateway | CachingDisabled | なし |

**Basic認証:**
CloudFront Functions (`wows-replay-basic-auth`) で実装。
認証情報はCloudFront Function内にハードコードされています。

### 環境変数

`.env` ファイルで設定:

```bash
# API Base URL (空 = 同一オリジン)
API_BASE_URL=
```

ビルド時に `API_BASE_URL` が空の場合、相対パス `/api/*` でAPIにアクセスします。

## ディレクトリ構成

```
web-ui/
├── components/          # 再利用可能なVueコンポーネント
├── composables/         # Composition API関数
│   └── useApi.ts       # API通信ロジック
├── pages/              # ページコンポーネント（ルーティング）
│   ├── index.vue       # 検索画面
│   └── match/
│       └── [id].vue    # 詳細画面
├── plugins/            # Nuxtプラグイン
│   └── vuetify.ts      # Vuetify設定
├── stores/             # Pinia状態管理
│   └── search.ts       # 検索状態
├── types/              # TypeScript型定義
│   └── replay.ts       # リプレイデータ型
├── app.vue             # ルートコンポーネント
├── nuxt.config.ts      # Nuxt設定
└── package.json        # 依存関係
```

## 機能

### 検索画面 (`/`)

- リプレイファイルの検索
- フィルタ条件:
  - ゲームタイプ（クラン戦/ランダム/ランク戦）
  - マップ
  - プレイヤー名
  - 敵艦名
  - 勝敗
  - 日時範囲
- ページネーション

### 詳細画面 (`/match/:id`)

- 試合情報表示
- プレイヤー一覧（自分/味方/敵）
- リプレイファイルダウンロード
- 動画生成（オンデマンド）
- 動画再生

## トラブルシューティング

### APIが繋がらない

`.env`ファイルの`API_BASE_URL`が正しいか確認してください。

### 動画が再生できない

ブラウザがサポートしている動画形式（MP4）であることを確認してください。
S3バケットのCORS設定も確認してください。

## ライセンス

Private
