"""
GitHub Releases ベースの自動アップデーター

GitHub Releases APIから最新バージョンを取得し、
自動的にダウンロード・適用する。
"""

import hashlib
import logging
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path
from typing import Optional, Tuple

import requests

logger = logging.getLogger(__name__)

# GitHub リポジトリ情報
GITHUB_REPO_OWNER = "aharada2021"
GITHUB_REPO_NAME = "Replay-Database"
GITHUB_API_BASE = f"https://api.github.com/repos/{GITHUB_REPO_OWNER}/{GITHUB_REPO_NAME}"
TAG_PREFIX = "client-v"

# アップデートの安全制限
MAX_UPDATE_SIZE_BYTES = 200 * 1024 * 1024  # 200MB
EXPECTED_EXE_NAME = "wows_replay_uploader.exe"


def parse_version(version_str: str) -> Tuple[int, ...]:
    """バージョン文字列をタプルに変換（比較用）"""
    try:
        return tuple(int(x) for x in version_str.split("."))
    except (ValueError, AttributeError):
        return (0, 0, 0)


def is_frozen() -> bool:
    """PyInstallerでパッケージされた実行ファイルかどうか"""
    return getattr(sys, "frozen", False)


def get_exe_path() -> Optional[Path]:
    """実行中のexeファイルパスを取得"""
    if is_frozen():
        return Path(sys.executable)
    return None


