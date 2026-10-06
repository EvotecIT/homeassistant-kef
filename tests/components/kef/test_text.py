"""HA text actions retain normalization and failure semantics through real HTTP."""

from unittest.mock import AsyncMock, patch

import pytest
from aiohttp import ClientSession, web
from homeassistant.const import CONF_HOST
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef.const import CONF_BACKEND, DOMAIN
from custom_components.kef.coordinator import KefCoordinator
from custom_components.kef.kef_client.client import ModernKefClient
from tests.conftest import TEST_HOST, TEST_SNAPSHOT
from tests.test_http_session import local_server

pytestmark = pytest.mark.usefixtures("socket_enabled")


@pytest.mark.parametrize("status", [200, 503])
@pytest.mark.parametrize(
    ("key", "value", "path", "normalized"),
    [
        ("ui_language", " en_GB ", "settings:/ui/language", "en_GB"),
        ("speaker_location", " gb ", "settings:/kef/host/speakerLocation", "GB"),
    ],
)
async def test_text_service_uses_normalized_wire_value(
    hass, key, value, path, normalized, status,
):
    entry = MockConfigEntry(
        domain=DOMAIN, title=TEST_SNAPSHOT.device.device_name,
        unique_id=TEST_SNAPSHOT.device.unique_id,
        data={CONF_HOST: TEST_HOST, CONF_BACKEND: TEST_SNAPSHOT.device.backend},
    )
    entry.add_to_hass(hass)

    async def refresh(coordinator):
        coordinator.async_set_updated_data(TEST_SNAPSHOT)

    with patch.object(KefCoordinator, "async_config_entry_first_refresh", refresh):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    captured = []

    async def handler(request):
        if request.method == "GET":
            assert request.query["path"] == "settings:/webserver/authMode"
            return web.json_response([{"type": "string_", "string_": "none"}])
        assert request.path == "/api/setData"
        captured.append(await request.json())
        return web.json_response({}, status=status)

    try:
        async with local_server(handler) as port, ClientSession() as session:
            entry.runtime_data.client = ModernKefClient(
                "127.0.0.1", session, port=port,
            )
            refresh_after_write = AsyncMock()
            entry.runtime_data.async_request_refresh = refresh_after_write
            entity_id = er.async_get(hass).async_get_entity_id(
                "text", DOMAIN, f"{TEST_SNAPSHOT.device.unique_id}_{key}",
            )
            assert entity_id is not None
            before = hass.states.get(entity_id).state
            action = hass.services.async_call(
                "text", "set_value", {"entity_id": entity_id, "value": value},
                blocking=True,
            )
            if status == 200:
                await action
                refresh_after_write.assert_awaited_once_with()
            else:
                with pytest.raises(HomeAssistantError):
                    await action
                refresh_after_write.assert_not_awaited()
            assert captured == [{
                "path": path, "role": "value",
                "value": {"type": "string_", "string_": normalized},
            }]
            assert hass.states.get(entity_id).state == before
            assert not session.closed
    finally:
        assert await hass.config_entries.async_unload(entry.entry_id)
