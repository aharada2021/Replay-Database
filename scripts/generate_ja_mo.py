"""
日本語MO翻訳ファイル生成スクリプト

英語MOファイルのIDS_*キーを元に、スキル・アップグレード・マップの日本語翻訳を
作成し、MOファイルを生成する。

翻訳マッピングのマスターデータ:
  - スキル: web-ui/app/composables/useCaptainSkills.ts
  - アップグレード: web-ui/app/composables/useUpgrades.ts
  - マップ: config/map_names.yaml

使用方法:
    python3 scripts/generate_ja_mo.py

出力:
    /tmp/ja_global.mo - 生成された日本語MOファイル
    S3にアップロード: game-data/{version}/translations/ja/LC_MESSAGES/global.mo
"""

import struct
import sys
import os
import re
import subprocess
import tempfile


# 英語表示名 → 日本語名（useCaptainSkills.tsのSKILLS_EN/SKILLS_JAから生成）
SKILL_EN_TO_JA = {
    "Gun Feeder": "装填手",
    "Basics of Survivability": "応急対応の基本",
    "Grease the Gears": "歯車のグリスアップ",
    "Fill the Tubes": "魚雷装填手",
    "Emergency Repair Specialist": "緊急修理技術者",
    "Consumable Enhancements": "消耗品強化",
    "Vigilance": "警戒",
    "Demolition Expert": "爆発物専門家",
    "Main Battery and AA Specialist": "主砲・対空兵装専門家",
    "Main Battery and AA Expert": "主砲・対空兵装専門家",
    "Aircraft Armor": "航空機装甲",
    "Improved Engine Boost": "エンジンブースト改良",
    "Concealment Expert": "隠蔽処理専門家",
    "Consumable Specialist": "消耗品技術者",
    "Fire Prevention Expert": "防火処理専門家",
    "Aiming Facility Maintenance": "照準安定化",
    "Sight Stabilization": "照準安定化",
    "Improved Engines": "エンジン改良",
    "Superintendent": "管理",
    "Preventive Maintenance": "予防整備",
    "Priority Target": "危険察知",
    "Last Stand": "最後の抵抗",
    "Expert Loader": "装填手",
    "Search and Destroy": "索敵掃討",
    "Adrenaline Rush": "アドレナリン・ラッシュ",
    "Swift Fish": "高速魚雷",
    "Survivability Expert": "抗堪専門家",
    "Manual Secondary Battery Aiming": "副砲の手動照準",
    "Focus Fire Training": "集中砲火訓練",
    "Incoming Fire Alert": "敵弾接近警報",
    "Watchful": "警戒態勢",
    "Air Supremacy": "制空権",
    "Pack A Punch": "強烈な打撃力",
    "Direction Center for Fighters": "戦闘機指揮所",
    "Engine Techie": "エンジン技師",
    "Inertia Fuse for HE Shells": "榴弾用慣性信管",
    "Radio Location": "無線方向探知",
    "AA Defense and ASW Expert": "対空・対潜専門家",
    "Secondary Armament Expert": "副砲専門家",
    "Super-Heavy AP Shells": "超重徹甲弾",
    "Heavy AP Shells": "重徹甲弾",
    "Extra-Heavy Ammunition": "特重弾薬",
    "Long-Range Secondary Battery Shells": "長射程副砲弾",
    "Improved Secondary Battery Aiming": "副砲照準改良",
    "Improved Repair Party Readiness": "改良型修理班準備",
    "Eye in the Sky": "上空の眼",
    "Emergency Repair Expert": "緊急修理専門家",
    "Hidden Menace": "隠れた脅威",
    "Pyrotechnician": "爆発物専門家",
    "Heavy HE and SAP Shells": "重榴弾・SAP弾",
    "Enhanced Armor-Piercing Ammunition": "強化型徹甲弾",
    "Patrol Group Leader": "偵察隊リーダー",
    "Enhanced Reactions": "強化型反応速度",
    "Interceptor": "迎撃機",
    "Repair Specialist": "修理技術者",
    "Enhanced Aircraft Armor": "強化型航空機装甲",
    "Bomber Flight Control": "爆撃機の飛行制御",
    "Last Gasp": "最後の奮闘",
    "Torpedo Bomber": "雷撃機",
    "Torpedo Bomber Acceleration": "高速航空魚雷",
    "Proximity Fuze": "近接信管",
    "Liquidator": "水浸し",
    "Brisk": "活発",
    "Close Quarters Expert": "接近戦",
    "Top Grade Gunner": "最上級砲手",
    "Fearless Brawler": "恐れ知らずの喧嘩屋",
    "Swift in Silence": "素早く静かに",
    "Outnumbered": "数的劣勢",
    "Dazzle": "幻惑",
    "Enhanced Sonar": "強化型ソナー",
    "Enhanced Impulse Generator": "強化型インパルス発生器",
    "Sonar Operator": "ソナー操作員",
    "Sonarman": "ソナー操作員",
    "Torpedo Crew Training": "魚雷員訓練",
    "Homing Torpedo Expert": "魚雷誘導マスター",
    "Torpedo Aiming Master": "魚雷誘導マスター",
    "Helmsman": "操舵手",
    "Improved Battery Capacity": "改良型バッテリー容量",
    "Improved Battery Efficiency": "改良型バッテリー効率",
    "Enlarged Propeller Shaft": "大型プロペラ・シャフト",
    "Improved Consumables": "消耗品技術者",
    "Extended Consumables": "消耗品強化",
    "Furious": "猛烈",
    "Submarine Adrenaline Rush": "アドレナリン・ラッシュ",
    # 追加スキル（composable未収録）
    "Defensive Fire Expert": "防御射撃専門家",
    "Combat Maneuver Specialist": "戦闘機動専門家",
    "Swift Flying Fish": "高速飛魚",
    "Pack a Punch": "強烈な打撃力",
    "Alt Torpedoes 2": "代替魚雷2",
}

