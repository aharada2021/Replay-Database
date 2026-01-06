# AWS Lambda Python 3.10 base image
FROM public.ecr.aws/lambda/python:3.10

# システムパッケージのインストール
RUN yum update -y && \
    yum install -y \
    git \
    gcc \
    gcc-c++ \
    make \
    libxml2-devel \
    libxslt-devel \
    python3-devel \
    && yum clean all

# 作業ディレクトリ
WORKDIR ${LAMBDA_TASK_ROOT}

# pipとsetuptoolsをアップグレード
RUN pip install --no-cache-dir --upgrade pip setuptools wheel

# Python依存関係をコピーしてインストール
COPY config/requirements_lambda.txt .
RUN pip install --no-cache-dir -r requirements_lambda.txt

# minimap_rendererをインストール（元のreplay_unpackを含む）
COPY minimap_renderer/ ./minimap_renderer/
RUN pip install --no-cache-dir -r ./minimap_renderer/requirements.txt && \
    pip install --no-cache-dir ./minimap_renderer/

# replays_unpack_upstreamをコピーしてパッチ適用（battle_result_extractor用）
COPY replays_unpack_upstream/ ./replays_unpack_upstream/

# BattleStatsを__all__にエクスポートするパッチを適用
RUN sed -i "/__all__ = \[/a\    'BattleStats'," \
    ./replays_unpack_upstream/replay_unpack/clients/wows/network/packets/__init__.py

# アプリケーションコードをコピー
COPY src/replay_processor.py .
COPY src/lambda_handler.py .
COPY src/replay_processor_handler.py .
COPY src/upload_api_handler.py .
COPY src/battle_result_extractor_handler.py .
COPY src/search_api_handler.py .
COPY src/generate_video_api_handler.py .
COPY src/utils/ ./utils/
COPY config/map_names.yaml .

# ファイルのパーミッションを設定（Lambda runtimeが読めるようにする）
RUN chmod -R 755 ${LAMBDA_TASK_ROOT}

# Lambda関数のハンドラーを指定
CMD ["lambda_handler.handle_interaction"]
