"""
リプレイ処理モジュール（renderer依存版）

minimap_rendererを使用したMP4動画生成機能のみを提供する。
メタデータ解析機能はutils.replay_metadataを使用すること。
"""

import json
import logging
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 艦船データのキャッシュ（ローカルファイルから読み込み）
_SHIP_DATA_CACHE: Optional[Dict[str, dict]] = None


class ReplayProcessor:
    """
    WoWSリプレイファイルのMP4生成を行うクラス

    renderer依存の機能のみを提供：
    - ローカル艦船データの読み込み（renderer.resources）
    - minimap_rendererを使用したMP4動画生成

    メタデータ解析はutils.replay_metadata.ReplayMetadataParserを使用すること。
    """

    @staticmethod
    def load_ship_data() -> Dict[str, dict]:
        """
        艦船データを読み込む（初回のみ、以降はキャッシュを使用）
        renderer.resourcesからships.jsonを読み込む

        Returns:
            艦船ID -> 艦船情報の辞書
        """
        global _SHIP_DATA_CACHE

        if _SHIP_DATA_CACHE is not None:
            return _SHIP_DATA_CACHE

        try:
            # インストールされたrendererパッケージから艦船データを読み込み
            try:
                from importlib.resources import files
            except ImportError:
                # Python 3.9以前のフォールバック
                from importlib_resources import files

            try:
                # renderer.resourcesパッケージからships.jsonを読み込む
                ships_json = (
                    files("renderer.resources")
                    .joinpath("ships.json")
                    .read_text(encoding="utf-8")
                )
                _SHIP_DATA_CACHE = json.loads(ships_json)
                logger.info(
                    f"艦船データを読み込みました: {len(_SHIP_DATA_CACHE)}隻"
                )
                return _SHIP_DATA_CACHE
            except Exception as e:
                logger.warning(f"艦船データの読み込みに失敗: {e}")
                _SHIP_DATA_CACHE = {}
                return _SHIP_DATA_CACHE

        except Exception as e:
            logger.warning(f"importlib.resourcesのインポートに失敗: {e}")
            _SHIP_DATA_CACHE = {}
            return _SHIP_DATA_CACHE

    @classmethod
    def get_ship_name(cls, ship_id: int) -> str:
        """
        艦船IDから艦船名を取得（ローカルデータのみ）

        Args:
            ship_id: 艦船ID

        Returns:
            艦船名（取得できない場合は "Unknown Ship (ID: xxxxx)"）
        """
        ship_data = cls.load_ship_data()
        ship_id_str = str(ship_id)

        if ship_id_str in ship_data:
            return ship_data[ship_id_str].get("name", "Unknown Ship")

        return f"Unknown Ship (ID: {ship_id})"

    @staticmethod
    def generate_minimap_video(
        replay_path: Path,
        output_path: Path,
        minimap_renderer_path: Optional[str] = None,
    ) -> bool:
        """
        minimap_rendererを使用してMP4動画を生成

        Args:
            replay_path: リプレイファイルのパス
            output_path: 出力MP4ファイルのパス
            minimap_renderer_path: minimap_rendererの実行パス（省略時はvenv-rendererのPython）

        Returns:
            成功した場合True、失敗した場合False
        """
        try:
            # minimap_rendererのモジュールを直接インポートして実行
            logger.info(f"minimap_rendererでMP4を生成: {replay_path}")

            # FFmpegのパスを環境変数に設定（imageio-ffmpegが検出できるように）
            import sys
            import os

            ffmpeg_path = "/usr/local/bin/ffmpeg"
            if os.path.exists(ffmpeg_path):
                logger.info(f"FFmpegバイナリが見つかりました: {ffmpeg_path}")
                os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path
            else:
                logger.warning(
                    f"FFmpegバイナリが見つかりません: {ffmpeg_path}"
                )
                # 環境変数が設定されているか確認
                if "IMAGEIO_FFMPEG_EXE" in os.environ:
                    logger.info(
                        f"環境変数IMAGEIO_FFMPEG_EXEは設定されています: {os.environ['IMAGEIO_FFMPEG_EXE']}"
                    )
                else:
                    logger.error(
                        "環境変数IMAGEIO_FFMPEG_EXEが設定されていません"
                    )

            from renderer.render import Renderer
            from replay_parser import ReplayParser

            # stdout/stderrを/dev/nullにリダイレクト
            # （ReplayParserとRenderer内部でバイナリデータが出力されるのを防ぐ）

            original_stdout = sys.stdout
            original_stderr = sys.stderr
            devnull = open(os.devnull, "w")

            try:
                sys.stdout = devnull
                sys.stderr = devnull

                # リプレイファイルをパース
                logger.info("リプレイファイルをパース中...")
                with open(replay_path, "rb") as f:
                    replay_info = ReplayParser(
                        f, strict=True, raw_data_output=False
                    ).get_info()

                logger.info(
                    f"リプレイバージョン: {replay_info['open']['clientVersionFromExe']}"
                )

                # レンダラーでMP4を生成
                logger.info("MP4動画をレンダリング中...")

                renderer = Renderer(
                    replay_info["hidden"]["replay_data"],
                    logs=False,  # Lambda環境ではログ出力を無効化（バイナリデータの出力を防ぐ）
                    enable_chat=True,
                    use_tqdm=False,  # Lambda環境ではtqdmを無効化
                )

                # 一時的にデフォルト出力先に生成
                default_output = replay_path.with_suffix(".mp4")
                renderer.start(str(default_output))
            finally:
                # stdout/stderrを復元
                sys.stdout = original_stdout
                sys.stderr = original_stderr
                devnull.close()

            # プレイヤービルド情報をJSONで保存
            builds_path = (
                replay_path.parent / f"{replay_path.stem}-builds.json"
            )
            with open(builds_path, "w") as fp:
                json.dump(renderer.get_player_build(), fp, indent=4)

            # 出力ファイルを指定された場所に移動
            if default_output.exists():
                if default_output != output_path:
                    import shutil

                    shutil.move(str(default_output), str(output_path))
                logger.info(f"MP4動画の生成に成功しました: {output_path}")
                return True
            else:
                logger.error(f"MP4ファイルが見つかりません: {default_output}")
                return False

        except ImportError as e:
            logger.error(
                f"minimap_rendererのインポートに失敗: {e}", exc_info=True
            )
            return False
        except Exception as e:
            logger.error(f"MP4生成エラー: {e}", exc_info=True)
            return False

    @staticmethod
    def generate_dual_minimap_video(
        green_replay_path: Path,
        red_replay_path: Path,
        output_path: Path,
        green_tag: Optional[str] = None,
        red_tag: Optional[str] = None,
    ) -> bool:
        """
        RenderDualを使用して両陣営視点のMP4動画を生成

        Args:
            green_replay_path: 味方視点のリプレイファイルパス
            red_replay_path: 敵視点のリプレイファイルパス
            output_path: 出力MP4ファイルのパス
            green_tag: 味方チームのタグ（クランタグ等）
            red_tag: 敵チームのタグ（クランタグ等）

        Returns:
            成功した場合True、失敗した場合False
        """
        try:
            logger.info(
                f"RenderDualでMP4を生成: green={green_replay_path}, red={red_replay_path}"
            )

            import sys
            import os

            # FFmpegのパスを環境変数に設定
            ffmpeg_path = "/usr/local/bin/ffmpeg"
            if os.path.exists(ffmpeg_path):
                logger.info(f"FFmpegバイナリが見つかりました: {ffmpeg_path}")
                os.environ["IMAGEIO_FFMPEG_EXE"] = ffmpeg_path
            else:
                logger.warning(
                    f"FFmpegバイナリが見つかりません: {ffmpeg_path}"
                )
                if "IMAGEIO_FFMPEG_EXE" in os.environ:
                    logger.info(
                        f"環境変数IMAGEIO_FFMPEG_EXE: {os.environ['IMAGEIO_FFMPEG_EXE']}"
                    )
                else:
                    logger.error(
                        "環境変数IMAGEIO_FFMPEG_EXEが設定されていません"
                    )

            from renderer.render import RenderDual
            from replay_parser import ReplayParser

            original_stdout = sys.stdout
            original_stderr = sys.stderr
            devnull = open(os.devnull, "w")

            try:
                sys.stdout = devnull
                sys.stderr = devnull

                # 両方のリプレイファイルをパース
                logger.info("greenリプレイファイルをパース中...")
                with open(green_replay_path, "rb") as f:
                    green_info = ReplayParser(
                        f, strict=True, raw_data_output=False
                    ).get_info()

                logger.info("redリプレイファイルをパース中...")
                with open(red_replay_path, "rb") as f:
                    red_info = ReplayParser(
                        f, strict=True, raw_data_output=False
                    ).get_info()

                logger.info(
                    f"リプレイバージョン: green={green_info['open']['clientVersionFromExe']}, "
                    f"red={red_info['open']['clientVersionFromExe']}"
                )

                # RenderDualでMP4を生成
                logger.info("Dual MP4動画をレンダリング中...")

                renderer = RenderDual(
                    green_info["hidden"]["replay_data"],
                    red_info["hidden"]["replay_data"],
                    green_tag=green_tag,
                    red_tag=red_tag,
                    logs=False,
                    enable_chat=True,
                    use_tqdm=False,
                )

                # 出力パスに直接生成
                renderer.start(str(output_path))

            finally:
                sys.stdout = original_stdout
                sys.stderr = original_stderr
                devnull.close()

            if output_path.exists():
                logger.info(f"Dual MP4動画の生成に成功しました: {output_path}")
                return True
            else:
                logger.error(
                    f"Dual MP4ファイルが見つかりません: {output_path}"
                )
                return False

        except ImportError as e:
            logger.error(f"RenderDualのインポートに失敗: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"Dual MP4生成エラー: {e}", exc_info=True)
            return False
