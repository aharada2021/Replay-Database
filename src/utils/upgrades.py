"""
アップグレード（近代化改修）ユーティリティ

リプレイデータからアップグレード情報を抽出し、
人間が読める名前に変換する機能を提供
"""

import json
import os
import struct
from io import BytesIO
from functools import lru_cache
from typing import Dict, List, Optional, Any


# PCMコード → 日本語名のマッピング
# スロット1-6の標準アップグレード + 特殊アップグレード
UPGRADE_NAMES_JA: Dict[str, str] = {
    # スロット1 (Tier I+)
    "PCM001": "主砲改良1",
    "PCM002": "副兵装改良1",
    "PCM003": "航空機改良1",
    "PCM004": "対空兵装改良1",
    "PCM005": "副砲改良1",
    "PCM030": "主兵装改良1",
    "PCM031": "補助兵装改良1",
    "PCM034": "照準システム改良0",
    "PCM084": "ソナー改良1",
    # スロット2 (Tier III+)
    "PCM020": "ダメージコントロールシステム改良1",
    "PCM021": "推進システム改良1",
    "PCM022": "操舵システム改良1",
    "PCM068": "航空機エンジン改良1",
    "PCM069": "機関室防護",
    "PCM085": "ソナー改良2",
    "PCM100": "ダメコンシステム改良3",
    # スロット3 (Tier V+)
    "PCM006": "主砲改良2",
    "PCM007": "魚雷発射管改良1",
    "PCM008": "射撃システム改良1",
    "PCM012": "副砲改良2",
    "PCM018": "対空砲改良1",
    "PCM028": "射撃管制室改良1",
    "PCM033": "照準システム改良1",
    "PCM066": "雷撃機改良1",
    "PCM067": "攻撃機改良1",
    "PCM070": "魚雷発射管改良1",
    "PCM071": "航空魚雷改良1",
    "PCM082": "潜航容量改良1",
    "PCM092": "スキップボマー改良1",
    # スロット4 (Tier VI+)
    "PCM023": "ダメージコントロールシステム改良2",
    "PCM024": "推進システム改良1",
    "PCM025": "操舵システム改良1",
    "PCM063": "攻撃機改良2",
    "PCM064": "雷撃機改良2",
    "PCM065": "爆撃機改良1",
    "PCM081": "スキップボマー改良2",
    "PCM087": "航空攻撃改良1",
    "PCM089": "爆雷改良1",
    "PCM090": "潜水艦操舵システム",
    "PCM093": "航空機改良3",
    # スロット5 (Tier VIII+)
    "PCM009": "飛行制御改良1",
    "PCM026": "魚雷警戒システム",
    "PCM027": "隠蔽システム改良1",
    "PCM035": "操舵システム改良2",
    "PCM072": "艦艇消耗品改良1",
    "PCM073": "航空隊消耗品改良1",
    "PCM101": "魚雷発射管改良3",
    "PCM102": "強化隔壁",
    # スロット6 (Tier IX+)
    "PCM010": "戦闘機改良1",
    "PCM011": "対空兵装改良2",
    "PCM013": "主砲改良3",
    "PCM014": "魚雷発射管改良2",
    "PCM015": "射撃管制システム改良2",
    "PCM016": "飛行制御改良2",
    "PCM017": "航空機改良2",
    "PCM019": "副砲改良3",
    "PCM029": "射撃管制室改良2",
    "PCM074": "補助兵装改良2",
    "PCM086": "潜航容量改良2",
    # 特殊アップグレード（消耗品系）
    "PCM036": "エンジンブースト改良1",
    "PCM037": "発煙装置改良1",
    "PCM038": "水上機改良1",
    "PCM039": "応急工作班改良1",
    "PCM040": "対空防御砲火改良1",
    "PCM041": "水中聴音改良1",
    "PCM042": "レーダー改良1",
    "PCM043": "主砲装填ブースター改良1",
    "PCM044": "主砲装填ブースター改良2",
    "PCM045": "主砲装填ブースター改良3",
    "PCM046": "主砲射撃装置改良1",
    "PCM047": "ダメコン改良特殊1",
    "PCM048": "照準改良特殊1",
    "PCM049": "ダメコン改良特殊2",
    "PCM050": "主砲改良特殊1",
    "PCM051": "隠蔽改良特殊1",
    "PCM052": "推進改良特殊1",
    "PCM053": "消耗品改良特殊1",
    "PCM054": "主砲射撃改良1",
    "PCM055": "主砲射撃改良2",
    "PCM056": "魚雷改良特殊1",
    "PCM057": "魚雷改良特殊2",
    "PCM058": "隠蔽改良特殊2",
    "PCM059": "煙幕改良特殊1",
    "PCM060": "装填改良特殊1",
    "PCM061": "爆撃機改良特殊1",
    "PCM062": "航空機速度改良1",
    "PCM075": "魚雷改良特殊3",
    "PCM076": "隠蔽改良特殊3",
    "PCM077": "煙幕改良特殊2",
    "PCM078": "主砲改良特殊2",
    "PCM079": "推進・隠蔽改良1",
    "PCM080": "主砲射撃改良3",
    "PCM083": "聴音改良特殊1",
    "PCM088": "爆雷改良特殊1",
    "PCM091": "潜水艦操舵改良1",
    "PCM094": "特殊改良1",
    "PCM095": "煙幕改良特殊3",
    "PCM096": "主砲改良特殊3",
    "PCM097": "雷撃機改良特殊1",
    "PCM098": "駆逐艦改良特殊1",
    "PCM099": "爆雷改良特殊2",
    "PCM103": "潜水艦改良特殊1",
    "PCM104": "潜水艦探知改良1",
    "PCM105": "対空・爆雷改良1",
    "PCM106": "主砲改良特殊4",
    "PCM107": "装填改良特殊2",
    "PCM108": "魚雷改良特殊4",
    "PCM109": "火災改良特殊1",
    "PCM110": "ミサイル改良1",
    "PCM111": "船体改良特殊1",
    "PCM112": "速度改良特殊1",
    "PCM113": "消耗品改良特殊2",
    "PCM114": "速度改良特殊2",
    "PCM115": "隠蔽改良特殊4",
    "PCM116": "操舵改良特殊1",
    "PCM117": "装填改良特殊3",
    "PCM118": "魚雷改良特殊5",
    # その他
    "PCM032": "特殊改良（空）",
}

