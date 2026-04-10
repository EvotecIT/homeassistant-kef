"""Coordinator tests for KEF."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock

import pytest
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef.const import (
    CONF_BACKEND,
    CONF_TCP_PORT,
    DOMAIN,
)
from custom_components.kef.coordinator import KefCoordinator
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
