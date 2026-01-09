# WoWS Replay Auto Uploader

World of Warshipsのリプレイファイルを自動的にアップロードするクライアント常駐ツールです。

## クイックスタート（5分でセットアップ）

### ステップ 1: ダウンロード

1. WoWS Replay Databaseにアクセス（URLは管理者から取得）
2. Discordでログイン
3. 左上のハンバーガーメニュー（三本線）を開く
4. 「自動アップローダー」をクリックしてダウンロード

### ステップ 2: API Keyを取得

1. 同じくハンバーガーメニューから「API Key」をクリック
2. 表示されたAPI Keyをコピー

### ステップ 3: 初回起動

1. ダウンロードしたzipファイルを展開
2. `wows_replay_uploader.exe` をダブルクリックして起動
3. セットアップウィザードが表示されます：
   - **API Key**: コピーしたAPI Keyを貼り付け
   - **リプレイフォルダ**: 自動検出されるのでそのままEnter
   - **Discord User ID**: 空欄でもOK
   - **スタートアップ登録**: 「Y」でPC起動時に自動起動

### ステップ 4: 完了

これで設定完了です。World of Warshipsで試合が終わるたびに、リプレイが自動でアップロードされます。

---

## 機能

- リプレイフォルダを監視して、新しいリプレイファイルを自動アップロード
- 重複検出（同じ試合のリプレイが既にアップロード済みの場合は通知）
- ネットワークエラー時の自動リトライ
- アップロード履歴の記録
- 一時ファイル除外（`temp.wowsreplay`は自動的にスキップ）
- 自動アップデート通知

---

## 詳細設定

### 設定ファイル (config.yaml)

初回セットアップ後、`config.yaml` が作成されます。手動で編集も可能です：

```yaml
# API認証キー
api_key: YOUR_API_KEY_HERE

# 監視するリプレイフォルダ
replays_folder: '%APPDATA%\Wargaming.net\WorldOfWarships\replays'

# Discord User ID（オプション）
discord_user_id: ''

# リトライ設定
retry_count: 3
retry_delay: 5

# PollingObserverを使用（ネットワークドライブ対応）
use_polling: true
```

### 設定項目の説明

| 項目 | 説明 | デフォルト値 |
|------|------|--------------|
| `api_key` | API認証キー（必須） | - |
| `replays_folder` | リプレイフォルダのパス | `%APPDATA%\Wargaming.net\WorldOfWarships\replays` |
| `discord_user_id` | Discord User ID（オプション） | （空） |
| `retry_count` | リトライ回数 | `3` |
| `retry_delay` | リトライ間隔（秒） | `5` |
| `use_polling` | PollingObserverを使用 | `true` |

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
- Python 3.11以上
- Windows環境（winregを使用）

### セットアップ手順

```bash
# 依存パッケージをインストール
pip install -r requirements.txt

# 実行
python wows_replay_uploader.py
```

### ビルド

PyInstallerで実行ファイルをビルド:

```bash
pyinstaller --onefile --windowed --name wows_replay_uploader wows_replay_uploader.py
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

A: アップロードされるのはリプレイファイルのみです。個人情報は収集しません。

---

## ライセンス

MIT License