# PCMコード → 日本語名（useUpgrades.tsから生成）
UPGRADE_NAMES_JA = {
    "PCM001": "主砲改良1",
    "PCM002": "副兵装改良1",
    "PCM003": "航空機改良1",
    "PCM004": "対空兵装改良1",
    "PCM005": "副砲改良1",
    "PCM006": "主砲改良2",
    "PCM007": "魚雷発射管改良1",
    "PCM008": "射撃システム改良1",
    "PCM009": "飛行制御改良1",
    "PCM010": "戦闘機改良1",
    "PCM011": "対空兵装改良2",
    "PCM012": "副砲改良2",
    "PCM013": "主砲改良3",
    "PCM014": "魚雷発射管改良2",
    "PCM015": "射撃管制システム改良2",
    "PCM016": "飛行制御改良2",
    "PCM017": "航空機改良2",
    "PCM018": "対空砲改良1",
    "PCM019": "副砲改良3",
    "PCM020": "ダメージコントロールシステム改良1",
    "PCM021": "推進システム改良1",
    "PCM022": "操舵システム改良1",
    "PCM023": "ダメージコントロールシステム改良2",
    "PCM024": "推進システム改良1",
    "PCM025": "操舵システム改良1",
    "PCM026": "魚雷警戒システム",
    "PCM027": "隠蔽システム改良1",
    "PCM028": "射撃管制室改良1",
    "PCM029": "射撃管制室改良2",
    "PCM030": "主兵装改良1",
    "PCM031": "補助兵装改良1",
    "PCM032": "特殊改良（空）",
    "PCM033": "照準システム改良1",
    "PCM034": "照準システム改良0",
    "PCM035": "操舵システム改良2",
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
    "PCM063": "攻撃機改良2",
    "PCM064": "雷撃機改良2",
    "PCM065": "爆撃機改良1",
    "PCM066": "雷撃機改良1",
    "PCM067": "攻撃機改良1",
    "PCM068": "航空機エンジン改良1",
    "PCM069": "機関室防護",
    "PCM070": "魚雷発射管改良1",
    "PCM071": "航空魚雷改良1",
    "PCM072": "艦艇消耗品改良1",
    "PCM073": "航空隊消耗品改良1",
    "PCM074": "補助兵装改良2",
    "PCM075": "魚雷改良特殊3",
    "PCM076": "隠蔽改良特殊3",
    "PCM077": "煙幕改良特殊2",
    "PCM078": "主砲改良特殊2",
    "PCM079": "推進・隠蔽改良1",
    "PCM080": "主砲射撃改良3",
    "PCM081": "スキップボマー改良2",
    "PCM082": "潜航容量改良1",
    "PCM083": "聴音改良特殊1",
    "PCM084": "ソナー改良1",
    "PCM085": "ソナー改良2",
    "PCM086": "潜航容量改良2",
    "PCM087": "航空攻撃改良1",
    "PCM088": "爆雷改良特殊1",
    "PCM089": "爆雷改良1",
    "PCM090": "潜水艦操舵システム",
    "PCM091": "潜水艦操舵改良1",
    "PCM092": "スキップボマー改良1",
    "PCM093": "航空機改良3",
    "PCM094": "特殊改良1",
    "PCM095": "煙幕改良特殊3",
    "PCM096": "主砲改良特殊3",
    "PCM097": "雷撃機改良特殊1",
    "PCM098": "駆逐艦改良特殊1",
    "PCM099": "爆雷改良特殊2",
    "PCM100": "ダメコンシステム改良3",
    "PCM101": "魚雷発射管改良3",
    "PCM102": "強化隔壁",
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
}


