"""Config-entry changes must schedule one reload through Home Assistant."""

import asyncio
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant import config_entries
from homeassistant.components import websocket_api
from homeassistant.components.config.config_entries import config_entry_update
from homeassistant.config_entries import ConfigEntryState, DiscoveryKey
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.exceptions import ConfigEntryNotReady
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from homeassistant.helpers.translation import async_get_translations
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef import async_setup_entry
from custom_components.kef.const import (
    AIRPLAY_ZEROCONF_TYPE,
    CONF_BACKEND,
    CONF_DEVICE_ID,
    CONF_TCP_PORT,
    DOMAIN,
)
from tests.conftest import TEST_DEVICE_INFO, TEST_HOST, TEST_SNAPSHOT


async def _entry(hass, monkeypatch, state, *, host=TEST_HOST):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_DEVICE_INFO.unique_id,
        title=TEST_DEVICE_INFO.device_name,
        data={
            CONF_HOST: host,
            CONF_PORT: 80,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
            CONF_DEVICE_ID: TEST_DEVICE_INFO.unique_id,
            CONF_PASSWORD: "saved-password",
        },
        options={CONF_PASSWORD: "saved-password", "scan_interval": 45},
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, state)
    if state is ConfigEntryState.LOADED:
        coordinator = Mock(
            data=TEST_SNAPSHOT,
            async_config_entry_first_refresh=AsyncMock(),
            async_start_event_listener=AsyncMock(),
            async_stop_event_listener=AsyncMock(),
        )
        monkeypatch.setattr(
            "custom_components.kef.KefCoordinator", Mock(return_value=coordinator)
        )
        monkeypatch.setattr(
            hass.config_entries, "async_forward_entry_setups", AsyncMock()
        )
        assert await async_setup_entry(hass, entry)
    return entry


@pytest.mark.parametrize("source", ["reauth", "reconfigure"])
@pytest.mark.parametrize("changed", [True, False])
@pytest.mark.parametrize(
    "state", [ConfigEntryState.LOADED, ConfigEntryState.NOT_LOADED]
)
async def test_connection_repair_reloads_once(
    hass, monkeypatch, source, changed, state
):
    """Changed and unchanged repairs reload once, with or without a listener."""
    entry = await _entry(hass, monkeypatch, state)
    old_entry_id, old_unique_id = entry.entry_id, entry.unique_id
    password = "replacement-password" if changed else "saved-password"
    client = Mock(async_identify=AsyncMock(return_value=TEST_DEVICE_INFO))
    monkeypatch.setattr(
        "custom_components.kef.config_flow.async_create_client",
        AsyncMock(return_value=client),
    )
    reload = AsyncMock(return_value=True)
    monkeypatch.setattr(hass.config_entries, "async_reload", reload)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source, "entry_id": entry.entry_id},
        data=entry.data if source == config_entries.SOURCE_REAUTH else None,
    )
    user_input = {CONF_PASSWORD: password}
    if source == config_entries.SOURCE_RECONFIGURE:
        user_input[CONF_HOST] = TEST_HOST
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"], user_input
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == f"{source}_successful"
    reload.assert_awaited_once_with(entry.entry_id)
    assert (entry.entry_id, entry.unique_id) == (old_entry_id, old_unique_id)
    assert entry.data[CONF_PASSWORD] == password
    assert entry.options == {CONF_PASSWORD: password, "scan_interval": 45}


@pytest.mark.parametrize("changed", [True, False])
@pytest.mark.parametrize(
    "state", [ConfigEntryState.LOADED, ConfigEntryState.SETUP_RETRY]
)
async def test_rediscovery_reloads_once(hass, monkeypatch, changed, state):
    """Rediscovery updates a loaded speaker or wakes a retrying entry once."""
    host = "old-speaker.local" if changed else "lsxii.local"
    entry = await _entry(hass, monkeypatch, state, host=host)
    reload = AsyncMock(return_value=True)
    monkeypatch.setattr(hass.config_entries, "async_reload", reload)
    discovery = ZeroconfServiceInfo(
        ip_address="192.0.2.11",
        ip_addresses=["192.0.2.11"],
        hostname="lsxii.local.",
        type=AIRPLAY_ZEROCONF_TYPE,
        name="Living Room LSX II._airplay._tcp.local.",
        port=7000,
        properties={
            "manufacturer": "KEF",
            "model": "LSX II",
            "deviceid": "02:00:00:00:00:01",
        },
    )

    discovery_key = DiscoveryKey(
        domain="zeroconf", key=(discovery.type, discovery.name), version=1
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_ZEROCONF,
            "discovery_key": discovery_key,
        },
        data=discovery,
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "lsxii.local"
    assert discovery_key in entry.discovery_keys["zeroconf"]
    if changed or state is ConfigEntryState.SETUP_RETRY:
        reload.assert_awaited_once_with(entry.entry_id)
    else:
        reload.assert_not_awaited()


@pytest.mark.parametrize(
    "state",
    [
        ConfigEntryState.LOADED,
        ConfigEntryState.NOT_LOADED,
        ConfigEntryState.SETUP_RETRY,
    ],
)
async def test_manual_rediscovery_preserves_reload_policy(hass, monkeypatch, state):
    """A host change wakes active/retrying speakers and preserves dormant state."""
    entry = await _entry(
        hass, monkeypatch, state, host="old-speaker.local"
    )
    client = Mock(async_identify=AsyncMock(return_value=TEST_DEVICE_INFO))
    monkeypatch.setattr(
        "custom_components.kef.config_flow.async_create_client",
        AsyncMock(return_value=client),
    )
    reload = AsyncMock(return_value=True)
    monkeypatch.setattr(hass.config_entries, "async_reload", reload)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: TEST_HOST},
    )
    await hass.async_block_till_done()

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == TEST_HOST
    if state is ConfigEntryState.NOT_LOADED:
        reload.assert_not_awaited()
    else:
        reload.assert_awaited_once_with(entry.entry_id)


