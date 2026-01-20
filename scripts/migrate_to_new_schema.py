"""
DynamoDB 新スキーマへのデータ移行スクリプト

旧テーブル (wows-replays-{stage}) から新テーブル構造に移行する。

使用方法:
    # Dry-run（実際には書き込まない）
    python scripts/migrate_to_new_schema.py --stage dev --dry-run

    # 実行
    python scripts/migrate_to_new_schema.py --stage dev

    # 特定の試合のみ移行
    python scripts/migrate_to_new_schema.py --stage dev --arena-id 3487309050689265
"""

import argparse
import time
from collections import defaultdict
from datetime import datetime
from decimal import Decimal

import boto3
from botocore.exceptions import ClientError


def get_game_type(raw_game_type: str) -> str:
    """
    リプレイファイルの gameType を正規化
    """
    game_type_map = {
        "clan": "clan",
        "ranked": "ranked",
        "pvp": "random",
        "pve": "other",
        "cooperative": "other",
        "event": "other",
    }
    return game_type_map.get(raw_game_type.lower(), "other")


def get_battle_table_name(game_type: str, stage: str) -> str:
    """
    gameType に対応するテーブル名を返す
    """
    table_map = {
        "clan": f"wows-clan-battles-{stage}",
        "ranked": f"wows-ranked-battles-{stage}",
        "random": f"wows-random-battles-{stage}",
        "other": f"wows-other-battles-{stage}",
    }
    return table_map.get(game_type, f"wows-other-battles-{stage}")


def parse_datetime_to_unix(date_time_str: str) -> int:
    """
    DD.MM.YYYY HH:MM:SS 形式の日時をUnix timestampに変換
    """
    try:
        dt = datetime.strptime(date_time_str, "%d.%m.%Y %H:%M:%S")
        return int(dt.timestamp())
    except ValueError:
        # フォールバック: 現在時刻を使用
        return int(time.time())


