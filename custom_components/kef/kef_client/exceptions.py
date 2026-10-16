"""Exceptions for the KEF integration."""

from __future__ import annotations

from typing import Literal


class KefError(Exception):
    """Base KEF integration error."""

    def __init__(
        self,
        message: str = "",
        *,
        backend: Literal["modern", "legacy"] | None = None,
        port: int | None = None,
        operation: Literal["identify", "connect", "request"] | None = None,
        probe_errors: tuple[KefError, ...] = (),
    ) -> None:
        """Keep optional safe connection context separate from private messages."""
        super().__init__(message)
        self.backend = backend
        self.port = port
        self.operation = operation
        self.probe_errors = probe_errors
        self.command: str | None = None
        self.phase: str | None = None
        self.connection_attempts: int | None = None
        self.elapsed_seconds: float | None = None


class KefConnectionError(KefError):
    """Raised when the speaker cannot be reached."""


class KefResponseError(KefError):
    """Raised when the speaker returns unexpected data."""


class KefCommandRejectedError(KefResponseError):
    """Raised when the legacy speaker returns a terminal command rejection."""


class KefAuthenticationRequiredError(KefResponseError):
    """Raised when the speaker API requires authentication."""


class KefUnsupportedDeviceError(KefError):
    """Raised when the detected device is not supported."""
