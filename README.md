# WoWS Replay Database

World of Warshipsのリプレイファイルを管理・分析するWebアプリケーション。

## 概要

- **Web UI**: リプレイ検索、試合詳細・統計表示、ミニマップ動画再生
- **Auto Uploader**: Windowsクライアント常駐ツールで自動アップロード（ゲームプレイ録画機能付き）
- **Discord連携**: OAuth認証、クラン戦通知

## 技術スタック

| コンポーネント | 技術 |
|---------------|------|
| バックエンド | Python 3.12, AWS Lambda, DynamoDB, S3 |
| リプレイ処理 | Rust (wows-replay-tool) |
| フロントエンド | Nuxt 4, Vue 3, Vuetify 3, Pinia 3, TypeScript |
| インフラ | Serverless Framework, CloudFront, API Gateway, Docker (ARM64) |
| CI/CD | GitHub Actions |

## 開発者向け情報

開発に必要な詳細情報は [CLAUDE.md](CLAUDE.md) を参照してください。

ゲームバージョンアップ時の対応手順は [docs/game-version-update.md](docs/game-version-update.md) を参照してください。

## Acknowledgments

- **[wows-toolkit](https://github.com/landaire/wows-toolkit)** by [@landaire](https://github.com/landaire) (MIT License)
  - リプレイ解析・ミニマップレンダリングのコアエンジンとして使用
  - 使用crate: `wows_replays`（リプレイパース）, `wowsunpack`（ゲームデータ抽出）, `wows_minimap_renderer`（動画レンダリング）
  - ゲームデータ抽出CLI `wows-data-mgr` を使用

サードパーティライセンスの全文は [THIRD-PARTY-LICENSES.md](THIRD-PARTY-LICENSES.md) を参照してください。

## ライセンス

Private
