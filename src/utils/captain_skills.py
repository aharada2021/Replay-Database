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
    task_root = os.environ.get("LAMBDA_TASK_ROOT", "")

    # 試行するパスのリスト（優先順）
    paths_to_try = []

    if task_root:
        # Lambda環境: /var/task/data/ships.json (新しいパス)
        paths_to_try.append(Path(task_root) / "data" / "ships.json")
        # フォールバック: 旧パス
        paths_to_try.append(
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
        project_root = Path(__file__).parent.parent.parent
        paths_to_try.append(project_root / "minimap_renderer" / "generated" / "ships.json")
        paths_to_try.append(
            project_root / "minimap_renderer" / "src" / "renderer" / "versions" / "14_11_0" / "resources" / "ships.json"
        )

    for ships_json_path in paths_to_try:
        try:
            with open(ships_json_path, "r", encoding="utf-8") as f:
                _ship_data_cache = json.load(f)
                print(f"Loaded ships.json from {ships_json_path}: {len(_ship_data_cache)} ships")
                return _ship_data_cache
        except FileNotFoundError:
            continue
        except Exception as e:
            print(f"Warning: Failed to load ships.json from {ships_json_path}: {e}")
            continue

    print("Warning: ships.json not found in any of the expected locations")
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


def get_ship_name_from_params_id(ship_params_id: int) -> Optional[str]:
    """
    shipParamsIdから艦艇名を取得

    Args:
        ship_params_id: 艦艇パラメータID

    Returns:
        艦艇名、または None（見つからない場合）
    """
    ship_data = _get_ship_data()
    ship_info = ship_data.get(str(ship_params_id))
    if ship_info:
        return ship_info.get("name")
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

# 日本語表示名マッピング（WoWS公式日本語版準拠）
SKILL_DISPLAY_TO_JAPANESE = {
    # 共通スキル
    "Gun Feeder": "装填手",
    "Basics of Survivability": "応急対応の基本",
    "Grease the Gears": "歯車のグリスアップ",
    "Fill the Tubes": "魚雷装填手",
    "Emergency Repair Specialist": "緊急修理技術者",
    "Consumable Enhancements": "消耗品強化",
    "Vigilance": "警戒",
    "Demolition Expert": "爆発物専門家",
    "Main Battery and AA Specialist": "主砲・対空兵装技術者",
    "Concealment Expert": "隠蔽処理専門家",
    "Superintendent": "管理",
    "Preventive Maintenance": "予防整備",
    "Priority Target": "危険察知",
    "Last Stand": "最後の抵抗",
    "Adrenaline Rush": "アドレナリン・ラッシュ",
    "Survivability Expert": "抗堪専門家",
    "Long-Range Secondary Battery Shells": "長射程副砲弾",
    "Manual Secondary Battery Aiming": "副砲の手動照準",
    "Improved Repair Party Readiness": "改良型修理班準備",
    "Emergency Repair Expert": "緊急修理専門家",
    "Radio Location": "無線方向探知",
    "Liquidator": "水浸し",
    "Fearless Brawler": "恐れ知らずの喧嘩屋",
    "Consumable Specialist": "消耗品技術者",
    "Main Battery and AA Expert": "主砲・対空兵装専門家",
    # 戦艦スキル
    "Inertia Fuse for HE Shells": "榴弾用慣性信管",
    "Brisk": "活発",
    "Super-Heavy AP Shells": "超重徹甲弾",
    "Focus Fire Training": "集中砲火訓練",
    "Furious": "猛烈",
    "Close Quarters Combat": "近距離戦闘",
    "Fire Prevention Expert": "防火処理専門家",
    # 巡洋艦スキル
    "Swift Fish": "高速魚雷",
    "Eye in the Sky": "上空の眼",
    "Heavy HE and SAP Shells": "重榴弾・SAP弾",
    "Pack A Punch": "強烈な打撃力",
    "Heavy AP Shells": "重徹甲弾",
    "Top Grade Gunner": "最上級砲手",
    "Outnumbered": "数的劣勢",
    "AA Defense and ASW Expert": "対空・対潜専門家",
    # 駆逐艦スキル
    "Extra-Heavy Ammunition": "特重弾薬",
    "Swift in Silence": "素早く静かに",
    "Dazzle": "幻惑",
    # 空母スキル
    "Last Gasp": "最後の奮闘",
    "Improved Engine Boost": "エンジンブースト改良",
    "Engine Techie": "エンジン技師",
    "Air Supremacy": "制空権",
    "Direction Center for Fighters": "戦闘機指揮所",
    "Search and Destroy": "索敵掃討",
    "Torpedo Bomber": "雷撃機",
    "Improved Engines": "エンジン改良",
    "Repair Specialist": "修理技術者",
    "Secondary Armament Expert": "副砲専門家",
    "Patrol Group Leader": "偵察隊リーダー",
    "Sight Stabilization": "照準安定化",
    "Enhanced Armor-Piercing Ammunition": "強化型徹甲弾",
    "Pyrotechnician": "爆発物専門家",
    "Aircraft Armor": "航空機装甲",
    "Interceptor": "迎撃機",
    "Bomber Flight Control": "爆撃機の飛行制御",
    "Proximity Fuze": "近接信管",
    "Close Quarters Expert": "接近戦",
    "Enhanced Aircraft Armor": "強化型航空機装甲",
    "Hidden Menace": "隠れた脅威",
    "Enhanced Reactions": "強化型反応速度",
    # 潜水艦スキル
    "Enhanced Sonar": "強化型ソナー",
    "Helmsman": "操舵手",
    "Improved Battery Capacity": "改良型バッテリー容量",
    "Torpedo Crew Training": "魚雷員訓練",
    "Enhanced Impulse Generator": "強化型インパルス発生器",
    "Sonarman": "ソナー操作員",
    "Watchful": "用心",
    "Torpedo Aiming Master": "魚雷誘導マスター",
    "Sonarman Expert": "ソナー操作専門家",
    "Improved Battery Efficiency": "改良型バッテリー効率",
    "Enlarged Propeller Shaft": "大型プロペラ・シャフト",
    "Submarine Adrenaline Rush": "潜水艦アドレナリン・ラッシュ",
    "Improved Sonar": "ソナー改良",
    "Sonar Operator": "ソナー操作員",
    "Submarine Vigilance": "潜水艦警戒",
    "Homing Torpedo Expert": "誘導魚雷専門家",
    "Expert Rear Gunner": "後部機銃手熟練",
    "Enhanced Battery Capacity": "蓄電池容量強化",
    "Optimized Battery": "蓄電池最適化",
    "Improved Consumables": "消耗品改良",
    "Extended Consumables": "消耗品延長",
    # その他
    "Incoming Fire Alert": "敵弾接近警報",
    "Expert Loader": "熟練装填手",
    "Torpedo Armament Expertise": "魚雷兵装専門家",
    "Enhanced Fighter Consumable": "戦闘機消耗品強化",
    "Armored Deck": "装甲甲板",
    "Enhanced Patrol Group": "哨戒隊強化",
    "Enhanced Dive Bomber Accuracy": "急降下爆撃機精度強化",
    "Engine Tuning": "エンジン調整",
    "Aiming Facility Maintenance": "照準設備整備",
    "Torpedo Bomber Acceleration": "雷撃機加速",
    "Enhanced Torpedo Bomber Aiming": "雷撃機照準強化",
    "Emergency Engine Power": "緊急エンジン出力",
    "Improved Secondary Battery Aiming": "副砲照準改良",
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


def extract_crew_skills(
    replay_hidden_data: Dict[str, Any],
) -> Dict[int, Dict[str, List[str]]]:
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
                    result[player_name] = [get_skill_display_name(s, language="ja") for s in skills]
                else:
                    # フォールバック: 艦種が特定できない場合は旧ロジック
                    # （最初に見つかったタイプのスキルを使用）
                    for fallback_type in [
                        "Destroyer",
                        "Cruiser",
                        "Battleship",
                        "AirCarrier",
                        "Submarine",
                    ]:
                        if fallback_type in learned_skills:
                            skills = learned_skills[fallback_type]
                            result[player_name] = [get_skill_display_name(s, language="ja") for s in skills]
                            break
                break

    return result
