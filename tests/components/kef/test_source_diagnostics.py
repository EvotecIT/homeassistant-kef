"""Source transitions must remain diagnosable even while cached state is usable."""

import json
import time
from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.update_coordinator import UpdateFailed
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockConfigEntry,
    async_fire_time_changed,
)

from custom_components.kef import async_remove_entry
from custom_components.kef.coordinator import KefCoordinator
from custom_components.kef.diagnostic_events import DiagnosticEvents, describe_error
from custom_components.kef.diagnostics import async_get_config_entry_diagnostics
from custom_components.kef.exceptions import KefConnectionError
from custom_components.kef.media_player import KefMediaPlayer
from tests.conftest import TEST_SNAPSHOT


async def test_source_ack_then_failed_refresh_and_wifi_recovery(hass):
    """A tolerated poll failure is recorded independently of HA cached health."""
    entry = MockConfigEntry(domain="kef", data={"host": "192.0.2.42"})
    coordinator = KefCoordinator(hass, entry)
    entry.runtime_data = coordinator
    coordinator.data = replace(TEST_SNAPSHOT, source="Wifi")
    coordinator.last_update_success = True
    error = KefConnectionError(
        "private password and IP", backend="legacy", port=50001, operation="connect"
    )
    error.command = "read_source"
    coordinator.client = SimpleNamespace(
        async_select_source=AsyncMock(),
        async_refresh=AsyncMock(side_effect=[error, coordinator.data]),
    )
    coordinator.async_request_refresh = AsyncMock(
        side_effect=coordinator._async_update_data,
    )
    player = KefMediaPlayer(coordinator)
    await player.async_select_source("Opt")
    report = await async_get_config_entry_diagnostics(hass, entry)
    assert report["health"]["last_update_success"] is True
    assert report["health"]["last_refresh_success"] is False
    assert report["health"]["refresh_failures"] == 1
    events = report["recent_events"]
    assert [event["operation"] for event in events] == [
        "source_change_requested",
        "source_write_acknowledged",
        "source_refresh_failed",
        "refresh",
    ]
    assert events[0]["context"] == {
        "previous_source": "Wifi",
        "requested_source": "Opt",
        "transition": 1,
    }
    assert events[2]["errors"][0]["command"] == "read_source"
    assert events[2]["context"]["transition"] == 1
    await coordinator._async_update_data()
    recovered = await async_get_config_entry_diagnostics(hass, entry)
    assert recovered["health"]["last_success"]
    assert recovered["health"]["last_refresh_success"] is True
    assert recovered["recent_events"][-1]["operation"] == "connection_recovered"
    assert "private password" not in json.dumps(recovered)
    assert "192.0.2.42" not in json.dumps(recovered)


async def test_failed_source_write_does_not_claim_acknowledgement(hass):
    entry = MockConfigEntry(domain="kef", data={})
    coordinator = KefCoordinator(hass, entry)
    coordinator.data = TEST_SNAPSHOT
    coordinator.client = SimpleNamespace(
        async_select_source=AsyncMock(side_effect=KefConnectionError("private")),
    )
    with pytest.raises(HomeAssistantError):
        await KefMediaPlayer(coordinator).async_select_source("Opt")
    operations = [e["operation"] for e in coordinator.diagnostic_events.as_list()]
    assert operations == ["source_change_requested", "command", "source_change_failed"]


async def test_debounced_source_writes_record_superseded_transition(hass):
    """Two supported actions during HA's cooldown cannot lose their outcome."""
    entry = MockConfigEntry(domain="kef", data={})
    coordinator = KefCoordinator(hass, entry)
    coordinator.data = replace(TEST_SNAPSHOT, source="Wifi")
    coordinator.client = SimpleNamespace(
        async_select_source=AsyncMock(),
        async_refresh=AsyncMock(return_value=coordinator.data),
    )
    # Start the real coordinator debouncer's default ten-second cooldown.
    await coordinator.async_request_refresh()
    player = KefMediaPlayer(coordinator)
    await player.async_select_source("Opt")
    await player.async_select_source("Aux")
    assert coordinator.client.async_refresh.await_count == 1
    events = coordinator.diagnostic_events.as_list()
    superseded = [e for e in events if e["operation"] == "source_refresh_superseded"]
    assert [e["context"]["transition"] for e in superseded] == [1]
    coordinator.client.async_refresh.return_value = replace(TEST_SNAPSHOT, source="Aux")
    future = dt_util.utcnow() + timedelta(seconds=11)
    with patch("time.monotonic", return_value=time.monotonic() + 11):
        async_fire_time_changed(hass, future)
        await hass.async_block_till_done()
    outcomes = [
        e
        for e in coordinator.diagnostic_events.as_list()
        if e["operation"] == "source_refresh_succeeded"
    ]
    assert [e["context"]["transition"] for e in outcomes] == [2]
    assert outcomes[0]["context"]["observed_source"] == "Aux"
    await coordinator.async_shutdown()


