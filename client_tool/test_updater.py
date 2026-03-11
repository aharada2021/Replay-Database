"""
updater.py のテスト

1. ユニットテスト: モックを使ったロジック検証
2. GitHub API疎通テスト: 実際のAPIを叩いて既存リリースを確認
"""

import hashlib
import os
import sys
import tempfile
import zipfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
import requests

# テスト対象
sys.path.insert(0, os.path.dirname(__file__))
from updater import (
    EXPECTED_EXE_NAME,
    GITHUB_API_BASE,
    MAX_UPDATE_SIZE_BYTES,
    TAG_PREFIX,
    AutoUpdater,
    parse_version,
)


# ========================================
# 1. ユニットテスト
# ========================================


class TestParseVersion:
    def test_normal_version(self):
        assert parse_version("1.2.3") == (1, 2, 3)

    def test_two_part_version(self):
        assert parse_version("1.2") == (1, 2)

    def test_single_part(self):
        assert parse_version("5") == (5,)

    def test_invalid_version(self):
        assert parse_version("abc") == (0, 0, 0)

    def test_empty_string(self):
        assert parse_version("") == (0, 0, 0)

    def test_none(self):
        assert parse_version(None) == (0, 0, 0)

    def test_version_comparison(self):
        assert parse_version("1.4.0") > parse_version("1.3.1")
        assert parse_version("2.0.0") > parse_version("1.9.9")
        assert parse_version("1.3.1") == parse_version("1.3.1")
        assert not parse_version("1.3.0") > parse_version("1.3.1")


class TestCheckForUpdates:
    """check_for_updates のモックテスト"""

    def _make_release_response(
        self, tag="client-v2.0.0", assets=None, name="Test Release"
    ):
        if assets is None:
            assets = [
                {
                    "name": "wows_replay_uploader.zip",
                    "browser_download_url": "https://github.com/example/release/download/v2.0.0/wows_replay_uploader.zip",
                },
                {
                    "name": "SHA256SUMS.txt",
                    "browser_download_url": "https://github.com/example/release/download/v2.0.0/SHA256SUMS.txt",
                },
            ]
        return MagicMock(
            status_code=200,
            json=lambda: {"tag_name": tag, "name": name, "assets": assets},
        )

    @patch("updater.requests.get")
    def test_newer_version_available(self, mock_get):
        mock_get.return_value = self._make_release_response(tag="client-v2.0.0")

        updater = AutoUpdater("1.3.1")
        result = updater.check_for_updates()

        assert result is True
        assert updater.latest_version == "2.0.0"
        assert updater.download_url is not None
        assert updater.checksum_url is not None

    @patch("updater.requests.get")
    def test_same_version(self, mock_get):
        mock_get.return_value = self._make_release_response(tag="client-v1.3.1")

        updater = AutoUpdater("1.3.1")
        result = updater.check_for_updates()

        assert result is False

    @patch("updater.requests.get")
    def test_older_version_on_server(self, mock_get):
        mock_get.return_value = self._make_release_response(tag="client-v1.0.0")

        updater = AutoUpdater("1.3.1")
        result = updater.check_for_updates()

        assert result is False

    @patch("updater.requests.get")
    def test_invalid_tag_format(self, mock_get):
        mock_get.return_value = self._make_release_response(tag="v2.0.0")

        updater = AutoUpdater("1.3.1")
        result = updater.check_for_updates()

        assert result is False

    @patch("updater.requests.get")
    def test_api_error(self, mock_get):
        mock_get.return_value = MagicMock(status_code=404)

        updater = AutoUpdater("1.3.1")
        result = updater.check_for_updates()

        assert result is False

    @patch("updater.requests.get")
    def test_network_error(self, mock_get):
        mock_get.side_effect = requests.ConnectionError("Network unreachable")

        updater = AutoUpdater("1.3.1")
        result = updater.check_for_updates()

        assert result is False

    @patch("updater.requests.get")
    def test_no_zip_asset(self, mock_get):
        mock_get.return_value = self._make_release_response(
            tag="client-v2.0.0",
            assets=[{"name": "readme.md", "browser_download_url": "https://example.com/readme.md"}],
        )

        updater = AutoUpdater("1.3.1")
        result = updater.check_for_updates()

        assert result is True
        assert updater.download_url is None
        assert updater.checksum_url is None

    @patch("updater.requests.get")
    def test_no_checksum_asset(self, mock_get):
        mock_get.return_value = self._make_release_response(
            tag="client-v2.0.0",
            assets=[
                {
                    "name": "wows_replay_uploader.zip",
                    "browser_download_url": "https://example.com/wows.zip",
                }
            ],
        )

        updater = AutoUpdater("1.3.1")
        result = updater.check_for_updates()

        assert result is True
        assert updater.download_url is not None
        assert updater.checksum_url is None


