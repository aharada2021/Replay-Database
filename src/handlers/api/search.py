"""
検索APIハンドラー

Web UIからの検索リクエストを処理
"""

import json
from decimal import Decimal
from datetime import datetime, timedelta
from functools import lru_cache

from utils import dynamodb
from utils.match_key import generate_match_key


@lru_cache(maxsize=2048)
def parse_datetime_for_sort(date_str: str) -> datetime:
    """
    日時文字列をソート用にパース（メモ化による高速化）

    Args:
        date_str: "DD.MM.YYYY HH:MM:SS" 形式の日時文字列

    Returns:
        datetime オブジェクト（パース失敗時は最小値）
    """
    if not date_str:
        return datetime.min

    try:
        # "DD.MM.YYYY HH:MM:SS" 形式
        return datetime.strptime(date_str, "%d.%m.%Y %H:%M:%S")
    except ValueError:
        try:
            # ISO形式のフォールバック
            return datetime.fromisoformat(date_str.replace("Z", "+00:00"))
        except ValueError:
            return datetime.min


def normalize_ship_name(name: str) -> str:
    """
    艦艇名を検索用に正規化

    DynamoDBは完全一致検索のため、入力を正規化して
    保存されている形式に合わせる

    Args:
        name: 入力された艦艇名

    Returns:
        正規化された艦艇名
    """
    if not name:
        return name

    # 大文字のまま保持するプレフィックス（コラボ艦艇など）
    uppercase_prefixes = ["AL ", "BA ", "GQ ", "STAR "]

    # まずタイトルケースに変換
    normalized = name.title()

    # 大文字プレフィックスを復元
    for prefix in uppercase_prefixes:
        lower_prefix = prefix.title()  # "Al ", "Ba ", etc.
        if normalized.startswith(lower_prefix):
            normalized = prefix + normalized[len(prefix) :]
            break

    return normalized


def parse_frontend_date(date_str: str) -> datetime:
    """
    フロントエンドの日付文字列をパース

    Args:
        date_str: "YYYY-MM-DD" 形式の日付文字列

    Returns:
        datetime オブジェクト（パース失敗時はNone）
    """
    if not date_str:
        return None

    try:
        # "YYYY-MM-DD" 形式
        return datetime.strptime(date_str, "%Y-%m-%d")
    except ValueError:
        return None


def calculate_fetch_multiplier(
    ally_clan_tag: str = None,
    enemy_clan_tag: str = None,
    ship_filtered_count: int = None,
    cursor_date_time: str = None,
    date_from: str = None,
    date_to: str = None,
) -> int:
    """
    検索条件に基づいてfetch_multiplierを動的に計算

    より厳しい（絞り込み率が高い）フィルタがある場合、
    より多くのデータを取得して、limit件のマッチを確保する

    Args:
        ally_clan_tag: 味方クランタグフィルタ
        enemy_clan_tag: 敵クランタグフィルタ
        ship_filtered_count: 艦艇フィルタで見つかったマッチ数（Noneの場合はフィルタなし）
        cursor_date_time: カーソル日時
        date_from: 開始日付
        date_to: 終了日付

    Returns:
        fetch_multiplier（5-25の範囲）
    """
    multiplier = 5  # 基本値

    # クランフィルタ（絞り込み率が高い）
    if ally_clan_tag or enemy_clan_tag:
        multiplier += 5

    # 艦艇フィルタ（結果数に応じて調整）
    if ship_filtered_count is not None:
        if ship_filtered_count < 50:
            multiplier += 3
        elif ship_filtered_count < 100:
            multiplier += 5
        else:
            multiplier += 8

    # 日付フィルタ
    if date_from or date_to:
        multiplier += 3

    # カーソルページネーション
    if cursor_date_time:
        multiplier += 5

    # 上限設定
    return min(multiplier, 25)


