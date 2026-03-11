# WoWS ゲームバージョンアップ対応手順

WoWSの新バージョン（例: 15.3.0）がリリースされた際の対応手順。

## 前提知識

### データフロー

```
WoWSゲームクライアント (Windows)
  ↓ wows-data-mgr dump-renderer-data
ローカルPC (renderer_data/)
  ↓ scripts/upload_game_data.py
S3 (game-data/{version}/)
  ↓ GitHub Actions (aws s3 sync)
Dockerイメージ (/opt/game-data/)
  ↓ wows-replay-tool (自動バージョン解決)
リプレイ処理結果
```

### wows-toolkit依存関係

`rust/wows-replay-tool` は以下のcrateをライブラリとして直接依存:

| crate | 用途 |
|-------|------|
| `wows_replays` | リプレイファイルのパース |
| `wowsunpack` | ゲームデータVFS・アセット抽出 |
| `wows_minimap_renderer` | ミニマップ動画レンダリング |

CIではコミットをピン留めし、カスタムパッチを適用してビルド:
- ピン留めコミット: `.github/workflows/deploy-lambda.yml` の `ref:` 行
- パッチ: `rust/wows-toolkit-patches.patch`

---

## チェックリスト

### 1. wows-toolkit upstream確認

- [ ] [landaire/wows-toolkit](https://github.com/landaire/wows-toolkit) が新バージョンをサポートしているか確認
- [ ] サポートしている場合: 該当コミットハッシュを控える
- [ ] サポートしていない場合: PR/Issue/ブランチを確認、なければパッチ対応が必要

### 2. ゲームデータ抽出（Windows作業）

Windows PCにWoWSがインストールされた環境で実行:

```bash
# wows-data-mgr を使用してゲームデータを抽出
cd path/to/wows-toolkit
cargo run --bin wows-data-mgr --release -- \
  dump-renderer-data \
  "C:\Games\World_of_Warships" \
  <major> <minor> <patch> \
  output_directory
```

出力ディレクトリ構成:
```
{version}_{build}/
  metadata.toml           # バージョン情報
  game_params.rkyv        # ゲームパラメータ (バイナリ)
  vfs/scripts/            # エンティティ定義 (抽出に必須)
  vfs/gui/                # UIアセット (レンダリングに必須)
  vfs/spaces/             # マップデータ (レンダリングに必須)
  translations/en/        # 英語翻訳ファイル
```

### 3. S3へアップロード

```bash
# 全データアップロード（レンダリング含む）
python3 scripts/upload_game_data.py --data-dir path/to/{version}_{build} --full

# 確認
aws s3 ls s3://wows-replay-bot-dev-temp/game-data/ | grep {version}
```

### 4. 日本語翻訳の生成・アップロード

新しいスキル・アップグレード・マップが追加された場合、先にマッピングを更新:

- [ ] `src/utils/captain_skills.py` の `SKILL_DISPLAY_TO_JAPANESE` に新スキルを追加
- [ ] `src/utils/upgrades.py` の `UPGRADE_NAMES_JA` に新アップグレードを追加
- [ ] `config/map_names.yaml` に新マップを追加

```bash
# 日本語MOファイルを生成してS3の全バージョンにアップロード
python3 scripts/generate_ja_mo.py --upload
```

### 5. CI/CDパイプライン更新

wows-toolkitのコミットを更新する場合:

- [ ] `.github/workflows/deploy-lambda.yml` の `ref:` を新コミットハッシュに変更
- [ ] `rust/wows-toolkit-patches.patch` が新コミットに適用できるか確認
  - 適用できない場合: パッチを再生成

```bash
# パッチ適用テスト
cd path/to/wows-toolkit
git checkout {new-commit}
git apply path/to/rust/wows-toolkit-patches.patch
```

### 6. ローカルビルド確認（任意）

```bash
cd rust/wows-replay-tool
cargo build --release

# 新バージョンのリプレイで抽出テスト
./target/release/wows-replay-tool extract \
  --replay path/to/new_version.wowsreplay \
  --game-data path/to/game-data/

# レンダリングテスト
./target/release/wows-replay-tool render \
  --replay path/to/new_version.wowsreplay \
  --game-data path/to/game-data/ \
  --output test.mp4
```

### 7. デプロイ・検証

- [ ] `develop` ブランチにpush → dev環境へ自動デプロイ
- [ ] 新バージョンのリプレイでアップロード → 抽出 → 動画生成を確認
- [ ] 旧バージョンのリプレイも正常に処理されることを確認（後方互換性）
- [ ] CloudWatchログで `Replay version: {version}` のバージョン解決を確認
- [ ] `main` ブランチにマージ → prod環境へデプロイ

---

## トラブルシューティング

### "No game data matches replay build {build}"

S3にアップロードしたゲームデータのビルド番号がリプレイと一致しない。
- `metadata.toml` のビルド番号を確認
- `wows-replay-tool` はリプレイ内のビルド番号と完全一致で検索する
- 複数バージョンのゲームデータがある場合のみ発生（1バージョンならフォールバック）

### "Failed to load Warhelios font from game files"

ゲームデータが不完全（レンダリング用アセットが不足）。
- `--full` オプションで再アップロード
- `vfs/gui/fonts/`, `vfs/gui/fla/minimap/`, `vfs/spaces/` が必要

### パース失敗（EntityCreate out of bounds等）

新バージョンでエンティティ定義が変更された。
- wows-toolkit upstream の対応を待つか、`packet2.rs` のパッチを更新
- `rust/wows-toolkit-patches.patch` のエラーハンドリングがパニックを防止

### 日本語名が表示されない

翻訳マッピングが不足。
- 該当するPythonファイル（`captain_skills.py`, `upgrades.py`）にマッピングを追加
- `generate_ja_mo.py --upload` を再実行

---

## 関連ファイル

| ファイル | 用途 |
|---------|------|
| `.github/workflows/deploy-lambda.yml` | wows-toolkitコミットピン留め |
| `rust/wows-toolkit-patches.patch` | upstreamへのカスタムパッチ |
| `rust/wows-replay-tool/src/extract.rs` | リプレイ抽出・バージョン解決ロジック |
| `rust/wows-replay-tool/src/render.rs` | ミニマップレンダリング |
| `scripts/upload_game_data.py` | ゲームデータS3アップロード |
| `scripts/generate_ja_mo.py` | 日本語翻訳MOファイル生成 |
| `src/utils/captain_skills.py` | スキル日本語マッピング |
| `src/utils/upgrades.py` | アップグレード日本語マッピング |
| `config/map_names.yaml` | マップ日本語名マッピング |
| `deploy/Dockerfile.lambda` | ゲームデータのDockerイメージ組み込み |
