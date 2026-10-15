"""Small, private-data-free history for downloadable KEF diagnostics."""

from __future__ import annotations

import logging
import math
import time
from collections import deque
from copy import deepcopy
from typing import Any

from homeassistant.core import HomeAssistant
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .exceptions import KefError
from .kef_client.const import DEFAULT_MODERN_SOURCE_LIST, LEGACY_SOURCE_LIST

_HISTORIES: HassKey[dict[str, DiagnosticEvents]] = HassKey("kef_entry_history")
_SOURCES = {*DEFAULT_MODERN_SOURCE_LIST, *LEGACY_SOURCE_LIST}
_LOGGER = logging.getLogger(__name__)


def entry_history(hass: HomeAssistant, entry_id: str) -> DiagnosticEvents:
    """Retain in-memory history across retries and reloads until entry removal."""
    return hass.data.setdefault(_HISTORIES, {}).setdefault(entry_id, DiagnosticEvents())


def remove_entry_history(hass: HomeAssistant, entry_id: str) -> None:
    """Release history when its entry is removed."""
    hass.data.get(_HISTORIES, {}).pop(entry_id, None)


def _safe_source(source: str | None) -> str | None:
    """Exclude arbitrary device or action strings from shareable reports."""
    return source if source in _SOURCES else None


def describe_error(
    error: BaseException,
    *,
    _seen: set[int] | None = None,
) -> list[dict[str, Any]]:
    """Describe exception types and OS error numbers, never messages or URLs."""
    chain: list[dict[str, Any]] = []
    seen = _seen if _seen is not None else set()
    current: BaseException | None = error
    while current is not None and id(current) not in seen and len(chain) < 6:
        seen.add(id(current))
        item: dict[str, Any] = {"type": type(current).__name__}
        if isinstance(current, OSError) and isinstance(current.errno, int):
            item["errno"] = current.errno
        if isinstance(current, KefError):
            if current.backend in {"modern", "legacy"}:
                item["backend"] = current.backend
            if isinstance(current.port, int) and 0 < current.port <= 65535:
                item["port"] = current.port
            if current.operation in {"identify", "connect", "request"}:
                item["operation"] = current.operation
            if current.command in {
                "read_source",
                "write_source",
                "read_volume",
                "write_volume",
                "read_playback",
                "write_playback",
                "other",
            }:
                item["command"] = current.command
            if current.phase in {
                "connecting",
                "reading_response",
                "waiting_for_acknowledgement",
            }:
                item["phase"] = current.phase
            if (
                isinstance(current.connection_attempts, int)
                and 0 <= current.connection_attempts <= 4
            ):
                item["connection_attempts"] = current.connection_attempts
            elapsed = current.elapsed_seconds
            if (
                isinstance(elapsed, (int, float))
                and math.isfinite(elapsed)
                and elapsed >= 0
            ):
                item["elapsed_seconds"] = round(elapsed, 3)
            if current.probe_errors:
                item["probes"] = [
                    describe_error(probe, _seen=seen.copy())
                    for probe in current.probe_errors[:2]
                    if id(probe) not in seen
                ]
        chain.append(item)
        current = current.__cause__ or current.__context__
    return chain


