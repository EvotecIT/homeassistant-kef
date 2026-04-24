"""Sensor platform for KEF."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENABLE_DIAGNOSTICS,
    DEFAULT_ENABLE_DIAGNOSTICS,
)
from .coordinator import KefConfigEntry, KefCoordinator
from .entity import KefEntity
from .models import KefSnapshot


@dataclass(frozen=True, kw_only=True)
class KefSensorDescription(SensorEntityDescription):
    """Describe a KEF sensor."""

    value_fn: Callable[[KefSnapshot], Any]
    diagnostics_only: bool = False


SENSORS: tuple[KefSensorDescription, ...] = (
    KefSensorDescription(
        key="backend",
        name="Backend",
        value_fn=lambda data: data.device.backend.value,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    KefSensorDescription(
        key="speaker_status",
        name="Speaker status",
        value_fn=lambda data: data.speaker_status,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    KefSensorDescription(
        key="play_mode",
        name="Play mode",
        value_fn=lambda data: data.play_mode,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    KefSensorDescription(
        key="service_id",
        name="Service ID",
        value_fn=lambda data: data.playback.service_id if data.playback else None,
        diagnostics_only=True,
        entity_category=EntityCategory.DIAGNOSTIC,
        entity_registry_enabled_default=False,
    ),
    KefSensorDescription(
        key="wifi_signal_level",
        name="Wi-Fi signal level",
        native_unit_of_measurement="dBm",
        value_fn=lambda data: data.wifi_info.signal_level if data.wifi_info else None,
        diagnostics_only=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    KefSensorDescription(
        key="wifi_ssid",
        name="Wi-Fi SSID",
        value_fn=lambda data: data.wifi_info.ssid if data.wifi_info else None,
        diagnostics_only=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    KefSensorDescription(
        key="wifi_frequency",
        name="Wi-Fi frequency",
        native_unit_of_measurement="MHz",
        value_fn=lambda data: data.wifi_info.frequency if data.wifi_info else None,
        diagnostics_only=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    KefSensorDescription(
        key="wifi_bssid",
        name="Wi-Fi BSSID",
        value_fn=lambda data: data.wifi_info.bssid if data.wifi_info else None,
        diagnostics_only=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    KefSensorDescription(
        key="network_ping",
        name="Network ping",
        native_unit_of_measurement="ms",
        value_fn=lambda data: data.network_ping_ms,
        diagnostics_only=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    KefSensorDescription(
        key="network_stability",
        name="Network stability",
        value_fn=lambda data: data.network_stability,
        diagnostics_only=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    KefSensorDescription(
        key="speed_test_status",
        name="Speed-test status",
        value_fn=lambda data: data.speed_test_status,
        diagnostics_only=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    KefSensorDescription(
        key="speed_test_average_download",
        name="Speed-test average download",
        native_unit_of_measurement="Mbit/s",
        value_fn=lambda data: data.speed_test_average_download,
        diagnostics_only=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    KefSensorDescription(
        key="speed_test_current_download",
        name="Speed-test current download",
        native_unit_of_measurement="Mbit/s",
        value_fn=lambda data: data.speed_test_current_download,
        diagnostics_only=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    KefSensorDescription(
        key="speed_test_packet_loss",
        name="Speed-test packet loss",
        native_unit_of_measurement="%",
        value_fn=lambda data: data.speed_test_packet_loss,
        diagnostics_only=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    KefSensorDescription(
        key="alert_alarm_count",
        name="Alarm count",
        value_fn=lambda data: data.alert_alarm_count,
        diagnostics_only=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    KefSensorDescription(
        key="alert_timer_count",
        name="Timer count",
        value_fn=lambda data: data.alert_timer_count,
        diagnostics_only=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
    KefSensorDescription(
        key="alert_snooze_time",
        name="Alert snooze time",
        native_unit_of_measurement="min",
        value_fn=lambda data: data.alert_snooze_minutes,
        diagnostics_only=True,
        entity_category=EntityCategory.DIAGNOSTIC,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KefConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEF sensors."""
    coordinator = entry.runtime_data
    enable_diagnostics = entry.options.get(
        CONF_ENABLE_DIAGNOSTICS,
        DEFAULT_ENABLE_DIAGNOSTICS,
    )

    entities = []
    for description in SENSORS:
        if description.diagnostics_only and not enable_diagnostics:
            continue
        entities.append(KefSensor(coordinator, description))
    async_add_entities(entities)


class KefSensor(KefEntity, CoordinatorEntity[KefCoordinator], SensorEntity):
    """Coordinator-backed KEF sensor."""

    entity_description: KefSensorDescription

    def __init__(
        self,
        coordinator: KefCoordinator,
        description: KefSensorDescription,
    ) -> None:
        """Initialize the sensor."""
        CoordinatorEntity.__init__(self, coordinator)
        KefEntity.__init__(self, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.data.device.unique_id}_{description.key}"
        )
        self._attr_name = None

    @property
    def native_value(self) -> Any:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data)
