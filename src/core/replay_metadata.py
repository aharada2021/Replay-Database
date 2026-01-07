"""
リプレイメタデータ解析モジュール（軽量版）

rendererに依存しない、純粋なメタデータ解析機能を提供する。
艦船名・クラン情報はWoWS APIから取得する。
"""

import json
import struct
import logging
import urllib.request
import urllib.parse
from datetime import datetime
from pathlib import Path
from typing import Optional, Dict

logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# キャッシュ
_SHIP_NAME_CACHE: Dict[int, str] = {}  # ship_id -> ship_name
_PLAYER_ACCOUNT_CACHE: Dict[str, Optional[int]] = {}  # player_name -> account_id
_CLAN_INFO_CACHE: Dict[int, Optional[dict]] = {}  # account_id -> clan_info


class ReplayMetadataParser:
    """リプレイファイルのメタデータ解析クラス（軽量版）"""

    # WoWS API Application ID
    WOWS_API_APP_ID = "a3045a196f55957db04b72a1b747f8e0"

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
                        f"リプレイファイルが不正です: JSONデータが不完全です"
                        f"（期待: {json_size}, 実際: {len(json_data)}）"
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
            date_time_str = metadata.get("dateTime")

            if not date_time_str:
                logger.warning("メタデータにdateTime情報がありません")
                return None

            try:
                # パース (フォーマット: "DD.MM.YYYY HH:MM:SS")
                dt = datetime.strptime(date_time_str, "%d.%m.%Y %H:%M:%S")
                # 日本語形式にフォーマット
                formatted = dt.strftime("%Y年%m月%d日 %H:%M:%S")
                return formatted
            except ValueError:
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
            return None

        except Exception as e:
            logger.error(f"ゲームタイプの抽出エラー: {e}", exc_info=True)
            return None

    @classmethod
    def fetch_ship_name_from_api(cls, ship_id: int) -> Optional[str]:
        """
        WoWS APIから艦船名を取得

        Args:
            ship_id: 艦船ID

        Returns:
            艦船名（取得できない場合は None）
        """
        # キャッシュから検索
        if ship_id in _SHIP_NAME_CACHE:
            return _SHIP_NAME_CACHE[ship_id]

        try:
            url = (
                f"https://api.worldofwarships.asia/wows/encyclopedia/ships/"
                f"?application_id={cls.WOWS_API_APP_ID}&ship_id={ship_id}&fields=name&language=en"
            )

            with urllib.request.urlopen(url, timeout=5) as response:
                data = json.loads(response.read().decode("utf-8"))

                if data.get("status") == "ok" and "data" in data:
                    ship_data = data["data"].get(str(ship_id))
                    if ship_data and "name" in ship_data:
                        ship_name = ship_data["name"]
                        logger.info(f"APIから艦船名を取得: {ship_id} -> {ship_name}")
                        _SHIP_NAME_CACHE[ship_id] = ship_name
                        return ship_name

        except Exception as e:
            logger.warning(f"APIからの艦船名取得エラー (ID: {ship_id}): {e}")

        return None

    @classmethod
    def get_ship_name(cls, ship_id: int) -> str:
        """
        艦船IDから艦船名を取得（APIから取得）

        Args:
            ship_id: 艦船ID

        Returns:
            艦船名（取得できない場合は "Unknown Ship (ID: xxxxx)"）
        """
        api_name = cls.fetch_ship_name_from_api(ship_id)
        if api_name:
            return api_name
        return f"Unknown Ship (ID: {ship_id})"

    @classmethod
    def fetch_account_id_from_api(cls, player_name: str) -> Optional[int]:
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
            encoded_name = urllib.parse.quote(player_name)
            url = (
                f"https://api.worldofwarships.asia/wows/account/list/"
                f"?application_id={cls.WOWS_API_APP_ID}&search={encoded_name}"
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

    @classmethod
    def fetch_clan_info_from_api(cls, account_id: int) -> Optional[dict]:
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
            url = (
                f"https://api.worldofwarships.asia/wows/clans/accountinfo/"
                f"?application_id={cls.WOWS_API_APP_ID}&account_id={account_id}"
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
                            f"?application_id={cls.WOWS_API_APP_ID}&clan_id={clan_id}"
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

    @classmethod
    def get_player_clan_tag(cls, player_name: str) -> Optional[str]:
        """
        プレイヤー名からクランタグを取得

        Args:
            player_name: プレイヤー名

        Returns:
            クランタグ（所属していない場合や取得できない場合は None）
        """
        account_id = cls.fetch_account_id_from_api(player_name)
        if not account_id:
            return None

        clan_info = cls.fetch_clan_info_from_api(account_id)
        if clan_info and "tag" in clan_info:
            return clan_info["tag"]

        return None

    @classmethod
    def extract_players_info(cls, metadata: dict) -> dict:
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
                ship_name = cls.get_ship_name(ship_id)
                player_name = player.get("name", "Unknown")

                # クランタグを取得
                clan_tag = cls.get_player_clan_tag(player_name)

                player_data = {
                    "name": player_name,
                    "shipId": ship_id,
                    "shipName": ship_name,
                    "clanTag": clan_tag,
                }

                relation = player.get("relation", 2)

                if relation == 0:
                    players_info["own"].append(player_data)
                elif relation == 1:
                    players_info["allies"].append(player_data)
                else:
                    players_info["enemies"].append(player_data)

            logger.info(
                f"プレイヤー情報を抽出: 自分={len(players_info['own'])}, "
                f"味方={len(players_info['allies'])}, 敵={len(players_info['enemies'])}"
            )

            return players_info

        except Exception as e:
            logger.error(f"プレイヤー情報の抽出エラー: {e}", exc_info=True)
            return players_info
