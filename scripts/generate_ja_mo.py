"""
日本語MO翻訳ファイル生成スクリプト

英語MOファイルのIDS_*キーを元に、既存のPythonマッピング（captain_skills.py,
upgrades.py, map_names.yaml）から日本語翻訳を作成し、MOファイルを生成する。

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

# プロジェクトルートをパスに追加
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.utils.captain_skills import SKILL_INTERNAL_TO_DISPLAY, SKILL_DISPLAY_TO_JAPANESE
from src.utils.upgrades import UPGRADE_NAMES_JA

# Python既存マッピングにない追加スキル翻訳
ADDITIONAL_SKILL_JA = {
    "Defensive Fire Expert": "防御射撃専門家",
    "Combat Maneuver Specialist": "戦闘機動専門家",
    "Swift Flying Fish": "高速飛魚",
    "Pack a Punch": "強烈な打撃力",
    "Alt Torpedoes 2": "代替魚雷2",
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
    # 英語表示名 → 日本語名のマップ構築
    en_to_ja_skill = {**SKILL_DISPLAY_TO_JAPANESE, **ADDITIONAL_SKILL_JA}

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
    try:
        subprocess.run(
            ["msgfmt", "-o", mo_path, po_path],
            check=True,
            capture_output=True,
            text=True,
        )
        print(f"Compiled MO: {mo_path}")
        mo_size = os.path.getsize(mo_path)
        print(f"MO file size: {mo_size:,} bytes")
        return True
    except FileNotFoundError:
        print("ERROR: msgfmt not found. Install gettext:")
        print("  brew install gettext  # macOS")
        print("  apt install gettext   # Linux")
        return False
    except subprocess.CalledProcessError as e:
        print(f"ERROR: msgfmt failed: {e.stderr}")
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
    en_mo_path = "/tmp/en_global.mo"

    if not os.path.exists(en_mo_path):
        print("Downloading English MO from S3...")
        os.system(
            "aws s3 cp s3://wows-replay-bot-dev-temp/game-data/15.2.0_12116141/"
            "translations/en/LC_MESSAGES/global.mo /tmp/en_global.mo"
        )

    print("=== Generating Japanese MO translation file ===\n")

    ja_translations, en_entries = generate_ja_translations(en_mo_path)

    po_path = "/tmp/ja_global.po"
    mo_path = "/tmp/ja_global.mo"

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
