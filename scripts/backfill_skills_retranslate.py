#!/usr/bin/env python3
"""
艦長スキル再翻訳バックフィルスクリプト

既存のallPlayersStatsの艦長スキル名を最新の翻訳で更新する。
旧翻訳→新翻訳のマッピングを使用。
"""

import os
import sys
from pathlib import Path

import boto3

# srcをパスに追加
SCRIPT_DIR = Path(__file__).parent.resolve()
PROJECT_ROOT = SCRIPT_DIR.parent
SRC_PATH = PROJECT_ROOT / "src"

sys.path.insert(0, str(SRC_PATH))

# 環境変数
REPLAYS_TABLE = os.environ.get("REPLAYS_TABLE", "wows-replays-dev")
REGION = os.environ.get("AWS_REGION", "ap-northeast-1")

# ドライラン（Trueの場合はDynamoDB更新をスキップ）
DRY_RUN = os.environ.get("DRY_RUN", "true").lower() == "true"

# 旧翻訳→新翻訳のマッピング
OLD_TO_NEW_TRANSLATIONS = {
    # 駆逐艦
    "砲旋回強化": "歯車のグリスアップ",
    "浸水発生率上昇": "水浸し",
    "消耗品専門家": "消耗品技術者",
    "被発見警告": "敵弾接近警報",
    "快速魚雷": "高速魚雷",
    "超重量弾": "特重弾薬",
    "優先目標": "危険察知",
    "主砲・対空兵装専門家": "主砲・対空兵装技術者",
    "主砲・対空熟練者": "主砲・対空兵装専門家",
    # 巡洋艦
    "空の目": "上空の眼",
    "強打": "強烈な打撃力",
    "一流砲手": "最上級砲手",
    "多勢に無勢": "数的劣勢",
    # 戦艦
    "爆破技師": "爆発物専門家",
    "緊急修理専門家": "緊急修理技術者",
    "超重量徹甲弾": "超重徹甲弾",
    "長距離副砲弾": "長射程副砲弾",
    "生存性基礎": "応急対応の基本",
    "修理班改良": "改良型修理班準備",
    "憤怒": "猛烈",
    "副砲手動照準": "副砲の手動照準",
    "近距離戦専門家": "接近戦",
    # 空母
    "最後のあがき": "最後の奮闘",
    "戦闘機管制": "戦闘機指揮所",
    "索敵殲滅": "索敵掃討",
    "修理専門家": "修理技術者",
    "副兵装専門家": "副砲専門家",
    "哨戒隊指揮官": "偵察隊リーダー",
    "強化徹甲弾": "強化型徹甲弾",
    "爆撃機管制": "爆撃機の飛行制御",
    "強化航空機装甲": "強化型航空機装甲",
    "潜在脅威": "隠れた脅威",
    "反応強化": "強化型反応速度",
    # 潜水艦
    "ソナー強化": "強化型ソナー",
    "蓄電池容量改良": "改良型バッテリー容量",
    "魚雷要員訓練": "魚雷員訓練",
    "インパルス発生器強化": "強化型インパルス発生器",
    "ソナー員": "ソナー操作員",
    "警戒監視": "用心",
    "魚雷照準名人": "魚雷誘導マスター",
    "ソナー員専門家": "ソナー操作専門家",
    "蓄電池効率改良": "改良型バッテリー効率",
    "プロペラシャフト拡大": "大型プロペラ・シャフト",
}


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


def retranslate_skill(skill_name: str) -> str:
    """旧翻訳を新翻訳に変換"""
    return OLD_TO_NEW_TRANSLATIONS.get(skill_name, skill_name)


def retranslate_skills(existing_stats):
    """
    既存のallPlayersStatsのcaptainSkillsを再翻訳

    Args:
        existing_stats: 既存のallPlayersStats

    Returns:
        (updated_stats, converted_count): 更新されたstatsと変換されたスキル数
    """
    if not existing_stats:
        return existing_stats, 0

    updated_stats = []
    converted_count = 0

    for stats in existing_stats:
        updated = dict(stats)
        captain_skills = stats.get("captainSkills", [])

        if captain_skills:
            new_skills = []
            for skill in captain_skills:
                new_skill = retranslate_skill(skill)
                if new_skill != skill:
                    converted_count += 1
                new_skills.append(new_skill)
            updated["captainSkills"] = new_skills

        updated_stats.append(updated)

    return updated_stats, converted_count


def process_match(table, arena_id, records):
    """1つの試合を処理"""
    first_record = records[0]
    existing_stats = first_record.get("allPlayersStats", [])

    if not existing_stats:
        return {"status": "skipped", "reason": "no_existing_stats"}

    has_skills = any(p.get("captainSkills") for p in existing_stats)
    if not has_skills:
        return {"status": "skipped", "reason": "no_captain_skills"}

    updated_stats, converted_count = retranslate_skills(existing_stats)

    if converted_count == 0:
        return {"status": "skipped", "reason": "no_changes_needed"}

    if not DRY_RUN:
        for record in records:
            table.update_item(
                Key={
                    "arenaUniqueID": record["arenaUniqueID"],
                    "playerID": record["playerID"],
                },
                UpdateExpression="SET allPlayersStats = :stats",
                ExpressionAttributeValues={":stats": updated_stats},
            )

    return {
        "status": "updated",
        "converted_count": converted_count,
    }


def main():
    print("艦長スキル再翻訳バックフィルを開始...")
    print(f"DRY_RUN: {DRY_RUN}")
    print(f"リプレイテーブル: {REPLAYS_TABLE}")

    dynamodb = get_dynamodb()
    table = dynamodb.Table(REPLAYS_TABLE)

    print("\n1. リプレイデータをスキャン中...")
    replays = scan_all_replays(table)
    print(f"   {len(replays)} 件のリプレイレコードを取得")

    matches = group_by_match(replays)
    print(f"   {len(matches)} 件のユニークな試合")

    print("\n2. 各試合を処理中...")
    stats = {
        "updated": 0,
        "skipped": 0,
        "error": 0,
        "total_converted": 0,
    }

    for i, (arena_id, records) in enumerate(matches.items()):
        if (i + 1) % 50 == 0:
            print(f"   処理中: {i + 1}/{len(matches)}")

        try:
            result = process_match(table, arena_id, records)

            if result["status"] == "updated":
                stats["updated"] += 1
                stats["total_converted"] += result.get("converted_count", 0)
                print(f"   [更新] {arena_id}: {result['converted_count']}件のスキルを再翻訳")
            elif result["status"] == "error":
                stats["error"] += 1
                print(f"   [エラー] {arena_id}: {result['reason']}")
            else:
                stats["skipped"] += 1
        except Exception as e:
            stats["error"] += 1
            print(f"   [エラー] {arena_id}: {e}")

    print("\n" + "=" * 50)
    print("処理完了!")
    print(f"  更新: {stats['updated']} 件")
    print(f"  スキップ: {stats['skipped']} 件")
    print(f"  エラー: {stats['error']} 件")
    print(f"  再翻訳されたスキル: {stats['total_converted']} 件")

    if DRY_RUN:
        print("\n[注意] DRY_RUNモードのため、DynamoDBは更新されていません。")
        print("実際に更新するには: DRY_RUN=false python scripts/backfill_skills_retranslate.py")


if __name__ == "__main__":
    main()
