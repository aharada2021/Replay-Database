"""
Video encoder using FFmpeg subprocess for H.264 encoding.

Uses a two-pass approach:
1. Write raw video frames and audio to temporary files
2. Mux and encode with FFmpeg at the end

This approach is more reliable on Windows than using multiple pipes.
"""

import logging
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import wave
from pathlib import Path
from queue import Empty, Queue
from typing import Optional

import numpy as np

from .config import CaptureConfig
from .exceptions import EncoderError

logger = logging.getLogger(__name__)

# Queue size limits
# Increased queue sizes for better buffering during I/O spikes
VIDEO_QUEUE_SIZE = 90  # 3 seconds at 30fps
AUDIO_QUEUE_SIZE = 180  # 3 seconds of audio chunks

# Dropped frame logging interval
DROPPED_FRAME_LOG_INTERVAL = 100


def find_ffmpeg() -> Optional[str]:
    """
    Find FFmpeg executable.

    Searches in the following order:
    1. Bundled with PyInstaller executable
    2. System PATH
    3. Common installation paths
    """
    if getattr(sys, "frozen", False):
        bundle_dir = Path(sys._MEIPASS)
        ffmpeg_path = bundle_dir / "ffmpeg.exe"
        if ffmpeg_path.exists():
            return str(ffmpeg_path)

    ffmpeg_in_path = shutil.which("ffmpeg")
    if ffmpeg_in_path:
        return ffmpeg_in_path

    if platform.system() == "Windows":
        common_paths = [
            Path(os.environ.get("LOCALAPPDATA", "")) / "Programs" / "ffmpeg" / "bin",
            Path("C:/ffmpeg/bin"),
            Path("C:/Program Files/ffmpeg/bin"),
        ]

        for path in common_paths:
            ffmpeg_path = path / "ffmpeg.exe"
            if ffmpeg_path.exists():
                return str(ffmpeg_path)

    return None


