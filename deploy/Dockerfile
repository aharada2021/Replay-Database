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
    wget \
    tar \
    xz \
    && yum clean all

# FFmpegのインストール (ARM64用 - John Van Sickle's static builds)
# たまに応答がない場合があるが、リビルドすれば確実に動作する
RUN cd /tmp && \
    wget -O ffmpeg-release-arm64-static.tar.xz "https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz" && \
    tar xf ffmpeg-release-arm64-static.tar.xz && \
    FFMPEG_BIN=$(find . -type f -name "ffmpeg" | head -n 1) && \
    echo "Found FFmpeg binary: $FFMPEG_BIN" && \
    chmod +x "$FFMPEG_BIN" && \
    mv "$FFMPEG_BIN" /usr/local/bin/ffmpeg && \
    /usr/local/bin/ffmpeg -version && \
    cd /tmp && rm -rf *

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

# 追加のWoWSバージョンサポートをコピー（サブモジュール更新待ちの間の対応）
COPY src/replay_versions/ ./replays_unpack_upstream/replay_unpack/clients/wows/versions/

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

# FFmpegのパスを環境変数に設定
ENV IMAGEIO_FFMPEG_EXE=/usr/local/bin/ffmpeg

# Lambda関数のハンドラーを指定
CMD ["lambda_handler.handle_interaction"]
