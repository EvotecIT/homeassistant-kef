"""HA configuration actions preserve wire values, state and HTTP failures."""

from dataclasses import replace
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
from custom_components.kef.models import KefEqProfile
from tests.conftest import EQ_PROFILE_V2_VALUE, TEST_HOST, TEST_SNAPSHOT
from tests.test_http_session import local_server

pytestmark = pytest.mark.usefixtures("socket_enabled")


@pytest.mark.parametrize("status", [200, 503])
@pytest.mark.parametrize(
    ("domain", "key", "value", "path", "wire_type", "normalized"),
    [
        ("text", "ui_language", " en_GB ", "settings:/ui/language", "string_", "en_GB"),
        (
            "text",
            "speaker_location",
            " gb ",
            "settings:/kef/host/speakerLocation",
            "string_",
            "GB",
        ),
        (
            "select",
            "standby_mode",
            "20 minutes",
            "settings:/kef/host/standbyMode",
            "kefStandbyMode",
            "standby_20mins",
        ),
        (
            "select",
            "cable_mode",
            "Wireless",
            "settings:/kef/host/cableMode",
            "kefCableMode",
            "wireless",
        ),
        (
            "select",
            "master_channel",
            "Left",
            "settings:/kef/host/masterChannelMode",
            "kefMasterChannelMode",
            "left",
        ),
        (
            "select", "remote_ir_code", "Set B",
            "settings:/kef/host/remote/remoteIRCode",
            "kefSpeakerIRCode", "ir_code_set_b",
        ),
        (
            "select", "streaming_quality", "256 kbps",
            "settings:/airable/bitrate", "airableStreamBitrate", "256",
        ),
        (
            "number", "default_volume_global", 37,
            "settings:/kef/host/defaultVolumeGlobal", "i32_", 37,
        ),
        (
            "number", "maximum_volume", 80,
            "settings:/kef/host/maximumVolume", "i32_", 80,
        ),
        (
            "number", "volume_step", 4,
            "settings:/kef/host/volumeStep", "i16_", 4,
        ),
        ("switch", "startup_tone", False,
         "settings:/kef/host/startupTone", "bool_", False),
        ("switch", "front_led", True,
         "settings:/kef/host/disableFrontLED", "bool_", False),
        ("switch", "standby_led", False,
         "settings:/kef/host/disableFrontStandbyLED", "bool_", True),
        *[
            ("switch", key, enabled, path, "bool_", not enabled)
            for key, path in (
                ("analytics", "settings:/kef/host/disableAnalytics"),
                ("app_analytics", "settings:/kef/host/disableAppAnalytics"),
            )
            for enabled in (False, True)
        ],
    ],
)
async def test_configuration_service_preserves_wire_value_and_state(
    hass,
    domain,
    key,
    value,
    path,
    wire_type,
    normalized,
    status,
):
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=TEST_SNAPSHOT.device.device_name,
        unique_id=TEST_SNAPSHOT.device.unique_id,
        data={CONF_HOST: TEST_HOST, CONF_BACKEND: TEST_SNAPSHOT.device.backend},
    )
    entry.add_to_hass(hass)

    snapshot = TEST_SNAPSHOT
    if key == "front_led":
        snapshot = replace(
            snapshot,
            device=replace(snapshot.device, model="LS50W2", model_code="LS50W2"),
            eq_profile=KefEqProfile.from_modern_value(EQ_PROFILE_V2_VALUE),
        )
    if domain == "switch":
        snapshot = replace(snapshot, **{f"{key}_enabled": not value})

    async def refresh(coordinator):
        coordinator.async_set_updated_data(snapshot)

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
                "127.0.0.1",
                session,
                port=port,
            )
            refresh_after_write = AsyncMock()
            entry.runtime_data.async_request_refresh = refresh_after_write
            entity_id = er.async_get(hass).async_get_entity_id(
                domain,
                DOMAIN,
                f"{TEST_SNAPSHOT.device.unique_id}_{key}",
            )
            assert entity_id is not None
            before = hass.states.get(entity_id).state
            data = {"entity_id": entity_id}
            if domain == "switch":
                service = "turn_on" if value else "turn_off"
            else:
                service = "select_option" if domain == "select" else "set_value"
                data["option" if domain == "select" else "value"] = value
            action = hass.services.async_call(domain, service, data, blocking=True)
            if status == 200:
                await action
                refresh_after_write.assert_awaited_once_with()
            else:
                with pytest.raises(HomeAssistantError) as error:
                    await action
                assert error.value.translation_domain == DOMAIN
                assert error.value.translation_key == "command_failed"
                assert error.value.translation_placeholders["error"]
                refresh_after_write.assert_not_awaited()
            assert captured == [
                {
                    "path": path,
                    "role": "value",
                    "value": {"type": wire_type, wire_type: normalized},
                }
            ]
            await hass.async_block_till_done()
            expected_state = before
            if status == 200:
                if domain == "select":
                    expected_state = value
                elif domain == "switch":
                    expected_state = "on" if value else "off"
            if domain == "number" and status == 200:
                assert float(hass.states.get(entity_id).state) == normalized
            else:
                assert hass.states.get(entity_id).state == expected_state
            assert not session.closed
    finally:
        assert await hass.config_entries.async_unload(entry.entry_id)
