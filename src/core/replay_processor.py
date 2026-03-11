"""
リプレイ処理モジュール

Rust wows-replay-tool を使用したMP4動画生成機能を提供する。
"""

import logging
import os
import subprocess
from pathlib import Path

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# Rust バイナリのパス
WOWS_REPLAY_TOOL_PATH = os.environ.get("WOWS_REPLAY_TOOL_PATH", "/opt/bin/wows-replay-tool")
GAME_DATA_DIR = os.environ.get("GAME_DATA_DIR", "/opt/game-data")


class ReplayProcessor:
    """
    WoWSリプレイファイルのMP4生成を行うクラス

    Rust wows-replay-tool render サブコマンドを使用して動画を生成する。
    """

    @staticmethod
    def generate_minimap_video(
        replay_path: Path,
        output_path: Path,
    ) -> bool:
        """
        Rust wows-replay-tool を使用してミニマップMP4動画を生成

        Args:
            replay_path: リプレイファイルのパス
            output_path: 出力MP4ファイルのパス

        Returns:
            成功した場合True、失敗した場合False
        """
        try:
            tool_path = WOWS_REPLAY_TOOL_PATH
            game_data = GAME_DATA_DIR

            if not os.path.exists(tool_path):
                logger.error(f"wows-replay-tool が見つかりません: {tool_path}")
                return False

            if not os.path.exists(game_data):
                logger.error(f"game-data ディレクトリが見つかりません: {game_data}")
                return False

            cmd = [
                tool_path,
                "render",
                "--replay",
                str(replay_path),
                "--game-data",
                game_data,
                "--output",
                str(output_path),
            ]

            logger.info(f"Rust render 実行: {' '.join(cmd)}")

            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=600,
            )

            if result.stdout:
                logger.info(f"Rust render stdout: {result.stdout[:1000]}")
            if result.stderr:
                log_fn = logger.info if result.returncode == 0 else logger.error
                log_fn(f"Rust render stderr: {result.stderr[:2000]}")

            if result.returncode != 0:
                logger.error(f"Rust render 失敗 (code={result.returncode})")
                return False

            if not output_path.exists():
                logger.error(f"出力ファイルが見つかりません: {output_path}")
                return False

            file_size = output_path.stat().st_size
            logger.info(f"MP4生成成功: {output_path} ({file_size:,} bytes)")
            return True

        except subprocess.TimeoutExpired:
            logger.error("Rust render タイムアウト (600秒)")
            return False
        except Exception as e:
            logger.error(f"MP4生成エラー: {e}", exc_info=True)
            return False