def load_map_names():
    """map_names.yamlから日本語マップ名を読み込む"""
    import yaml

    yaml_path = os.path.join(os.path.dirname(__file__), "..", "config", "map_names.yaml")
    with open(yaml_path, "r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    return data.get("maps", {})


def parse_mo_file(mo_path):
    """MOファイルをパースして(key, value)ペアのリストを返す"""
    with open(mo_path, "rb") as f:
        data = f.read()

    magic = struct.unpack("<I", data[:4])[0]
    if magic == 0x950412DE:
        fmt = "<"
    elif magic == 0xDE120495:
        fmt = ">"
    else:
        raise ValueError(f"Invalid MO magic: {hex(magic)}")

    nstrings = struct.unpack(f"{fmt}I", data[8:12])[0]
    orig_offset = struct.unpack(f"{fmt}I", data[12:16])[0]
    trans_offset = struct.unpack(f"{fmt}I", data[16:20])[0]

    entries = []
    for i in range(nstrings):
        orig_len, orig_off = struct.unpack(
            f"{fmt}II", data[orig_offset + i * 8 : orig_offset + i * 8 + 8]
        )
        trans_len, trans_off = struct.unpack(
            f"{fmt}II", data[trans_offset + i * 8 : trans_offset + i * 8 + 8]
        )
        orig = data[orig_off : orig_off + orig_len].decode("utf-8", errors="replace")
        trans = data[trans_off : trans_off + trans_len].decode("utf-8", errors="replace")
        entries.append((orig, trans))

    return entries


def camel_to_upper_snake(name):
    """CamelCase → UPPER_SNAKE_CASE 変換"""
    s1 = re.sub("(.)([A-Z][a-z]+)", r"\1_\2", name)
    s2 = re.sub("([a-z0-9])([A-Z])", r"\1_\2", s1)
    return s2.upper()


def build_skill_key_map(en_entries):
    """英語MOからスキルキー → 英語名のマップを構築（名前のみ、説明やUI文字列を除外）"""
    skill_en_map = {}
    exclude_patterns = ["_DESC", "_INACTIVE", "_OVERRIDE", "_TRIGGER_", "_SELECT_", "_ISEPIC"]
    for key, val in en_entries:
        if key.startswith("IDS_SKILL_"):
            if not any(p in key for p in exclude_patterns):
                skill_en_map[key] = val
    return skill_en_map


def build_upgrade_key_map(en_entries):
    """英語MOからアップグレードキー → 英語名のマップを構築"""
    upgrade_en_map = {}
    for key, val in en_entries:
        if key.startswith("IDS_TITLE_PCM") and "_DESCR" not in key:
            upgrade_en_map[key] = val
    return upgrade_en_map


def build_map_key_map(en_entries):
    """英語MOからマップキー → 英語名のマップを構築"""
    map_en_map = {}
    for key, val in en_entries:
        if key.startswith("IDS_SPACES/") and "_DESCR" not in key:
            map_en_map[key] = val
    return map_en_map


def generate_ja_translations(en_mo_path):
    """英語MOファイルから日本語翻訳POエントリを生成"""
    en_entries = parse_mo_file(en_mo_path)
    print(f"Loaded {len(en_entries)} entries from English MO")

    ja_translations = {}

    # === スキル翻訳 ===
    # 英語表示名 → 日本語名のマップ
    en_to_ja_skill = SKILL_EN_TO_JA

    # IDS_SKILL_* キーと英語名を取得
    skill_en_map = build_skill_key_map(en_entries)
    skill_matched = 0
    skill_missed = []

    for ids_key, en_name in skill_en_map.items():
        if en_name in en_to_ja_skill:
            ja_translations[ids_key] = en_to_ja_skill[en_name]
            skill_matched += 1
        else:
            skill_missed.append((ids_key, en_name))

    print(f"Skills: {skill_matched} matched, {len(skill_missed)} missed")
    if skill_missed:
        for key, name in skill_missed[:10]:
            print(f"  MISS: {key} = {name}")
        if len(skill_missed) > 10:
            print(f"  ... and {len(skill_missed) - 10} more")

    # === アップグレード翻訳 ===
    upgrade_en_map = build_upgrade_key_map(en_entries)
    upgrade_matched = 0
    upgrade_missed = []

    for ids_key, en_name in upgrade_en_map.items():
        # IDS_TITLE_PCM030_MAINWEAPON_MOD_I → PCM030 を抽出
        match = re.match(r"IDS_TITLE_(PCM\d+)_", ids_key)
        if match:
            pcm_code = match.group(1)
            if pcm_code in UPGRADE_NAMES_JA:
                ja_translations[ids_key] = UPGRADE_NAMES_JA[pcm_code]
                upgrade_matched += 1
            else:
                upgrade_missed.append((ids_key, pcm_code, en_name))

    print(f"Upgrades: {upgrade_matched} matched, {len(upgrade_missed)} missed")
    if upgrade_missed:
        for key, pcm, name in upgrade_missed[:10]:
            print(f"  MISS: {key} ({pcm}) = {name}")

    # === マップ翻訳 ===
    map_names = load_map_names()
    map_en_map = build_map_key_map(en_entries)
    map_matched = 0
    map_missed = []

    # マップ名の正規化マップ: yamlキーの様々なバリエーションを構築
    map_names_normalized = {}
    for yaml_id, ja_name in map_names.items():
        map_names_normalized[yaml_id.lower()] = ja_name

    for ids_key, en_name in map_en_map.items():
        # IDS_SPACES/20_NE_two_brothers → NE_two_brothers を抽出
        space_name = ids_key.replace("IDS_SPACES/", "")
        # 数字_プレフィックスを除去: "20_NE_two_brothers" → "NE_two_brothers"
        map_id = re.sub(r"^\d+_", "", space_name)

        found = False
        # 試行1: そのまま比較（大文字小文字無視）
        if map_id.lower() in map_names_normalized:
            ja_translations[ids_key] = map_names_normalized[map_id.lower()]
            map_matched += 1
            found = True
        else:
            # 試行2: 方向プレフィックス（NE_, OC_, NA_, CO_）を除去して比較
            stripped = re.sub(r"^(NE_|OC_|NA_|CO_|AS\d+_|R\d+_)", "", map_id)
            if stripped.lower() in map_names_normalized:
                ja_translations[ids_key] = map_names_normalized[stripped.lower()]
                map_matched += 1
                found = True

        if not found:
            map_missed.append((ids_key, map_id, en_name))

    print(f"Maps: {map_matched} matched, {len(map_missed)} missed")
    if map_missed:
        for key, mid, name in map_missed[:10]:
            print(f"  MISS: {key} ({mid}) = {name}")
        if len(map_missed) > 10:
            print(f"  ... and {len(map_missed) - 10} more")

    # === 翻訳がないエントリは英語をそのまま使う ===
    # MOファイルは全エントリを含む必要がある
    total_with_ja = len(ja_translations)
    for key, en_val in en_entries:
        if key not in ja_translations:
            ja_translations[key] = en_val

    print(f"\nTotal: {len(ja_translations)} entries ({total_with_ja} Japanese, "
          f"{len(ja_translations) - total_with_ja} English fallback)")

    return ja_translations, en_entries


def escape_po_string(s):
    """PO形式の文字列エスケープ"""
    s = s.replace("\\", "\\\\")
    s = s.replace('"', '\\"')
    s = s.replace("\n", "\\n")
    s = s.replace("\t", "\\t")
    return s


def write_po_file(po_path, ja_translations, en_entries):
    """PO形式で翻訳ファイルを書き出す"""
    with open(po_path, "w", encoding="utf-8") as f:
        # PO header
        f.write('# Japanese translations for WoWS\n')
        f.write('msgid ""\n')
        f.write('msgstr ""\n')
        f.write('"Content-Type: text/plain; charset=UTF-8\\n"\n')
        f.write('"Content-Transfer-Encoding: 8bit\\n"\n')
        f.write('"Language: ja\\n"\n')
        f.write('\n')

        for key, en_val in en_entries:
            if not key:  # skip empty header entry
                continue
            ja_val = ja_translations.get(key, en_val)
            f.write(f'msgid "{escape_po_string(key)}"\n')
            f.write(f'msgstr "{escape_po_string(ja_val)}"\n')
            f.write('\n')


def compile_mo(po_path, mo_path):
    """POファイルをMOファイルにコンパイル"""
    # まずmsgfmtを試行、なければpolibにフォールバック
    try:
        subprocess.run(
            ["msgfmt", "-o", mo_path, po_path],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"Compiled MO (msgfmt): {mo_path}")
        mo_size = os.path.getsize(mo_path)
        print(f"MO file size: {mo_size:,} bytes")
        return True
    except FileNotFoundError:
        pass
    except subprocess.CalledProcessError as e:
        print(f"ERROR: msgfmt failed: {e.stderr}")
        return False

    # polib fallback
    try:
        import polib
        po = polib.pofile(po_path)
        po.save_as_mofile(mo_path)
        print(f"Compiled MO (polib): {mo_path}")
        mo_size = os.path.getsize(mo_path)
        print(f"MO file size: {mo_size:,} bytes")
        return True
    except ImportError:
        print("ERROR: Neither msgfmt nor polib available.")
        print("  pip install polib  # or install gettext")
        return False


def upload_to_s3(mo_path, versions=None):
    """MOファイルをS3にアップロード"""
    import boto3

    s3 = boto3.client("s3")
    bucket = "wows-replay-bot-dev-temp"

    if versions is None:
        # S3から利用可能なバージョンを自動検出
        paginator = s3.get_paginator("list_objects_v2")
        versions = set()
        for page in paginator.paginate(Bucket=bucket, Prefix="game-data/", Delimiter="/"):
            for prefix in page.get("CommonPrefixes", []):
                ver = prefix["Prefix"].replace("game-data/", "").rstrip("/")
                if ver:
                    versions.add(ver)
        versions = sorted(versions)

    for version in versions:
        s3_key = f"game-data/{version}/translations/ja/LC_MESSAGES/global.mo"
        print(f"Uploading to s3://{bucket}/{s3_key}")
        s3.upload_file(mo_path, bucket, s3_key)
        print(f"  Done: {s3_key}")


def main():
    tmp_dir = tempfile.gettempdir()
    en_mo_path = os.path.join(tmp_dir, "en_global.mo")

    # ローカルのrenderer_dataから英語MOを探す
    local_en_mo = None
    for search_dir in [
        os.path.join(os.path.dirname(__file__), "..", "..", "wows-toolkit", "renderer_data"),
        os.path.join("C:\\Users\\family\\workdir\\wows-toolkit\\renderer_data"),
    ]:
        if os.path.isdir(search_dir):
            for d in sorted(os.listdir(search_dir), reverse=True):
                candidate = os.path.join(search_dir, d, "translations", "en", "LC_MESSAGES", "global.mo")
                if os.path.exists(candidate):
                    local_en_mo = candidate
                    break
        if local_en_mo:
            break

    if local_en_mo and not os.path.exists(en_mo_path):
        import shutil
        print(f"Copying English MO from {local_en_mo}")
        shutil.copy2(local_en_mo, en_mo_path)
    elif not os.path.exists(en_mo_path):
        print("Downloading English MO from S3...")
        os.system(
            "aws s3 cp s3://wows-replay-bot-dev-temp/game-data/15.3.0_12267945/"
            "translations/en/LC_MESSAGES/global.mo " + en_mo_path
        )

    print("=== Generating Japanese MO translation file ===\n")

    ja_translations, en_entries = generate_ja_translations(en_mo_path)

    po_path = os.path.join(tmp_dir, "ja_global.po")
    mo_path = os.path.join(tmp_dir, "ja_global.mo")

    print(f"\nWriting PO: {po_path}")
    write_po_file(po_path, ja_translations, en_entries)

    if not compile_mo(po_path, mo_path):
        return 1

    # 検証: MOファイルを読み込んで翻訳を確認
    print("\n=== Verification ===")
    ja_entries = parse_mo_file(mo_path)
    ja_dict = dict(ja_entries)

    test_keys = [
        ("IDS_SKILL_DETECTION_VISIBILITY_RANGE", "隠蔽処理専門家"),
        ("IDS_SKILL_ARMAMENT_RELOAD_AA_DAMAGE", "アドレナリン・ラッシュ"),
        ("IDS_TITLE_PCM030_MAINWEAPON_MOD_I", "主兵装改良1"),
        ("IDS_TITLE_PCM027_CONCEALMENTMEASURES_MOD_I", "隠蔽システム改良1"),
    ]

    for key, expected in test_keys:
        actual = ja_dict.get(key, "NOT FOUND")
        status = "OK" if actual == expected else "MISMATCH"
        print(f"  {status}: {key} = {actual} (expected: {expected})")

    # マップ検証
    map_test = [k for k in ja_dict if k.startswith("IDS_SPACES/") and "_DESCR" not in k]
    ja_map_count = sum(1 for k in map_test if not ja_dict[k].isascii())
    print(f"  Maps with Japanese: {ja_map_count}/{len(map_test)}")

    if "--upload" in sys.argv:
        print("\n=== Uploading to S3 ===")
        upload_to_s3(mo_path)
    else:
        print("\nTo upload to S3, run with --upload flag:")
        print("  python3 scripts/generate_ja_mo.py --upload")

    return 0


if __name__ == "__main__":
    sys.exit(main())
