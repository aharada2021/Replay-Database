"""
Video encoder using FFmpeg subprocess for H.264 encoding.

Uses real-time encoding approach:
1. Pipe raw video frames directly to FFmpeg for immediate H.264 encoding
2. Write audio to a small temp WAV file
3. Quick mux at the end to combine video and audio

This approach avoids huge temporary raw video files (100GB+ for 20min capture).
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
    Video encoder using FFmpeg for real-time H.264 encoding.

    Encodes video frames in real-time by piping directly to FFmpeg,
    avoiding huge temporary raw video files. Audio is stored in a
    small temp WAV file and muxed at the end.
    """

    AUDIO_SAMPLE_RATE = 48000  # Match WASAPI loopback device default
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

        # FFmpeg process for real-time video encoding
        self._ffmpeg_process: Optional[subprocess.Popen] = None

        # Temp files
        self._temp_dir: Optional[Path] = None
        self._temp_video_file: Optional[Path] = None  # Encoded video (no audio)
        self._temp_audio_file: Optional[Path] = None  # WAV audio
        self._audio_handle = None

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
                self._setup_encoding()
                self._running = True

                # Start video writer thread (pipes to FFmpeg)
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

                logger.info(
                    f"Video encoder started (real-time): {self._width}x{self._height} "
                    f"@ {self.config.target_fps}fps, audio={self.config.capture_audio}"
                )
                return True

            except Exception as e:
                logger.error(f"Failed to start encoder: {e}")
                self._cleanup()
                raise EncoderError(f"Failed to start encoder: {e}")

    def _setup_encoding(self):
        """Set up FFmpeg process for real-time encoding and audio temp file."""
        self._temp_dir = Path(tempfile.mkdtemp(prefix="wows_capture_"))
        logger.debug(f"Created temp directory: {self._temp_dir}")

        # Temp file for encoded video (will be muxed with audio at the end)
        self._temp_video_file = self._temp_dir / "video.mp4"

        # Start FFmpeg process for real-time video encoding
        quality = self.config.get_quality_preset()
        video_size = f"{self._width}x{self._height}"

        # Use 'fast' preset for real-time encoding (balance between speed and quality)
        # The configured preset is used for final quality, but we need fast encoding
        realtime_preset = "fast" if quality["preset"] in ("medium", "slow") else quality["preset"]

        cmd = [
            self._ffmpeg_path,
            "-y",  # Overwrite output
            "-f", "rawvideo",
            "-pixel_format", "bgra",
            "-video_size", video_size,
            "-framerate", str(self.config.target_fps),
            "-i", "pipe:0",  # Read from stdin
            "-c:v", "libx264",
            "-preset", realtime_preset,
            "-crf", str(quality["crf"]),
            "-pix_fmt", "yuv420p",
            "-movflags", "+faststart",
            str(self._temp_video_file),
        ]

        logger.debug(f"FFmpeg real-time command: {' '.join(cmd)}")

        # Hide console window on Windows
        startupinfo = None
        creationflags = 0
        if platform.system() == "Windows":
            startupinfo = subprocess.STARTUPINFO()
            startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
            startupinfo.wShowWindow = subprocess.SW_HIDE
            creationflags = subprocess.CREATE_NO_WINDOW

        self._ffmpeg_process = subprocess.Popen(
            cmd,
            stdin=subprocess.PIPE,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            startupinfo=startupinfo,
            creationflags=creationflags,
        )

        # Set up audio temp file
        if self.config.capture_audio:
            self._temp_audio_file = self._temp_dir / "audio.wav"
            self._audio_handle = wave.open(str(self._temp_audio_file), "wb")
            self._audio_handle.setnchannels(self.AUDIO_CHANNELS)
            self._audio_handle.setsampwidth(self.AUDIO_SAMPLE_WIDTH)
            self._audio_handle.setframerate(self.AUDIO_SAMPLE_RATE)

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
            if not self._running:
                return
            if not self.config.capture_audio:
                return

        try:
            audio_bytes = audio.tobytes()
            self._audio_queue.put_nowait((audio_bytes, timestamp))
            if self._audio_chunks == 0 and self._audio_queue.qsize() == 1:
                logger.debug(f"First audio chunk queued: {len(audio_bytes)} bytes")
        except Exception:
            self._dropped_audio += 1
            if self._dropped_audio % DROPPED_FRAME_LOG_INTERVAL == 1:
                logger.debug(f"Dropped {self._dropped_audio} audio chunks")

    def _video_writer_loop(self):
        """Write video frames directly to FFmpeg stdin for real-time encoding."""
        logger.debug("Video writer thread started (real-time encoding)")
        bytes_written = 0

        while True:
            with self._lock:
                running = self._running
                queue_empty = self._video_queue.empty()

            if not running and queue_empty:
                break

            try:
                frame_data, _ = self._video_queue.get(timeout=0.1)
                if self._ffmpeg_process and self._ffmpeg_process.stdin:
                    self._ffmpeg_process.stdin.write(frame_data)
                    self._frame_count += 1
                    bytes_written += len(frame_data)

                    # Log progress periodically
                    if self._frame_count == 1:
                        logger.debug(f"First frame sent to FFmpeg: {len(frame_data)} bytes")
                    elif self._frame_count % 300 == 0:  # Every 10 seconds at 30fps
                        mb_written = bytes_written / (1024 * 1024)
                        logger.debug(f"Frames encoded: {self._frame_count}, raw data: {mb_written:.1f} MB")

            except Empty:
                continue
            except BrokenPipeError:
                logger.error("FFmpeg pipe broken - encoder may have crashed")
                break
            except Exception as e:
                logger.error(f"Error writing video frame: {e}")
                break

        # Close FFmpeg stdin to signal end of input
        if self._ffmpeg_process and self._ffmpeg_process.stdin:
            try:
                self._ffmpeg_process.stdin.close()
            except Exception:
                pass

        logger.debug(f"Video writer finished: {self._frame_count} frames encoded")

    def _audio_writer_loop(self):
        """Write audio chunks to temp WAV file."""
        logger.info("Audio writer thread started")

        while True:
            with self._lock:
                running = self._running
                queue_empty = self._audio_queue.empty()

            if not running and queue_empty:
                break

            try:
                audio_data, _ = self._audio_queue.get(timeout=0.1)
                if self._audio_handle:
                    self._audio_handle.writeframes(audio_data)
                    self._audio_chunks += 1
                    if self._audio_chunks == 1:
                        logger.info(f"First audio chunk written to WAV: {len(audio_data)} bytes")
                    elif self._audio_chunks % 1000 == 0:
                        logger.info(f"Audio chunks written: {self._audio_chunks}")
            except Empty:
                continue
            except Exception as e:
                logger.error(f"Error writing audio chunk: {e}")
                break

        logger.info(f"Audio writer finished: {self._audio_chunks} chunks written")

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

        logger.info("Stopping encoder...")

        # Wait for writer threads to finish
        if self._video_writer_thread is not None:
            self._video_writer_thread.join(timeout=30.0)
            logger.debug("Video writer thread joined")

        if self._audio_writer_thread is not None:
            self._audio_writer_thread.join(timeout=10.0)
            logger.debug("Audio writer thread joined")

        # Close audio file handle
        if self._audio_handle is not None:
            try:
                self._audio_handle.close()
            except Exception:
                pass
            self._audio_handle = None

        # Wait for FFmpeg to finish encoding
        if self._ffmpeg_process is not None:
            try:
                logger.info("Waiting for FFmpeg to finish encoding...")
                _, stderr = self._ffmpeg_process.communicate(timeout=120)

                if self._ffmpeg_process.returncode != 0:
                    stderr_text = stderr.decode("utf-8", errors="ignore")
                    logger.error(f"FFmpeg error (code {self._ffmpeg_process.returncode}): {stderr_text[-500:]}")
            except subprocess.TimeoutExpired:
                logger.error("FFmpeg encoding timed out")
                self._ffmpeg_process.kill()
            except Exception as e:
                logger.error(f"Error waiting for FFmpeg: {e}")

            self._ffmpeg_process = None

        # Log stats
        if self._dropped_frames > 0:
            logger.warning(f"Dropped {self._dropped_frames} video frames during capture")
        if self._dropped_audio > 0:
            logger.warning(f"Dropped {self._dropped_audio} audio chunks during capture")

        # Mux video and audio if needed
        result = self._finalize_output()

        # Cleanup temp files
        self._cleanup()

        return result

    def _finalize_output(self) -> Optional[Path]:
        """Mux encoded video with audio (if present) to create final output."""
        logger.debug(f"Finalizing output to: {self.output_path}")
        logger.debug(f"Temp video file: {self._temp_video_file}")

        if not self._temp_video_file or not self._temp_video_file.exists():
            logger.error("Encoded video file not found")
            return None

        video_size = self._temp_video_file.stat().st_size
        logger.debug(f"Temp video size: {video_size / (1024*1024):.1f} MB")

        if video_size == 0:
            logger.error("Encoded video file is empty")
            return None

        # Check if we have audio to mux
        audio_size = 0
        if self._temp_audio_file and self._temp_audio_file.exists():
            audio_size = self._temp_audio_file.stat().st_size
            logger.debug(f"Temp audio size: {audio_size} bytes")

        has_audio = (
            self.config.capture_audio
            and self._temp_audio_file is not None
            and self._temp_audio_file.exists()
            and audio_size > 44  # WAV header size
        )

        # Ensure output directory exists
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        if not has_audio:
            # No audio - just copy the video file (use copy instead of move for reliability)
            logger.info("No audio to mux, using video-only output")
            try:
                shutil.copy2(str(self._temp_video_file), str(self.output_path))
                if self.output_path.exists():
                    size_mb = self.output_path.stat().st_size / (1024 * 1024)
                    logger.info(f"Video saved: {self.output_path} ({size_mb:.1f} MB)")
                    return self.output_path
                else:
                    logger.error(f"Output file not created: {self.output_path}")
                    return None
            except Exception as e:
                logger.error(f"Failed to copy video file: {e}")
                import traceback
                logger.error(traceback.format_exc())
                return None

        # Mux video and audio
        logger.info("Muxing video and audio...")
        cmd = [
            self._ffmpeg_path,
            "-y",
            "-i", str(self._temp_video_file),
            "-i", str(self._temp_audio_file),
            "-c:v", "copy",  # Copy video stream (already encoded)
            "-c:a", "aac",
            "-b:a", "192k",
            "-shortest",  # End when shortest stream ends
            "-movflags", "+faststart",
            str(self.output_path),
        ]

        logger.debug(f"FFmpeg mux command: {' '.join(cmd)}")

        try:
            startupinfo = None
            creationflags = 0
            if platform.system() == "Windows":
                startupinfo = subprocess.STARTUPINFO()
                startupinfo.dwFlags |= subprocess.STARTF_USESHOWWINDOW
                startupinfo.wShowWindow = subprocess.SW_HIDE
                creationflags = subprocess.CREATE_NO_WINDOW

            process = subprocess.Popen(
                cmd,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                startupinfo=startupinfo,
                creationflags=creationflags,
            )

            _, stderr = process.communicate(timeout=120)

            if process.returncode != 0:
                stderr_text = stderr.decode("utf-8", errors="ignore")
                logger.error(f"FFmpeg mux error: {stderr_text[-500:]}")
                # Fall back to video-only
                logger.warning("Falling back to video-only output")
                shutil.move(str(self._temp_video_file), str(self.output_path))

            if self.output_path.exists() and self.output_path.stat().st_size > 0:
                size_mb = self.output_path.stat().st_size / (1024 * 1024)
                logger.info(f"Video saved: {self.output_path} ({size_mb:.1f} MB)")
                return self.output_path
            else:
                logger.error("Output file is empty or missing")
                return None

        except subprocess.TimeoutExpired:
            logger.error("FFmpeg mux timed out")
            process.kill()
            return None
        except Exception as e:
            logger.error(f"FFmpeg mux error: {e}")
            return None

    def _cleanup(self):
        """Clean up temporary files and resources."""
        if self._ffmpeg_process is not None:
            try:
                self._ffmpeg_process.kill()
            except Exception:
                pass
            self._ffmpeg_process = None

        if self._audio_handle is not None:
            try:
                self._audio_handle.close()
            except Exception:
                pass
            self._audio_handle = None

        if self._temp_dir is not None and self._temp_dir.exists():
            try:
                shutil.rmtree(self._temp_dir)
                logger.debug(f"Cleaned up temp directory: {self._temp_dir}")
            except Exception as e:
                logger.warning(f"Failed to cleanup temp files: {e}")
            self._temp_dir = None

        self._temp_video_file = None
        self._temp_audio_file = None

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
