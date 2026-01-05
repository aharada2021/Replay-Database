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
from pathlib import Path
from datetime import datetime
from typing import Optional, Dict, Any
from watchdog.observers import Observer
from watchdog.observers.polling import PollingObserver
from watchdog.events import PatternMatchingEventHandler, FileCreatedEvent

# ログ設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('wows_replay_uploader.log', encoding='utf-8'),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


class Config:
    """設定管理クラス"""

    DEFAULT_CONFIG = {
        'api_url': 'https://874mutasbd.execute-api.ap-northeast-1.amazonaws.com/api/upload',
        'api_key': 'YOUR_API_KEY_HERE',
        'replays_folder': os.path.expandvars('%APPDATA%\\Wargaming.net\\WorldOfWarships\\replays'),
        'auto_start': True,
        'discord_user_id': '',
        'retry_count': 3,
        'retry_delay': 5,
        'use_polling': True  # PollingObserverを使用（安定性向上）
    }

    def __init__(self, config_path: str = 'config.yaml'):
        self.config_path = config_path
        self.config = self._load_config()

    def _load_config(self) -> Dict[str, Any]:
        """設定ファイルを読み込み"""
        if not os.path.exists(self.config_path):
            logger.warning(f"設定ファイルが見つかりません: {self.config_path}")
            logger.info("デフォルト設定で新規作成します")
            self._create_default_config()
            return self.DEFAULT_CONFIG.copy()

        try:
            with open(self.config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)
                logger.info(f"設定ファイルを読み込みました: {self.config_path}")
                return {**self.DEFAULT_CONFIG, **config}
        except Exception as e:
            logger.error(f"設定ファイルの読み込みエラー: {e}")
            return self.DEFAULT_CONFIG.copy()

    def _create_default_config(self):
        """デフォルト設定ファイルを作成"""
        try:
            with open(self.config_path, 'w', encoding='utf-8') as f:
                yaml.dump(self.DEFAULT_CONFIG, f, allow_unicode=True, default_flow_style=False)
            logger.info(f"デフォルト設定ファイルを作成しました: {self.config_path}")
        except Exception as e:
            logger.error(f"設定ファイルの作成エラー: {e}")

    def get(self, key: str, default=None):
        """設定値を取得"""
        return self.config.get(key, default)


class ReplayUploader:
    """リプレイアップロードクラス"""

    def __init__(self, config: Config):
        self.config = config
        self.api_url = config.get('api_url')
        self.api_key = config.get('api_key')
        self.discord_user_id = config.get('discord_user_id', '')
        self.retry_count = config.get('retry_count', 3)
        self.retry_delay = config.get('retry_delay', 5)

        # アップロード履歴
        self.upload_history = []
        self.failed_uploads = []

    def upload_replay(self, file_path: Path) -> Dict[str, Any]:
        """
        リプレイファイルをアップロード

        Args:
            file_path: リプレイファイルのパス

        Returns:
            APIレスポンス
        """
        if not file_path.exists():
            logger.error(f"ファイルが見つかりません: {file_path}")
            return {'status': 'error', 'message': 'File not found'}

        logger.info(f"アップロード開始: {file_path.name}")

        # ヘッダー
        headers = {
            'X-Api-Key': self.api_key
        }

        if self.discord_user_id:
            headers['X-User-Id'] = self.discord_user_id

        # ファイルをアップロード
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

                    # 履歴に追加
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

        # 失敗リストに追加
        self.failed_uploads.append({
            'file': str(file_path),
            'timestamp': datetime.now().isoformat()
        })

        return {'status': 'error', 'message': 'Upload failed after retries'}


