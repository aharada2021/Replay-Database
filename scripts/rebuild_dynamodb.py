#!/usr/bin/env python3
"""
DynamoDB再構築スクリプト

S3にアップロードされているリプレイファイルからDynamoDBのデータを再構築します。
艦船名やバトル統計の修正時に使用。

使用方法:
    # ドライラン（変更を適用しない）
    python scripts/rebuild_dynamodb.py --dry-run

    # 実行
    python scripts/rebuild_dynamodb.py

    # 特定のリプレイのみ処理
    python scripts/rebuild_dynamodb.py --arena-id <arenaUniqueID>
"""

import argparse
import json
import sys
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any, List

# プロジェクトルートをパスに追加
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

import boto3
from botocore.exceptions import ClientError

from core.replay_metadata import ReplayMetadataParser
from parsers.battle_stats_extractor import (
    extract_battle_stats,
    get_win_loss_clan_battle,
    get_experience_earned,
    get_arena_unique_id,
)
from parsers.battlestats_parser import BattleStatsParser
from utils.dynamodb import get_table, calculate_main_clan_tag


# 設定
import os

S3_BUCKET = os.environ.get("S3_BUCKET", "wows-replay-bot-dev-temp")
AWS_REGION = "ap-northeast-1"


def get_s3_client():
    """S3クライアントを取得"""
    return boto3.client("s3", region_name=AWS_REGION)


def list_all_replays(s3_client) -> List[Dict[str, Any]]:
    """S3内の全リプレイファイルをリスト"""
    replays = []
    paginator = s3_client.get_paginator("list_objects_v2")

    for page in paginator.paginate(Bucket=S3_BUCKET, Prefix="replays/"):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            if key.endswith(".wowsreplay"):
                replays.append({
                    "s3_key": key,
                    "size": obj["Size"],
                    "last_modified": obj["LastModified"],
                })

    return replays


def parse_s3_key(s3_key: str) -> Dict[str, Any]:
    """
    S3キーからarenaUniqueIDとplayerIDを抽出

    形式: replays/{arenaUniqueID}/{playerID}/{filename}
    """
    parts = s3_key.split("/")
    if len(parts) >= 4:
        return {
            "arena_unique_id": parts[1],
            "player_id": int(parts[2]) if parts[2].isdigit() else 0,
            "filename": parts[3],
        }
    return {}


def download_replay(s3_client, s3_key: str) -> Optional[Path]:
    """リプレイファイルをダウンロード"""
    try:
        with tempfile.NamedTemporaryFile(suffix=".wowsreplay", delete=False) as tmp:
            tmp_path = Path(tmp.name)
            s3_client.download_fileobj(S3_BUCKET, s3_key, tmp)
            return tmp_path
    except Exception as e:
        print(f"  [ERROR] ダウンロード失敗: {e}")
        return None


