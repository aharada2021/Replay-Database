#!/usr/bin/env python3
"""
WoWS Replay Auto Uploader

World of Warshipsのリプレイファイルを自動的にアップロードするクライアント常駐ツール
"""

import os
import sys
import time
import yaml
import json
import logging
import requests
import multiprocessing
import winreg
import webbrowser
import tempfile
import subprocess
import re
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Tuple

from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import PatternMatchingEventHandler, FileCreatedEvent

# ========================================
# 定数
# ========================================

# APIエンドポイント（環境変数または設定ファイルから読み込み可能）
# デフォルトは空、セットアップ時または設定ファイルから設定される
DEFAULT_API_BASE_URL = ""  # 例: "https://wows-replay.mirage0926.com"

# バージョン情報
VERSION = "1.2.0"

# デフォルトのリプレイフォルダ
DEFAULT_REPLAYS_FOLDER = os.path.expandvars('%APPDATA%\\Wargaming.net\\WorldOfWarships\\replays')

# 設定ファイルパス
CONFIG_FILE = 'config.yaml'

# ログ設定
def setup_logging():
    """ログ設定を初期化"""
    log_file = Path(os.path.dirname(os.path.abspath(sys.argv[0]))) / 'wows_replay_uploader.log'
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return logging.getLogger(__name__)

logger = None


# ========================================
# 初回セットアップウィザード
# ========================================

