"""Concurrent HA actions respect the speaker platform's request budget."""

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

from homeassistant.const import CONF_HOST
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef.const import CONF_BACKEND, DOMAIN
from custom_components.kef.coordinator import KefCoordinator
from tests.conftest import TEST_HOST, TEST_SNAPSHOT


async def test_multi_entity_switch_action_is_serialized_by_home_assistant(hass):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=TEST_SNAPSHOT.device.device_name,
        unique_id=TEST_SNAPSHOT.device.unique_id,
        data={CONF_HOST: TEST_HOST, CONF_BACKEND: TEST_SNAPSHOT.device.backend},
    )
    entry.add_to_hass(hass)

    async def refresh(coordinator):
        coordinator.async_set_updated_data(TEST_SNAPSHOT)

    with patch.object(KefCoordinator, "async_config_entry_first_refresh", refresh):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    active = 0
    maximum = 0
    completed = []

    async def write(value):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        await asyncio.sleep(0)
        completed.append(value)
        active -= 1

    entry.runtime_data.client = SimpleNamespace(
        async_set_startup_tone_enabled=write,
        async_set_auto_switch_hdmi_enabled=write,
    )
    entry.runtime_data.async_request_refresh = AsyncMock()
    registry = er.async_get(hass)
    targets = [
        registry.async_get_entity_id(
            "switch", DOMAIN, f"{TEST_SNAPSHOT.device.unique_id}_{key}"
        )
        for key in ("startup_tone", "auto_switch_hdmi")
    ]
    assert all(targets)
    try:
        await hass.services.async_call(
            "switch", "turn_on", {"entity_id": targets}, blocking=True
        )
        assert completed == [True, True]
        assert maximum == 1
    finally:
        assert await hass.config_entries.async_unload(entry.entry_id)
