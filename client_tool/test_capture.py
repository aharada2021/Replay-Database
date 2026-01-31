#!/usr/bin/env python3
"""
Test script for game capture functionality.
Run this in Windows PowerShell to verify the capture module works.
"""

import logging
import sys
import time
from pathlib import Path

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def test_imports():
    """Test that all modules can be imported."""
    print("\n=== Test 1: Module Imports ===")

    try:
        from capture.config import CaptureConfig
        print("[OK] CaptureConfig")
    except Exception as e:
        print(f"[FAIL] CaptureConfig: {e}")
        return False

    try:
        from capture.exceptions import CaptureError, WindowNotFoundError
        print("[OK] Exceptions")
    except Exception as e:
        print(f"[FAIL] Exceptions: {e}")
        return False

    try:
        from capture.screen_capture import ScreenCapture, MockScreenCapture, WINDOWS_CAPTURE_AVAILABLE
        print(f"[OK] ScreenCapture (Windows API: {WINDOWS_CAPTURE_AVAILABLE})")
    except Exception as e:
        print(f"[FAIL] ScreenCapture: {e}")
        return False

    try:
        from capture.audio_capture import AudioCapture, PYAUDIO_AVAILABLE
        print(f"[OK] AudioCapture (PyAudio: {PYAUDIO_AVAILABLE})")
    except Exception as e:
        print(f"[FAIL] AudioCapture: {e}")
        return False

    try:
        from capture.video_encoder import VideoEncoder
        print("[OK] VideoEncoder")
    except Exception as e:
        print(f"[FAIL] VideoEncoder: {e}")
        return False

    try:
        from capture.manager import GameCaptureManager
        print("[OK] GameCaptureManager")
    except Exception as e:
        print(f"[FAIL] GameCaptureManager: {e}")
        return False

    print("\nAll imports successful!")
    return True


def test_config():
    """Test configuration loading."""
    print("\n=== Test 2: Configuration ===")

    from capture.config import CaptureConfig

    # Test default config
    config = CaptureConfig()
    print(f"  Default FPS: {config.target_fps}")
    print(f"  Default Quality: {config.video_quality}")
    print(f"  Default Output: {config.output_folder}")
    print(f"  Max Duration: {config.max_duration_minutes} min")

    # Test custom config
    custom = CaptureConfig(
        target_fps=60,
        video_quality="high",
        capture_microphone=True
    )
    print(f"  Custom FPS: {custom.target_fps}")
    print(f"  Custom Quality: {custom.video_quality}")

    print("[OK] Configuration works")
    return True


def test_ffmpeg():
    """Test FFmpeg availability."""
    print("\n=== Test 3: FFmpeg ===")

    from capture.video_encoder import find_ffmpeg

    ffmpeg_path = find_ffmpeg()
    if ffmpeg_path:
        print(f"[OK] FFmpeg found: {ffmpeg_path}")
        return True
    else:
        print("[WARN] FFmpeg not found in PATH")
        print("  Install FFmpeg: winget install FFmpeg")
        print("  Or download from: https://ffmpeg.org/download.html")
        return False


def test_window_detection():
    """Test window detection (requires Windows)."""
    print("\n=== Test 4: Window Detection ===")

    from capture.config import CaptureConfig
    from capture.screen_capture import ScreenCapture, WINDOWS_CAPTURE_AVAILABLE

    if not WINDOWS_CAPTURE_AVAILABLE:
        print("[SKIP] Not running on Windows")
        return True

    config = CaptureConfig()

    def dummy_callback(frame, timestamp):
        pass

    capture = ScreenCapture(config, dummy_callback)

    window = capture.find_wows_window()
    if window:
        print(f"[OK] Found WoWS window: {window.title}")
        print(f"     Resolution: {window.width}x{window.height}")
    else:
        print("[INFO] WoWS window not found (game not running)")

    return True