class SetupWizard:
    """初回セットアップウィザード"""

    def __init__(self):
        self.config = {}

    def run(self) -> Dict[str, Any]:
        """セットアップウィザードを実行"""
        self._clear_screen()
        self._print_header()

        print("\n初回セットアップを開始します。\n")

        # API Base URL入力
        self.config['api_base_url'] = self._get_api_base_url()

        # API Key入力
        self.config['api_key'] = self._get_api_key()

        # リプレイフォルダ設定
        self.config['replays_folder'] = self._get_replays_folder()

        # Discord User ID（オプション）
        self.config['discord_user_id'] = self._get_discord_user_id()

        # スタートアップ登録
        self._prompt_startup_registration()

        # 設定を保存
        self._save_config()

        print("\n" + "=" * 60)
        print("セットアップが完了しました！")
        print("=" * 60)
        print("\nリプレイファイルの自動アップロードを開始します...")
        time.sleep(2)

        return self.config

    def _clear_screen(self):
        """画面をクリア"""
        os.system('cls' if os.name == 'nt' else 'clear')

    def _print_header(self):
        """ヘッダーを表示"""
        print("=" * 60)
        print("  WoWS Replay Auto Uploader - 初回セットアップ")
        print(f"  Version {VERSION}")
        print("=" * 60)

    def _get_api_base_url(self) -> str:
        """API Base URLを取得"""
        print("-" * 40)
        print("【ステップ 1/4】サーバーURLの設定")
        print("-" * 40)
        print("\nWoWS Replay DatabaseのサーバーURLを入力してください。")
        print("例: https://wows-replay.example.com\n")

        while True:
            api_base_url = input("サーバーURL: ").strip()
            if api_base_url and api_base_url.startswith("https://"):
                return api_base_url.rstrip("/")
            print("エラー: https:// で始まる有効なURLを入力してください。\n")

    def _get_api_key(self) -> str:
        """API Keyを取得"""
        print("\n" + "-" * 40)
        print("【ステップ 2/4】API Keyの設定")
        print("-" * 40)
        api_base_url = self.config.get('api_base_url', '')
        print(f"\nAPI Keyは {api_base_url} で取得できます。")
        print("※ Discordサーバーのメンバーである必要があります。\n")

        while True:
            api_key = input("API Key を入力してください: ").strip()
            if api_key:
                return api_key
            print("エラー: API Keyは必須です。\n")

    def _get_replays_folder(self) -> str:
        """リプレイフォルダを取得"""
        print("\n" + "-" * 40)
        print("【ステップ 3/4】リプレイフォルダの設定")
        print("-" * 40)

        # デフォルトフォルダの確認
        if os.path.exists(DEFAULT_REPLAYS_FOLDER):
            print(f"\nデフォルトのリプレイフォルダが見つかりました:")
            print(f"  {DEFAULT_REPLAYS_FOLDER}")
            choice = input("\nこのフォルダを使用しますか? (Y/n): ").strip().lower()
            if choice != 'n':
                return DEFAULT_REPLAYS_FOLDER

        # カスタムパス入力
        print("\nリプレイフォルダのパスを入力してください。")
        print("例: C:\\Games\\World_of_Warships\\replays")

        while True:
            folder = input("\nリプレイフォルダ: ").strip()
            folder = os.path.expandvars(folder)

            if os.path.exists(folder):
                return folder
            else:
                print(f"エラー: フォルダが見つかりません: {folder}")
                create = input("フォルダを作成しますか? (y/N): ").strip().lower()
                if create == 'y':
                    try:
                        os.makedirs(folder, exist_ok=True)
                        return folder
                    except Exception as e:
                        print(f"フォルダ作成エラー: {e}")

    def _get_discord_user_id(self) -> str:
        """Discord User ID を取得（オプション）"""
        print("\n" + "-" * 40)
        print("【ステップ 4/4】Discord連携（オプション）")
        print("-" * 40)
        print("\nDiscord User IDを設定すると、アップロード時にあなたのID情報が")
        print("関連付けられます。空欄でもOKです。")

        user_id = input("\nDiscord User ID (空欄可): ").strip()
        return user_id

    def _prompt_startup_registration(self):
        """スタートアップ登録を促す"""
        print("\n" + "-" * 40)
        print("【スタートアップ登録】")
        print("-" * 40)
        print("\nWindows起動時にこのツールを自動で起動するよう設定できます。")
        choice = input("スタートアップに登録しますか? (Y/n): ").strip().lower()

        if choice != 'n':
            if self._register_startup():
                print("✓ スタートアップに登録しました。")
            else:
                print("※ スタートアップ登録に失敗しました。後で手動で設定できます。")
        else:
            print("スキップしました。後からメニューで登録できます。")

    def _register_startup(self) -> bool:
        """スタートアップに登録"""
        try:
            # 実行ファイルのパスを取得
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = os.path.abspath(sys.argv[0])

            # レジストリに登録
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, "WoWSReplayUploader", 0, winreg.REG_SZ, f'"{exe_path}"')
            winreg.CloseKey(key)
            return True
        except Exception as e:
            if logger:
                logger.error(f"スタートアップ登録エラー: {e}")
            return False

    def _save_config(self):
        """設定を保存"""
        config_data = {
            'api_base_url': self.config['api_base_url'],
            'api_key': self.config['api_key'],
            'replays_folder': self.config['replays_folder'],
            'discord_user_id': self.config.get('discord_user_id', ''),
            'retry_count': 3,
            'retry_delay': 5,
            'use_polling': True
        }

        config_path = Path(os.path.dirname(os.path.abspath(sys.argv[0]))) / CONFIG_FILE
        with open(config_path, 'w', encoding='utf-8') as f:
            yaml.dump(config_data, f, allow_unicode=True, default_flow_style=False)


# ========================================
# 設定管理
# ========================================

class Config:
    """設定管理クラス"""

    DEFAULT_CONFIG = {
        'api_key': '',
        'api_base_url': DEFAULT_API_BASE_URL,
        'replays_folder': DEFAULT_REPLAYS_FOLDER,
        'discord_user_id': '',
        'retry_count': 3,
        'retry_delay': 5,
        'use_polling': True
    }

    def __init__(self):
        self.config_path = Path(os.path.dirname(os.path.abspath(sys.argv[0]))) / CONFIG_FILE
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """設定ファイルを読み込み"""
        if not self.config_path.exists():
            return None  # 初回セットアップが必要

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                if logger:
                    logger.info(f"設定ファイルを読み込みました: {self.config_path}")
                return {**self.DEFAULT_CONFIG, **config}
        except Exception as e:
            if logger:
                logger.error(f"設定ファイルの読み込みエラー: {e}")
            return None

    def is_configured(self) -> bool:
        """設定が完了しているか確認"""
        if self.config is None:
            return False
        api_key = self.config.get('api_key', '')
        api_base_url = self.config.get('api_base_url', '')
        return bool(api_key and api_key != 'YOUR_API_KEY_HERE' and api_base_url)

    def get(self, key: str, default=None):
        """設定値を取得"""
        if self.config is None:
            return default
        return self.config.get(key, default)

    def update(self, new_config: Dict[str, Any]):
        """設定を更新"""
        self.config = {**self.DEFAULT_CONFIG, **new_config}


