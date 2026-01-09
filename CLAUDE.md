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
git push origin main     # prod環境へ自動デプロイ
git push origin develop  # dev環境へ自動デプロイ
```

### 環境分離（2026-01-09実施）
| 項目 | 本番環境 (prod) | 開発環境 (dev) |
|------|----------------|---------------|
| ブランチ | main | develop |
| Web UI | https://wows-replay.mirage0926.com | https://dev-wows-replay.mirage0926.com |
| CloudFront | (GitHub Secrets参照) | (GitHub Secrets参照) |
| S3 (Web UI) | wows-replay-web-ui-prod | wows-replay-web-ui-dev |
| S3 (一時ファイル) | wows-replay-bot-prod-temp | wows-replay-bot-dev-temp |
| DynamoDB | wows-replays-prod | wows-replays-dev |
| Discord App | 本番用 | 開発用（別アプリ） |

### 手動デプロイ(基本禁止)
```bash
# Lambda
cd deploy && npx serverless deploy --stage prod --region ap-northeast-1

# Web UI
cd web-ui && npm run generate && aws s3 sync .output/public s3://wows-replay-web-ui-prod
```

### CI/CD最適化（2026-01-08実施済み）
- npmキャッシュ: Serverless Frameworkインストール高速化
- Dockerレイヤー最適化: 変更頻度の低いレイヤーを先に配置

## GitHub Secrets（必須設定）

### Lambda Backend (`deploy-lambda.yml`)
| Secret名 | 説明 | 例 |
|----------|------|-----|
| `AWS_ACCESS_KEY_ID` | AWSアクセスキー | - |
| `AWS_SECRET_ACCESS_KEY` | AWSシークレットキー | - |
| `DISCORD_PUBLIC_KEY` | Discord Bot公開鍵 | - |
| `DISCORD_APPLICATION_ID` | Discordアプリケーション ID | - |
| `DISCORD_BOT_TOKEN` | Discord Botトークン | - |
| `DISCORD_CLIENT_SECRET` | Discord OAuth2シークレット | - |
| `INPUT_CHANNEL_ID` | 入力チャンネルID | - |
| `GUILD_ID` | Discord サーバーID | - |
| `UPLOAD_API_KEY` | リプレイアップロード用APIキー | - |
| `FRONTEND_URL` | フロントエンドURL | `https://wows-replay.example.com` |
| `ALLOWED_GUILD_ID` | アクセス許可するギルドID | - |
| `ALLOWED_ROLE_IDS` | アクセス許可するロールID（カンマ区切り） | - |

### Web UI (`deploy-web-ui.yml`) - 環境別Secrets
| Secret名 | 説明 | production例 | development例 |
|----------|------|-------------|---------------|
| `CLOUDFRONT_DISTRIBUTION_ID` | CloudFront ID | (prod用ID) | (dev用ID) |
| `S3_BUCKET_WEB_UI` | Web UI用S3バケット | `wows-replay-web-ui-prod` | `wows-replay-web-ui-dev` |
| `CUSTOM_DOMAIN` | カスタムドメイン | `wows-replay.example.com` | `dev.wows-replay.example.com` |
| `S3_BUCKET_URL` | 動画配信S3 URL | `https://...-prod-temp.s3...` | `https://...-dev-temp.s3...` |

### 環境変数化の方針（2026-01-09実施）
- ハードコードされていたFQDN/URLをすべてGitHub Secretsから環境変数として注入
- Python/Vue/client_tool全てでFRONTEND_URLを環境変数から取得
- CORSオリジンもFRONTEND_URL環境変数を使用

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
- ギルドID: GitHub Secretsで設定
- ロールベースアクセス制御を追加（GitHub Secretsで設定）
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

### BattleStats詳細フィールドのバックフィル（2026-01-08完了）
- 既存のDynamoDBレコードに被ダメージ内訳、潜在ダメージ内訳、crits等を追加
- バックフィルスクリプト: `scripts/backfill_battlestats.py`
- 実行結果: 232試合、3,588プレイヤー統計を更新
- ツールチップで実データが表示されることを確認

### GSI検索順序修正（2026-01-09完了）
- **問題**: `GameTypeIndex`のソートキー`dateTime`がDD.MM.YYYY形式のため、年をまたぐと正しくソートされない
  - 例: "01.01.2026" < "29.12.2025"（文字列比較では0 < 2）
