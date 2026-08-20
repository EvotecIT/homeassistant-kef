"""Coordinator tests for KEF."""

from __future__ import annotations

import asyncio
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant.exceptions import ConfigEntryAuthFailed
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef.const import (
    CONF_BACKEND,
    CONF_TCP_PORT,
    DOMAIN,
)
from custom_components.kef.coordinator import KefCoordinator
from custom_components.kef.exceptions import KefAuthenticationRequiredError, KefError
from custom_components.kef.models import KefBackend
from tests.conftest import TEST_HOST, TEST_PORT, TEST_SNAPSHOT


@pytest.mark.asyncio
async def test_event_listener_requests_refresh_on_events(hass) -> None:
    """Modern event-queue updates should trigger a coordinator refresh."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
        },
        title="KEF",
    )
    coordinator = KefCoordinator(hass, entry)
    coordinator.async_request_refresh = AsyncMock()

    class _FakeModernClient:
        backend = KefBackend.MODERN

        def __init__(self) -> None:
            self.async_poll_events = AsyncMock(
                side_effect=[
                    [
                        {
                            "path": "player:volume",
                            "itemValue": {"type": "i32_", "i32_": 79},
                        }
                    ],
                    asyncio.CancelledError(),
                ]
            )
            self.async_reset_event_queue = AsyncMock()

    coordinator.client = _FakeModernClient()

    with pytest.raises(asyncio.CancelledError):
        await coordinator._async_event_listener_loop()

    coordinator.async_request_refresh.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_event_listener_falls_back_after_device_error(monkeypatch, hass) -> None:
    """Event queue failures should reset local state and retain polling fallback."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
        },
        title="KEF",
    )
    coordinator = KefCoordinator(hass, entry)

    class _FakeModernClient:
        backend = KefBackend.MODERN
        async_poll_events = AsyncMock(side_effect=KefError("offline"))
        async_reset_event_queue = AsyncMock()

    coordinator.client = _FakeModernClient()

    async def cancel_after_fallback(delay: float) -> None:
        assert delay == 5
        raise asyncio.CancelledError

    with monkeypatch.context() as patch_context:
        patch_context.setattr(
            "custom_components.kef.coordinator.asyncio.sleep",
            cancel_after_fallback,
        )
        with pytest.raises(asyncio.CancelledError):
            await coordinator._async_event_listener_loop()

    coordinator.client.async_reset_event_queue.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_stop_event_listener_cancels_and_clears_queue(hass) -> None:
    """Unloading should cancel the listener and clear its local queue state."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
        },
        title="KEF",
    )
    coordinator = KefCoordinator(hass, entry)

    class _FakeModernClient:
        backend = KefBackend.MODERN
        async_reset_event_queue = AsyncMock()

    coordinator.client = _FakeModernClient()
    listener_task = asyncio.create_task(asyncio.Event().wait())
    coordinator._event_listener_task = listener_task

    await coordinator.async_stop_event_listener()

    assert listener_task.cancelled()
    assert coordinator._event_listener_task is None
    coordinator.client.async_reset_event_queue.assert_awaited_once_with()


@pytest.mark.asyncio
async def test_update_data_raises_config_entry_auth_failed(hass) -> None:
    """Authentication failures should trigger Home Assistant reauth."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
        },
        title="KEF",
    )
    coordinator = KefCoordinator(hass, entry)
    coordinator.client = AsyncMock()
    coordinator.client.async_refresh.side_effect = KefAuthenticationRequiredError(
        "password required"
    )

    with pytest.raises(ConfigEntryAuthFailed):
        await coordinator._async_update_data()


@pytest.mark.asyncio
async def test_apply_local_change_publishes_updated_snapshot(hass) -> None:
    """A local change should replace the snapshot and notify listeners."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
        },
        title="KEF",
    )
    coordinator = KefCoordinator(hass, entry)
    coordinator.data = replace(TEST_SNAPSHOT, volume_raw=40, volume_level=0.40)
    updates: list[int | None] = []
    coordinator.async_add_listener(lambda: updates.append(coordinator.data.volume_raw))

    coordinator.async_apply_local_change(volume_raw=44, volume_level=0.44)

    assert coordinator.data.volume_raw == 44
    assert coordinator.data.volume_level == 0.44
    assert updates == [44]


@pytest.mark.asyncio
async def test_apply_local_change_is_a_no_op_before_first_refresh(hass) -> None:
    """No snapshot yet means nothing to patch."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
        },
        title="KEF",
    )
    coordinator = KefCoordinator(hass, entry)

    coordinator.async_apply_local_change(volume_raw=44)

    assert coordinator.data is None


def _coordinator(hass) -> KefCoordinator:
    """Build a coordinator against a throwaway config entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": TEST_HOST,
            "port": TEST_PORT,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
        },
        title="KEF",
    )
    return KefCoordinator(hass, entry)


@pytest.mark.asyncio
async def test_local_change_survives_a_read_that_started_before_it(hass) -> None:
    """An in-flight read is stale for a field written during it; keep the write."""
    coordinator = _coordinator(hass)
    coordinator.data = replace(TEST_SNAPSHOT, volume_raw=40, volume_level=0.40)
    reading = asyncio.Event()
    finish = asyncio.Event()

    async def _slow_refresh():
        reading.set()
        await finish.wait()
        # captured before the write below
        return replace(TEST_SNAPSHOT, volume_raw=40, volume_level=0.40)

    coordinator.client = SimpleNamespace(async_refresh=_slow_refresh)
    task = asyncio.create_task(coordinator._async_update_data())
    await reading.wait()
    coordinator.async_apply_local_change(volume_raw=44, volume_level=0.44)
    finish.set()

    snapshot = await task
    assert snapshot.volume_raw == 44
    assert snapshot.volume_level == 0.44


@pytest.mark.asyncio
async def test_a_newer_read_replaces_the_local_change(hass) -> None:
    """Once a read that started after the write lands, the device wins."""
    coordinator = _coordinator(hass)
    coordinator.data = replace(TEST_SNAPSHOT, volume_raw=40, volume_level=0.40)
    coordinator.async_apply_local_change(volume_raw=44, volume_level=0.44)

    async def _refresh():
        return replace(TEST_SNAPSHOT, volume_raw=60, volume_level=0.60)

    coordinator.client = SimpleNamespace(async_refresh=_refresh)

    snapshot = await coordinator._async_update_data()
    assert snapshot.volume_raw == 60
    assert coordinator._local_changes == {}