def test_mock_capture():
    """Test mock capture for 3 seconds."""
    print("\n=== Test 5: Mock Capture (3 seconds) ===")

    from capture.config import CaptureConfig
    from capture.screen_capture import MockScreenCapture

    config = CaptureConfig(target_fps=10)
    frames_received = []

    def frame_callback(frame, timestamp):
        frames_received.append((frame.shape, timestamp))

    capture = MockScreenCapture(config, frame_callback)

    print("  Starting mock capture...")
    capture.start()

    time.sleep(3)

    capture.stop()

    print(f"  Received {len(frames_received)} frames")
    if len(frames_received) > 0:
        print(f"  Frame shape: {frames_received[0][0]}")
        print(f"  First timestamp: {frames_received[0][1]:.3f}s")
        print(f"  Last timestamp: {frames_received[-1][1]:.3f}s")
        print("[OK] Mock capture works")
        return True
    else:
        print("[FAIL] No frames received")
        return False


def test_video_encoder():
    """Test video encoder with mock frames."""
    print("\n=== Test 6: Video Encoder (5 seconds) ===")

    import numpy as np
    from capture.config import CaptureConfig
    from capture.video_encoder import VideoEncoder, find_ffmpeg

    if not find_ffmpeg():
        print("[SKIP] FFmpeg not available")
        return True

    config = CaptureConfig(target_fps=10, video_quality="low")
    output_path = Path("test_output.mp4")

    encoder = VideoEncoder(config, output_path)

    print("  Starting encoder...")
    if not encoder.start(1920, 1080):
        print("[FAIL] Failed to start encoder")
        return False

    # Generate 5 seconds of frames
    print("  Generating test frames...")
    for i in range(50):  # 5 seconds at 10fps
        frame = np.zeros((1080, 1920, 4), dtype=np.uint8)
        # Create gradient based on frame number
        frame[:, :, 0] = (i * 5) % 256  # Blue
        frame[:, :, 1] = (i * 3) % 256  # Green
        frame[:, :, 2] = (i * 7) % 256  # Red
        frame[:, :, 3] = 255  # Alpha

        encoder.write_frame(frame, i * 0.1)
        time.sleep(0.05)

    print("  Stopping encoder...")
    encoder.stop()

    if output_path.exists():
        size = output_path.stat().st_size
        print(f"  Output file: {output_path} ({size} bytes)")
        output_path.unlink()  # Clean up
        print("[OK] Video encoder works")
        return True
    else:
        print("[FAIL] Output file not created")
        return False


def test_manager():
    """Test GameCaptureManager initialization."""
    print("\n=== Test 7: GameCaptureManager ===")

    from capture.config import CaptureConfig
    from capture.manager import GameCaptureManager

    config = CaptureConfig(
        output_folder=str(Path.cwd()),
        capture_audio=False  # Skip audio for simple test
    )

    manager = GameCaptureManager(config)
    print(f"  Manager created")
    print(f"  Available: {manager.is_available()}")
    print(f"  Running: {manager.is_running()}")

    print("[OK] GameCaptureManager works")
    return True


def main():
    """Run all tests."""
    print("=" * 50)
    print("Game Capture Module Test Suite")
    print("=" * 50)

    results = []

    # Always run import test first
    results.append(("Imports", test_imports()))

    if not results[0][1]:
        print("\n[ABORT] Import test failed, cannot continue")
        sys.exit(1)

    # Run other tests
    results.append(("Config", test_config()))
    results.append(("FFmpeg", test_ffmpeg()))
    results.append(("Window Detection", test_window_detection()))
    results.append(("Mock Capture", test_mock_capture()))
    results.append(("Video Encoder", test_video_encoder()))
    results.append(("Manager", test_manager()))

    # Summary
    print("\n" + "=" * 50)
    print("Test Summary")
    print("=" * 50)

    passed = sum(1 for _, r in results if r)
    total = len(results)

    for name, result in results:
        status = "PASS" if result else "FAIL"
        print(f"  {name}: {status}")

    print(f"\nTotal: {passed}/{total} tests passed")

    if passed == total:
        print("\nAll tests passed! Ready for real capture testing.")
        return 0
    else:
        print("\nSome tests failed. Check the output above.")
        return 1


if __name__ == "__main__":
    sys.exit(main())