class VideoEncoder:
    """
    Video encoder using FFmpeg for H.264 encoding.

    Encodes video frames and audio data into an MP4 file using FFmpeg subprocess.
    Uses a two-pass approach for reliability:
    1. Capture phase: Write frames to raw video file, audio to WAV file
    2. Encode phase: Use FFmpeg to encode and mux into final MP4
    """

    AUDIO_SAMPLE_RATE = 44100
    AUDIO_CHANNELS = 2
    AUDIO_SAMPLE_WIDTH = 2  # 16-bit

    def __init__(self, config: CaptureConfig, output_path: Path):
        """
        Initialize video encoder.

        Args:
            config: Capture configuration
            output_path: Path for output video file
        """
        self.config = config
        self.output_path = output_path
        self._ffmpeg_path = config.ffmpeg_path or find_ffmpeg()
        self._running = False
        self._lock = threading.Lock()

        # Queues for buffering
        self._video_queue: Queue = Queue(maxsize=VIDEO_QUEUE_SIZE)
        self._audio_queue: Queue = Queue(maxsize=AUDIO_QUEUE_SIZE)

        # Writer threads
        self._video_writer_thread: Optional[threading.Thread] = None
        self._audio_writer_thread: Optional[threading.Thread] = None

        # Temp files for raw data
        self._temp_dir: Optional[Path] = None
        self._raw_video_file: Optional[Path] = None
        self._raw_audio_file: Optional[Path] = None
        self._raw_video_handle = None
        self._raw_audio_handle = None

        # Stats
        self._width: Optional[int] = None
        self._height: Optional[int] = None
        self._start_time: Optional[float] = None
        self._frame_count = 0
        self._dropped_frames = 0
        self._audio_chunks = 0
        self._dropped_audio = 0

    @staticmethod
    def is_available() -> bool:
        """Check if FFmpeg is available."""
        return find_ffmpeg() is not None

    def start(self, width: int, height: int) -> bool:
        """
        Start the video encoder.

        Args:
            width: Video width
            height: Video height

        Returns:
            True if encoder started successfully
        """
        if self._ffmpeg_path is None:
            logger.error("FFmpeg not found")
            raise EncoderError("FFmpeg not found. Please install FFmpeg.")

        with self._lock:
            if self._running:
                logger.warning("Encoder already running")
                return True

            # Round dimensions to even numbers (required by libx264)
            self._width = width if width % 2 == 0 else width + 1
            self._height = height if height % 2 == 0 else height + 1

            if self._width != width or self._height != height:
                logger.info(
                    f"Adjusted dimensions from {width}x{height} to "
                    f"{self._width}x{self._height} (libx264 requires even dimensions)"
                )
            self._start_time = time.perf_counter()
            self._frame_count = 0
            self._dropped_frames = 0
            self._audio_chunks = 0
            self._dropped_audio = 0

            try:
                self._setup_temp_files()
                self._running = True

                # Start video writer thread
                self._video_writer_thread = threading.Thread(
                    target=self._video_writer_loop, daemon=True, name="VideoWriter"
                )
                self._video_writer_thread.start()

                # Start audio writer thread if audio enabled
                if self.config.capture_audio:
                    self._audio_writer_thread = threading.Thread(
                        target=self._audio_writer_loop, daemon=True, name="AudioWriter"
                    )
                    self._audio_writer_thread.start()

                logger.info(f"Video encoder started: {width}x{height}")
                return True

            except Exception as e:
                logger.error(f"Failed to start encoder: {e}")
                self._cleanup_temp_files()
                raise EncoderError(f"Failed to start encoder: {e}")

    def _setup_temp_files(self):
        """Create temporary files for raw video and audio data."""
        self._temp_dir = Path(tempfile.mkdtemp(prefix="wows_capture_"))
        logger.debug(f"Created temp directory: {self._temp_dir}")

        self._raw_video_file = self._temp_dir / "video.raw"
        self._raw_video_handle = open(self._raw_video_file, "wb")

        if self.config.capture_audio:
            self._raw_audio_file = self._temp_dir / "audio.wav"
            self._raw_audio_handle = wave.open(str(self._raw_audio_file), "wb")
            self._raw_audio_handle.setnchannels(self.AUDIO_CHANNELS)
            self._raw_audio_handle.setsampwidth(self.AUDIO_SAMPLE_WIDTH)
            self._raw_audio_handle.setframerate(self.AUDIO_SAMPLE_RATE)

    def write_frame(self, frame: np.ndarray, timestamp: float):
        """
        Write a video frame.

        Args:
            frame: Frame data as numpy array (BGRA format)
            timestamp: Frame timestamp in seconds
        """
        with self._lock:
            if not self._running:
                return

        try:
            self._video_queue.put_nowait((frame.tobytes(), timestamp))
        except Exception:
            self._dropped_frames += 1
            if self._dropped_frames % DROPPED_FRAME_LOG_INTERVAL == 1:
                logger.debug(f"Dropped {self._dropped_frames} video frames")

    def write_audio(self, audio: np.ndarray, timestamp: float):
        """
        Write audio data.

        Args:
            audio: Audio data as numpy array (int16)
            timestamp: Audio timestamp in seconds
        """
        with self._lock:
            if not self._running or not self.config.capture_audio:
                return

        try:
            self._audio_queue.put_nowait((audio.tobytes(), timestamp))
        except Exception:
            self._dropped_audio += 1
            if self._dropped_audio % DROPPED_FRAME_LOG_INTERVAL == 1:
                logger.debug(f"Dropped {self._dropped_audio} audio chunks")

    def _video_writer_loop(self):
        """Write video frames to temp file."""
        while True:
            with self._lock:
                running = self._running
                queue_empty = self._video_queue.empty()

            if not running and queue_empty:
                break

            try:
                frame_data, _ = self._video_queue.get(timeout=0.1)
                if self._raw_video_handle:
                    self._raw_video_handle.write(frame_data)
                    self._frame_count += 1
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error writing video frame: {e}")
                break

        logger.debug(f"Video writer finished: {self._frame_count} frames written")

    def _audio_writer_loop(self):
        """Write audio chunks to temp WAV file."""
        while True:
            with self._lock:
                running = self._running
                queue_empty = self._audio_queue.empty()

            if not running and queue_empty:
                break

            try:
                audio_data, _ = self._audio_queue.get(timeout=0.1)
                if self._raw_audio_handle:
                    self._raw_audio_handle.writeframes(audio_data)
                    self._audio_chunks += 1
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error writing audio chunk: {e}")
                break

        logger.debug(f"Audio writer finished: {self._audio_chunks} chunks written")

    def stop(self) -> Optional[Path]:
        """
        Stop the encoder and finalize the video file.

        Returns:
            Path to the output file if successful, None otherwise
        """
        with self._lock:
            if not self._running:
                return None
            self._running = False

        logger.info("Stopping encoder and finalizing video...")

        # Wait for writer threads to finish
        if self._video_writer_thread is not None:
            self._video_writer_thread.join(timeout=10.0)

        if self._audio_writer_thread is not None:
            self._audio_writer_thread.join(timeout=10.0)

        # Close file handles
        self._close_file_handles()

        # Log stats
        if self._dropped_frames > 0:
            logger.warning(f"Dropped {self._dropped_frames} video frames during capture")
        if self._dropped_audio > 0:
            logger.warning(f"Dropped {self._dropped_audio} audio chunks during capture")

        # Encode with FFmpeg
        result = self._encode_with_ffmpeg()

        # Cleanup temp files
        self._cleanup_temp_files()

        return result

    def _close_file_handles(self):
        """Close open file handles."""
        if self._raw_video_handle is not None:
            try:
                self._raw_video_handle.close()
            except Exception:
                pass
            self._raw_video_handle = None

        if self._raw_audio_handle is not None:
            try:
                self._raw_audio_handle.close()
            except Exception:
                pass
            self._raw_audio_handle = None

    def _encode_with_ffmpeg(self) -> Optional[Path]:
        """Encode raw files to final MP4 using FFmpeg."""
        if self._frame_count == 0:
            logger.error("No frames captured")
            return None

        quality = self.config.get_quality_preset()
        video_size = f"{self._width}x{self._height}"

        cmd = [
            self._ffmpeg_path,
            "-y",  # Overwrite output
            # Video input
            "-f", "rawvideo",
            "-pixel_format", "bgra",
            "-video_size", video_size,
            "-framerate", str(self.config.target_fps),
            "-i", str(self._raw_video_file),
        ]

        # Audio input (if available)
        has_audio = (
            self.config.capture_audio
            and self._raw_audio_file is not None
            and self._raw_audio_file.exists()
            and self._raw_audio_file.stat().st_size > 44  # WAV header size
        )

        if has_audio:
            cmd.extend(["-i", str(self._raw_audio_file)])

        # Video encoding settings
        cmd.extend([
            "-c:v", "libx264",
            "-preset", quality["preset"],
            "-crf", str(quality["crf"]),
            "-pix_fmt", "yuv420p",
        ])

        # Audio encoding settings
        if has_audio:
            cmd.extend([
                "-c:a", "aac",
                "-b:a", "192k",
            ])

        # Output settings
        cmd.extend([
            "-movflags", "+faststart",
            str(self.output_path),
        ])

        logger.debug(f"FFmpeg command: {' '.join(cmd)}")

        try:
            # Hide console window on Windows
            startupinfo = None
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
            )

            _, stderr = process.communicate(timeout=300)  # 5 minute timeout

            if process.returncode != 0:
                stderr_text = stderr.decode("utf-8", errors="ignore")
                logger.error(f"FFmpeg error (code {process.returncode}): {stderr_text}")
                return None

            if self.output_path.exists() and self.output_path.stat().st_size > 0:
                logger.info(f"Video saved: {self.output_path}")
                return self.output_path
            else:
                logger.error("Output file is empty or missing")
                return None

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg encoding timed out")
            process.kill()
            return None

        except Exception as e:
            logger.error(f"FFmpeg encoding error: {e}")
            return None

    def _cleanup_temp_files(self):
        """Clean up temporary files."""
        if self._temp_dir is not None and self._temp_dir.exists():
            try:
                shutil.rmtree(self._temp_dir)
                logger.debug(f"Cleaned up temp directory: {self._temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp files: {e}")
            self._temp_dir = None

        self._raw_video_file = None
        self._raw_audio_file = None

    def is_running(self) -> bool:
        """Check if encoder is running."""
        with self._lock:
            return self._running


class MockVideoEncoder:
    """Mock video encoder for testing."""

    def __init__(self, config: CaptureConfig, output_path: Path):
        self.config = config
        self.output_path = output_path
        self._running = False
        self._frame_count = 0
        self._audio_chunk_count = 0
        self._lock = threading.Lock()

    @staticmethod
    def is_available() -> bool:
        return True

    def start(self, width: int, height: int) -> bool:
        with self._lock:
            self._running = True
        logger.info(f"Mock encoder started: {width}x{height}")
        return True

    def write_frame(self, frame: np.ndarray, timestamp: float):
        with self._lock:
            if self._running:
                self._frame_count += 1

    def write_audio(self, audio: np.ndarray, timestamp: float):
        with self._lock:
            if self._running:
                self._audio_chunk_count += 1

    def stop(self) -> Optional[Path]:
        with self._lock:
            self._running = False

        logger.info(
            f"Mock encoder stopped: {self._frame_count} frames, "
            f"{self._audio_chunk_count} audio chunks"
        )

        # Write a minimal valid file for testing
        self.output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.output_path, "wb") as f:
            f.write(b"MOCK_VIDEO_DATA")
        return self.output_path

    def is_running(self) -> bool:
        with self._lock:
            return self._running
