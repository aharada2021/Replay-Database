"""
試合詳細APIハンドラー

特定の試合IDに対する全リプレイを取得
"""

import json
from decimal import Decimal
from datetime import datetime

from utils import dynamodb


class DecimalEncoder(json.JSONEncoder):
    """DynamoDB Decimalオブジェクトをシリアライズするカスタムエンコーダー"""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)


def round_datetime_to_5min(date_time_str):
    """
    日時を5分単位に丸める

    Args:
        date_time_str: "04.01.2026 21:56:55" 形式の日時文字列

    Returns:
        5分単位に丸めた日時文字列 (例: "04.01.2026 21:55:00")
    """
    try:
        # フォーマット例: "04.01.2026 21:56:55"
        dt = datetime.strptime(date_time_str, "%d.%m.%Y %H:%M:%S")

        # 分を5分単位に切り捨て
        rounded_minute = (dt.minute // 5) * 5

        # 丸めた日時を返す
        rounded_dt = dt.replace(minute=rounded_minute, second=0)
        return rounded_dt.strftime("%d.%m.%Y %H:%M:00")
    except Exception as e:
        print(f"Error rounding datetime: {e}, returning original: {date_time_str}")
        return date_time_str


def generate_match_key(item):
    """
    同一試合を識別するためのキーを生成

    Args:
        item: DynamoDBアイテム

    Returns:
        マッチキー文字列
    """
    # 全プレイヤー名を収集
    players = set()

    # ownPlayerを追加
    own_player = item.get("ownPlayer", {})
    if isinstance(own_player, dict) and own_player.get("name"):
        players.add(own_player["name"])

    # alliesを追加
    for ally in item.get("allies", []):
        if ally.get("name"):
            players.add(ally["name"])

    # enemiesを追加
    for enemy in item.get("enemies", []):
        if enemy.get("name"):
            players.add(enemy["name"])

    # プレイヤーリストをソート（安定したキーのため）
    player_list = sorted(players)

    # 日時を5分単位に丸める
    date_time = item.get("dateTime", "")
    rounded_date_time = round_datetime_to_5min(date_time)

    # マップとゲームタイプ
    map_id = item.get("mapId", "")
    game_type = item.get("gameType", "")

    # マッチキーを生成
    # フォーマット: "日時(5分丸め)|マップ|ゲームタイプ|プレイヤー1|プレイヤー2|..."
    match_key = f"{rounded_date_time}|{map_id}|{game_type}|{'|'.join(player_list)}"

    return match_key


def handle(event, context):
    """
    試合詳細APIのハンドラー

    Args:
        event: APIイベント
        context: Lambdaコンテキスト

    Returns:
        APIレスポンス
    """
    try:
        # CORS headers
        cors_headers = {
            "Access-Control-Allow-Origin": "*",
            "Access-Control-Allow-Headers": "Content-Type",
            "Access-Control-Allow-Methods": "GET, OPTIONS",
        }

        # OPTIONS request (preflight)
        http_method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
        if http_method == "OPTIONS":
            return {"statusCode": 200, "headers": cors_headers, "body": ""}

        # パスパラメータからarenaUniqueIDを取得
        path_parameters = event.get("pathParameters", {})
        arena_unique_id = path_parameters.get("arenaUniqueID")

        if not arena_unique_id:
            return {
                "statusCode": 400,
                "headers": cors_headers,
                "body": json.dumps({"error": "arenaUniqueID is required"}),
            }

        # まず指定されたarenaUniqueIDのレコードを取得してmatch_keyを生成
        table = dynamodb.get_table()
        response = table.query(
            KeyConditionExpression="arenaUniqueID = :aid",
            ExpressionAttributeValues={":aid": str(arena_unique_id)},
        )

        seed_items = response.get("Items", [])

        if not seed_items:
            return {
                "statusCode": 404,
                "headers": cors_headers,
                "body": json.dumps({"error": "Match not found"}),
            }

        # ownPlayerが配列の場合、単一オブジェクトに変換
        for item in seed_items:
            if "ownPlayer" in item and isinstance(item["ownPlayer"], list):
                item["ownPlayer"] = item["ownPlayer"][0] if item["ownPlayer"] else {}

        # 最初のレコードからmatch_keyを生成
        seed_item = seed_items[0]
        target_match_key = generate_match_key(seed_item)

        print(f"Target match_key: {target_match_key}")

        # 全リプレイをスキャンして同じmatch_keyを持つものを探す
        # 小規模データベースの場合はScanで十分
        # 大規模な場合はGameTypeIndexを使って絞り込む
        game_type = seed_item.get("gameType")

        # GameTypeIndexで同じゲームタイプのリプレイを取得
        all_response = table.query(
            IndexName="GameTypeIndex",
            KeyConditionExpression="gameType = :gt",
            ExpressionAttributeValues={":gt": game_type},
        )

        all_items = all_response.get("Items", [])

        # ownPlayerが配列の場合、単一オブジェクトに変換
        for item in all_items:
            if "ownPlayer" in item and isinstance(item["ownPlayer"], list):
                item["ownPlayer"] = item["ownPlayer"][0] if item["ownPlayer"] else {}

        # match_keyが一致するアイテムをフィルタリング
        items = []
        for item in all_items:
            if generate_match_key(item) == target_match_key:
                items.append(item)

        print(f"Found {len(items)} replays for the same match")

        # 試合情報を構築（最初のリプレイから共通情報を取得）
        first_replay = items[0]
        match_info = {
            "arenaUniqueID": arena_unique_id,
            "dateTime": first_replay.get("dateTime"),
            "mapId": first_replay.get("mapId"),
            "mapDisplayName": first_replay.get("mapDisplayName"),
            "gameType": first_replay.get("gameType"),
            "clientVersion": first_replay.get("clientVersion"),
            "winLoss": first_replay.get("winLoss"),
            "experienceEarned": first_replay.get("experienceEarned"),
            "ownPlayer": first_replay.get("ownPlayer"),
            "allies": first_replay.get("allies", []),
            "enemies": first_replay.get("enemies", []),
            "allyMainClanTag": first_replay.get("allyMainClanTag"),
            "enemyMainClanTag": first_replay.get("enemyMainClanTag"),
            "replays": [],
        }

        # 全リプレイ情報を追加
        for item in items:
            match_info["replays"].append(
                {
                    "arenaUniqueID": item.get("arenaUniqueID"),  # 元のarenaUniqueIDも保存
                    "playerID": item.get("playerID"),
                    "playerName": item.get("playerName"),
                    "uploadedBy": item.get("uploadedBy"),
                    "uploadedAt": item.get("uploadedAt"),
                    "s3Key": item.get("s3Key"),
                    "fileName": item.get("fileName"),
                    "fileSize": item.get("fileSize"),
                    "mp4S3Key": item.get("mp4S3Key"),
                    "mp4GeneratedAt": item.get("mp4GeneratedAt"),
                    "ownPlayer": item.get("ownPlayer"),
                }
            )

        # レスポンス
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps(match_info, cls=DecimalEncoder),
        }

    except Exception as e:
        print(f"Error in match_detail_api_handler: {e}")
        import traceback

        traceback.print_exc()

        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)}),
        }
