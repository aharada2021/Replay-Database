# Claude Code Project Rules

## 重要: タスク完了時のルール
**毎回タスクが完了したら、このCLAUDE.mdを更新すること。**
- 完了したタスクを「今後の予定」から削除
- 新たに判明した注意事項を追加
- 変更があった技術的な情報を更新

## プロジェクト概要
World of Warshipsのリプレイファイルを管理・分析するWebアプリケーション。Web UIとDiscord OAuth認証・クラン戦通知を提供。

## 技術スタック

### バックエンド
- Python 3.12 (AWS Lambda)
- Serverless Framework
- DynamoDB
- S3
- Docker (ARM64, 全Lambda共通イメージ `Dockerfile.lambda`)
- Rust wows-replay-tool（リプレイ抽出・レンダリング）

### フロントエンド
- Nuxt 4 / Vue 3
- Vuetify 3
- Pinia 3 (状態管理)
- TypeScript

## ディレクトリ構成
```
/deploy          - Serverless設定、Dockerfile
/src/handlers    - Lambda関数
  /api           - REST API ハンドラー
  /processing    - S3トリガー等の処理ハンドラー
/src/core        - コアロジック（replay_processor, replay_metadata）
/src/utils       - 共通ユーティリティ
/web-ui          - Nuxt.jsフロントエンド
  /app           - Nuxt 4 ソースディレクトリ（pages, components, composables, stores, plugins, middleware, types）
/scripts         - 運用スクリプト（generate_ja_mo, upload_game_data, migrate_dynamodb, rebuild_dynamodb等）
/config          - 設定ファイル
/client_tool     - Windows用リプレイアップローダークライアント
  /capture       - ゲームキャプチャモジュール（screen, audio, video encoder）
/rust            - Rust wows-replay-tool ソース
```

## DynamoDBテーブル
- `wows-replays-{stage}` - リプレイデータ本体（旧、移行完了後に削除予定）
- `wows-{clan,ranked,random,other}-battles-{stage}` - gameType別バトルテーブル
- `wows-{ship,player,clan}-index-{stage}` - 検索インデックス
- `wows-ship-match-index-{stage}` - 艦艇検索インデックス（旧）
- `wows-sessions-{stage}` - ユーザーセッション
- `wows-comments-{stage}` - コメント

## デプロイ

### GitHub Actions経由（推奨）
```bash
git push origin main     # prod環境へ自動デプロイ
git push origin develop  # dev環境へ自動デプロイ
```
手動デプロイ(基本禁止)

## 開発コマンド

### Linting
```bash
cd src && black . && flake8 .
```

