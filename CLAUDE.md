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
- Nuxt 4 / Vue 3
- Vuetify 3
- Pinia 3 (状態管理)
- TypeScript

## ディレクトリ構成
```
/deploy          - Serverless設定、Dockerfile
/src/handlers    - Lambda関数
/src/utils       - 共通ユーティリティ
/web-ui          - Nuxt.jsフロントエンド
  /app           - Nuxt 4 ソースディレクトリ（pages, components, composables, stores, plugins, middleware, types）
/scripts         - 運用スクリプト
/config          - 設定ファイル
/client_tool     - Windows用リプレイアップローダークライアント
  /capture       - ゲームキャプチャモジュール（screen, audio, video encoder）
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

### Discord通知
- クラン戦のみ通知（`gameType == "clan"` で判定）
- `generate-video-api` Lambda で動画生成完了時に送信
- 環境変数: `NOTIFICATION_CHANNEL_ID`, `DISCORD_BOT_TOKEN`
- 通知ユーティリティ: `src/utils/discord_notify.py`

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
- **動画アップロードフロー リアーキテクチャ（2026-02-04）**:
  - 問題: 動画アップロードとリプレイ処理が独立した非同期操作で、ArenaUniqueID解決のタイミング不整合が発生
  - 根本原因: 動画とリプレイのアップロードタイミングが分離されていたこと自体が不整合の原因
  - 解決策: 動画を先にUUID一時パスにアップロード → S3キーをリプレイアップロード時にヘッダーで渡す → サーバー側で一括処理
  - `src/handlers/api/upload_video.py`: 新規作成（動画presign/multipart専用ハンドラー）
    - `handle_presign()`: UUID生成、Presigned URL発行（single PUT or multipart）
    - `handle_complete_multipart()`: S3マルチパート完了（DB操作なし）
    - `handle_abort_multipart()`: マルチパート中止
  - `src/handlers/api/upload.py`: `X-Video-S3-Key`ヘッダー受付、`pending_video_s3_key`をDB保存
  - `src/utils/dynamodb.py`: `put_replay_record()`に`pending_video_s3_key`パラメータ追加
  - `src/handlers/processing/battle_result_extractor.py`: `migrate_gameplay_video()`がDBの`pendingVideoS3Key`を使用（S3 HEAD推測を廃止）
  - `client_tool/wows_replay_uploader.py`: アップロードフロー再構成（動画→リプレイ順序、例外処理強化）
  - `deploy/serverless.yml`: 旧エンドポイント削除、新エンドポイント追加、CORS `X-Video-S3-Key`許可
  - 削除: `src/handlers/api/upload_multipart.py`（`upload_video.py`に置換）
  - CloudFront: `/gameplay-videos/*` ビヘイビア追加（S3オリジンへルーティング、2026-02-01設定済み）
- **ゲームプレイ動画キャプチャ バグ修正（2026-02-01）**:
  - 動画時間圧縮問題修正: `video_encoder.py`
    - `-use_wallclock_as_timestamps 1`: 実時間タイムスタンプ使用で動画時間を正確に
    - `-vf fps=fps=30:round=near` + `-vsync cfr`: フレーム補間で固定フレームレート出力
  - マイク音声ノイズ問題修正: 常にFFmpegでミックスする方式に変更
    - `audio_capture.py`: `has_separate_mic()`がマイク有効時は常にTrueを返す
    - `audio_capture.py`: `get_mic_channels()`追加、`_capture_loop`はマイクバッファを消費しない
    - `video_encoder.py`: マイク音声を別WAVファイルに保存、FFmpegでリサンプリング＆ミックス
    - `manager.py`: 専用マイクスレッドでマイク音声をポーリング
    - FFmpegフィルタ: `pan=stereo|c0=c0|c1=c0`でモノラル→ステレオ変換、`amix`でミックス
  - 音声・映像同期修正: FFmpeg muxに同期オプション追加
    - `-async 1` と `aresample` フィルタで音ズレ補正
  - 動画アップロード失敗修正: S3マルチパートアップロード実装（※2026-02-04にリアーキテクチャ済み、詳細は上記参照）
  - テストスクリプト: `client_tool/test_ffmpeg_encoding.py` 新規作成
    - `--with-mic`オプションでマイクテスト対応
- **クライアントツール配布方法をGitHub Releasesに変更（2026-02-01）**:
  - `.github/workflows/build-client-tool.yml`: S3アップロードを削除し、GitHub Releaseを自動作成
  - `web-ui/app/app.vue`: ダウンロードURLをGitHub Releasesに変更
  - タグ形式: `client-v{version}`、ダウンロードURL: `/releases/latest/download/wows_replay_uploader.zip`
- **ゲームプレイ動画アップロード機能（2026-02-01、2026-02-04リアーキテクチャ）**:
  - クライアントツールでキャプチャした動画をS3にアップロードする機能
  - **現行フロー（2026-02-04〜）**: 動画先行アップロード → リプレイアップロード時にS3キー連携
    - `src/handlers/api/upload_video.py`: 動画presign/multipart専用ハンドラー
    - `src/handlers/api/upload.py`: `X-Video-S3-Key`ヘッダーで動画S3キー受付
    - `src/utils/dynamodb.py`: `pendingVideoS3Key`をDBレコードに保存
    - `src/handlers/processing/battle_result_extractor.py`: `migrate_gameplay_video()`で正式パスに移行
  - `client_tool/wows_replay_uploader.py`:
    - `PendingVideoQueue`クラス: 動画→リプレイのマッピング管理
    - `_upload_video_to_s3()`: 動画先行アップロード（presign API → S3 PUT/multipart）
    - 設定オプション: `upload_gameplay_video`, `keep_local_copy`, `max_upload_size_mb`
    - 例外処理: 動画アップロード失敗時もリプレイのみアップロード続行
  - `src/utils/dynamodb_tables.py`:
    - `update_gameplay_video_info()`: UPLOAD#レコードに動画情報更新
    - `update_match_has_gameplay_video()`: MATCHレコードにフラグ設定
  - `src/handlers/api/match_detail.py`: レスポンスに`gameplayVideoS3Key`等追加
  - `web-ui/app/types/replay.ts`: `gameplayVideoS3Key`等の型追加
  - `web-ui/app/components/MatchDetailExpansion.vue`:
    - ミニマップ/ゲームプレイ動画切り替えボタン（v-btn-toggle）
    - 動画タイプごとのプレーヤー表示
- **ゲームキャプチャ機能（2026-01-31）**:
  - クライアントツールにゲームプレイ録画機能を追加（v1.3.0）
  - `client_tool/capture/` モジュール新規作成
    - `screen_capture.py`: Windows Graphics Capture API（windows-capture）でゲームウィンドウキャプチャ
    - `audio_capture.py`: PyAudioWPatchでWASAPI loopback + マイク入力キャプチャ
    - `video_encoder.py`: FFmpegでH.264 MP4エンコード（2パス方式：raw→WAV→FFmpeg mux）
    - `manager.py`: GameCaptureManager - キャプチャオーケストレーション
    - `config.py`: CaptureConfig - 設定管理（品質、FPS、保存先など）
  - `tempArenaInfo.json` 検出で試合開始を検知、`*.wowsreplay` 作成で試合終了を検知
  - 最大録画時間制限（デフォルト30分）、フレームドロップログ出力
  - 新規依存: windows-capture, PyAudioWPatch, numpy, FFmpeg
- **Nuxt 4 移行（2026-01-27）**:
  - Nuxt 3 → Nuxt 4.3.0、Pinia 2 → Pinia 3 へ移行
  - codemodによりソースファイルを `web-ui/app/` ディレクトリへ移動（Nuxt 4 デフォルト構造）
  - `hid` プロパティ削除（Unhead v2）、`compatibilityDate` を `2025-07-01` に更新
  - `@nuxt/devtools` パッケージ削除（Nuxt 4 に内蔵）
  - stores/ と types/ も app/ ディレクトリへ移動（`~` エイリアス対応）
- **WoWS 15.1.0 & 15.2.0 バージョン対応（2026-02-20）**:
  - `replays_unpack_upstream`サブモジュールを27308f7に更新（15.1.0サポート）
  - `src/replay_versions/15_2_0/`ローカルオーバーレイ作成（15.1.0ベース）
  - `minimap_renderer/src/renderer/versions/15_1_0/`, `15_2_0/`: ミニマップリソース追加（15.0.0ベース）
  - `minimap_renderer/src/replay_unpack/clients/wows/versions/15_1_0/`, `15_2_0/`: エンティティ定義追加（Python: 15.0.0ベース、scripts/: 各バージョン固有）
  - `src/parsers/battlestats_parser.py`: 15.1.0対応（配列長460→503のインデックスシフトに対応、14.11.0後方互換あり）
  - 15.1.0リプレイで全24プレイヤーのパース・レンダラー初期化を検証済み
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
- download APIから`?file=uploader`機能を削除（GitHub Releasesに移行済み、`src/handlers/api/download.py`）
- リプレイ処理統合テスト実装
- クラン戦シーズン毎のデータ表示
- 過去データのクリーンナップタスクの追加(一定時間たったリプレイファイルの保管は不要。レンダラーファイルと統計データのみを残す設計で良いかは要検討)
- 複数テナント化（マルチテナント）設計
- 各種FAQ追加
- dynamodbのデータの中身についてclaudeに質問する機能の追加
- 本サービスのランディングページ追加