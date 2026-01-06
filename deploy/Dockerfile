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

# FFmpegのインストール (ARM64用 - BtbN/FFmpeg-Builds)
RUN cd /tmp && \
    wget -O ffmpeg-linuxarm64.tar.xz "https://github.com/BtbN/FFmpeg-Builds/releases/download/latest/ffmpeg-master-latest-linuxarm64-gpl.tar.xz" && \
    tar xf ffmpeg-linuxarm64.tar.xz && \
    mv ffmpeg-master-latest-linuxarm64-gpl/bin/ffmpeg /usr/local/bin/ && \
    mv ffmpeg-master-latest-linuxarm64-gpl/bin/ffprobe /usr/local/bin/ && \
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

# BattleStatsを__all__にエクスポートするパッチを適用
# PACKETS_MAPPING_12_6_0エイリアスも追加（minimap_renderer互換性のため）
RUN sed -i "/__all__ = \[/a\    'BattleStats'," \
    ./replays_unpack_upstream/replay_unpack/clients/wows/network/packets/__init__.py && \
    sed -i "s/'PACKETS_MAPPING_12_6'/'PACKETS_MAPPING_12_6',\n    'PACKETS_MAPPING_12_6_0'/" \
    ./replays_unpack_upstream/replay_unpack/clients/wows/network/packets/__init__.py && \
    echo "" >> ./replays_unpack_upstream/replay_unpack/clients/wows/network/packets/__init__.py && \
    echo "# Alias for backward compatibility with minimap_renderer" >> ./replays_unpack_upstream/replay_unpack/clients/wows/network/packets/__init__.py && \
    echo "PACKETS_MAPPING_12_6_0 = PACKETS_MAPPING_12_6" >> ./replays_unpack_upstream/replay_unpack/clients/wows/network/packets/__init__.py

# パッチ適用後にreplays_unpackをインストール
RUN pip install --no-cache-dir ./replays_unpack_upstream/

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
