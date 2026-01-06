import json
import struct
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple, Dict
import urllib.request
import urllib.parse

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 艦船データのキャッシュ
_SHIP_DATA_CACHE: Optional[Dict[str, dict]] = None

# クラン情報のキャッシュ
_PLAYER_ACCOUNT_CACHE: Dict[str, Optional[int]] = {}  # player_name -> account_id
_CLAN_INFO_CACHE: Dict[int, Optional[dict]] = {}  # account_id -> clan_info (clan_id, tag)


class ReplayProcessor:
    """WoWSリプレイファイルの解析とMP4生成を行うクラス"""

    @staticmethod
    def load_ship_data() -> Dict[str, dict]:
        """
        艦船データを読み込む（初回のみ、以降はキャッシュを使用）

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
                ships_json = files("renderer.resources").joinpath("ships.json").read_text(encoding="utf-8")
                _SHIP_DATA_CACHE = json.loads(ships_json)
                logger.info(f"艦船データを読み込みました: {len(_SHIP_DATA_CACHE)}隻")
                return _SHIP_DATA_CACHE
            except Exception as e:
                logger.warning(f"艦船データの読み込みに失敗: {e}")
                _SHIP_DATA_CACHE = {}
                return _SHIP_DATA_CACHE

        except Exception as e:
            logger.warning(f"importlib.resourcesのインポートに失敗: {e}")
            _SHIP_DATA_CACHE = {}
            return _SHIP_DATA_CACHE

    @staticmethod
    def fetch_ship_name_from_api(ship_id: int) -> Optional[str]:
        """
        WoWS APIから艦船名を取得

        Args:
            ship_id: 艦船ID

        Returns:
            艦船名（取得できない場合は None）
        """
        try:
            # WoWS Asia API
            application_id = "a3045a196f55957db04b72a1b747f8e0"
            url = (
                f"https://api.worldofwarships.asia/wows/encyclopedia/ships/"
                f"?application_id={application_id}&ship_id={ship_id}&fields=name"
            )

            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))

                if data.get("status") == "ok" and "data" in data:
                    ship_data = data["data"].get(str(ship_id))
                    if ship_data and "name" in ship_data:
                        ship_name = ship_data["name"]
                        logger.info(f"APIから艦船名を取得: {ship_id} -> {ship_name}")

                        # キャッシュに保存
                        global _SHIP_DATA_CACHE
                        if _SHIP_DATA_CACHE is None:
                            _SHIP_DATA_CACHE = {}
                        _SHIP_DATA_CACHE[str(ship_id)] = {"name": ship_name}

                        return ship_name

        except Exception as e:
            logger.warning(f"APIからの艦船名取得エラー (ID: {ship_id}): {e}")

        return None

    @staticmethod
    def get_ship_name(ship_id: int) -> str:
        """
        艦船IDから艦船名を取得（ローカルデータ → API）

        Args:
            ship_id: 艦船ID

        Returns:
            艦船名（取得できない場合は "Unknown Ship (ID: xxxxx)"）
        """
        ship_data = ReplayProcessor.load_ship_data()
        ship_id_str = str(ship_id)

        # まずローカルデータから検索
        if ship_id_str in ship_data:
            return ship_data[ship_id_str].get("name", "Unknown Ship")

        # ローカルにない場合、APIから取得
        api_name = ReplayProcessor.fetch_ship_name_from_api(ship_id)
        if api_name:
            return api_name

        # 取得できなかった場合
        return f"Unknown Ship (ID: {ship_id})"

    @staticmethod
    def fetch_account_id_from_api(player_name: str) -> Optional[int]:
        """
        WoWS APIからプレイヤー名でaccount_idを取得

        Args:
            player_name: プレイヤー名

        Returns:
            account_id（取得できない場合は None）
        """
        # キャッシュから検索
        if player_name in _PLAYER_ACCOUNT_CACHE:
            return _PLAYER_ACCOUNT_CACHE[player_name]

        try:
            application_id = "a3045a196f55957db04b72a1b747f8e0"
            encoded_name = urllib.parse.quote(player_name)
            url = (
                f"https://api.worldofwarships.asia/wows/account/list/"
                f"?application_id={application_id}&search={encoded_name}"
            )

            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))

                if data.get("status") == "ok" and "data" in data:
                    players = data["data"]
                    if players and len(players) > 0:
                        # 完全一致を探す
                        for player in players:
                            if player.get("nickname") == player_name:
                                account_id = player.get("account_id")
                                logger.info(f"APIからアカウントIDを取得: {player_name} -> {account_id}")
                                _PLAYER_ACCOUNT_CACHE[player_name] = account_id
                                return account_id

                        # 完全一致がない場合は最初の結果を使用
                        account_id = players[0].get("account_id")
                        logger.info(f"APIからアカウントIDを取得（部分一致）: {player_name} -> {account_id}")
                        _PLAYER_ACCOUNT_CACHE[player_name] = account_id
                        return account_id

        except Exception as e:
            logger.warning(f"APIからのアカウントID取得エラー ({player_name}): {e}")

        _PLAYER_ACCOUNT_CACHE[player_name] = None
        return None

    @staticmethod
    def fetch_clan_info_from_api(account_id: int) -> Optional[dict]:
        """
        WoWS APIからaccount_idでクラン情報を取得

        Args:
            account_id: アカウントID

        Returns:
            {'clan_id': int, 'tag': str} または None
        """
        # キャッシュから検索
        if account_id in _CLAN_INFO_CACHE:
            return _CLAN_INFO_CACHE[account_id]

        try:
            # Step 1: account_idからclan_idを取得
            application_id = "a3045a196f55957db04b72a1b747f8e0"
            url = (
                f"https://api.worldofwarships.asia/wows/clans/accountinfo/"
                f"?application_id={application_id}&account_id={account_id}"
            )

            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))

                if data.get("status") == "ok" and "data" in data:
                    account_data = data["data"].get(str(account_id))
                    if account_data and account_data.get("clan_id"):
                        clan_id = account_data["clan_id"]

                        # Step 2: clan_idからtagを取得
                        clan_url = (
                            f"https://api.worldofwarships.asia/wows/clans/info/"
                            f"?application_id={application_id}&clan_id={clan_id}"
                        )

                        with urllib.request.urlopen(clan_url, timeout=5) as clan_response:
                            clan_data = json.loads(clan_response.read().decode("utf-8"))

                            if clan_data.get("status") == "ok" and "data" in clan_data:
                                clan_info = clan_data["data"].get(str(clan_id))
                                if clan_info and "tag" in clan_info:
                                    tag = clan_info["tag"]
                                    result = {"clan_id": clan_id, "tag": tag}
                                    logger.info(f"APIからクラン情報を取得: account_id={account_id} -> [{tag}]")
                                    _CLAN_INFO_CACHE[account_id] = result
                                    return result

        except Exception as e:
            logger.warning(f"APIからのクラン情報取得エラー (account_id: {account_id}): {e}")

        _CLAN_INFO_CACHE[account_id] = None
        return None

    @staticmethod
    def get_player_clan_tag(player_name: str) -> Optional[str]:
        """
        プレイヤー名からクランタグを取得

        Args:
            player_name: プレイヤー名

        Returns:
            クランタグ（所属していない場合や取得できない場合は None）
        """
        # Step 1: プレイヤー名からaccount_idを取得
        account_id = ReplayProcessor.fetch_account_id_from_api(player_name)
        if not account_id:
            return None

        # Step 2: account_idからクラン情報を取得
        clan_info = ReplayProcessor.fetch_clan_info_from_api(account_id)
        if clan_info and "tag" in clan_info:
            return clan_info["tag"]

        return None

    @staticmethod
    def parse_replay_metadata(replay_path: Path) -> Optional[dict]:
        """
        リプレイファイルからメタデータを抽出

        WoWSリプレイファイル形式:
        - 最初の12バイト: ヘッダー
          - 0-3: Magic number (0x11343212)
          - 4-7: Block 1のサイズ
          - 8-11: Block 2（JSON）のサイズ
        - Block 2: JSONメタデータ
        - 残り: バイナリデータ

        Args:
            replay_path: リプレイファイルのパス

        Returns:
            メタデータの辞書 または None
        """
        try:
            with open(replay_path, "rb") as f:
                # 最初の12バイトのヘッダーを読み取り
                header = f.read(12)
                if len(header) < 12:
                    logger.error("リプレイファイルが不正です: ヘッダー情報が不足しています")
                    return None

                # ヘッダーを解析
                magic = struct.unpack("<I", header[0:4])[0]
                _block1_size = struct.unpack("<I", header[4:8])[0]  # noqa: F841
                json_size = struct.unpack("<I", header[8:12])[0]

                # Magic numberの確認（任意）
                if magic != 0x11343212:
                    logger.warning(f"予期しないMagic number: 0x{magic:08x}")

                # JSONブロック（Block 2）を読み取り
                json_data = f.read(json_size)

                if len(json_data) < json_size:
                    logger.error(
                        f"リプレイファイルが不正です: JSONデータが不完全です（期待: {json_size}, 実際: {len(json_data)}）"
                    )
                    return None

                # JSONをパース
                metadata = json.loads(json_data.decode("utf-8"))
                logger.info("リプレイメタデータの解析に成功しました")

                return metadata

        except Exception as e:
            logger.error(f"リプレイファイルの解析エラー: {e}", exc_info=True)
            return None

    @staticmethod
    def extract_battle_time(metadata: dict) -> Optional[str]:
        """
        メタデータから対戦時間を抽出

        Args:
            metadata: リプレイメタデータ

        Returns:
            フォーマットされた対戦時間 または None
        """
        try:
            # dateTimeキーから対戦時間を取得
            date_time_str = metadata.get("dateTime")

            if not date_time_str:
                logger.warning("メタデータにdateTime情報がありません")
                return None

            # フォーマット例: "09.01.2026 12:34:56"
            # または "DD.MM.YYYY HH:MM:SS"
            try:
                # パース
                dt = datetime.strptime(date_time_str, "%d.%m.%Y %H:%M:%S")
                # 日本語形式にフォーマット
                formatted = dt.strftime("%Y年%m月%d日 %H:%M:%S")
                return formatted
            except ValueError:
                # 別のフォーマットを試す
                logger.warning(f"日時フォーマットの解析に失敗: {date_time_str}")
                return date_time_str

        except Exception as e:
            logger.error(f"対戦時間の抽出エラー: {e}", exc_info=True)
            return None

    @staticmethod
    def extract_game_type(metadata: dict) -> Optional[str]:
        """
        メタデータからゲームタイプを抽出

        Args:
            metadata: リプレイメタデータ

        Returns:
            ゲームタイプ文字列 (例: "ClanBattle", "RandomBattle", "RankBattle") または None
        """
        try:
            # matchGroupキーからゲームタイプを取得
            match_group = metadata.get("matchGroup")

            if match_group:
                logger.info(f"ゲームタイプ (matchGroup): {match_group}")
                return match_group

            # gameLogicキーから取得を試みる
            game_logic = metadata.get("gameLogic")
            if game_logic:
                logger.info(f"ゲームタイプ (gameLogic): {game_logic}")
                return game_logic

            # battleTypeキーから取得を試みる
            battle_type = metadata.get("battleType")
            if battle_type:
                logger.info(f"ゲームタイプ (battleType): {battle_type}")
                return battle_type

            logger.warning("メタデータにゲームタイプ情報がありません")
            logger.debug(f"利用可能なメタデータキー: {list(metadata.keys())}")
            return None

        except Exception as e:
            logger.error(f"ゲームタイプの抽出エラー: {e}", exc_info=True)
            return None

    @staticmethod
    def extract_players_info(metadata: dict) -> dict:
        """
        メタデータからプレイヤー情報を抽出して敵味方に分類

        Args:
            metadata: リプレイメタデータ

        Returns:
            {
                'own': [{'name': str, 'shipId': int, 'shipName': str, 'clanTag': str or None}, ...],
                'allies': [{'name': str, 'shipId': int, 'shipName': str, 'clanTag': str or None}, ...],
                'enemies': [{'name': str, 'shipId': int, 'shipName': str, 'clanTag': str or None}, ...]
            }
        """
        players_info = {"own": [], "allies": [], "enemies": []}

        try:
            vehicles = metadata.get("vehicles", [])

            for player in vehicles:
                ship_id = player.get("shipId", 0)
                ship_name = ReplayProcessor.get_ship_name(ship_id)
                player_name = player.get("name", "Unknown")

                # クランタグを取得
                clan_tag = ReplayProcessor.get_player_clan_tag(player_name)

                player_data = {
                    "name": player_name,
                    "shipId": ship_id,
                    "shipName": ship_name,
                    "clanTag": clan_tag,
                }

                relation = player.get("relation", 2)

                if relation == 0:
                    # 自分
                    players_info["own"].append(player_data)
                elif relation == 1:
                    # 味方
                    players_info["allies"].append(player_data)
                else:
                    # 敵（relation == 2 または不明）
                    players_info["enemies"].append(player_data)

            logger.info(
                f"プレイヤー情報を抽出: 自分={len(players_info['own'])}, "
                f"味方={len(players_info['allies'])}, 敵={len(players_info['enemies'])}"
            )

            return players_info

        except Exception as e:
            logger.error(f"プレイヤー情報の抽出エラー: {e}", exc_info=True)
            return players_info

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

            from renderer.render import Renderer
            from replay_parser import ReplayParser

            # stdout/stderrを/dev/nullにリダイレクト
            # （ReplayParserとRenderer内部でバイナリデータが出力されるのを防ぐ）
            import sys
            import os

            original_stdout = sys.stdout
            original_stderr = sys.stderr
            devnull = open(os.devnull, "w")

            try:
                sys.stdout = devnull
                sys.stderr = devnull

                # リプレイファイルをパース
                logger.info("リプレイファイルをパース中...")
                with open(replay_path, "rb") as f:
                    replay_info = ReplayParser(f, strict=True, raw_data_output=False).get_info()

                logger.info(f"リプレイバージョン: {replay_info['open']['clientVersionFromExe']}")

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
            builds_path = replay_path.parent / f"{replay_path.stem}-builds.json"
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
            logger.error(f"minimap_rendererのインポートに失敗: {e}", exc_info=True)
            return False
        except Exception as e:
            logger.error(f"MP4生成エラー: {e}", exc_info=True)
            return False

    @classmethod
    def process_replay(
        cls,
        replay_path: Path,
        output_dir: Path,
        minimap_renderer_path: Optional[str] = None,
    ) -> Tuple[Optional[str], Optional[str], Optional[Path], dict]:
        """
        リプレイファイルを処理して対戦時間、ゲームタイプ、MP4、プレイヤー情報を生成

        Args:
            replay_path: リプレイファイルのパス
            output_dir: 出力ディレクトリ
            minimap_renderer_path: minimap_rendererの実行パス

        Returns:
            (対戦時間, ゲームタイプ, MP4ファイルパス, プレイヤー情報) のタプル
        """
        # メタデータを解析
        metadata = cls.parse_replay_metadata(replay_path)

        battle_time = None
        game_type = None
        players_info = {"own": [], "allies": [], "enemies": []}

        if metadata:
            battle_time = cls.extract_battle_time(metadata)
            game_type = cls.extract_game_type(metadata)
            players_info = cls.extract_players_info(metadata)

        # MP4を生成
        output_dir.mkdir(parents=True, exist_ok=True)
        mp4_path = output_dir / f"{replay_path.stem}.mp4"

        success = cls.generate_minimap_video(replay_path, mp4_path, minimap_renderer_path)

        if success and mp4_path.exists():
            logger.info(f"MP4ファイルを生成しました: {mp4_path}")
            return battle_time, game_type, mp4_path, players_info
        else:
            logger.warning("MP4ファイルの生成に失敗しました")
            return battle_time, game_type, None, players_info
