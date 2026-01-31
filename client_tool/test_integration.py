#!/usr/bin/env python3
"""
Integration test for game capture with replay uploader.

This script simulates the game start/end flow:
1. Creates tempArenaInfo.json (simulates game start)
2. Waits for capture to start
3. Records for specified duration
4. Creates .wowsreplay file (simulates game end)
5. Waits for capture to stop and video to be saved

Usage:
    python test_integration.py [--duration SECONDS] [--replays-folder PATH]
"""

import argparse
import json
import logging
import os
import shutil
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from capture import CaptureConfig, GameCaptureManager

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def create_temp_arena_info(replays_folder: Path) -> Path:
    """Create a mock tempArenaInfo.json file."""
    arena_info = {
        "clientVersionFromXml": "15,0,0,0",
        "gameMode": 7,
        "clientVersionFromExe": "0, 15, 0, 0",
        "scenarioUiCategoryId": 1,
        "mapDisplayName": "Test Map",
        "mapId": 1,
        "matchGroup": "ranked",
        "weatherParams": {},
        "duration": 1200,
        "gameLogic": "Domination",
        "name": "Test Arena",
        "scenario": "Ranked",
        "playerID": 12345,
        "playerName": "TestPlayer",
        "playerVehicle": "PJSD025-Shimakaze-1943",
        "playersPerTeam": 7,
        "teamsCount": 2,
        "dateTime": datetime.now().strftime("%d.%m.%Y %H:%M:%S"),
        "mapName": "spaces/s01_NavalBase",
        "playerShipId": 4181604048,
        "vehicles": [
            {
                "shipId": 4181604048,
                "relation": 0,
                "id": 12345,
                "name": "TestPlayer"
            }
        ]
    }

    filepath = replays_folder / "tempArenaInfo.json"
    with open(filepath, 'w', encoding='utf-8') as f:
        json.dump(arena_info, f, indent=2)

    logger.info(f"Created tempArenaInfo.json at {filepath}")
    return filepath


def create_mock_replay(replays_folder: Path) -> Path:
    """Create a mock .wowsreplay file."""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"{timestamp}_TEST_Integration_Test.wowsreplay"
    filepath = replays_folder / filename

    # Create a minimal mock replay file
    with open(filepath, 'wb') as f:
        f.write(b'\x00' * 1024)  # Minimal dummy content

    logger.info(f"Created mock replay at {filepath}")
    return filepath


def run_integration_test(
    duration: int = 10,
    replays_folder: str = None,
    output_folder: str = None,
):
    """
    Run the integration test.

    Args:
        duration: Recording duration in seconds
        replays_folder: Path to WoWS replays folder
        output_folder: Path to save captured videos
    """
    print("=" * 60)
    print("Game Capture Integration Test")
    print("=" * 60)

    # Use temp directory if no replays folder specified
    if replays_folder:
        replays_path = Path(replays_folder)
    else:
        replays_path = Path(tempfile.mkdtemp(prefix="wows_test_"))
        print(f"Using temp replays folder: {replays_path}")

    # Output folder
    if output_folder:
        output_path = Path(output_folder)
    else:
        output_path = Path.cwd()

    output_path.mkdir(parents=True, exist_ok=True)

    print(f"\nConfiguration:")
    print(f"  Replays folder: {replays_path}")
    print(f"  Output folder: {output_path}")
    print(f"  Recording duration: {duration} seconds")

    # Create capture config
    config = CaptureConfig(
        output_folder=str(output_path),
        max_duration_minutes=5,
        target_fps=30,
        video_quality="medium",
    )

    # Create capture manager
    manager = GameCaptureManager(config)

    if not manager.is_available():
        print("\n[ERROR] Capture not available on this system")
        return False

    print("\n--- Phase 1: Simulate Game Start ---")
    print("Creating tempArenaInfo.json...")

    # Create temp arena info
    arena_info_path = create_temp_arena_info(replays_path)

    # Read arena info
    with open(arena_info_path, 'r', encoding='utf-8') as f:
        arena_info = json.load(f)

    print("Starting capture...")
    result = manager.start_capture(arena_info=arena_info, wait_for_window=True)

    if not result:
        print("[ERROR] Failed to start capture")
        # Cleanup
        arena_info_path.unlink(missing_ok=True)
        return False

    print(f"[OK] Capture started")

    print(f"\n--- Phase 2: Recording ({duration} seconds) ---")
    for i in range(duration):
        time.sleep(1)
        dur = manager.get_duration()
        running = manager.is_running()
        status = "Recording" if running else "Stopped"
        print(f"  {i+1}/{duration}s - {status} (duration: {dur:.1f}s)")

    print("\n--- Phase 3: Simulate Game End ---")
    print("Creating .wowsreplay file...")

    # Create mock replay file
    replay_path = create_mock_replay(replays_path)

    print("Stopping capture...")
    output_file = manager.stop_capture()

    # Wait for encoding to complete
    print("Waiting for encoding to complete...")
    time.sleep(5)

    print("\n--- Phase 4: Verify Results ---")

    # Cleanup temp files
    arena_info_path.unlink(missing_ok=True)
    replay_path.unlink(missing_ok=True)

    if output_file and output_file.exists():
        size_mb = output_file.stat().st_size / 1024 / 1024
        print(f"\n[SUCCESS] Video saved!")
        print(f"  File: {output_file}")
        print(f"  Size: {size_mb:.2f} MB")

        # Verify with ffprobe if available
        try:
            import subprocess
            probe_result = subprocess.run(
                ['ffprobe', '-v', 'quiet', '-print_format', 'json',
                 '-show_format', str(output_file)],
                capture_output=True, text=True
            )
            if probe_result.returncode == 0:
                info = json.loads(probe_result.stdout)
                if 'format' in info:
                    video_duration = float(info['format'].get('duration', 0))
                    print(f"  Duration: {video_duration:.1f}s")
        except Exception:
            pass

        return True
    else:
        print(f"\n[FAIL] Video not saved")
        print(f"  Expected output: {output_file}")
        return False


def main():
    parser = argparse.ArgumentParser(
        description='Integration test for game capture'
    )
    parser.add_argument(
        '--duration', '-d',
        type=int,
        default=10,
        help='Recording duration in seconds (default: 10)'
    )
    parser.add_argument(
        '--replays-folder', '-r',
        type=str,
        default=None,
        help='Path to WoWS replays folder (default: temp directory)'
    )
    parser.add_argument(
        '--output-folder', '-o',
        type=str,
        default=None,
        help='Path to save captured videos (default: current directory)'
    )

    args = parser.parse_args()

    success = run_integration_test(
        duration=args.duration,
        replays_folder=args.replays_folder,
        output_folder=args.output_folder,
    )

    print("\n" + "=" * 60)
    if success:
        print("Integration test PASSED")
    else:
        print("Integration test FAILED")
    print("=" * 60)

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
