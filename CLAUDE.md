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

## デプロイ

### GitHub Actions経由（推奨）
```bash
git push origin main  # dev環境へ自動デプロイ（約2分）
```

### 手動デプロイ(基本禁止)
```bash
# Lambda
cd deploy && npx serverless deploy --stage dev --region ap-northeast-1

# Web UI
cd web-ui && npm run generate && aws s3 sync .output/public s3://wows-replay-web-ui-prod
```

### CI/CD最適化（2026-01-08実施済み）
- npmキャッシュ: Serverless Frameworkインストール高速化
- Dockerレイヤー最適化: 変更頻度の低いレイヤーを先に配置
- 詳細: `docs/CD_OPTIMIZATION_PLAN.md`

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
python3 scripts/backfill_search_optimization.py  # 検索最適化フィールド追加（matchKey, dateTimeSortable）
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

## 完了したタスク
### マッチ詳細ページ直接遷移機能（2026-01-08完了）
- Discord通知にリンク追加済み（`src/utils/discord_notify.py`）
- バックエンドAPI正常動作確認済み（`/api/match/{arenaUniqueID}`）
- CloudFront設定正常（エラーページでindex.htmlにリダイレクト設定済み）
- **修正内容**: APIレスポンスのJSONパース処理追加、`data.replays`のnullチェック追加

### マッチ詳細ページ表示内容アップデート（2026-01-08完了）
- `MatchDetailExpansion`コンポーネントを再利用して検索一覧と同じUXを実現
- 戦闘統計スコアボード表示（撃沈、与ダメ、観測、被ダメ、潜在、命中、火災、浸水、Crits、XP）
- クラン対戦情報表示（[味方クラン] vs [敵クラン]）
- コンパクトなヘッダーに試合情報を集約
- マップ名を日本語表示に変更（`useMapNames`composable使用）

### Discord認証のギルド・ロール設定変更（2026-01-08完了）
- ギルドID: `487923834868072449`に変更
- ロールベースアクセス制御を追加: `487924554111516672`, `1458737823585927179`
- OAuth2スコープに`guilds.members.read`を追加
- 許可されたロールを持つユーザーのみアクセス可能に

### 検索機能の高速化・最適化（2026-01-08完了）
**短期改善（既存データ構造変更なし）**:
- Lambda memorySize: 256MB → 512MB（CPU性能向上）
- 日時パースのメモ化（`@lru_cache`）
- 単一パスフィルタリング（4-5回の走査を1回に）
- fetch_multiplier動的化（検索条件に応じて5-25で調整）

**中期改善（データ構造拡張）**:
- `matchKey`/`dateTimeSortable`の事前計算（`battle_result_extractor.py`で追加）
- バックフィルスクリプト作成（`scripts/backfill_search_optimization.py`）
- 検索ロジックで事前計算値を優先使用

**期待効果**: レスポンス時間 50-70% 短縮（3-5秒 → 1-2秒）

**バックフィル実行手順**:
1. `DRY_RUN=true python3 scripts/backfill_search_optimization.py` で対象確認
2. `python3 scripts/backfill_search_optimization.py` で本番実行

### BattleStatsフィールドマッピング修正（2026-01-08完了）
- 被ダメージ内訳: `received_damage_ap`(202), `received_damage_he`(204), `received_damage_torps`(205)等
- 潜在ダメージ内訳: `potential_damage_art`(419), `potential_damage_tpd`(420)
- リボン: `citadels`(457), `crits`(453), `kills`(454), `fires`(455), `floods`(456)
- 更新ファイル: `src/parsers/battlestats_parser.py`

### 艦長スキル・艦艇コンポーネント抽出機能（2026-01-08完了）
- **艦長スキル**: `hidden['crew']['learned_skills']`から抽出
  - 内部名→表示名マッピング: `src/utils/captain_skills.py`
  - 80種類以上のスキル名マッピング（WoWS 14.x準拠）
- **艦艇コンポーネント**: `hidden['players'][id]['shipComponents']`から抽出
  - 船体、主砲、魚雷、エンジン等のバリアント（A, B, AB1等）
  - `src/utils/ship_modules.py`
- **統合**: `battle_result_extractor.py`で`allPlayersStats`に含める
  - `captainSkills`: スキル名の配列
  - `shipComponents`: コンポーネント辞書（`{"hull": "A", "artillery": "B", ...}`）
- **注意**: 敵プレイヤーのデータは取得不可（ゲームの仕様）
- **未実装**: アップグレード（近代化改修）はゲームデータファイルが必要

## 今後の予定
- リプレイ処理統合テスト実装（計画書: `docs/INTEGRATION_TEST_PLAN.md`）
- アップグレード（近代化改修）抽出機能（ゲームデータファイル連携が必要）
- クラン戦シーズン毎のデータ表示
- 過去データのクリーンナップタスクの追加(一定時間たったリプレイファイルの保管は不要。レンダラーファイルと統計データのみを残す設計で良いかは要検討)
- 複数テナント化（マルチテナント）設計
- 各種FAQ追加
- dynamodbのデータの中身についてclaudeに質問する機能の追加
- 本サービスのランディングページ追加