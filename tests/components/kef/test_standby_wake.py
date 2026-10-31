"""Standby and second wake-up controls follow the speaker's constraints."""

from dataclasses import replace
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import CONF_HOST
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef.const import CONF_BACKEND, DOMAIN
from custom_components.kef.coordinator import KefCoordinator
from custom_components.kef.kef_client.const import MODERN_MODEL_SOURCE_MAP
from custom_components.kef.select import SELECTS, KefSelect
from tests.conftest import TEST_HOST, TEST_SNAPSHOT


@pytest.mark.parametrize("model", ["LSXII", "LSXIILT", "LS50WII", "LS60W", "XIO"])
async def test_wake_options_follow_model_inputs(hass, model):
    snapshot = replace(
        TEST_SNAPSHOT,
        device=replace(TEST_SNAPSHOT.device, model=model),
        source_list=MODERN_MODEL_SOURCE_MAP[model],
    )
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: TEST_HOST, CONF_BACKEND: "modern"},
    )
    coordinator = KefCoordinator(hass, entry)
    coordinator.async_set_updated_data(snapshot)
    entity = KefSelect(coordinator, next(d for d in SELECTS if d.key == "wake_source"))
    assert "Default" in entity.options
    assert "Wi-Fi" in entity.options
    assert ("USB" in entity.options) is (model in {"LSXII", "LSXIILT"})
    if model not in {"LSXII", "LSXIILT"}:
        with pytest.raises(HomeAssistantError) as error:
            await entity.async_select_option("USB")
        assert error.value.translation_key == "unsupported_wake_source"


@pytest.mark.parametrize(
    ("standby", "wake", "key", "option"),
    [
        ("standby_none", "usb", "standby_mode", "20 minutes"),
        ("standby_20mins", "wakeup_default", "wake_source", "USB"),
    ],
)
async def test_stale_select_action_rejects_eco_wake_conflict(
    hass, standby, wake, key, option,
):
    entry = MockConfigEntry(
        domain=DOMAIN, data={CONF_HOST: TEST_HOST, CONF_BACKEND: "modern"},
    )
    coordinator = KefCoordinator(hass, entry)
    coordinator.async_set_updated_data(replace(
        TEST_SNAPSHOT, standby_mode=standby, wake_source=wake,
    ))
    client = AsyncMock()
    coordinator.client = client
    entity = KefSelect(coordinator, next(d for d in SELECTS if d.key == key))
    assert option not in entity.options
    with pytest.raises(HomeAssistantError) as error:
        await entity.async_select_option(option)
    assert error.value.translation_key == "eco_wake_source"
    assert client.mock_calls == []
    assert coordinator.data.standby_mode == standby
    assert coordinator.data.wake_source == wake


async def test_configuration_actions_restore_compatible_choices(hass):
    """The standard HA actions can clear wake, enable ECO, then leave ECO."""
    snapshot = replace(TEST_SNAPSHOT, wake_source="usb")
    entry = MockConfigEntry(
        domain=DOMAIN, title=snapshot.device.device_name,
        unique_id=snapshot.device.unique_id,
        data={CONF_HOST: TEST_HOST, CONF_BACKEND: "modern"},
    )
    entry.add_to_hass(hass)

    async def refresh(coordinator):
        coordinator.async_set_updated_data(snapshot)

    with patch.object(KefCoordinator, "async_config_entry_first_refresh", refresh):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
    coordinator = entry.runtime_data
    client = AsyncMock()
    coordinator.client = client
    coordinator.async_request_refresh = AsyncMock()
    registry = er.async_get(hass)
    ids = {
        key: registry.async_get_entity_id(
            "select", DOMAIN, f"{snapshot.device.unique_id}_{key}",
        )
        for key in ("standby_mode", "wake_source")
    }

    async def select(key, option):
        await hass.services.async_call(
            "select", "select_option",
            {"entity_id": ids[key], "option": option}, blocking=True,
        )
        await hass.async_block_till_done()

    try:
        assert "20 minutes" not in (
            hass.states.get(ids["standby_mode"]).attributes["options"]
        )
        await select("wake_source", "Default")
        await select("standby_mode", "20 minutes")
        assert hass.states.get(ids["wake_source"]).attributes["options"] == ["Default"]
        await select("standby_mode", "Never")
        assert "USB" in hass.states.get(ids["wake_source"]).attributes["options"]
        await select("wake_source", "USB")
        assert hass.states.get(ids["standby_mode"]).state == "Never"
        assert hass.states.get(ids["wake_source"]).state == "USB"
        assert client.async_set_standby_mode.await_args_list[0].args == (
            "standby_20mins",
        )
        assert client.async_set_wake_source.await_args_list[0].args == (
            "wakeup_default",
        )
    finally:
        assert await hass.config_entries.async_unload(entry.entry_id)