# ========================================
# 自動アップデート
# ========================================

class AutoUpdater:
    """自動アップデートクラス"""

    def __init__(self, api_base_url: str = ""):
        self.current_version = VERSION
        self.latest_version = None
        self.download_url = None
        self.api_base_url = api_base_url
        self.version_url = f"{api_base_url}/api/download?file=uploader" if api_base_url else ""

    @staticmethod
    def parse_version(version_str: str) -> Tuple[int, ...]:
        """バージョン文字列をタプルに変換（比較用）"""
        try:
            # "1.2.0" -> (1, 2, 0)
            return tuple(int(x) for x in version_str.split('.'))
        except (ValueError, AttributeError):
            return (0, 0, 0)

    @staticmethod
    def extract_version_from_filename(filename: str) -> Optional[str]:
        """ファイル名からバージョンを抽出"""
        # 例: wows_replay_uploader-1.2.0.zip -> 1.2.0
        match = re.search(r'-(\d+\.\d+\.\d+)\.', filename)
        if match:
            return match.group(1)
        return None

    def is_newer_version(self, latest: str, current: str) -> bool:
        """最新バージョンが現在より新しいか確認"""
        latest_tuple = self.parse_version(latest)
        current_tuple = self.parse_version(current)
        return latest_tuple > current_tuple

    def check_for_updates(self) -> bool:
        """アップデートを確認。新しいバージョンがあればTrueを返す"""
        if not self.version_url:
            if logger:
                logger.debug("API base URL not configured, skipping update check")
            return False

        try:
            response = requests.get(self.version_url, timeout=10)
            if response.status_code == 200:
                data = response.json()
                download_url = data.get('url', '')
                filename = data.get('filename', '')

                # ファイル名からバージョンを抽出
                latest_version = self.extract_version_from_filename(filename)

                if latest_version:
                    self.latest_version = latest_version
                    self.download_url = download_url

                    # バージョン比較
                    if self.is_newer_version(latest_version, self.current_version):
                        if logger:
                            logger.info(f"新しいバージョンを検出: {latest_version} (現在: {self.current_version})")
                        return True
                    else:
                        if logger:
                            logger.debug(f"最新バージョンです: {self.current_version}")
                        return False
        except Exception as e:
            if logger:
                logger.debug(f"アップデート確認エラー: {e}")
        return False

    def prompt_update(self):
        """アップデートを促す"""
        print("\n" + "=" * 60)
        print("  新しいバージョンが利用可能です！")
        print("=" * 60)
        print(f"\n現在のバージョン: {self.current_version}")
        if self.latest_version:
            print(f"最新バージョン:   {self.latest_version}")
        print("\nアップデートをダウンロードしますか?")
        choice = input("(Y/n): ").strip().lower()

        if choice != 'n':
            self._download_update()

    def _download_update(self):
        """アップデートをダウンロード"""
        if not self.download_url:
            print("ダウンロードURLが取得できませんでした。")
            return

        try:
            print("\nブラウザでダウンロードページを開きます...")
            # 署名付きURLで直接ダウンロード
            webbrowser.open(self.download_url)
            print("\nダウンロード完了後、現在のアプリを終了して新しいバージョンに置き換えてください。")
        except Exception as e:
            print(f"エラー: {e}")
            print(f"\n手動でダウンロードしてください: {self.api_base_url}")


# ========================================
# スタートアップ管理
# ========================================

