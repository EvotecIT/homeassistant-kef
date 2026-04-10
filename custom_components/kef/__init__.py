"""The KEF integration."""

from __future__ import annotations

from homeassistant.const import Platform
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_ENABLE_DIAGNOSTICS,
    DEFAULT_ENABLE_DIAGNOSTICS,
)
from .coordinator import KefConfigEntry, KefCoordinator

PLATFORMS = [
    Platform.MEDIA_PLAYER,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
]

_ACTIVE_SENSOR_ENTITY_KEYS = {
    "backend",
    "speaker_status",
    "play_mode",
    "service_id",
    "wifi_signal_level",
    "wifi_ssid",
    "wifi_frequency",
    "wifi_bssid",
}

_ACTIVE_BINARY_SENSOR_ENTITY_KEYS: set[str] = set()


async def async_setup_entry(hass, entry: KefConfigEntry) -> bool:
    """Set up KEF from a config entry."""
    coordinator = KefCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await _async_cleanup_optional_entities(hass, entry, coordinator)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_start_event_listener()
    return True


async def async_unload_entry(hass, entry: KefConfigEntry) -> bool:
    """Unload a config entry."""
    await entry.runtime_data.async_stop_event_listener()
    return await hass.config_entries.async_unload_platforms(entry, PLATFORMS)


async def async_reload_entry(hass, entry: KefConfigEntry) -> None:
    """Reload the config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def _async_cleanup_optional_entities(
    hass,
    entry: KefConfigEntry,
    coordinator: KefCoordinator,
) -> None:
    """Remove stale registry entries for optional or retired entities."""
    registry = er.async_get(hass)
    device_unique_id = coordinator.data.device.unique_id
    diagnostics_enabled = entry.options.get(
        CONF_ENABLE_DIAGNOSTICS,
        DEFAULT_ENABLE_DIAGNOSTICS,
    )
    expected_sensor_keys = {"backend", "speaker_status", "play_mode"}
    if diagnostics_enabled:
        expected_sensor_keys.update(
            {
                "service_id",
                "wifi_signal_level",
                "wifi_ssid",
                "wifi_frequency",
                "wifi_bssid",
            }
        )
    expected_binary_sensor_keys = set(_ACTIVE_BINARY_SENSOR_ENTITY_KEYS)

    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        platform = entity_entry.entity_id.split(".", 1)[0]
        unique_id = entity_entry.unique_id
        if platform not in {"sensor", "binary_sensor"}:
            continue

        if not unique_id.startswith(f"{device_unique_id}_"):
            registry.async_remove(entity_entry.entity_id)
            continue

        key = unique_id.removeprefix(f"{device_unique_id}_")
        if platform == "sensor" and key not in expected_sensor_keys:
            registry.async_remove(entity_entry.entity_id)
        if platform == "binary_sensor" and key not in expected_binary_sensor_keys:
            registry.async_remove(entity_entry.entity_id)
