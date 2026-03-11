"""
検索APIハンドラー

Web UIからの検索リクエストを処理

テーブル構造:
- gameType別テーブル（clan, ranked, random, other）
- MATCHレコードは試合単位で事前グループ化済み
- ListingIndex を使用した高速ページネーション
- allPlayersStatsは別途/statsエンドポイントで取得
"""

import json
from datetime import datetime, timezone
from decimal import Decimal

from utils.dynamodb_tables import (
    BattleTableClient,
    IndexTableClient,
    normalize_game_type,
    parse_index_sk,
)


def normalize_ship_name(name: str) -> str:
    """
    艦艇名を検索用に正規化

    ship-indexテーブルのPKはUPPERCASEで統一されているため、
    ユーザー入力を単純にUPPERCASEに変換する。

    Args:
        name: 入力された艦艇名

    Returns:
        UPPERCASE艦艇名
    """
    if not name:
        return name
    return name.upper()


class DecimalEncoder(json.JSONEncoder):
    """DynamoDB Decimalオブジェクトをシリアライズするカスタムエンコーダー"""

    def default(self, obj):
        if isinstance(obj, Decimal):
            return int(obj) if obj % 1 == 0 else float(obj)
        return super(DecimalEncoder, self).default(obj)


def search_matches(
    game_type: str = None,
    map_id: str = None,
    ship_name: str = None,
    ship_team: str = None,
    player_name: str = None,
    clan_tag: str = None,
    ally_clan_tag: str = None,
    enemy_clan_tag: str = None,
    date_from: str = None,
    date_to: str = None,
    win_loss: str = None,
    limit: int = 30,
    cursor_unix_time: int = None,
) -> dict:
    """
    試合検索

    Returns:
        {
            "items": [...],
            "nextCursor": int or None,
            "hasMore": bool
        }
    """
    index_client = IndexTableClient()
    filtered_arena_ids = None

    # インデックス検索（艦艇、プレイヤー、クラン）
    if ship_name:
        ship_result = index_client.search_by_ship(
            ship_name=ship_name,
            game_type=normalize_game_type(game_type) if game_type else None,
            limit=500,
        )
        filtered_arena_ids = set()
        for item in ship_result.get("items", []):
            parsed = parse_index_sk(item.get("SK", ""))
            if parsed.get("arenaUniqueID"):
                # チームフィルタ
                if ship_team == "ally" and item.get("allyCount", 0) < 1:
                    continue
                if ship_team == "enemy" and item.get("enemyCount", 0) < 1:
                    continue
                filtered_arena_ids.add(parsed["arenaUniqueID"])
        print(f"Ship filter: {ship_name} found {len(filtered_arena_ids)} matches")

    if player_name:
        player_result = index_client.search_by_player(
            player_name=player_name,
            game_type=normalize_game_type(game_type) if game_type else None,
            limit=500,
        )
        player_arena_ids = set()
        for item in player_result.get("items", []):
            parsed = parse_index_sk(item.get("SK", ""))
            if parsed.get("arenaUniqueID"):
                player_arena_ids.add(parsed["arenaUniqueID"])
        if filtered_arena_ids is not None:
            filtered_arena_ids = filtered_arena_ids.intersection(player_arena_ids)
        else:
            filtered_arena_ids = player_arena_ids
        print(f"Player filter: {player_name} found {len(player_arena_ids)} matches")

    if clan_tag:
        clan_result = index_client.search_by_clan(
            clan_tag=clan_tag,
            game_type=normalize_game_type(game_type) if game_type else None,
            limit=500,
        )
        clan_arena_ids = set()
        for item in clan_result.get("items", []):
            parsed = parse_index_sk(item.get("SK", ""))
            if parsed.get("arenaUniqueID"):
                clan_arena_ids.add(parsed["arenaUniqueID"])
        if filtered_arena_ids is not None:
            filtered_arena_ids = filtered_arena_ids.intersection(clan_arena_ids)
        else:
            filtered_arena_ids = clan_arena_ids
        print(f"Clan filter: {clan_tag} found {len(clan_arena_ids)} matches")

    # 日付文字列をUnix時間に変換（YYYY-MM-DD → unixTime）
    unix_time_from = None
    unix_time_to = None
    if date_from:
        try:
            dt = datetime.strptime(date_from, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            unix_time_from = int(dt.timestamp())
        except ValueError:
            pass
    if date_to:
        try:
            # 日付の終わり（23:59:59）まで含める
            dt = datetime.strptime(date_to, "%Y-%m-%d").replace(
                hour=23, minute=59, second=59, tzinfo=timezone.utc
            )
            unix_time_to = int(dt.timestamp())
        except ValueError:
            pass

    # カーソルがある場合、unix_time_toをカーソルに制限
    effective_unix_time_to = unix_time_to
    if cursor_unix_time:
        cursor_limit = cursor_unix_time - 1  # カーソル位置を含めない
        if effective_unix_time_to is None or cursor_limit < effective_unix_time_to:
            effective_unix_time_to = cursor_limit

    # 複合フィルタがあるか判定
    has_post_filter = bool(
        filtered_arena_ids is not None or ally_clan_tag or enemy_clan_tag or win_loss
    )

    # gameType指定の場合は単一テーブルをクエリ
    # 指定なしの場合は全テーブルをクエリしてマージ
    game_types_to_query = []
    if game_type:
        game_types_to_query = [normalize_game_type(game_type)]
    else:
        game_types_to_query = ["clan", "ranked", "random", "other"]

    all_items = []
    for gt in game_types_to_query:
        battle_client = BattleTableClient(gt)

        # 複合フィルタがある場合はページネーションループで十分な結果を取得
        filtered_items = []
        arena_ids_to_fetch = []
        last_key = None
        max_queries = 10  # 無限ループ防止
        query_count = 0

        while query_count < max_queries:
            query_count += 1
            fetch_limit = limit * 3 if has_post_filter else limit * 2

            query_result = battle_client.list_matches(
                limit=fetch_limit,
                last_evaluated_key=last_key,
                map_id=map_id,
                unix_time_from=unix_time_from,
                unix_time_to=effective_unix_time_to,
            )

            for item in query_result.get("items", []):
                # インデックスフィルタ
                if filtered_arena_ids is not None:
                    if item.get("arenaUniqueID") not in filtered_arena_ids:
                        continue

                # クランタグフィルタ
                if ally_clan_tag and item.get("allyMainClanTag") != ally_clan_tag:
                    continue
                if enemy_clan_tag and item.get("enemyMainClanTag") != enemy_clan_tag:
                    continue

                # 勝敗フィルタ（"loss"/"lose"の表記揺れに対応）
                if win_loss:
                    item_wl = item.get("winLoss", "")
                    if win_loss == "loss":
                        if item_wl not in ("loss", "lose"):
                            continue
                    elif item_wl != win_loss:
                        continue

                arena_id = item.get("arenaUniqueID")
                if arena_id:
                    filtered_items.append(item)
                    arena_ids_to_fetch.append(arena_id)

            last_key = query_result.get("lastEvaluatedKey")

            # 十分な結果が集まったかDynamoDBの結果が尽きたら終了
            if len(filtered_items) >= limit + 1 or not last_key:
                break

        # BatchGetItemで完全なMATCHレコードを一括取得
        if arena_ids_to_fetch:
            full_matches = battle_client.batch_get_matches(arena_ids_to_fetch)

            for item in filtered_items:
                arena_id = item.get("arenaUniqueID")
                full_match = full_matches.get(arena_id)
                if full_match:
                    item = full_match

                # gameTypeを追加（テーブルから判断）
                item["gameType"] = gt
                all_items.append(item)

    # unixTime降順でソート
    all_items.sort(key=lambda x: x.get("unixTime", 0), reverse=True)

    # ページネーション
    has_more = len(all_items) > limit
    paginated = all_items[:limit]

    # 次のカーソル
    next_cursor = None
    if has_more and paginated:
        next_cursor = paginated[-1].get("unixTime")

    # ゲームプレイ動画情報をUPLOADレコードから補完
    # MATCHレコードのuploadersにはgameplayVideoS3Keyが含まれないため、
    # hasGameplayVideo=trueの試合のみUPLOADレコードから取得する
    gameplay_video_map = {}  # {(arenaUniqueID, playerID): {s3Key, size}}
    for item in paginated:
        if not item.get("hasGameplayVideo"):
            continue
        arena_id = item.get("arenaUniqueID")
        gt = item.get("gameType", "other")
        uploaders = item.get("uploaders", [])
        client = BattleTableClient(gt)
        for uploader in uploaders:
            pid = uploader.get("playerID")
            if pid is None:
                continue
            try:
                upload_record = client.table.get_item(
                    Key={"arenaUniqueID": arena_id, "recordType": f"UPLOAD#{pid}"},
                    ProjectionExpression="gameplayVideoS3Key,gameplayVideoSize",
                ).get("Item", {})
                if upload_record.get("gameplayVideoS3Key"):
                    gameplay_video_map[(arena_id, pid)] = {
                        "gameplayVideoS3Key": upload_record["gameplayVideoS3Key"],
                        "gameplayVideoSize": upload_record.get("gameplayVideoSize"),
                    }
            except Exception:
                pass

    # レスポンス形式に変換（旧形式との互換性）
    for item in paginated:
        # uploaders から代表リプレイ情報を設定
        uploaders = item.get("uploaders", [])
        if uploaders:
            rep = uploaders[0]
            rep_player_name = rep.get("playerName", "")
            item["representativePlayerID"] = rep.get("playerID")
            item["representativePlayerName"] = rep_player_name

            # ownPlayer を生成（allies から shipName と clanTag を取得）
            own_player = {"name": rep_player_name}
            allies = item.get("allies", [])
            for ally in allies:
                if ally.get("name") == rep_player_name:
                    own_player["shipName"] = ally.get("shipName", "")
                    own_player["clanTag"] = ally.get("clanTag", "")
                    break
            item["ownPlayer"] = own_player
        item["replayCount"] = len(uploaders)
        item["hasDualReplay"] = item.get("dualRendererAvailable", False)
        # allPlayersStatsは含まれていない（別APIで取得）
        item["allPlayersStats"] = []

        # replays配列を生成（フロントエンドのMatchDetailExpansion用）
        replays = []
        mp4_s3_key = item.get("mp4S3Key")
        dual_mp4_s3_key = item.get("dualMp4S3Key")
        arena_id = item.get("arenaUniqueID")
        for uploader in uploaders:
            pid = uploader.get("playerID")
            video_info = gameplay_video_map.get((arena_id, pid), {})
            replay = {
                "arenaUniqueID": arena_id,
                "playerID": pid,
                "playerName": uploader.get("playerName"),
                "mp4S3Key": mp4_s3_key,
                "dualMp4S3Key": dual_mp4_s3_key,
                "gameplayVideoS3Key": video_info.get("gameplayVideoS3Key"),
                "gameplayVideoSize": video_info.get("gameplayVideoSize"),
            }
            replays.append(replay)
        item["replays"] = replays

    return {
        "items": paginated,
        "nextCursor": next_cursor,
        "hasMore": has_more,
    }


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
        http_method = event.get("httpMethod") or event.get("requestContext", {}).get(
            "http", {}
        ).get("method")
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
        player_name = params.get("playerName")  # プレイヤー名検索
        clan_tag = params.get("clanTag")  # クラン検索
        date_from = params.get("dateFrom")  # YYYY-MM-DD
        date_to = params.get("dateTo")  # YYYY-MM-DD
        win_loss = params.get("winLoss")  # "win", "loss", "draw", or None
        limit = params.get("limit", 30)
        cursor_unix_time = params.get("cursorUnixTime")

        # 検索実行
        result = search_matches(
            game_type=game_type,
            map_id=map_id,
            ship_name=ship_name,
            ship_team=ship_team,
            player_name=player_name,
            clan_tag=clan_tag,
            ally_clan_tag=ally_clan_tag,
            enemy_clan_tag=enemy_clan_tag,
            date_from=date_from,
            date_to=date_to,
            win_loss=win_loss,
            limit=limit,
            cursor_unix_time=cursor_unix_time,
        )

        return {
            "statusCode": 200,
            "headers": cors_headers,
            "body": json.dumps(
                {
                    "items": result["items"],
                    "cursorUnixTime": result["nextCursor"],
                    "hasMore": result["hasMore"],
                    "count": len(result["items"]),
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