class ReplayFileHandler(PatternMatchingEventHandler):
    """リプレイファイル監視ハンドラー"""

    def __init__(self, uploader: ReplayUploader):
        # *.wowsreplayファイルのみを監視、temp.wowsreplayは除外
        super().__init__(
            patterns=["*.wowsreplay"],
            ignore_patterns=["temp.wowsreplay"],
            ignore_directories=True,
            case_sensitive=False
        )
        self.uploader = uploader
        self.processing_files = set()  # 処理中のファイル

    def on_created(self, event: FileCreatedEvent):
        """ファイル作成イベント"""
        if event.is_directory:
            return

        file_path = Path(event.src_path)

        # 既に処理中の場合はスキップ
        if str(file_path) in self.processing_files:
            return

        logger.info(f"新しいリプレイファイルを検出: {file_path.name}")

        # 処理中リストに追加
        self.processing_files.add(str(file_path))

        try:
            # ファイル書き込み完了を待つ
            self._wait_for_file_complete(file_path)

            # アップロード
            result = self.uploader.upload_replay(file_path)

            # 重複チェック
            if result.get('status') == 'duplicate':
                logger.warning(f"重複: このゲームは既に {result.get('originalUploader')} さんがアップロードしています")
                logger.warning(f"アップロード日時: {result.get('uploadedAt')}")

        except Exception as e:
            logger.error(f"ファイル処理エラー: {e}")

        finally:
            # 処理中リストから削除
            self.processing_files.discard(str(file_path))

    def _wait_for_file_complete(self, file_path: Path, timeout: int = 30):
        """
        ファイル書き込み完了を待つ

        Args:
            file_path: ファイルパス
            timeout: タイムアウト（秒）
        """
        logger.debug(f"ファイル書き込み完了待機中: {file_path.name}")

        last_size = -1
        stable_count = 0
        start_time = time.time()

        while time.time() - start_time < timeout:
            try:
                current_size = file_path.stat().st_size

                if current_size == last_size:
                    stable_count += 1

                    # 5秒間サイズが変化しなければ完了とみなす
                    if stable_count >= 5:
                        logger.debug(f"ファイル書き込み完了: {file_path.name} ({current_size} bytes)")
                        return
                else:
                    stable_count = 0
                    last_size = current_size

                time.sleep(1)

            except FileNotFoundError:
                logger.warning(f"ファイルが見つかりません: {file_path}")
                return

        logger.warning(f"タイムアウト: ファイル書き込み完了を確認できませんでした: {file_path.name}")


class ReplayMonitor:
    """リプレイフォルダ監視クラス"""

    def __init__(self, config: Config):
        self.config = config
        self.replays_folder = config.get('replays_folder')
        self.uploader = ReplayUploader(config)
        self.observer = None

    def start(self):
        """監視を開始"""
        # リプレイフォルダの存在確認
        if not os.path.exists(self.replays_folder):
            logger.error(f"リプレイフォルダが見つかりません: {self.replays_folder}")
            logger.error("設定ファイル (config.yaml) を確認してください")
            return

        logger.info(f"リプレイフォルダを監視開始: {self.replays_folder}")
        logger.info(f"API URL: {self.config.get('api_url')}")

        # Observerの選択（PollingObserverの方が安定）
        use_polling = self.config.get('use_polling', True)
        if use_polling:
            logger.info("PollingObserverを使用します（安定性重視）")
            self.observer = PollingObserver()
        else:
            logger.info("標準Observerを使用します")
            self.observer = Observer()

        # ファイル監視を開始
        event_handler = ReplayFileHandler(self.uploader)
        self.observer.schedule(event_handler, self.replays_folder, recursive=False)
        self.observer.start()

        try:
            while True:
                time.sleep(10)
                # 定期的にステータスを表示
                if len(self.uploader.upload_history) > 0:
                    logger.debug(f"アップロード済み: {len(self.uploader.upload_history)}件")
                if len(self.uploader.failed_uploads) > 0:
                    logger.debug(f"失敗: {len(self.uploader.failed_uploads)}件")

        except KeyboardInterrupt:
            logger.info("監視を停止します...")
            self.observer.stop()

        self.observer.join()
        logger.info("監視を終了しました")


def main():
    """メイン関数"""
    # PyInstallerでのマルチプロセシング対応
    multiprocessing.freeze_support()

    logger.info("=" * 60)
    logger.info("WoWS Replay Auto Uploader")
    logger.info("=" * 60)

    # 設定ファイルを読み込み
    config_path = 'config.yaml'
    if len(sys.argv) > 1:
        config_path = sys.argv[1]

    config = Config(config_path)

    # API Key確認
    api_key = config.get('api_key')
    if not api_key or api_key == 'YOUR_API_KEY_HERE':
        logger.error("API Keyが設定されていません")
        logger.error(f"設定ファイル ({config_path}) にAPI Keyを設定してください")
        input("\n終了するにはEnterキーを押してください...")
        sys.exit(1)

    # 監視開始
    monitor = ReplayMonitor(config)
    monitor.start()


if __name__ == '__main__':
    main()
