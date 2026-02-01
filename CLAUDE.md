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
  - 動画アップロード失敗修正: S3マルチパートアップロード実装
    - `src/handlers/api/upload_multipart.py`: 新規作成
      - `handle_init_multipart()`: アップロード開始（UploadId + Presigned URLs）
      - `handle_complete_multipart()`: パート結合完了
      - `handle_abort_multipart()`: アップロード中止
      - セキュリティ: ArenaUniqueID検証、ファイルサイズ制限（2GB）
    - `client_tool/wows_replay_uploader.py`: マルチパートアップロード対応
      - 10MB以上のファイルは自動的にマルチパートアップロード使用
      - Content-Typeヘッダー削除（Presigned URL署名不一致による403エラー修正）
    - `deploy/serverless.yml`: 新規エンドポイント＋S3マルチパートIAM権限追加
  - 動画S3キー移行問題修正: 一時ID→正式arenaUniqueIDへの移行
    - 問題: クライアントはtempArenaID（一時ID）で動画をアップロードするが、正式なarenaUniqueIDはリプレイ解析後に判明
    - `src/handlers/processing/battle_result_extractor.py`: `migrate_gameplay_video()`関数追加
      - 一時IDパスに動画が存在するか確認
      - 正式arenaUniqueIDのパスにS3コピー
      - DynamoDBを更新（gameplayVideoS3Key, hasGameplayVideo）
      - 元のS3オブジェクトを削除
  - テストスクリプト: `client_tool/test_ffmpeg_encoding.py` 新規作成
    - `--with-mic`オプションでマイクテスト対応
- **クライアントツール配布方法をGitHub Releasesに変更（2026-02-01）**:
  - `.github/workflows/build-client-tool.yml`: S3アップロードを削除し、GitHub Releaseを自動作成
  - `web-ui/app/app.vue`: ダウンロードURLをGitHub Releasesに変更
  - タグ形式: `client-v{version}`、ダウンロードURL: `/releases/latest/download/wows_replay_uploader.zip`
- **ゲームプレイ動画アップロード機能（2026-02-01）**:
  - クライアントツールでキャプチャした動画をS3にアップロードする機能を追加
  - `client_tool/wows_replay_uploader.py`:
    - `PendingVideoQueue`クラス: 動画→リプレイのマッピング管理
    - `ReplayUploader._upload_gameplay_video()`: S3へのPresigned URL PUT
    - `ReplayUploader._notify_video_upload_complete()`: アップロード完了通知
    - 設定オプション: `upload_gameplay_video`, `keep_local_copy`, `max_upload_size_mb`
  - `src/handlers/api/upload.py`:
    - `generate_video_upload_url()`: Presigned PUT URL生成
    - `handle_video_complete()`: 動画アップロード完了通知API
  - `src/utils/dynamodb_tables.py`:
    - `update_gameplay_video_info()`: UPLOAD#レコードに動画情報更新
    - `update_match_has_gameplay_video()`: MATCHレコードにフラグ設定
  - `src/handlers/api/match_detail.py`: レスポンスに`gameplayVideoS3Key`等追加
  - `web-ui/app/types/replay.ts`: `gameplayVideoS3Key`等の型追加
  - `web-ui/app/components/MatchDetailExpansion.vue`:
    - ミニマップ/ゲームプレイ動画切り替えボタン（v-btn-toggle）
    - 動画タイプごとのプレーヤー表示
  - `deploy/serverless.yml`: `/api/upload/video-complete` エンドポイント追加
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