def rebuild_record(
    s3_client,
    replay_info: Dict[str, Any],
    dry_run: bool = False,
) -> bool:
    """
    単一のリプレイレコードを再構築

    Args:
        s3_client: S3クライアント
        replay_info: リプレイ情報 (s3_key, size, etc.)
        dry_run: Trueの場合、変更を適用しない

    Returns:
        成功した場合True
    """
    s3_key = replay_info["s3_key"]
    key_info = parse_s3_key(s3_key)

    if not key_info:
        print(f"  [SKIP] 無効なS3キー形式: {s3_key}")
        return False

    arena_unique_id = key_info["arena_unique_id"]
    player_id = key_info["player_id"]

    print(f"  処理中: arenaID={arena_unique_id}, playerID={player_id}")

    # リプレイをダウンロード
    tmp_path = download_replay(s3_client, s3_key)
    if not tmp_path:
        return False

    try:
        # メタデータを再抽出
        metadata = ReplayMetadataParser.parse_replay_metadata(tmp_path)
        if not metadata:
            print(f"  [ERROR] メタデータの解析に失敗")
            return False

        # プレイヤー情報を再抽出（艦船名がAPIから再取得される）
        players_info = ReplayMetadataParser.extract_players_info(metadata)
        game_type = ReplayMetadataParser.extract_game_type(metadata)

        # バトル統計を再抽出
        battle_results = extract_battle_stats(str(tmp_path))

        # 更新データを構築
        update_data = {
            # プレイヤー情報（艦船名を含む）
            "ownPlayer": players_info.get("own", [{}])[0] if players_info.get("own") else {},
            "allies": players_info.get("allies", []),
            "enemies": players_info.get("enemies", []),
            "gameType": game_type or metadata.get("matchGroup", "unknown"),
        }

        # クラン情報を再計算
        if update_data["gameType"] == "clan":
            ally_players = [update_data["ownPlayer"]] + update_data["allies"] if update_data["ownPlayer"] else update_data["allies"]
            update_data["allyMainClanTag"] = calculate_main_clan_tag(ally_players)
            update_data["enemyMainClanTag"] = calculate_main_clan_tag(update_data["enemies"])

        # バトル統計がある場合
        if battle_results:
            # 勝敗情報
            update_data["winLoss"] = get_win_loss_clan_battle(battle_results)
            update_data["experienceEarned"] = get_experience_earned(battle_results)

            # 正しいarenaUniqueIDを取得
            real_arena_id = get_arena_unique_id(battle_results)
            if real_arena_id:
                update_data["realArenaUniqueID"] = str(real_arena_id)

            # プレイヤー統計
            players_public_info = battle_results.get("playersPublicInfo", {})
            if players_public_info:
                all_stats = BattleStatsParser.parse_all_players(players_public_info)

                # 自分の統計を特定
                player_name = metadata.get("playerName", "")
                own_stats = None
                for pid, stats in all_stats.items():
                    if stats.get("player_name") == player_name:
                        own_stats = stats
                        break

                if own_stats:
                    stats_data = BattleStatsParser.to_dynamodb_format(own_stats)
                    update_data.update({
                        "damage": stats_data.get("damage", 0),
                        "receivedDamage": stats_data.get("receivedDamage", 0),
                        "spottingDamage": stats_data.get("spottingDamage", 0),
                        "potentialDamage": stats_data.get("potentialDamage", 0),
                        "kills": stats_data.get("kills", 0),
                        "fires": stats_data.get("fires", 0),
                        "floods": stats_data.get("floods", 0),
                        "baseXP": stats_data.get("baseXP", 0),
                        "hitsAP": stats_data.get("hitsAP", 0),
                        "hitsHE": stats_data.get("hitsHE", 0),
                        "hitsSecondaries": stats_data.get("hitsSecondaries", 0),
                        "damageAP": stats_data.get("damageAP", 0),
                        "damageHE": stats_data.get("damageHE", 0),
                        "damageHESecondaries": stats_data.get("damageHESecondaries", 0),
                        "damageTorps": stats_data.get("damageTorps", 0),
                        "damageDeepWaterTorps": stats_data.get("damageDeepWaterTorps", 0),
                        "damageOther": stats_data.get("damageOther", 0),
                        "damageFire": stats_data.get("damageFire", 0),
                        "damageFlooding": stats_data.get("damageFlooding", 0),
                        "citadels": stats_data.get("citadels", 0),
                    })

                # 全プレイヤー統計を構築
                all_players_stats = build_all_players_stats(all_stats, update_data)
                if all_players_stats:
                    update_data["allPlayersStats"] = all_players_stats

        if dry_run:
            print(f"  [DRY-RUN] 更新内容:")
            print(f"    艦船名例: {update_data.get('ownPlayer', {}).get('shipName', 'N/A')}")
            print(f"    ダメージ: {update_data.get('damage', 'N/A')}")
            print(f"    Citadels: {update_data.get('citadels', 'N/A')}")
            return True

        # DynamoDBを更新
        table = get_table()

        # UpdateExpressionを構築
        update_expressions = []
        expression_values = {}
        expression_names = {}

        for key, value in update_data.items():
            if value is not None:
                safe_key = f"#{key}"
                expression_names[safe_key] = key
                update_expressions.append(f"{safe_key} = :{key}")
                expression_values[f":{key}"] = value

        if update_expressions:
            table.update_item(
                Key={
                    "arenaUniqueID": arena_unique_id,
                    "playerID": player_id,
                },
                UpdateExpression="SET " + ", ".join(update_expressions),
                ExpressionAttributeNames=expression_names,
                ExpressionAttributeValues=expression_values,
            )
            print(f"  [OK] 更新完了")

        return True

    except Exception as e:
        print(f"  [ERROR] 処理エラー: {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # 一時ファイルを削除
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


def build_all_players_stats(all_stats: dict, record: dict) -> list:
    """
    全プレイヤーの統計情報をチーム情報と紐付けて配列で返す
    (battle_result_extractor.pyからコピー)
    """
    player_team_map = {}

    own_player = record.get("ownPlayer", {})
    if isinstance(own_player, list):
        own_player = own_player[0] if own_player else {}
    if own_player and own_player.get("name"):
        player_team_map[own_player["name"]] = {
            "team": "ally",
            "shipId": own_player.get("shipId", 0),
            "shipName": own_player.get("shipName", ""),
            "isOwn": True,
        }

    for ally in record.get("allies", []):
        if ally.get("name"):
            player_team_map[ally["name"]] = {
                "team": "ally",
                "shipId": ally.get("shipId", 0),
                "shipName": ally.get("shipName", ""),
                "isOwn": False,
            }

    for enemy in record.get("enemies", []):
        if enemy.get("name"):
            player_team_map[enemy["name"]] = {
                "team": "enemy",
                "shipId": enemy.get("shipId", 0),
                "shipName": enemy.get("shipName", ""),
                "isOwn": False,
            }

    result = []
    for player_id, stats in all_stats.items():
        player_name = stats.get("player_name", "")
        team_info = player_team_map.get(player_name, {"team": "unknown", "shipId": 0, "shipName": ""})

        stats_data = BattleStatsParser.to_dynamodb_format(stats)
        stats_data["team"] = team_info["team"]
        stats_data["shipId"] = team_info.get("shipId", 0)
        stats_data["shipName"] = team_info.get("shipName", "")
        stats_data["isOwn"] = team_info.get("isOwn", False)

        result.append(stats_data)

    result.sort(key=lambda x: x.get("damage", 0), reverse=True)
    return result


def main():
    parser = argparse.ArgumentParser(description="DynamoDB再構築スクリプト")
    parser.add_argument("--dry-run", action="store_true", help="変更を適用せずにシミュレーション")
    parser.add_argument("--arena-id", type=str, help="特定のarenaUniqueIDのみ処理")
    parser.add_argument("--limit", type=int, default=0, help="処理する最大件数 (0=無制限)")
    args = parser.parse_args()

    print("=" * 60)
    print("DynamoDB再構築スクリプト")
    print("=" * 60)

    if args.dry_run:
        print("[MODE] ドライラン（変更は適用されません）")

    s3_client = get_s3_client()

    # リプレイ一覧を取得
    print("\nS3からリプレイ一覧を取得中...")
    replays = list_all_replays(s3_client)
    print(f"  {len(replays)} 件のリプレイが見つかりました")

    # 特定のarenaIDでフィルタ
    if args.arena_id:
        replays = [r for r in replays if args.arena_id in r["s3_key"]]
        print(f"  フィルタ後: {len(replays)} 件")

    # 件数制限
    if args.limit > 0:
        replays = replays[:args.limit]
        print(f"  制限適用後: {len(replays)} 件")

    # 処理実行
    print("\n処理開始...")
    success_count = 0
    error_count = 0

    for i, replay in enumerate(replays, 1):
        print(f"\n[{i}/{len(replays)}] {replay['s3_key']}")

        if rebuild_record(s3_client, replay, dry_run=args.dry_run):
            success_count += 1
        else:
            error_count += 1

    # 結果サマリー
    print("\n" + "=" * 60)
    print("処理完了")
    print("=" * 60)
    print(f"  成功: {success_count} 件")
    print(f"  エラー: {error_count} 件")

    if args.dry_run:
        print("\n[INFO] ドライランモードでした。実際に変更を適用するには --dry-run を外して再実行してください。")


if __name__ == "__main__":
    main()
