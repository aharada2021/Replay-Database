#!/usr/bin/env python3
"""
Live capture test - monitors WoWS replays folder for real games.

This script watches for:
1. tempArenaInfo.json creation -> starts capture
2. .wowsreplay file creation -> stops capture

Usage:
    python test_live_capture.py

Press Ctrl+C to stop monitoring.
"""

import logging
import signal
import sys
import time
from pathlib import Path

from watchdog.observers.polling import PollingObserver
from watchdog.events import PatternMatchingEventHandler

sys.path.insert(0, str(Path(__file__).parent))

from capture import CaptureConfig, GameCaptureManager

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Set third-party loggers to INFO to reduce noise
logging.getLogger('watchdog').setLevel(logging.INFO)

# Configuration
REPLAYS_FOLDER = Path(r"C:\Games\World_of_Warships\replays\15.0.0.0")
OUTPUT_FOLDER = Path(r"C:\Users\family\Videos\WoWS Captures")


class GameStartHandler(PatternMatchingEventHandler):
    """Watches for tempArenaInfo.json (game start)."""

    def __init__(self, manager: GameCaptureManager):
        super().__init__(patterns=["tempArenaInfo.json"], ignore_directories=True)
        self.manager = manager

    def on_created(self, event):
        logger.info(f"Game start detected: {event.src_path}")
        try:
            import json
            with open(event.src_path, 'r', encoding='utf-8') as f:
                arena_info = json.load(f)

            map_name = arena_info.get('mapDisplayName', 'Unknown')
            game_mode = arena_info.get('gameLogic', 'Unknown')
            logger.info(f"Map: {map_name}, Mode: {game_mode}")

            if not self.manager.is_running():
                self.manager.start_capture(arena_info=arena_info, wait_for_window=True)
        except Exception as e:
            logger.error(f"Error starting capture: {e}")


class GameEndHandler(PatternMatchingEventHandler):
    """Watches for .wowsreplay files (game end)."""

    def __init__(self, manager: GameCaptureManager):
        super().__init__(patterns=["*.wowsreplay"], ignore_directories=True)
        self.manager = manager

    def on_created(self, event):
        logger.info(f"Game end detected: {event.src_path}")
        if self.manager.is_running():
            output = self.manager.stop_capture()
            if output and output.exists():
                size_mb = output.stat().st_size / 1024 / 1024
                logger.info(f"Video saved: {output} ({size_mb:.2f} MB)")
            else:
                logger.warning("Failed to save video")


def main():
    print("=" * 60)
    print("WoWS Live Game Capture Test")
    print("=" * 60)
    print(f"\nReplays folder: {REPLAYS_FOLDER}")
    print(f"Output folder: {OUTPUT_FOLDER}")
    print("\nWaiting for game to start...")
    print("Press Ctrl+C to stop.\n")

    # Ensure output folder exists
    OUTPUT_FOLDER.mkdir(parents=True, exist_ok=True)

    # Create capture manager
    config = CaptureConfig(
        output_folder=str(OUTPUT_FOLDER),
        target_fps=30,
        video_quality="medium",
        capture_audio=True,
        capture_scale=0.5,  # Scale to 50% resolution to reduce raw file size
        max_duration_minutes=30,
    )
    logger.info(f"Capture config: scale={config.capture_scale}, fps={config.target_fps}, audio={config.capture_audio}")
    manager = GameCaptureManager(config)

    if not manager.is_available():
        logger.error("Capture not available on this system")
        return 1

    # Set up file watchers
    observer = PollingObserver()
    observer.schedule(GameStartHandler(manager), str(REPLAYS_FOLDER), recursive=False)
    observer.schedule(GameEndHandler(manager), str(REPLAYS_FOLDER), recursive=False)

    # Handle Ctrl+C
    def signal_handler(sig, frame):
        print("\n\nStopping...")
        if manager.is_running():
            output = manager.stop_capture()
            if output and output.exists():
                print(f"Video saved: {output}")
        observer.stop()
        sys.exit(0)

    signal.signal(signal.SIGINT, signal_handler)

    # Start watching
    observer.start()

    try:
        while True:
            time.sleep(1)
            if manager.is_running():
                duration = manager.get_duration()
                print(f"\r  Recording: {duration:.0f}s", end="", flush=True)
    except KeyboardInterrupt:
        pass
    finally:
        observer.stop()
        observer.join()

    return 0


if __name__ == "__main__":
    sys.exit(main())
