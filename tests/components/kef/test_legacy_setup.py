"""A legacy TCP speaker loads through HA without modern-only controls."""

import pytest
from homeassistant.components.media_player.const import MediaPlayerEntityFeature
from homeassistant.const import CONF_HOST
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef.const import (
    CONF_BACKEND,
    CONF_DEVICE_ID,
    CONF_TCP_PORT,
    DOMAIN,
)
from custom_components.kef.kef_client.client import LegacyBinaryClient
from tests.test_legacy_transport import legacy_server

pytestmark = pytest.mark.usefixtures("socket_enabled")


@pytest.mark.parametrize(
    ("source_code", "source", "playback_code", "state", "has_transport", "seeded"),
    [(11, "Opt", None, "on", False, False),
     (2, "Wifi", 129, "playing", True, False),
     (9, "Bluetooth", 128, "paused", True, False),
     (139, "Opt", None, "off", False, False),
     (11, "Opt", None, "on", False, True)],
    ids=["optical", "wifi-playing", "bluetooth-paused", "standby", "existing-device"],
)
async def test_legacy_tcp_setup_and_reload_preserve_supported_entities(
    hass, source_code, source, playback_code, state, has_transport, seeded,
):
    """The real TCP client composes with HA setup, platform gates and reload."""
    async def handler(reader, writer):
        command = received[-1]
        assert command[0] == ord("G"), "setup/reload must never write controls"
        value = {ord("0"): source_code, ord("%"): 42, ord("1"): playback_code}[
            command[1]
        ]
        assert value is not None
        writer.write(bytes([82, command[1], 129, value, 255]))
        await writer.drain()
        assert await reader.read() == b""

    async with legacy_server(handler, command_length=None) as (
        port, received, disconnected,
    ):
        identity = "legacy-protocol-fixture"
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Legacy protocol fixture",
            unique_id=identity,
            data={
                CONF_HOST: "127.0.0.1",
                CONF_BACKEND: "legacy",
                CONF_TCP_PORT: port,
                CONF_DEVICE_ID: identity,
            },
        )
        entry.add_to_hass(hass)
        seeded_device = None
        if seeded:
            devices = dr.async_get(hass)
            seeded_device = devices.async_get_or_create(
                config_entry_id=entry.entry_id,
                identifiers={(DOMAIN, identity)},
                configuration_url=f"http://127.0.0.1:{port}",
            )
            devices.async_update_device(
                seeded_device.id, name_by_user="Protocol room",
            )
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        try:
            assert isinstance(entry.runtime_data.client, LegacyBinaryClient)
            registry = er.async_get(hass)
            rows = er.async_entries_for_config_entry(registry, entry.entry_id)
            assert {row.entity_id.split(".", 1)[0] for row in rows} <= {
                "media_player", "sensor",
            }
            media_id = registry.async_get_entity_id("media_player", DOMAIN, identity)
            assert media_id is not None
            media = hass.states.get(media_id)
            assert media is not None
            assert media.state == state
            assert entry.runtime_data.data.source == source
            assert entry.runtime_data.data.volume_level == 0.42
            # HA omits source/volume attributes while the media player is off.
            if state != "off":
                assert media.attributes["source"] == source
                assert media.attributes["volume_level"] == 0.42
            transport = (
                MediaPlayerEntityFeature.PLAY | MediaPlayerEntityFeature.PAUSE
                | MediaPlayerEntityFeature.NEXT_TRACK
                | MediaPlayerEntityFeature.PREVIOUS_TRACK
            )
            features = MediaPlayerEntityFeature(media.attributes["supported_features"])
            assert features & transport == (transport if has_transport else 0)
            media_entry = registry.async_get(media_id)
            assert media_entry is not None
            device = dr.async_get(hass).async_get(media_entry.device_id)
            assert device is not None
            assert device.identifiers == {(DOMAIN, identity)}
            assert device.configuration_url is None
            if seeded_device is not None:
                assert device.id == seeded_device.id
                assert device.name_by_user == "Protocol room"
            assert b"G%\x80" in received
            assert (b"G1\x80" in received) is has_transport

            before = {row.unique_id: row.entity_id for row in rows}
            owner = entry.runtime_data
            assert await hass.config_entries.async_reload(entry.entry_id)
            await hass.async_block_till_done()
            assert entry.runtime_data is not owner
            assert {
                row.unique_id: row.entity_id
                for row in er.async_entries_for_config_entry(registry, entry.entry_id)
            } == before
            assert hass.states.get(media_id).state == state
        finally:
            assert await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()
