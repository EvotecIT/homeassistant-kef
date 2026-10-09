"""Config-entry changes must schedule one reload through Home Assistant."""

from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState, DiscoveryKey
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
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


async def test_manual_rediscovery_reloads_once(hass, monkeypatch):
    """Adding an already configured speaker at its new host updates it once."""
    entry = await _entry(
        hass, monkeypatch, ConfigEntryState.LOADED, host="old-speaker.local"
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
