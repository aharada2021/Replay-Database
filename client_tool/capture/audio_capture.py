"""
Audio capture using PyAudioWPatch for WASAPI loopback capture.
"""

import logging
import threading
import time
from dataclasses import dataclass
from typing import Callable, List, Optional

import numpy as np

from .config import CaptureConfig
from .exceptions import AudioDeviceError

logger = logging.getLogger(__name__)

# Try to import PyAudioWPatch for WASAPI loopback support
try:
    import pyaudiowpatch as pyaudio

    PYAUDIO_AVAILABLE = True
except ImportError:
    try:
        import pyaudio

        PYAUDIO_AVAILABLE = True
        logger.warning("PyAudioWPatch not available, using standard PyAudio")
    except ImportError:
        PYAUDIO_AVAILABLE = False
        pyaudio = None
        logger.warning("PyAudio not available - audio capture disabled")


@dataclass
class AudioDevice:
    """Information about an audio device."""

    index: int
    name: str
    channels: int
    sample_rate: int
    is_loopback: bool


class AudioCapture:
    """
    Audio capture for desktop audio and microphone.

    Uses PyAudioWPatch for WASAPI loopback capture of desktop audio,
    and standard audio input for microphone capture.
    """

    SAMPLE_RATE = 44100
    CHANNELS = 2
    CHUNK_SIZE = 1024
    FORMAT = pyaudio.paInt16 if pyaudio else None

    def __init__(
        self,
        config: CaptureConfig,
        audio_callback: Callable[[np.ndarray, float], None],
    ):
        """
        Initialize audio capture.

        Args:
            config: Capture configuration
            audio_callback: Callback for audio data (audio_data, timestamp)
        """
        self.config = config
        self.audio_callback = audio_callback
        self._pa: Optional["pyaudio.PyAudio"] = None
        self._loopback_stream = None
        self._mic_stream = None
        self._running = False
        self._lock = threading.Lock()
        self._start_time: Optional[float] = None
        self._capture_thread: Optional[threading.Thread] = None

    @staticmethod
    def is_available() -> bool:
        """Check if audio capture is available."""
        return PYAUDIO_AVAILABLE

    def list_devices(self) -> List[AudioDevice]:
        """List available audio devices."""
        if not self.is_available():
            return []

        devices = []
        pa = pyaudio.PyAudio()

        try:
            for i in range(pa.get_device_count()):
                try:
                    info = pa.get_device_info_by_index(i)
                    is_loopback = info.get("isLoopbackDevice", False)
                    devices.append(
                        AudioDevice(
                            index=i,
                            name=info.get("name", f"Device {i}"),
                            channels=info.get("maxInputChannels", 0),
                            sample_rate=int(info.get("defaultSampleRate", 44100)),
                            is_loopback=is_loopback,
                        )
                    )
                except Exception as e:
                    logger.debug(f"Error getting device {i} info: {e}")
        finally:
            pa.terminate()

        return devices

    def _find_loopback_device(self) -> Optional[int]:
        """Find the default loopback device for desktop audio capture."""
        if not self.is_available():
            return None

        try:
            wasapi_info = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_speakers = self._pa.get_device_info_by_index(
                wasapi_info["defaultOutputDevice"]
            )

            if not default_speakers.get("isLoopbackDevice", False):
                for i in range(self._pa.get_device_count()):
                    info = self._pa.get_device_info_by_index(i)
                    if (
                        info.get("isLoopbackDevice", False)
                        and info.get("hostApi") == wasapi_info["index"]
                    ):
                        logger.info(f"Found loopback device: {info['name']}")
                        return i

            return default_speakers["index"]
        except Exception as e:
            logger.warning(f"Could not find loopback device: {e}")
            return None

    def _find_mic_device(self) -> Optional[int]:
        """Find the default microphone device."""
        if not self.is_available():
            return None

        try:
            default_input = self._pa.get_default_input_device_info()
            logger.info(f"Found microphone device: {default_input['name']}")
            return default_input["index"]
        except Exception as e:
            logger.warning(f"Could not find microphone device: {e}")
            return None

    def start(self) -> bool:
        """
        Start audio capture.

        Returns:
            True if capture started successfully
        """
        if not self.is_available():
            logger.error("Audio capture not available")
            return False

        with self._lock:
            if self._running:
                logger.warning("Audio capture already running")
                return True

            try:
                self._pa = pyaudio.PyAudio()
                self._start_time = time.perf_counter()

                if self.config.capture_audio:
                    self._start_loopback_capture()

                if self.config.capture_microphone:
                    self._start_mic_capture()

                self._running = True
                self._capture_thread = threading.Thread(
                    target=self._capture_loop, daemon=True
                )
                self._capture_thread.start()

                logger.info("Audio capture started")
                return True

            except Exception as e:
                logger.error(f"Failed to start audio capture: {e}")
                self._cleanup()
                raise AudioDeviceError(f"Failed to start audio capture: {e}")

    def _start_loopback_capture(self):
        """Start desktop audio (loopback) capture."""
        loopback_device = self._find_loopback_device()
        if loopback_device is None:
            logger.warning("No loopback device found, desktop audio disabled")
            return

        try:
            device_info = self._pa.get_device_info_by_index(loopback_device)
            channels = min(int(device_info.get("maxInputChannels", 2)), 2)
            sample_rate = int(device_info.get("defaultSampleRate", self.SAMPLE_RATE))

            self._loopback_stream = self._pa.open(
                format=self.FORMAT,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=loopback_device,
                frames_per_buffer=self.CHUNK_SIZE,
            )
            logger.info(
                f"Loopback capture started: {channels}ch @ {sample_rate}Hz"
            )
        except Exception as e:
            logger.warning(f"Failed to start loopback capture: {e}")
            self._loopback_stream = None

    def _start_mic_capture(self):
        """Start microphone capture."""
        mic_device = self._find_mic_device()
        if mic_device is None:
            logger.warning("No microphone found, mic capture disabled")
            return

        try:
            device_info = self._pa.get_device_info_by_index(mic_device)
            channels = min(int(device_info.get("maxInputChannels", 1)), 2)
            sample_rate = int(device_info.get("defaultSampleRate", self.SAMPLE_RATE))

            self._mic_stream = self._pa.open(
                format=self.FORMAT,
                channels=channels,
                rate=sample_rate,
                input=True,
                input_device_index=mic_device,
                frames_per_buffer=self.CHUNK_SIZE,
            )
            logger.info(f"Mic capture started: {channels}ch @ {sample_rate}Hz")
        except Exception as e:
            logger.warning(f"Failed to start mic capture: {e}")
            self._mic_stream = None

    def _capture_loop(self):
        """Main capture loop for reading audio data."""
        while True:
            # Check running state under lock
            with self._lock:
                if not self._running:
                    break
                start_time = self._start_time
                loopback_stream = self._loopback_stream
                mic_stream = self._mic_stream

            try:
                timestamp = time.perf_counter() - start_time

                loopback_data = None
                mic_data = None

                if loopback_stream is not None:
                    try:
                        raw_data = loopback_stream.read(
                            self.CHUNK_SIZE, exception_on_overflow=False
                        )
                        loopback_data = np.frombuffer(raw_data, dtype=np.int16)
                    except Exception as e:
                        logger.debug(f"Loopback read error: {e}")

                if mic_stream is not None:
                    try:
                        raw_data = mic_stream.read(
                            self.CHUNK_SIZE, exception_on_overflow=False
                        )
                        mic_data = np.frombuffer(raw_data, dtype=np.int16)

                        if self.config.mic_volume != 1.0:
                            mic_data = (
                                mic_data.astype(np.float32) * self.config.mic_volume
                            ).astype(np.int16)
                    except Exception as e:
                        logger.debug(f"Mic read error: {e}")

                mixed_audio = self._mix_audio(loopback_data, mic_data)

                if mixed_audio is not None:
                    self.audio_callback(mixed_audio, timestamp)

            except Exception as e:
                logger.error(f"Audio capture error: {e}")
                time.sleep(0.01)

    def _mix_audio(
        self, loopback: Optional[np.ndarray], mic: Optional[np.ndarray]
    ) -> Optional[np.ndarray]:
        """Mix loopback and microphone audio."""
        if loopback is None and mic is None:
            return None

        if loopback is None:
            return mic

        if mic is None:
            return loopback

        if len(loopback) == len(mic):
            mixed = loopback.astype(np.float32) + mic.astype(np.float32)
        else:
            target_len = max(len(loopback), len(mic))
            loopback_padded = np.zeros(target_len, dtype=np.float32)
            mic_padded = np.zeros(target_len, dtype=np.float32)
            loopback_padded[: len(loopback)] = loopback
            mic_padded[: len(mic)] = mic
            mixed = loopback_padded + mic_padded

        mixed = np.clip(mixed, -32768, 32767).astype(np.int16)
        return mixed

    def stop(self):
        """Stop audio capture."""
        with self._lock:
            if not self._running:
                return

            self._running = False

        if self._capture_thread is not None:
            self._capture_thread.join(timeout=2.0)

        self._cleanup()
        logger.info("Audio capture stopped")

    def _cleanup(self):
        """Clean up audio resources."""
        if self._loopback_stream is not None:
            try:
                self._loopback_stream.stop_stream()
                self._loopback_stream.close()
            except Exception:
                pass
            self._loopback_stream = None

        if self._mic_stream is not None:
            try:
                self._mic_stream.stop_stream()
                self._mic_stream.close()
            except Exception:
                pass
            self._mic_stream = None

        if self._pa is not None:
            try:
                self._pa.terminate()
            except Exception:
                pass
            self._pa = None

    def is_running(self) -> bool:
        """Check if audio capture is running."""
        with self._lock:
            return self._running


