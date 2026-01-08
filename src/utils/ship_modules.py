"""
艦艇モジュールユーティリティ

リプレイデータから艦艇のモジュール構成（船体、主砲、魚雷等）と
アップグレード情報を抽出する機能を提供
"""

from typing import Dict, List, Any
import struct


# 艦艇コンポーネントの表示優先度（重要度順）
COMPONENT_PRIORITY = [
    "hull",  # 船体
    "artillery",  # 主砲
    "torpedoes",  # 魚雷
    "fireControl",  # 射撃管制装置
    "engine",  # エンジン
    "atba",  # 副砲
    "airDefense",  # 対空兵装
    "finders",  # 探知機
    "directors",  # 測距儀
    "depthCharges",  # 爆雷
    "radars",  # レーダー
]

# コンポーネント名の日本語マッピング
COMPONENT_NAMES_JA = {
    "hull": "船体",
    "artillery": "主砲",
    "torpedoes": "魚雷",
    "fireControl": "射撃管制",
    "engine": "エンジン",
    "atba": "副砲",
    "airDefense": "対空",
    "finders": "探知機",
    "directors": "測距儀",
    "depthCharges": "爆雷",
    "radars": "レーダー",
    "abilities": "艦艇特性",
}

# デフォルト値を示すサフィックス（装備なしまたは固定）
DEFAULT_SUFFIXES = [
    "Default",
    "TypeDefault",
]


def is_default_component(value: str) -> bool:
    """
    コンポーネントがデフォルト（未装備または固定）かどうかを判定

    Args:
        value: コンポーネント値（例: "A_Hull", "TorpedoesDefault"）

    Returns:
        デフォルト値の場合True
    """
    if not value:
        return True
    for suffix in DEFAULT_SUFFIXES:
        if value.endswith(suffix):
            return True
    return False


def format_component_value(value: str) -> str:
    """
    コンポーネント値を読みやすい形式に変換

    Args:
        value: コンポーネント値（例: "A_Hull", "AB1_Artillery"）

    Returns:
        フォーマット済み文字列（例: "Hull A", "Artillery AB1"）
    """
    if not value or is_default_component(value):
        return ""

    # "A_Hull" -> "A", "AB1_Artillery" -> "AB1" のパターンを処理
    parts = value.split("_")
    if len(parts) >= 2:
        prefix = parts[0]
        # コンポーネント名を除去してバリアント情報のみ返す
        return prefix

    return value


def extract_ship_components(player_data: Dict[str, Any]) -> Dict[str, str]:
    """
    プレイヤーデータから艦艇コンポーネント情報を抽出

    Args:
        player_data: hidden['players'][player_id]のデータ

    Returns:
        {component_type: variant} のマッピング（デフォルト値は除外）
    """
    ship_components = player_data.get("shipComponents", {})
    result = {}

    for component in COMPONENT_PRIORITY:
        value = ship_components.get(component, "")
        if value and not is_default_component(value):
            result[component] = format_component_value(value)

    return result


def get_ship_modules_display(player_data: Dict[str, Any], language: str = "en") -> List[str]:
    """
    表示用の艦艇モジュールリストを取得

    Args:
        player_data: hidden['players'][player_id]のデータ
        language: 言語コード（"en" または "ja"）

    Returns:
        表示用文字列のリスト（例: ["Hull A", "Artillery B", "Engine A"]）
    """
    components = extract_ship_components(player_data)
    result = []

    for component in COMPONENT_PRIORITY:
        if component in components:
            variant = components[component]
            if language == "ja" and component in COMPONENT_NAMES_JA:
                result.append(f"{COMPONENT_NAMES_JA[component]} {variant}")
            else:
                # 英語の場合はコンポーネント名をキャピタライズ
                component_name = component.replace("_", " ").title()
                result.append(f"{component_name} {variant}")

    return result


def map_player_to_modules(
    replay_hidden_data: Dict[str, Any],
) -> Dict[str, Dict[str, Any]]:
    """
    プレイヤー名から艦艇モジュール情報へのマッピングを生成

    Args:
        replay_hidden_data: ReplayParserの hidden セクションデータ

    Returns:
        {player_name: {"components": {...}, "abilities": [...]}}
    """
    result = {}
    players_data = replay_hidden_data.get("players", {})

    for player_id, player_info in players_data.items():
        if not isinstance(player_info, dict):
            continue

        player_name = player_info.get("name", "")
        if not player_name:
            continue

        components = extract_ship_components(player_info)

        # 艦艇特性（abilities）も抽出
        ship_components = player_info.get("shipComponents", {})
        abilities_value = ship_components.get("abilities", "")

        result[player_name] = {
            "components": components,
            "abilities": abilities_value if not is_default_component(abilities_value) else None,
        }

    return result


def decode_ship_config_dump(config_dump: bytes) -> Dict[str, Any]:
    """
    shipConfigDumpのバイナリデータをデコード

    注意: このデータには近代化改修（アップグレード）のIDが含まれているが、
    ゲームデータファイルがないとIDから名前への変換ができない。

    Args:
        config_dump: shipConfigDumpのバイナリデータ

    Returns:
        デコードされた構造（IDのみ、名前変換なし）
    """
    if not config_dump or len(config_dump) < 16:
        return {}

    # 基本構造
    # [0:4]   - バージョン (1)
    # [4:8]   - 艦艇パラメータID
    # [8:12]  - モジュール数?
    # [12:16] - フラグ/カウント
    # [16:]   - モジュールID配列（32bit整数）

    result = {
        "version": struct.unpack("<I", config_dump[0:4])[0],
        "shipParamsId": struct.unpack("<I", config_dump[4:8])[0],
        "moduleCount": struct.unpack("<I", config_dump[8:12])[0],
        "flag": struct.unpack("<I", config_dump[12:16])[0],
        "moduleIds": [],
    }

    # モジュールIDを抽出
    offset = 16
    while offset + 4 <= len(config_dump):
        module_id = struct.unpack("<I", config_dump[offset : offset + 4])[0]
        if module_id != 0:
            result["moduleIds"].append(module_id)
        offset += 4

    return result


def get_upgrade_ids_from_config_dump(config_dump: bytes) -> List[int]:
    """
    shipConfigDumpから近代化改修（アップグレード）のIDを抽出

    Args:
        config_dump: shipConfigDumpのバイナリデータ

    Returns:
        アップグレードID（ゲームデータがないと名前に変換できない）
    """
    decoded = decode_ship_config_dump(config_dump)
    return decoded.get("moduleIds", [])


# 既知のアップグレードIDマッピング（部分的、ゲームバージョンで変動）
# TODO: ゲームデータから自動生成する仕組みが必要
KNOWN_UPGRADE_IDS = {
    # スロット1
    # スロット2
    # ...
    # 注: アップグレードIDはゲームバージョンごとに変動するため、
    # 静的マッピングは信頼性が低い
}
