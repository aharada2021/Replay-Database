"""
Game Capture Manager - Orchestrates screen, audio capture and video encoding.
"""

import json
import logging
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Optional

import numpy as np

from .audio_capture import AudioCapture, MockAudioCapture
from .config import CaptureConfig
from .exceptions import (
    CaptureAlreadyRunningError,
    CaptureError,
    CaptureNotRunningError,
    WindowNotFoundError,
)
from .screen_capture import MockScreenCapture, ScreenCapture
from .video_encoder import MockVideoEncoder, VideoEncoder

logger = logging.getLogger(__name__)


class GameCaptureManager:
    """
    Manages game capture including screen, audio, and video encoding.

    Orchestrates the capture pipeline:
    1. Screen capture (Windows Graphics Capture API)
    2. Audio capture (WASAPI loopback + microphone)
    3. Video encoding (FFmpeg H.264)
    """

    def __init__(self, config: CaptureConfig, use_mocks: bool = False):
        """
        Initialize the capture manager.

        Args:
            config: Capture configuration
            use_mocks: Use mock implementations for testing
        """
        self.config = config
        self._use_mocks = use_mocks

        self._screen_capture: Optional[ScreenCapture] = None
        self._audio_capture: Optional[AudioCapture] = None
        self._encoder: Optional[VideoEncoder] = None

        self._running = False
        self._lock = threading.Lock()
        self._start_time: Optional[float] = None
        self._output_path: Optional[Path] = None

        self._arena_info: Optional[dict] = None

        self._window_search_thread: Optional[threading.Thread] = None
        self._window_found = threading.Event()

        # Max duration timer
        self._duration_timer: Optional[threading.Timer] = None

    def is_available(self) -> bool:
        """Check if capture is available on this system."""
        if self._use_mocks:
            return True

        screen_ok = ScreenCapture.is_available()
        encoder_ok = VideoEncoder.is_available()

        if not screen_ok:
            logger.warning("Screen capture not available")
        if not encoder_ok:
            logger.warning("Video encoder (FFmpeg) not available")

        return screen_ok and encoder_ok

    def start_capture(
        self,
        arena_info: Optional[dict] = None,
        wait_for_window: bool = True,
    ) -> bool:
        """
        Start game capture.

        Args:
            arena_info: Optional arena info from tempArenaInfo.json
            wait_for_window: If True, wait for window to appear

        Returns:
            True if capture started successfully

        Raises:
            CaptureAlreadyRunningError: If capture is already running
            WindowNotFoundError: If game window not found (when wait_for_window=False)
        """
        if not self.config.enabled:
            logger.info("Capture is disabled in config")
            return False

        with self._lock:
            if self._running:
                raise CaptureAlreadyRunningError("Capture is already running")

        self._arena_info = arena_info

        if wait_for_window:
            return self._start_with_window_search()
        else:
            return self._start_capture_now()

    def _start_with_window_search(self) -> bool:
        """Start capture after finding the game window."""
        self._window_found.clear()

        self._window_search_thread = threading.Thread(
            target=self._window_search_loop, daemon=True
        )
        self._window_search_thread.start()

        logger.info("Waiting for game window...")
        return True

    def _window_search_loop(self):
        """Background thread to search for game window."""
        screen_cls = MockScreenCapture if self._use_mocks else ScreenCapture

        while not self._window_found.is_set():
            try:
                temp_screen = screen_cls(
                    self.config, lambda frame, ts: None
                )
                window_info = temp_screen.find_wows_window()

                if window_info is not None:
                    logger.info(f"Found game window: {window_info.title}")
                    self._window_found.set()

                    try:
                        self._start_capture_now()
                    except Exception as e:
                        logger.error(f"Failed to start capture: {e}")
                    return

            except Exception as e:
                logger.debug(f"Window search error: {e}")

            time.sleep(self.config.window_retry_interval)

    def _start_capture_now(self) -> bool:
        """Start capture immediately (window must exist)."""
        with self._lock:
            if self._running:
                return True

            try:
                self._output_path = self._generate_output_path()
                self.config.ensure_output_folder()

                screen_cls = MockScreenCapture if self._use_mocks else ScreenCapture
                audio_cls = MockAudioCapture if self._use_mocks else AudioCapture
                encoder_cls = MockVideoEncoder if self._use_mocks else VideoEncoder

                self._screen_capture = screen_cls(
                    self.config, self._on_video_frame
                )

                if not self._screen_capture.start():
                    raise CaptureError("Failed to start screen capture")

                window_info = self._screen_capture.get_window_info()
                if window_info is None:
                    raise WindowNotFoundError("Window info not available")

                self._encoder = encoder_cls(self.config, self._output_path)
                if not self._encoder.start(window_info.width, window_info.height):
                    raise CaptureError("Failed to start encoder")

                if self.config.capture_audio or self.config.capture_microphone:
                    self._audio_capture = audio_cls(
                        self.config, self._on_audio_data
                    )
                    if not self._audio_capture.start():
                        logger.warning("Audio capture failed, continuing without audio")
                        self._audio_capture = None

                self._running = True
                self._start_time = time.perf_counter()

                # Start max duration timer
                self._start_duration_timer()

                logger.info(f"Capture started: {self._output_path}")
                return True

            except Exception as e:
                logger.error(f"Failed to start capture: {e}")
                self._cleanup()
                raise

    def _generate_output_path(self) -> Path:
        """Generate output file path based on arena info and timestamp."""
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")

        if self._arena_info:
            map_name = self._arena_info.get("mapDisplayName", "unknown")
            game_mode = self._arena_info.get("gameLogic", "unknown")
            filename = f"WoWS_{map_name}_{game_mode}_{timestamp}.mp4"
        else:
            filename = f"WoWS_capture_{timestamp}.mp4"

        filename = "".join(
            c if c.isalnum() or c in "._-" else "_" for c in filename
        )

        return self.config.output_folder / filename

    def _on_video_frame(self, frame: np.ndarray, timestamp: float):
        """Callback for video frames."""
        if self._encoder is not None and self._running:
            self._encoder.write_frame(frame, timestamp)

    def _on_audio_data(self, audio: np.ndarray, timestamp: float):
        """Callback for audio data."""
        if self._encoder is not None and self._running:
            self._encoder.write_audio(audio, timestamp)

    def _start_duration_timer(self):
        """Start a timer to enforce max capture duration."""
        if self.config.max_duration_minutes <= 0:
            return

        max_seconds = self.config.max_duration_minutes * 60

        def on_max_duration():
            logger.warning(
                f"Maximum capture duration reached ({self.config.max_duration_minutes} minutes)"
            )
            self.stop_capture()

        self._duration_timer = threading.Timer(max_seconds, on_max_duration)
        self._duration_timer.daemon = True
        self._duration_timer.start()

        logger.debug(
            f"Max duration timer set: {self.config.max_duration_minutes} minutes"
        )

    def _cancel_duration_timer(self):
        """Cancel the max duration timer."""
        if self._duration_timer is not None:
            self._duration_timer.cancel()
            self._duration_timer = None

    def stop_capture(self) -> Optional[Path]:
        """
        Stop game capture and finalize video file.

        Returns:
            Path to the saved video file, or None if failed

        Raises:
            CaptureNotRunningError: If capture is not running
        """
        # Cancel duration timer first
        self._cancel_duration_timer()

        with self._lock:
            if not self._running:
                if self._window_search_thread is not None:
                    self._window_found.set()
                    self._window_search_thread.join(timeout=2.0)
                    self._window_search_thread = None
                    logger.info("Window search cancelled")
                    return None
                return None

            self._running = False

        logger.info("Stopping capture...")

        duration = 0.0
        if self._start_time is not None:
            duration = time.perf_counter() - self._start_time

        if self._screen_capture is not None:
            self._screen_capture.stop()
            self._screen_capture = None

        if self._audio_capture is not None:
            self._audio_capture.stop()
            self._audio_capture = None

        output_path = None
        if self._encoder is not None:
            output_path = self._encoder.stop()
            self._encoder = None

        if output_path is not None:
            logger.info(
                f"Capture saved: {output_path} (duration: {duration:.1f}s)"
            )
        else:
            logger.warning("Failed to save capture")

        return output_path

    def _cleanup(self):
        """Clean up all resources."""
        if self._screen_capture is not None:
            try:
                self._screen_capture.stop()
            except Exception:
                pass
            self._screen_capture = None

        if self._audio_capture is not None:
            try:
                self._audio_capture.stop()
            except Exception:
                pass
            self._audio_capture = None

        if self._encoder is not None:
            try:
                self._encoder.stop()
            except Exception:
                pass
            self._encoder = None

    def is_running(self) -> bool:
        """Check if capture is running."""
        with self._lock:
            return self._running

    def is_waiting_for_window(self) -> bool:
        """Check if waiting for game window."""
        return (
            self._window_search_thread is not None
            and self._window_search_thread.is_alive()
            and not self._window_found.is_set()
        )

    def get_duration(self) -> float:
        """Get current capture duration in seconds."""
        if self._start_time is None:
            return 0.0
        return time.perf_counter() - self._start_time

    def get_output_path(self) -> Optional[Path]:
        """Get the current/last output file path."""
        return self._output_path


def load_arena_info(arena_info_path: Path) -> Optional[dict]:
    """
    Load tempArenaInfo.json file.

    Args:
        arena_info_path: Path to tempArenaInfo.json

    Returns:
        Parsed arena info dict, or None if failed
    """
    try:
        with open(arena_info_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        logger.warning(f"Failed to load arena info: {e}")
        return None
