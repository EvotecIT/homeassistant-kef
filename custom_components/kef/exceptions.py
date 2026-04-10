"""Compatibility wrapper for reusable KEF exceptions."""

from .kef_client import (
    KefConnectionError,
    KefError,
    KefResponseError,
    KefUnsupportedDeviceError,
)

__all__ = [
    "KefConnectionError",
    "KefError",
    "KefResponseError",
    "KefUnsupportedDeviceError",
]