# PCMコード → 英語名のマッピング
UPGRADE_NAMES_EN: Dict[str, str] = {
    # Slot 1
    "PCM001": "Main Armaments Mod 1",
    "PCM002": "Auxiliary Armaments Mod 1",
    "PCM003": "Air Groups Mod 1",
    "PCM004": "AA Guns Mod 1",
    "PCM005": "Secondary Battery Mod 1",
    "PCM030": "Main Armaments Mod 1",
    "PCM031": "Auxiliary Armaments Mod 1",
    "PCM034": "Aiming Systems Mod 0",
    "PCM084": "Sonar Mod 1",
    # Slot 2
    "PCM020": "Damage Control System Mod 1",
    "PCM021": "Propulsion Mod 1",
    "PCM022": "Steering Gears Mod 1",
    "PCM068": "Aircraft Engines Mod 1",
    "PCM069": "Engine Room Protection",
    "PCM085": "Sonar Mod 2",
    "PCM100": "Damage Control System Mod 3",
    # Slot 3
    "PCM006": "Main Battery Mod 2",
    "PCM007": "Torpedo Tubes Mod 1",
    "PCM008": "Gun Fire Control System Mod 1",
    "PCM012": "Secondary Battery Mod 2",
    "PCM018": "AA Guns Mod 2",
    "PCM028": "Artillery Plotting Room Mod 1",
    "PCM033": "Aiming Systems Mod 1",
    "PCM066": "Torpedo Bombers Mod 1",
    "PCM067": "Attack Aircraft Mod 1",
    "PCM070": "Torpedo Tubes Mod 1",
    "PCM071": "Aerial Torpedoes Mod 1",
    "PCM082": "Dive Capacity Mod 1",
    "PCM092": "Skip Bomber Mod 1",
    # Slot 4
    "PCM023": "Damage Control System Mod 2",
    "PCM024": "Propulsion Mod 1",
    "PCM025": "Steering Gears Mod 1",
    "PCM063": "Attack Aircraft Mod 2",
    "PCM064": "Torpedo Bombers Mod 2",
    "PCM065": "Dive Bombers Mod 1",
    "PCM081": "Skip Bomber Mod 2",
    "PCM087": "Airstrike Mod 1",
    "PCM089": "Depth Charges Mod 1",
    "PCM090": "Submarine Steering Gears",
    "PCM093": "Air Groups Mod 3",
    # Slot 5
    "PCM009": "Flight Control Mod 1",
    "PCM026": "Torpedo Lookout System",
    "PCM027": "Concealment System Mod 1",
    "PCM035": "Steering Gears Mod 2",
    "PCM072": "Ship Consumables Mod 1",
    "PCM073": "Squadron Consumables Mod 1",
    "PCM101": "Torpedo Tubes Mod 3",
    "PCM102": "Reinforced Bulkheads",
    # Slot 6
    "PCM010": "Fighter Mod 1",
    "PCM011": "AA Guns Mod 3",
    "PCM013": "Main Battery Mod 3",
    "PCM014": "Torpedo Tubes Mod 2",
    "PCM015": "Gun Fire Control System Mod 2",
    "PCM016": "Flight Control Mod 2",
    "PCM017": "Air Groups Mod 2",
    "PCM019": "Secondary Battery Mod 3",
    "PCM029": "Artillery Plotting Room Mod 2",
    "PCM074": "Auxiliary Armaments Mod 2",
    "PCM086": "Dive Capacity Mod 2",
    # Special
    "PCM036": "Engine Boost Mod 1",
    "PCM037": "Smoke Generator Mod 1",
    "PCM038": "Spotting Aircraft Mod 1",
    "PCM039": "Damage Control Party Mod 1",
    "PCM040": "Defensive AA Fire Mod 1",
    "PCM041": "Hydroacoustic Search Mod 1",
    "PCM042": "Surveillance Radar Mod 1",
    "PCM043": "Main Battery Reload Booster Mod 1",
}