- **解決**: 新しいGSIを追加（`dateTimeSortable`をソートキーに使用）
  - `GameTypeSortableIndex`: gameType + dateTimeSortable
  - `MapIdSortableIndex`: mapId + dateTimeSortable
- **注意**: DynamoDBは1回の更新で1つのGSIしか追加できない
- 更新ファイル: `deploy/serverless.yml`, `src/utils/dynamodb.py`

### 艦長スキル抽出機能（2026-01-08完了）
- **艦長スキル**: `hidden['crew']['learned_skills']`から抽出
  - 内部名→表示名マッピング: `src/utils/captain_skills.py`
  - 80種類以上のスキル名マッピング（WoWS 14.x準拠）
- **統合**: `battle_result_extractor.py`で`allPlayersStats`に含める
  - `captainSkills`: スキル名の配列
- **注意**: 全プレイヤー（味方・敵問わず）のデータが取得可能

### 艦長スキル表示バグ修正と艦種表示追加（2026-01-09完了）
- **バグ**: 艦長スキルが誤った艦種のスキルセットを表示していた
  - 原因: 艦長は駆逐/巡洋/戦艦/空母/潜水艦の各スキルセットを持てるが、固定順で最初に見つかったセットを使用していた
  - 修正: `shipParamsId`から`ships.json`を参照して正しい艦種（species）を特定
  - 対応ファイル: `src/utils/captain_skills.py`
- **艦種表示機能**:
  - バックエンド: `battle_result_extractor.py`で`shipClass`フィールドを`allPlayersStats`に追加
  - フロントエンド: スコアボードに艦種アイコン列を追加
  - アイコン: `web-ui/public/icons/ships/`（Destroyer, Cruiser, Battleship, AirCarrier, Submarine, Auxiliary）
  - composable: `web-ui/composables/useShipClass.ts`（艦種名、短縮名、アイコンURL）
- **艦種データソース**: `minimap_renderer/src/renderer/versions/14_11_0/resources/ships.json`
- **バックフィル実行**: 237試合、3,708件のshipClassを追加（`scripts/backfill_ship_class.py`）

### 艦長スキル日本語化（2026-01-09完了）
- **概要**: 英語のスキル名を日本語に変換して表示
- **実装内容**:
  - `SKILL_DISPLAY_TO_JAPANESE`マッピング追加（約100スキル）: `src/utils/captain_skills.py`
  - `map_player_to_skills`関数を`language="ja"`で日本語出力に変更
  - データソース: WoWS公式Wiki（日本語版）
- **バックフィル実行**: 237試合、24,503件のスキル名を日本語化（`scripts/backfill_skills_japanese.py`）
- **注意**: 新規リプレイは自動的に日本語で保存される

### アップグレード（近代化改修）表示機能（2026-01-09完了）
- **概要**: リプレイから各プレイヤーのアップグレード（近代化改修）情報を抽出・表示
- **実装内容**:
  - `src/utils/upgrades.py`: アップグレード抽出ユーティリティ
    - `decode_ship_config_dump()`: リプレイの`shipConfigDump`バイナリをデコード
    - `map_player_to_upgrades()`: プレイヤー名→アップグレードリスト
    - PCMコード→日本語名マッピング（118アップグレード対応）
  - `src/utils/modernizations.json`: アップグレードID→PCMコードマッピング
  - `battle_result_extractor.py`: `allPlayersStats`に`upgrades`配列を追加
  - フロントエンド: プレイヤー名ホバーでアップグレード表示（青色チップ）
- **データソース**: `minimap_renderer/src/renderer/data/modernizations.json`
- **注意**: 艦長スキル同様、全プレイヤー（味方・敵問わず）のデータが取得可能
- **バックフィル実行**: 237試合、3,431件のアップグレードを追加（`scripts/backfill_upgrades.py`）

