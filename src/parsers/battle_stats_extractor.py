"""
BattleStatsパケットからバトル結果を抽出するユーティリティモジュール

scripts/extract_battle_result.pyからロジックを流用し、Lambda関数で使いやすいように関数化
"""

import os
import sys
from pathlib import Path
from typing import Optional, Dict, Any

# extractor専用イメージではreplays_unpack_upstreamのみがインストールされる
# replays_unpackライブラリのパスを追加
task_root = os.environ.get("LAMBDA_TASK_ROOT", "")
if task_root:
    # Lambda環境: /var/task/replays_unpack_upstream
    sys.path.insert(0, str(Path(task_root) / "replays_unpack_upstream"))
else:
    # ローカル開発環境: プロジェクトルートからの相対パス
    sys.path.insert(0, str(Path(__file__).parent.parent.parent / "replays_unpack_upstream"))

from replay_unpack.replay_reader import ReplayReader  # noqa: E402
from replay_unpack.clients.wows.player import ReplayPlayer as WoWSReplayPlayer  # noqa: E402
from replay_unpack.clients.wows.network.packets import BattleStats  # noqa: E402


class BattleResultExtractor(WoWSReplayPlayer):
    """バトル結果を抽出するカスタムReplayPlayer"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.battle_results = None

    def _process_packet(self, time, packet):
        """パケットを処理（BattleStatsパケットをキャプチャ）"""
        if isinstance(packet, BattleStats):
            self.battle_results = packet.serverData

        # 親クラスの処理を呼び出す
        super()._process_packet(time, packet)


def extract_battle_stats(replay_path: str) -> Optional[Dict[str, Any]]:
    """
    リプレイファイルからBattleStatsパケットを抽出

    Args:
        replay_path: リプレイファイルのパス

    Returns:
        BattleStatsパケットのserverData (dict) または None（抽出失敗時）

    Raises:
        Exception: ファイル読み込みエラーなど
    """
    try:
        # リプレイファイルを読み込み
        reader = ReplayReader(str(replay_path))
        replay = reader.get_replay_data()

        # メタデータ
        metadata = replay.engine_data

        # バージョン
        version = metadata.get("clientVersionFromXml", "").replace(" ", "").split(",")

        # バトル結果抽出プレイヤーを作成
        extractor = BattleResultExtractor(version)

        # リプレイを再生
        extractor.play(replay.decrypted_data, strict_mode=False)

        # バトル結果を返す
        return extractor.battle_results

    except Exception as e:
        raise Exception(f"BattleStats extraction failed: {e}")


def get_win_loss_clan_battle(battle_results: Dict[str, Any]) -> str:
    """
    Clan Battleの勝敗を判定

    経験値から勝敗を判定:
    - 300,000 (実際の30,000 × 10) = 勝利
    - 150,000 (実際の15,000 × 10) = 敗北

    Args:
        battle_results: BattleStatsパケットのserverData

    Returns:
        "win", "loss", "draw", または "unknown"
    """
    if not battle_results:
        return "unknown"

    private_data = battle_results.get("privateDataList", [])

    # privateDataList[7]が経験値の配列
    if len(private_data) > 7 and isinstance(private_data[7], list) and len(private_data[7]) > 0:
        exp = private_data[7][0]  # 実際の値 × 10で記録されている

        if exp == 300000:  # 30,000 exp - 勝利
            return "win"
        elif exp == 150000:  # 15,000 exp - 敗北
            return "loss"

    return "unknown"


def get_experience_earned(battle_results: Dict[str, Any]) -> Optional[int]:
    """
    獲得経験値を取得（実際の値、10倍されていない値）

    Args:
        battle_results: BattleStatsパケットのserverData

    Returns:
        獲得経験値 (int) または None
    """
    if not battle_results:
        return None

    private_data = battle_results.get("privateDataList", [])

    if len(private_data) > 7 and isinstance(private_data[7], list) and len(private_data[7]) > 0:
        exp_raw = private_data[7][0]  # 10倍された値
        return exp_raw // 10  # 実際の値に戻す

    return None


def get_arena_unique_id(battle_results: Dict[str, Any]) -> Optional[int]:
    """
    arenaUniqueIDを取得

    Args:
        battle_results: BattleStatsパケットのserverData

    Returns:
        arenaUniqueID (int) または None
    """
    if not battle_results:
        return None

    return battle_results.get("arenaUniqueID")
