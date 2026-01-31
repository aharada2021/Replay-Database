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

        # Callback buffer for loopback audio
        self._loopback_buffer = []
        self._loopback_channels = 2
        self._loopback_sample_rate = self.SAMPLE_RATE
        self._loopback_reader_thread: Optional[threading.Thread] = None

        # Buffer for mic audio
        self._mic_buffer = []
        self._mic_channels = 1
        self._mic_sample_rate = self.SAMPLE_RATE
        self._mic_reader_thread: Optional[threading.Thread] = None

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
        """Find the loopback device for the default audio output."""
        if not self.is_available():
            return None

        try:
            wasapi_info = self._pa.get_host_api_info_by_type(pyaudio.paWASAPI)
            default_output_idx = wasapi_info["defaultOutputDevice"]
            default_output = self._pa.get_device_info_by_index(default_output_idx)
            default_output_name = default_output.get("name", "")

            logger.info(f"Default output device: {default_output_name} (index {default_output_idx})")

            # Find the loopback device that matches the default output
            # Loopback device names usually contain the output device name + "[Loopback]"
            best_match = None
            best_match_score = 0

            for i in range(self._pa.get_device_count()):
                info = self._pa.get_device_info_by_index(i)
                if info.get("isLoopbackDevice", False):
                    loopback_name = info.get("name", "")

                    # Check if this loopback matches the default output
                    # Remove "[Loopback]" suffix for comparison
                    base_name = loopback_name.replace("[Loopback]", "").strip()

                    # Score based on name similarity
                    if default_output_name in loopback_name or base_name in default_output_name:
                        score = len(base_name)
                        if score > best_match_score:
                            best_match = i
                            best_match_score = score
                            logger.debug(f"Loopback candidate: {loopback_name} (score={score})")

            if best_match is not None:
                match_info = self._pa.get_device_info_by_index(best_match)
                logger.info(f"Found loopback device: {match_info['name']}")
                return best_match

            # Fallback: return first loopback device
            for i in range(self._pa.get_device_count()):
                info = self._pa.get_device_info_by_index(i)
                if info.get("isLoopbackDevice", False):
                    logger.warning(f"Using fallback loopback device: {info['name']}")
                    return i

            return None
        except Exception as e:
            logger.warning(f"Could not find loopback device: {e}")
            import traceback
            logger.debug(traceback.format_exc())
            return None

    def _find_mic_device(self) -> Optional[int]:
        """Find the default microphone device."""
        if not self.is_available():
            return None

        # Try to get default input device first
        try:
            default_input = self._pa.get_default_input_device_info()
            logger.info(f"Found default microphone: {default_input['name']}")
            return default_input["index"]
        except Exception as e:
            logger.debug(f"No default input device: {e}")

        # Fallback: search for a microphone device
        try:
            for i in range(self._pa.get_device_count()):
                info = self._pa.get_device_info_by_index(i)
                name = info.get("name", "").lower()
                max_input_channels = info.get("maxInputChannels", 0)

                # Look for devices with "マイク" or "mic" in the name that have input channels
                if max_input_channels > 0 and not info.get("isLoopbackDevice", False):
                    if "マイク" in info.get("name", "") or "mic" in name or "microphone" in name:
                        logger.info(f"Found microphone device: {info['name']} (index {i})")
                        return i

            # Last fallback: any device with input channels that's not loopback
            for i in range(self._pa.get_device_count()):
                info = self._pa.get_device_info_by_index(i)
                max_input_channels = info.get("maxInputChannels", 0)
                if max_input_channels > 0 and not info.get("isLoopbackDevice", False):
                    logger.info(f"Found input device (fallback): {info['name']} (index {i})")
                    return i

        except Exception as e:
            logger.warning(f"Error searching for microphone: {e}")

        logger.warning("No microphone device found")
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
                self._running = True  # Set before starting threads

                if self.config.capture_audio:
                    self._start_loopback_capture()

                if self.config.capture_microphone:
                    self._start_mic_capture()

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
        """Start desktop audio (loopback) capture using blocking read with dedicated thread."""
        # Check for override device (for testing)
        if hasattr(self, '_override_loopback_device') and self._override_loopback_device is not None:
            loopback_device = self._override_loopback_device
            logger.info(f"Using override loopback device: {loopback_device}")
        else:
            loopback_device = self._find_loopback_device()

        if loopback_device is None:
            logger.warning("No loopback device found, desktop audio disabled")
            return

        try:
            device_info = self._pa.get_device_info_by_index(loopback_device)
            self._loopback_channels = min(int(device_info.get("maxInputChannels", 2)), 2)
            self._loopback_sample_rate = int(device_info.get("defaultSampleRate", self.SAMPLE_RATE))

            # Use blocking mode with dedicated reader thread
            self._loopback_buffer = []
            self._loopback_stream = self._pa.open(
                format=self.FORMAT,
                channels=self._loopback_channels,
                rate=self._loopback_sample_rate,
                input=True,
                input_device_index=loopback_device,
                frames_per_buffer=self.CHUNK_SIZE,
            )

            # Start dedicated reader thread for loopback
            self._loopback_reader_thread = threading.Thread(
                target=self._loopback_reader_loop,
                daemon=True,
                name="LoopbackReader"
            )
            self._loopback_reader_thread.start()

            logger.info(
                f"Loopback capture started (blocking mode): {self._loopback_channels}ch @ {self._loopback_sample_rate}Hz"
            )
        except Exception as e:
            logger.warning(f"Failed to start loopback capture: {e}")
            import traceback
            logger.warning(traceback.format_exc())
            self._loopback_stream = None

    def _loopback_reader_loop(self):
        """Dedicated thread for reading loopback audio (blocking reads)."""
        logger.info("Loopback reader thread started")
        print("[AUDIO] Loopback reader thread started")
        read_count = 0

        try:
            while self._running:
                if self._loopback_stream is None:
                    logger.warning("Loopback stream is None, exiting reader loop")
                    break

                if not self._loopback_stream.is_active():
                    logger.warning("Loopback stream is not active")
                    # Try to start it
                    try:
                        self._loopback_stream.start_stream()
                        logger.info("Started loopback stream")
                    except Exception as e:
                        logger.error(f"Failed to start stream: {e}")
                        break

                try:
                    # Read with exception_on_overflow=False to avoid errors
                    raw_data = self._loopback_stream.read(
                        self.CHUNK_SIZE,
                        exception_on_overflow=False
                    )

                    if raw_data:
                        audio_data = np.frombuffer(raw_data, dtype=np.int16)
                        read_count += 1

                        if read_count == 1:
                            max_amp = np.max(np.abs(audio_data)) if len(audio_data) > 0 else 0
                            logger.info(f"Loopback first read: {len(audio_data)} samples, max_amp={max_amp}")
                            print(f"[AUDIO] First loopback read: {len(audio_data)} samples, max_amp={max_amp}")

                        with self._lock:
                            self._loopback_buffer.append(audio_data.copy())

                        if read_count % 1000 == 0:
                            logger.debug(f"Loopback reads: {read_count}")

                except IOError as e:
                    if self._running:
                        logger.warning(f"Loopback IOError: {e}")
                    time.sleep(0.01)
                except Exception as e:
                    if self._running:
                        logger.error(f"Loopback read error: {type(e).__name__}: {e}")
                        import traceback
                        logger.error(traceback.format_exc())
                    break

        except Exception as e:
            logger.error(f"Loopback reader loop error: {type(e).__name__}: {e}")
            import traceback
            logger.error(traceback.format_exc())

        logger.info(f"Loopback reader thread stopped after {read_count} reads")
        print(f"[AUDIO] Loopback reader thread stopped after {read_count} reads")

    def _start_mic_capture(self):
        """Start microphone capture with dedicated reader thread."""
        mic_device = self._find_mic_device()
        if mic_device is None:
            logger.warning("No microphone found, mic capture disabled")
            return

        try:
            device_info = self._pa.get_device_info_by_index(mic_device)
            self._mic_channels = min(int(device_info.get("maxInputChannels", 1)), 2)
            self._mic_sample_rate = int(device_info.get("defaultSampleRate", self.SAMPLE_RATE))

            self._mic_buffer = []
            self._mic_stream = self._pa.open(
                format=self.FORMAT,
                channels=self._mic_channels,
                rate=self._mic_sample_rate,
                input=True,
                input_device_index=mic_device,
                frames_per_buffer=self.CHUNK_SIZE,
            )

            # Start dedicated reader thread for mic
            self._mic_reader_thread = threading.Thread(
                target=self._mic_reader_loop,
                daemon=True,
                name="MicReader"
            )
            self._mic_reader_thread.start()

            logger.info(f"Mic capture started: {self._mic_channels}ch @ {self._mic_sample_rate}Hz")
        except Exception as e:
            logger.warning(f"Failed to start mic capture: {e}")
            import traceback
            logger.warning(traceback.format_exc())
            self._mic_stream = None

    def _mic_reader_loop(self):
        """Dedicated thread for reading microphone audio."""
        logger.info("Mic reader thread started")
        read_count = 0

        try:
            while self._running:
                if self._mic_stream is None:
                    break

                try:
                    raw_data = self._mic_stream.read(
                        self.CHUNK_SIZE,
                        exception_on_overflow=False
                    )

                    if raw_data:
                        audio_data = np.frombuffer(raw_data, dtype=np.int16)

                        # Apply mic volume
                        if self.config.mic_volume != 1.0:
                            audio_data = (audio_data.astype(np.float32) * self.config.mic_volume).astype(np.int16)

                        read_count += 1
                        if read_count == 1:
                            max_amp = np.max(np.abs(audio_data)) if len(audio_data) > 0 else 0
                            logger.info(f"Mic first read: {len(audio_data)} samples, max_amp={max_amp}")
                            print(f"[AUDIO] First mic read: {len(audio_data)} samples, max_amp={max_amp}")

                        with self._lock:
                            self._mic_buffer.append(audio_data.copy())

                except IOError as e:
                    if self._running:
                        logger.debug(f"Mic IOError: {e}")
                    time.sleep(0.01)
                except Exception as e:
                    if self._running:
                        logger.warning(f"Mic read error: {e}")
                    break

        except Exception as e:
            logger.error(f"Mic reader loop error: {e}")

        logger.info(f"Mic reader thread stopped after {read_count} reads")

    def _capture_loop(self):
        """Main capture loop for processing audio data from callbacks."""
        chunk_count = 0
        logger.info("Audio capture loop started")

        with self._lock:
            loopback_available = self._loopback_stream is not None
            mic_available = self._mic_stream is not None
        logger.info(f"Audio streams: loopback={loopback_available}, mic={mic_available}")

        while True:
            # Check running state under lock
            with self._lock:
                if not self._running:
                    break
                start_time = self._start_time

            try:
                timestamp = time.perf_counter() - start_time

                loopback_data = None
                mic_data = None

                # Get loopback data from buffer
                with self._lock:
                    if hasattr(self, '_loopback_buffer') and self._loopback_buffer:
                        loopback_data = np.concatenate(self._loopback_buffer)
                        self._loopback_buffer.clear()

                # Get mic data from buffer
                with self._lock:
                    if hasattr(self, '_mic_buffer') and self._mic_buffer:
                        mic_data = np.concatenate(self._mic_buffer)
                        self._mic_buffer.clear()

                if loopback_data is not None and len(loopback_data) > 0:
                    if chunk_count == 0:
                        logger.info(
                            f"First loopback chunk: {len(loopback_data)} samples, "
                            f"max_amplitude={np.max(np.abs(loopback_data))}"
                        )

                if mic_data is not None and len(mic_data) > 0:
                    if not hasattr(self, '_mic_logged'):
                        self._mic_logged = True
                        logger.info(
                            f"First mic chunk: {len(mic_data)} samples, "
                            f"max_amplitude={np.max(np.abs(mic_data))}"
                        )

                # Mix loopback and mic if both available
                mixed_audio = self._mix_audio(loopback_data, mic_data)

                if mixed_audio is not None and len(mixed_audio) > 0:
                    self.audio_callback(mixed_audio, timestamp)
                    chunk_count += 1
                    if chunk_count == 1:
                        logger.info(f"First audio chunk sent to callback: {len(mixed_audio)} samples")
                    elif chunk_count % 1000 == 0:
                        logger.info(f"Audio chunks sent: {chunk_count}")
                else:
                    # No data available, sleep briefly to avoid busy-waiting
                    time.sleep(0.01)

            except Exception as e:
                logger.error(f"Audio capture error: {e}")
                import traceback
                logger.error(traceback.format_exc())
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

        # Wait for reader threads
        if self._loopback_reader_thread is not None:
            self._loopback_reader_thread.join(timeout=2.0)
            self._loopback_reader_thread = None

        if self._mic_reader_thread is not None:
            self._mic_reader_thread.join(timeout=2.0)
            self._mic_reader_thread = None

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
