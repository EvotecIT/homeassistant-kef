"""Downloads must help failed setup without exposing private connection data."""

import json
from html.parser import HTMLParser
from unittest.mock import AsyncMock, patch

from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.plugins import aiohttp_client  # noqa: F401

from custom_components.kef.diagnostic_events import DiagnosticEvents
from custom_components.kef.exceptions import KefConnectionError
from custom_components.kef.setup_diagnostics import async_create_setup_report


class _Links(HTMLParser):
    def __init__(self):
        super().__init__()
        self.anchors = []

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.anchors.append(dict(attrs))


async def test_failed_setup_download(hass, hass_client, hass_client_no_auth) -> None:
    """An admin can download the failed form's report without adding an entry."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, "config", {})
    client = await hass_client()
    error = KefConnectionError("secret-password at http://192.0.2.42/?token=private")
    error.__cause__ = ConnectionRefusedError(111, "192.0.2.42")
    with patch(
        "custom_components.kef.config_flow.async_create_client",
        AsyncMock(side_effect=error),
    ):
        response = await client.post(
            "/api/config/config_entries/flow",
            json={"handler": "kef", "show_advanced_options": False},
        )
        initial = await response.json()
        assert response.status == 200
        assert initial["description_placeholders"]["diagnostics"] == ""
        response = await client.post(
            f"/api/config/config_entries/flow/{initial['flow_id']}",
            json={"host": "192.0.2.42", "password": "secret-password"},
        )
    form = await response.json()
    assert form["errors"] == {"base": "cannot_connect"}
    description = form["description_placeholders"]["diagnostics"]
    links = _Links()
    links.feed(description)
    assert len(links.anchors) == 1
    # HA routes same-window links as frontend pages instead of HTTP downloads.
    assert links.anchors[0]["target"] == "_blank"
    link = links.anchors[0]["href"]
    # A normal browser download has no bearer header; the signed URL must work.
    browser = await hass_client_no_auth()
    download = await browser.get(link)
    assert download.status == 200
    assert "attachment" in download.headers["Content-Disposition"]
    assert download.headers["Cache-Control"] == "no-store"
    report = await download.json()
    assert report["integration_version"]
    assert report["setup"]["failures"] == [[
        {"type": "KefConnectionError"},
        {"type": "ConnectionRefusedError", "errno": 111},
    ]]
    assert not hass.config_entries.async_entries("kef")
    serialized = json.dumps(report)
    for private in ("192.0.2.42", "secret-password", "token=private"):
        assert private not in serialized
    unsigned = await browser.get(link.split("?", 1)[0])
    assert unsigned.status == 401
    with patch(
        "custom_components.kef.setup_diagnostics.time.monotonic", return_value=1e20,
    ):
        expired = await client.get(link.split("?", 1)[0])
    assert expired.status == 404


async def test_setup_report_requires_admin_and_bounds_memory(
    hass, hass_client, hass_admin_user
) -> None:
    """Non-admin users cannot download reports and old reports are evicted."""
    assert await async_setup_component(hass, "http", {})
    client = await hass_client()
    links = [
        await async_create_setup_report(
            hass, source="user", errors=[KefConnectionError("private")], elapsed=1,
        )
        for _ in range(21)
    ]
    first_path = links[0].split("?", 1)[0]
    last_path = links[-1].split("?", 1)[0]
    assert (await client.get(first_path)).status == 404
    assert (await client.get(last_path)).status == 200
    hass_admin_user.is_owner = False
    hass_admin_user.groups = []
    assert (await client.get(last_path)).status == 401


def test_recent_events_are_safe_bounded_and_coalesced() -> None:
    """Offline retries retain useful counts instead of unbounded raw messages."""
    events = DiagnosticEvents()
    for _ in range(100):
        events.record("refresh", KefConnectionError("192.0.2.42 secret"))
    assert len(events.as_list()) == 1
    assert events.as_list()[0]["count"] == 100
    events.record("connection_recovered")
    assert events.as_list()[-1]["errors"] == []
    for _ in range(40):
        events.record("refresh", KefConnectionError("private"))
        events.record("connection_recovered")
    assert len(events.as_list()) == 32
    assert "private" not in json.dumps(events.as_list())

