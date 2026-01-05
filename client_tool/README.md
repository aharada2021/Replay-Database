# WoWS Replay Auto Uploader

World of Warshipsのリプレイファイルを自動的にアップロードするクライアント常駐ツールです。

## 機能

- ✅ リプレイフォルダを監視して、新しいリプレイファイルを自動アップロード
- ✅ 重複検出（同じ試合のリプレイが既にアップロード済みの場合は通知）
- ✅ ネットワークエラー時の自動リトライ
- ✅ アップロード履歴の記録

## インストール

### 方法1: 実行ファイル（.exe）を使用（推奨）

1. `wows_replay_uploader.exe` をダウンロード
2. 任意のフォルダに配置
3. `config.yaml.template` を `config.yaml` にコピー
4. `config.yaml` を編集して API Key を設定
5. `wows_replay_uploader.exe` を実行

### 方法2: Pythonから実行

#### 必要な環境
- Python 3.11以上

#### セットアップ手順

```bash
# 依存パッケージをインストール
pip install -r requirements.txt

# 設定ファイルを作成
copy config.yaml.template config.yaml

# config.yaml を編集してAPI Keyを設定
notepad config.yaml

# 実行
python wows_replay_uploader.py
```

## 設定ファイル (config.yaml)

```yaml
# API設定
api_url: https://874mutasbd.execute-api.ap-northeast-1.amazonaws.com/api/upload
api_key: YOUR_API_KEY_HERE  # ← ここにAPI Keyを入力

# 監視設定
replays_folder: '%APPDATA%\Wargaming.net\WorldOfWarships\replays'

# 自動起動
auto_start: true

# Discord User ID（オプション）
discord_user_id: ''

# リトライ設定
retry_count: 3
retry_delay: 5
```

### 設定項目の説明

| 項目 | 説明 | デフォルト値 |
|------|------|--------------|
| `api_url` | アップロードAPIのURL | （デプロイ時のURL） |
| `api_key` | API認証キー | - |
| `replays_folder` | リプレイフォルダのパス | `%APPDATA%\Wargaming.net\WorldOfWarships\replays` |
| `auto_start` | 自動起動設定 | `true` |
| `discord_user_id` | Discord User ID（オプション） | （空） |
| `retry_count` | リトライ回数 | `3` |
| `retry_delay` | リトライ間隔（秒） | `5` |

## 使い方

### 1. 初回起動

1. `wows_replay_uploader.exe` を実行
2. API Keyが設定されていない場合はエラーメッセージが表示されます
3. `config.yaml` を編集してAPI Keyを設定
4. 再度実行

### 2. 通常使用

- プログラムを起動すると、リプレイフォルダの監視が開始されます
- World of Warshipsで試合が終了してリプレイが保存されると、自動的にアップロードされます
- 重複している場合は、既にアップロード済みであることが通知されます

### 3. ログの確認

`wows_replay_uploader.log` ファイルにログが記録されます。

## スタートアップ登録（自動起動）

Windowsのスタートアップに登録することで、PC起動時に自動的にツールを起動できます。

1. `Win + R` キーを押して「ファイル名を指定して実行」を開く
2. `shell:startup` と入力してEnter
3. スタートアップフォルダが開くので、`wows_replay_uploader.exe` のショートカットを作成して配置

## トラブルシューティング

### アップロードが失敗する

1. `config.yaml` のAPI Keyが正しいか確認
2. インターネット接続を確認
3. ログファイル `wows_replay_uploader.log` でエラー内容を確認

### リプレイフォルダが見つからない

1. `config.yaml` の `replays_folder` が正しいパスか確認
2. World of Warshipsのリプレイ保存設定が有効か確認

### 重複エラーが表示される

- 同じ試合のリプレイが既に別のプレイヤーによってアップロードされています
- これは正常な動作です（重複を防ぐための機能）

## ビルド（開発者向け）

PyInstallerで実行ファイルをビルド:

```bash
pyinstaller --onefile --windowed --name wows_replay_uploader wows_replay_uploader.py
```

ビルドされたファイルは `dist/wows_replay_uploader.exe` に作成されます。

## ライセンス

MIT License
