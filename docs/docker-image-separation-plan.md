# Dockerイメージ分離計画

## 現状の問題点

### 1. replay_unpackバージョン衝突
現在、1つのDockerイメージで以下2つの異なるreplay_unpackバージョンを使用：
- **minimap_renderer/replay_unpack**: 動画生成用（processor関数）
- **replays_unpack_upstream**: BattleStats抽出用（battle-result-extractor関数）

### 2. 発生している問題
```
JSONDecodeError: Expecting value: line 1 column 1 (char 0)
```

**原因**:
- `ReplayReader.get_replay_data()`でリプレイファイルのメタデータブロックをパース時にエラー
- 2つのreplay_unpackバージョンが混在し、ファイル読み込みロジックが不整合

### 3. 現在の暫定対応
- `sys.path.insert(0, ...)`を削除してminimap_rendererのreplay_unpackを使用
- しかし、まだJSONDecodeErrorが発生（根本解決には至っていない）

---

## 提案する解決策

### アーキテクチャ変更: Lambda関数ごとにDockerイメージを分離

```
現在:
┌─────────────────────────────────────┐
│ 1つのDockerイメージ                    │
├─────────────────────────────────────┤
│ - minimap_renderer (replay_unpack)  │
│ - replays_unpack_upstream           │
│ - FFmpeg                            │
│ - すべてのLambda関数コード             │
└─────────────────────────────────────┘
        ↓ 使用
  すべてのLambda関数

変更後:
┌────────────────────────────┐  ┌──────────────────────────────┐
│ Dockerイメージ1 (processor)  │  │ Dockerイメージ2 (extractor)    │
├────────────────────────────┤  ├──────────────────────────────┤
│ - minimap_renderer         │  │ - replays_unpack_upstream    │
│ - replay_unpack (bundled)  │  │ - 軽量なPython依存関係のみ      │
│ - FFmpeg                   │  │                              │
│ - processor関連コードのみ     │  │ - extractor関連コードのみ       │
└────────────────────────────┘  └──────────────────────────────┘
        ↓                              ↓
  processor, interactions     battle-result-extractor
  generate-video-api
```

---

## 実装手順

### Phase 1: Dockerfileの分離

#### 1.1 `deploy/Dockerfile.processor` を作成
**用途**: processor, interactions, generate-video-api関数

