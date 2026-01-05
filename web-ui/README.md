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

### S3 + CloudFrontへのデプロイ

1. **S3バケット作成**

```bash
aws s3 mb s3://wows-replay-web-ui-dev --region ap-northeast-1
```

2. **静的ウェブサイトホスティング有効化**

```bash
aws s3 website s3://wows-replay-web-ui-dev --index-document index.html --error-document 404.html
```

3. **ビルド & アップロード**

```bash
npm run generate
aws s3 sync .output/public/ s3://wows-replay-web-ui-dev --delete
```

4. **パブリックアクセス設定**

```bash
aws s3api put-bucket-policy --bucket wows-replay-web-ui-dev --policy '{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "PublicReadGetObject",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::wows-replay-web-ui-dev/*"
    }
  ]
}'
```

5. **CloudFront Distribution作成（オプション）**

CloudFrontを使用すると、HTTPS対応やカスタムドメイン設定が可能です。

```bash
# CloudFront Distributionは手動またはserverless.ymlで設定
```

### デプロイスクリプト

簡単にデプロイできるようにスクリプトを作成しました:

```bash
# 開発環境へデプロイ
npm run deploy:dev

# 本番環境へデプロイ
npm run deploy:prod
```

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
