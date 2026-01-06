"""
リプレイ解析ハンドラー（extractor環境）

Discord slash commandからのリプレイファイルを解析し、
メタデータを抽出してvideo-generator Lambdaを呼び出す
"""

import os
import json
import logging
import tempfile
from pathlib import Path
from typing import Optional
import requests
import boto3

from core.replay_metadata import ReplayMetadataParser

# ログ設定
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 環境変数
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_API_BASE = "https://discord.com/api/v10"
TEMP_BUCKET = os.environ.get("TEMP_BUCKET", "wows-replay-bot-dev-temp")
VIDEO_GENERATOR_FUNCTION_NAME = os.environ.get(
    "VIDEO_GENERATOR_FUNCTION_NAME", "wows-replay-bot-dev-video-generator"
)

# AWSクライアント
s3_client = boto3.client("s3")
lambda_client = boto3.client("lambda")


def load_map_config() -> tuple:
    """マップ設定を読み込む"""
    import yaml

    # srcディレクトリの親（プロジェクトルート）からconfig/map_names.yamlを参照
    src_dir = Path(__file__).parent.parent.parent  # handlers/processing -> handlers -> src
    map_file = src_dir.parent / "config" / "map_names.yaml"
    try:
        with open(map_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            maps = data.get("maps", {})
            game_type_prefixes = data.get("game_type_prefixes", {})
            default_map_name = data.get("default_map_name", "その他のマップ")
            return maps, game_type_prefixes, default_map_name
    except Exception as e:
        logger.error(f"マップ名マッピングファイルの読み込みエラー: {e}")
        return {}, {}, "その他のマップ"


def extract_map_id_from_filename(filename: str) -> Optional[str]:
    """リプレイファイル名からマップIDを抽出"""
    if not filename.endswith(".wowsreplay"):
        return None

    name_without_ext = filename.replace(".wowsreplay", "")
    parts = name_without_ext.split("_")

    if len(parts) >= 4:
        for i in range(len(parts) - 1, -1, -1):
            if parts[i].isdigit():
                if i + 1 < len(parts):
                    map_id = "_".join(parts[i + 1 :])
                    return map_id
                break

    return None


def get_opponent_clan(players_info: dict) -> str:
    """敵プレイヤーの過半数のクランタグを取得"""
    enemies = players_info.get("enemies", [])

    if not enemies:
        return "不明"

    clan_counts = {}
    for player in enemies:
        clan_tag = player.get("clanTag")
        if clan_tag:
            clan_counts[clan_tag] = clan_counts.get(clan_tag, 0) + 1

    if not clan_counts:
        return "クランなし"

    max_clan_tag = max(clan_counts.items(), key=lambda x: x[1])
    tag, count = max_clan_tag

    total_enemies = len(enemies)
    if count >= total_enemies / 2:
        return f"{tag} ({count}名)"
    else:
        return f"混成 (最多: {tag} {count}名)"


def download_file(url: str, dest_path: Path) -> bool:
    """URLからファイルをダウンロード"""
    try:
        response = requests.get(url, timeout=30)
        response.raise_for_status()

        with open(dest_path, "wb") as f:
            f.write(response.content)

        logger.info(f"ファイルをダウンロード: {dest_path}")
        return True
    except Exception as e:
        logger.error(f"ファイルダウンロードエラー: {e}")
        return False


def send_followup_message(
    webhook_url: str, content: str, flags: int = 64, fallback_channel_id: str = None
):
    """Discord Webhookでフォローアップメッセージを送信"""
    try:
        response = requests.post(
            webhook_url, json={"content": content, "flags": flags}, timeout=30
        )
        response.raise_for_status()
        logger.info("フォローアップメッセージを送信しました")
        return True
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.warning("フォローアップメッセージのwebhookが期限切れ (15分経過)")
        else:
            logger.error(f"フォローアップメッセージ送信エラー: {e}")
        return False
    except Exception as e:
        logger.error(f"フォローアップメッセージ送信エラー: {e}")
        return False


def get_channel_by_name(guild_id: str, channel_name: str) -> Optional[str]:
    """チャンネル名からチャンネルIDを取得"""
    url = f"{DISCORD_API_BASE}/guilds/{guild_id}/channels"
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}

    try:
        response = requests.get(url, headers=headers, timeout=30)
        response.raise_for_status()
        channels = response.json()

        for channel in channels:
            if channel.get("name") == channel_name and channel.get("type") == 0:
                return channel["id"]

        return None
    except Exception as e:
        logger.error(f"チャンネル取得エラー: {e}")
        return None