# スロット番号の定義（PCMコードからスロットを推測）
UPGRADE_SLOTS: Dict[str, int] = {
    # Slot 1
    "PCM001": 1,
    "PCM002": 1,
    "PCM003": 1,
    "PCM004": 1,
    "PCM005": 1,
    "PCM030": 1,
    "PCM031": 1,
    "PCM034": 1,
    "PCM084": 1,
    # Slot 2
    "PCM020": 2,
    "PCM021": 2,
    "PCM022": 2,
    "PCM068": 2,
    "PCM069": 2,
    "PCM085": 2,
    "PCM100": 2,
    # Slot 3
    "PCM006": 3,
    "PCM007": 3,
    "PCM008": 3,
    "PCM012": 3,
    "PCM018": 3,
    "PCM028": 3,
    "PCM033": 3,
    "PCM066": 3,
    "PCM067": 3,
    "PCM070": 3,
    "PCM071": 3,
    "PCM082": 3,
    "PCM092": 3,
    # Slot 4
    "PCM023": 4,
    "PCM024": 4,
    "PCM025": 4,
    "PCM063": 4,
    "PCM064": 4,
    "PCM065": 4,
    "PCM081": 4,
    "PCM087": 4,
    "PCM089": 4,
    "PCM090": 4,
    "PCM093": 4,
    # Slot 5
    "PCM009": 5,
    "PCM026": 5,
    "PCM027": 5,
    "PCM035": 5,
    "PCM072": 5,
    "PCM073": 5,
    "PCM101": 5,
    "PCM102": 5,
    # Slot 6
    "PCM010": 6,
    "PCM011": 6,
    "PCM013": 6,
    "PCM014": 6,
    "PCM015": 6,
    "PCM016": 6,
    "PCM017": 6,
    "PCM019": 6,
    "PCM029": 6,
    "PCM074": 6,
    "PCM086": 6,
}


