"""
艦長スキルユーティリティ

内部スキル名から人間が読める表示名へのマッピングと、
リプレイデータからスキル情報を抽出する機能を提供
"""

import json
import os
from pathlib import Path
from typing import Dict, List, Optional, Any

# 艦艇データのキャッシュ（遅延ロード）
_ship_data_cache: Optional[Dict[str, Dict]] = None


def _get_ship_data() -> Dict[str, Dict]:
    """
    ships.jsonから艦艇データをロード（キャッシュ付き）

    Returns:
        {shipParamsId: {"species": "Destroyer", "name": "...", ...}}
    """
    global _ship_data_cache

    if _ship_data_cache is not None:
        return _ship_data_cache

    # ships.jsonのパスを特定
    # Lambda環境: /var/task/minimap_renderer/src/renderer/versions/14_11_0/resources/ships.json
    # ローカル: プロジェクトルートからの相対パス
    task_root = os.environ.get("LAMBDA_TASK_ROOT", "")
    if task_root:
        ships_json_path = (
            Path(task_root)
            / "minimap_renderer"
            / "src"
            / "renderer"
            / "versions"
            / "14_11_0"
            / "resources"
            / "ships.json"
        )
    else:
        # ローカル開発環境
        ships_json_path = (
            Path(__file__).parent.parent.parent
            / "minimap_renderer"
            / "src"
            / "renderer"
            / "versions"
            / "14_11_0"
            / "resources"
            / "ships.json"
        )

    try:
        with open(ships_json_path, "r", encoding="utf-8") as f:
            _ship_data_cache = json.load(f)
            print(f"Loaded ships.json: {len(_ship_data_cache)} ships")
    except FileNotFoundError:
        print(f"Warning: ships.json not found at {ships_json_path}")
        _ship_data_cache = {}
    except Exception as e:
        print(f"Warning: Failed to load ships.json: {e}")
        _ship_data_cache = {}

    return _ship_data_cache


def get_ship_class_from_params_id(ship_params_id: int) -> Optional[str]:
    """
    shipParamsIdから艦種（species）を取得

    Args:
        ship_params_id: 艦艇パラメータID

    Returns:
        艦種名（"Destroyer", "Cruiser", "Battleship", "AirCarrier", "Submarine"）
        または None（見つからない場合）
    """
    ship_data = _get_ship_data()
    ship_info = ship_data.get(str(ship_params_id))
    if ship_info:
        return ship_info.get("species")
    return None


