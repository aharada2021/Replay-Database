#!/usr/bin/env python3
"""
Audio capture test - tests loopback audio capture in isolation.

Usage:
    python test_audio_only.py

Play some audio on your system while running this test.
Press Ctrl+C to stop.
"""

import logging
import signal
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

def test_audio_capture():
    """Test audio capture functionality."""
    print("=" * 60)
    print("Audio Capture Test")
    print("=" * 60)
    print("\nPlay some audio on your system (music, video, game sounds).")
    print("Press Ctrl+C to stop.\n")

    # Import audio capture
    try:
        from capture.audio_capture import AudioCapture, PYAUDIO_AVAILABLE
        from capture.config import CaptureConfig
    except ImportError as e:
        print(f"Import error: {e}")
        return 1

    if not PYAUDIO_AVAILABLE:
        print("PyAudio/PyAudioWPatch not available!")
        return 1

    print("PyAudioWPatch is available.")

    # Ask about microphone
    test_mic = input("\nTest microphone as well? (y/N): ").lower() == 'y'

    # List audio devices
    config = CaptureConfig(capture_audio=True, capture_microphone=test_mic)

    # Create a simple callback to count and display audio data
    audio_chunks = []
    chunk_count = [0]  # Use list to allow modification in nested function

    def audio_callback(audio_data, timestamp):
        chunk_count[0] += 1
        audio_chunks.append(len(audio_data))
        if chunk_count[0] == 1:
            print(f"\n[SUCCESS] First audio chunk received: {len(audio_data)} samples at {timestamp:.2f}s")
        elif chunk_count[0] % 100 == 0:
            avg_samples = sum(audio_chunks[-100:]) / 100
            print(f"  Audio chunks: {chunk_count[0]}, avg samples/chunk: {avg_samples:.0f}")

    # Create and start audio capture
    capture = AudioCapture(config, audio_callback)

    # List devices first
    print("\nAvailable audio devices:")
    devices = capture.list_devices()
    loopback_devices = []
    for dev in devices:
        loopback_marker = " [LOOPBACK]" if dev.is_loopback else ""
        print(f"  [{dev.index}] {dev.name} - {dev.channels}ch @ {dev.sample_rate}Hz{loopback_marker}")
        if dev.is_loopback:
            loopback_devices.append(dev)

    # Ask user to select loopback device
    if loopback_devices:
        print("\nLoopback devices available:")
        for i, dev in enumerate(loopback_devices):
            print(f"  {i+1}. [{dev.index}] {dev.name}")
        print(f"  0. Auto-detect (current: device 10)")

        try:
            choice = input("\nSelect loopback device (0-{}, default=0): ".format(len(loopback_devices)))
            if choice and choice != "0":
                idx = int(choice) - 1
                if 0 <= idx < len(loopback_devices):
                    selected_device = loopback_devices[idx]
                    print(f"\nUsing device: {selected_device.name}")
                    # Override the device selection
                    capture._override_loopback_device = selected_device.index
        except (ValueError, IndexError):
            pass

    print("\nStarting audio capture...")

    if not capture.start():
        print("Failed to start audio capture!")
        return 1

    print("Audio capture started. Waiting for audio data...")
    print("(If no '[SUCCESS]' message appears, no audio is being captured)")

    # Handle Ctrl+C
    running = [True]
    def signal_handler(sig, frame):
        print("\n\nStopping...")
        running[0] = False

    signal.signal(signal.SIGINT, signal_handler)

    # Wait and display status
    start_time = time.time()
    try:
        while running[0]:
            time.sleep(1)
            elapsed = time.time() - start_time
            if chunk_count[0] == 0:
                print(f"\r  Waiting for audio... ({elapsed:.0f}s) - No audio received yet", end="", flush=True)
            else:
                print(f"\r  Running: {elapsed:.0f}s, chunks: {chunk_count[0]}      ", end="", flush=True)
    except KeyboardInterrupt:
        pass

    # Stop capture
    capture.stop()

    print(f"\n\nTest complete:")
    print(f"  Total audio chunks received: {chunk_count[0]}")
    if chunk_count[0] > 0:
        print(f"  Total samples: {sum(audio_chunks)}")
        print("  [SUCCESS] Audio capture is working!")
    else:
        print("  [FAILED] No audio was captured.")
        print("\n  Possible causes:")
        print("  - No audio playing on system")
        print("  - Wrong loopback device selected")
        print("  - WASAPI loopback not supported on this device")

    return 0 if chunk_count[0] > 0 else 1


if __name__ == "__main__":
    sys.exit(test_audio_capture())
