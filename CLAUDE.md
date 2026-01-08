# Claude Code Project Rules

## プロジェクト概要
World of Warshipsのリプレイファイルを管理・分析するWebアプリケーション。Discord Bot連携とWeb UIを提供。

## 技術スタック

### バックエンド
- Python 3.10 (AWS Lambda) # minimap_rendererの依存関係で3.10指定
- Serverless Framework
- DynamoDB
- S3
- Docker (ARM64)

### フロントエンド
- Nuxt 3 / Vue 3
- Vuetify 3
- Pinia (状態管理)
- TypeScript

## ディレクトリ構成
```
/deploy          - Serverless設定、Dockerfile
/src/handlers    - Lambda関数
/src/utils       - 共通ユーティリティ
/web-ui          - Nuxt.jsフロントエンド
/scripts         - 運用スクリプト
/config          - 設定ファイル
```

## DynamoDBテーブル
- `wows-replays-{stage}` - リプレイデータ本体
- `wows-ship-match-index-{stage}` - 艦艇検索インデックス
- `wows-sessions-{stage}` - ユーザーセッション

## デプロイ

### GitHub Actions経由（推奨）
```bash
git push origin main  # dev環境へ自動デプロイ
```

### 手動デプロイ(基本禁止)
```bash
# Lambda
cd deploy && npx serverless deploy --stage dev --region ap-northeast-1

# Web UI
cd web-ui && npm run generate && aws s3 sync .output/public s3://wows-replay-web-ui-prod
```

## 開発コマンド

### Linting
```bash
cd src && black . && flake8 .
```

### ログ確認
```bash
aws logs tail /aws/lambda/wows-replay-bot-dev-search-api --region ap-northeast-1 --since 30m
aws logs tail /aws/lambda/wows-replay-bot-dev-battle-result-extractor --region ap-northeast-1 --since 30m
```

### バックフィル
```bash
python3 scripts/backfill_ship_index.py  # 艦艇インデックス再構築
```

## コーディング規約

### Python
- フォーマッタ: black
- リンター: flake8
- 行長: 120文字

### TypeScript/Vue
- Composition API使用
- Pinia for 状態管理

## 注意事項

### DynamoDB
- 予約語（`dateTime`など）は `#dateTime` + ExpressionAttributeNames で回避
- 日付形式: DynamoDB内は `DD.MM.YYYY HH:MM:SS`、フロントエンドは `YYYY-MM-DD`
- KeyConditionExpressionは1キーにつき1条件。範囲は `BETWEEN` を使用

### 検索機能
- 艦艇名検索は `normalize_ship_name()` で正規化（大文字小文字対応）
- 日付フィルタはPython側で実行（DynamoDB形式との互換性のため）
- カーソルベースページネーション（30件/ページ）

### IAM権限
- Lambda関数がDynamoDBにアクセスする場合、`serverless.yml`のiamRoleStatementsに権限を追加
- `BatchWriteItem`等の権限漏れに注意

## よくある問題と解決策

### 検索が動かない
1. CloudWatchログを確認: `aws logs tail /aws/lambda/wows-replay-bot-dev-search-api`
2. DynamoDB権限を確認: `deploy/serverless.yml`のiamRoleStatements
3. 環境変数を確認: `SHIP_MATCH_INDEX_TABLE`など

### デプロイ失敗
1. GitHub Actionsのログを確認
2. ECRイメージのビルドエラーを確認
3. Serverless Frameworkのエラーメッセージを確認
4. Cloudformationの状態を確認

## 今後の予定
- 被ダメ、潜在ダメージ、critsの数値修正
- CD(ビルド)の高速化
- 検索機能の高速化、最適化設計
- Auto uploader経由のリプレイアップロード時(レンダラー作成やDynamoDBへの統計データの格納完了時)にDiscord通知
- クラン戦シーズン毎のデータ表示
- 過去データのクリーンナップタスクの追加(一定時間たったリプレイファイルの保管は不要。レンダラーファイルと統計データのみを残す設計で良いかは要検討)
- 複数テナント化（マルチテナント）設計
- 各種FAQ追加
- dynamodbのデータの中身についてclaudeに質問する機能の追加
- 本サービスのランディングページ追加