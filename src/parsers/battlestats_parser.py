"""
BattleStats playersPublicInfo配列パーサー

BattleStatsパケットの位置ベース配列からプレイヤー統計を抽出するユーティリティ
"""

from typing import Dict, Any, List


class BattleStatsParser:
    """
    BattleStatsパケットのplayersPublicInfo配列をパースするクラス

    バージョン: 14.11.0で検証済み（2026-01-08更新）
    """

    # インデックスマッピング（14.11.0基準、実際のリプレイデータから検証済み）
    INDICES = {
        # 基本情報
        "account_db_id": 0,
        "player_name": 1,
        "clan_id": 2,
        "clan_tag": 3,
        "clan_color": 4,
        "clan_league": 5,
        "team_id": 6,
        "ship_id": 7,  # 艦艇ID（shipParamsId、艦艇タイプではない）
        "realm": 9,
        "max_health": 15,
        "life_time_sec": 22,  # 生存時間（秒）
        "distance": 23,  # 移動距離
        # 戦闘成績（リボン）
        "kills": 454,  # RIBBON_FRAG
        # 命中数内訳
        "hits_ap": 66,  # hits_main_ap
        "hits_sap": 67,  # hits_main_sap（イタリア巡洋艦等のSAP弾）
        "hits_he": 68,  # hits_main_he
        "hits_secondaries_sap": 70,  # hits_atba_sap（副砲SAP、Napoli等）※実データで検証済み
        "hits_secondaries": 71,  # hits_atba_he（副砲HE）
        "hits": 68,  # 互換性のため維持（実際はHE弾のみ）
        # 与えた火災・浸水（リボン）
        "fires": 455,  # RIBBON_BURN
        "floods": 456,  # RIBBON_FLOOD
        # 与えたダメージ内訳
        "damage_ap": 157,  # damage_main_ap
        "damage_sap": 158,  # damage_main_sap（イタリア巡洋艦等のSAP弾）
        "damage_he": 159,  # damage_main_he
        "damage_sap_secondaries": 161,  # damage_atba_sap（副砲SAP、Napoli等）※実データで検証済み
        "damage_he_secondaries": 162,  # damage_atba_he（副砲HE）
        "damage_torps": 166,  # damage_tpd_normal
        "damage_deep_water_torps": 167,  # damage_tpd_deep
        "damage_other": 178,  # その他ダメージ
        "damage_fire": 179,  # damage_fire
        "damage_flooding": 180,  # damage_flood
        # 総ダメージ
        "damage": 429,  # 総与ダメージ
        # 被ダメージ内訳
        "received_damage_ap": 202,  # received_damage_main_ap
        "received_damage_sap": 203,  # received_damage_main_sap（SAP被ダメージ）
        "received_damage_he": 204,  # received_damage_main_he
        "received_damage_torps": 205,  # received_damage_tpd_normal
        "received_damage_deep_water_torps": 206,  # received_damage_tpd_deep（深度魚雷被ダメージ）
        "received_damage_sap_secondaries": 218,  # received_damage_atba_sap（副砲SAP被ダメージ）※実データで検証済み
        "received_damage_he_secondaries": 219,  # received_damage_atba_he
        "received_damage_fire": 223,  # received_damage_fire
        "received_damage_flood": 224,  # received_damage_flood
        # 潜在ダメージ内訳
        "potential_damage_art": 419,  # agro_art（砲撃による潜在）
        "potential_damage_tpd": 420,  # agro_tpd（魚雷による潜在）
        # 偵察・経験値
        "spotting_damage": 415,  # scouting_damage
        "base_xp": 406,  # exp（表示用経験値）
        "raw_xp": 405,  # raw_exp
        # Citadel・クリティカル（リボン）
        "citadels": 457,  # RIBBON_CITADEL
        "crits": 453,  # RIBBON_CRIT
        # 互換性のための計算用フィールド（実際の値はparse時に計算）
        "received_damage": None,  # 被ダメ合計（計算で算出）
        "potential_damage": None,  # 潜在合計（計算で算出）
    }

    @classmethod
    def parse_player_stats(cls, player_data: List[Any]) -> Dict[str, Any]:
        """
        プレイヤーデータ配列から統計情報を抽出

        Args:
            player_data: playersPublicInfoのプレイヤーデータ配列

        Returns:
            統計情報の辞書
        """
        if not isinstance(player_data, list) or len(player_data) < 460:
            data_len = len(player_data) if isinstance(player_data, list) else 0
            raise ValueError(
                f"Invalid player_data: expected list with 460+ elements, "
                f"got {type(player_data)} with {data_len} elements"
            )

        stats = {}

        for key, index in cls.INDICES.items():
            # 計算フィールドはスキップ（後で計算）
            if index is None:
                continue

            try:
                value = player_data[index]

                # データ型変換
                if key in ["account_db_id", "clan_id", "ship_id"] and value is not None:
                    stats[key] = int(value)
                elif key in ["player_name", "clan_tag", "realm"] and value is not None:
                    stats[key] = str(value)
                elif isinstance(value, float):
                    stats[key] = int(value)
                else:
                    stats[key] = value

            except (IndexError, TypeError, ValueError):
                # インデックスが存在しない、または変換失敗時は0を設定
                stats[key] = 0 if key not in ["player_name", "clan_tag", "realm"] else ""

        # 被ダメージ合計を計算
        stats["received_damage"] = sum(
            [
                stats.get("received_damage_ap", 0) or 0,
                stats.get("received_damage_sap", 0) or 0,
                stats.get("received_damage_he", 0) or 0,
                stats.get("received_damage_torps", 0) or 0,
                stats.get("received_damage_deep_water_torps", 0) or 0,
                stats.get("received_damage_unknown_218", 0) or 0,
                stats.get("received_damage_he_secondaries", 0) or 0,
                stats.get("received_damage_fire", 0) or 0,
                stats.get("received_damage_flood", 0) or 0,
            ]
        )

        # 潜在ダメージ合計を計算
        stats["potential_damage"] = sum(
            [
                stats.get("potential_damage_art", 0) or 0,
                stats.get("potential_damage_tpd", 0) or 0,
            ]
        )

        return stats

    @classmethod
    def parse_all_players(cls, players_public_info: Dict[str, List[Any]]) -> Dict[str, Dict[str, Any]]:
        """
        全プレイヤーの統計情報を抽出

        Args:
            players_public_info: BattleStatsのplayersPublicInfo辞書

        Returns:
            プレイヤーID -> 統計情報のマッピング
        """
        result = {}

        for player_id, player_data in players_public_info.items():
            try:
                stats = cls.parse_player_stats(player_data)
                result[player_id] = stats
            except ValueError as e:
                print(f"Warning: Failed to parse player {player_id}: {e}")
                continue

        return result

    @classmethod
    def get_team_stats(cls, players_public_info: Dict[str, List[Any]], team_id: int) -> List[Dict[str, Any]]:
        """
        特定チームのプレイヤー統計を取得

        Args:
            players_public_info: BattleStatsのplayersPublicInfo辞書
            team_id: チームID (0 or 1)

        Returns:
            チームメンバーの統計情報リスト（ダメージ順にソート）
        """
        all_stats = cls.parse_all_players(players_public_info)

        # チームIDは配列の特定位置に無いため、別途判定が必要
        # （簡易版: metadata等から取得することを想定）
        team_stats = []
        for player_id, stats in all_stats.items():
            team_stats.append(stats)

        # ダメージでソート
        team_stats.sort(key=lambda x: x.get("damage", 0), reverse=True)

        return team_stats

    @classmethod
    def format_stats_for_display(cls, stats: Dict[str, Any]) -> str:
        """
        統計情報を人間が読める形式にフォーマット

        Args:
            stats: プレイヤー統計情報

        Returns:
            フォーマット済み文字列
        """
        clan_tag = f"[{stats['clan_tag']}]" if stats.get("clan_tag") else ""

        lines = [
            f"プレイヤー: {clan_tag} {stats['player_name']}",
            f"与ダメージ: {stats['damage']:,}",
            f"被ダメージ: {stats['received_damage']:,}",
            f"偵察ダメージ: {stats['spotting_damage']:,}",
            f"潜在ダメージ: {stats['potential_damage']:,}",
            f"撃沈数: {stats['kills']}",
            f"命中数: {stats['hits']}",
            f"火災: {stats['fires']} / 浸水: {stats['floods']}",
            f"基礎経験値: {stats['base_xp']:,}",
        ]

        return "\n".join(lines)

    @classmethod
    def to_dynamodb_format(cls, stats: Dict[str, Any]) -> Dict[str, Any]:
        """
        DynamoDB保存用にフォーマット

        Args:
            stats: プレイヤー統計情報

        Returns:
            DynamoDB保存用の辞書
        """
        # DynamoDBではNoneを保存できないため、デフォルト値を設定
        return {
            "playerName": stats.get("player_name", "Unknown"),
            "clanTag": stats.get("clan_tag", ""),
            # 基本統計
            "damage": stats.get("damage", 0) or 0,
            "receivedDamage": stats.get("received_damage", 0) or 0,
            "spottingDamage": stats.get("spotting_damage", 0) or 0,
            "potentialDamage": stats.get("potential_damage", 0) or 0,
            "kills": stats.get("kills", 0) or 0,
            "fires": stats.get("fires", 0) or 0,
            "floods": stats.get("floods", 0) or 0,
            "baseXP": stats.get("base_xp", 0) or 0,
            # 命中数内訳
            "hitsAP": stats.get("hits_ap", 0) or 0,
            "hitsSAP": stats.get("hits_sap", 0) or 0,
            "hitsHE": stats.get("hits_he", 0) or 0,
            "hitsSecondariesSAP": stats.get("hits_secondaries_sap", 0) or 0,
            "hitsSecondariesAP": stats.get("hits_secondaries_ap", 0) or 0,
            "hitsSecondaries": stats.get("hits_secondaries", 0) or 0,
            # 与ダメージ内訳
            "damageAP": stats.get("damage_ap", 0) or 0,
            "damageSAP": stats.get("damage_sap", 0) or 0,
            "damageHE": stats.get("damage_he", 0) or 0,
            "damageSAPSecondaries": stats.get("damage_sap_secondaries", 0) or 0,
            "damageUnknown161": stats.get("damage_unknown_161", 0) or 0,
            "damageHESecondaries": stats.get("damage_he_secondaries", 0) or 0,
            "damageTorps": stats.get("damage_torps", 0) or 0,
            "damageDeepWaterTorps": stats.get("damage_deep_water_torps", 0) or 0,
            "damageOther": stats.get("damage_other", 0) or 0,
            "damageFire": stats.get("damage_fire", 0) or 0,
            "damageFlooding": stats.get("damage_flooding", 0) or 0,
            # 被ダメージ内訳
            "receivedDamageAP": stats.get("received_damage_ap", 0) or 0,
            "receivedDamageSAP": stats.get("received_damage_sap", 0) or 0,
            "receivedDamageHE": stats.get("received_damage_he", 0) or 0,
            "receivedDamageTorps": stats.get("received_damage_torps", 0) or 0,
            "receivedDamageDeepWaterTorps": stats.get("received_damage_deep_water_torps", 0) or 0,
            "receivedDamageSAPSecondaries": stats.get("received_damage_sap_secondaries", 0) or 0,
            "receivedDamageUnknown218": stats.get("received_damage_unknown_218", 0) or 0,  # 互換性のため維持
            "receivedDamageHESecondaries": stats.get("received_damage_he_secondaries", 0) or 0,
            "receivedDamageFire": stats.get("received_damage_fire", 0) or 0,
            "receivedDamageFlood": stats.get("received_damage_flood", 0) or 0,
            # 潜在ダメージ内訳
            "potentialDamageArt": stats.get("potential_damage_art", 0) or 0,
            "potentialDamageTpd": stats.get("potential_damage_tpd", 0) or 0,
            # Citadel・クリティカル
            "citadels": stats.get("citadels", 0) or 0,
            "crits": stats.get("crits", 0) or 0,
        }


# 使用例
if __name__ == "__main__":
    import json
    import sys
    from pathlib import Path

    if len(sys.argv) < 2:
        print("Usage: python battlestats_parser.py <battlestats.json>")
        sys.exit(1)

    battlestats_path = Path(sys.argv[1])

    with open(battlestats_path, "r", encoding="utf-8") as f:
        battlestats = json.load(f)

    players_public_info = battlestats.get("playersPublicInfo", {})

    # 全プレイヤーをパース
    all_stats = BattleStatsParser.parse_all_players(players_public_info)

    print(f"\n全プレイヤーの統計 ({len(all_stats)}名):\n")

    # ダメージ順にソート
    sorted_players = sorted(all_stats.values(), key=lambda x: x.get("damage", 0), reverse=True)

    for stats in sorted_players:
        print(f"{stats['player_name']:<30} | ダメージ: {stats['damage']:>8,} | 撃沈: {stats['kills']}")

    print("\n詳細（トッププレイヤー）:")
    if sorted_players:
        print(BattleStatsParser.format_stats_for_display(sorted_players[0]))