class DiagnosticEvents:
    """Keep recent failures and recovery in memory without capturing raw logs."""

    def __init__(self) -> None:
        self._events: deque[dict[str, Any]] = deque(maxlen=32)
        self.setup_attempts = 0
        self.last_setup_attempt: str | None = None
        self.refresh_failures = 0
        self.refresh_successes = 0
        self.last_success: str | None = None
        self.last_refresh_success: bool | None = None
        self.last_refresh_at: str | None = None
        self._last_source: str | None = None
        self._transition = 0
        self._pending: tuple[int, float] | None = None

    def setup_started(self) -> None:
        """Count coordinator attempts without splitting repeated failure events."""
        self.setup_attempts += 1
        self.last_setup_attempt = dt_util.utcnow().isoformat()

    def record(
        self,
        operation: str,
        error: BaseException | None = None,
        *,
        previous_source: str | None = None,
        requested_source: str | None = None,
        observed_source: str | None = None,
        transition: int | None = None,
    ) -> None:
        """Coalesce consecutive occurrences of the same safe event."""
        details = describe_error(error) if error is not None else []
        now = dt_util.utcnow().isoformat()
        context: dict[str, Any] = {}
        for key, value in (
            ("previous_source", previous_source),
            ("requested_source", requested_source),
            ("observed_source", observed_source),
        ):
            if (safe := _safe_source(value)) is not None:
                context[key] = safe
        if transition is not None:
            context["transition"] = transition
        _LOGGER.debug(
            "KEF diagnostic event %s context=%s errors=%s", operation, context, details
        )
        if self._events:
            previous = self._events[-1]

            # Timing varies across identical failures; preserve the latest timing
            # while coalescing the same failure and source context.
            def signature(errors: list[dict[str, Any]]) -> list[dict[str, Any]]:
                """Compare failure identity independently of variable timings."""
                result = []
                for item in errors:
                    stable = {k: v for k, v in item.items() if k != "elapsed_seconds"}
                    if "probes" in stable:
                        stable["probes"] = [
                            signature(probe) for probe in stable["probes"]
                        ]
                    result.append(stable)
                return result

            if (
                previous["operation"] == operation
                and previous.get("context", {}) == context
                and signature(previous["errors"]) == signature(details)
            ):
                previous["count"] += 1
                previous["last_seen"] = now
                previous["errors"] = details
                return
        self._events.append(
            {
                "operation": operation,
                "errors": details,
                "count": 1,
                "first_seen": now,
                "last_seen": now,
                **({"context": context} if context else {}),
            }
        )

    def begin_source_change(self, previous: str | None, requested: str) -> int:
        """Record intent separately from acknowledgement and observation."""
        self._transition += 1
        self.record(
            "source_change_requested",
            previous_source=previous,
            requested_source=requested,
            transition=self._transition,
        )
        return self._transition

    def source_acknowledged(self, transition: int) -> None:
        """Observe the next poll that starts after this acknowledged write."""
        if self._pending is not None:
            self.record("source_refresh_superseded", transition=self._pending[0])
        self.record("source_write_acknowledged", transition=transition)
        self._pending = (transition, time.monotonic())

    def refresh_started(self, started: float) -> int | None:
        """Bind an eligible acknowledgement to this poll before network awaits."""
        if self._pending is None or started < self._pending[1]:
            return None
        transition, _ = self._pending
        self._pending = None
        return transition

    def refresh_result(
        self,
        transition: int | None,
        *,
        source: str | None = None,
        error: BaseException | None = None,
    ) -> None:
        """Record actual device I/O, including failures hidden by cached state."""
        recovered = error is None and self.last_refresh_success is False
        self.last_refresh_success = error is None
        self.last_refresh_at = dt_util.utcnow().isoformat()
        if error is None:
            self.refresh_successes += 1
            self.last_success = dt_util.utcnow().isoformat()
            safe = _safe_source(source)
            if safe != self._last_source:
                self.record("source_observed", observed_source=safe)
                self._last_source = safe
        else:
            self.refresh_failures += 1
        if transition is not None:
            self.record(
                "source_refresh_failed" if error else "source_refresh_succeeded",
                error,
                observed_source=source,
                transition=transition,
            )
        if recovered:
            self.record("connection_recovered", observed_source=source)

    def summary(self) -> dict[str, Any]:
        """Return lifetime counters for this entry's current HA session."""
        return {
            "setup_attempts": self.setup_attempts,
            "last_setup_attempt": self.last_setup_attempt,
            "refresh_failures": self.refresh_failures,
            "refresh_successes": self.refresh_successes,
            "last_success": self.last_success,
            "last_refresh_success": self.last_refresh_success,
            "last_refresh_at": self.last_refresh_at,
        }

    def as_list(self) -> list[dict[str, Any]]:
        """Return a detached report so callers cannot change the stored history."""
        return deepcopy(list(self._events))
