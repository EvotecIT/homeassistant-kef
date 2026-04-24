"""Compatibility wrapper for reusable KEF exceptions."""

from .kef_client import (
    KefAuthenticationRequiredError,
    KefConnectionError,
    KefError,
    KefResponseError,
    KefUnsupportedDeviceError,
)

__all__ = [
    "KefAuthenticationRequiredError",
    "KefConnectionError",
    "KefError",
    "KefResponseError",
    "KefUnsupportedDeviceError",
]
