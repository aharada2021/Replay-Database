# WoWS Replay Web UI

リプレイデータベースのフロントエンド（Nuxt 4 + Vuetify 3）

## ディレクトリ構成

```
web-ui/
  app/                  # Nuxt 4 ソースディレクトリ
    components/         # Vueコンポーネント
    composables/        # Composition API ユーティリティ
    middleware/         # ルートミドルウェア（認証）
    pages/              # ページコンポーネント（ファイルベースルーティング）
    plugins/            # Nuxtプラグイン（Vuetify）
    stores/             # Pinia ストア
    types/              # TypeScript型定義
    app.vue             # ルートコンポーネント
  public/               # 静的アセット
  nuxt.config.ts        # Nuxt設定
```

## 開発

```bash
npm install
npm run dev
```

http://localhost:3000 でアクセス

## ビルド

```bash
npm run generate
```

出力: `.output/public/`

## デプロイ

`main`または`develop`ブランチへのpushで自動デプロイ（GitHub Actions）
