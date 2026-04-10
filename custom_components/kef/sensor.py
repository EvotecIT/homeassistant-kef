"""Sensor platform for KEF."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from homeassistant.components.sensor import SensorEntity, SensorEntityDescription
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    CONF_ENABLE_DIAGNOSTICS,
    CONF_ENABLE_EQ_SENSORS,
    DEFAULT_ENABLE_DIAGNOSTICS,
)
from .coordinator import KefConfigEntry, KefCoordinator
from .entity import KefEntity
from .models import KefSnapshot


@dataclass(frozen=True, kw_only=True)
class KefSensorDescription(SensorEntityDescription):
    """Describe a KEF sensor."""

    value_fn: Callable[[KefSnapshot], Any]
    requires_eq: bool = False
    diagnostics_only: bool = False


SENSORS: tuple[KefSensorDescription, ...] = (
    KefSensorDescription(
        key="backend",
        translation_key="backend",
        value_fn=lambda data: data.device.backend.value,
    ),
    KefSensorDescription(
        key="speaker_status",
        translation_key="speaker_status",
        value_fn=lambda data: data.speaker_status,
    ),
    KefSensorDescription(
        key="play_mode",
        translation_key="play_mode",
        value_fn=lambda data: data.play_mode,
    ),
    KefSensorDescription(
        key="service_id",
        translation_key="service_id",
        value_fn=lambda data: data.playback.service_id if data.playback else None,
        diagnostics_only=True,
    ),
    KefSensorDescription(
        key="wifi_signal_level",
        translation_key="wifi_signal_level",
        native_unit_of_measurement="dBm",
        value_fn=lambda data: data.wifi_info.signal_level if data.wifi_info else None,
        diagnostics_only=True,
    ),
    KefSensorDescription(
        key="wifi_ssid",
        translation_key="wifi_ssid",
        value_fn=lambda data: data.wifi_info.ssid if data.wifi_info else None,
        diagnostics_only=True,
    ),
    KefSensorDescription(
        key="wifi_frequency",
        translation_key="wifi_frequency",
        native_unit_of_measurement="MHz",
        value_fn=lambda data: data.wifi_info.frequency if data.wifi_info else None,
        diagnostics_only=True,
    ),
    KefSensorDescription(
        key="wifi_bssid",
        translation_key="wifi_bssid",
        value_fn=lambda data: data.wifi_info.bssid if data.wifi_info else None,
        diagnostics_only=True,
    ),
    KefSensorDescription(
        key="balance",
        translation_key="balance",
        value_fn=lambda data: data.eq_profile.balance if data.eq_profile else None,
        requires_eq=True,
    ),
    KefSensorDescription(
        key="bass_extension",
        translation_key="bass_extension",
        value_fn=lambda data: (
            data.eq_profile.bass_extension if data.eq_profile else None
        ),
        requires_eq=True,
    ),
    KefSensorDescription(
        key="treble_amount",
        translation_key="treble_amount",
        native_unit_of_measurement="steps",
        value_fn=lambda data: (
            data.eq_profile.treble_amount if data.eq_profile else None
        ),
        requires_eq=True,
    ),
    KefSensorDescription(
        key="subwoofer_gain",
        translation_key="subwoofer_gain",
        native_unit_of_measurement="steps",
        value_fn=lambda data: (
            data.eq_profile.subwoofer_gain if data.eq_profile else None
        ),
        requires_eq=True,
    ),
    KefSensorDescription(
        key="high_pass_frequency",
        translation_key="high_pass_frequency",
        native_unit_of_measurement="steps",
        value_fn=lambda data: (
            data.eq_profile.high_pass_frequency if data.eq_profile else None
        ),
        requires_eq=True,
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
    enable_eq_sensors = entry.options.get(CONF_ENABLE_EQ_SENSORS, True)

    entities = []
    for description in SENSORS:
        if description.diagnostics_only and not enable_diagnostics:
            continue
        if description.requires_eq and not enable_eq_sensors:
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
