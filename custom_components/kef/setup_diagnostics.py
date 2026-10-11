"""Temporary administrator downloads for setup failures without an entry."""

from __future__ import annotations

import platform
import time
from collections import OrderedDict
from datetime import timedelta
from typing import Any
from uuid import uuid4

from aiohttp import web
from homeassistant.components.http.auth import async_sign_path
from homeassistant.components.http.decorators import require_admin
from homeassistant.const import __version__ as HA_VERSION
from homeassistant.core import HomeAssistant
from homeassistant.helpers.http import HomeAssistantView
from homeassistant.loader import async_get_integration
from homeassistant.util import dt as dt_util
from homeassistant.util.hass_dict import HassKey

from .const import DOMAIN
from .diagnostic_events import describe_error

_LIFETIME = timedelta(minutes=15)
_MAX_REPORTS = 20
_DATA: HassKey[OrderedDict[str, tuple[float, dict[str, Any]]]] = HassKey(
    "kef_setup_diagnostics"
)


def _prune(reports: OrderedDict[str, tuple[float, dict[str, Any]]]) -> None:
    """Expire reports and bound memory even if setup repeatedly fails."""
    now = time.monotonic()
    for report_id, (expires, _) in list(reports.items()):
        if expires <= now:
            del reports[report_id]


async def async_create_setup_report(
    hass: HomeAssistant, *, source: str | None,
    errors: list[BaseException], elapsed: float
) -> str:
    """Store safe failure details and return a signed administrator download URL."""
    # Headless library/test callers may run flows without an HTTP frontend.
    if getattr(hass, "http", None) is None:
        return ""
    if _DATA not in hass.data:
        hass.data[_DATA] = OrderedDict()
        hass.http.register_view(KefSetupDiagnosticsView())
    reports = hass.data[_DATA]
    _prune(reports)
    while len(reports) >= _MAX_REPORTS:
        reports.popitem(last=False)
    integration = await async_get_integration(hass, DOMAIN)
    report = {
        "created_at": dt_util.utcnow().isoformat(),
        "home_assistant_version": HA_VERSION,
        "integration_version": integration.version,
        "python_version": platform.python_version(),
        "os": platform.system(),
        "architecture": platform.machine(),
        "setup": {
            "source": source,
            "elapsed_seconds": round(elapsed, 3),
            "failures": [describe_error(error) for error in errors],
        },
    }
    report_id = uuid4().hex
    reports[report_id] = (time.monotonic() + _LIFETIME.total_seconds(), report)
    return async_sign_path(
        hass, f"/api/kef/setup_diagnostics/{report_id}", _LIFETIME
    )


class KefSetupDiagnosticsView(HomeAssistantView):
    """Serve only already-redacted reports through Home Assistant authentication."""

    url = "/api/kef/setup_diagnostics/{report_id}"
    name = "api:kef:setup_diagnostics"
    requires_auth = True

    @require_admin
    async def get(self, request: web.Request, report_id: str) -> web.Response:
        """Download a recent setup attempt; expired links require another attempt."""
        hass: HomeAssistant = request.app["hass"]
        reports = hass.data[_DATA]
        _prune(reports)
        if report_id not in reports:
            raise web.HTTPNotFound()
        return self.json(
            reports[report_id][1],
            headers={
                "Content-Disposition": (
                    'attachment; filename="kef-setup-diagnostics.json"'
                ),
                "Cache-Control": "no-store",
            },
        )
