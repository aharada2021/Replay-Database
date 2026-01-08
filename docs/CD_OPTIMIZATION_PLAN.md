# CD高速化プラン

## 現状分析

### デプロイ時間（2026年1月時点）

| シナリオ | 合計時間 |
|---------|---------|
| キャッシュヒット時 | 2.5〜3分 |
| キャッシュミス時 | 5分 |

### ジョブ別内訳

| ジョブ | キャッシュヒット | キャッシュミス |
|-------|----------------|--------------|
| Setup | 9秒 | 9秒 |
| Build Processor | 46秒 | 2分 |
| Build Extractor | 47秒 | 1.5分 |
| Deploy to Dev | 1.5〜2.5分 | 1.5〜2.5分 |

### 現在のボトルネック

1. **FFmpegダウンロード**（Processor Dockerfile）
   - johnvansickle.comから毎回ダウンロード（キャッシュミス時）
   - 約40MB、30〜40秒

2. **yum update**（両Dockerfile）
   - ベースイメージ更新時に再実行
   - 10〜20秒

3. **Serverless Framework インストール**（Deploy）
   - `npm install -g serverless@3` 毎回実行
   - 15〜20秒

4. **serverless deploy**（Deploy）
   - CloudFormation経由で全Lambda関数を更新
   - 1〜2分（削減困難）

---

## 改善案

### Phase 1: クイックウィン（実装時間: 1-2時間）

#### 1.1 npm/Serverlessのキャッシュ化
**効果**: Deploy時間 -15秒

```yaml
# deploy-lambda.yml の deploy-dev job に追加
- name: Cache npm
  uses: actions/cache@v4
  with:
    path: ~/.npm
    key: npm-serverless-${{ runner.os }}
    restore-keys: npm-serverless-

- name: Install Serverless Framework
  run: npm install -g serverless@3
```

#### 1.2 Dockerレイヤーの最適化
**効果**: キャッシュミス時 -20〜30秒

```dockerfile
# Dockerfile.processor 変更案
FROM public.ecr.aws/lambda/python:3.10

# 依存関係インストール（変更頻度低い）を先に
COPY config/requirements_lambda.txt .
RUN pip install --no-cache-dir --upgrade pip setuptools wheel && \
    pip install --no-cache-dir -r requirements_lambda.txt

# yum + FFmpegを1つのレイヤーに（キャッシュ効率化）
RUN yum update -y && \
    yum install -y git gcc gcc-c++ make libxml2-devel libxslt-devel python3-devel wget tar xz && \
    yum clean all && \
    cd /tmp && \
    wget -q -O ffmpeg.tar.xz "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz" && \
    tar xf ffmpeg.tar.xz && \
    mv $(find . -type f -name "ffmpeg" | head -n 1) /usr/local/bin/ffmpeg && \
    chmod +x /usr/local/bin/ffmpeg && \
    rm -rf /tmp/*

# コード（変更頻度高い）は最後
COPY minimap_renderer/ ./minimap_renderer/
RUN pip install --no-cache-dir -r ./minimap_renderer/requirements.txt && \
    pip install --no-cache-dir ./minimap_renderer/
COPY src/handlers/ ./handlers/
...
```

---

### Phase 2: 中規模改善（実装時間: 2-4時間）

#### 2.1 FFmpeg事前ビルド済みベースイメージ
**効果**: Processorビルド時間 -30〜40秒

ECRにFFmpeg入りベースイメージを保持:

```dockerfile
# deploy/Dockerfile.base-processor（新規作成）
FROM public.ecr.aws/lambda/python:3.10

RUN yum update -y && \
    yum install -y git gcc gcc-c++ make libxml2-devel libxslt-devel python3-devel wget tar xz && \
    yum clean all

RUN cd /tmp && \
    wget -q -O ffmpeg.tar.xz "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz" && \
    tar xf ffmpeg.tar.xz && \
    mv $(find . -type f -name "ffmpeg" | head -n 1) /usr/local/bin/ffmpeg && \
    chmod +x /usr/local/bin/ffmpeg && \
    rm -rf /tmp/*
```

```yaml
# 新ワークフロー: build-base-images.yml（手動実行、月1回程度）
name: Build Base Images
on:
  workflow_dispatch:
jobs:
  build-base:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: docker/setup-buildx-action@v3
      - name: Build and push base image
        run: |
          docker build -f deploy/Dockerfile.base-processor -t $ECR/wows-replay-bot:base-processor .
          docker push $ECR/wows-replay-bot:base-processor
```

```dockerfile
# deploy/Dockerfile.processor（修正）
FROM {account_id}.dkr.ecr.ap-northeast-1.amazonaws.com/wows-replay-bot:base-processor

# ベースイメージにFFmpegとシステムパッケージが含まれているので、
# Python依存関係とコードのみインストール
COPY config/requirements_lambda.txt .
RUN pip install --no-cache-dir -r requirements_lambda.txt
...
```

#### 2.2 変更検知による条件付きビルド
**効果**: 変更なしの場合スキップ（1分以上短縮）

```yaml
# deploy-lambda.yml
jobs:
  detect-changes:
    runs-on: ubuntu-latest
    outputs:
      processor: ${{ steps.filter.outputs.processor }}
      extractor: ${{ steps.filter.outputs.extractor }}
    steps:
      - uses: actions/checkout@v4
      - uses: dorny/paths-filter@v3
        id: filter
        with:
          filters: |
            processor:
              - 'deploy/Dockerfile.processor'
              - 'minimap_renderer/**'
              - 'config/requirements_lambda.txt'
            extractor:
              - 'deploy/Dockerfile.extractor'
              - 'src/**'
              - 'replays_unpack_upstream/**'
              - 'config/**'

  build-processor:
    needs: [setup, detect-changes]
    if: needs.detect-changes.outputs.processor == 'true'
    ...
```

---

### Phase 3: 大規模改善（実装時間: 1日以上）

#### 3.1 Serverless関数ごとの個別デプロイ
**効果**: 変更した関数のみデプロイ（30秒〜1分短縮）

```bash
# 変更検知に基づいて個別デプロイ
serverless deploy function -f interactions --stage dev
serverless deploy function -f upload-api --stage dev
```

ただし、CloudFormationを経由しないため設定変更には不向き。

#### 3.2 GitHub Actionsのlarger runnerを使用
**効果**: ビルド時間 30-50%短縮

```yaml
jobs:
  build-processor:
    runs-on: ubuntu-latest-4core  # 有料オプション
```

---

## 推奨実装順序

| 優先度 | 改善項目 | 効果 | 実装時間 |
|-------|---------|------|---------|
| 1 | npm/Serverlessキャッシュ | -15秒 | 30分 |
| 2 | Dockerレイヤー最適化 | -20秒 | 1時間 |
| 3 | FFmpegベースイメージ | -30秒 | 2時間 |
| 4 | 変更検知条件付きビルド | -1分（変更なし時） | 2時間 |

**Phase 1 + 2 実装後の予想デプロイ時間: 1.5〜2分**

---

## 実装しない方がよい案

1. **DockerレイヤーキャッシュをGitHub Actionsキャッシュに変更**
   - 現在ECRレジストリキャッシュで十分機能している
   - 変更のリスクに見合わない

2. **serverless deployの完全排除**
   - CloudFormation経由でないとIAM/DynamoDB設定が反映されない
   - リスクが高い

3. **Self-hosted runner**
   - 運用コストが高い
   - セキュリティ管理が必要
