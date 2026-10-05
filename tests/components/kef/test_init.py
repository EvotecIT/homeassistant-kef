"""KEF config-entry lifecycle contracts."""

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
