"""The KEF integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.helpers import entity_registry as er

from .const import CONF_ENABLE_EQ_SENSORS, DEFAULT_ENABLE_EQ_SENSORS
from .coordinator import KefConfigEntry, KefCoordinator

PLATFORMS = [
    Platform.MEDIA_PLAYER,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]

_EQ_ENTITY_KEYS = {
    "balance",
    "bass_extension",
    "treble_amount",
    "subwoofer_gain",
    "high_pass_frequency",
    "desk_mode",
    "wall_mode",
    "phase_correction",
    "high_pass_mode",
}


async def async_setup_entry(hass, entry: KefConfigEntry) -> bool:
    """Set up KEF from a config entry."""
    coordinator = KefCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await _async_cleanup_optional_entities(hass, entry, coordinator)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    return True


async def async_unload_entry(hass, entry: KefConfigEntry) -> bool:
    """Unload a config entry."""
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass, entry: KefConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_cleanup_optional_entities(
    hass,
    entry: KefConfigEntry,
    coordinator: KefCoordinator,
) -> None:
    """Remove registry entries for optional entities that are now disabled."""
    if entry.options.get(CONF_ENABLE_EQ_SENSORS, DEFAULT_ENABLE_EQ_SENSORS):
        return

    registry = er.async_get(hass)
    device_unique_id = coordinator.data.device.unique_id
    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        unique_id = entity_entry.unique_id
        if not unique_id.startswith(f"{device_unique_id}_"):
            continue

        key = unique_id.removeprefix(f"{device_unique_id}_")
        if key in _EQ_ENTITY_KEYS:
            registry.async_remove(entity_entry.entity_id)
