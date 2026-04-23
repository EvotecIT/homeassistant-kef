"""Compatibility wrapper for reusable KEF models."""

from .kef_client import (
    KefBackend,
    KefDeviceInfo,
    KefEqProfile,
    KefFirmwareUpdateInfo,
    KefPlaybackInfo,
    KefSnapshot,
    KefWifiInfo,
)

__all__ = [
    "KefBackend",
    "KefDeviceInfo",
    "KefEqProfile",
    "KefFirmwareUpdateInfo",
    "KefPlaybackInfo",
    "KefSnapshot",
    "KefWifiInfo",
]
