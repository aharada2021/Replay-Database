"""
動画生成ハンドラー（processor環境）

replay-analyzer Lambdaから呼び出され、
MP4動画を生成してDiscordに投稿する
"""

import os
import json
import logging
import tempfile
from pathlib import Path
import requests
import boto3

from core.replay_processor import ReplayProcessor

# ログ設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

# 環境変数
DISCORD_BOT_TOKEN = os.getenv("DISCORD_BOT_TOKEN")
DISCORD_API_BASE = "https://discord.com/api/v10"
TEMP_BUCKET = os.environ.get("TEMP_BUCKET", "wows-replay-bot-dev-temp")

# AWSクライアント
s3_client = boto3.client("s3")


def send_channel_message(channel_id: str, content: str = None, embed: dict = None, files: list = None) -> bool:
    """Discordチャンネルにメッセージを送信"""
    url = f"{DISCORD_API_BASE}/channels/{channel_id}/messages"
    headers = {"Authorization": f"Bot {DISCORD_BOT_TOKEN}"}

    payload = {}
    if content:
        payload["content"] = content
    if embed:
        payload["embeds"] = [embed]

    try:
        if files:
            # ファイル添付付きの場合
            files_payload = []
            for i, file_path in enumerate(files):
                with open(file_path, "rb") as f:
                    files_payload.append((f"files[{i}]", (Path(file_path).name, f.read())))

            response = requests.post(
                url,
                headers=headers,
                data={"payload_json": json.dumps(payload)},
                files=files_payload,
                timeout=60,
            )
        else:
            # テキストのみ
            headers["Content-Type"] = "application/json"
            response = requests.post(url, headers=headers, json=payload, timeout=30)

        response.raise_for_status()
        logger.info("メッセージを送信しました")
        return True
    except Exception as e:
        logger.error(f"メッセージ送信エラー: {e}")
        return False


def send_followup_message(webhook_url: str, content: str, flags: int = 64, fallback_channel_id: str = None):
    """Discord Webhookでフォローアップメッセージを送信"""
    try:
        response = requests.post(webhook_url, json={"content": content, "flags": flags}, timeout=30)
        response.raise_for_status()
        logger.info("フォローアップメッセージを送信しました")
        return True
    except requests.exceptions.HTTPError as e:
        if e.response.status_code == 404:
            logger.warning("フォローアップメッセージのwebhookが期限切れ (15分経過)")
            # 404の場合、webhookが期限切れなのでfallbackチャンネルに送信
            if fallback_channel_id:
                logger.info(f"代わりにチャンネル {fallback_channel_id} に直接メッセージを送信します")
                return send_channel_message(fallback_channel_id, content)
        else:
            logger.error(f"フォローアップメッセージ送信エラー: {e}")
        return False
    except Exception as e:
        logger.error(f"フォローアップメッセージ送信エラー: {e}")
        return False


