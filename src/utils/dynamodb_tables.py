"""
DynamoDB テーブル操作ユーティリティ

新スキーマ（gameType別テーブル）に対応した共通関数を提供
"""

import os
import time
from collections import defaultdict
from datetime import datetime
from decimal import Decimal
from typing import Optional

import boto3


# gameType の正規化マッピング
GAME_TYPE_MAP = {
    "clan": "clan",
    "ranked": "ranked",
    "pvp": "random",
    "pve": "other",
    "cooperative": "other",
    "event": "other",
}

# gameType 別テーブル名（環境変数から取得）
def get_battle_table_name(game_type: str) -> str:
    """
    gameType に対応するテーブル名を環境変数から取得
    """
    table_env_map = {
        "clan": "CLAN_BATTLES_TABLE",
        "ranked": "RANKED_BATTLES_TABLE",
        "random": "RANDOM_BATTLES_TABLE",
        "other": "OTHER_BATTLES_TABLE",
    }
    env_var = table_env_map.get(game_type, "OTHER_BATTLES_TABLE")
    return os.environ.get(env_var, f"wows-{game_type}-battles-dev")


def get_all_battle_table_names() -> dict:
    """
    全 gameType のテーブル名を取得
    """
    return {
        "clan": get_battle_table_name("clan"),
        "ranked": get_battle_table_name("ranked"),
        "random": get_battle_table_name("random"),
        "other": get_battle_table_name("other"),
    }


def normalize_game_type(raw_game_type: str) -> str:
    """
    リプレイファイルの gameType を正規化
    """
    return GAME_TYPE_MAP.get(raw_game_type.lower(), "other")


def parse_datetime_to_unix(date_time_str: str) -> int:
    """
    DD.MM.YYYY HH:MM:SS 形式の日時を Unix timestamp に変換
    """
    try:
        dt = datetime.strptime(date_time_str, "%d.%m.%Y %H:%M:%S")
        return int(dt.timestamp())
    except ValueError:
        return int(time.time())


def unix_to_datetime_str(unix_time: int) -> str:
    """
    Unix timestamp を DD.MM.YYYY HH:MM:SS 形式に変換
    """
    dt = datetime.fromtimestamp(unix_time)
    return dt.strftime("%d.%m.%Y %H:%M:%S")


def create_index_sk(game_type: str, unix_time: int, arena_unique_id: str) -> str:
    """
    インデックステーブルのソートキーを生成
    形式: {gameType}#{unixTime}#{arenaUniqueID}
    """
    return f"{game_type}#{unix_time}#{arena_unique_id}"


def parse_index_sk(sk: str) -> dict:
    """
    インデックステーブルのソートキーをパース
    """
    parts = sk.split("#")
    if len(parts) >= 3:
        return {
            "gameType": parts[0],
            "unixTime": int(parts[1]),
            "arenaUniqueID": parts[2],
        }
    return {}


def decimal_to_python(obj):
    """
    DynamoDB の Decimal 型を Python の int/float に変換
    """
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_python(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_python(i) for i in obj]
    elif isinstance(obj, set):
        return list(decimal_to_python(i) for i in obj)
    return obj


