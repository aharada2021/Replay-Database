# WoWS Replay Auto Uploader

World of Warshipsのリプレイファイルを自動的にアップロードするクライアント常駐ツールです。

**バージョン: 1.3.1**

## 主な機能

- リプレイファイルの自動アップロード
- **ゲームプレイ録画機能** (v1.3.0〜)
- **録画した動画の自動アップロード** (v1.3.0〜)
- 重複検出・自動リトライ
- Windows起動時の自動起動

---

## クイックスタート（5分でセットアップ）

### ステップ 1: ダウンロード

1. [GitHub Releases](https://github.com/aharada2021/Replay-Database/releases/latest) から最新版をダウンロード
2. または、WoWS Replay Databaseにアクセスし、ハンバーガーメニューから「自動アップローダー」をクリック

### ステップ 2: API Keyを取得

1. WoWS Replay DatabaseにDiscordでログイン
2. ハンバーガーメニューから「API Key」をクリック
3. 表示されたAPI Keyをコピー

### ステップ 3: 初回起動

1. ダウンロードしたzipファイルを展開
2. `wows_replay_uploader.exe` をダブルクリックして起動
3. セットアップウィザードが表示されます：
   - **API Key**: コピーしたAPI Keyを貼り付け
   - **リプレイフォルダ**: 自動検出されるのでそのままEnter
   - **ゲームキャプチャ設定**: 録画機能を使う場合は設定
   - **スタートアップ登録**: 「Y」でPC起動時に自動起動

### ステップ 4: 完了

これで設定完了です。World of Warshipsで試合が終わるたびに、リプレイが自動でアップロードされます。

---

## ゲームプレイ録画機能 (v1.3.0〜)

試合中のゲームプレイを自動的に録画し、サーバーにアップロードする機能です。

### 必要条件

- **FFmpeg**: 動画エンコードに必要（**exeにバンドル済み**のため、通常はインストール不要）

### 動作の流れ

1. `tempArenaInfo.json` の作成を検出 → 録画開始
2. `.wowsreplay` ファイルの作成を検出 → 録画終了
3. リプレイと動画を自動アップロード
4. WebサイトでミニマップとゲームプレイVODを視聴可能

### 録画設定

セットアップウィザードで以下を設定できます：

| 項目 | 説明 |
|------|------|
| 録画品質 | low / medium / high |
| デスクトップ音声 | ゲーム音声を録音 |
| マイク入力 | ボイスチャット等を録音 |
| 動画アップロード | 録画後に自動アップロード |
| ローカル保存 | アップロード後もファイルを保持 |

---

## 詳細設定

### 設定ファイル (config.yaml)

初回セットアップ後、`config.yaml` が作成されます。手動で編集も可能です：

```yaml
# API認証キー（必須）
api_key: YOUR_API_KEY_HERE

# サーバーURL
api_base_url: https://wows-replay.mirage0926.com

# 監視するリプレイフォルダ
replays_folder: '%APPDATA%\Wargaming.net\WorldOfWarships\replays'

# Discord User ID（オプション）
discord_user_id: ''

# リトライ設定
retry_count: 3
retry_delay: 5

# PollingObserverを使用（ネットワークドライブ対応）
use_polling: true

# ゲームキャプチャ設定
capture:
  enabled: true                                   # キャプチャ機能の有効/無効
  output_folder: '%USERPROFILE%\Videos\WoWS Captures'  # 録画保存先
  video_quality: medium                           # 録画品質 (low/medium/high)
  target_fps: 30                                  # フレームレート
  capture_audio: true                             # デスクトップ音声を録音
  capture_microphone: false                       # マイク入力を録音
  mic_volume: 0.7                                 # マイク音量 (0.0-1.0)
  max_duration_minutes: 30                        # 最大録画時間（分）
  upload_gameplay_video: true                     # 動画を自動アップロード
  keep_local_copy: false                          # アップロード後もローカルに保持
  max_upload_size_mb: 500                         # アップロード上限（MB）
```

### 設定項目の説明

#### 基本設定

| 項目 | 説明 | デフォルト値 |
|------|------|--------------|
| `api_key` | API認証キー（必須） | - |
| `api_base_url` | サーバーURL | `https://wows-replay.mirage0926.com` |
| `replays_folder` | リプレイフォルダのパス | 自動検出 |
| `discord_user_id` | Discord User ID（オプション） | （空） |
| `retry_count` | リトライ回数 | `3` |
| `retry_delay` | リトライ間隔（秒） | `5` |
| `use_polling` | PollingObserverを使用 | `true` |

#### キャプチャ設定 (capture)

| 項目 | 説明 | デフォルト値 |
|------|------|--------------|
| `enabled` | キャプチャ機能の有効/無効 | `false` |
| `output_folder` | 録画ファイルの保存先 | `%USERPROFILE%\Videos\WoWS Captures` |
| `video_quality` | 録画品質 (low/medium/high) | `medium` |
| `target_fps` | フレームレート | `30` |
| `capture_audio` | デスクトップ音声を録音 | `true` |
| `capture_microphone` | マイク入力を録音 | `false` |
| `mic_volume` | マイク音量 (0.0-1.0) | `0.7` |
| `max_duration_minutes` | 最大録画時間（分） | `30` |
| `upload_gameplay_video` | 動画を自動アップロード | `true` |
| `keep_local_copy` | アップロード後もローカルに保持 | `false` |
| `max_upload_size_mb` | アップロード上限（MB） | `500` |

---

## スタートアップ登録（PC起動時に自動起動）

### 方法1: セットアップウィザードで登録（推奨）

初回起動時のウィザードで「Y」を選択すると自動で登録されます。

### 方法2: 手動で登録

1. `Win + R` キーを押して「ファイル名を指定して実行」を開く
2. `shell:startup` と入力してEnter
3. スタートアップフォルダが開くので、`wows_replay_uploader.exe` のショートカットを作成して配置

---

## トラブルシューティング

### アップロードが失敗する

1. **API Keyを確認**: `config.yaml` のAPI Keyが正しいか確認
2. **インターネット接続を確認**: ブラウザで他のサイトにアクセスできるか確認
3. **ログを確認**: `wows_replay_uploader.log` でエラー内容を確認

### リプレイフォルダが見つからない

1. `config.yaml` の `replays_folder` が正しいパスか確認
2. World of Warshipsの設定でリプレイ保存が有効か確認
3. WoWSをSteam版で使っている場合はパスが異なる場合があります

### 録画機能が動作しない

1. **ログを確認**: `wows_replay_uploader.log` でエラー内容を確認
2. **ゲームウィンドウを確認**: World of Warshipsがウィンドウモードまたはボーダーレスで起動しているか確認
3. **Pythonから実行時のみ**: FFmpegがインストールされているか確認（exeにはバンドル済み）

### 録画品質が悪い / ファイルサイズが大きい

`config.yaml` の `capture.video_quality` を調整してください：

| 品質 | ビットレート | 用途 |
|------|-------------|------|
| `low` | 2 Mbps | 低スペックPC / 容量節約 |
| `medium` | 5 Mbps | 標準（推奨） |
| `high` | 10 Mbps | 高画質 |

### 動画アップロードが失敗する

1. **ファイルサイズを確認**: `max_upload_size_mb` の上限を超えていないか
2. **ネットワークを確認**: 大容量ファイルのアップロードには安定した接続が必要
3. **リトライ**: 一時的なエラーの場合、自動リトライで成功することがあります

### 重複エラーが表示される

- 同じ試合のリプレイが既に別のプレイヤーによってアップロードされています
- これは正常な動作です（重複を防ぐための機能）

### temp.wowsreplayについて

- `temp.wowsreplay`はゲーム中に作成される一時ファイルです
- このファイルは自動的に除外されるため、アップロードされません

### ウイルス対策ソフトにブロックされる

- PyInstallerでビルドされたexeファイルは、誤検知されることがあります
- 安全なファイルです。除外設定に追加してください

---

## Pythonから実行（開発者向け）

### 必要な環境
- Python 3.10以上
- Windows環境（winregを使用）
- FFmpeg（キャプチャ機能使用時、PATHに追加が必要）

### セットアップ手順

```bash
# 依存パッケージをインストール
pip install -r requirements.txt

# 実行
python wows_replay_uploader.py
```

### 依存パッケージ

```
requests>=2.28.0
watchdog>=3.0.0
PyYAML>=6.0
windows-capture>=1.0.0
PyAudioWPatch>=0.2.12
numpy>=1.24.0
```

### ビルド

```bash
# PyInstallerでビルド
pyinstaller build.spec

# または
python -m PyInstaller build.spec
```

ビルドされたファイルは `dist/wows_replay_uploader.exe` に作成されます。

---

## よくある質問

### Q: API Keyはどこで取得できますか？

A: WoWS Replay DatabaseにDiscordでログイン後、ハンバーガーメニューの「API Key」から取得できます。

### Q: 複数のPCで使用できますか？

A: はい、同じAPI Keyを複数のPCで使用できます。

### Q: アップロードされたリプレイはどこで見られますか？

A: WoWS Replay Databaseで検索できます。

### Q: プライバシーは大丈夫ですか？

A: アップロードされるのはリプレイファイルと録画した動画のみです。個人情報は収集しません。

### Q: 録画機能を使うとPCが重くなりますか？

A: FFmpegを使用したハードウェアエンコードにより、最小限の負荷で録画できます。ただし、低スペックPCの場合は `video_quality: low` の使用を推奨します。

### Q: 録画ファイルはどこに保存されますか？

A: デフォルトでは `%USERPROFILE%\Videos\WoWS Captures` に保存されます。`config.yaml` で変更可能です。

### Q: 動画をアップロードせずにローカルにのみ保存できますか？

A: はい、`config.yaml` で `upload_gameplay_video: false` に設定してください。

---

## 更新履歴

### v1.3.1 (2026-02-01)
- 動画アップロードのバグ修正（S3キー移行問題）
- マルチパートアップロードの安定性向上

### v1.3.0 (2026-01-31)
- ゲームプレイ録画機能を追加
- 録画した動画の自動アップロード機能を追加
- FFmpegによるH.264エンコード対応
- デスクトップ音声・マイク入力のキャプチャ対応

### v1.2.0
- 自動アップデート通知機能を追加
- PollingObserver対応（安定性向上）

### v1.1.0
- 重複検出機能を追加
- リトライ機能を改善

### v1.0.0
- 初回リリース

---

## ライセンス

MIT License
