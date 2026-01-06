"""
DynamoDB操作ヘルパーモジュール

Version: 2026-01-06 - Added clan tag calculation support
"""

import os
import boto3
from typing import Optional, Dict, Any, List
from datetime import datetime
from collections import Counter


# DynamoDBクライアント（遅延初期化）
_dynamodb = None
REPLAYS_TABLE_NAME = os.environ.get("REPLAYS_TABLE", "wows-replays-dev")


def get_dynamodb_resource():
    """DynamoDBリソースを取得（遅延初期化）"""
    global _dynamodb
    if _dynamodb is None:
        _dynamodb = boto3.resource("dynamodb", region_name=os.environ.get("AWS_REGION", "ap-northeast-1"))
    return _dynamodb


def get_table():
    """DynamoDBテーブルを取得"""
    return get_dynamodb_resource().Table(REPLAYS_TABLE_NAME)


def calculate_main_clan_tag(players: List[Dict[str, Any]]) -> Optional[str]:
    """
    プレイヤーリストから最も多いクランタグを計算

    Args:
        players: プレイヤー情報のリスト

    Returns:
        最も多いクランタグ、またはNone
    """
    if not players:
        return None

    # クランタグを持つプレイヤーのみを抽出
    clan_tags = [p.get("clanTag") for p in players if p.get("clanTag")]

    if not clan_tags:
        return None

    # 最も多いクランタグを取得
    counter = Counter(clan_tags)
    most_common = counter.most_common(1)

    return most_common[0][0] if most_common else None


def put_replay_record(
    arena_unique_id: int,
    player_id: int,
    player_name: str,
    uploaded_by: str,
    metadata: Dict[str, Any],
    players_info: Dict[str, Any],
    s3_key: str,
    file_name: str,
    file_size: int,
    game_type: Optional[str] = None,
) -> None:
    """
    リプレイレコードをDynamoDBに保存

    Args:
        arena_unique_id: arenaUniqueID
        player_id: プレイヤーID
        player_name: プレイヤー名
        uploaded_by: アップロードしたユーザー（Discord User ID等）
        metadata: リプレイのメタデータ
        players_info: プレイヤー情報（own, allies, enemies）
        s3_key: S3に保存されたリプレイファイルのキー
        file_name: 元のファイル名
        file_size: ファイルサイズ（バイト）
        game_type: ゲームタイプ（clan/pvp/ranked）

    Raises:
        Exception: DynamoDB操作エラー
    """
    table = get_table()

    # タイムスタンプ
    uploaded_at = datetime.utcnow().isoformat()

    # プレイヤー情報の取得
    own_player = players_info.get("own", [{}])[0] if players_info.get("own") else {}
    allies = players_info.get("allies", [])
    enemies = players_info.get("enemies", [])

    # クランタグの計算（クラン戦のみ）
    determined_game_type = game_type or metadata.get("matchGroup", "unknown")
    ally_main_clan_tag = None
    enemy_main_clan_tag = None

    if determined_game_type == "clan":
        # 味方クラン: 自分 + allies
        ally_players = [own_player] + allies if own_player else allies
        ally_main_clan_tag = calculate_main_clan_tag(ally_players)

        # 敵クラン: enemies
        enemy_main_clan_tag = calculate_main_clan_tag(enemies)

    # レコード作成
    item = {
        "arenaUniqueID": str(arena_unique_id),
        "playerID": player_id,
        "playerName": player_name,
        "uploadedBy": uploaded_by,
        "uploadedAt": uploaded_at,
        # 試合情報
        "dateTime": metadata.get("dateTime", ""),
        "mapId": metadata.get("mapName", ""),
        "mapDisplayName": metadata.get("mapDisplayName", ""),
        "gameType": determined_game_type,
        "clientVersion": metadata.get("clientVersionFromXml", ""),
        # プレイヤー情報
        "ownPlayer": own_player,
        "allies": allies,
        "enemies": enemies,
        # クラン情報（クラン戦のみ）
        "allyMainClanTag": ally_main_clan_tag,
        "enemyMainClanTag": enemy_main_clan_tag,
        # ファイル情報
        "s3Key": s3_key,
        "fileName": file_name,
        "fileSize": file_size,
        # 勝敗情報（後で更新される）
        "winLoss": "unknown",
        "experienceEarned": None,
        # 動画情報
        "mp4GeneratedAt": None,
        "mp4S3Key": None,
    }

    table.put_item(Item=item)


def update_battle_result(
    arena_unique_id: int,
    player_id: int,
    win_loss: str,
    experience_earned: Optional[int],
) -> None:
    """
    バトル結果（勝敗・経験値）を更新

    Args:
        arena_unique_id: arenaUniqueID
        player_id: プレイヤーID
        win_loss: 勝敗（win/loss/draw/unknown）
        experience_earned: 獲得経験値

    Raises:
        Exception: DynamoDB操作エラー
    """
    table = get_table()

    table.update_item(
        Key={"arenaUniqueID": str(arena_unique_id), "playerID": player_id},
        UpdateExpression="SET winLoss = :wl, experienceEarned = :exp",
        ExpressionAttributeValues={":wl": win_loss, ":exp": experience_earned},
    )


