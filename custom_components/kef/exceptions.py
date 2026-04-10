"""Exceptions for the KEF integration."""


class KefError(Exception):
    """Base KEF integration error."""


class KefConnectionError(KefError):
    """Raised when the speaker cannot be reached."""


class KefResponseError(KefError):
    """Raised when the speaker returns unexpected data."""


class KefUnsupportedDeviceError(KefError):
    """Raised when the detected device is not supported."""
