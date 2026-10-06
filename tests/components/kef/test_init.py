"""KEF config-entry lifecycle contracts."""

import asyncio
from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef import PLATFORMS, async_unload_entry
from custom_components.kef.const import DOMAIN


@pytest.mark.parametrize("unload_succeeds", [True, False])
async def test_unload_preserves_listener_when_platforms_refuse(hass, unload_succeeds):
    """An entry that stays loaded must keep receiving speaker events."""
    entry = MockConfigEntry(domain=DOMAIN)
    entry.runtime_data = SimpleNamespace(async_stop_event_listener=AsyncMock())
    with patch.object(
        hass.config_entries,
        "async_unload_platforms",
        AsyncMock(return_value=unload_succeeds),
    ) as unload:
        assert await async_unload_entry(hass, entry) is unload_succeeds

    unload.assert_awaited_once_with(entry, PLATFORMS)
    if unload_succeeds:
        entry.runtime_data.async_stop_event_listener.assert_awaited_once_with()
    else:
        entry.runtime_data.async_stop_event_listener.assert_not_awaited()


async def test_reloads_replace_event_listener_and_preserve_entities(hass):
    from homeassistant.const import CONF_HOST
    from homeassistant.helpers import entity_registry as er

    from custom_components.kef.const import CONF_BACKEND
    from custom_components.kef.coordinator import KefCoordinator
    from custom_components.kef.models import KefBackend
    from tests.conftest import TEST_HOST, TEST_SNAPSHOT

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SNAPSHOT.device.unique_id,
        data={CONF_HOST: TEST_HOST, CONF_BACKEND: TEST_SNAPSHOT.device.backend},
    )
    entry.add_to_hass(hass)
    clients = []

    async def refresh(coordinator):
        started = asyncio.Event()

        async def poll(*, timeout):
            started.set()
            await asyncio.Event().wait()

        client = SimpleNamespace(
            backend=KefBackend.MODERN,
            async_poll_events=poll,
            async_reset_event_queue=AsyncMock(),
            started=started,
        )
        clients.append(client)
        coordinator.client = client
        coordinator.async_set_updated_data(deepcopy(TEST_SNAPSHOT))

    with patch.object(KefCoordinator, "async_config_entry_first_refresh", refresh):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await asyncio.wait_for(clients[-1].started.wait(), timeout=5)
        registry = er.async_get(hass)
        entity_ids = {
            entity.entity_id
            for entity in er.async_entries_for_config_entry(registry, entry.entry_id)
        }
        assert entity_ids
        for _ in range(2):
            previous = entry.runtime_data
            previous_task = previous._event_listener_task
            previous_client = clients[-1]
            assert await hass.config_entries.async_reload(entry.entry_id)
            await asyncio.wait_for(clients[-1].started.wait(), timeout=5)
            assert entry.runtime_data is not previous
            assert previous_task.cancelled()
            assert previous._event_listener_task is None
            previous_client.async_reset_event_queue.assert_awaited_once()
            assert {
                entity.entity_id
                for entity in er.async_entries_for_config_entry(
                    registry, entry.entry_id
                )
            } == entity_ids
        final_task = entry.runtime_data._event_listener_task
        assert await hass.config_entries.async_unload(entry.entry_id)
        assert final_task.cancelled()
        clients[-1].async_reset_event_queue.assert_awaited_once()


async def test_platform_setup_failure_recovers_without_starting_old_listener(hass):
    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.const import CONF_HOST

    from custom_components.kef.const import CONF_BACKEND
    from custom_components.kef.coordinator import KefCoordinator
    from tests.conftest import TEST_HOST, TEST_SNAPSHOT

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SNAPSHOT.device.unique_id,
        data={CONF_HOST: TEST_HOST, CONF_BACKEND: TEST_SNAPSHOT.device.backend},
    )
    entry.add_to_hass(hass)
    owners = []

    async def refresh(coordinator):
        owners.append(coordinator)
        coordinator.async_set_updated_data(deepcopy(TEST_SNAPSHOT))

    with (
        patch.object(KefCoordinator, "async_config_entry_first_refresh", refresh),
        patch.object(
            KefCoordinator, "async_start_event_listener", new_callable=AsyncMock
        ) as start,
    ):
        with patch.object(
            hass.config_entries,
            "async_forward_entry_setups",
            AsyncMock(side_effect=RuntimeError("platform setup failed")),
        ):
            assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_ERROR
        start.assert_not_awaited()
        assert owners[0]._event_listener_task is None
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data is owners[1]
        assert owners[1] is not owners[0]
        start.assert_awaited_once()
        assert await hass.config_entries.async_unload(entry.entry_id)


async def test_offline_startup_retries_without_entities_then_recovers(hass):
    from homeassistant.config_entries import ConfigEntryState
    from homeassistant.const import CONF_HOST
    from homeassistant.helpers import entity_registry as er

    from custom_components.kef.const import CONF_BACKEND
    from custom_components.kef.coordinator import KefCoordinator
    from custom_components.kef.exceptions import KefConnectionError
    from tests.conftest import TEST_HOST, TEST_SNAPSHOT

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_SNAPSHOT.device.unique_id,
        data={CONF_HOST: TEST_HOST, CONF_BACKEND: TEST_SNAPSHOT.device.backend},
    )
    entry.add_to_hass(hass)
    client = SimpleNamespace(
        async_refresh=AsyncMock(return_value=deepcopy(TEST_SNAPSHOT))
    )
    with (
        patch(
            "custom_components.kef.coordinator.async_create_client",
            AsyncMock(side_effect=KefConnectionError("speaker offline")),
        ) as connect,
        patch.object(
            KefCoordinator, "async_start_event_listener", new_callable=AsyncMock
        ) as start,
    ):
        assert not await hass.config_entries.async_setup(entry.entry_id)
        assert entry.state is ConfigEntryState.SETUP_RETRY
        assert not hasattr(entry, "runtime_data")
        assert not er.async_entries_for_config_entry(
            er.async_get(hass), entry.entry_id
        )
        start.assert_not_awaited()
        connect.side_effect = None
        connect.return_value = client
        assert await hass.config_entries.async_reload(entry.entry_id)
        await hass.async_block_till_done()
        assert entry.state is ConfigEntryState.LOADED
        assert entry.runtime_data.client is client
        assert entry.runtime_data.last_update_success
        assert er.async_entries_for_config_entry(er.async_get(hass), entry.entry_id)
        start.assert_awaited_once()
        assert await hass.config_entries.async_unload(entry.entry_id)
