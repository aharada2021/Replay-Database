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
    wget \
    tar \
    xz \
    && yum clean all

# FFmpegのインストール (ARM64用)
RUN cd /tmp && \
    wget https://johnvansickle.com/ffmpeg/releases/ffmpeg-release-arm64-static.tar.xz && \
    tar xvf ffmpeg-release-arm64-static.tar.xz && \
    mv ffmpeg-*-arm64-static/ffmpeg /usr/local/bin/ && \
    mv ffmpeg-*-arm64-static/ffprobe /usr/local/bin/ && \
    rm -rf ffmpeg-* && \
    chmod +x /usr/local/bin/ffmpeg /usr/local/bin/ffprobe

# 作業ディレクトリ
WORKDIR ${LAMBDA_TASK_ROOT}

# Python依存関係をコピーしてインストール
COPY config/requirements_lambda.txt .
RUN pip install --no-cache-dir -r requirements_lambda.txt

# minimap_rendererをローカルからインストール
COPY minimap_renderer/ ./minimap_renderer/
RUN pip install --no-cache-dir ./minimap_renderer/

# replays_unpack_upstreamをコピー
COPY replays_unpack_upstream/ ./replays_unpack_upstream/

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
