"""Number platform for KEF configuration controls."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.number import NumberEntity, NumberEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import WAKE_SOURCE_OPTIONS
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


async def _async_set_fixed_volume_level(
    coordinator: KefCoordinator,
    value: float,
) -> None:
    """Set the fixed volume level."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_fixed_volume_level(round(value))


def _friendly_source_name(source: str) -> str:
    """Return a UI-friendly source label."""
    return WAKE_SOURCE_OPTIONS.get(source, source.replace("_", " ").title())


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
    KefNumberDescription(
        key="fixed_volume_level",
        name="Fixed volume level",
        icon="mdi:volume-equal",
        entity_category=EntityCategory.CONFIG,
        native_min_value=0,
        native_max_value=100,
        native_step=1,
        value_fn=lambda data: data.fixed_volume_level,
        async_set_fn=_async_set_fixed_volume_level,
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

    entities: list[KefNumber] = [
        KefNumber(coordinator, description)
        for description in NUMBERS
        if description.value_fn(coordinator.data) is not None
    ]
    for source, value in coordinator.data.default_volume_by_source.items():
        entities.append(
            KefSourceVolumeNumber(
                coordinator,
                source,
                value,
            )
        )
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
        self._attr_name = description.name

    @property
    def native_value(self) -> float | None:
        """Return the current numeric value."""
        value = self.entity_description.value_fn(self.coordinator.data)
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the number value."""
        await self.entity_description.async_set_fn(self.coordinator, value)
        await self.coordinator.async_request_refresh()


class KefSourceVolumeNumber(KefEntity, CoordinatorEntity[KefCoordinator], NumberEntity):
    """Coordinator-backed source-specific KEF startup volume number."""

    _attr_entity_category = EntityCategory.CONFIG
    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_icon = "mdi:volume-medium"

    def __init__(
        self,
        coordinator: KefCoordinator,
        source: str,
        initial_value: int,
    ) -> None:
        """Initialize the source startup volume number."""
        CoordinatorEntity.__init__(self, coordinator)
        KefEntity.__init__(self, coordinator)
        self._source = source
        self._initial_value = initial_value
        self._attr_unique_id = (
            f"{coordinator.data.device.unique_id}_default_volume_{source}"
        )
        self._attr_name = f"{_friendly_source_name(source)} startup volume"

    @property
    def available(self) -> bool:
        """Return whether the number is available."""
        return (
            self.coordinator.last_update_success
            and self._source in self.coordinator.data.default_volume_by_source
        )

    @property
    def native_value(self) -> float | None:
        """Return the current source-specific startup volume."""
        value = self.coordinator.data.default_volume_by_source.get(
            self._source,
            self._initial_value,
        )
        return None if value is None else float(value)

    async def async_set_native_value(self, value: float) -> None:
        """Set the source-specific startup volume."""
        client = self.coordinator.client
        if client is None:
            return
        await client.async_set_default_volume_for_source(self._source, round(value))
        await self.coordinator.async_request_refresh()
