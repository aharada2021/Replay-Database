#!/usr/bin/env python3
"""
WoWS Replay Auto Uploader

World of Warshipsのリプレイファイルを自動的にアップロードするクライアント常駐ツール
ゲームプレイキャプチャ機能も含む
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
import threading
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any, Tuple, Callable

from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import PatternMatchingEventHandler, FileCreatedEvent, FileDeletedEvent

# Capture module (optional - may not be available on non-Windows systems)
try:
    from capture import CaptureConfig, GameCaptureManager
    from capture.manager import load_arena_info

    CAPTURE_AVAILABLE = True
except ImportError:
    CAPTURE_AVAILABLE = False

# ========================================
# 定数
# ========================================

# APIエンドポイント（環境変数または設定ファイルから読み込み可能）
# デフォルトは空、セットアップ時または設定ファイルから設定される
DEFAULT_API_BASE_URL = ""  # 例: "https://your-server.example.com"

# ゲームプレイ動画アップロード設定
DEFAULT_MAX_UPLOAD_SIZE_MB = 500  # デフォルト最大アップロードサイズ(MB)

# バージョン情報
VERSION = "1.3.0"

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

        # キャプチャ設定（オプション）
        self.config['capture'] = self._get_capture_settings()

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
        print("steam版: D:\\SteamLibrary\\steamapps\\common\\World of Warships\\replays")

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
        print("【ステップ 4/5】Discord連携（オプション）")
        print("-" * 40)
        print("\nDiscord User IDを設定すると、アップロード時にあなたのID情報が")
        print("関連付けられます。空欄でもOKです。")

        user_id = input("\nDiscord User ID (空欄可): ").strip()
        return user_id

    def _get_capture_settings(self) -> Dict[str, Any]:
        """キャプチャ設定を取得（オプション）"""
        print("\n" + "-" * 40)
        print("【ステップ 5/5】ゲームキャプチャ設定（オプション）")
        print("-" * 40)

        if not CAPTURE_AVAILABLE:
            print("\n※ キャプチャ機能は現在利用できません。")
            print("  必要なライブラリがインストールされていません。")
            return {'enabled': False}

        print("\n試合中のゲームプレイを自動的に録画できます。")
        print("録画は試合開始時に自動的に開始され、終了時に停止します。")

        choice = input("\nキャプチャ機能を有効にしますか? (y/N): ").strip().lower()

        if choice != 'y':
            print("キャプチャ機能を無効にしました。")
            return {'enabled': False}

        # 保存先フォルダ
        default_folder = os.path.expandvars('%USERPROFILE%\\Videos\\WoWS Captures')
        print(f"\n録画ファイルの保存先 (デフォルト: {default_folder})")
        output_folder = input("保存先フォルダ (空欄でデフォルト): ").strip()
        if not output_folder:
            output_folder = default_folder

        # 品質設定
        print("\n録画品質を選択してください:")
        print("  1. low    - ファイルサイズ小、CPU負荷軽い")
        print("  2. medium - バランス型（推奨）")
        print("  3. high   - 高品質、ファイルサイズ大")

        quality_choice = input("品質 (1/2/3、デフォルト: 2): ").strip()
        quality_map = {'1': 'low', '2': 'medium', '3': 'high'}
        video_quality = quality_map.get(quality_choice, 'medium')

        # オーディオ設定
        capture_audio = input("\nデスクトップ音声を録音しますか? (Y/n): ").strip().lower() != 'n'
        capture_mic = False
        if capture_audio:
            capture_mic = input("マイク入力も録音しますか? (y/N): ").strip().lower() == 'y'

        # 動画アップロード設定
        print("\n--- 動画アップロード設定 ---")
        print("録画したゲームプレイ動画をサーバーにアップロードできます。")
        print("アップロードすると、Webサイトで視聴可能になります。")
        upload_gameplay_video = input("\nゲームプレイ動画をアップロードしますか? (Y/n): ").strip().lower() != 'n'

        keep_local_copy = False
        max_upload_size_mb = DEFAULT_MAX_UPLOAD_SIZE_MB
        if upload_gameplay_video:
            keep_local_copy = input("アップロード後もローカルコピーを保持しますか? (y/N): ").strip().lower() == 'y'
            print(f"\n最大アップロードサイズ (デフォルト: {DEFAULT_MAX_UPLOAD_SIZE_MB}MB)")
            size_input = input("最大サイズ (MB, 空欄でデフォルト): ").strip()
            if size_input:
                try:
                    max_upload_size_mb = int(size_input)
                except ValueError:
                    print(f"無効な値です。デフォルト ({DEFAULT_MAX_UPLOAD_SIZE_MB}MB) を使用します。")

        print("\n✓ キャプチャ設定が完了しました。")

        return {
            'enabled': True,
            'output_folder': output_folder,
            'video_quality': video_quality,
            'capture_audio': capture_audio,
            'capture_microphone': capture_mic,
            'target_fps': 30,
            'max_duration_minutes': 30,
            'upload_gameplay_video': upload_gameplay_video,
            'keep_local_copy': keep_local_copy,
            'max_upload_size_mb': max_upload_size_mb,
        }

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
            'use_polling': True,
            'capture': self.config.get('capture', {'enabled': False}),
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

# ========================================
# 動画トラッキング
# ========================================

class PendingVideoQueue:
    """キャプチャした動画ファイルを対応するリプレイファイルに関連付けるクラス"""

    def __init__(self):
        self.pending: Dict[str, Path] = {}  # arena_hash -> video_path
        self._lock = threading.Lock()

    def add_video(self, arena_hash: str, video_path: Path):
        """
        動画ファイルをキューに追加

        Args:
            arena_hash: アリーナ識別子（tempArenaInfo.jsonから取得）
            video_path: 動画ファイルのパス
        """
        with self._lock:
            self.pending[arena_hash] = video_path
            if logger:
                logger.info(f"動画をキューに追加: {arena_hash} -> {video_path}")

    def get_video_for_replay(self, replay_path: Path) -> Optional[Path]:
        """
        リプレイファイルに対応する動画ファイルを取得

        Args:
            replay_path: リプレイファイルのパス

        Returns:
            対応する動画ファイルのパス（なければNone）

        Note:
            現在の実装では、最後に追加された動画を返すシンプルな方式を採用。
            通常の使用パターン（1試合ずつプレイ）では問題ないが、
            複数の試合を短時間に連続でプレイした場合は動画の対応がずれる可能性がある。
            将来的にはリプレイファイルの内容からarena情報を抽出して
            正確にマッチングすることが望ましい。
        """
        with self._lock:
            if not self.pending:
                return None

            # 最後に追加された動画を返す
            # TODO: リプレイファイルからarenaUniqueIDを抽出して正確にマッチングする
            arena_hash = list(self.pending.keys())[-1]
            video_path = self.pending.pop(arena_hash, None)

            if video_path and video_path.exists():
                if logger:
                    logger.info(f"リプレイに動画を関連付け: {replay_path.name} -> {video_path}")
                return video_path

            return None

    def get_video_by_hash(self, arena_hash: str) -> Optional[Path]:
        """
        アリーナハッシュで動画ファイルを取得

        Args:
            arena_hash: アリーナ識別子

        Returns:
            動画ファイルのパス（なければNone）
        """
        with self._lock:
            video_path = self.pending.pop(arena_hash, None)
            if video_path and video_path.exists():
                return video_path
            return None

    def cleanup_old_entries(self, max_age_seconds: int = 3600):
        """
        古いエントリをクリーンアップ

        Args:
            max_age_seconds: この秒数より古いエントリを削除
        """
        with self._lock:
            current_time = time.time()
            to_remove = []

            for arena_hash, video_path in self.pending.items():
                if video_path.exists():
                    file_age = current_time - video_path.stat().st_mtime
                    if file_age > max_age_seconds:
                        to_remove.append(arena_hash)
                else:
                    to_remove.append(arena_hash)

            for arena_hash in to_remove:
                del self.pending[arena_hash]
                if logger:
                    logger.debug(f"古い動画エントリを削除: {arena_hash}")


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

        # ゲームプレイ動画設定
        capture_config = config.get('capture', {})
        self.upload_gameplay_video = capture_config.get('upload_gameplay_video', True)
        self.keep_local_copy = capture_config.get('keep_local_copy', False)
        self.max_upload_size_mb = capture_config.get('max_upload_size_mb', DEFAULT_MAX_UPLOAD_SIZE_MB)

        # アップロード履歴
        self.upload_history = []
        self.failed_uploads = []

    def upload_replay(
        self,
        file_path: Path,
        video_path: Optional[Path] = None
    ) -> Dict[str, Any]:
        """
        リプレイファイルをアップロード

        Args:
            file_path: リプレイファイルのパス
            video_path: ゲームプレイ動画のパス（オプション）

        Returns:
            アップロード結果
        """
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
                        'arena_id': result.get('tempArenaID')
                    })

                    # ゲームプレイ動画をアップロード
                    if video_path and self.upload_gameplay_video:
                        video_upload_url = result.get('videoUploadUrl')
                        if video_upload_url:
                            self._upload_gameplay_video(
                                video_path,
                                video_upload_url,
                                result.get('videoS3Key'),
                                result.get('tempArenaID'),
                                result.get('playerID')
                            )

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

    def _upload_gameplay_video(
        self,
        video_path: Path,
        upload_url: str,
        s3_key: str,
        arena_unique_id: str,
        player_id: int
    ) -> bool:
        """
        ゲームプレイ動画をS3にアップロード

        Args:
            video_path: 動画ファイルのパス
            upload_url: Presigned PUT URL
            s3_key: S3キー
            arena_unique_id: アリーナユニークID
            player_id: プレイヤーID

        Returns:
            成功した場合True
        """
        if not video_path.exists():
            logger.warning(f"動画ファイルが見つかりません: {video_path}")
            return False

        # ファイルサイズ
        file_size = video_path.stat().st_size
        file_size_mb = file_size / (1024 * 1024)

        if file_size_mb > self.max_upload_size_mb:
            logger.warning(
                f"動画ファイルが大きすぎます: {file_size_mb:.1f}MB "
                f"(上限: {self.max_upload_size_mb}MB)"
            )
            return False

        logger.info(f"ゲームプレイ動画アップロード開始: {video_path.name} ({file_size_mb:.1f}MB)")

        for attempt in range(1, self.retry_count + 1):
            try:
                with open(video_path, 'rb') as f:
                    # プログレス表示付きでアップロード
                    response = requests.put(
                        upload_url,
                        data=self._upload_with_progress(f, file_size),
                        headers={'Content-Type': 'video/mp4'},
                        timeout=600  # 10分タイムアウト（大きいファイル用）
                    )

                if response.status_code in (200, 204):
                    logger.info(f"動画アップロード成功: {s3_key}")

                    # サーバーに完了通知を送信
                    self._notify_video_upload_complete(
                        arena_unique_id, player_id, s3_key, file_size
                    )

                    # ローカルコピーを削除（設定による）
                    if not self.keep_local_copy:
                        try:
                            video_path.unlink()
                            logger.info(f"ローカル動画ファイルを削除: {video_path}")
                        except Exception as e:
                            logger.warning(f"ローカル動画ファイル削除エラー: {e}")

                    return True
                else:
                    logger.error(
                        f"動画アップロード失敗 (試行 {attempt}/{self.retry_count}): "
                        f"HTTP {response.status_code}"
                    )

                    if attempt < self.retry_count:
                        logger.info(f"{self.retry_delay}秒後にリトライします...")
                        time.sleep(self.retry_delay)

            except requests.exceptions.RequestException as e:
                logger.error(f"動画アップロードネットワークエラー (試行 {attempt}/{self.retry_count}): {e}")
                if attempt < self.retry_count:
                    logger.info(f"{self.retry_delay}秒後にリトライします...")
                    time.sleep(self.retry_delay)

            except Exception as e:
                logger.error(f"動画アップロード予期しないエラー: {e}")
                break

        logger.error(f"動画アップロード失敗: {video_path}")
        return False

    def _notify_video_upload_complete(
        self,
        arena_unique_id: str,
        player_id: int,
        s3_key: str,
        file_size: int
    ):
        """
        動画アップロード完了をサーバーに通知

        Args:
            arena_unique_id: アリーナユニークID
            player_id: プレイヤーID
            s3_key: S3キー
            file_size: ファイルサイズ（バイト）
        """
        try:
            video_complete_url = f"{self.api_base_url}/api/upload/video-complete"

            response = requests.post(
                video_complete_url,
                headers={
                    'X-Api-Key': self.api_key,
                    'Content-Type': 'application/json'
                },
                json={
                    'arenaUniqueID': arena_unique_id,
                    'playerID': player_id,
                    'videoS3Key': s3_key,
                    'fileSize': file_size
                },
                timeout=30
            )

            if response.status_code == 200:
                logger.info("動画アップロード完了通知成功")
            elif response.status_code == 202:
                logger.info("動画アップロード完了通知: 試合データ処理待ち")
            else:
                logger.warning(f"動画アップロード完了通知失敗: HTTP {response.status_code}")

        except Exception as e:
            logger.warning(f"動画アップロード完了通知エラー: {e}")

    def _upload_with_progress(self, file_obj, total_size: int):
        """
        プログレス表示付きでファイルを読み込むジェネレータ

        Args:
            file_obj: ファイルオブジェクト
            total_size: 総バイト数

        Yields:
            ファイルデータのチャンク
        """
        chunk_size = 1024 * 1024  # 1MB chunks
        uploaded = 0
        last_progress = 0

        while True:
            chunk = file_obj.read(chunk_size)
            if not chunk:
                break

            uploaded += len(chunk)
            progress = int(uploaded / total_size * 100)

            # 10%ごとにログ出力
            if progress >= last_progress + 10:
                logger.info(f"動画アップロード進捗: {progress}%")
                last_progress = progress

            yield chunk


# ========================================
# ファイル監視
# ========================================

class ReplayFileHandler(PatternMatchingEventHandler):
    """リプレイファイル監視ハンドラー"""

    def __init__(
        self,
        uploader: ReplayUploader,
        capture_manager: Optional["GameCaptureManager"] = None,
        pending_video_queue: Optional[PendingVideoQueue] = None,
    ):
        super().__init__(
            patterns=["*.wowsreplay"],
            ignore_patterns=["temp.wowsreplay"],
            ignore_directories=True,
            case_sensitive=False
        )
        self.uploader = uploader
        self.capture_manager = capture_manager
        self.pending_video_queue = pending_video_queue
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

        video_path = None

        try:
            # キャプチャを停止し、動画パスを取得
            if self.capture_manager is not None:
                if self.capture_manager.is_running():
                    logger.info("試合終了を検出、キャプチャを停止します...")
                    video_path = self.capture_manager.stop_capture()
                    if video_path is not None:
                        logger.info(f"録画ファイルを保存しました: {video_path}")
                elif self.capture_manager.is_waiting_for_window():
                    logger.info("ウィンドウ検索をキャンセルします...")
                    self.capture_manager.stop_capture()

            # pending_video_queueから動画を取得（キャプチャマネージャーから取れなかった場合）
            if video_path is None and self.pending_video_queue is not None:
                video_path = self.pending_video_queue.get_video_for_replay(file_path)
                if video_path:
                    logger.info(f"キューから動画を取得: {video_path}")

            self._wait_for_file_complete(file_path)
            result = self.uploader.upload_replay(file_path, video_path=video_path)

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


class GameCaptureFileHandler(PatternMatchingEventHandler):
    """tempArenaInfo.json監視ハンドラー（キャプチャ開始用）"""

    def __init__(self, capture_manager: "GameCaptureManager", replays_folder: str):
        super().__init__(
            patterns=["tempArenaInfo.json"],
            ignore_directories=True,
            case_sensitive=False
        )
        self.capture_manager = capture_manager
        self.replays_folder = Path(replays_folder)

    def on_created(self, event: FileCreatedEvent):
        """tempArenaInfo.json作成を検出（試合開始）"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)
        logger.info(f"試合開始を検出: {file_path.name}")

        try:
            time.sleep(0.5)

            arena_info = None
            try:
                arena_info = load_arena_info(file_path)
                if arena_info:
                    map_name = arena_info.get('mapDisplayName', 'Unknown')
                    game_mode = arena_info.get('gameLogic', 'Unknown')
                    logger.info(f"マップ: {map_name}, モード: {game_mode}")
            except Exception as e:
                logger.warning(f"アリーナ情報の読み込みに失敗: {e}")

            if not self.capture_manager.is_running():
                logger.info("ゲームキャプチャを開始します...")
                self.capture_manager.start_capture(arena_info=arena_info, wait_for_window=True)
            else:
                logger.warning("キャプチャは既に実行中です")

        except Exception as e:
            logger.error(f"キャプチャ開始エラー: {e}")

    def on_deleted(self, event: FileDeletedEvent):
        """tempArenaInfo.json削除を検出（試合終了のバックアップ検出）"""
        if event.is_directory:
            return

        logger.debug(f"tempArenaInfo.json削除を検出")


