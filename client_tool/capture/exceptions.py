"""
Custom exceptions for the capture module.
"""


class CaptureError(Exception):
    """Base exception for capture-related errors."""

    pass


class WindowNotFoundError(CaptureError):
    """Raised when the target window cannot be found."""

    pass


class AudioDeviceError(CaptureError):
    """Raised when audio device initialization fails."""

    pass


class EncoderError(CaptureError):
    """Raised when video encoding fails."""

    pass


class CaptureAlreadyRunningError(CaptureError):
    """Raised when attempting to start capture while already running."""

    pass


class CaptureNotRunningError(CaptureError):
    """Raised when attempting to stop capture while not running."""

    pass
