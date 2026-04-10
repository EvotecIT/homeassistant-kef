"""Number platform for KEF configuration controls."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import KefConfigEntry, KefCoordinator
from .entity import KefEntity
from .models import KefBackend, KefSnapshot


async def _async_set_default_volume_global(
    coordinator: KefCoordinator,
    value: float,
) -> None:
    """Set the global startup volume."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_default_volume_global(round(value))


async def _async_set_maximum_volume(
    coordinator: KefCoordinator,
    value: float,
) -> None:
    """Set the maximum volume."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_maximum_volume(round(value))


async def _async_set_volume_step(
    coordinator: KefCoordinator,
    value: float,
) -> None:
    """Set the volume step."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_volume_step(round(value))


@dataclass(frozen=True, kw_only=True)
class KefNumberDescription(NumberEntityDescription):
    """Describe a KEF configuration number."""

    value_fn: Callable[[KefSnapshot], int | None]
    async_set_fn: Callable[[KefCoordinator, float], Awaitable[None]]


NUMBERS: tuple[KefNumberDescription, ...] = (
    KefNumberDescription(
        key="default_volume_global",
        name="Startup volume",
        icon="mdi:volume-medium",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        value_fn=lambda data: data.default_volume_global,
        async_set_fn=_async_set_default_volume_global,
    ),
    KefNumberDescription(
        key="maximum_volume",
        name="Maximum volume",
        icon="mdi:volume-high",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        value_fn=lambda data: data.maximum_volume,
        async_set_fn=_async_set_maximum_volume,
    ),
    KefNumberDescription(
        key="volume_step",
        name="Volume step",
        icon="mdi:stairs",
        entity_category=EntityCategory.CONFIG,
        native_min_value=1,
        native_max_value=10,
        native_step=1,
        value_fn=lambda data: data.volume_step,
        async_set_fn=_async_set_volume_step,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KefConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEF configuration numbers."""
    coordinator = entry.runtime_data
    if coordinator.data.device.backend is not KefBackend.MODERN:
        return

    entities = [
        KefNumber(coordinator, description)
        for description in NUMBERS
        if description.value_fn(coordinator.data) is not None
    ]
    async_add_entities(entities)


class KefNumber(KefEntity, CoordinatorEntity[KefCoordinator], NumberEntity):
    """Coordinator-backed KEF configuration number."""

    entity_description: KefNumberDescription

    def __init__(
        self,
        coordinator: KefCoordinator,
        description: KefNumberDescription,
    ) -> None:
        """Initialize the number entity."""
        CoordinatorEntity.__init__(self, coordinator)
        KefEntity.__init__(self, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.data.device.unique_id}_{description.key}"
        )

    @property
    def native_value(self) -> float | None:
        """Return the current numeric value."""
        value = self.entity_description.value_fn(self.coordinator.data)
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the number value."""
        await self.entity_description.async_set_fn(self.coordinator, value)
        await self.coordinator.async_request_refresh()