def update_video_info(arena_unique_id: int, player_id: int, mp4_s3_key: str) -> None:
    """
    動画情報を更新

    Args:
        arena_unique_id: arenaUniqueID
        player_id: プレイヤーID
        mp4_s3_key: 生成したMP4のS3キー

    Raises:
        Exception: DynamoDB操作エラー
    """
    table = get_table()

    mp4_generated_at = datetime.utcnow().isoformat()

    table.update_item(
        Key={"arenaUniqueID": str(arena_unique_id), "playerID": player_id},
        UpdateExpression="SET mp4S3Key = :s3key, mp4GeneratedAt = :generated",
        ExpressionAttributeValues={
            ":s3key": mp4_s3_key,
            ":generated": mp4_generated_at,
        },
    )


def get_replay_record(arena_unique_id: int, player_id: int) -> Optional[Dict[str, Any]]:
    """
    リプレイレコードを取得

    Args:
        arena_unique_id: arenaUniqueID
        player_id: プレイヤーID

    Returns:
        レコード (dict) または None（見つからない場合）

    Raises:
        Exception: DynamoDB操作エラー
    """
    table = get_table()

    response = table.get_item(Key={"arenaUniqueID": str(arena_unique_id), "playerID": player_id})

    return response.get("Item")


def check_duplicate_by_arena_id(arena_unique_id: int) -> Optional[Dict[str, Any]]:
    """
    同じarenaUniqueIDのレコードが既に存在するか確認

    Args:
        arena_unique_id: arenaUniqueID

    Returns:
        既存レコード (dict) または None（重複なし）

    Raises:
        Exception: DynamoDB操作エラー
    """
    table = get_table()

    response = table.query(
        KeyConditionExpression="arenaUniqueID = :aid",
        ExpressionAttributeValues={":aid": str(arena_unique_id)},
        Limit=1,
    )

    items = response.get("Items", [])
    return items[0] if items else None


def search_replays(
    game_type: Optional[str] = None,
    map_id: Optional[str] = None,
    player_name: Optional[str] = None,
    win_loss: Optional[str] = None,
    date_from: Optional[str] = None,
    date_to: Optional[str] = None,
    limit: int = 50,
    last_evaluated_key: Optional[Dict] = None,
) -> Dict[str, Any]:
    """
    リプレイを検索

    Args:
        game_type: ゲームタイプフィルタ
        map_id: マップIDフィルタ
        player_name: プレイヤー名検索
        win_loss: 勝敗フィルタ
        date_from: 開始日時
        date_to: 終了日時
        limit: 取得件数上限
        last_evaluated_key: ページネーション用の最後のキー

    Returns:
        {
            'items': [...],
            'last_evaluated_key': {...} or None
        }

    Raises:
        Exception: DynamoDB操作エラー
    """
    table = get_table()

    # GSIを使用した検索
    if game_type:
        # GameTypeIndexを使用
        key_condition = "gameType = :gt"
        expression_values = {":gt": game_type}

        if date_from:
            key_condition += " AND dateTime >= :df"
            expression_values[":df"] = date_from
        if date_to:
            key_condition += " AND dateTime <= :dt"
            expression_values[":dt"] = date_to

        query_params = {
            "IndexName": "GameTypeIndex",
            "KeyConditionExpression": key_condition,
            "ExpressionAttributeValues": expression_values,
            "Limit": limit,
            "ScanIndexForward": False,  # 降順（新しい順）
        }

        if last_evaluated_key:
            query_params["ExclusiveStartKey"] = last_evaluated_key

        response = table.query(**query_params)

    elif player_name:
        # PlayerNameIndexを使用
        key_condition = "playerName = :pn"
        expression_values = {":pn": player_name}

        if date_from:
            key_condition += " AND dateTime >= :df"
            expression_values[":df"] = date_from
        if date_to:
            key_condition += " AND dateTime <= :dt"
            expression_values[":dt"] = date_to

        query_params = {
            "IndexName": "PlayerNameIndex",
            "KeyConditionExpression": key_condition,
            "ExpressionAttributeValues": expression_values,
            "Limit": limit,
            "ScanIndexForward": False,
        }

        if last_evaluated_key:
            query_params["ExclusiveStartKey"] = last_evaluated_key

        response = table.query(**query_params)

    elif map_id:
        # MapIdIndexを使用
        key_condition = "mapId = :mid"
        expression_values = {":mid": map_id}

        if date_from:
            key_condition += " AND dateTime >= :df"
            expression_values[":df"] = date_from
        if date_to:
            key_condition += " AND dateTime <= :dt"
            expression_values[":dt"] = date_to

        query_params = {
            "IndexName": "MapIdIndex",
            "KeyConditionExpression": key_condition,
            "ExpressionAttributeValues": expression_values,
            "Limit": limit,
            "ScanIndexForward": False,
        }

        if last_evaluated_key:
            query_params["ExclusiveStartKey"] = last_evaluated_key

        response = table.query(**query_params)

    else:
        # フィルタなしの場合はScan
        scan_params = {"Limit": limit}

        if last_evaluated_key:
            scan_params["ExclusiveStartKey"] = last_evaluated_key

        response = table.scan(**scan_params)

    # 勝敗フィルタ（クライアント側フィルタ）
    items = response.get("Items", [])
    if win_loss:
        items = [item for item in items if item.get("winLoss") == win_loss]

    return {"items": items, "last_evaluated_key": response.get("LastEvaluatedKey")}