class StartupManager:
    """スタートアップ管理クラス"""

    REG_PATH = r"Software\Microsoft\Windows\CurrentVersion\Run"
    APP_NAME = "WoWSReplayUploader"

    @classmethod
    def is_registered(cls) -> bool:
        """スタートアップに登録されているか確認"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                cls.REG_PATH,
                0,
                winreg.KEY_READ
            )
            try:
                winreg.QueryValueEx(key, cls.APP_NAME)
                winreg.CloseKey(key)
                return True
            except FileNotFoundError:
                winreg.CloseKey(key)
                return False
        except Exception:
            return False

    @classmethod
    def register(cls) -> bool:
        """スタートアップに登録"""
        try:
            if getattr(sys, 'frozen', False):
                exe_path = sys.executable
            else:
                exe_path = os.path.abspath(sys.argv[0])

            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                cls.REG_PATH,
                0,
                winreg.KEY_SET_VALUE
            )
            winreg.SetValueEx(key, cls.APP_NAME, 0, winreg.REG_SZ, f'"{exe_path}"')
            winreg.CloseKey(key)
            return True
        except Exception as e:
            if logger:
                logger.error(f"スタートアップ登録エラー: {e}")
            return False

    @classmethod
    def unregister(cls) -> bool:
        """スタートアップから削除"""
        try:
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                cls.REG_PATH,
                0,
                winreg.KEY_SET_VALUE
            )
            winreg.DeleteValue(key, cls.APP_NAME)
            winreg.CloseKey(key)
            return True
        except Exception as e:
            if logger:
                logger.error(f"スタートアップ削除エラー: {e}")
            return False


# ========================================
# リプレイアップロード
# ========================================

class ReplayUploader:
    """リプレイアップロードクラス"""

    def __init__(self, config: Config):
        self.config = config
        self.api_base_url = config.get('api_base_url', '')
        self.api_url = f"{self.api_base_url}/api/upload"
        self.api_key = config.get('api_key')
        self.discord_user_id = config.get('discord_user_id', '')
        self.retry_count = config.get('retry_count', 3)
        self.retry_delay = config.get('retry_delay', 5)

        # アップロード履歴
        self.upload_history = []
        self.failed_uploads = []

    def upload_replay(self, file_path: Path) -> Dict[str, Any]:
        """リプレイファイルをアップロード"""
        if not file_path.exists():
            logger.error(f"ファイルが見つかりません: {file_path}")
            return {'status': 'error', 'message': 'File not found'}

        logger.info(f"アップロード開始: {file_path.name}")

        headers = {
            'X-Api-Key': self.api_key
        }

        if self.discord_user_id:
            headers['X-User-Id'] = self.discord_user_id

        for attempt in range(1, self.retry_count + 1):
            try:
                with open(file_path, 'rb') as f:
                    files = {'file': (file_path.name, f, 'application/octet-stream')}
                    response = requests.post(
                        self.api_url,
                        headers=headers,
                        files=files,
                        timeout=60
                    )

                if response.status_code == 200:
                    result = response.json()
                    logger.info(f"アップロード成功: {file_path.name}")

                    self.upload_history.append({
                        'file': file_path.name,
                        'timestamp': datetime.now().isoformat(),
                        'status': result.get('status'),
                        'arena_id': result.get('arenaUniqueID')
                    })

                    return result
                else:
                    logger.error(f"アップロード失敗 (試行 {attempt}/{self.retry_count}): HTTP {response.status_code}")
                    logger.error(f"レスポンス: {response.text}")

                    if attempt < self.retry_count:
                        logger.info(f"{self.retry_delay}秒後にリトライします...")
                        time.sleep(self.retry_delay)

            except requests.exceptions.RequestException as e:
                logger.error(f"ネットワークエラー (試行 {attempt}/{self.retry_count}): {e}")
                if attempt < self.retry_count:
                    logger.info(f"{self.retry_delay}秒後にリトライします...")
                    time.sleep(self.retry_delay)

            except Exception as e:
                logger.error(f"予期しないエラー: {e}")
                break

        self.failed_uploads.append({
            'file': str(file_path),
            'timestamp': datetime.now().isoformat()
        })

        return {'status': 'error', 'message': 'Upload failed after retries'}


# ========================================
# ファイル監視
# ========================================

class ReplayFileHandler(PatternMatchingEventHandler):
    """リプレイファイル監視ハンドラー"""

    def __init__(self, uploader: ReplayUploader):
        super().__init__(
            patterns=["*.wowsreplay"],
            ignore_patterns=["temp.wowsreplay"],
            ignore_directories=True,
            case_sensitive=False
        )
        self.uploader = uploader
        self.processing_files = set()

    def on_created(self, event: FileCreatedEvent):
        """ファイル作成イベント"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        if str(file_path) in self.processing_files:
            return

        logger.info(f"新しいリプレイファイルを検出: {file_path.name}")
        self.processing_files.add(str(file_path))

        try:
            self._wait_for_file_complete(file_path)
            result = self.uploader.upload_replay(file_path)

            if result.get('status') == 'duplicate':
                logger.warning(f"重複: このゲームは既に {result.get('originalUploader')} さんがアップロードしています")

        except Exception as e:
            logger.error(f"ファイル処理エラー: {e}")

        finally:
            self.processing_files.discard(str(file_path))

    def _wait_for_file_complete(self, file_path: Path, timeout: int = 30):
        """ファイル書き込み完了を待つ"""
        logger.debug(f"ファイル書き込み完了待機中: {file_path.name}")

        last_size = -1
        stable_count = 0
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                current_size = file_path.stat().st_size
                if current_size == last_size:
                    stable_count += 1
                    if stable_count >= 5:
                        logger.debug(f"ファイル書き込み完了: {file_path.name}")
                        return
                else:
                    stable_count = 0
                    last_size = current_size
                time.sleep(1)
            except FileNotFoundError:
                logger.warning(f"ファイルが見つかりません: {file_path}")
                return

        logger.warning(f"タイムアウト: {file_path.name}")