class MockAudioCapture:
    """Mock audio capture for testing without audio dependencies."""

    SAMPLE_RATE = 44100
    CHANNELS = 2
    CHUNK_SIZE = 1024

    def __init__(
        self,
        config: CaptureConfig,
        audio_callback: Callable[[np.ndarray, float], None],
    ):
        self.config = config
        self.audio_callback = audio_callback
        self._running = False
        self._thread: Optional[threading.Thread] = None

    @staticmethod
    def is_available() -> bool:
        return True

    def list_devices(self) -> List[AudioDevice]:
        return [
            AudioDevice(
                index=0,
                name="Mock Loopback Device",
                channels=2,
                sample_rate=44100,
                is_loopback=True,
            ),
            AudioDevice(
                index=1,
                name="Mock Microphone",
                channels=1,
                sample_rate=44100,
                is_loopback=False,
            ),
        ]

    def start(self) -> bool:
        if self._running:
            return True

        self._running = True
        self._thread = threading.Thread(target=self._generate_audio, daemon=True)
        self._thread.start()
        logger.info("Mock audio capture started")
        return True

    def _generate_audio(self):
        """Generate silent audio for testing."""
        start_time = time.perf_counter()
        chunk_duration = self.CHUNK_SIZE / self.SAMPLE_RATE

        while self._running:
            timestamp = time.perf_counter() - start_time

            audio = np.zeros(self.CHUNK_SIZE * self.CHANNELS, dtype=np.int16)
            self.audio_callback(audio, timestamp)

            time.sleep(chunk_duration)

    def stop(self):
        self._running = False
        if self._thread is not None:
            self._thread.join(timeout=2.0)
        logger.info("Mock audio capture stopped")

    def is_running(self) -> bool:
        return self._running
