"""Home Assistant discovers writable legacy DSP entities and applies scenes."""

import pytest
from homeassistant.const import CONF_HOST
from homeassistant.helpers import entity_registry as er
from homeassistant.setup import async_setup_component
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef.const import (
    CONF_BACKEND,
    CONF_DEVICE_ID,
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

            registers[ord("0")] = 11
            await entry.runtime_data.async_refresh()
            await hass.async_block_till_done()

            desk = entity_id("switch", "desk_mode")
            bass = entity_id("select", "bass_extension")
            wall = entity_id("number", "wall_mode_db")
            treble = entity_id("number", "treble_amount")
            high = entity_id("switch", "high_pass_mode")
            crossover = entity_id("number", "high_pass_frequency")
            assert all((desk, bass, wall, treble, high, crossover))
            assert entity_id("select", "standby_mode") is None
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
                    },
                },
                blocking=True,
            )
            await entry.runtime_data.async_refresh()
            await hass.async_block_till_done()

            assert registers[0x27] == 0xAD
            assert registers[0x29] == 131
            assert registers[0x2B] == 137
            assert hass.states.get(desk).state == "on"
            assert hass.states.get(bass).state == "Less"
            assert float(hass.states.get(wall).state) == -4.5
            assert float(hass.states.get(crossover).state) == 95
        finally:
            assert await hass.config_entries.async_unload(entry.entry_id)
            await hass.async_block_till_done()
