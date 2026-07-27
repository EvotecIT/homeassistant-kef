"""Coordinator tests for KEF."""

from __future__ import annotations

import asyncio
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
from tests.conftest import TEST_HOST, TEST_PORT


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
