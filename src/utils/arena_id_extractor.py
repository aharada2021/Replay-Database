"""
arenaUniqueIDを抽出するユーティリティモジュール

scripts/extract_arena_ids.pyからロジックを流用し、Lambda関数で使いやすいように関数化
"""

import sys
from pathlib import Path
from typing import Optional

# replays_unpackライブラリのパスを追加
sys.path.insert(0, str(Path(__file__).parent.parent.parent / "replays_unpack_upstream"))

from replay_unpack.replay_reader import ReplayReader  # noqa: E402
from replay_unpack.clients.wows.network.packets import BattleStats  # noqa: E402
from replay_unpack.clients.wows.player import ReplayPlayer as WoWSReplayPlayer  # noqa: E402


class ArenaIDExtractor(WoWSReplayPlayer):
    """arenaUniqueIDを抽出するカスタムReplayPlayer"""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.battle_results = None

    def _process_packet(self, time, packet):
        """BattleStatsパケットをキャプチャ"""
        if isinstance(packet, BattleStats):
            self.battle_results = packet.serverData

        super()._process_packet(time, packet)


def extract_arena_unique_id(replay_path: str) -> Optional[int]:
    """
    リプレイファイルからarenaUniqueIDを抽出

    Args:
        replay_path: リプレイファイルのパス

    Returns:
        arenaUniqueID (int) または None（抽出失敗時）

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

        # arenaUniqueID抽出プレイヤーを作成
        extractor = ArenaIDExtractor(version)

        # リプレイを再生
        extractor.play(replay.decrypted_data, strict_mode=False)

        # arenaUniqueIDを返す
        if extractor.battle_results:
            return extractor.battle_results.get("arenaUniqueID")

        return None

    except Exception as e:
        raise Exception(f"arenaUniqueID extraction failed: {e}")
