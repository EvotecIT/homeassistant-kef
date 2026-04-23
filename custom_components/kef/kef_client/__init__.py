"""Reusable KEF local control client package."""

from .client import (
    BaseKefClient,
    LegacyBinaryClient,
    ModernKefClient,
    async_create_client,
)
from .exceptions import (
    KefAuthenticationRequiredError,
    KefConnectionError,
    KefError,
    KefResponseError,
    KefUnsupportedDeviceError,
)
from .models import (
    KefBackend,
    KefDeviceInfo,
    KefEqProfile,
    KefFirmwareUpdateInfo,
    KefPlaybackInfo,
    KefSnapshot,
    KefWifiInfo,
)

__all__ = [
    "BaseKefClient",
    "KefBackend",
    "KefAuthenticationRequiredError",
    "KefConnectionError",
    "KefDeviceInfo",
    "KefEqProfile",
    "KefError",
    "KefFirmwareUpdateInfo",
    "KefPlaybackInfo",
    "KefResponseError",
    "KefSnapshot",
    "KefUnsupportedDeviceError",
    "KefWifiInfo",
    "LegacyBinaryClient",
    "ModernKefClient",
    "async_create_client",
]