def filter_matches_single_pass(
    matches: list,
    cursor_dt: datetime = None,
    date_from_dt: datetime = None,
    date_to_dt: datetime = None,
    ally_clan_tag: str = None,
    enemy_clan_tag: str = None,
) -> list:
    """
    単一パスで全フィルタを適用（複数回のリスト走査を回避）

    Args:
        matches: マッチリスト
        cursor_dt: カーソル日時（これより前のデータのみ）
        date_from_dt: 開始日時
        date_to_dt: 終了日時（この日の翌日0時未満）
        ally_clan_tag: 味方クランタグ
        enemy_clan_tag: 敵クランタグ

    Returns:
        フィルタリングされたマッチリスト
    """
    result = []
    for m in matches:
        match_dt = parse_datetime_for_sort(m.get("dateTime", ""))

        # カーソルフィルタ: カーソルより前（古い）のデータのみ
        if cursor_dt and match_dt >= cursor_dt:
            continue

        # 日付範囲フィルタ
        if date_from_dt and match_dt < date_from_dt:
            continue
        if date_to_dt and match_dt >= date_to_dt:
            continue

        # クランタグフィルタ
        if ally_clan_tag and m.get("allyMainClanTag") != ally_clan_tag:
            continue
        if enemy_clan_tag and m.get("enemyMainClanTag") != enemy_clan_tag:
            continue

        result.append(m)

    return result


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
        ship_name_raw = params.get("shipName")
        # 艦艇名を正規化（DynamoDBは完全一致検索のため）
        ship_name = normalize_ship_name(ship_name_raw) if ship_name_raw else None
        ship_team = params.get("shipTeam")  # "ally", "enemy", or None
        ship_min_count = params.get("shipMinCount", 1)
        player_name = params.get("playerName")  # プレイヤー名検索
        win_loss = params.get("winLoss")
        date_from = params.get("dateFrom")
        date_to = params.get("dateTo")
        limit = params.get("limit", 50)
        # カーソルベースのページネーション
        # cursorDateTime: 前回の最後のマッチのdateTime（これより前のデータを取得）
        cursor_date_time = params.get("cursorDateTime")

        # 艦艇検索の場合、インデックステーブルを使用
        ship_filtered_arena_ids = None
        if ship_name:
            ship_result = dynamodb.search_matches_by_ship_with_count(
                ship_name=ship_name,
                team=ship_team,
                min_count=ship_min_count,
                limit=500,  # 十分な数を取得
            )
            ship_filtered_arena_ids = set(item.get("arenaUniqueID") for item in ship_result.get("items", []))
            print(f"Ship filter: {ship_name} found {len(ship_filtered_arena_ids)} matches")

        # プレイヤー名検索の場合、PlayerNameIndexを使用
        player_filtered_arena_ids = None
        if player_name:
            player_result = dynamodb.search_replays_by_player_name(
                player_name=player_name,
                limit=500,  # 十分な数を取得
            )
            player_filtered_arena_ids = set(item.get("arenaUniqueID") for item in player_result.get("items", []))
            print(f"Player filter: {player_name} found {len(player_filtered_arena_ids)} matches")

        # 検索実行（グループ化・フィルタ後にlimit件になるよう多めに取得）
        # Note: DynamoDBのソートキーはDD.MM.YYYY形式のため、文字列ソートでは正しい時系列順にならない
        # そのため多めにデータを取得し、Python側で正しくソートし直す
        # また、日付フィルタはDynamoDBに渡さない:
        # - フロントエンドはYYYY-MM-DD形式で送信
        # - DynamoDBはDD.MM.YYYY HH:MM:SS形式で保存
        # - 形式が異なるため、DynamoDBの文字列比較が正しく動作しない
        # - カーソル・日付によるフィルタリングはPython側で行う
        # プレイヤー名フィルタも考慮
        combined_filtered_count = None
        if ship_filtered_arena_ids is not None:
            combined_filtered_count = len(ship_filtered_arena_ids)
        if player_filtered_arena_ids is not None:
            if combined_filtered_count is not None:
                combined_filtered_count = min(combined_filtered_count, len(player_filtered_arena_ids))
            else:
                combined_filtered_count = len(player_filtered_arena_ids)

        fetch_multiplier = calculate_fetch_multiplier(
            ally_clan_tag=ally_clan_tag,
            enemy_clan_tag=enemy_clan_tag,
            ship_filtered_count=combined_filtered_count,
            cursor_date_time=cursor_date_time,
            date_from=date_from,
            date_to=date_to,
        )

        result = dynamodb.search_replays(
            game_type=game_type,
            map_id=map_id,
            win_loss=win_loss,
            date_from=None,  # 日付フィルタはPython側で行う（形式が異なるため）
            date_to=None,  # 日付フィルタはPython側で行う（形式が異なるため）
            limit=limit * fetch_multiplier,
        )

        # 既存レコードのownPlayerが配列の場合、単一オブジェクトに変換
        items = result["items"]
        for item in items:
            if "ownPlayer" in item and isinstance(item["ownPlayer"], list):
                item["ownPlayer"] = item["ownPlayer"][0] if item["ownPlayer"] else {}

        # 艦艇フィルタを適用（インデックステーブルで取得したarenaUniqueIDでフィルタ）
        if ship_filtered_arena_ids is not None:
            items = [item for item in items if item.get("arenaUniqueID") in ship_filtered_arena_ids]
            print(f"After ship filter: {len(items)} items")

        # プレイヤー名フィルタを適用（PlayerNameIndexで取得したarenaUniqueIDでフィルタ）
        if player_filtered_arena_ids is not None:
            items = [item for item in items if item.get("arenaUniqueID") in player_filtered_arena_ids]
            print(f"After player filter: {len(items)} items")

        # 試合単位でグループ化（プレイヤーセットベース）
        matches = {}
        match_key_to_arena_ids = {}  # match_key -> 最初のarenaUniqueIDのマッピング

        for item in items:
            # マッチキーを取得（事前計算値があれば使用、なければ生成）
            # 最適化: 新しいレコードはmatchKeyが事前計算されている
            match_key = item.get("matchKey") or generate_match_key(item)

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
                    "dateTimeSortable": item.get("dateTimeSortable"),  # 最適化: ソート用
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
                    # コメント数
                    "commentCount": item.get("commentCount", 0),
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
                    # Dual Render
                    "dualMp4S3Key": item.get("dualMp4S3Key"),
                    "dualMp4GeneratedAt": item.get("dualMp4GeneratedAt"),
                    "hasDualReplay": item.get("hasDualReplay", False),
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

        # 各試合の代表リプレイを選択（dualMp4生成済み > mp4生成済み > 最初にアップロードされた順）
        for match_key, match in matches.items():
            replays = match["replays"]

            # Dual mp4が生成済みのリプレイを最優先
            replays_with_dual = [r for r in replays if r.get("dualMp4S3Key")]
            if replays_with_dual:
                representative = replays_with_dual[0]
            else:
                # 次に通常mp4が生成済みのリプレイを優先
                replays_with_video = [r for r in replays if r.get("mp4S3Key")]
                if replays_with_video:
                    representative = replays_with_video[0]
                else:
                    representative = replays[0]

            # hasDualReplayフラグ（いずれかのリプレイがDual可能な場合）
            has_dual_replay = any(r.get("hasDualReplay") for r in replays)

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
            # Dual Render
            match["dualMp4S3Key"] = representative.get("dualMp4S3Key")
            match["dualMp4GeneratedAt"] = representative.get("dualMp4GeneratedAt")
            match["hasDualReplay"] = has_dual_replay
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
        # 最適化: dateTimeSortable（YYYYMMDDHHMMSS形式）があれば文字列ソートで正しい順序になる
        # フォールバック: DD.MM.YYYY形式はparse_datetime_for_sortでパースしてソート
        def get_sort_key(match):
            sortable = match.get("dateTimeSortable")
            if sortable and sortable != "00000000000000":
                return sortable
            return parse_datetime_for_sort(match.get("dateTime", "")).strftime("%Y%m%d%H%M%S")

        match_list = sorted(
            matches.values(),
            key=get_sort_key,
            reverse=True,
        )

        # フィルタリング用のパラメータを準備
        cursor_dt = parse_datetime_for_sort(cursor_date_time) if cursor_date_time else None
        date_from_dt = parse_frontend_date(date_from) if date_from else None
        date_to_dt = (
            parse_frontend_date(date_to) + timedelta(days=1) if date_to and parse_frontend_date(date_to) else None
        )

        # 単一パスで全フィルタを適用（最適化: 複数回のリスト走査を回避）
        match_list = filter_matches_single_pass(
            matches=match_list,
            cursor_dt=cursor_dt,
            date_from_dt=date_from_dt,
            date_to_dt=date_to_dt,
            ally_clan_tag=ally_clan_tag,
            enemy_clan_tag=enemy_clan_tag,
        )

        # 艦艇フィルタは既にship_filtered_arena_idsで適用済み

        # ページネーション: limit件を返し、次のページのカーソルを設定
        has_more = len(match_list) > limit
        paginated_list = match_list[:limit]

        # 次のページ用カーソル（最後のマッチのdateTime）
        next_cursor = None
        if has_more and paginated_list:
            last_match = paginated_list[-1]
            next_cursor = last_match.get("dateTime")

        # レスポンス
        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps(
                {
                    "items": paginated_list,
                    "cursorDateTime": next_cursor,
                    "hasMore": has_more,
                    "count": len(paginated_list),
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