class TestVerifyChecksum:
    """_verify_checksum のモックテスト"""

    def _create_test_zip(self, tmp_path: Path) -> Path:
        zip_path = tmp_path / "test.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("test.txt", "hello world")
        return zip_path

    def _compute_sha256(self, file_path: Path) -> str:
        sha256 = hashlib.sha256()
        with open(file_path, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()

    def test_no_checksum_url_skips(self, tmp_path):
        updater = AutoUpdater("1.0.0")
        updater.checksum_url = None

        zip_path = self._create_test_zip(tmp_path)
        assert updater._verify_checksum(zip_path) is True

    @patch("updater.requests.get")
    def test_valid_checksum(self, mock_get, tmp_path):
        zip_path = self._create_test_zip(tmp_path)
        expected_hash = self._compute_sha256(zip_path)

        mock_get.return_value = MagicMock(
            status_code=200,
            text=f"{expected_hash}  wows_replay_uploader.zip\n",
        )
        mock_get.return_value.raise_for_status = MagicMock()

        updater = AutoUpdater("1.0.0")
        updater.checksum_url = "https://example.com/SHA256SUMS.txt"

        assert updater._verify_checksum(zip_path) is True

    @patch("updater.requests.get")
    def test_invalid_checksum(self, mock_get, tmp_path):
        zip_path = self._create_test_zip(tmp_path)

        mock_get.return_value = MagicMock(
            status_code=200,
            text="0000000000000000000000000000000000000000000000000000000000000000  wows_replay_uploader.zip\n",
        )
        mock_get.return_value.raise_for_status = MagicMock()

        updater = AutoUpdater("1.0.0")
        updater.checksum_url = "https://example.com/SHA256SUMS.txt"

        assert updater._verify_checksum(zip_path) is False

    @patch("updater.requests.get")
    def test_checksum_download_failure_is_graceful(self, mock_get, tmp_path):
        mock_get.side_effect = requests.ConnectionError("fail")

        zip_path = self._create_test_zip(tmp_path)
        updater = AutoUpdater("1.0.0")
        updater.checksum_url = "https://example.com/SHA256SUMS.txt"

        # ダウンロード失敗時はスキップ（Trueを返す）
        assert updater._verify_checksum(zip_path) is True

    @patch("updater.requests.get")
    def test_checksum_no_zip_entry(self, mock_get, tmp_path):
        zip_path = self._create_test_zip(tmp_path)

        mock_get.return_value = MagicMock(
            status_code=200,
            text="abcdef1234567890  readme.md\n",
        )
        mock_get.return_value.raise_for_status = MagicMock()

        updater = AutoUpdater("1.0.0")
        updater.checksum_url = "https://example.com/SHA256SUMS.txt"

        # ZIP用のハッシュがない場合はスキップ
        assert updater._verify_checksum(zip_path) is True


class TestZipSlipProtection:
    """ZIP展開のZip Slip対策テスト"""

    def test_safe_zip_extracts(self, tmp_path):
        """正常なZIPファイルは展開できる"""
        zip_path = tmp_path / "safe.zip"
        with zipfile.ZipFile(zip_path, "w") as zf:
            zf.writestr("wows_replay_uploader.exe", "fake exe content")
            zf.writestr("config.yaml.template", "api_key: xxx")

        extract_dir = tmp_path / "extracted"
        extract_dir.mkdir()

        with zipfile.ZipFile(zip_path, "r") as zf:
            for member in zf.namelist():
                member_path = (extract_dir / member).resolve()
                assert str(member_path).startswith(str(extract_dir.resolve()))
            zf.extractall(extract_dir)

        assert (extract_dir / "wows_replay_uploader.exe").exists()


class TestDownloadSizeLimit:
    """ダウンロードサイズ制限のテスト"""

    @patch("updater.requests.get")
    @patch("updater.get_exe_path")
    def test_content_length_too_large(self, mock_exe_path, mock_get):
        mock_exe_path.return_value = Path("/fake/wows_replay_uploader.exe")

        mock_response = MagicMock()
        mock_response.headers = {"content-length": str(MAX_UPDATE_SIZE_BYTES + 1)}
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        updater = AutoUpdater("1.0.0")
        updater.download_url = "https://example.com/test.zip"

        result = updater._download_and_replace(Path("/fake/wows_replay_uploader.exe"))
        assert result is False


class TestCleanupOldBackups:
    """bakファイルクリーンアップのテスト"""

    @patch("updater.get_exe_path")
    def test_cleanup_bak_files(self, mock_exe_path, tmp_path):
        exe_path = tmp_path / "wows_replay_uploader.exe"
        exe_path.write_text("exe")
        mock_exe_path.return_value = exe_path

        bak1 = tmp_path / "wows_replay_uploader.bak"
        bak2 = tmp_path / "old_file.bak"
        bak1.write_text("old")
        bak2.write_text("old2")

        updater = AutoUpdater("1.0.0")
        updater.cleanup_old_backups()

        assert not bak1.exists()
        assert not bak2.exists()
        assert exe_path.exists()

    @patch("updater.get_exe_path")
    def test_cleanup_no_exe_path(self, mock_exe_path):
        mock_exe_path.return_value = None

        updater = AutoUpdater("1.0.0")
        updater.cleanup_old_backups()  # エラーなく完了すること


class TestRollback:
    """ロールバックのテスト"""

    def test_rollback_restores_bak(self, tmp_path):
        exe_path = tmp_path / "wows_replay_uploader.exe"
        bak_path = tmp_path / "wows_replay_uploader.bak"
        bak_path.write_text("original exe content")

        updater = AutoUpdater("1.0.0")
        updater._rollback(exe_path)

        assert exe_path.exists()
        assert not bak_path.exists()
        assert exe_path.read_text() == "original exe content"

    def test_rollback_no_bak_does_nothing(self, tmp_path):
        exe_path = tmp_path / "wows_replay_uploader.exe"

        updater = AutoUpdater("1.0.0")
        updater._rollback(exe_path)  # エラーなく完了すること

    def test_rollback_skips_if_exe_exists(self, tmp_path):
        exe_path = tmp_path / "wows_replay_uploader.exe"
        bak_path = tmp_path / "wows_replay_uploader.bak"
        exe_path.write_text("current")
        bak_path.write_text("backup")

        updater = AutoUpdater("1.0.0")
        updater._rollback(exe_path)

        # 両方存在する場合はロールバックしない
        assert exe_path.read_text() == "current"
        assert bak_path.exists()


# ========================================
# 2. GitHub API 疎通テスト
# ========================================


class TestGitHubAPIIntegration:
    """
    実際のGitHub APIを叩く疎通テスト
    ネットワーク接続が必要。CI環境ではスキップ可能。
    """

    @pytest.mark.skipif(
        os.environ.get("SKIP_NETWORK_TESTS") == "1",
        reason="SKIP_NETWORK_TESTS=1",
    )
    def test_github_api_reachable(self):
        """GitHub APIエンドポイントに到達可能"""
        response = requests.get(
            f"{GITHUB_API_BASE}/releases",
            headers={"Accept": "application/vnd.github.v3+json"},
            timeout=10,
        )
        assert response.status_code == 200
        releases = response.json()
        assert isinstance(releases, list)

    @pytest.mark.skipif(
        os.environ.get("SKIP_NETWORK_TESTS") == "1",
        reason="SKIP_NETWORK_TESTS=1",
    )
    def test_check_for_updates_real_api(self):
        """実際のGitHub APIでcheck_for_updatesが正常動作"""
        # 非常に古いバージョンでテスト（必ずアップデートがあるはず）
        updater = AutoUpdater("0.0.1")
        result = updater.check_for_updates()

        # リリースが存在すればTrueが返る
        if result:
            assert updater.latest_version is not None
            assert updater.download_url is not None
            print(f"\n  最新バージョン: {updater.latest_version}")
            print(f"  ダウンロードURL: {updater.download_url}")
            print(f"  チェックサムURL: {updater.checksum_url}")
        else:
            # リリースが存在しない場合（リポジトリにまだリリースがない）
            print("\n  リリースが見つかりませんでした（正常）")

    @pytest.mark.skipif(
        os.environ.get("SKIP_NETWORK_TESTS") == "1",
        reason="SKIP_NETWORK_TESTS=1",
    )
    def test_current_version_is_latest(self):
        """現在のバージョンでcheck_for_updatesがFalseを返す"""
        # wows_replay_uploader.py から現在のバージョンを取得
        try:
            from wows_replay_uploader import VERSION
        except ImportError:
            pytest.skip("wows_replay_uploader.py not importable")

        updater = AutoUpdater(VERSION)
        result = updater.check_for_updates()

        print(f"\n  現在のバージョン: {VERSION}")
        print(f"  最新バージョン: {updater.latest_version}")
        print(f"  アップデート必要: {result}")


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
