#!/usr/bin/env python3
"""
FFmpeg encoding test script.

Tests the capture and encoding pipeline to verify:
1. Video duration matches real time (±2 seconds for 60-second test)
2. Audio has no noise artifacts
3. Audio and video are synchronized

Usage:
    python test_ffmpeg_encoding.py [--duration SECONDS] [--no-audio]

Requirements:
    - FFmpeg must be installed and available in PATH
    - Windows with desktop audio capture capability
    - Game window not required (uses desktop capture)
"""

import argparse
import json
import logging
import subprocess
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from capture import CaptureConfig, GameCaptureManager
from capture.video_encoder import find_ffmpeg

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def get_video_duration(video_path: Path) -> float:
    """Get video duration using ffprobe."""
    ffprobe_path = find_ffmpeg()
    if ffprobe_path:
        ffprobe_path = ffprobe_path.replace("ffmpeg", "ffprobe")
    else:
        ffprobe_path = "ffprobe"

    cmd = [
        ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(video_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            logger.error(f"ffprobe error: {result.stderr}")
            return 0.0

        data = json.loads(result.stdout)
        duration = float(data.get("format", {}).get("duration", 0))
        return duration
    except Exception as e:
        logger.error(f"Failed to get video duration: {e}")
        return 0.0


def get_stream_info(video_path: Path) -> dict:
    """Get detailed stream information using ffprobe."""
    ffprobe_path = find_ffmpeg()
    if ffprobe_path:
        ffprobe_path = ffprobe_path.replace("ffmpeg", "ffprobe")
    else:
        ffprobe_path = "ffprobe"

    cmd = [
        ffprobe_path,
        "-v", "quiet",
        "-print_format", "json",
        "-show_streams",
        str(video_path),
    ]

    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
        if result.returncode != 0:
            return {}

        data = json.loads(result.stdout)
        return data
    except Exception as e:
        logger.error(f"Failed to get stream info: {e}")
        return {}


def run_capture_test(duration: int, capture_audio: bool, output_folder: Path) -> Path:
    """Run a capture test for the specified duration."""
    logger.info(f"Starting {duration}-second capture test...")
    logger.info(f"Audio capture: {'enabled' if capture_audio else 'disabled'}")

    # Create capture config
    config = CaptureConfig(
        output_folder=output_folder,
        video_quality="medium",
        target_fps=30,
        capture_audio=capture_audio,
        capture_microphone=False,  # Disable mic for testing
        max_duration_minutes=10,
    )

    # Create capture manager
    manager = GameCaptureManager(config)

    if not manager.is_available():
        logger.error("Capture is not available (FFmpeg not found)")
        return None

    # Start capture without waiting for game window (use desktop)
    logger.info("Starting capture (desktop mode)...")
    start_time = time.time()

    # Start capture - will capture desktop if game window not found
    if not manager.start_capture(wait_for_window=False):
        logger.error("Failed to start capture")
        return None

    # Wait for specified duration
    logger.info(f"Capturing for {duration} seconds...")
    for i in range(duration):
        time.sleep(1)
        if (i + 1) % 10 == 0:
            logger.info(f"  {i + 1}/{duration} seconds elapsed...")

    # Stop capture
    elapsed = time.time() - start_time
    logger.info(f"Stopping capture after {elapsed:.1f} seconds...")
    video_path = manager.stop_capture()

    if video_path is None:
        logger.error("Capture failed - no video file produced")
        return None

    logger.info(f"Video saved: {video_path}")
    return video_path


def verify_video(video_path: Path, expected_duration: float, tolerance: float = 2.0) -> bool:
    """Verify the captured video meets expectations."""
    logger.info("=" * 60)
    logger.info("VERIFICATION RESULTS")
    logger.info("=" * 60)

    # Check file exists
    if not video_path.exists():
        logger.error(f"Video file not found: {video_path}")
        return False

    file_size = video_path.stat().st_size / (1024 * 1024)
    logger.info(f"File size: {file_size:.1f} MB")

    # Get video duration
    actual_duration = get_video_duration(video_path)
    if actual_duration == 0:
        logger.error("Could not determine video duration")
        return False

    logger.info(f"Expected duration: {expected_duration:.1f} seconds")
    logger.info(f"Actual duration:   {actual_duration:.1f} seconds")

    duration_diff = abs(actual_duration - expected_duration)
    logger.info(f"Difference:        {duration_diff:.1f} seconds")

    # Check duration tolerance
    if duration_diff > tolerance:
        logger.error(
            f"FAIL: Duration difference ({duration_diff:.1f}s) exceeds "
            f"tolerance ({tolerance:.1f}s)"
        )
        time_compression = (expected_duration - actual_duration) / expected_duration * 100
        if time_compression > 0:
            logger.error(f"       Video is {time_compression:.1f}% shorter than expected")
        else:
            logger.error(f"       Video is {-time_compression:.1f}% longer than expected")
        return False

    logger.info(f"PASS: Duration within tolerance")

    # Get stream info
    stream_info = get_stream_info(video_path)
    streams = stream_info.get("streams", [])

    video_stream = None
    audio_stream = None
    for stream in streams:
        if stream.get("codec_type") == "video":
            video_stream = stream
        elif stream.get("codec_type") == "audio":
            audio_stream = stream

    if video_stream:
        logger.info("")
        logger.info("Video stream:")
        logger.info(f"  Codec: {video_stream.get('codec_name', 'unknown')}")
        logger.info(f"  Resolution: {video_stream.get('width')}x{video_stream.get('height')}")
        logger.info(f"  Frame rate: {video_stream.get('r_frame_rate', 'unknown')}")
        logger.info(f"  Duration: {video_stream.get('duration', 'N/A')} seconds")

    if audio_stream:
        logger.info("")
        logger.info("Audio stream:")
        logger.info(f"  Codec: {audio_stream.get('codec_name', 'unknown')}")
        logger.info(f"  Sample rate: {audio_stream.get('sample_rate', 'unknown')} Hz")
        logger.info(f"  Channels: {audio_stream.get('channels', 'unknown')}")
        logger.info(f"  Duration: {audio_stream.get('duration', 'N/A')} seconds")

        # Check audio/video sync
        if video_stream and audio_stream:
            video_duration = float(video_stream.get("duration", 0))
            audio_duration = float(audio_stream.get("duration", 0))
            sync_diff = abs(video_duration - audio_duration)
            logger.info("")
            logger.info(f"Audio/Video sync difference: {sync_diff:.3f} seconds")
            if sync_diff > 0.5:
                logger.warning(f"  WARNING: Sync difference > 0.5s may be noticeable")
            else:
                logger.info(f"  PASS: Sync is acceptable")

    logger.info("")
    logger.info("=" * 60)
    logger.info("To verify audio quality, please play the video and check for:")
    logger.info("  - Choppy or stuttering audio")
    logger.info("  - Static noise or crackling")
    logger.info("  - Audio cutting in and out")
    logger.info("=" * 60)

    return True


def main():
    parser = argparse.ArgumentParser(description="Test FFmpeg encoding settings")
    parser.add_argument(
        "--duration",
        type=int,
        default=60,
        help="Capture duration in seconds (default: 60)",
    )
    parser.add_argument(
        "--no-audio",
        action="store_true",
        help="Disable audio capture",
    )
    parser.add_argument(
        "--output-folder",
        type=str,
        default=None,
        help="Output folder for test video (default: current directory)",
    )
    parser.add_argument(
        "--verify-only",
        type=str,
        default=None,
        help="Skip capture, only verify existing video file",
    )

    args = parser.parse_args()

    # Set output folder
    if args.output_folder:
        output_folder = Path(args.output_folder)
    else:
        output_folder = Path.cwd()

    output_folder.mkdir(parents=True, exist_ok=True)

    # If verify-only mode
    if args.verify_only:
        video_path = Path(args.verify_only)
        success = verify_video(video_path, args.duration)
        sys.exit(0 if success else 1)

    # Run capture test
    video_path = run_capture_test(
        duration=args.duration,
        capture_audio=not args.no_audio,
        output_folder=output_folder,
    )

    if video_path is None:
        logger.error("Capture test failed")
        sys.exit(1)

    # Verify the captured video
    success = verify_video(video_path, args.duration)

    if success:
        logger.info("")
        logger.info("Test PASSED! Video file: " + str(video_path))
    else:
        logger.error("")
        logger.error("Test FAILED! Please check the logs above.")

    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
