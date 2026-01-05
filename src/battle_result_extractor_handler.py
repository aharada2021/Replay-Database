"""
バトル結果抽出ハンドラー

S3にリプレイファイルがアップロードされた時にトリガーされ、
BattleStatsパケットから勝敗情報を抽出してDynamoDBを更新
"""

import json
import os
import boto3
import tempfile
from pathlib import Path
from typing import Dict, Any

from utils.battle_stats_extractor import (
    extract_battle_stats,
    get_win_loss_clan_battle,
    get_experience_earned,
    get_arena_unique_id
)
from utils import dynamodb

# S3クライアント
s3_client = boto3.client('s3')


def handle(event, context):
    """
    S3イベントハンドラー

    Args:
        event: S3イベント
        context: Lambdaコンテキスト

    Returns:
        処理結果
    """
    try:
        # S3イベントから情報を取得
        for record in event.get('Records', []):
            bucket = record['s3']['bucket']['name']
            key = record['s3']['object']['key']

            print(f"Processing: s3://{bucket}/{key}")

            # .wowsreplayファイルのみ処理
            if not key.endswith('.wowsreplay'):
                print(f"Skipping non-replay file: {key}")
                continue

            # S3からファイルをダウンロード
            with tempfile.NamedTemporaryFile(suffix='.wowsreplay', delete=False) as tmp_file:
                tmp_path = Path(tmp_file.name)
                s3_client.download_fileobj(bucket, key, tmp_file)

            try:
                # BattleStatsパケットを抽出
                battle_results = extract_battle_stats(str(tmp_path))

                if not battle_results:
                    print(f"No battle results found in {key}")
                    continue

                # arenaUniqueIDを取得
                arena_unique_id = get_arena_unique_id(battle_results)

                if not arena_unique_id:
                    print(f"No arenaUniqueID found in {key}")
                    continue

                # 勝敗情報を取得
                win_loss = get_win_loss_clan_battle(battle_results)
                experience_earned = get_experience_earned(battle_results)

                print(f"Arena ID: {arena_unique_id}, Win/Loss: {win_loss}, Exp: {experience_earned}")

                # S3キーからplayerIDを抽出
                # S3キー形式: replays/{arenaUniqueID}/{playerID}/{filename}
                key_parts = key.split('/')
                if len(key_parts) >= 3:
                    try:
                        player_id = int(key_parts[2])
                    except ValueError:
                        print(f"Failed to extract playerID from key: {key}")
                        continue
                else:
                    print(f"Invalid S3 key format: {key}")
                    continue

                # DynamoDBを更新
                dynamodb.update_battle_result(
                    arena_unique_id=arena_unique_id,
                    player_id=player_id,
                    win_loss=win_loss,
                    experience_earned=experience_earned
                )

                print(f"Successfully updated battle result for arena {arena_unique_id}, player {player_id}")

            finally:
                # 一時ファイルを削除
                if tmp_path.exists():
                    tmp_path.unlink()

        return {
            'statusCode': 200,
            'body': json.dumps({'message': 'Battle results extracted successfully'})
        }

    except Exception as e:
        print(f"Error in battle_result_extractor_handler: {e}")
        import traceback
        traceback.print_exc()

        return {
            'statusCode': 500,
            'body': json.dumps({'error': str(e)})
        }