**含める依存関係**:
- minimap_renderer (replay_unpack含む)
- FFmpeg (John Van Sickle's static build)
- imageio-ffmpeg==0.4.7
- その他requirements_lambda.txt

**含めるコード**:
- `src/replay_processor.py`
- `src/replay_processor_handler.py`
- `src/lambda_handler.py`
- `src/generate_video_api_handler.py`
- `src/utils/` (一部)
- `config/map_names.yaml`

**サイズ予測**: ~800MB-1GB

#### 1.2 `deploy/Dockerfile.extractor` を作成
**用途**: battle-result-extractor, upload-api, search-api, match-detail-api関数

**含める依存関係**:
- replays_unpack_upstream
- 基本的なPython依存関係のみ
- FFmpeg不要

**含めるコード**:
- `src/battle_result_extractor_handler.py`
- `src/upload_api_handler.py`
- `src/search_api_handler.py`
- `src/match_detail_api_handler.py`
- `src/utils/battle_stats_extractor.py`

**サイズ予測**: ~300-400MB

### Phase 2: serverless.ymlの更新

```yaml
functions:
  # ========================================
  # Processorイメージを使用する関数群
  # ========================================
  interactions:
    image:
      uri: ${env:ECR_PROCESSOR_IMAGE_URI}
      command:
        - lambda_handler.handle_interaction
    architecture: arm64
    timeout: 30
    memorySize: 256

  processor:
    image:
      uri: ${env:ECR_PROCESSOR_IMAGE_URI}
      command:
        - replay_processor_handler.handle_replay_processing
    architecture: arm64
    timeout: 900
    memorySize: 1024

  generate-video-api:
    image:
      uri: ${env:ECR_PROCESSOR_IMAGE_URI}
      command:
        - generate_video_api_handler.handle
    architecture: arm64
    timeout: 900
    memorySize: 1024

  # ========================================
  # Extractorイメージを使用する関数群
  # ========================================
  battle-result-extractor:
    image:
      uri: ${env:ECR_EXTRACTOR_IMAGE_URI}
      command:
        - battle_result_extractor_handler.handle
    architecture: arm64
    timeout: 300
    memorySize: 512

  upload-api:
    image:
      uri: ${env:ECR_EXTRACTOR_IMAGE_URI}
      command:
        - upload_api_handler.handle
    architecture: arm64
    timeout: 60
    memorySize: 512

  search-api:
    image:
      uri: ${env:ECR_EXTRACTOR_IMAGE_URI}
      command:
        - search_api_handler.handle
    architecture: arm64
    timeout: 30
    memorySize: 256

  match-detail-api:
    image:
      uri: ${env:ECR_EXTRACTOR_IMAGE_URI}
      command:
        - match_detail_api_handler.handle
    architecture: arm64
    timeout: 30
    memorySize: 256
```

### Phase 3: GitHub Actionsの更新

`.github/workflows/deploy.yml` を更新して2つのイメージをビルド：

```yaml
- name: Build processor Docker image
  run: |
    docker buildx build \
      --platform linux/arm64 \
      --file deploy/Dockerfile.processor \
      --tag $ECR_REGISTRY/$ECR_REPOSITORY:processor-$GITHUB_SHA \
      --tag $ECR_REGISTRY/$ECR_REPOSITORY:processor-latest \
      --push \
      .

- name: Build extractor Docker image
  run: |
    docker buildx build \
      --platform linux/arm64 \
      --file deploy/Dockerfile.extractor \
      --tag $ECR_REGISTRY/$ECR_REPOSITORY:extractor-$GITHUB_SHA \
      --tag $ECR_REGISTRY/$ECR_REPOSITORY:extractor-latest \
      --push \
      .

- name: Deploy with Serverless Framework
  env:
    ECR_PROCESSOR_IMAGE_URI: ${{ env.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:processor-${{ github.sha }}
    ECR_EXTRACTOR_IMAGE_URI: ${{ env.ECR_REGISTRY }}/${{ env.ECR_REPOSITORY }}:extractor-${{ github.sha }}
  run: |
    cd deploy
    npx serverless deploy --stage ${{ env.STAGE }} --region ap-northeast-1 --verbose
```

### Phase 4: battle_stats_extractor.pyの修正

`replays_unpack_upstream`を直接使用するように戻す：

```python
# extractor専用イメージではreplays_unpack_upstreamのみがインストールされる
import sys
from pathlib import Path

# replays_unpackライブラリのパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "replays_unpack_upstream"))

from replay_unpack.replay_reader import ReplayReader
from replay_unpack.clients.wows.player import ReplayPlayer as WoWSReplayPlayer
from replay_unpack.clients.wows.network.packets import BattleStats
```

---

## 変更が必要なファイル

### 新規作成
- [ ] `deploy/Dockerfile.processor`
- [ ] `deploy/Dockerfile.extractor`

### 変更
- [ ] `deploy/serverless.yml`
  - 各関数にimage URIを個別指定
  - 環境変数を2つに分離（`ECR_PROCESSOR_IMAGE_URI`, `ECR_EXTRACTOR_IMAGE_URI`）
- [ ] `.github/workflows/deploy.yml`
  - 2つのイメージをビルド＆プッシュ
  - 環境変数を追加
- [ ] `src/utils/battle_stats_extractor.py`
  - `sys.path.insert`を復活
  - `replays_unpack_upstream`から直接インポート

### 削除候補
- [ ] `deploy/Dockerfile` (現在の統合Dockerfile)
  - または、processor用にリネーム

---

## メリット

### 1. バージョン衝突の完全解消
- ✅ processor: minimap_rendererのreplay_unpackのみ
- ✅ extractor: replays_unpack_upstreamのみ
- ✅ 完全に分離され、相互干渉なし

### 2. イメージサイズ削減
- **extractor**: FFmpeg不要 → ~400MB（現在の半分以下）
- **processor**: replays_unpack_upstream不要 → 若干削減

### 3. ビルド時間短縮
- 変更があった機能のイメージのみ再ビルド可能
- processor変更時にextractorは再ビルド不要（逆も同様）

### 4. メンテナンス性向上
- 各イメージの責務が明確
- 依存関係の把握が容易
- トラブルシューティングが簡単

### 5. スケーラビリティ
- 将来的に別機能を追加する際、新しいDockerイメージを追加可能
- マイクロサービス的なアーキテクチャに移行しやすい

---

## デメリット・懸念点

### 1. 管理対象の増加
- Dockerfileが1つ → 2つ
- ECRイメージタグも2倍

**対策**:
- 命名規則を明確化（processor-*, extractor-*）
- 自動化により手動作業は増えない

### 2. ビルド時間の合計増加
- 両イメージを順次ビルド
- 初回は時間がかかる可能性

**対策**:
- GitHub Actionsのキャッシュ活用
- 並列ビルド検討（Docker buildxのマルチプラットフォームビルド）

### 3. デプロイの複雑化
- 2つのイメージURIを管理

**対策**:
- GitHub Actionsで自動設定
- serverless.ymlで環境変数から取得

---

## リスクと対策

### リスク1: 初回デプロイの失敗
**確率**: 中
**影響**: 高（全Lambda関数が停止）

**対策**:
1. dev環境で十分にテスト
2. ロールバック手順を事前準備
3. 既存Dockerfileをバックアップ

### リスク2: ECRストレージコスト増加
**確率**: 高
**影響**: 低（2倍になっても月数ドル程度）

**対策**:
- 古いイメージの自動削除（ライフサイクルポリシー）
- 最新10バージョンのみ保持

### リスク3: battle_stats_extractor.pyの動作不良
**確率**: 中
**影響**: 高（BattleStats抽出失敗）

**対策**:
1. 変更前にローカルでreplay_unpack_upstreamの動作確認
2. テストリプレイファイルで検証
3. エラーハンドリング強化

---

## 実装スケジュール案

### Week 1: 準備・検証
- [ ] Dockerfile.processorを作成
- [ ] Dockerfile.extractorを作成
- [ ] ローカルで両イメージのビルド成功を確認

### Week 2: CI/CD整備
- [ ] GitHub Actions更新
- [ ] dev環境にデプロイテスト
- [ ] processor関数の動作確認（動画生成）
- [ ] extractor関数の動作確認（BattleStats抽出）

### Week 3: 本番デプロイ
- [ ] 問題なければ本番環境にデプロイ
- [ ] 1週間監視
- [ ] 旧Dockerfileを削除またはアーカイブ

---

## 代替案

### 代替案1: 現状維持（minimap_rendererのreplay_unpackを共用）
**メリット**: 変更不要、即座に対応可能
**デメリット**: JSONDecodeErrorが続く可能性、根本解決にならない

### 代替案2: replays_unpack_upstreamをforkして修正
**メリット**: 1つのDockerイメージで統一可能
**デメリット**:
- メンテナンス負担増
- minimap_rendererとの互換性維持が困難
- 上流の更新を取り込みにくい

### 代替案3: BattleStats抽出を別サービス化
**メリット**: 完全分離、スケーリング柔軟
**デメリット**:
- アーキテクチャ大幅変更
- コスト増（別のLambda or ECS）
- オーバーエンジニアリング

---

## 結論

**推奨**: Dockerイメージ分離（本計画）を実施

**理由**:
1. JSONDecodeErrorの根本原因（バージョン衝突）を完全解消
2. 実装コストが妥当（1-2週間）
3. 長期的なメンテナンス性向上
4. リスクは管理可能

**次のステップ**:
1. この計画をレビュー・承認
2. Week 1から実装開始
3. dev環境でテスト後、本番デプロイ

---

## 補足: Dockerfile.processor と Dockerfile.extractor の概要

### Dockerfile.processor
```dockerfile
FROM public.ecr.aws/lambda/python:3.10

# FFmpegインストール
RUN cd /tmp && \
    wget -O ffmpeg.tar.xz "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz" && \
    tar xf ffmpeg.tar.xz && \
    mv */ffmpeg /usr/local/bin/ && \
    rm -rf *

# minimap_renderer (replay_unpack含む)
COPY minimap_renderer/ ./minimap_renderer/
RUN pip install --no-cache-dir -r ./minimap_renderer/requirements.txt && \
    pip install --no-cache-dir ./minimap_renderer/

# processor関連コード
COPY src/replay_processor.py .
COPY src/replay_processor_handler.py .
COPY src/lambda_handler.py .
COPY src/generate_video_api_handler.py .
COPY config/map_names.yaml .

ENV IMAGEIO_FFMPEG_EXE=/usr/local/bin/ffmpeg
CMD ["lambda_handler.handle_interaction"]
```

### Dockerfile.extractor
```dockerfile
FROM public.ecr.aws/lambda/python:3.10

# 軽量な依存関係のみ
COPY config/requirements_lambda.txt .
RUN pip install --no-cache-dir -r requirements_lambda.txt

# replays_unpack_upstreamのみ
COPY replays_unpack_upstream/ ./replays_unpack_upstream/
RUN sed -i "/__all__ = \[/a\    'BattleStats'," \
    ./replays_unpack_upstream/replay_unpack/clients/wows/network/packets/__init__.py

# extractor関連コード
COPY src/battle_result_extractor_handler.py .
COPY src/upload_api_handler.py .
COPY src/search_api_handler.py .
COPY src/match_detail_api_handler.py .
COPY src/utils/battle_stats_extractor.py ./utils/

CMD ["battle_result_extractor_handler.handle"]
```
