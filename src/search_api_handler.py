"""
検索APIハンドラー

Web UIからの検索リクエストを処理
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
    検索APIのハンドラー

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
            "Access-Control-Allow-Methods": "POST, OPTIONS",
        }

        # OPTIONS request (preflight)
        http_method = event.get("httpMethod") or event.get("requestContext", {}).get("http", {}).get("method")
        if http_method == "OPTIONS":
            return {"statusCode": 200, "headers": cors_headers, "body": ""}

        # リクエストボディ解析
        body = event.get("body", "{}")
        if isinstance(body, str):
            params = json.loads(body)
        else:
            params = body

        # 検索パラメータ
        game_type = params.get("gameType")
        map_id = params.get("mapId")
        player_name = params.get("playerName")
        enemy_clan_tag = params.get("enemyClanTag")
        win_loss = params.get("winLoss")
        date_from = params.get("dateFrom")
        date_to = params.get("dateTo")
        limit = params.get("limit", 50)
        last_evaluated_key = params.get("lastEvaluatedKey")

        # 検索実行
        result = dynamodb.search_replays(
            game_type=game_type,
            map_id=map_id,
            player_name=player_name,
            win_loss=win_loss,
            date_from=date_from,
            date_to=date_to,
            limit=limit,
            last_evaluated_key=last_evaluated_key,
        )

        # 既存レコードのownPlayerが配列の場合、単一オブジェクトに変換
        items = result["items"]
        for item in items:
            if "ownPlayer" in item and isinstance(item["ownPlayer"], list):
                item["ownPlayer"] = item["ownPlayer"][0] if item["ownPlayer"] else {}

        # 試合単位でグループ化（プレイヤーセットベース）
        matches = {}
        match_key_to_arena_ids = {}  # match_key -> 最初のarenaUniqueIDのマッピング

        for item in items:
            # マッチキーを生成
            match_key = generate_match_key(item)

            if match_key not in matches:
                # 新しい試合として登録
                # arenaUniqueIDは最初に見つかったものを使用
                arena_id = item.get("arenaUniqueID", "")
                match_key_to_arena_ids[match_key] = arena_id

                matches[match_key] = {
                    "arenaUniqueID": arena_id,  # 代表arenaUniqueID
                    "matchKey": match_key,  # デバッグ用
                    "replays": [],
                    # 代表データ（最初のリプレイから取得）
                    "dateTime": item.get("dateTime"),
                    "mapId": item.get("mapId"),
                    "mapDisplayName": item.get("mapDisplayName"),
                    "gameType": item.get("gameType"),
                    "clientVersion": item.get("clientVersion"),
                    "winLoss": item.get("winLoss"),
                    "experienceEarned": item.get("experienceEarned"),
                    "ownPlayer": item.get("ownPlayer"),
                    "allies": item.get("allies"),
                    "enemies": item.get("enemies"),
                    # クラン情報
                    "allyMainClanTag": item.get("allyMainClanTag"),
                    "enemyMainClanTag": item.get("enemyMainClanTag"),
                }

            # リプレイ提供者情報を追加
            matches[match_key]["replays"].append(
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
                }
            )

        # 各試合の代表リプレイを選択（mp4生成済み > 最初にアップロードされた順）
        for match_key, match in matches.items():
            replays = match["replays"]

            # mp4が生成済みのリプレイを優先
            replays_with_video = [r for r in replays if r.get("mp4S3Key")]
            if replays_with_video:
                representative = replays_with_video[0]
            else:
                representative = replays[0]

            # 代表リプレイの情報をマッチに追加
            match["representativeArenaUniqueID"] = representative.get("arenaUniqueID")
            match["representativePlayerID"] = representative.get("playerID")
            match["representativePlayerName"] = representative.get("playerName")
            match["uploadedBy"] = representative.get("uploadedBy")
            match["uploadedAt"] = representative.get("uploadedAt")
            match["s3Key"] = representative.get("s3Key")
            match["fileName"] = representative.get("fileName")
            match["fileSize"] = representative.get("fileSize")
            match["mp4S3Key"] = representative.get("mp4S3Key")
            match["mp4GeneratedAt"] = representative.get("mp4GeneratedAt")
            match["replayCount"] = len(replays)

        # マッチのリストに変換（日時順にソート）
        match_list = sorted(matches.values(), key=lambda x: x.get("dateTime", ""), reverse=True)

        # 敵クランタグでフィルタリング（クライアント側フィルタ）
        if enemy_clan_tag:
            match_list = [m for m in match_list if m.get("enemyMainClanTag") == enemy_clan_tag]

        # レスポンス
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps(
                {
                    "items": match_list,
                    "lastEvaluatedKey": result["last_evaluated_key"],
                    "count": len(match_list),
                },
                cls=DecimalEncoder,
            ),
        }

    except Exception as e:
        print(f"Error in search_api_handler: {e}")
        import traceback

        traceback.print_exc()

        return {
            "statusCode": 500,
            "headers": {"Access-Control-Allow-Origin": "*"},
            "body": json.dumps({"error": str(e)}),
        }
