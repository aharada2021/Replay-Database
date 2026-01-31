"""
Configuration for game capture functionality.
"""

import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional


@dataclass
class CaptureConfig:
    """Configuration for game capture settings."""

    enabled: bool = True
    output_folder: Path = field(
        default_factory=lambda: Path.home() / "Videos" / "WoWS Captures"
    )
    video_quality: str = "medium"  # low, medium, high
    target_fps: int = 30
    capture_scale: float = 0.5  # Scale factor for capture resolution (0.5 = half size)
    capture_audio: bool = True
    capture_microphone: bool = False
    mic_volume: float = 3.0  # Mic boost factor (1.0 = no boost, 3.0 = 3x amplification)
    max_duration_minutes: int = 30

    # Window detection settings
    window_title_pattern: str = "World of Warships"
    window_retry_interval: float = 5.0  # seconds

    # Encoder settings
    ffmpeg_path: Optional[str] = None  # Auto-detect if None

    def __post_init__(self):
        """Validate and expand configuration values."""
        if isinstance(self.output_folder, str):
            self.output_folder = Path(os.path.expandvars(self.output_folder))

        if self.video_quality not in ("low", "medium", "high"):
            self.video_quality = "medium"

        if self.target_fps < 15:
            self.target_fps = 15
        elif self.target_fps > 60:
            self.target_fps = 60

        # Validate capture scale (0.25 to 1.0)
        if self.capture_scale < 0.25:
            self.capture_scale = 0.25
        elif self.capture_scale > 1.0:
            self.capture_scale = 1.0

        # Mic volume can be boosted up to 10x to balance against desktop audio
        if self.mic_volume < 0.0:
            self.mic_volume = 0.0
        elif self.mic_volume > 10.0:
            self.mic_volume = 10.0

        if self.max_duration_minutes < 1:
            self.max_duration_minutes = 1
        elif self.max_duration_minutes > 120:
            self.max_duration_minutes = 120

    def ensure_output_folder(self) -> Path:
        """Ensure output folder exists and return the path."""
        self.output_folder.mkdir(parents=True, exist_ok=True)
        return self.output_folder

    def get_quality_preset(self) -> dict:
        """Get FFmpeg encoding preset based on quality setting."""
        presets = {
            "low": {
                "crf": 28,
                "preset": "ultrafast",
                "bitrate": "2M",
            },
            "medium": {
                "crf": 23,
                "preset": "medium",
                "bitrate": "5M",
            },
            "high": {
                "crf": 18,
                "preset": "slow",
                "bitrate": "10M",
            },
        }
        return presets.get(self.video_quality, presets["medium"])

    @classmethod
    def from_dict(cls, data: dict) -> "CaptureConfig":
        """Create CaptureConfig from dictionary."""
        capture_data = data.get("capture", {})

        output_folder = capture_data.get("output_folder")
        if output_folder:
            output_folder = Path(os.path.expandvars(output_folder))
        else:
            output_folder = Path.home() / "Videos" / "WoWS Captures"

        return cls(
            enabled=capture_data.get("enabled", True),
            output_folder=output_folder,
            video_quality=capture_data.get("video_quality", "medium"),
            target_fps=capture_data.get("target_fps", 30),
            capture_scale=capture_data.get("capture_scale", 0.5),
            capture_audio=capture_data.get("capture_audio", True),
            capture_microphone=capture_data.get("capture_microphone", False),
            mic_volume=capture_data.get("mic_volume", 3.0),
            max_duration_minutes=capture_data.get("max_duration_minutes", 30),
            window_title_pattern=capture_data.get(
                "window_title_pattern", "World of Warships"
            ),
            window_retry_interval=capture_data.get("window_retry_interval", 5.0),
            ffmpeg_path=capture_data.get("ffmpeg_path"),
        )

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "capture": {
                "enabled": self.enabled,
                "output_folder": str(self.output_folder),
                "video_quality": self.video_quality,
                "target_fps": self.target_fps,
                "capture_scale": self.capture_scale,
                "capture_audio": self.capture_audio,
                "capture_microphone": self.capture_microphone,
                "mic_volume": self.mic_volume,
                "max_duration_minutes": self.max_duration_minutes,
                "window_title_pattern": self.window_title_pattern,
                "window_retry_interval": self.window_retry_interval,
                "ffmpeg_path": self.ffmpeg_path,
            }
        }