def decode_ship_config_dump(config_dump: bytes) -> Dict[str, Any]:
    """
    shipConfigDumpをデコードしてアップグレードID等を取得

    Args:
        config_dump: shipConfigDumpのバイナリデータ

    Returns:
        デコードされたデータ（modernization, signals等を含む）
    """
    if not config_dump or len(config_dump) < 20:
        return {"modernization": [], "signals": []}

    try:
        with BytesIO(config_dump) as bio:
            # 構造:
            # [0:4]   - unknown_1
            # [4:8]   - ship_params_id
            # [8:12]  - unknown_2
            # [12:16] - units count (d)
            # [16:16+d*4] - units array
            # [next 4] - applied external config (>= 13.2.0)
            # [next 4] - modernization count (e)
            # [next e*4] - modernization IDs
            # [next 4] - signals count (f)
            # [next f*4] - signal IDs

            struct.unpack("<L", bio.read(4))  # unknown_1
            struct.unpack("<L", bio.read(4))  # ship_params_id
            struct.unpack("<L", bio.read(4))  # unknown_2

            (d,) = struct.unpack("<L", bio.read(4))  # units count
            bio.read(4 * d)  # skip units

            bio.read(4)  # applied external config (>= 13.2.0)

            (e,) = struct.unpack("<L", bio.read(4))  # modernization count
            modern = struct.unpack("<" + "L" * e, bio.read(e * 4)) if e > 0 else ()

            (f,) = struct.unpack("<L", bio.read(4))  # signals count
            signals = struct.unpack("<" + "L" * f, bio.read(f * 4)) if f > 0 else ()

            return {
                "modernization": list(modern),
                "signals": list(signals),
            }
    except (struct.error, ValueError) as e:
        print(f"Warning: Failed to decode shipConfigDump: {e}")
        return {"modernization": [], "signals": []}


@lru_cache(maxsize=1)
def _load_modernizations() -> Dict[str, Any]:
    """近代化改修データを読み込み"""
    # Lambda環境とローカル環境の両方に対応
    task_root = os.environ.get("LAMBDA_TASK_ROOT", "")
    if task_root:
        json_path = os.path.join(task_root, "utils", "modernizations.json")
    else:
        json_path = os.path.join(os.path.dirname(__file__), "modernizations.json")

    try:
        with open(json_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"modernizations": {}}


def get_upgrade_name(upgrade_id: int, language: str = "ja") -> Optional[str]:
    """
    アップグレードIDから名前を取得

    Args:
        upgrade_id: アップグレードID（数値）
        language: 言語コード（"ja" または "en"）

    Returns:
        アップグレード名、見つからない場合はNone
    """
    if not upgrade_id:
        return None

    # IDからPCMコードを取得
    modernizations = _load_modernizations()
    mod_data = modernizations.get("modernizations", {}).get(str(upgrade_id))

    if not mod_data:
        return None

    pcm_code = mod_data.get("index", "")

    # PCMコードから名前を取得
    if language == "ja":
        return UPGRADE_NAMES_JA.get(pcm_code, pcm_code)
    else:
        return UPGRADE_NAMES_EN.get(pcm_code, pcm_code)


def get_upgrade_pcm_code(upgrade_id: int) -> Optional[str]:
    """
    アップグレードIDからPCMコードを取得

    Args:
        upgrade_id: アップグレードID（数値）

    Returns:
        PCMコード（例: "PCM001"）、見つからない場合はNone
    """
    if not upgrade_id:
        return None

    modernizations = _load_modernizations()
    mod_data = modernizations.get("modernizations", {}).get(str(upgrade_id))

    if not mod_data:
        return None

    return mod_data.get("index")


def extract_player_upgrades(hidden_data: Dict[str, Any], language: str = "ja") -> Dict[str, List[str]]:
    """
    hiddenデータからプレイヤーのアップグレード情報を抽出

    Args:
        hidden_data: リプレイのhiddenセクションデータ
        language: 言語コード（"ja" または "en"）

    Returns:
        {player_name: [upgrade_name, ...]} のマッピング
    """
    result = {}
    players_data = hidden_data.get("players", {})

    for player_id, player_info in players_data.items():
        if not isinstance(player_info, dict):
            continue

        player_name = player_info.get("name", "")
        if not player_name:
            continue

        # shipConfigDumpからアップグレードIDを取得
        ship_config_dump = player_info.get("shipConfigDump")
        if not ship_config_dump:
            continue

        # shipConfigDumpをデコード
        decoded = decode_ship_config_dump(ship_config_dump)
        modernization = decoded.get("modernization", [])

        if modernization:
            upgrades = []
            for upgrade_id in modernization:
                if upgrade_id:
                    name = get_upgrade_name(upgrade_id, language)
                    if name:
                        upgrades.append(name)

            if upgrades:
                result[player_name] = upgrades

    return result


def map_player_to_upgrades(hidden_data: Dict[str, Any], language: str = "ja") -> Dict[str, List[str]]:
    """
    プレイヤー名からアップグレードリストへのマッピングを生成

    Args:
        hidden_data: リプレイのhiddenセクションデータ
        language: 言語コード（"ja" または "en"）

    Returns:
        {player_name: [upgrade_name, ...]} のマッピング
    """
    return extract_player_upgrades(hidden_data, language)