### 艦長スキル日本語翻訳修正（2026-01-09完了）
- **概要**: WoWS公式クライアントの日本語表記に合わせて翻訳を修正
- **修正内容**:
  - 駆逐艦: 歯車のグリスアップ、水浸し、消耗品技術者、敵弾接近警報、高速魚雷、特重弾薬、危険察知、主砲・対空兵装技術者/専門家
  - 巡洋艦: 上空の眼、強烈な打撃力、最上級砲手、数的劣勢
  - 戦艦: 応急対応の基本、改良型修理班準備、猛烈、接近戦
  - 空母: 最後の奮闘、戦闘機指揮所、索敵掃討、爆撃機の飛行制御、隠れた脅威
  - 潜水艦: 強化型ソナー、改良型バッテリー容量、ソナー操作員、用心、魚雷誘導マスター
- **バックフィル実行**: 237試合、4,944件のスキル名を再翻訳（`scripts/backfill_skills_retranslate.py`）

### スコアボードデフォルトソート順変更（2026-01-09完了）
- **概要**: 戦闘統計スコアボードのデフォルト表示順を変更
- **ソート順**:
  1. チーム: 味方 → 敵
  2. 艦種: 空母 → 戦艦 → 巡洋艦 → 駆逐艦 → 潜水艦
  3. 経験値: 高い順
  4. ダメージ: 高い順
- **追加機能**: ヘッダークリックでソート変更後、「デフォルト順に戻す」ボタン表示

### 勝敗判定の全ゲームタイプ対応（2026-01-09完了）
- **問題**: 従来の勝敗判定はXP固定値（勝利:30,000XP、敗北:15,000XP）で判定していたため、クラン戦以外では動作しなかった
- **解決**: `hidden['battle_result']['winner_team_id']`とプレイヤーの`teamId`を比較する新方式を追加
- **実装内容**:
  - `get_win_loss_from_hidden()`: `src/parsers/battle_stats_extractor.py`
  - 判定ロジック:
    - `winner_team_id == own_team_id` → win
    - `winner_team_id != own_team_id` → loss
    - `winner_team_id == -1` or `None` → draw
- **フォールバック**: hiddenデータから取得できない場合は従来のXP判定を使用
- **対応ゲームタイプ**: ランダム戦、ランク戦、クラン戦、Co-op戦 等すべて
- **バックフィル実行**: 55件の勝敗情報を更新（勝利:48、敗北:7）- `scripts/backfill_winloss.py`

### セッション有効期限の延長（2026-01-09完了）
- **変更**: セッションTTLを24時間から1ヶ月（30日）に延長
- **対象ファイル**: `src/handlers/api/auth.py`
- **設定値**: `SESSION_TTL = 30 * 24 * 60 * 60`（2,592,000秒）
- Cookieの有効期限も同様に1ヶ月

### GSI最適化（2026-01-09完了）
- **目的**: 不要なGSIを削除してDynamoDB書き込みコストを削減
- **実施内容**:
  - Phase 1: `MapIdIndex`を削除（未使用、`MapIdSortableIndex`で代替可能）
  - Phase 1: `GameTypeIndex`の参照を`GameTypeSortableIndex`に変更
    - `src/handlers/processing/battle_result_extractor.py`
    - `src/handlers/api/match_detail.py`
  - Phase 2: `GameTypeIndex`を削除（安定稼働確認後に実施）
- **効果**: 書き込みコスト約40%削減（GSI 5→3）
- **最終GSI構成**: GameTypeSortableIndex, MapIdSortableIndex, PlayerNameIndex

### クラン戦分析レポート機能（2026-01-09完了）
- **概要**: DynamoDBのクラン戦データをClaudeが分析してレポート生成
- **出力**: `reports/clan_battle_analysis_2025-12-25.md`
- **分析内容**:
  - マップ別勝率
  - 時間帯・曜日別勝率
  - 敵艦艇別勝率（苦手/得意）
  - 味方プレイヤー別勝率
  - プレイヤー組み合わせ（ペア相性）
  - Alaska構成に対する勝率
- **注意**: 勝敗判定は`baseXP > 250`で行っている

### リポジトリ公開準備（2026-01-09完了）
- **AGPL-3.0ライセンス対応**: minimap_rendererがAGPL-3.0のため、リポジトリを公開する必要あり
- **セキュリティ監査**:
  - ハードコードされたシークレットなし（すべて環境変数経由）
  - Discord Guild/Role IDのデフォルト値を削除
  - GitHub Secretsに `ALLOWED_GUILD_ID`, `ALLOWED_ROLE_IDS` を設定