class ReplayMonitor:
    """リプレイフォルダ監視クラス"""

    def __init__(self, config: Config):
        self.config = config
        self.replays_folder = config.get('replays_folder')
        self.uploader = ReplayUploader(config)
        self.observer = None
        self.capture_manager: Optional["GameCaptureManager"] = None
        self.pending_video_queue = PendingVideoQueue()

        self._init_capture()

    def _init_capture(self):
        """キャプチャ機能を初期化"""
        if not CAPTURE_AVAILABLE:
            logger.info("キャプチャモジュールが利用できません")
            return

        capture_config_data = self.config.get('capture', {})

        if not capture_config_data.get('enabled', False):
            logger.info("キャプチャ機能は無効です")
            return

        try:
            capture_config = CaptureConfig.from_dict({'capture': capture_config_data})

            self.capture_manager = GameCaptureManager(capture_config)

            if self.capture_manager.is_available():
                logger.info("キャプチャ機能が有効です")
                logger.info(f"録画保存先: {capture_config.output_folder}")

                # 動画アップロード設定を表示
                upload_video = capture_config_data.get('upload_gameplay_video', True)
                logger.info(f"動画アップロード: {'有効' if upload_video else '無効'}")
            else:
                logger.warning("キャプチャ機能は利用できません（FFmpegが見つかりません）")
                self.capture_manager = None
        except Exception as e:
            logger.error(f"キャプチャ初期化エラー: {e}")
            self.capture_manager = None

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

        # リプレイファイル監視ハンドラー
        replay_handler = ReplayFileHandler(
            self.uploader,
            self.capture_manager,
            self.pending_video_queue
        )
        self.observer.schedule(replay_handler, self.replays_folder, recursive=False)

        # キャプチャ開始用のtempArenaInfo.json監視ハンドラー
        if self.capture_manager is not None:
            capture_handler = GameCaptureFileHandler(
                self.capture_manager, self.replays_folder
            )
            self.observer.schedule(capture_handler, self.replays_folder, recursive=False)
            logger.info("ゲームキャプチャ監視を開始しました")

        self.observer.start()

        try:
            while True:
                time.sleep(10)
                # 古い動画エントリをクリーンアップ（1時間以上経過したもの）
                self.pending_video_queue.cleanup_old_entries(max_age_seconds=3600)
        except KeyboardInterrupt:
            logger.info("監視を停止します...")

            # キャプチャを停止
            if self.capture_manager is not None and self.capture_manager.is_running():
                logger.info("キャプチャを停止します...")
                self.capture_manager.stop_capture()

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