class AutoUpdater:
    """GitHub Releases ベースの自動アップデーター"""

    def __init__(self, current_version: str):
        self.current_version = current_version
        self.latest_version: Optional[str] = None
        self.download_url: Optional[str] = None
        self.checksum_url: Optional[str] = None
        self.release_name: Optional[str] = None

    def cleanup_old_backups(self):
        """前回のアップデートで残った.bakファイルを削除"""
        exe_path = get_exe_path()
        if not exe_path:
            return

        exe_dir = exe_path.parent
        for bak_file in exe_dir.glob("*.bak"):
            try:
                bak_file.unlink()
                logger.info(f"旧バックアップを削除: {bak_file.name}")
            except OSError:
                pass

    def check_for_updates(self) -> bool:
        """
        GitHub Releasesから最新バージョンを確認

        Returns:
            新しいバージョンがあればTrue
        """
        try:
            response = requests.get(
                f"{GITHUB_API_BASE}/releases/latest",
                headers={"Accept": "application/vnd.github.v3+json"},
                timeout=10,
            )
            if response.status_code != 200:
                logger.debug(f"GitHub API レスポンス: {response.status_code}")
                return False

            release = response.json()
            tag_name = release.get("tag_name", "")

            if not tag_name.startswith(TAG_PREFIX):
                logger.debug(f"不明なタグ形式: {tag_name}")
                return False

            latest_version = tag_name[len(TAG_PREFIX) :]
            self.latest_version = latest_version
            self.release_name = release.get("name", "")

            # ZIPアセットとチェックサムのダウンロードURLを取得
            for asset in release.get("assets", []):
                name = asset.get("name", "")
                url = asset.get("browser_download_url")
                if name.endswith(".zip"):
                    self.download_url = url
                elif name == "SHA256SUMS.txt":
                    self.checksum_url = url

            if parse_version(latest_version) > parse_version(self.current_version):
                logger.info(
                    f"新しいバージョンを検出: {latest_version} (現在: {self.current_version})"
                )
                return True

            logger.debug(f"最新バージョンです: {self.current_version}")
            return False

        except requests.RequestException as e:
            logger.debug(f"アップデート確認エラー: {e}")
            return False

    def prompt_update(self) -> bool:
        """
        アップデートを促し、ユーザーの選択を返す

        Returns:
            アップデートを実行する場合True
        """
        print("\n" + "=" * 60)
        print("  新しいバージョンが利用可能です！")
        print("=" * 60)
        print(f"\n現在のバージョン: {self.current_version}")
        if self.latest_version:
            print(f"最新バージョン:   {self.latest_version}")
        if self.release_name:
            print(f"リリース名:       {self.release_name}")
        print("\n自動アップデートを実行しますか?")
        choice = input("(Y/n): ").strip().lower()

        if choice == "n":
            return False

        return self._apply_update()

    def _apply_update(self) -> bool:
        """
        アップデートをダウンロードして適用

        Returns:
            成功した場合True（プロセス再起動するので通常は戻らない）
        """
        if not self.download_url:
            print("ダウンロードURLが取得できませんでした。")
            return False

        exe_path = get_exe_path()
        if not exe_path:
            print("開発環境ではアップデートを適用できません。")
            print(f"手動でダウンロードしてください: {self.download_url}")
            return False

        try:
            print(f"\nダウンロード中... ({self.download_url})")
            return self._download_and_replace(exe_path)
        except Exception as e:
            logger.error(f"アップデート適用エラー: {e}")
            print(f"\nアップデートに失敗しました: {e}")
            print("手動でダウンロードしてください。")
            self._rollback(exe_path)
            return False

    def _download_and_replace(self, exe_path: Path) -> bool:
        """ZIPをダウンロードし、exeを置き換えてプロセスを再起動"""
        bak_path = exe_path.with_suffix(".bak")

        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_dir_path = Path(tmp_dir)
            zip_path = tmp_dir_path / "update.zip"

            # ダウンロード（サイズ制限付き）
            response = requests.get(self.download_url, stream=True, timeout=60)
            response.raise_for_status()

            total_size = int(response.headers.get("content-length", 0))
            if total_size > MAX_UPDATE_SIZE_BYTES:
                print(f"ダウンロードサイズが上限を超えています: {total_size} bytes")
                return False

            downloaded = 0
            with open(zip_path, "wb") as f:
                for chunk in response.iter_content(chunk_size=8192):
                    f.write(chunk)
                    downloaded += len(chunk)
                    if downloaded > MAX_UPDATE_SIZE_BYTES:
                        print("\nダウンロードサイズが上限を超えました。中止します。")
                        return False
                    if total_size > 0:
                        pct = int(downloaded * 100 / total_size)
                        print(f"\r  ダウンロード: {pct}%", end="", flush=True)

            # SHA256チェックサム検証
            if not self._verify_checksum(zip_path):
                return False

            print("\n  展開中...")

            # ZIP展開（Zip Slip対策: パスがextract_dir内に収まることを検証）
            extract_dir = tmp_dir_path / "extracted"
            extract_dir.mkdir()
            with zipfile.ZipFile(zip_path, "r") as zf:
                for member in zf.namelist():
                    member_path = (extract_dir / member).resolve()
                    if not str(member_path).startswith(str(extract_dir.resolve())):
                        logger.error(f"不正なZIPエントリを検出: {member}")
                        print("更新ファイルが不正です。中止します。")
                        return False
                zf.extractall(extract_dir)

            # 期待するexe名で検索
            new_exe = None
            for f in extract_dir.rglob(EXPECTED_EXE_NAME):
                new_exe = f
                break

            if not new_exe:
                print(f"更新ファイルに{EXPECTED_EXE_NAME}が見つかりません。")
                return False

            # 実行中のexeをリネーム（Windowsでは実行中のexeを直接上書きできない）
            print("  適用中...")
            if bak_path.exists():
                bak_path.unlink()

            exe_path.rename(bak_path)

            # 新しいexeをコピー
            shutil.copy2(new_exe, exe_path)

        print(f"\n  アップデート完了！ v{self.current_version} → v{self.latest_version}")
        print("  再起動します...\n")

        # バッチスクリプトでプロセスを再起動
        self._restart_via_batch(exe_path)
        return True

    def _restart_via_batch(self, exe_path: Path):
        """バッチスクリプト経由でプロセスを再起動"""
        batch_content = f"""@echo off
timeout /t 2 /nobreak >nul
start "" "{exe_path}"
del "%~f0"
"""
        batch_path = exe_path.parent / "_restart_updater.bat"
        batch_path.write_text(batch_content, encoding="utf-8")

        subprocess.Popen(
            ["cmd", "/c", str(batch_path)],
            creationflags=subprocess.CREATE_NO_WINDOW
            if hasattr(subprocess, "CREATE_NO_WINDOW")
            else 0x08000000,
        )
        sys.exit(0)

    def _verify_checksum(self, zip_path: Path) -> bool:
        """
        SHA256SUMSファイルをダウンロードしてZIPのチェックサムを検証

        Returns:
            検証成功またはチェックサム未提供の場合True、不一致の場合False
        """
        if not self.checksum_url:
            logger.debug("SHA256SUMSアセットなし、チェックサム検証をスキップ")
            return True

        try:
            print("\n  チェックサム検証中...")
            response = requests.get(self.checksum_url, timeout=10)
            response.raise_for_status()

            # "sha256hash  filename" 形式をパース
            expected_hash = None
            for line in response.text.strip().splitlines():
                parts = line.split()
                if len(parts) >= 2 and parts[1].endswith(".zip"):
                    expected_hash = parts[0].lower()
                    break

            if not expected_hash:
                logger.warning("SHA256SUMSにZIPのハッシュが見つかりません")
                return True

            # 実際のハッシュを計算
            sha256 = hashlib.sha256()
            with open(zip_path, "rb") as f:
                for chunk in iter(lambda: f.read(8192), b""):
                    sha256.update(chunk)
            actual_hash = sha256.hexdigest().lower()

            if actual_hash != expected_hash:
                logger.error(
                    f"チェックサム不一致: expected={expected_hash}, actual={actual_hash}"
                )
                print("  チェックサム検証に失敗しました。ダウンロードが破損している可能性があります。")
                return False

            logger.info("チェックサム検証OK")
            print("  チェックサム検証OK")
            return True

        except requests.RequestException as e:
            logger.warning(f"チェックサムダウンロード失敗: {e}")
            return True

    def _rollback(self, exe_path: Path):
        """アップデート失敗時のロールバック"""
        bak_path = exe_path.with_suffix(".bak")
        if bak_path.exists() and not exe_path.exists():
            try:
                bak_path.rename(exe_path)
                logger.info("ロールバック成功")
                print("ロールバックしました。")
            except OSError as e:
                logger.error(f"ロールバック失敗: {e}")
                print(f"ロールバック失敗: {e}")
                print(f"手動で {bak_path} を {exe_path} にリネームしてください。")