def decimal_to_python(obj):
    """
    DynamoDB の Decimal 型を Python の int/float に変換
    """
    if isinstance(obj, Decimal):
        if obj % 1 == 0:
            return int(obj)
        return float(obj)
    elif isinstance(obj, dict):
        return {k: decimal_to_python(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [decimal_to_python(i) for i in obj]
    elif isinstance(obj, set):
        return [decimal_to_python(i) for i in obj]
    return obj


def python_to_decimal(obj):
    """
    Python の int/float を DynamoDB の Decimal 型に変換
    """
    if isinstance(obj, float):
        return Decimal(str(obj))
    elif isinstance(obj, int):
        return obj  # DynamoDB は int をそのまま受け入れる
    elif isinstance(obj, dict):
        return {k: python_to_decimal(v) for k, v in obj.items()}
    elif isinstance(obj, list):
        return [python_to_decimal(i) for i in obj]
    return obj


class DataMigrator:
    def __init__(self, stage: str, dry_run: bool = True):
        self.stage = stage
        self.dry_run = dry_run
        self.dynamodb = boto3.resource("dynamodb", region_name="ap-northeast-1")

        # テーブル参照
        self.old_replays_table = self.dynamodb.Table(f"wows-replays-{stage}")
        self.ship_index_table = self.dynamodb.Table(f"wows-ship-index-{stage}")
        self.player_index_table = self.dynamodb.Table(f"wows-player-index-{stage}")
        self.clan_index_table = self.dynamodb.Table(f"wows-clan-index-{stage}")

        # 統計
        self.stats = {
            "total_old_records": 0,
            "unique_matches": 0,
            "match_records_created": 0,
            "stats_records_created": 0,
            "upload_records_created": 0,
            "ship_index_records": 0,
            "player_index_records": 0,
            "clan_index_records": 0,
            "errors": [],
        }

    def get_battle_table(self, game_type: str):
        """gameType に対応するテーブルを取得"""
        table_name = get_battle_table_name(game_type, self.stage)
        return self.dynamodb.Table(table_name)

    def fetch_old_data(self, arena_id: str = None) -> list:
        """旧テーブルからデータを取得"""
        items = []

        if arena_id:
            # 特定の試合のみ取得
            response = self.old_replays_table.query(
                KeyConditionExpression="arenaUniqueID = :aid",
                ExpressionAttributeValues={":aid": arena_id},
            )
            items.extend(response.get("Items", []))
        else:
            # 全件取得
            response = self.old_replays_table.scan()
            items.extend(response.get("Items", []))

            while "LastEvaluatedKey" in response:
                response = self.old_replays_table.scan(
                    ExclusiveStartKey=response["LastEvaluatedKey"]
                )
                items.extend(response.get("Items", []))

        self.stats["total_old_records"] = len(items)
        return items

    def group_by_match(self, items: list) -> dict:
        """arenaUniqueID でグループ化"""
        matches = defaultdict(list)
        for item in items:
            arena_id = item.get("arenaUniqueID")
            if arena_id:
                matches[arena_id].append(item)

        self.stats["unique_matches"] = len(matches)
        return matches

    def create_match_record(self, arena_id: str, uploads: list) -> dict:
        """MATCH レコードを作成"""
        # 最初のアップロードを基準にする
        first_upload = uploads[0]

        # Unix timestamp に変換
        date_time = first_upload.get("dateTime", "")
        unix_time = parse_datetime_to_unix(date_time)

        # アップロード者リスト作成
        uploaders = []
        for upload in uploads:
            own_player = upload.get("ownPlayer", {})
            if isinstance(own_player, dict):
                player_id = upload.get("playerID", 0)
                player_name = own_player.get("name", upload.get("playerName", ""))
                # team の判定: 最初のアップロード者と同じクランなら ally
                first_clan = uploads[0].get("ownPlayer", {}).get("clanTag", "")
                this_clan = own_player.get("clanTag", "")
                team = "ally" if this_clan == first_clan else "enemy"

                uploaders.append(
                    {
                        "playerID": decimal_to_python(player_id),
                        "playerName": player_name,
                        "team": team,
                    }
                )

        # allPlayersStats から allies/enemies を構築（もしなければ既存のを使用）
        allies = decimal_to_python(first_upload.get("allies", []))
        enemies = decimal_to_python(first_upload.get("enemies", []))

        # 最初のアップロード者の視点情報
        first_own_player = first_upload.get("ownPlayer", {})
        ally_perspective_player_id = decimal_to_python(first_upload.get("playerID", 0))
        ally_perspective_player_name = (
            first_own_player.get("name", "") if isinstance(first_own_player, dict) else ""
        )

        # dual renderer 判定
        ally_uploads = [u for u in uploaders if u.get("team") == "ally"]
        enemy_uploads = [u for u in uploaders if u.get("team") == "enemy"]
        dual_renderer_available = len(ally_uploads) > 0 and len(enemy_uploads) > 0

        match_record = {
            "arenaUniqueID": arena_id,
            "recordType": "MATCH",
            # GSI用
            "listingKey": "ACTIVE",
            "unixTime": unix_time,
            # 基本情報
            "dateTime": date_time,
            "mapId": first_upload.get("mapId", ""),
            "mapDisplayName": first_upload.get("mapDisplayName", ""),
            "clientVersion": first_upload.get("clientVersion", ""),
            # 味方視点
            "allyPerspectivePlayerID": ally_perspective_player_id,
            "allyPerspectivePlayerName": ally_perspective_player_name,
            "winLoss": first_upload.get("winLoss", ""),
            # チーム情報
            "allyMainClanTag": first_upload.get("allyMainClanTag", ""),
            "enemyMainClanTag": first_upload.get("enemyMainClanTag", ""),
            "allies": allies,
            "enemies": enemies,
            # 動画
            "mp4S3Key": first_upload.get("mp4S3Key", ""),
            "mp4GeneratedAt": decimal_to_python(first_upload.get("mp4GeneratedAt"))
            if first_upload.get("mp4GeneratedAt")
            else None,
            "dualRendererAvailable": dual_renderer_available,
            # コメント
            "commentCount": decimal_to_python(first_upload.get("commentCount", 0)),
            # アップロード者
            "uploaders": uploaders,
        }

        return python_to_decimal(match_record)

    def create_stats_record(self, arena_id: str, uploads: list) -> dict:
        """STATS レコードを作成"""
        first_upload = uploads[0]
        all_players_stats = first_upload.get("allPlayersStats", [])

        stats_record = {
            "arenaUniqueID": arena_id,
            "recordType": "STATS",
            "allPlayersStats": decimal_to_python(all_players_stats),
        }

        return python_to_decimal(stats_record)

    def create_upload_record(self, arena_id: str, upload: dict, team: str) -> dict:
        """UPLOAD レコードを作成"""
        player_id = decimal_to_python(upload.get("playerID", 0))
        own_player = upload.get("ownPlayer", {})
        unix_time = parse_datetime_to_unix(upload.get("dateTime", ""))

        upload_record = {
            "arenaUniqueID": arena_id,
            "recordType": f"UPLOAD#{player_id}",
            # アップロード者情報
            "playerID": player_id,
            "playerName": own_player.get("name", "") if isinstance(own_player, dict) else upload.get("playerName", ""),
            "team": team,
            # リプレイファイル
            "s3Key": upload.get("s3Key", ""),
            "fileName": upload.get("fileName", ""),
            "fileSize": decimal_to_python(upload.get("fileSize", 0)),
            "uploadedAt": unix_time,
            "uploadedBy": upload.get("uploadedBy", ""),
            # ownPlayer情報
            "ownPlayer": decimal_to_python(own_player),
            # 成績
            "damage": decimal_to_python(upload.get("damage", 0)),
            "kills": decimal_to_python(upload.get("kills", 0)),
            "spottingDamage": decimal_to_python(upload.get("spottingDamage", 0)),
            "potentialDamage": decimal_to_python(upload.get("potentialDamage", 0)),
            "receivedDamage": decimal_to_python(upload.get("receivedDamage", 0)),
            "baseXP": decimal_to_python(upload.get("baseXP", 0)),
            "experienceEarned": decimal_to_python(upload.get("experienceEarned", 0)),
            "citadels": decimal_to_python(upload.get("citadels", 0)),
            "fires": decimal_to_python(upload.get("fires", 0)),
            "floods": decimal_to_python(upload.get("floods", 0)),
            "damageAP": decimal_to_python(upload.get("damageAP", 0)),
            "damageHE": decimal_to_python(upload.get("damageHE", 0)),
            "damageTorps": decimal_to_python(upload.get("damageTorps", 0)),
            "damageFire": decimal_to_python(upload.get("damageFire", 0)),
            "damageFlooding": decimal_to_python(upload.get("damageFlooding", 0)),
            "hitsAP": decimal_to_python(upload.get("hitsAP", 0)),
            "hitsHE": decimal_to_python(upload.get("hitsHE", 0)),
        }

        return python_to_decimal(upload_record)

    def create_ship_index_records(
        self, arena_id: str, game_type: str, unix_time: int, all_players_stats: list
    ) -> list:
        """艦艇インデックスレコードを作成"""
        ship_counts = defaultdict(lambda: {"ally": 0, "enemy": 0})

        for player in all_players_stats:
            ship_name = player.get("shipName", "").upper()
            team = player.get("team", "")
            if ship_name and team in ["ally", "enemy"]:
                ship_counts[ship_name][team] += 1

        records = []
        for ship_name, counts in ship_counts.items():
            sk = f"{game_type}#{unix_time}#{arena_id}"
            record = {
                "shipName": ship_name,
                "SK": sk,
                "allyCount": counts["ally"],
                "enemyCount": counts["enemy"],
                "totalCount": counts["ally"] + counts["enemy"],
            }
            records.append(record)

        return records

    def create_player_index_records(
        self, arena_id: str, game_type: str, unix_time: int, all_players_stats: list
    ) -> list:
        """プレイヤーインデックスレコードを作成"""
        records = []

        for player in all_players_stats:
            player_name = player.get("playerName", "")
            if not player_name:
                continue

            sk = f"{game_type}#{unix_time}#{arena_id}"
            record = {
                "playerName": player_name,
                "SK": sk,
                "team": player.get("team", ""),
                "clanTag": player.get("clanTag", ""),
                "shipName": player.get("shipName", ""),
            }
            records.append(record)

        return records

    def create_clan_index_records(
        self,
        arena_id: str,
        game_type: str,
        unix_time: int,
        all_players_stats: list,
        ally_main_clan: str,
        enemy_main_clan: str,
    ) -> list:
        """クランインデックスレコードを作成"""
        clan_counts = defaultdict(lambda: {"ally": 0, "enemy": 0})

        for player in all_players_stats:
            clan_tag = player.get("clanTag", "")
            team = player.get("team", "")
            if clan_tag and team in ["ally", "enemy"]:
                clan_counts[clan_tag][team] += 1

        records = []
        for clan_tag, counts in clan_counts.items():
            sk = f"{game_type}#{unix_time}#{arena_id}"
            is_main = clan_tag in [ally_main_clan, enemy_main_clan]
            team = "ally" if counts["ally"] > counts["enemy"] else "enemy"

            record = {
                "clanTag": clan_tag,
                "SK": sk,
                "team": team,
                "memberCount": counts["ally"] + counts["enemy"],
                "isMainClan": is_main,
            }
            records.append(record)

        return records

    def write_batch(self, table, items: list):
        """バッチ書き込み"""
        if self.dry_run:
            return

        with table.batch_writer() as batch:
            for item in items:
                batch.put_item(Item=item)

    def migrate_match(self, arena_id: str, uploads: list):
        """1試合分のデータを移行"""
        try:
            first_upload = uploads[0]
            raw_game_type = first_upload.get("gameType", "other")
            game_type = get_game_type(raw_game_type)
            battle_table = self.get_battle_table(game_type)

            # MATCH レコード作成
            match_record = self.create_match_record(arena_id, uploads)
            unix_time = match_record.get("unixTime", 0)

            # STATS レコード作成
            stats_record = self.create_stats_record(arena_id, uploads)

            # UPLOAD レコード作成
            upload_records = []
            first_clan = uploads[0].get("ownPlayer", {}).get("clanTag", "")
            for upload in uploads:
                this_clan = upload.get("ownPlayer", {}).get("clanTag", "")
                team = "ally" if this_clan == first_clan else "enemy"
                upload_record = self.create_upload_record(arena_id, upload, team)
                upload_records.append(upload_record)

            # バトルテーブルに書き込み
            battle_items = [match_record, stats_record] + upload_records
            self.write_batch(battle_table, battle_items)
            self.stats["match_records_created"] += 1
            self.stats["stats_records_created"] += 1
            self.stats["upload_records_created"] += len(upload_records)

            # インデックステーブルに書き込み
            all_players_stats = decimal_to_python(first_upload.get("allPlayersStats", []))

            # Ship index
            ship_records = self.create_ship_index_records(
                arena_id, game_type, unix_time, all_players_stats
            )
            self.write_batch(self.ship_index_table, ship_records)
            self.stats["ship_index_records"] += len(ship_records)

            # Player index
            player_records = self.create_player_index_records(
                arena_id, game_type, unix_time, all_players_stats
            )
            self.write_batch(self.player_index_table, player_records)
            self.stats["player_index_records"] += len(player_records)

            # Clan index
            ally_main_clan = first_upload.get("allyMainClanTag", "")
            enemy_main_clan = first_upload.get("enemyMainClanTag", "")
            clan_records = self.create_clan_index_records(
                arena_id,
                game_type,
                unix_time,
                all_players_stats,
                ally_main_clan,
                enemy_main_clan,
            )
            self.write_batch(self.clan_index_table, clan_records)
            self.stats["clan_index_records"] += len(clan_records)

            print(f"  ✓ {arena_id}: {game_type}, {len(upload_records)} uploads")

        except Exception as e:
            error_msg = f"Error migrating {arena_id}: {e}"
            print(f"  ✗ {error_msg}")
            self.stats["errors"].append(error_msg)

    def run(self, arena_id: str = None):
        """移行を実行"""
        print(f"=== DynamoDB Migration Script ===")
        print(f"Stage: {self.stage}")
        print(f"Dry-run: {self.dry_run}")
        print()

        # データ取得
        print("Fetching data from old table...")
        items = self.fetch_old_data(arena_id)
        print(f"  Found {len(items)} records")

        # グループ化
        print("Grouping by match...")
        matches = self.group_by_match(items)
        print(f"  Found {len(matches)} unique matches")
        print()

        # 移行実行
        print("Migrating matches...")
        for i, (arena_id, uploads) in enumerate(matches.items(), 1):
            print(f"[{i}/{len(matches)}] ", end="")
            self.migrate_match(arena_id, uploads)

        # 結果表示
        print()
        print("=== Migration Summary ===")
        print(f"Total old records: {self.stats['total_old_records']}")
        print(f"Unique matches: {self.stats['unique_matches']}")
        print(f"MATCH records created: {self.stats['match_records_created']}")
        print(f"STATS records created: {self.stats['stats_records_created']}")
        print(f"UPLOAD records created: {self.stats['upload_records_created']}")
        print(f"Ship index records: {self.stats['ship_index_records']}")
        print(f"Player index records: {self.stats['player_index_records']}")
        print(f"Clan index records: {self.stats['clan_index_records']}")
        print(f"Errors: {len(self.stats['errors'])}")

        if self.stats["errors"]:
            print()
            print("Errors:")
            for error in self.stats["errors"]:
                print(f"  - {error}")

        if self.dry_run:
            print()
            print("*** DRY-RUN MODE - No data was written ***")
            print("Run without --dry-run to actually migrate data.")


def main():
    parser = argparse.ArgumentParser(description="Migrate DynamoDB to new schema")
    parser.add_argument(
        "--stage",
        required=True,
        choices=["dev", "prod"],
        help="Stage (dev or prod)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Dry-run mode (no actual writes)",
    )
    parser.add_argument(
        "--arena-id",
        help="Migrate only specific arena ID",
    )

    args = parser.parse_args()

    migrator = DataMigrator(stage=args.stage, dry_run=args.dry_run)
    migrator.run(arena_id=args.arena_id)


if __name__ == "__main__":
    main()
