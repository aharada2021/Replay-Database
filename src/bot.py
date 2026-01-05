import os
import logging
import yaml
from datetime import datetime
from typing import Optional, Dict
from pathlib import Path
import discord
from discord.ext import commands
from dotenv import load_dotenv

from replay_processor import ReplayProcessor

# ログ設定
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# 環境変数の読み込み
load_dotenv()

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN")
GUILD_ID = os.getenv("GUILD_ID")
INPUT_CHANNEL_ID = os.getenv("INPUT_CHANNEL_ID")

if not DISCORD_TOKEN:
    raise ValueError("DISCORD_TOKEN is not set in .env file")
if not INPUT_CHANNEL_ID:
    raise ValueError("INPUT_CHANNEL_ID is not set in .env file")

# Intentsの設定
intents = discord.Intents.default()
intents.message_content = True
intents.guilds = True

# Botの設定
bot = commands.Bot(command_prefix="!", intents=intents)

# マップマッピングの読み込み
MAP_NAMES: Dict[str, str] = {}
DEFAULT_CHANNEL_NAME = "その他のマップ"


def load_map_names():
    """YAMLファイルからマップ名のマッピングを読み込む"""
    global MAP_NAMES, DEFAULT_CHANNEL_NAME

    map_file = Path(__file__).parent / "map_names.yaml"

    try:
        with open(map_file, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
            MAP_NAMES = data.get("maps", {})
            DEFAULT_CHANNEL_NAME = data.get("default_channel", "その他のマップ")
            logger.info(f"マップ名マッピングを読み込みました: {len(MAP_NAMES)}件")
    except FileNotFoundError:
        logger.warning(f"マップ名マッピングファイルが見つかりません: {map_file}")
        logger.warning("デフォルトのマッピングを使用します")
    except Exception as e:
        logger.error(f"マップ名マッピングファイルの読み込みエラー: {e}")


def extract_map_id_from_filename(filename: str) -> Optional[str]:
    """
    WoWSリプレイファイル名からマップIDを抽出する

    ファイル名フォーマット例:
    20260103_232822_PZSD109-Chung-Mu_19_OC_prey.wowsreplay
    20260104_001926_PZSD109-Chung-Mu_16_OC_bees_to_honey.wowsreplay

    Args:
        filename: リプレイファイル名

    Returns:
        マップID (例: "OC_prey", "OC_bees_to_honey") または None
    """
    if not filename.endswith(".wowsreplay"):
        return None

    # ファイル名から拡張子を除去
    name_without_ext = filename.replace(".wowsreplay", "")

    # パターン: 日付_時刻_艦船名_数字_マップID
    # 右から左に見て、最初に数字のみの部分を見つけ、その次からマップID
    parts = name_without_ext.split("_")

    if len(parts) >= 4:
        # 右から左にスキャンして、数字のみの部分を見つける
        for i in range(len(parts) - 1, -1, -1):
            if parts[i].isdigit():
                # 数字の次の要素から最後までがマップID
                if i + 1 < len(parts):
                    map_id = "_".join(parts[i + 1 :])
                    return map_id
                break

    return None


def get_japanese_map_name(map_id: str) -> str:
    """
    マップIDから日本語マップ名を取得

    Args:
        map_id: マップID (例: "19_OC_prey")

    Returns:
        日本語マップ名 (例: "大海原")
    """
    return MAP_NAMES.get(map_id, DEFAULT_CHANNEL_NAME)


def get_opponent_clan(players_info: dict) -> str:
    """
    敵プレイヤーの過半数のクランタグを取得

    Args:
        players_info: プレイヤー情報

    Returns:
        クラン名（過半数のクランタグまたは「混成」「クランなし」など）
    """
    enemies = players_info.get("enemies", [])

    if not enemies:
        return "不明"

    # クランタグを集計（クラン所属者のみ）
    clan_counts = {}
    for player in enemies:
        clan_tag = player.get("clanTag")
        if clan_tag:
            clan_counts[clan_tag] = clan_counts.get(clan_tag, 0) + 1

    if not clan_counts:
        return "クランなし"

    # 最も多いクランタグを取得
    max_clan_tag = max(clan_counts.items(), key=lambda x: x[1])
    tag, count = max_clan_tag

    # 過半数（半数以上）かチェック
    total_enemies = len(enemies)
    if count >= total_enemies / 2:
        return f"{tag} ({count}名)"
    else:
        # 最も多いクランでも過半数に達していない場合
        return f"混成 (最多: {tag} {count}名)"


async def find_map_channel(guild: discord.Guild, channel_name: str) -> Optional[discord.TextChannel]:
    """
    指定された名前のチャンネルを検索

    Args:
        guild: Discordサーバー
        channel_name: チャンネル名

    Returns:
        テキストチャンネル または None
    """
    for channel in guild.text_channels:
        if channel.name == channel_name:
            logger.info(f"マップチャンネルを発見: {channel_name}")
            return channel

    logger.warning(f"マップチャンネルが見つかりません: {channel_name}")
    return None


@bot.event
async def on_ready():
    """Botが起動したときの処理"""
    logger.info(f"{bot.user} としてログインしました")
    logger.info(f"Bot ID: {bot.user.id}")

    # マップ名マッピングを読み込み
    load_map_names()

    logger.info("------")
    logger.info(f"INPUT_CHANNEL_ID: {INPUT_CHANNEL_ID}")
    logger.info("Bot起動完了")


@bot.event
async def on_message(message: discord.Message):
    """メッセージを受信したときの処理"""
    # Bot自身のメッセージは無視
    if message.author.bot:
        return

    # GUILD_IDが設定されている場合、そのサーバーのみ対応
    if GUILD_ID and str(message.guild.id) != GUILD_ID:
        return

    # INPUT_CHANNELでのみ動作
    if str(message.channel.id) != INPUT_CHANNEL_ID:
        await bot.process_commands(message)
        return

    # 添付ファイルがある場合のみ処理
    if not message.attachments:
        await bot.process_commands(message)
        return

    # 各添付ファイルを処理
    for attachment in message.attachments:
        filename = attachment.filename

        # .wowsreplayファイルのみ処理
        if not filename.endswith(".wowsreplay"):
            continue

        logger.info(f"リプレイファイルを検出: {filename}")

        # 処理開始のリアクション
        await message.add_reaction("⏳")

        try:
            # マップIDを抽出
            map_id = extract_map_id_from_filename(filename)

            if not map_id:
                logger.warning(f"マップ情報を抽出できませんでした: {filename}")
                await message.add_reaction("❌")
                await message.reply("リプレイファイル名からマップ情報を取得できませんでした。")
                continue

            # 日本語マップ名を取得
            japanese_map_name = get_japanese_map_name(map_id)
            logger.info(f"マップID: {map_id} -> {japanese_map_name}")

            # マップチャンネルを検索
            target_channel = await find_map_channel(message.guild, japanese_map_name)

            if not target_channel:
                await message.add_reaction("⚠️")
                await message.reply(
                    f"マップ「{japanese_map_name}」に対応するチャンネルが見つかりませんでした。\n"
                    f"チャンネル名: `{japanese_map_name}`"
                )
                continue

            # リプレイファイルを一時保存
            temp_dir = Path(__file__).parent / "temp"
            temp_dir.mkdir(exist_ok=True)

            replay_path = temp_dir / filename
            await attachment.save(replay_path)

            logger.info(f"リプレイファイルを保存: {replay_path}")

            # リプレイファイルを処理（対戦時間を取得、MP4を生成、プレイヤー情報を取得）
            output_dir = temp_dir / "videos"
            battle_time, mp4_path, players_info = ReplayProcessor.process_replay(replay_path, output_dir)

            if not battle_time:
                battle_time = "取得失敗"

            # 敵の過半数クランタグから対戦クランを決定
            clan_name = get_opponent_clan(players_info)
            logger.info(f"対戦クラン: {clan_name}")

            # マップチャンネルに投稿
            embed = discord.Embed(
                title=f"🎮 リプレイ: {japanese_map_name}", color=discord.Color.blue(), timestamp=datetime.utcnow()
            )
            embed.add_field(name="🏴 対戦クラン", value=clan_name, inline=True)
            embed.add_field(name="⏰ 対戦時間", value=battle_time, inline=True)
            embed.add_field(name="📁 ファイル名", value=filename, inline=False)

            # プレイヤー情報を追加
            if players_info:
                # 自分
                if players_info["own"]:
                    own_text = "\n".join(
                        [
                            (
                                f"• [{p['clanTag']}] {p['name']} ({p['shipName']})"
                                if p["clanTag"]
                                else f"• {p['name']} ({p['shipName']})"
                            )
                            for p in players_info["own"]
                        ]
                    )
                    embed.add_field(name="👤 自分", value=own_text, inline=False)

                # 味方
                if players_info["allies"]:
                    allies_list = [
                        (
                            f"• [{p['clanTag']}] {p['name']} ({p['shipName']})"
                            if p["clanTag"]
                            else f"• {p['name']} ({p['shipName']})"
                        )
                        for p in players_info["allies"]
                    ]
                    allies_text = "\n".join(allies_list)
                    # 長すぎる場合は制限
                    if len(allies_text) > 1024:
                        allies_text = "\n".join(allies_list[:15]) + f"\n... 他 {len(allies_list) - 15} 名"
                    embed.add_field(name="🤝 味方", value=allies_text, inline=True)

                # 敵
                if players_info["enemies"]:
                    enemies_list = [
                        (
                            f"• [{p['clanTag']}] {p['name']} ({p['shipName']})"
                            if p["clanTag"]
                            else f"• {p['name']} ({p['shipName']})"
                        )
                        for p in players_info["enemies"]
                    ]
                    enemies_text = "\n".join(enemies_list)
                    # 長すぎる場合は制限
                    if len(enemies_text) > 1024:
                        enemies_text = "\n".join(enemies_list[:15]) + f"\n... 他 {len(enemies_list) - 15} 名"
                    embed.add_field(name="⚔️ 敵", value=enemies_text, inline=True)

            embed.set_footer(
                text=f"アップロード: {message.author.display_name}",
                icon_url=message.author.avatar.url if message.author.avatar else None,
            )

            # ファイルを準備
            files = []

            # MP4動画が生成されている場合は添付
            if mp4_path and mp4_path.exists():
                files.append(discord.File(mp4_path, filename=f"{replay_path.stem}.mp4"))
                logger.info("MP4動画を添付します")
            else:
                logger.warning("MP4動画が生成されていないため、リプレイファイルのみ送信します")
                files.append(discord.File(replay_path))

            # メッセージを送信
            await target_channel.send(embed=embed, files=files)

            # 一時ファイルを削除
            replay_path.unlink(missing_ok=True)
            if mp4_path and mp4_path.exists():
                mp4_path.unlink(missing_ok=True)

            # 成功のリアクション
            await message.remove_reaction("⏳", bot.user)
            await message.add_reaction("✅")

            # 元のメッセージに返信
            await message.reply(
                f"✅ リプレイファイルを {target_channel.mention} に投稿しました！", mention_author=False
            )

            logger.info(f"ファイルを {japanese_map_name} に送信しました: {filename}")

        except discord.Forbidden:
            logger.error("権限エラー: メッセージ送信の権限がありません")
            await message.remove_reaction("⏳", bot.user)
            await message.add_reaction("⚠️")
            await message.reply("エラー: Botにチャンネルへの投稿権限がありません。")
        except Exception as e:
            logger.error(f"エラーが発生しました: {e}", exc_info=True)
            await message.remove_reaction("⏳", bot.user)
            await message.add_reaction("❌")
            await message.reply(f"エラーが発生しました: {str(e)}")

    # コマンドも処理
    await bot.process_commands(message)


@bot.command(name="test")
async def test_command(ctx):
    """テストコマンド"""
    await ctx.send("✅ Bot is working!")


@bot.command(name="info")
async def info_command(ctx):
    """Bot情報を表示"""
    embed = discord.Embed(
        title="WoWS Replay Classification Bot",
        description="World of Warshipsのリプレイファイルをマップ別に自動分類するBot",
        color=discord.Color.blue(),
    )
    embed.add_field(
        name="📝 使い方",
        value=f"<#{INPUT_CHANNEL_ID}> に.wowsreplayファイルを投稿してください。\n対戦クランは敵プレイヤーの過半数クランタグから自動判定されます。",
        inline=False,
    )
    embed.add_field(
        name="⚙️ コマンド",
        value="`!test` - Botの動作確認\n`!info` - このメッセージを表示\n`!reload_maps` - マップマッピングを再読み込み",
        inline=False,
    )
    embed.add_field(name="📊 統計", value=f"マップ登録数: {len(MAP_NAMES)}", inline=False)

    await ctx.send(embed=embed)


@bot.command(name="reload_maps")
@commands.has_permissions(administrator=True)
async def reload_maps_command(ctx):
    """マップマッピングを再読み込み（管理者のみ）"""
    load_map_names()
    await ctx.send(f"✅ マップマッピングを再読み込みしました。登録数: {len(MAP_NAMES)}")


if __name__ == "__main__":
    try:
        bot.run(DISCORD_TOKEN)
    except Exception as e:
        logger.error(f"Botの起動に失敗しました: {e}", exc_info=True)
