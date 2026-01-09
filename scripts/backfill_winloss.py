#!/usr/bin/env python3
"""
勝敗情報バックフィルスクリプト

既存のDynamoDBレコードの勝敗情報（winLoss）を更新する。
S3からリプレイファイルをダウンロードし、hiddenデータから勝敗を抽出する。
"""

import os
import sys
import tempfile
from pathlib import Path

import boto3

# srcをパスに追加
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_PATH = PROJECT_ROOT / "src"
REPLAYS_UNPACK_PATH = PROJECT_ROOT / "replays_unpack_upstream"

sys.path.insert(0, str(SRC_PATH))
sys.path.insert(0, str(REPLAYS_UNPACK_PATH))

from parsers.battle_stats_extractor import extract_hidden_data, get_win_loss_from_hidden

# 環境変数
REPLAYS_TABLE = os.environ.get("REPLAYS_TABLE", "wows-replays-dev")
TEMP_BUCKET = os.environ.get("TEMP_BUCKET", "wows-replay-bot-dev-temp")
REGION = os.environ.get("AWS_REGION", "ap-northeast-1")

# ドライラン（Trueの場合はDynamoDB更新をスキップ）
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"


def get_dynamodb():
    return boto3.resource("dynamodb", region_name=REGION)


def get_s3_client():
    return boto3.client("s3", region_name=REGION)


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


def group_by_match(replays):
    """arenaUniqueIDでグループ化"""
    matches = {}
    for item in replays:
        arena_id = item.get("arenaUniqueID", "")
        if not arena_id:
            continue
        if arena_id not in matches:
            matches[arena_id] = []
        matches[arena_id].append(item)
    return matches


def download_replay_file(s3_client, s3_key):
    """S3からリプレイファイルをダウンロード"""
    tmp_path = None
    with tempfile.NamedTemporaryFile(suffix=".wowsreplay", delete=False) as tmp_file:
        tmp_path = Path(tmp_file.name)
        s3_client.download_fileobj(TEMP_BUCKET, s3_key, tmp_file)
    return tmp_path


def process_match(table, s3_client, arena_id, records):
    """
    1つの試合を処理

    Args:
        table: DynamoDBテーブル
        s3_client: S3クライアント
        arena_id: 試合ID
        records: この試合のDynamoDBレコード
    """
    first_record = records[0]
    current_win_loss = first_record.get("winLoss", "unknown")

    # 既にwin/loss/drawが設定されている場合はスキップ
    if current_win_loss in ("win", "loss", "draw"):
        return {"status": "skipped", "reason": "already_has_winloss", "current": current_win_loss}

    # S3キーを取得（最初のレコードを使用）
    s3_key = first_record.get("s3Key")
    if not s3_key:
        return {"status": "skipped", "reason": "no_s3_key"}

    # リプレイファイルをダウンロード
    tmp_path = None
    try:
        tmp_path = download_replay_file(s3_client, s3_key)

        # hiddenデータを抽出
        hidden_data = extract_hidden_data(str(tmp_path))
        if not hidden_data:
            return {"status": "skipped", "reason": "no_hidden_data"}

        # 勝敗を判定
        win_loss = get_win_loss_from_hidden(hidden_data)
        if win_loss == "unknown":
            return {"status": "skipped", "reason": "win_loss_unknown"}

        # DynamoDBを更新
        if not DRY_RUN:
            for record in records:
                table.update_item(
                    Key={
                        "arenaUniqueID": record["arenaUniqueID"],
                        "playerID": record["playerID"],
                    },
                    UpdateExpression="SET winLoss = :wl",
                    ExpressionAttributeValues={":wl": win_loss},
                )

        return {
            "status": "updated",
            "win_loss": win_loss,
        }

    except Exception as e:
        return {"status": "error", "reason": str(e)}

    finally:
        # 一時ファイルを削除
        if tmp_path and tmp_path.exists():
            tmp_path.unlink()


def main():
    print("勝敗情報のバックフィルを開始...")
    print(f"DRY_RUN: {DRY_RUN}")
    print(f"リプレイテーブル: {REPLAYS_TABLE}")
    print(f"S3バケット: {TEMP_BUCKET}")

    dynamodb = get_dynamodb()
    table = dynamodb.Table(REPLAYS_TABLE)
    s3_client = get_s3_client()

    # 全リプレイをスキャン
    print("\n1. リプレイデータをスキャン中...")
    replays = scan_all_replays(table)
    print(f"   {len(replays)} 件のリプレイレコードを取得")

    # arenaUniqueIDでグループ化
    matches = group_by_match(replays)
    print(f"   {len(matches)} 件のユニークな試合")

    # 各試合を処理
    print("\n2. 各試合を処理中...")
    stats = {
        "updated": 0,
        "skipped": 0,
        "error": 0,
        "win": 0,
        "loss": 0,
        "draw": 0,
    }

    for i, (arena_id, records) in enumerate(matches.items()):
        if (i + 1) % 10 == 0:
            print(f"   処理中: {i + 1}/{len(matches)}")

        try:
            result = process_match(table, s3_client, arena_id, records)

            if result["status"] == "updated":
                stats["updated"] += 1
                win_loss = result["win_loss"]
                stats[win_loss] = stats.get(win_loss, 0) + 1
                print(f"   [更新] {arena_id}: {win_loss}")
            elif result["status"] == "error":
                stats["error"] += 1
                print(f"   [エラー] {arena_id}: {result['reason']}")
            else:
                stats["skipped"] += 1
                # 詳細なスキップ理由は表示しない（多すぎるため）
                if result.get("reason") not in ["already_has_winloss", "no_s3_key"]:
                    print(f"   [スキップ] {arena_id}: {result['reason']}")
        except Exception as e:
            stats["error"] += 1
            print(f"   [エラー] {arena_id}: {e}")

    # 結果を表示
    print("\n" + "=" * 50)
    print("処理完了!")
    print(f"  更新: {stats['updated']} 件")
    print(f"    - 勝利: {stats['win']} 件")
    print(f"    - 敗北: {stats['loss']} 件")
    print(f"    - 引分: {stats['draw']} 件")
    print(f"  スキップ: {stats['skipped']} 件")
    print(f"  エラー: {stats['error']} 件")

    if DRY_RUN:
        print("\n[注意] DRY_RUNモードのため、DynamoDBは更新されていません。")
        print("実際に更新するには: DRY_RUN=false python scripts/backfill_winloss.py")


if __name__ == "__main__":
    main()
