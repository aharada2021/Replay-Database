#!/usr/bin/env python3
"""
艦艇-試合インデックステーブルのバックフィルスクリプト

既存のリプレイデータから艦艇インデックスを再構築する
"""

import os
import sys
import boto3
from collections import Counter

# 環境変数
REPLAYS_TABLE = os.environ.get("REPLAYS_TABLE", "wows-replays-dev")
SHIP_MATCH_INDEX_TABLE = os.environ.get("SHIP_MATCH_INDEX_TABLE", "wows-ship-match-index-dev")
REGION = os.environ.get("AWS_REGION", "ap-northeast-1")


def get_dynamodb():
    return boto3.resource("dynamodb", region_name=REGION)


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


def create_ship_index_entries(item):
    """1つのリプレイから艦艇インデックスエントリを作成"""
    arena_unique_id = item.get("arenaUniqueID", "")
    date_time = item.get("dateTime", "")
    game_type = item.get("gameType", "")
    map_id = item.get("mapId", "")

    # プレイヤー情報
    own_player = item.get("ownPlayer", {})
    if isinstance(own_player, list):
        own_player = own_player[0] if own_player else {}
    allies = item.get("allies", [])
    enemies = item.get("enemies", [])

    # 艦艇ごとのカウントを集計
    ship_counts = {}  # shipName -> {"ally": count, "enemy": count}

    # 自分 + 味方の艦艇
    ally_players = []
    if own_player and own_player.get("shipName"):
        ally_players.append(own_player)
    ally_players.extend(allies or [])

    for player in ally_players:
        ship_name = player.get("shipName")
        if not ship_name:
            continue
        if ship_name not in ship_counts:
            ship_counts[ship_name] = {"ally": 0, "enemy": 0}
        ship_counts[ship_name]["ally"] += 1

    # 敵の艦艇
    for player in enemies or []:
        ship_name = player.get("shipName")
        if not ship_name:
            continue
        if ship_name not in ship_counts:
            ship_counts[ship_name] = {"ally": 0, "enemy": 0}
        ship_counts[ship_name]["enemy"] += 1

    # インデックスエントリを作成
    entries = []
    for ship_name, counts in ship_counts.items():
        entries.append({
            "shipName": ship_name,
            "arenaUniqueID": arena_unique_id,
            "dateTime": date_time,
            "gameType": game_type,
            "mapId": map_id,
            "allyCount": counts["ally"],
            "enemyCount": counts["enemy"],
            "totalCount": counts["ally"] + counts["enemy"],
        })

    return entries


def main():
    print("艦艇-試合インデックスのバックフィルを開始...")

    dynamodb = get_dynamodb()
    replays_table = dynamodb.Table(REPLAYS_TABLE)
    ship_index_table = dynamodb.Table(SHIP_MATCH_INDEX_TABLE)

    print(f"リプレイテーブル: {REPLAYS_TABLE}")
    print(f"艦艇インデックステーブル: {SHIP_MATCH_INDEX_TABLE}")

    # 全リプレイをスキャン
    print("\n1. リプレイデータをスキャン中...")
    replays = scan_all_replays(replays_table)
    print(f"   {len(replays)} 件のリプレイを取得")

    # 重複を除去（同じ試合の複数リプレイは1つにまとめる）
    unique_matches = {}
    for item in replays:
        arena_id = item.get("arenaUniqueID", "")
        if arena_id and arena_id not in unique_matches:
            unique_matches[arena_id] = item

    print(f"   {len(unique_matches)} 件のユニークな試合")

    # インデックスエントリを作成
    print("\n2. 艦艇インデックスエントリを作成中...")
    all_entries = []
    for arena_id, item in unique_matches.items():
        entries = create_ship_index_entries(item)
        all_entries.extend(entries)

    print(f"   {len(all_entries)} 件のインデックスエントリを作成")

    # バッチ書き込み
    print("\n3. インデックステーブルに書き込み中...")
    with ship_index_table.batch_writer() as batch:
        for i, entry in enumerate(all_entries):
            batch.put_item(Item=entry)
            if (i + 1) % 100 == 0:
                print(f"   {i + 1}/{len(all_entries)} 件を書き込み...")

    print(f"\n完了! {len(all_entries)} 件のインデックスエントリを作成しました。")

    # 統計を表示
    ship_counts = Counter(e["shipName"] for e in all_entries)
    print("\n上位10艦艇:")
    for ship, count in ship_counts.most_common(10):
        print(f"  {ship}: {count} 件")


if __name__ == "__main__":
    main()
