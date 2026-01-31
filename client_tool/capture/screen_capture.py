"""
Screen capture using Windows Graphics Capture API via windows-capture.
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, Optional

import numpy as np

from .config import CaptureConfig
from .exceptions import WindowNotFoundError

logger = logging.getLogger(__name__)

# Windows-specific imports
try:
    import windows_capture
    from windows_capture import WindowsCapture, CaptureControl, Frame

    WINDOWS_CAPTURE_AVAILABLE = True
except ImportError:
    WINDOWS_CAPTURE_AVAILABLE = False
    logger.warning("windows-capture not available - screen capture disabled")

try:
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    CTYPES_AVAILABLE = True
except ImportError:
    CTYPES_AVAILABLE = False


@dataclass
class WindowInfo:
    """Information about a captured window."""

    hwnd: int
    title: str
    width: int
    height: int


class ScreenCapture:
    """
    Screen capture for WoWS game window using Windows Graphics Capture API.

    Uses the windows-capture library for efficient GPU-accelerated capture.
    """

    def __init__(
        self,
        config: CaptureConfig,
        frame_callback: Callable[[np.ndarray, float], None],
    ):
        """
        Initialize screen capture.

        Args:
            config: Capture configuration
            frame_callback: Callback for each captured frame (frame_data, timestamp)
        """
        self.config = config
        self.frame_callback = frame_callback
        self._capture: Optional["WindowsCapture"] = None
        self._control: Optional["CaptureControl"] = None
        self._running = False
        self._lock = threading.Lock()
        self._start_time: Optional[float] = None
        self._window_info: Optional[WindowInfo] = None
        self._frame_interval = 1.0 / config.target_fps
        self._last_frame_time = 0.0

    @staticmethod
    def is_available() -> bool:
        """Check if screen capture is available on this system."""
        return WINDOWS_CAPTURE_AVAILABLE and CTYPES_AVAILABLE

    def find_wows_window(self) -> Optional[WindowInfo]:
        """
        Find the World of Warships game window.

        Returns:
            WindowInfo if found, None otherwise
        """
        if not CTYPES_AVAILABLE:
            return None

        pattern = self.config.window_title_pattern.lower()
        found_hwnd = None
        found_title = None

        def enum_callback(hwnd, _):
            nonlocal found_hwnd, found_title
            if user32.IsWindowVisible(hwnd):
                length = user32.GetWindowTextLengthW(hwnd) + 1
                buffer = ctypes.create_unicode_buffer(length)
                user32.GetWindowTextW(hwnd, buffer, length)
                title = buffer.value
                if pattern in title.lower():
                    found_hwnd = hwnd
                    found_title = title
                    return False  # Stop enumeration
            return True

        WNDENUMPROC = ctypes.WINFUNCTYPE(
            ctypes.c_bool, ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int)
        )
        user32.EnumWindows(WNDENUMPROC(enum_callback), 0)

        if found_hwnd is None:
            return None

        rect = wintypes.RECT()
        user32.GetClientRect(found_hwnd, ctypes.byref(rect))
        width = rect.right - rect.left
        height = rect.bottom - rect.top

        return WindowInfo(
            hwnd=found_hwnd,
            title=found_title,
            width=width,
            height=height,
        )

    def start(self) -> bool:
        """
        Start screen capture.

        Returns:
            True if capture started successfully
        """
        if not self.is_available():
            logger.error("Screen capture not available")
            return False

        with self._lock:
            if self._running:
                logger.warning("Screen capture already running")
                return True

            window_info = self.find_wows_window()
            if window_info is None:
                logger.error(
                    f"Window not found: {self.config.window_title_pattern}"
                )
                raise WindowNotFoundError(
                    f"Could not find window: {self.config.window_title_pattern}"
                )

            self._window_info = window_info
            logger.info(
                f"Found window: {window_info.title} "
                f"({window_info.width}x{window_info.height})"
            )

            try:
                self._start_capture()
                self._running = True
                self._start_time = time.perf_counter()
                logger.info("Screen capture started")
                return True
            except Exception as e:
                logger.error(f"Failed to start screen capture: {e}")
                return False

    def _start_capture(self):
        """Initialize and start the Windows capture."""
        capture_self = self

        @windows_capture.capture_window_handler
        class Handler:
            def on_frame_arrived(self, frame: Frame, control: CaptureControl):
                capture_self._handle_frame(frame, control)

            def on_closed(self):
                capture_self._handle_closed()

        self._capture = WindowsCapture(
            cursor_capture=False,
            draw_border=False,
            window_name=self._window_info.title,
        )

        self._control = self._capture.start_capture(Handler())

    def _handle_frame(self, frame: "Frame", control: "CaptureControl"):
        """Handle incoming frame from capture."""
        # Check running state and get start_time under lock
        with self._lock:
            if not self._running:
                return
            start_time = self._start_time

        current_time = time.perf_counter()

        # Frame rate limiting (no lock needed for this check)
        if current_time - self._last_frame_time < self._frame_interval:
            return

        self._last_frame_time = current_time

        try:
            frame_data = np.array(frame.raw_frame)

            timestamp = current_time - start_time

            self.frame_callback(frame_data, timestamp)
        except Exception as e:
            logger.error(f"Error processing frame: {e}")

    def _handle_closed(self):
        """Handle capture session closed (window closed or minimized)."""
        logger.warning("Capture session closed")
        with self._lock:
            self._running = False

    def stop(self):
        """Stop screen capture."""
        with self._lock:
            if not self._running:
                return

            self._running = False

            if self._control is not None:
                try:
                    self._control.stop()
                except Exception as e:
                    logger.warning(f"Error stopping capture: {e}")
                self._control = None

            self._capture = None
            logger.info("Screen capture stopped")

    def is_running(self) -> bool:
        """Check if capture is running."""
        with self._lock:
            return self._running

    def get_window_info(self) -> Optional[WindowInfo]:
        """Get information about the captured window."""
        return self._window_info


class MockScreenCapture:
    """Mock screen capture for testing without Windows dependencies."""

    def __init__(
        self,
        config: CaptureConfig,
        frame_callback: Callable[[np.ndarray, float], None],
    ):
        self.config = config
        self.frame_callback = frame_callback
        self._running = False
        self._thread: Optional[threading.Thread] = None

    @staticmethod
    def is_available() -> bool:
        return True

    def find_wows_window(self) -> Optional[WindowInfo]:
        return WindowInfo(
            hwnd=12345,
            title="World of Warships [Mock]",
            width=1920,
            height=1080,
        )

    def start(self) -> bool:
        if self._running:
            return True

        self._running = True
        self._thread = threading.Thread(target=self._generate_frames)
        self._thread.daemon = True
        self._thread.start()
        logger.info("Mock screen capture started")
        return True

    def _generate_frames(self):
        """Generate mock frames for testing."""
        start_time = time.perf_counter()
        frame_interval = 1.0 / self.config.target_fps

        while self._running:
            current_time = time.perf_counter()
            timestamp = current_time - start_time

            frame = np.zeros((1080, 1920, 4), dtype=np.uint8)
            frame[:, :, 0] = 128  # Blue channel
            frame[:, :, 3] = 255  # Alpha

            self.frame_callback(frame, timestamp)

            time.sleep(frame_interval)

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        logger.info("Mock screen capture stopped")

    def is_running(self) -> bool:
        return self._running

    def get_window_info(self) -> Optional[WindowInfo]:
        return self.find_wows_window()
