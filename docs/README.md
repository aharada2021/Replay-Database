# WoWS Replay Classification Bot

World of Warships（WoWS）のリプレイファイルをマップ別に自動分類し、ミニマップ動画を生成してDiscordチャンネルに投稿するBotです。

## 機能

- リプレイファイル（.wowsreplay）の自動分類
- マップIDから日本語マップ名への変換
- リプレイファイル内部から対戦時間を抽出
- minimap_rendererを使用したミニマップ動画（MP4）の自動生成
- マップ別のDiscordチャンネルへの自動投稿

## 必要環境

- Python 3.8以上
- Discord Bot Token
- minimap_renderer（WoWs-Builder-Team製）

## セットアップ

### 1. リポジトリのクローン

```bash
cd /path/to/your/directory
git clone <このリポジトリのURL>
cd wows-reploy-classfication-bot
```

### 2. Python仮想環境の作成（推奨）

```bash
python -m venv venv

# macOS/Linux
source venv/bin/activate

# Windows
venv\Scripts\activate
```

### 3. 依存パッケージのインストール

```bash
pip install -r requirements.txt
```

### 4. minimap_rendererのインストール

minimap_rendererは別途インストールが必要です。

```bash
# GitHubからクローン
git clone https://github.com/WoWs-Builder-Team/minimap_renderer.git
cd minimap_renderer

# インストール（詳細は公式READMEを参照）
pip install -e .
cd ..
```

**注意**: minimap_rendererの動作には追加の依存関係（FFmpegなど）が必要な場合があります。詳細は[公式リポジトリ](https://github.com/WoWs-Builder-Team/minimap_renderer)を参照してください。

### 5. Discord Botの作成

1. [Discord Developer Portal](https://discord.com/developers/applications)にアクセス
2. "New Application"をクリックして新しいアプリケーションを作成
3. "Bot"タブに移動し、"Add Bot"をクリック
4. "TOKEN"をコピー（後で使用）
5. "Privileged Gateway Intents"で以下を有効化:
   - Message Content Intent
   - Server Members Intent

### 6. Botをサーバーに招待

1. Developer Portalで"OAuth2" > "URL Generator"に移動
2. "SCOPES"で`bot`を選択
3. "BOT PERMISSIONS"で以下を選択:
   - Read Messages/View Channels
   - Send Messages
   - Embed Links
   - Attach Files
   - Read Message History
   - Add Reactions
4. 生成されたURLをブラウザで開き、Botをサーバーに招待

### 7. Discordサーバーの準備

1. **開発者モードを有効化**:
   - Discord設定 > アプリの設定 > 詳細設定 > 開発者モードをON

2. **チャンネルの作成**:
   - `input` - リプレイファイルをアップロードするチャンネル
   - マップ別チャンネル（`map_names.yaml`で定義されたマップ名）
     - 例: `大海原`, `ソロモン諸島`, `北極光` など

3. **チャンネルIDの取得**:
   - `input`チャンネルを右クリック > "チャンネルIDをコピー"
   - サーバーアイコンを右クリック > "サーバーIDをコピー"

### 8. 環境変数の設定

`.env.example`をコピーして`.env`を作成:

```bash
cp .env.example .env
```

`.env`を編集:

```env
DISCORD_TOKEN=your_bot_token_here
GUILD_ID=your_guild_id_here
INPUT_CHANNEL_ID=your_input_channel_id_here
```

### 9. マップ名マッピングの調整

`map_names.yaml`を編集して、マップIDと日本語チャンネル名のマッピングを調整してください。

```yaml
maps:
  "19_OC_prey": "大海原"
  "01_solomon_islands": "ソロモン諸島"
  # ...既存のDiscordチャンネル名に合わせて編集
```

## 使い方

### Botの起動

```bash
python bot.py
```

正常に起動すると、以下のようなログが表示されます:

```
<Bot名> としてログインしました
Bot ID: <Bot ID>
マップ名マッピングを読み込みました: XX件
------
INPUT_CHANNEL_ID: <チャンネルID>
Bot起動完了
```

### リプレイファイルのアップロード

1. `input`チャンネルに移動
2. リプレイファイル（.wowsreplay）をアップロード
3. メッセージ本文に対戦相手のクラン名を記入

例:
```
ABC
```
（添付ファイル: 20260103_232822_PZSD109-Chung-Mu_19_OC_prey.wowsreplay）

### Botの動作

1. リプレイファイルを検出すると⏳リアクションを追加
2. ファイル名からマップIDを抽出
3. マップIDを日本語マップ名に変換
4. リプレイファイルから対戦時間を取得
5. minimap_rendererでMP4動画を生成
6. 該当するマップ別チャンネルに投稿
   - 対戦クラン名
   - 対戦時間
   - ファイル名
   - MP4動画（生成成功時）またはリプレイファイル
7. 処理完了後、✅リアクションを追加

## コマンド

- `!test` - Botの動作確認
- `!info` - Bot情報の表示
- `!reload_maps` - マップマッピングの再読み込み（管理者のみ）

## ファイル構成

```
wows-reploy-classfication-bot/
├── bot.py                  # メインのBotコード
├── replay_processor.py     # リプレイ解析・MP4生成モジュール
├── map_names.yaml          # マップIDと日本語名のマッピング
├── requirements.txt        # Python依存パッケージ
├── .env.example            # 環境変数のサンプル
├── .env                    # 環境変数（作成必要）
├── .gitignore             # Git除外設定
├── README.md              # このファイル
├── specification.md       # 仕様書
├── data/                  # データディレクトリ
│   └── replays/          # サンプルリプレイファイル
└── temp/                  # 一時ファイル（自動生成）
    └── videos/           # 生成されたMP4（自動生成）
```

## トラブルシューティング

### Botが起動しない

- `.env`ファイルが正しく設定されているか確認
- `DISCORD_TOKEN`が有効か確認
- Python環境が正しくセットアップされているか確認

### マップチャンネルが見つからない

- `map_names.yaml`のマップ名が既存のDiscordチャンネル名と完全一致しているか確認
- チャンネル名は大文字小文字を区別します

### MP4が生成されない

- minimap_rendererが正しくインストールされているか確認
- FFmpegなどの依存ソフトウェアがインストールされているか確認
- ログを確認してエラーメッセージを確認

### リプレイファイルの解析に失敗する

- リプレイファイルが破損していないか確認
- ファイル名が正しい形式か確認（例: `20260103_232822_PZSD109-Chung-Mu_19_OC_prey.wowsreplay`）

## 開発・カスタマイズ

### 新しいマップの追加

`map_names.yaml`に新しいマップIDと日本語名を追加:

```yaml
maps:
  "XX_new_map": "新しいマップ"
```

Discordサーバーに対応するチャンネルを作成してください。

### ログレベルの変更

`bot.py`の以下の行を編集:

```python
logging.basicConfig(
    level=logging.INFO,  # DEBUG, WARNING, ERROR に変更可能
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
```

## ライセンス

このプロジェクトは個人使用を目的としています。

## 参考リンク

- [discord.py Documentation](https://discordpy.readthedocs.io/)
- [minimap_renderer GitHub](https://github.com/WoWs-Builder-Team/minimap_renderer)
- [World of Warships](https://worldofwarships.asia/)