### 運用スクリプト
```bash
python3 scripts/generate_ja_mo.py      # 日本語MOファイル生成
python3 scripts/upload_game_data.py     # ゲームデータをS3にアップロード
python3 scripts/rebuild_dynamodb.py     # S3リプレイからDynamoDBレコード再構築
python3 scripts/migrate_dynamodb.py     # dev→prod データ移行
python3 scripts/migrate_to_new_schema.py # スキーマ移行
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
- **GSI変更制限**: CloudFormationで1回の更新につき1つのGSIしか追加/削除できない
- **GSI一覧（2026-01-09更新）**:
  - `GameTypeSortableIndex`: gameType + dateTimeSortable（使用中）
  - `MapIdSortableIndex`: mapId + dateTimeSortable（使用中）
  - `PlayerNameIndex`: playerName + dateTime（将来のプレイヤー検索用に維持）
  - ~~`GameTypeIndex`~~: 削除済み（2026-01-09）
  - ~~`MapIdIndex`~~: 削除済み（2026-01-09）

### 検索機能
- 艦艇名検索は `normalize_ship_name()` で正規化（大文字小文字対応）
- 日付フィルタはPython側で実行（DynamoDB形式との互換性のため）
- カーソルベースページネーション（30件/ページ）
- `matchKey`: 試合グループ化キー（事前計算）
- `dateTimeSortable`: ソート可能な日時形式（YYYYMMDDHHMMSS）

### 一時arenaID (Temp Arena ID)
- クライアントは試合開始時に`tempArenaInfo.json`からMD5ハッシュ（16桁hex）を生成して一時IDとして使用
- 正式な`arenaUniqueID`はリプレイファイル処理後に判明
- 判定: `is_temp_arena_id()` - 16桁hex かつ 全数字でない（`src/utils/dynamodb_tables.py`）

### 動画アップロードフロー（2026-02-04改訂）
- **フロー**: 動画を先にアップロード → S3キーをリプレイアップロード時にヘッダーで渡す → `battle_result_extractor`が正式パスに移行
- **動画一時パス**: `pending-videos/{uuid_hex16}/capture.mp4`（UUID生成、tempArenaIDとは無関係）
- **API**:
  - `POST /api/upload/video/presign`: 動画アップロード用Presigned URL生成（小ファイル: single PUT、大ファイル: multipart）
  - `POST /api/upload/video/complete`: マルチパートアップロード完了（S3操作のみ、DB操作なし）
  - `POST /api/upload/video/abort`: マルチパートアップロード中止
  - `POST /api/upload`: リプレイアップロード時に`X-Video-S3-Key`ヘッダーで動画S3キーを渡す
- **サーバー処理**: `battle_result_extractor`がDynamoDBレコードの`pendingVideoS3Key`を読み取り、正式パス（`gameplay-videos/{arenaUniqueID}/{playerID}/capture.mp4`）にS3コピー＆旧パス削除
- **例外処理**: 動画アップロード失敗時もリプレイのみアップロードを続行（クライアント側でcatch）

### IAM権限
- Lambda関数がDynamoDBにアクセスする場合、`serverless.yml`のiamRoleStatementsに権限を追加
- `BatchWriteItem`等の権限漏れに注意

### Discord連携（認証+通知のみ）
- **認証**: Discord OAuth2（`src/handlers/api/auth.py`）、セッション管理（`wows-sessions-{stage}`）
- **通知**: クラン戦のみ通知（`gameType == "clan"`）、`src/utils/discord_notify.py`
- 環境変数: `DISCORD_APPLICATION_ID`, `DISCORD_BOT_TOKEN`, `DISCORD_CLIENT_SECRET`, `NOTIFICATION_CHANNEL_ID`
- ~~スラッシュコマンド~~: 削除済み（2026-03-11）

## よくある問題と解決策

### 検索が動かない
1. CloudWatchログを確認
2. DynamoDB権限を確認: `deploy/serverless.yml`のiamRoleStatements
3. 環境変数を確認: `SHIP_MATCH_INDEX_TABLE`など

### デプロイ失敗
1. GitHub Actionsのログを確認
2. ECRイメージのビルドエラーを確認
3. Serverless Frameworkのエラーメッセージを確認
4. Cloudformationの状態を確認

## 完了したタスク
- **コードベースクリーンアップ（2026-03-11）**:
  - Discord Botスラッシュコマンド機能削除: `src/handlers/discord/`, `replay_analyzer.py`, `video_generator.py`, `src/scripts/`
  - serverless.yml: `interactions`, `replay-analyzer`, `video-generator` Lambda関数削除
  - 環境変数削除: `DISCORD_PUBLIC_KEY`, `INPUT_CHANNEL_ID`, `GUILD_ID`
  - バックフィルスクリプト13本削除（全て実行済み・通常フローに統合済み）
  - download API: `?file=uploader` 機能削除（GitHub Releasesに移行済み）
  - Python 3.10 → 3.12 アップグレード
- **Dockerfile統合: extractor/processor → 単一lambda（2026-03-11）**:
  - `deploy/Dockerfile.lambda`: 統合Dockerfile（CMDは`serverless.yml`の`image.command`で上書き）
  - `.github/workflows/deploy-lambda.yml`: ビルドジョブ統合（2→1）
- **Rust移行 Phase 4: 旧Pythonパーサー/サブモジュール完全除去（2026-03-11）**:
  - サブモジュール削除: `minimap_renderer/`, `replays_unpack_upstream/`, `.gitmodules`
  - ディレクトリ削除: `src/parsers/`, `src/replay_versions/`
  - `battle_result_extractor.py`: Python fallback除去、Rust常時使用化
  - `requirements_lambda.txt`: pycryptodomex/packaging/lxml除去
- **Rust移行 Phase 3: レンダリングパイプラインRust化（2026-03-11）**:
  - Processor LambdaでRust `wows-replay-tool render` サブプロセスを使用
  - Dual Render一時無効化（既存dual動画は後方互換で参照可能）
- **Rust抽出パイプライン移行 Phase 2（2026-03-11）**:
  - `rust/wows-replay-tool` の `extract` サブコマンドでリプレイ抽出をRustで実行
  - 翻訳: `WOWS_LANG` 環境変数（デフォルト `ja`、フォールバック `en`）
- **動画アップロードフロー リアーキテクチャ（2026-02-04）**
- **ゲームプレイ動画キャプチャ バグ修正（2026-02-01）**
- **クライアントツール配布方法をGitHub Releasesに変更（2026-02-01）**
- **ゲームプレイ動画アップロード機能（2026-02-01、2026-02-04リアーキテクチャ）**
- **ゲームキャプチャ機能（2026-01-31）**
- **Nuxt 4 移行（2026-01-27）**
- **新DynamoDBテーブル構造と動画再生修正（2026-01-20）**
- **Dual Render機能（2026-01-10）**

## 今後の予定
- **Dual Render Rust再実装**: wows-replay-toolにdual renderサブコマンド追加
- wows-toolkitパッチのupstream PR提出
- リプレイ処理統合テスト実装
- クラン戦シーズン毎のデータ表示
- 過去データのクリーンナップタスクの追加(一定時間たったリプレイファイルの保管は不要。レンダラーファイルと統計データのみを残す設計で良いかは要検討)
- 複数テナント化（マルチテナント）設計
- 各種FAQ追加
- dynamodbのデータの中身についてclaudeに質問する機能の追加
- 本サービスのランディングページ追加
