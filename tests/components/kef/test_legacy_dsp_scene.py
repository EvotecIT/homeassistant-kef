"""Home Assistant discovers writable legacy DSP entities and applies scenes."""

import pytest
from homeassistant.const import CONF_HOST
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef.const import (
    CONF_BACKEND,
    CONF_DEVICE_ID,
    CONF_LEGACY_VOLUME_CAP,
    CONF_TCP_PORT,
    DOMAIN,
)
from tests.test_legacy_dsp import dsp_speaker

pytestmark = pytest.mark.usefixtures("socket_enabled")


async def test_legacy_dsp_scene_after_standby_startup(hass):
    """Powering on discovers the DSP entities and scene writes reach the speaker."""
    registers = {
        ord("0"): 139,
        ord("%"): 42,
        0x27: 0x84,
        0x28: 138,
        0x29: 140,
        0x2A: 132,
        0x2B: 255,
        0x2C: 136,
        0x2D: 138,
    }
    async with dsp_speaker(registers) as (port, received):
        identity = "legacy-dsp-test"
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Legacy DSP",
            unique_id=identity,
            data={
                CONF_HOST: "127.0.0.1",
                CONF_BACKEND: "legacy",
                CONF_TCP_PORT: port,
                CONF_DEVICE_ID: identity,
            },
        )
        entry.add_to_hass(hass)
        assert await hass.config_entries.async_setup(entry.entry_id)
        assert await async_setup_component(hass, "scene", {})
        await hass.async_block_till_done()
        registry = er.async_get(hass)

        def entity_id(platform, key):
            return registry.async_get_entity_id(platform, DOMAIN, f"{identity}_{key}")

        try:
            assert entity_id("switch", "desk_mode") is None
            assert b"G'\x80" not in received
            standby = entity_id("select", "standby_mode")
            assert standby is not None
            assert hass.states.get(standby).state == "20 minutes"
            assert hass.states.get(standby).attributes["options"] == [
                "Never", "20 minutes", "60 minutes",
            ]

            registers[ord("0")] = 11
            await entry.runtime_data.async_refresh()
            await hass.async_block_till_done()

            desk = entity_id("switch", "desk_mode")
            bass = entity_id("select", "bass_extension")
            wall = entity_id("number", "wall_mode_db")
            treble = entity_id("number", "treble_amount")
            high = entity_id("switch", "high_pass_mode")
            crossover = entity_id("number", "high_pass_frequency")
            phase = entity_id("switch", "phase_correction")
            orientation = entity_id("select", "master_channel")
            assert all((desk, bass, wall, treble, high, crossover, phase, orientation))
            assert hass.states.get(phase).state == "on"
            assert hass.states.get(orientation).state == "Left / Right"
            media = registry.async_get_entity_id("media_player", DOMAIN, identity)
            assert media is not None
            assert hass.states.get(media).attributes["master_channel"] == "right"
            assert hass.states.get(wall).attributes["min"] == -6
            assert hass.states.get(treble).attributes["max"] == 2
            assert hass.states.get(treble).attributes["step"] == 0.5
            assert hass.states.get(crossover).state == "unknown"

            await hass.services.async_call(
                "scene",
                "apply",
                {
                    "entities": {
                        desk: "on",
                        bass: "Less",
                        wall: "-4.5",
                        high: "on",
                        crossover: "95",
                        phase: "off",
                        orientation: "Right / Left",
                    },
                },
                blocking=True,
            )
            await entry.runtime_data.async_refresh()
            await hass.async_block_till_done()

            assert registers[0x27] == 0xA9
            assert registers[ord("0")] == 75
            assert hass.states.get(phase).state == "off"
            assert hass.states.get(orientation).state == "Right / Left"
            assert hass.states.get(media).attributes["master_channel"] == "left"
            await hass.services.async_call(
                "select",
                "select_option",
                {"entity_id": standby, "option": "60 minutes"},
                blocking=True,
            )
            await entry.runtime_data.async_refresh()
            assert registers[ord("0")] == 91
            assert hass.states.get(standby).state == "60 minutes"
            assert hass.states.get(orientation).state == "Right / Left"
            assert registers[0x29] == 131
            assert registers[0x2B] == 137
            assert hass.states.get(desk).state == "on"
            assert hass.states.get(bass).state == "Less"
            assert float(hass.states.get(wall).state) == -4.5
            assert float(hass.states.get(crossover).state) == 95
        finally:
            assert await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()


async def test_legacy_ha_volume_cap_limits_set_step_and_unmute(hass):
    """Save the legacy option and enforce it through Home Assistant actions."""
    registers = {ord("0"): 11, ord("%"): 32, 0x27: 255}
    async with dsp_speaker(registers) as (port, received):
        identity = "legacy-volume-cap-test"
        entry = MockConfigEntry(
            domain=DOMAIN,
            title="Legacy volume cap",
            unique_id=identity,
            data={
                CONF_HOST: "127.0.0.1",
                CONF_BACKEND: "legacy",
                CONF_TCP_PORT: port,
                CONF_DEVICE_ID: identity,
            },
        )
        entry.add_to_hass(hass)
        options = hass.config_entries.options
        flow = await options.async_init(entry.entry_id)
        result = await options.async_configure(
            flow["flow_id"],
            {CONF_LEGACY_VOLUME_CAP: 40.0},
        )
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert entry.options[CONF_LEGACY_VOLUME_CAP] == 40
        assert type(entry.options[CONF_LEGACY_VOLUME_CAP]) is int

        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()
        entity_id = er.async_get(hass).async_get_entity_id(
            "media_player", DOMAIN, identity
        )
        assert entity_id is not None

        async def action(service, **data):
            await hass.services.async_call(
                "media_player",
                service,
                {"entity_id": entity_id, **data},
                blocking=True,
            )

        try:
            await action("volume_set", volume_level=0.95)
            assert registers[ord("%")] == 40
            assert hass.states.get(entity_id).attributes["volume_level"] == 0.4

            registers[ord("%")] = 39  # A direct device change before the next poll.
            await action("volume_up")
            assert registers[ord("%")] == 40
            writes = [command for command in received if command.startswith(b"S%")]
            await action("volume_up")
            assert [
                command for command in received if command.startswith(b"S%")
            ] == writes

            registers[ord("%")] = 90
            await action("volume_mute", is_volume_muted=True)
            assert registers[ord("%")] == 218
            await action("volume_mute", is_volume_muted=False)
            assert registers[ord("%")] == 40
            await entry.runtime_data.async_refresh()
            attrs = hass.states.get(entity_id).attributes
            assert attrs["is_volume_muted"] is False
            assert attrs["volume_level"] == 0.4
        finally:
            assert await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()