async def test_reload_recovery_to_same_source_remains_in_history(hass):
    entry = MockConfigEntry(domain="kef", data={})
    first = KefCoordinator(hass, entry)
    first.data = replace(TEST_SNAPSHOT, source="Wifi")
    first.client = SimpleNamespace(async_refresh=AsyncMock(return_value=first.data))
    await first._async_update_data()
    first.client.async_refresh.side_effect = KefConnectionError("offline")
    await first._async_update_data()
    second = KefCoordinator(hass, entry)
    second.client = SimpleNamespace(async_refresh=AsyncMock(return_value=first.data))
    await second._async_update_data()
    recovered = second.diagnostic_events.as_list()[-1]
    assert recovered["operation"] == "connection_recovered"
    assert recovered["context"]["observed_source"] == "Wifi"


async def test_initialization_retries_keep_history_until_entry_removal(hass):
    entry = MockConfigEntry(domain="kef", data={})
    other = MockConfigEntry(domain="kef", data={})
    first = KefCoordinator(hass, entry)
    first.client = SimpleNamespace(
        async_refresh=AsyncMock(
            side_effect=KefConnectionError("secret"),
        )
    )
    with pytest.raises(UpdateFailed):
        await first._async_update_data()
    second = KefCoordinator(hass, entry)
    second.client = first.client
    entry.runtime_data = second
    with pytest.raises(UpdateFailed):
        await second._async_update_data()
    report = await async_get_config_entry_diagnostics(hass, entry)
    assert report["health"]["setup_attempts"] == 2
    assert report["health"]["refresh_failures"] == 2
    assert report["recent_events"][0]["count"] == 2
    assert report["integration_version"]
    assert report["home_assistant_version"]
    assert report["python_version"]
    assert KefCoordinator(hass, other).diagnostic_events.as_list() == []
    await async_remove_entry(hass, entry)
    assert KefCoordinator(hass, entry).diagnostic_events.as_list() == []


async def test_entry_history_download_works_while_setup_retries(hass, hass_client):
    """The entry-menu HTTP download includes earlier failed setup attempts."""
    assert await async_setup_component(hass, "http", {})
    assert await async_setup_component(hass, "diagnostics", {})
    assert await async_setup_component(hass, "kef", {})
    await hass.async_block_till_done()
    entry = MockConfigEntry(domain="kef", data={"host": "192.0.2.42"})
    entry.add_to_hass(hass)
    for _ in range(2):
        coordinator = KefCoordinator(hass, entry)
        entry.runtime_data = coordinator
        coordinator.client = SimpleNamespace(
            async_refresh=AsyncMock(
                side_effect=KefConnectionError("private"),
            )
        )
        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
    client = await hass_client()
    download = await client.get(f"/api/diagnostics/config_entry/{entry.entry_id}")
    assert download.status == 200
    report = (await download.json())["data"]
    assert report["health"]["setup_attempts"] == 2
    assert report["health"]["refresh_failures"] == 2
    assert report["recent_events"][0]["count"] == 2
    assert "192.0.2.42" not in json.dumps(report)


def test_pre_write_poll_is_not_attributed_to_acknowledged_source_change():
    events = DiagnosticEvents()
    in_flight = time.monotonic()
    transition = events.begin_source_change("Wifi", "Opt")
    events.source_acknowledged(transition)
    events.refresh_result(in_flight, source="Wifi")
    assert not any(
        e["operation"] == "source_refresh_succeeded" for e in events.as_list()
    )
    events.refresh_result(time.monotonic(), source="Opt")
    assert events.as_list()[-1]["operation"] == "source_refresh_succeeded"
    assert events.as_list()[-1]["context"]["observed_source"] == "Opt"


def test_source_history_and_protocol_details_reject_private_values():
    events = DiagnosticEvents()
    events.begin_source_change("secret source", "http://private/?password=secret")
    error = KefConnectionError("private", backend="legacy", port=50001)
    error.command = "http://private"
    error.elapsed_seconds = float("nan")
    error.connection_attempts = 1000
    events.record("refresh", error)
    assert describe_error(error) == [
        {"type": "KefConnectionError", "backend": "legacy", "port": 50001}
    ]
    assert "private" not in json.dumps(events.as_list())
    assert "secret" not in json.dumps(events.as_list())
    for i in range(40):
        events.begin_source_change("Wifi", "Opt" if i % 2 else "Aux")
    assert len(events.as_list()) == 32
    detached = events.as_list()
    detached[-1]["context"]["requested_source"] = "private"
    assert events.as_list()[-1]["context"]["requested_source"] == "Opt"