- **Gitヒストリークリーンアップ**:
  - `reports/` をgitignoreに追加、git履歴から完全削除（git-filter-repo使用）
  - `private/` ディレクトリを作成し、内部ドキュメント・調査スクリプトを移動
- **private/ディレクトリ**（gitignore済み、ローカル保持）:
  - `private/scripts/`: 調査・デバッグ用スクリプト9ファイル
  - `private/docs/`: 完了済み計画・内部技術ドキュメント9ファイル

### 本番環境と開発環境の分離（2026-01-09完了）
- **概要**: GitFlow（main→prod, develop→dev）によるデプロイフロー整備
- **AWSリソース作成（prod）**:
  - `wows-replays-prod`: DynamoDB（CloudFormation管理、3 GSI）
  - `wows-ship-match-index-prod`: DynamoDB
  - `wows-sessions-prod`: DynamoDB
  - `wows-replay-bot-prod-temp`: S3（手動作成）
- **AWSリソース作成（dev）**:
  - `wows-replay-web-ui-dev`: S3
  - CloudFront: S3 + API Gateway両方をorigin
  - ACM証明書: dev-wows-replay.mirage0926.com
  - Route53: dev-wows-replay.mirage0926.com → CloudFront
- **データ移行**: dev→prodへ242試合、2986艦艇インデックス、531 S3オブジェクト（1.3GB）を移行
- **GitHub Actions変更**:
  - `deploy-lambda.yml`: main push→prod, develop push→dev
  - `deploy-web-ui.yml`: 同様のブランチ対応
  - S3トリガー: serverless.ymlで管理（`existing: true`）
- **スクリプト追加**: `scripts/migrate_dynamodb.py`（DynamoDB移行）
- **GitHub Environments**: production / development 各14シークレット設定
- **開発用Discord App**: 別アプリケーションを使用（完全分離）
- **注意**: GitHub Actions用IAMユーザーに`cloudfront:CreateInvalidation`権限追加が必要

### ハードコードURL/FQDN環境変数化（2026-01-09完了）
- **概要**: ハードコードされていたURL/FQDNをすべてGitHub Secrets経由で環境変数として注入
- **対象ファイル**:
  - `.github/workflows/deploy-lambda.yml`: FRONTEND_URLをシークレット化
  - `.github/workflows/deploy-web-ui.yml`: CLOUDFRONT_DISTRIBUTION_ID, S3_BUCKET_PROD, CUSTOM_DOMAIN, S3_BUCKET_URLをシークレット化
  - `deploy/serverless.yml`: CORSオリジンにFRONTEND_URL環境変数を使用
  - `src/handlers/api/auth.py`, `src/handlers/api/download.py`: CORSオリジンにFRONTEND_URL使用
  - `src/utils/discord_notify.py`: web_ui_base_urlにFRONTEND_URL使用
  - `web-ui/nuxt.config.ts`: s3BucketUrl設定追加
  - `web-ui/components/MatchDetailExpansion.vue`: S3動画URLを設定から取得
  - `web-ui/app.vue`: サーバーURL表示・コピー機能追加
  - `client_tool/wows_replay_uploader.py`: api_base_url設定項目追加
- **client_tool変更**:
  - セットアップウィザードにサーバーURL入力ステップ追加
  - 設定ファイル（config.yaml）にapi_base_url保存
  - Web UIの「API Key」ダイアログを「自動アップローダー設定」に改名しサーバーURL表示追加
  - セットアップガイドも4ステップに更新
- **新規GitHub Secrets**: FRONTEND_URL, CLOUDFRONT_DISTRIBUTION_ID, S3_BUCKET_PROD, CUSTOM_DOMAIN, S3_BUCKET_URL

## 今後の予定
- リプレイ処理統合テスト実装
- クラン戦シーズン毎のデータ表示
- 過去データのクリーンナップタスクの追加(一定時間たったリプレイファイルの保管は不要。レンダラーファイルと統計データのみを残す設計で良いかは要検討)
- 複数テナント化（マルチテナント）設計
- 各種FAQ追加
- dynamodbのデータの中身についてclaudeに質問する機能の追加
- 本サービスのランディングページ追加