"""Small, private-data-free history for downloadable KEF diagnostics."""

from __future__ import annotations

from collections import deque
from typing import Any

from homeassistant.util import dt as dt_util

from .exceptions import KefError


def describe_error(
    error: BaseException, *, _seen: set[int] | None = None,
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

    def record(self, operation: str, error: BaseException | None = None) -> None:
        """Coalesce consecutive occurrences of the same safe event."""
        details = describe_error(error) if error is not None else []
        now = dt_util.utcnow().isoformat()
        if self._events:
            previous = self._events[-1]
            if previous["operation"] == operation and previous["errors"] == details:
                previous["count"] += 1
                previous["last_seen"] = now
                return
        self._events.append({
            "operation": operation,
            "errors": details,
            "count": 1,
            "first_seen": now,
            "last_seen": now,
        })

    def as_list(self) -> list[dict[str, Any]]:
        """Return a detached report so callers cannot change the stored history."""
        return [
            {**event, "errors": [dict(item) for item in event["errors"]]}
            for event in self._events
        ]