class ReplayMonitor:
    """リプレイフォルダ監視クラス"""

    def __init__(self, config: Config):
        self.config = config
        self.replays_folder = config.get('replays_folder')
        self.uploader = ReplayUploader(config)
        self.observer = None

    def start(self):
        """監視を開始"""
        if not os.path.exists(self.replays_folder):
            logger.error(f"リプレイフォルダが見つかりません: {self.replays_folder}")
            return

        logger.info(f"リプレイフォルダを監視開始: {self.replays_folder}")
        logger.info(f"API URL: {self.uploader.api_url}")

        use_polling = self.config.get('use_polling', True)
        if use_polling:
            logger.info("PollingObserverを使用します")
            self.observer = PollingObserver()
        else:
            self.observer = Observer()

        event_handler = ReplayFileHandler(self.uploader)
        self.observer.schedule(event_handler, self.replays_folder, recursive=False)
        self.observer.start()

        try:
            while True:
                time.sleep(10)
        except KeyboardInterrupt:
            logger.info("監視を停止します...")
            self.observer.stop()

        self.observer.join()
        logger.info("監視を終了しました")


# ========================================
# メイン
# ========================================

def main():
    """メイン関数"""
    global logger

    # PyInstallerでのマルチプロセシング対応
    multiprocessing.freeze_support()

    # ログ設定
    logger = setup_logging()

    logger.info("=" * 60)
    logger.info(f"WoWS Replay Auto Uploader v{VERSION}")
    logger.info("=" * 60)

    # 設定を読み込み
    config = Config()

    # 初回セットアップが必要か確認
    if not config.is_configured():
        wizard = SetupWizard()
        new_config = wizard.run()
        config.update(new_config)

    # アップデート確認
    api_base_url = config.get('api_base_url', '')
    updater = AutoUpdater(api_base_url)
    if updater.check_for_updates():
        updater.prompt_update()

    # スタートアップ登録状態を確認
    if not StartupManager.is_registered():
        print("\n※ スタートアップに登録されていません。")
        print("  Windows起動時に自動で起動させたい場合は、後から設定できます。\n")

    # 監視開始
    monitor = ReplayMonitor(config)
    monitor.start()


if __name__ == '__main__':
    main()
