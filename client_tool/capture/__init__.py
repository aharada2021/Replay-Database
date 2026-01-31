"""
Game Capture Module for WoWS Replay Uploader

Provides screen and audio capture functionality for recording
World of Warships gameplay.
"""

from .config import CaptureConfig
from .manager import GameCaptureManager
from .exceptions import (
    CaptureError,
    WindowNotFoundError,
    AudioDeviceError,
    EncoderError,
    CaptureAlreadyRunningError,
    CaptureNotRunningError,
)

__all__ = [
    "CaptureConfig",
    "GameCaptureManager",
    "CaptureError",
    "WindowNotFoundError",
    "AudioDeviceError",
    "EncoderError",
    "CaptureAlreadyRunningError",
    "CaptureNotRunningError",
]