# 内部スキル名 → 表示名（英語）のマッピング
# WoWS 14.x準拠
SKILL_INTERNAL_TO_DISPLAY = {
    # Tier 1 Skills
    "GmReloadAaDamageConstant": "Gun Feeder",
    "DefenceCritFireFlooding": "Basics of Survivability",
    "GmTurn": "Grease the Gears",
    "TorpedoReload": "Fill the Tubes",
    "ConsumablesCrashcrewRegencrewReload": "Emergency Repair Specialist",
    "ConsumablesDuration": "Consumable Enhancements",
    "DetectionTorpedoRange": "Vigilance",
    "HeFireProbability": "Demolition Expert",
    "GmRangeAaDamageBubbles": "Main Battery and AA Specialist",
    "PlanesDefenseDamageConstant": "Air Supremacy",
    "PlanesForsageDuration": "Engine Tuning",
    "DetectionVisibilityRange": "Concealment Expert",
    "ConsumablesReload": "Improved Engine Boost",
    "DefenceFireProbability": "Fire Prevention Expert",
    "PlanesAimingBoost": "Aiming Facility Maintenance",
    "PlanesSpeed": "Swift Fish",
    "ConsumablesAdditional": "Superintendent",
    "DefenseCritProbability": "Preventive Maintenance",
    "DetectionAlert": "Priority Target",
    "Maneuverability": "Last Stand",
    "GmShellReload": "Expert Loader",
    "PlanesConsumablesCallfightersUpgrade": "Search and Destroy",
    "ArmamentReloadAaDamage": "Adrenaline Rush",
    "TorpedoSpeed": "Swift Fish",
    "DefenseHp": "Survivability Expert",
    "AtbaAccuracy": "Long-Range Secondary Battery Shells",
    "AaPrioritysectorDamageConstant": "Focus Fire Training",
    "DetectionAiming": "Incoming Fire Alert",
    "PlanesReload": "Improved Engine Boost",
    "TorpedoDamage": "Torpedo Armament Expertise",
    "ConsumablesFighterAdditional": "Direction Center for Fighters",
    "PlanesConsumablesSpeedboosterReload": "Enhanced Aircraft Armor",
    "HePenetration": "Inertia Fuse for HE Shells",
    "DetectionDirection": "Radio Location",
    "AaDamageConstantBubbles": "AA Defense and ASW Expert",
    "AaDamageConstantBubblesCv": "Enhanced Reactions",
    "ApDamageBb": "Close Quarters Combat",
    "ApDamageCa": "Heavy AP Shells",
    "ApDamageDd": "Main Battery and AA Expert",
    "AtbaRange": "Manual Secondary Battery Aiming",
    "AtbaUpgrade": "Improved Secondary Battery Aiming",
    "ConsumablesCrashcrewRegencrewUpgrade": "Improved Repair Party Readiness",
    "ConsumablesSpotterUpgrade": "Enhanced Fighter Consumable",
    "DefenceUw": "Emergency Repair Expert",
    "DetectionVisibilityCrashcrew": "Swift in Silence",
    "HeFireProbabilityCv": "Pyrotechnician",
    "HeSapDamage": "Super-Heavy AP Shells",
    "PlanesApDamage": "Armored Deck",
    "PlanesConsumablesCallfightersAdditional": "Patrol Group Leader",
    "PlanesConsumablesCallfightersPreparationtime": "Interceptor",
    "PlanesConsumablesCallfightersRange": "Enhanced Patrol Group",
    "PlanesConsumablesRegeneratehealthUpgrade": "Enhanced Aircraft Armor",
    "PlanesDefenseDamageBubbles": "Enhanced Armor-Piercing Ammunition",
    "PlanesDivebomberSpeed": "Enhanced Dive Bomber Accuracy",
    "PlanesForsageRenewal": "Engine Techie",
    "PlanesHp": "Survivability Expert",
    "PlanesTorpedoArmingrange": "Proximity Fuze",
    "PlanesTorpedoSpeed": "Torpedo Bomber Acceleration",
    "PlanesTorpedoUwReduced": "Enhanced Torpedo Bomber Aiming",
    "TorpedoFloodingProbability": "Liquidator",
    "TriggerSpeedBb": "Emergency Engine Power",
    "TriggerGmAtbaReloadBb": "Close Quarters Expert",
    "TriggerGmAtbaReloadCa": "Top Grade Gunner",
    "TriggerGmReload": "Fearless Brawler",
    "TriggerSpeed": "Swift Fish",
    "TriggerSpeedAccuracy": "Eye in the Sky",
    "TriggerSpreading": "Consumable Specialist",
    "TriggerPingerReloadBuff": "Improved Sonar",
    "TriggerPingerSpeedBuff": "Enhanced Sonar",
    "SubmarineHoldSectors": "Sonar Operator",
    "TriggerConsSonarTimeCoeff": "Submarine Vigilance",
    "TriggerSeenTorpedoReload": "Torpedo Crew Training",
    "SubmarineTorpedoPingDamage": "Homing Torpedo Expert",
    "TriggerConsRudderTimeCoeff": "Expert Rear Gunner",
    "SubmarineBatteryCapacity": "Enhanced Battery Capacity",
    "SubmarineDangerAlert": "Enhanced Impulse Generator",
    "SubmarineBatteryBurnDown": "Optimized Battery",
    "SubmarineSpeed": "Improved Battery Efficiency",
    "SubmarineConsumablesReload": "Improved Consumables",
    "SubmarineConsumablesDuration": "Extended Consumables",
    "TriggerBurnGmReload": "Furious",
    "ArmamentReloadSubmarine": "Submarine Adrenaline Rush",
}

# 日本語表示名マッピング（必要に応じて使用）
SKILL_DISPLAY_TO_JAPANESE = {
    "Gun Feeder": "装填手",
    "Basics of Survivability": "生存性基礎",
    "Grease the Gears": "砲旋回強化",
    "Fill the Tubes": "魚雷装填強化",
    "Emergency Repair Specialist": "緊急修理専門家",
    "Consumable Enhancements": "消耗品強化",
    "Vigilance": "警戒",
    "Demolition Expert": "爆発物専門家",
    "Main Battery and AA Specialist": "主砲・対空兵装専門家",
    "Concealment Expert": "隠蔽専門家",
    "Superintendent": "管理",
    "Preventive Maintenance": "予防整備",
    "Priority Target": "優先目標",
    "Last Stand": "最後の抵抗",
    "Adrenaline Rush": "アドレナリンラッシュ",
    "Survivability Expert": "生存性専門家",
    "Long-Range Secondary Battery Shells": "長距離副砲弾",
    "Manual Secondary Battery Aiming": "副砲手動照準",
    "Improved Repair Party Readiness": "修理班準備改良",
    "Emergency Repair Expert": "緊急修理専門家",
    "Radio Location": "無線探知",
    "Liquidator": "破壊者",
    "Fearless Brawler": "恐れを知らない格闘家",
    "Consumable Specialist": "消耗品専門家",
    "Main Battery and AA Expert": "主砲・対空熟練者",
}


def get_skill_display_name(internal_name: str, language: str = "en") -> str:
    """
    内部スキル名から表示名を取得

    Args:
        internal_name: 内部スキル名（例: "DetectionVisibilityRange"）
        language: 言語コード（"en" または "ja"）

    Returns:
        表示名（マッピングがない場合は内部名をそのまま返す）
    """
    display_name = SKILL_INTERNAL_TO_DISPLAY.get(internal_name, internal_name)

    if language == "ja":
        return SKILL_DISPLAY_TO_JAPANESE.get(display_name, display_name)

    return display_name