def handle(event, context):
    """
    動画生成用Lambda関数

    Args:
        event: {
            'replay_s3_key': S3上のリプレイファイルキー,
            'filename': 元のファイル名,
            'guild_id': DiscordサーバーID,
            'webhook_url': Discord Webhook URL,
            'target_channel_id': 投稿先チャンネルID,
            'target_channel_name': 投稿先チャンネル名,
            'battle_time': 対戦時間,
            'game_type': ゲームタイプ,
            'players_info': プレイヤー情報,
            'clan_name': 対戦クラン名
        }
        context: Lambda context
    """
    try:
        logger.info(f"動画生成を開始します: event={json.dumps(event, default=str)}")

        replay_s3_key = event["replay_s3_key"]
        filename = event["filename"]
        webhook_url = event["webhook_url"]
        target_channel_id = event["target_channel_id"]
        target_channel_name = event["target_channel_name"]
        battle_time = event.get("battle_time", "取得失敗")
        game_type = event.get("game_type")
        players_info = event.get("players_info", {"own": [], "allies": [], "enemies": []})
        clan_name = event.get("clan_name", "不明")

        # 一時ディレクトリでファイルを処理
        with tempfile.TemporaryDirectory() as temp_dir:
            temp_path = Path(temp_dir)
            replay_path = temp_path / filename
            output_dir = temp_path / "videos"
            output_dir.mkdir(parents=True, exist_ok=True)

            # S3からリプレイファイルをダウンロード
            logger.info(f"S3からリプレイファイルをダウンロード: s3://{TEMP_BUCKET}/{replay_s3_key}")
            with open(replay_path, "wb") as f:
                s3_client.download_fileobj(TEMP_BUCKET, replay_s3_key, f)

            # MP4を生成
            mp4_path = output_dir / f"{replay_path.stem}.mp4"
            success = ReplayProcessor.generate_minimap_video(replay_path, mp4_path)

            logger.info(f"MP4生成結果: success={success}, mp4_path={mp4_path}")

            # Embedを作成
            embed = {
                "title": f"リプレイ: {target_channel_name}",
                "color": 3447003,  # Blue
                "fields": [
                    {"name": "対戦クラン", "value": clan_name, "inline": True},
                    {"name": "対戦時間", "value": battle_time, "inline": True},
                ],
            }

            # ゲームタイプを表示
            if game_type:
                embed["fields"].append({"name": "ゲームタイプ", "value": game_type, "inline": True})

            # ファイル名を追加
            embed["fields"].append({"name": "ファイル名", "value": filename, "inline": False})

            # プレイヤー情報を追加
            if players_info:
                if players_info.get("own"):
                    own_text = "\n".join(
                        [
                            (
                                f"[{p['clanTag']}] {p['name']} ({p['shipName']})"
                                if p.get("clanTag")
                                else f"{p['name']} ({p['shipName']})"
                            )
                            for p in players_info["own"]
                        ]
                    )
                    embed["fields"].append({"name": "自分", "value": own_text, "inline": False})

                if players_info.get("allies"):
                    allies_list = [
                        (
                            f"[{p['clanTag']}] {p['name']} ({p['shipName']})"
                            if p.get("clanTag")
                            else f"{p['name']} ({p['shipName']})"
                        )
                        for p in players_info["allies"]
                    ]
                    allies_text = "\n".join(allies_list)
                    if len(allies_text) > 1024:
                        allies_text = "\n".join(allies_list[:15]) + f"\n... 他 {len(allies_list) - 15} 名"
                    embed["fields"].append({"name": "味方", "value": allies_text, "inline": True})

                if players_info.get("enemies"):
                    enemies_list = [
                        (
                            f"[{p['clanTag']}] {p['name']} ({p['shipName']})"
                            if p.get("clanTag")
                            else f"{p['name']} ({p['shipName']})"
                        )
                        for p in players_info["enemies"]
                    ]
                    enemies_text = "\n".join(enemies_list)
                    if len(enemies_text) > 1024:
                        enemies_text = "\n".join(enemies_list[:15]) + f"\n... 他 {len(enemies_list) - 15} 名"
                    embed["fields"].append({"name": "敵", "value": enemies_text, "inline": True})

            # ファイルを準備
            files = []
            if success and mp4_path.exists():
                files.append(str(mp4_path))
            else:
                # MP4生成失敗時はリプレイファイルを添付
                files.append(str(replay_path))

            # チャンネルに投稿
            post_success = send_channel_message(target_channel_id, embed=embed, files=files)

            if post_success:
                send_followup_message(
                    webhook_url,
                    f"リプレイファイルを <#{target_channel_id}> に投稿しました！",
                    fallback_channel_id=target_channel_id,
                )
            else:
                send_followup_message(
                    webhook_url,
                    "メッセージの投稿に失敗しました。",
                    fallback_channel_id=target_channel_id,
                )

            # 一時S3ファイルを削除
            try:
                s3_client.delete_object(Bucket=TEMP_BUCKET, Key=replay_s3_key)
                logger.info(f"一時S3ファイルを削除: {replay_s3_key}")
            except Exception as e:
                logger.warning(f"一時S3ファイルの削除に失敗: {e}")

    except Exception as e:
        logger.error(f"動画生成エラー: {e}", exc_info=True)
        try:
            send_followup_message(
                event.get("webhook_url"),
                f"動画生成中にエラーが発生しました: {str(e)}",
            )
        except Exception:
            pass
