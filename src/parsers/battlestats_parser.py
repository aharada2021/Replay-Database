"""
BattleStats playersPublicInfo配列パーサー

BattleStatsパケットの位置ベース配列からプレイヤー統計を抽出するユーティリティ
"""

from typing import Dict, Any, List


class BattleStatsParser:
    """
    BattleStatsパケットのplayersPublicInfo配列をパースするクラス

    バージョン: 14.11.0で検証済み
    """

    # インデックスマッピング（14.11.0基準）
    INDICES = {
        # 基本情報
        "player_id": 0,
        "player_name": 1,
        "account_db_id": 2,
        "clan_tag": 3,
        "clan_id": 4,
        "realm": 9,
        "survival_time": 22,
        "survival_percentage": 23,
        # 戦闘成績
        "kills": 32,
        # 命中数内訳
        "hits_ap": 66,
        "hits_he": 68,  # 主砲のみ
        "hits_secondaries": 71,  # 副砲HE弾
        "hits": 68,  # 互換性のため維持（実際はHE弾のみ）
        # DoT（継続ダメージ）
        "floods": 75,
        "fires": 86,
        # ダメージ内訳
        "damage_ap": 157,  # 主砲AP弾
        "damage_he": 159,  # 主砲HE弾
        "damage_he_secondaries": 162,  # 副砲HE弾
        "damage_torps": 166,  # 通常魚雷
        "damage_deep_water_torps": 167,  # 深度魚雷（パンアジア駆逐艦）
        "damage_other": 178,  # その他ダメージ（主砲AP+副砲AP等の残差）
        "damage_fire": 179,  # 火災ダメージ
        "damage_flooding": 180,  # 浸水ダメージ
        # 総ダメージ統計
        "received_damage": 204,
        "damage": 429,
        # 経験値・スポットダメージ
        "base_xp": 406,
        "spotting_damage": 415,
        "potential_damage": 419,
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
        if not isinstance(player_data, list) or len(player_data) < 430:
            data_len = len(player_data) if isinstance(player_data, list) else 0
            raise ValueError(
                f"Invalid player_data: expected list with 430+ elements, "
                f"got {type(player_data)} with {data_len} elements"
            )

        stats = {}

        for key, index in cls.INDICES.items():
            try:
                value = player_data[index]

                # データ型変換
                if key == "potential_damage" and isinstance(value, float):
                    stats[key] = int(value)
                elif key in ["player_id", "account_db_id", "clan_id"] and value is not None:
                    stats[key] = int(value)
                elif key in ["player_name", "clan_tag", "realm"] and value is not None:
                    stats[key] = str(value)
                else:
                    stats[key] = value

            except (IndexError, TypeError, ValueError):
                # インデックスが存在しない、または変換失敗時はNoneを設定
                stats[key] = None

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
            "damage": stats.get("damage", 0),
            "receivedDamage": stats.get("received_damage", 0),
            "spottingDamage": stats.get("spotting_damage", 0),
            "potentialDamage": stats.get("potential_damage", 0),
            "kills": stats.get("kills", 0),
            "fires": stats.get("fires", 0),
            "floods": stats.get("floods", 0),
            "baseXP": stats.get("base_xp", 0),
            # 命中数内訳
            "hitsAP": stats.get("hits_ap", 0),
            "hitsHE": stats.get("hits_he", 0),
            "hitsSecondaries": stats.get("hits_secondaries", 0),
            # ダメージ内訳
            "damageAP": stats.get("damage_ap", 0),
            "damageHE": stats.get("damage_he", 0),
            "damageHESecondaries": stats.get("damage_he_secondaries", 0),
            "damageTorps": stats.get("damage_torps", 0),
            "damageDeepWaterTorps": stats.get("damage_deep_water_torps", 0),
            "damageOther": stats.get("damage_other", 0),
            "damageFire": stats.get("damage_fire", 0),
            "damageFlooding": stats.get("damage_flooding", 0),
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