def extract_crew_skills(replay_hidden_data: Dict[str, Any]) -> Dict[int, Dict[str, List[str]]]:
    """
    リプレイのhiddenデータから艦長スキル情報を抽出

    Args:
        replay_hidden_data: ReplayParserの hidden セクションデータ

    Returns:
        {avatar_id: {"crew_id": int, "skills": {"Battleship": ["Skill1", ...], ...}}}
    """
    result = {}
    crew_data = replay_hidden_data.get("crew", {})

    for avatar_id, crew_info in crew_data.items():
        if not isinstance(crew_info, dict):
            continue

        crew_id = crew_info.get("crew_id")
        learned_skills = crew_info.get("learned_skills", {})

        # 内部名を表示名に変換
        skills_by_ship_type = {}
        for ship_type, skills in learned_skills.items():
            if isinstance(skills, list):
                skills_by_ship_type[ship_type] = [get_skill_display_name(skill) for skill in skills]

        result[avatar_id] = {
            "crew_id": crew_id,
            "skills": skills_by_ship_type,
        }

    return result


def get_player_skills_from_replay(
    replay_hidden_data: Dict[str, Any],
    player_avatar_id: int,
    ship_type: str,
) -> Optional[List[str]]:
    """
    特定プレイヤーの艦長スキルを取得

    Args:
        replay_hidden_data: ReplayParserの hidden セクションデータ
        player_avatar_id: プレイヤーのavatarId
        ship_type: 艦艇タイプ（"Battleship", "Cruiser", "Destroyer", "AirCarrier", "Submarine"）

    Returns:
        スキル名のリスト（取得できない場合は None）
    """
    crew_data = replay_hidden_data.get("crew", {})

    # avatarIdからcrew情報を検索
    # crewのキーはavatarIdとは異なる場合がある（crew_idベース）
    # playersセクションからavatarIdに対応するcrewを見つける必要がある
    players_data = replay_hidden_data.get("players", {})

    for player_id, player_info in players_data.items():
        if not isinstance(player_info, dict):
            continue

        if player_info.get("avatarId") == player_avatar_id:
            crew_params = player_info.get("crewParams", [])
            if crew_params and len(crew_params) > 0:
                crew_id = crew_params[0]

                # crew_idで検索
                for c_id, c_info in crew_data.items():
                    if isinstance(c_info, dict) and c_info.get("crew_id") == crew_id:
                        learned_skills = c_info.get("learned_skills", {})
                        skills = learned_skills.get(ship_type, [])
                        return [get_skill_display_name(s) for s in skills]

    return None


def map_player_to_skills(
    replay_hidden_data: Dict[str, Any],
) -> Dict[str, List[str]]:
    """
    プレイヤー名から艦長スキルへのマッピングを生成

    shipParamsIdから艦艇タイプを特定し、該当艦種のスキルセットのみを返す。
    艦長は複数艦種のスキルを持てるが、現在乗っている艦の艦種に対応した
    スキルセットのみが有効。

    Args:
        replay_hidden_data: ReplayParserの hidden セクションデータ

    Returns:
        {player_name: [skill1, skill2, ...]}
    """
    result = {}
    players_data = replay_hidden_data.get("players", {})
    crew_data = replay_hidden_data.get("crew", {})

    for player_id, player_info in players_data.items():
        if not isinstance(player_info, dict):
            continue

        player_name = player_info.get("name", "")
        crew_params = player_info.get("crewParams", [])
        ship_params_id = player_info.get("shipParamsId")

        if not player_name or not crew_params:
            continue

        crew_id = crew_params[0] if len(crew_params) > 0 else None
        if not crew_id:
            continue

        # shipParamsIdから艦艇タイプを取得（ships.jsonを使用）
        ship_class = None
        if ship_params_id:
            ship_class = get_ship_class_from_params_id(ship_params_id)

        for c_id, c_info in crew_data.items():
            if isinstance(c_info, dict) and c_info.get("crew_id") == crew_id:
                learned_skills = c_info.get("learned_skills", {})

                # 艦艇タイプが特定できた場合、そのタイプのスキルのみを取得
                if ship_class and ship_class in learned_skills:
                    skills = learned_skills[ship_class]
                    result[player_name] = [get_skill_display_name(s) for s in skills]
                else:
                    # フォールバック: 艦種が特定できない場合は旧ロジック
                    # （最初に見つかったタイプのスキルを使用）
                    for fallback_type in ["Destroyer", "Cruiser", "Battleship", "AirCarrier", "Submarine"]:
                        if fallback_type in learned_skills:
                            skills = learned_skills[fallback_type]
                            result[player_name] = [get_skill_display_name(s) for s in skills]
                            break
                break

    return result
