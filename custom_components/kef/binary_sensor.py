"""Binary sensor platform for KEF."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass

from homeassistant.components.binary_sensor import (
    BinarySensorEntity,
    BinarySensorEntityDescription,
)
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import CONF_ENABLE_EQ_SENSORS
from .coordinator import KefConfigEntry, KefCoordinator
from .entity import KefEntity
from .models import KefSnapshot


@dataclass(frozen=True, kw_only=True)
class KefBinarySensorDescription(BinarySensorEntityDescription):
    """Describe a KEF binary sensor."""

    value_fn: Callable[[KefSnapshot], bool]


BINARY_SENSORS: tuple[KefBinarySensorDescription, ...] = (
    KefBinarySensorDescription(
        key="desk_mode",
        name="Desk mode",
        value_fn=lambda data: bool(data.eq_profile and data.eq_profile.desk_mode),
        entity_category=EntityCategory.CONFIG,
    ),
    KefBinarySensorDescription(
        key="wall_mode",
        name="Wall mode",
        value_fn=lambda data: bool(data.eq_profile and data.eq_profile.wall_mode),
        entity_category=EntityCategory.CONFIG,
    ),
    KefBinarySensorDescription(
        key="phase_correction",
        name="Phase correction",
        value_fn=lambda data: bool(
            data.eq_profile and data.eq_profile.phase_correction
        ),
        entity_category=EntityCategory.CONFIG,
    ),
    KefBinarySensorDescription(
        key="high_pass_mode",
        name="High-pass mode",
        value_fn=lambda data: bool(data.eq_profile and data.eq_profile.high_pass_mode),
        entity_category=EntityCategory.CONFIG,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KefConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEF binary sensors."""
    if not entry.options.get(CONF_ENABLE_EQ_SENSORS, True):
        return

    coordinator = entry.runtime_data
    async_add_entities(
        [KefBinarySensor(coordinator, description) for description in BINARY_SENSORS]
    )


class KefBinarySensor(
    KefEntity,
    CoordinatorEntity[KefCoordinator],
    BinarySensorEntity,
):
    """Coordinator-backed KEF binary sensor."""

    entity_description: KefBinarySensorDescription

    def __init__(
        self,
        coordinator: KefCoordinator,
        description: KefBinarySensorDescription,
    ) -> None:
        """Initialize the binary sensor."""
        CoordinatorEntity.__init__(self, coordinator)
        KefEntity.__init__(self, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.data.device.unique_id}_{description.key}"
        )
        self._attr_name = None

    @property
    def is_on(self) -> bool | None:
        """Return whether the binary sensor is on."""
        if self.coordinator.data.eq_profile is None:
            return None
        return self.entity_description.value_fn(self.coordinator.data)
