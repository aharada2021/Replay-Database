"""
Rust wows-replay-tool subprocess wrapper.

Calls the pre-built wows-replay-tool binary for replay extraction and rendering.
"""

import json
import os
import subprocess
from typing import Optional


# Rust field names (camelCase) → DynamoDB field names
# Differences are mostly in abbreviation casing: damageAp → damageAP
_STATS_FIELD_MAP = {
    "damage": "damage",
    "damageAp": "damageAP",
    "damageSap": "damageSAP",
    "damageHe": "damageHE",
    "damageSapSecondaries": "damageSAPSecondaries",
    "damageHeSecondaries": "damageHESecondaries",
    "damageTorps": "damageTorps",
    "damageDeepWaterTorps": "damageDeepWaterTorps",
    "damageFire": "damageFire",
    "damageFlooding": "damageFlooding",
    "damageOther": "damageOther",
    "receivedDamage": "receivedDamage",
    "receivedDamageAp": "receivedDamageAP",
    "receivedDamageSap": "receivedDamageSAP",
    "receivedDamageHe": "receivedDamageHE",
    "receivedDamageTorps": "receivedDamageTorps",
    "receivedDamageDeepWaterTorps": "receivedDamageDeepWaterTorps",
    "receivedDamageHeSecondaries": "receivedDamageHESecondaries",
    "receivedDamageSapSecondaries": "receivedDamageSAPSecondaries",
    "receivedDamageFire": "receivedDamageFire",
    "receivedDamageFlood": "receivedDamageFlood",
    "hitsAp": "hitsAP",
    "hitsSap": "hitsSAP",
    "hitsHe": "hitsHE",
    "hitsSecondaries": "hitsSecondaries",
    "hitsSecondariesSap": "hitsSecondariesSAP",
    "potentialDamage": "potentialDamage",
    "potentialDamageArt": "potentialDamageArt",
    "potentialDamageTpd": "potentialDamageTpd",
    "spottingDamage": "spottingDamage",
    "kills": "kills",
    "fires": "fires",
    "floods": "floods",
    "citadels": "citadels",
    "crits": "crits",
    "baseXp": "baseXP",
    "lifetimeSec": "lifetimeSec",
    "distance": "distance",
}


def get_binary_path() -> str:
    """Get path to wows-replay-tool binary."""
    return os.environ.get("WOWS_REPLAY_TOOL_PATH", "/opt/bin/wows-replay-tool")


def get_game_data_dir() -> str:
    """Get path to pre-extracted game data directory."""
    return os.environ.get("GAME_DATA_DIR", "/opt/game-data")


def extract_replay(replay_path: str, game_data_dir: Optional[str] = None) -> dict:
    """
    Call wows-replay-tool extract and parse JSON output.

    Args:
        replay_path: Path to .wowsreplay file
        game_data_dir: Path to game data directory (default: GAME_DATA_DIR env)

    Returns:
        Parsed JSON dict from Rust tool

    Raises:
        RuntimeError: If extraction fails
    """
    binary = get_binary_path()
    data_dir = game_data_dir or get_game_data_dir()

    result = subprocess.run(
        [binary, "extract", "--replay", replay_path, "--game-data", data_dir],
        capture_output=True,
        text=True,
        timeout=120,
    )

    if result.returncode != 0:
        stderr = result.stderr.strip()
        raise RuntimeError(f"wows-replay-tool extract failed (rc={result.returncode}): {stderr}")

    return json.loads(result.stdout)


def map_stats_to_dynamodb(rust_stats: dict) -> dict:
    """
    Map Rust stats field names to DynamoDB field names.

    Args:
        rust_stats: Stats dict from Rust JSON output (camelCase)

    Returns:
        Stats dict with DynamoDB field names
    """
    return {_STATS_FIELD_MAP.get(k, k): v for k, v in rust_stats.items() if k in _STATS_FIELD_MAP}


def build_players_info_from_rust(rust_output: dict) -> dict:
    """
    Build players_info dict (own/allies/enemies) from Rust output.

    Args:
        rust_output: Full Rust extraction result

    Returns:
        {"own": [...], "allies": [...], "enemies": [...]}
    """
    players_info = {"own": [], "allies": [], "enemies": []}

    for player in rust_output.get("players", []):
        player_data = {
            "name": player.get("playerName", ""),
            "shipId": player.get("shipId", 0),
            "shipName": player.get("shipName", ""),
            "clanTag": player.get("clanTag", ""),
        }

        relation = player.get("relation", 2)
        if relation == 0:
            players_info["own"].append(player_data)
        elif relation == 1:
            players_info["allies"].append(player_data)
        else:
            players_info["enemies"].append(player_data)

    return players_info


def build_all_players_stats_from_rust(rust_output: dict) -> list:
    """
    Build allPlayersStats array from Rust output for DynamoDB.

    Args:
        rust_output: Full Rust extraction result

    Returns:
        List of player stat dicts sorted by damage descending
    """
    result = []

    for player in rust_output.get("players", []):
        relation = player.get("relation", 2)
        team = "ally" if relation != 2 else "enemy"
        is_own = relation == 0

        # Map stats to DynamoDB format
        stats_data = map_stats_to_dynamodb(player.get("stats", {}))

        # Add player info
        stats_data["playerName"] = player.get("playerName", "")
        stats_data["team"] = team
        stats_data["shipId"] = player.get("shipId", 0)
        stats_data["shipName"] = player.get("shipName", "")
        stats_data["shipClass"] = player.get("shipClass", "")
        stats_data["isOwn"] = is_own

        # Add build info
        build = player.get("build", {})
        captain_skills = build.get("captainSkills", [])
        if captain_skills:
            stats_data["captainSkills"] = captain_skills

        upgrades = build.get("upgrades", [])
        if upgrades:
            stats_data["upgrades"] = upgrades

        result.append(stats_data)

    # Sort by damage descending
    result.sort(key=lambda x: x.get("damage", 0), reverse=True)

    return result


def get_own_player_stats(rust_output: dict) -> Optional[dict]:
    """
    Extract own player's stats from Rust output, mapped to DynamoDB format.

    Args:
        rust_output: Full Rust extraction result

    Returns:
        Own player's stats dict or None
    """
    for player in rust_output.get("players", []):
        if player.get("relation") == 0:
            return map_stats_to_dynamodb(player.get("stats", {}))
    return None
