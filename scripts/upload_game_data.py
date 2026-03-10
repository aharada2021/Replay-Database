"""
ゲームデータの抽出とS3アップロード

Windows環境でwows-data-mgrを実行してゲームデータを抽出し、
extraction用の最小データ（entity_defs, game_params.rkyv, translations）をS3にアップロードする。

使い方:
  # 抽出済みデータのアップロードのみ
  python scripts/upload_game_data.py --data-dir /path/to/renderer_data/15.2.0_12116141

  # 全バージョンを一括アップロード
  python scripts/upload_game_data.py --data-dir /path/to/renderer_data --all

  # フルデータ（rendering用含む）をアップロード
  python scripts/upload_game_data.py --data-dir /path/to/renderer_data/15.2.0_12116141 --full

環境変数:
  AWS_PROFILE: AWSプロファイル（省略時はdefault）
  GAME_DATA_BUCKET: S3バケット名（省略時はwows-replay-bot-dev-temp）
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path


S3_BUCKET = os.environ.get("GAME_DATA_BUCKET", "wows-replay-bot-dev-temp")
S3_PREFIX = "game-data"

# extraction用の最小データ（~43MB/version）
EXTRACTION_PATHS = [
    "metadata.toml",
    "game_params.rkyv",
    "vfs/scripts/",
    "translations/",
]

# rendering用の追加データ（extraction + ~72MB/version）
RENDERING_EXTRA_PATHS = [
    "vfs/gui/",
    "vfs/spaces/",
    "vfs/content/",
]


def find_versions(data_dir: Path) -> list:
    """data_dir内のバージョンディレクトリを検出"""
    versions = []
    for entry in sorted(data_dir.iterdir()):
        if entry.is_dir() and (entry / "metadata.toml").exists():
            versions.append(entry)
    return versions


def parse_version_from_metadata(version_dir: Path) -> str:
    """metadata.tomlからバージョン文字列を取得"""
    meta_path = version_dir / "metadata.toml"
    if not meta_path.exists():
        return version_dir.name

    version = ""
    build = ""
    for line in meta_path.read_text().splitlines():
        line = line.strip()
        if line.startswith("version"):
            version = line.split("=", 1)[1].strip().strip('"')
        elif line.startswith("build"):
            build = line.split("=", 1)[1].strip().strip('"')

    if version and build:
        return f"{version}_{build}"
    return version_dir.name


def upload_version(version_dir: Path, full: bool = False, dry_run: bool = False):
    """1バージョン分のデータをS3にアップロード"""
    version_name = parse_version_from_metadata(version_dir)
    s3_dest = f"s3://{S3_BUCKET}/{S3_PREFIX}/{version_name}"

    paths = EXTRACTION_PATHS[:]
    if full:
        paths += RENDERING_EXTRA_PATHS

    print(f"\n{'[DRY RUN] ' if dry_run else ''}Uploading {version_name} ({'full' if full else 'extraction-only'})")
    print(f"  Source: {version_dir}")
    print(f"  Dest:   {s3_dest}")

    for rel_path in paths:
        src = version_dir / rel_path
        dest = f"{s3_dest}/{rel_path}"

        if not src.exists():
            print(f"  SKIP (not found): {rel_path}")
            continue

        if src.is_dir():
            cmd = ["aws", "s3", "sync", str(src), dest]
        else:
            cmd = ["aws", "s3", "cp", str(src), dest]

        if dry_run:
            print(f"  Would run: {' '.join(cmd)}")
        else:
            print(f"  Syncing: {rel_path}")
            result = subprocess.run(cmd, capture_output=True, text=True)
            if result.returncode != 0:
                print(f"  ERROR: {result.stderr.strip()}")
                return False

    print(f"  Done: {version_name}")
    return True


def list_s3_versions():
    """S3にアップロード済みのバージョンを表示"""
    cmd = ["aws", "s3", "ls", f"s3://{S3_BUCKET}/{S3_PREFIX}/"]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"Error listing S3: {result.stderr.strip()}")
        return

    print(f"\nVersions in s3://{S3_BUCKET}/{S3_PREFIX}/:")
    for line in result.stdout.strip().splitlines():
        # Format: "                           PRE 15.1.0_11965230/"
        name = line.strip().replace("PRE ", "").strip("/")
        if name:
            print(f"  {name}")


def main():
    parser = argparse.ArgumentParser(description="Upload game data to S3")
    parser.add_argument("--data-dir", required=True, help="Path to renderer_data directory or specific version")
    parser.add_argument("--all", action="store_true", help="Upload all versions found in data-dir")
    parser.add_argument("--full", action="store_true", help="Upload full data (including rendering assets)")
    parser.add_argument("--dry-run", action="store_true", help="Show what would be uploaded without uploading")
    parser.add_argument("--list", action="store_true", help="List versions already in S3")
    args = parser.parse_args()

    if args.list:
        list_s3_versions()
        return

    data_dir = Path(args.data_dir)
    if not data_dir.exists():
        print(f"Error: {data_dir} does not exist")
        sys.exit(1)

    if args.all:
        versions = find_versions(data_dir)
        if not versions:
            print(f"No version directories found in {data_dir}")
            sys.exit(1)
        print(f"Found {len(versions)} version(s): {[v.name for v in versions]}")
        for v in versions:
            upload_version(v, full=args.full, dry_run=args.dry_run)
    else:
        if not (data_dir / "metadata.toml").exists():
            print(f"Error: {data_dir} is not a valid version directory (no metadata.toml)")
            print("Use --all to scan for all versions in a parent directory")
            sys.exit(1)
        upload_version(data_dir, full=args.full, dry_run=args.dry_run)

    if not args.dry_run:
        print("\n--- S3 Status ---")
        list_s3_versions()


if __name__ == "__main__":
    main()