def python_to_decimal(obj):
    """
    Python の int/float を DynamoDB の Decimal 型に変換
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, dict):
        return {k: python_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [python_to_decimal(i) for i in obj]
    return obj


class BattleTableClient:
    """
    バトルテーブル操作クライアント
    """

    def __init__(self, game_type: str):
        self.game_type = normalize_game_type(game_type)
        self.dynamodb = boto3.resource("dynamodb")
        self.table_name = get_battle_table_name(self.game_type)
        self.table = self.dynamodb.Table(self.table_name)

    def get_match(self, arena_unique_id: str) -> Optional[dict]:
        """
        MATCH レコードを取得
        """
        response = self.table.get_item(
            Key={"arenaUniqueID": arena_unique_id, "recordType": "MATCH"}
        )
        item = response.get("Item")
        return decimal_to_python(item) if item else None

    def get_stats(self, arena_unique_id: str) -> Optional[dict]:
        """
        STATS レコードを取得
        """
        response = self.table.get_item(
            Key={"arenaUniqueID": arena_unique_id, "recordType": "STATS"}
        )
        item = response.get("Item")
        return decimal_to_python(item) if item else None

    def get_uploads(self, arena_unique_id: str) -> list:
        """
        UPLOAD レコードを全て取得
        """
        response = self.table.query(
            KeyConditionExpression="arenaUniqueID = :aid AND begins_with(recordType, :prefix)",
            ExpressionAttributeValues={
                ":aid": arena_unique_id,
                ":prefix": "UPLOAD#",
            },
        )
        items = response.get("Items", [])
        return [decimal_to_python(item) for item in items]

    def get_full_match(self, arena_unique_id: str) -> Optional[dict]:
        """
        試合の全データ（MATCH + STATS + UPLOADS）を取得
        """
        response = self.table.query(
            KeyConditionExpression="arenaUniqueID = :aid",
            ExpressionAttributeValues={":aid": arena_unique_id},
        )

        items = response.get("Items", [])
        if not items:
            return None

        result = {"match": None, "stats": None, "uploads": []}

        for item in items:
            record_type = item.get("recordType", "")
            item_data = decimal_to_python(item)

            if record_type == "MATCH":
                result["match"] = item_data
            elif record_type == "STATS":
                result["stats"] = item_data
            elif record_type.startswith("UPLOAD#"):
                result["uploads"].append(item_data)

        return result

    def put_match(self, match_record: dict):
        """
        MATCH レコードを保存
        """
        item = python_to_decimal(match_record)
        item["arenaUniqueID"] = match_record["arenaUniqueID"]
        item["recordType"] = "MATCH"
        self.table.put_item(Item=item)

    def put_stats(self, arena_unique_id: str, all_players_stats: list):
        """
        STATS レコードを保存
        """
        item = {
            "arenaUniqueID": arena_unique_id,
            "recordType": "STATS",
            "allPlayersStats": python_to_decimal(all_players_stats),
        }
        self.table.put_item(Item=item)

    def put_upload(self, upload_record: dict):
        """
        UPLOAD レコードを保存
        """
        player_id = upload_record.get("playerID", 0)
        item = python_to_decimal(upload_record)
        item["arenaUniqueID"] = upload_record["arenaUniqueID"]
        item["recordType"] = f"UPLOAD#{player_id}"
        self.table.put_item(Item=item)

    def update_comment_count(self, arena_unique_id: str, delta: int):
        """
        コメント数を更新
        """
        self.table.update_item(
            Key={"arenaUniqueID": arena_unique_id, "recordType": "MATCH"},
            UpdateExpression="SET commentCount = if_not_exists(commentCount, :zero) + :delta",
            ExpressionAttributeValues={":zero": 0, ":delta": delta},
        )

    def update_video_info(self, arena_unique_id: str, mp4_s3_key: str, generated_at: int):
        """
        動画情報を更新
        """
        self.table.update_item(
            Key={"arenaUniqueID": arena_unique_id, "recordType": "MATCH"},
            UpdateExpression="SET mp4S3Key = :key, mp4GeneratedAt = :at",
            ExpressionAttributeValues={
                ":key": mp4_s3_key,
                ":at": generated_at,
            },
        )

    def list_matches(
        self,
        limit: int = 20,
        last_evaluated_key: dict = None,
        map_id: str = None,
    ) -> dict:
        """
        試合一覧を取得（ページネーション対応）

        Returns:
            {
                "items": [...],
                "lastEvaluatedKey": {...} or None
            }
        """
        if map_id:
            # MapIndex を使用
            query_params = {
                "IndexName": "MapIndex",
                "KeyConditionExpression": "mapId = :mid",
                "ExpressionAttributeValues": {":mid": map_id},
                "ScanIndexForward": False,  # 降順（新しい順）
                "Limit": limit,
            }
        else:
            # ListingIndex を使用
            query_params = {
                "IndexName": "ListingIndex",
                "KeyConditionExpression": "listingKey = :lk",
                "ExpressionAttributeValues": {":lk": "ACTIVE"},
                "ScanIndexForward": False,  # 降順（新しい順）
                "Limit": limit,
            }

        if last_evaluated_key:
            query_params["ExclusiveStartKey"] = last_evaluated_key

        response = self.table.query(**query_params)

        items = [decimal_to_python(item) for item in response.get("Items", [])]
        last_key = response.get("LastEvaluatedKey")

        return {"items": items, "lastEvaluatedKey": last_key}


class IndexTableClient:
    """
    インデックステーブル操作クライアント
    """

    def __init__(self):
        self.dynamodb = boto3.resource("dynamodb")

        # テーブル名を環境変数から取得
        self.ship_table = self.dynamodb.Table(
            os.environ.get("SHIP_INDEX_TABLE", "wows-ship-index-dev")
        )
        self.player_table = self.dynamodb.Table(
            os.environ.get("PLAYER_INDEX_TABLE", "wows-player-index-dev")
        )
        self.clan_table = self.dynamodb.Table(
            os.environ.get("CLAN_INDEX_TABLE", "wows-clan-index-dev")
        )

    def put_ship_index(
        self,
        ship_name: str,
        game_type: str,
        unix_time: int,
        arena_unique_id: str,
        ally_count: int,
        enemy_count: int,
    ):
        """
        艦艇インデックスを保存
        """
        sk = create_index_sk(game_type, unix_time, arena_unique_id)
        self.ship_table.put_item(
            Item={
                "shipName": ship_name.upper(),
                "SK": sk,
                "allyCount": ally_count,
                "enemyCount": enemy_count,
                "totalCount": ally_count + enemy_count,
            }
        )

    def put_player_index(
        self,
        player_name: str,
        game_type: str,
        unix_time: int,
        arena_unique_id: str,
        team: str,
        clan_tag: str,
        ship_name: str,
    ):
        """
        プレイヤーインデックスを保存
        """
        sk = create_index_sk(game_type, unix_time, arena_unique_id)
        self.player_table.put_item(
            Item={
                "playerName": player_name,
                "SK": sk,
                "team": team,
                "clanTag": clan_tag,
                "shipName": ship_name,
            }
        )

    def put_clan_index(
        self,
        clan_tag: str,
        game_type: str,
        unix_time: int,
        arena_unique_id: str,
        team: str,
        member_count: int,
        is_main_clan: bool,
    ):
        """
        クランインデックスを保存
        """
        sk = create_index_sk(game_type, unix_time, arena_unique_id)
        self.clan_table.put_item(
            Item={
                "clanTag": clan_tag,
                "SK": sk,
                "team": team,
                "memberCount": member_count,
                "isMainClan": is_main_clan,
            }
        )

    def search_by_ship(
        self,
        ship_name: str,
        game_type: str = None,
        limit: int = 20,
        last_evaluated_key: dict = None,
    ) -> dict:
        """
        艦艇名で検索
        """
        query_params = {
            "KeyConditionExpression": "shipName = :sn",
            "ExpressionAttributeValues": {":sn": ship_name.upper()},
            "ScanIndexForward": False,
            "Limit": limit,
        }

        if game_type:
            query_params["KeyConditionExpression"] += " AND begins_with(SK, :prefix)"
            query_params["ExpressionAttributeValues"][":prefix"] = f"{game_type}#"

        if last_evaluated_key:
            query_params["ExclusiveStartKey"] = last_evaluated_key

        response = self.ship_table.query(**query_params)

        items = [decimal_to_python(item) for item in response.get("Items", [])]
        last_key = response.get("LastEvaluatedKey")

        return {"items": items, "lastEvaluatedKey": last_key}

    def search_by_player(
        self,
        player_name: str,
        game_type: str = None,
        limit: int = 20,
        last_evaluated_key: dict = None,
    ) -> dict:
        """
        プレイヤー名で検索
        """
        query_params = {
            "KeyConditionExpression": "playerName = :pn",
            "ExpressionAttributeValues": {":pn": player_name},
            "ScanIndexForward": False,
            "Limit": limit,
        }

        if game_type:
            query_params["KeyConditionExpression"] += " AND begins_with(SK, :prefix)"
            query_params["ExpressionAttributeValues"][":prefix"] = f"{game_type}#"

        if last_evaluated_key:
            query_params["ExclusiveStartKey"] = last_evaluated_key

        response = self.player_table.query(**query_params)

        items = [decimal_to_python(item) for item in response.get("Items", [])]
        last_key = response.get("LastEvaluatedKey")

        return {"items": items, "lastEvaluatedKey": last_key}

    def search_by_clan(
        self,
        clan_tag: str,
        game_type: str = None,
        limit: int = 20,
        last_evaluated_key: dict = None,
    ) -> dict:
        """
        クランタグで検索
        """
        query_params = {
            "KeyConditionExpression": "clanTag = :ct",
            "ExpressionAttributeValues": {":ct": clan_tag},
            "ScanIndexForward": False,
            "Limit": limit,
        }

        if game_type:
            query_params["KeyConditionExpression"] += " AND begins_with(SK, :prefix)"
            query_params["ExpressionAttributeValues"][":prefix"] = f"{game_type}#"

        if last_evaluated_key:
            query_params["ExclusiveStartKey"] = last_evaluated_key

        response = self.clan_table.query(**query_params)

        items = [decimal_to_python(item) for item in response.get("Items", [])]
        last_key = response.get("LastEvaluatedKey")

        return {"items": items, "lastEvaluatedKey": last_key}


def find_match_game_type(arena_unique_id: str) -> Optional[str]:
    """
    arenaUniqueID から gameType を特定する

    全バトルテーブルを検索して MATCH レコードを探す
    """
    dynamodb = boto3.resource("dynamodb")

    for game_type in ["clan", "ranked", "random", "other"]:
        table_name = get_battle_table_name(game_type)
        table = dynamodb.Table(table_name)

        try:
            response = table.get_item(
                Key={"arenaUniqueID": arena_unique_id, "recordType": "MATCH"},
                ProjectionExpression="arenaUniqueID",
            )
            if response.get("Item"):
                return game_type
        except Exception:
            continue

    return None
