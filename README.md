# WoWS Replay Database

World of Warshipsのリプレイファイルを管理・分析するWebアプリケーション。

## 概要

- **Web UI**: リプレイ検索、試合詳細表示、動画生成
- **Discord Bot**: `/upload_replay`コマンドでリプレイアップロード
- **Auto Uploader**: クライアント常駐ツールで自動アップロード

## 技術スタック

| コンポーネント | 技術 |
|---------------|------|
| バックエンド | Python 3.10, AWS Lambda, DynamoDB, S3 |
| フロントエンド | Nuxt 4, Vue 3, Vuetify 3, Pinia 3, TypeScript |
| インフラ | Serverless Framework, CloudFront, API Gateway |
| CI/CD | GitHub Actions |

## 開発者向け情報

開発に必要な詳細情報は [CLAUDE.md](CLAUDE.md) を参照してください。

## ライセンス

AGPL 3.0 (minimap_renderer使用)