@pytest.mark.parametrize("field", ["data", "options", "title", "unique_id"])
async def test_registered_listener_preserves_setting_reload(hass, monkeypatch, field):
    """Settings and naming changes retain the registered listener's reload."""
    entry = await _entry(hass, monkeypatch, ConfigEntryState.LOADED)
    reload = AsyncMock(return_value=True)
    monkeypatch.setattr(hass.config_entries, "async_reload", reload)
    value = {
        "data": {**entry.data, CONF_HOST: "new-speaker.local"},
        "options": {**entry.options, "scan_interval": 60},
        "title": "Renamed speaker",
        "unique_id": "changed-speaker-id",
    }[field]

    hass.config_entries.async_update_entry(entry, **{field: value})
    await hass.async_block_till_done()

    reload.assert_awaited_once_with(entry.entry_id)


async def test_system_polling_options_reload_once(hass, hass_ws_client, monkeypatch):
    """The real HA system-options handler owns disabling and restoring polling."""
    entry = await _entry(hass, monkeypatch, ConfigEntryState.LOADED)
    reload = AsyncMock(return_value=True)
    monkeypatch.setattr(hass.config_entries, "async_reload", reload)
    websocket_api.async_register_command(hass, config_entry_update)
    client = await hass_ws_client(hass)
    for message_id, disabled in enumerate((True, False), start=1):
        await client.send_json(
            {
                "id": message_id,
                "type": "config_entries/update",
                "entry_id": entry.entry_id,
                "pref_disable_polling": disabled,
            }
        )
        result = await client.receive_json()
        await hass.async_block_till_done()
        assert result["success"]
        assert entry.pref_disable_polling is disabled
        assert reload.await_count == message_id
    await client.close()


async def test_connection_success_messages_are_translated(hass):
    """The runtime translation catalog resolves both successful repair reasons."""
    translations = await async_get_translations(hass, "en", "config", {DOMAIN})
    for reason in ("reauth_successful", "reconfigure_successful"):
        assert translations[f"component.{DOMAIN}.config.abort.{reason}"]


@pytest.mark.parametrize("first_refresh_fails", [False, True])
async def test_rediscovery_during_setup_uses_new_host(
    hass, monkeypatch, first_refresh_fails
):
    """A discovery update survives the active setup lock and failed first refresh."""
    entry = await _entry(
        hass, monkeypatch, ConfigEntryState.NOT_LOADED, host="old-speaker.local"
    )
    entered, release = asyncio.Event(), asyncio.Event()
    setup_hosts = []

    async def first_refresh():
        entered.set()
        await release.wait()
        if first_refresh_fails:
            raise ConfigEntryNotReady("Old speaker address is unavailable")

    def coordinator_factory(_hass, setup_entry):
        setup_hosts.append(setup_entry.data[CONF_HOST])
        return Mock(
            data=TEST_SNAPSHOT,
            async_config_entry_first_refresh=AsyncMock(
                side_effect=first_refresh if len(setup_hosts) == 1 else None
            ),
            async_start_event_listener=AsyncMock(),
            async_stop_event_listener=AsyncMock(),
        )

    monkeypatch.setattr("custom_components.kef.KefCoordinator", coordinator_factory)
    monkeypatch.setattr(hass.config_entries, "async_forward_entry_setups", AsyncMock())
    monkeypatch.setattr(
        hass.config_entries, "async_unload_platforms", AsyncMock(return_value=True)
    )
    reload = AsyncMock(wraps=hass.config_entries.async_reload)
    monkeypatch.setattr(hass.config_entries, "async_reload", reload)
    unload_states = []
    original_unload = hass.config_entries.async_unload

    async def unload(*args, **kwargs):
        unload_states.append(entry.state)
        return await original_unload(*args, **kwargs)

    monkeypatch.setattr(hass.config_entries, "async_unload", unload)
    task = hass.async_create_task(hass.config_entries.async_setup(entry.entry_id))
    await asyncio.wait_for(entered.wait(), timeout=10)
    discovery = ZeroconfServiceInfo(
        ip_address="192.0.2.11", ip_addresses=["192.0.2.11"],
        hostname="lsxii.local.", type=AIRPLAY_ZEROCONF_TYPE,
        name="Living Room LSX II._airplay._tcp.local.", port=7000,
        properties={"manufacturer": "KEF", "model": "LSX II",
                    "deviceid": "02:00:00:00:00:01"},
    )
    try:
        result = await hass.config_entries.flow.async_init(
            DOMAIN,
            context={
                "source": config_entries.SOURCE_ZEROCONF,
                "discovery_key": DiscoveryKey(
                    domain="zeroconf", key=(discovery.type, discovery.name), version=1
                ),
            },
            data=discovery,
        )
        assert result["reason"] == "already_configured"
        assert entry.state is ConfigEntryState.SETUP_IN_PROGRESS
    finally:
        release.set()
    await task
    await hass.async_block_till_done()
    assert entry.state is ConfigEntryState.LOADED
    assert setup_hosts == ["old-speaker.local", "lsxii.local"]
    assert unload_states == [
        ConfigEntryState.SETUP_RETRY if first_refresh_fails else ConfigEntryState.LOADED
    ]
    reload.assert_awaited_once_with(entry.entry_id)
    assert len(entry.update_listeners) == 1
