"""The KEF integration."""

from __future__ import annotations

import voluptuous as vol
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er

from .const import (
    CONF_ENABLE_DIAGNOSTICS,
    DEFAULT_ENABLE_DIAGNOSTICS,
    DOMAIN,
)
from .coordinator import KefConfigEntry, KefCoordinator
from .exceptions import KefError

PLATFORMS = [
    Platform.MEDIA_PLAYER,
    Platform.SWITCH,
    Platform.SELECT,
    Platform.NUMBER,
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.UPDATE,
    Platform.TEXT,
]

ATTR_FIRMWARE_FILE_PATH = "file_path"
SERVICE_INSTALL_FIRMWARE_FILE = "install_firmware_file"

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
    _async_register_services(hass)
    coordinator = KefCoordinator(hass, entry)
    await coordinator.async_config_entry_first_refresh()
    entry.runtime_data = coordinator
    await _async_cleanup_optional_entities(hass, entry, coordinator)
    entry.async_on_unload(entry.add_update_listener(async_reload_entry))
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)
    await coordinator.async_start_event_listener()
    return True


def _async_register_services(hass: HomeAssistant) -> None:
    """Register integration-level services."""
    if hass.services.has_service(DOMAIN, SERVICE_INSTALL_FIRMWARE_FILE):
        return

    async def async_handle_install_firmware_file(call: ServiceCall) -> None:
        await _async_handle_install_firmware_file(hass, call)

    hass.services.async_register(
        DOMAIN,
        SERVICE_INSTALL_FIRMWARE_FILE,
        async_handle_install_firmware_file,
        schema=vol.Schema(
            {
                vol.Required(ATTR_ENTITY_ID): cv.entity_id,
                vol.Required(ATTR_FIRMWARE_FILE_PATH): cv.string,
            }
        ),
    )


async def _async_handle_install_firmware_file(
    hass: HomeAssistant,
    call: ServiceCall,
) -> None:
    """Upload a local firmware image through the selected KEF update entity."""
    entity_id = call.data[ATTR_ENTITY_ID]
    registry = er.async_get(hass)
    entity_entry = registry.async_get(entity_id)
    if (
        entity_entry is None
        or entity_entry.domain != Platform.UPDATE
        or entity_entry.platform != DOMAIN
        or entity_entry.config_entry_id is None
    ):
        raise HomeAssistantError("Target must be a KEF firmware update entity")

    config_entry = hass.config_entries.async_get_entry(entity_entry.config_entry_id)
    coordinator = getattr(config_entry, "runtime_data", None)
    if config_entry is None or coordinator is None or coordinator.client is None:
        raise HomeAssistantError("KEF config entry is not ready")

    try:
        await coordinator.client.async_upload_firmware_update(
            call.data[ATTR_FIRMWARE_FILE_PATH]
        )
        await coordinator.async_request_refresh()
    except KefError as err:
        raise HomeAssistantError(str(err)) from err


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
                "network_ping",
                "network_stability",
                "speed_test_status",
                "speed_test_average_download",
                "speed_test_current_download",
                "speed_test_packet_loss",
                "alert_alarm_count",
                "alert_timer_count",
                "alert_snooze_time",
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
