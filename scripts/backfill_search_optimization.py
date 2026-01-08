#!/usr/bin/env python3
"""
検索最適化用フィールドのバックフィルスクリプト

既存のリプレイデータに以下のフィールドを追加:
- matchKey: 試合グループ化用キー（事前計算）
- dateTimeSortable: ソート可能な日時形式（YYYYMMDDHHMMSS）
"""

import os
import sys

# srcディレクトリをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import boto3
from datetime import datetime

# 環境変数
REPLAYS_TABLE = os.environ.get("REPLAYS_TABLE", "wows-replays-dev")
REGION = os.environ.get("AWS_REGION", "ap-northeast-1")
DRY_RUN = os.environ.get("DRY_RUN", "false").lower() == "true"


def get_dynamodb():
    return boto3.resource("dynamodb", region_name=REGION)


def format_sortable_datetime(date_str: str) -> str:
    """
    日時文字列をソート可能な形式に変換

    DD.MM.YYYY HH:MM:SS → YYYYMMDDHHMMSS
    """
    if not date_str:
        return "00000000000000"

    try:
        dt = datetime.strptime(date_str, "%d.%m.%Y %H:%M:%S")
        return dt.strftime("%Y%m%d%H%M%S")
    except ValueError:
        return "00000000000000"


def round_datetime_to_5min(date_time_str: str) -> str:
    """日時を5分単位に丸める"""
    try:
        dt = datetime.strptime(date_time_str, "%d.%m.%Y %H:%M:%S")
        rounded_minute = (dt.minute // 5) * 5
        rounded_dt = dt.replace(minute=rounded_minute, second=0)
        return rounded_dt.strftime("%d.%m.%Y %H:%M:00")
    except Exception:
        return date_time_str


def generate_match_key(item: dict) -> str:
    """
    同一試合を識別するためのキーを生成
    """
    # 全プレイヤー名を収集
    players = set()

    # ownPlayerを追加
    own_player = item.get("ownPlayer", {})
    if isinstance(own_player, list):
        own_player = own_player[0] if own_player else {}
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

    # プレイヤーリストをソート
    player_list = sorted(players)

    # 日時を5分単位に丸める
    date_time = item.get("dateTime", "")
    rounded_date_time = round_datetime_to_5min(date_time)

    # マップとゲームタイプ
    map_id = item.get("mapId", "")
    game_type = item.get("gameType", "")

    # マッチキーを生成
    match_key = f"{rounded_date_time}|{map_id}|{game_type}|{'|'.join(player_list)}"

    return match_key


def scan_all_replays(table):
    """全リプレイをスキャン"""
    items = []
    response = table.scan()
    items.extend(response.get("Items", []))

    while "LastEvaluatedKey" in response:
        response = table.scan(ExclusiveStartKey=response["LastEvaluatedKey"])
        items.extend(response.get("Items", []))
        print(f"  Scanned {len(items)} items...")

    return items


def main():
    print("検索最適化フィールドのバックフィルを開始...")
    print(f"モード: {'DRY RUN（書き込みなし）' if DRY_RUN else '本番実行'}")

    dynamodb = get_dynamodb()
    replays_table = dynamodb.Table(REPLAYS_TABLE)

    print(f"リプレイテーブル: {REPLAYS_TABLE}")

    # 全リプレイをスキャン
    print("\n1. リプレイデータをスキャン中...")
    replays = scan_all_replays(replays_table)
    print(f"   {len(replays)} 件のリプレイを取得")

    # フィールドがないレコードを特定
    print("\n2. 更新が必要なレコードを特定中...")
    needs_update = []
    already_updated = 0

    for item in replays:
        has_match_key = item.get("matchKey") is not None
        has_sortable = item.get("dateTimeSortable") is not None

        if not has_match_key or not has_sortable:
            needs_update.append(item)
        else:
            already_updated += 1

    print(f"   更新が必要: {len(needs_update)} 件")
    print(f"   既に更新済み: {already_updated} 件")

    if not needs_update:
        print("\n全レコードが既に更新済みです。")
        return

    # 更新を実行
    print("\n3. レコードを更新中...")
    updated_count = 0
    error_count = 0

    for i, item in enumerate(needs_update):
        arena_unique_id = item.get("arenaUniqueID")
        player_id = item.get("playerID")

        if not arena_unique_id or player_id is None:
            print(f"   警告: キーが不完全なレコードをスキップ: {item}")
            error_count += 1
            continue

        # 新しいフィールドを計算
        match_key = generate_match_key(item)
        date_time_sortable = format_sortable_datetime(item.get("dateTime", ""))

        if DRY_RUN:
            if (i + 1) <= 3:  # 最初の3件のみ表示
                print(f"   [DRY RUN] {arena_unique_id}/{player_id}")
                print(f"     matchKey: {match_key[:80]}...")
                print(f"     dateTimeSortable: {date_time_sortable}")
        else:
            try:
                replays_table.update_item(
                    Key={
                        "arenaUniqueID": arena_unique_id,
                        "playerID": player_id,
                    },
                    UpdateExpression="SET matchKey = :mk, dateTimeSortable = :dts",
                    ExpressionAttributeValues={
                        ":mk": match_key,
                        ":dts": date_time_sortable,
                    },
                )
                updated_count += 1
            except Exception as e:
                print(f"   エラー: {arena_unique_id}/{player_id}: {e}")
                error_count += 1

        if (i + 1) % 100 == 0:
            print(f"   {i + 1}/{len(needs_update)} 件を処理...")

    # 結果表示
    print("\n完了!")
    if DRY_RUN:
        print(f"DRY RUN: {len(needs_update)} 件のレコードが更新対象です。")
        print("本番実行するには DRY_RUN=false を設定してください。")
    else:
        print(f"更新成功: {updated_count} 件")
        print(f"エラー: {error_count} 件")


if __name__ == "__main__":
    main()