def handle(event, context):
    """
    リプレイ解析用Lambda関数

    Args:
        event: {
            'attachment': Discord添付ファイル情報,
            'guild_id': DiscordサーバーID,
            'webhook_url': Discord Webhook URL
        }
        context: Lambda context
    """
    try:
        logger.info(f"リプレイ解析を開始します: event={json.dumps(event, default=str)}")

        attachment = event["attachment"]
        guild_id = event["guild_id"]
        webhook_url = event["webhook_url"]

        filename = attachment["filename"]
        file_url = attachment["url"]
        logger.info(f"ファイル名: {filename}")

        # マップ設定を読み込み
        MAPS, GAME_TYPE_PREFIXES, DEFAULT_MAP_NAME = load_map_config()
        logger.info(
            f"マップ設定を読み込みました: {len(MAPS)}個のマップ, "
            f"{len(GAME_TYPE_PREFIXES)}個のゲームタイプprefix"
        )

        # 一時ディレクトリでファイルを処理
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            replay_path = temp_path / filename

            # ファイルをダウンロード
            if not download_file(file_url, replay_path):
                send_followup_message(
                    webhook_url, "❌ ファイルのダウンロードに失敗しました。"
                )
                return

            # メタデータを解析
            metadata = ReplayMetadataParser.parse_replay_metadata(replay_path)

            if not metadata:
                send_followup_message(
                    webhook_url, "❌ リプレイファイルの解析に失敗しました。"
                )
                return

            # メタデータから情報を抽出
            battle_time = ReplayMetadataParser.extract_battle_time(metadata)
            game_type = ReplayMetadataParser.extract_game_type(metadata)
            players_info = ReplayMetadataParser.extract_players_info(metadata)

            logger.info(
                f"メタデータ解析完了: battle_time={battle_time}, game_type={game_type}"
            )

            # マップIDを取得
            map_id = extract_map_id_from_filename(filename)
            logger.info(f"ファイル名から抽出したマップID: {map_id}")

            if not map_id:
                send_followup_message(
                    webhook_url,
                    "❌ リプレイファイル名からマップ情報を取得できませんでした。",
                )
                return

            # 日本語マップ名を取得
            japanese_map_name = MAPS.get(map_id, DEFAULT_MAP_NAME)

            # ゲームタイプに基づいてprefixを取得
            prefix = ""
            if game_type and game_type in GAME_TYPE_PREFIXES:
                prefix = GAME_TYPE_PREFIXES[game_type]
                logger.info(f"ゲームタイプ: {game_type}, prefix: {prefix}")
            else:
                logger.warning(f"不明なゲームタイプ: {game_type}, prefixなしで続行")

            # チャンネル名を構築
            target_channel_name = f"{prefix}{japanese_map_name}"
            logger.info(
                f"マップID: {map_id} → 日本語名: {japanese_map_name} → "
                f"チャンネル: {target_channel_name}"
            )

            # チャンネルIDを取得
            target_channel_id = get_channel_by_name(guild_id, target_channel_name)
            if not target_channel_id:
                send_followup_message(
                    webhook_url,
                    f"❌ チャンネル「{target_channel_name}」が見つかりませんでした。",
                )
                return

            if not battle_time:
                battle_time = "取得失敗"

            # 対戦クランを決定
            clan_name = get_opponent_clan(players_info)

            # S3にリプレイファイルをアップロード（video-generatorがアクセスできるように）
            import uuid

            temp_id = str(uuid.uuid4())
            s3_key = f"temp-replays/{temp_id}/{filename}"

            with open(replay_path, "rb") as f:
                s3_client.put_object(
                    Bucket=TEMP_BUCKET,
                    Key=s3_key,
                    Body=f.read(),
                    ContentType="application/octet-stream",
                )

            logger.info(f"リプレイファイルをS3にアップロード: s3://{TEMP_BUCKET}/{s3_key}")

            # video-generator Lambda を呼び出し
            video_payload = {
                "replay_s3_key": s3_key,
                "filename": filename,
                "guild_id": guild_id,
                "webhook_url": webhook_url,
                "target_channel_id": target_channel_id,
                "target_channel_name": target_channel_name,
                "battle_time": battle_time,
                "game_type": game_type,
                "players_info": players_info,
                "clan_name": clan_name,
            }

            lambda_client.invoke(
                FunctionName=VIDEO_GENERATOR_FUNCTION_NAME,
                InvocationType="Event",  # 非同期呼び出し
                Payload=json.dumps(video_payload),
            )

            logger.info(
                f"video-generator Lambdaを呼び出しました: {VIDEO_GENERATOR_FUNCTION_NAME}"
            )

    except Exception as e:
        logger.error(f"リプレイ解析エラー: {e}", exc_info=True)
        try:
            send_followup_message(
                event.get("webhook_url"), f"❌ 解析中にエラーが発生しました: {str(e)}"
            )
        except Exception:
            pass
