"""Reusable KEF local control client package."""

from .client import (
    BaseKefClient,
    LegacyBinaryClient,
    ModernKefClient,
    async_create_client,
)
from .exceptions import (
    KefConnectionError,
    KefError,
    KefResponseError,
    KefUnsupportedDeviceError,
)
from .models import (
    KefBackend,
    KefDeviceInfo,
    KefEqProfile,
    KefPlaybackInfo,
    KefSnapshot,
    KefWifiInfo,
)

__all__ = [
    "BaseKefClient",
    "KefBackend",
    "KefConnectionError",
    "KefDeviceInfo",
    "KefEqProfile",
    "KefError",
    "KefPlaybackInfo",
    "KefResponseError",
    "KefSnapshot",
    "KefUnsupportedDeviceError",
    "KefWifiInfo",
    "LegacyBinaryClient",
    "ModernKefClient",
    "async_create_client",
]
