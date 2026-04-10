"""Compatibility wrapper for the reusable KEF client package."""

from .kef_client import (
    BaseKefClient,
    LegacyBinaryClient,
    ModernKefClient,
    async_create_client,
)

__all__ = [
    "BaseKefClient",
    "LegacyBinaryClient",
    "ModernKefClient",
    "async_create_client",
]
