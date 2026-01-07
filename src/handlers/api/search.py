"""
検索APIハンドラー

Web UIからの検索リクエストを処理
"""

import json
from decimal import Decimal

from utils import dynamodb
from utils.match_key import generate_match_key


class DecimalEncoder(json.JSONEncoder):
    """DynamoDB Decimalオブジェクトをシリアライズするカスタムエンコーダー"""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)


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
        ally_clan_tag = params.get("allyClanTag")
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
                    # 全プレイヤー統計
                    "allPlayersStats": item.get("allPlayersStats", []),
                }

            # リプレイ提供者情報を追加（BattleStatsを含む）
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
                    # BattleStats - 基本統計
                    "damage": item.get("damage"),
                    "receivedDamage": item.get("receivedDamage"),
                    "spottingDamage": item.get("spottingDamage"),
                    "potentialDamage": item.get("potentialDamage"),
                    "kills": item.get("kills"),
                    "fires": item.get("fires"),
                    "floods": item.get("floods"),
                    "baseXP": item.get("baseXP"),
                    # BattleStats - 命中数内訳
                    "hitsAP": item.get("hitsAP"),
                    "hitsHE": item.get("hitsHE"),
                    "hitsSecondaries": item.get("hitsSecondaries"),
                    # BattleStats - ダメージ内訳
                    "damageAP": item.get("damageAP"),
                    "damageHE": item.get("damageHE"),
                    "damageHESecondaries": item.get("damageHESecondaries"),
                    "damageTorps": item.get("damageTorps"),
                    "damageDeepWaterTorps": item.get("damageDeepWaterTorps"),
                    "damageOther": item.get("damageOther"),
                    "damageFire": item.get("damageFire"),
                    "damageFlooding": item.get("damageFlooding"),
                    # Citadel
                    "citadels": item.get("citadels"),
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

            # 代表リプレイのBattleStatsをマッチレベルにも追加
            match["damage"] = representative.get("damage")
            match["receivedDamage"] = representative.get("receivedDamage")
            match["spottingDamage"] = representative.get("spottingDamage")
            match["potentialDamage"] = representative.get("potentialDamage")
            match["kills"] = representative.get("kills")
            match["fires"] = representative.get("fires")
            match["floods"] = representative.get("floods")
            match["baseXP"] = representative.get("baseXP")
            match["hitsAP"] = representative.get("hitsAP")
            match["hitsHE"] = representative.get("hitsHE")
            match["hitsSecondaries"] = representative.get("hitsSecondaries")
            match["damageAP"] = representative.get("damageAP")
            match["damageHE"] = representative.get("damageHE")
            match["damageHESecondaries"] = representative.get("damageHESecondaries")
            match["damageTorps"] = representative.get("damageTorps")
            match["damageDeepWaterTorps"] = representative.get("damageDeepWaterTorps")
            match["damageOther"] = representative.get("damageOther")
            match["damageFire"] = representative.get("damageFire")
            match["damageFlooding"] = representative.get("damageFlooding")
            match["citadels"] = representative.get("citadels")

        # マッチのリストに変換（日時順にソート）
        match_list = sorted(matches.values(), key=lambda x: x.get("dateTime", ""), reverse=True)

        # クランタグでフィルタリング（クライアント側フィルタ）
        if ally_clan_tag:
            match_list = [m for m in match_list if m.get("allyMainClanTag") == ally_clan_tag]
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
