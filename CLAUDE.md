# Claude Code Project Rules

## 重要: タスク完了時のルール
**毎回タスクが完了したら、このCLAUDE.mdを更新すること。**
- 完了したタスクを「今後の予定」から削除
- 新たに判明した注意事項を追加
- 変更があった技術的な情報を更新

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
- `wows-analysis-usage-{stage}` - Claude AI分析API使用量管理

## デプロイ

### GitHub Actions経由（推奨）
```bash
git push origin main     # prod環境へ自動デプロイ
git push origin develop  # dev環境へ自動デプロイ
```
手動デプロイ(基本禁止)

### CI/CD最適化（2026-01-08実施済み）
- npmキャッシュ: Serverless Frameworkインストール高速化
- Dockerレイヤー最適化: 変更頻度の低いレイヤーを先に配置

## 開発コマンド

### Linting
```bash
cd src && black . && flake8 .
```


### バックフィル
```bash
python3 scripts/backfill_ship_index.py  # 艦艇インデックス再構築
python3 scripts/backfill_search_optimization.py  # 検索最適化フィールド追加（matchKey, dateTimeSortable）
python3 scripts/backfill_battlestats.py  # BattleStats詳細フィールド追加（被ダメ内訳、潜在内訳、crits等）
python3 scripts/backfill_captain_skills.py  # 艦長スキル追加
python3 scripts/backfill_ship_class.py  # 艦種（shipClass）追加
python3 scripts/backfill_skills_japanese.py  # 艦長スキル日本語化
python3 scripts/backfill_winloss.py  # 勝敗情報追加（全ゲームタイプ対応）
# DRY_RUN=true で実行すると、書き込みなしで対象レコードを確認可能
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
- **最適化フィールド（2026-01-08追加）**:
  - `matchKey`: 試合グループ化キー（事前計算）
  - `dateTimeSortable`: ソート可能な日時形式（YYYYMMDDHHMMSS）
  - 新規レコードは自動追加、既存レコードはバックフィルスクリプトで追加

### IAM権限
- Lambda関数がDynamoDBにアクセスする場合、`serverless.yml`のiamRoleStatementsに権限を追加
- `BatchWriteItem`等の権限漏れに注意

### Discord通知
- クラン戦のみ通知（`gameType == "clan"` で判定）
- `generate-video-api` Lambda で動画生成完了時に送信
- 環境変数: `NOTIFICATION_CHANNEL_ID`, `DISCORD_BOT_TOKEN`
- 通知ユーティリティ: `src/utils/discord_notify.py`

### Claude AIデータ分析
- エンドポイント: POST /api/analyze
- 認証: Discord OAuth2セッション必須
- レート制限: 1日5クエリ、50,000トークン上限、30秒クールダウン
- 使用モデル: claude-sonnet-4-20250514
- 使用量テーブル: `wows-analysis-usage-{stage}` (TTL: 7日)
- フロントエンド: `/analyze` ページ
- **デプロイ前に環境変数設定必須**: `ANTHROPIC_API_KEY`

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
- **Claude AIデータ分析機能（2026-01-23）**:
  - 戦闘データについてClaude AIに自然言語で質問できる機能
  - レート制限: 1日5クエリ、50,000トークン、30秒クールダウン
  - バックエンド: `src/utils/rate_limiter.py`, `src/utils/data_aggregator.py`, `src/utils/claude_client.py`
  - API: `src/handlers/api/analyze.py` (POST /api/analyze)
  - フロントエンド: `/analyze` ページ、useAnalysis composable、analysis store
  - 環境変数: `ANTHROPIC_API_KEY`, `ANALYSIS_USAGE_TABLE`
  - 単体テスト: `src/tests/test_data_aggregator.py`, `src/tests/test_rate_limiter.py`
- **replay_unpack v15.0.0.0対応（2026-01-21）**:
  - replays_unpack_upstreamサブモジュールを最新版に更新（15.0.0サポート含む）
  - ローカルの`src/replay_versions/15_0_0/`を削除し、upstreamを直接使用
  - minimap_rendererも15.0.0対応済み
- **新DynamoDBテーブル構造と動画再生修正（2026-01-20）**:
  - gameType別テーブル（clan, ranked, random, other）への移行完了
  - 検索APIにreplays配列を追加し動画再生をサポート
  - S3 URLのダブルスラッシュ問題を修正
  - 動画生成時に新テーブルへの書き込みを追加
  - 初回アップロード者列から不要な艦艇名表示を削除
- **Dual Render機能（2026-01-10）**: 敵味方両チームのリプレイがある場合に両陣営視点動画を自動生成
  - `src/utils/dual_render.py`: チーム判定ユーティリティ
  - `src/core/replay_processor.py`: `generate_dual_minimap_video()` メソッド追加
  - `src/utils/dynamodb.py`: Dual関連DB操作（`dualMp4S3Key`, `hasDualReplay`）
  - `src/handlers/api/generate_video.py`: Dual動画生成対応
  - `src/handlers/processing/battle_result_extractor.py`: Dual検出ロジック
  - フロントエンド: 検索結果にDualバッジ、詳細画面で両陣営視点表示

## 今後の予定
- リプレイ処理統合テスト実装
- クラン戦シーズン毎のデータ表示
- 過去データのクリーンナップタスクの追加(一定時間たったリプレイファイルの保管は不要。レンダラーファイルと統計データのみを残す設計で良いかは要検討)
- 複数テナント化（マルチテナント）設計
- 各種FAQ追加
- 本サービスのランディングページ追加