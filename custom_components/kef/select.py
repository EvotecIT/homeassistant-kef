"""Select platform for KEF configuration controls."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import MASTER_CHANNEL_OPTIONS, STANDBY_MODE_OPTIONS, WAKE_SOURCE_OPTIONS
from .coordinator import KefConfigEntry, KefCoordinator
from .entity import KefEntity
from .models import KefBackend, KefSnapshot


async def _async_set_standby_mode(
    coordinator: KefCoordinator,
    value: str,
) -> None:
    """Set the standby mode."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_standby_mode(value)


async def _async_set_wake_source(
    coordinator: KefCoordinator,
    value: str,
) -> None:
    """Set the wake source."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_wake_source(value)


async def _async_set_master_channel(
    coordinator: KefCoordinator,
    value: str,
) -> None:
    """Set the master channel assignment."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_master_channel(value)


@dataclass(frozen=True, kw_only=True)
class KefSelectDescription(SelectEntityDescription):
    """Describe a KEF configuration select."""

    value_fn: Callable[[KefSnapshot], str | None]
    async_set_fn: Callable[[KefCoordinator, str], Awaitable[None]]
    options_map: dict[str, str]


SELECTS: tuple[KefSelectDescription, ...] = (
    KefSelectDescription(
        key="standby_mode",
        name="Standby mode",
        icon="mdi:sleep",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.standby_mode,
        async_set_fn=_async_set_standby_mode,
        options_map=STANDBY_MODE_OPTIONS,
    ),
    KefSelectDescription(
        key="wake_source",
        name="Wake source",
        icon="mdi:power-plug",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.wake_source,
        async_set_fn=_async_set_wake_source,
        options_map=WAKE_SOURCE_OPTIONS,
    ),
    KefSelectDescription(
        key="master_channel",
        name="Master channel",
        icon="mdi:speaker",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.master_channel,
        async_set_fn=_async_set_master_channel,
        options_map=MASTER_CHANNEL_OPTIONS,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KefConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEF configuration selects."""
    coordinator = entry.runtime_data
    if coordinator.data.device.backend is not KefBackend.MODERN:
        return

    entities = [
        KefSelect(coordinator, description)
        for description in SELECTS
        if description.value_fn(coordinator.data) is not None
    ]
    async_add_entities(entities)


class KefSelect(KefEntity, CoordinatorEntity[KefCoordinator], SelectEntity):
    """Coordinator-backed KEF configuration select."""

    entity_description: KefSelectDescription

    def __init__(
        self,
        coordinator: KefCoordinator,
        description: KefSelectDescription,
    ) -> None:
        """Initialize the select."""
        CoordinatorEntity.__init__(self, coordinator)
        KefEntity.__init__(self, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.data.device.unique_id}_{description.key}"
        )
        self._attr_options = list(description.options_map.values())
        self._attr_name = description.name

    @property
    def current_option(self) -> str | None:
        """Return the current friendly option."""
        value = self.entity_description.value_fn(self.coordinator.data)
        if value is None:
            return None
        return self.entity_description.options_map.get(value, value)

    async def async_select_option(self, option: str) -> None:
        """Select an option."""
        reverse_map = {
            friendly: raw
            for raw, friendly in self.entity_description.options_map.items()
        }
        raw_value = reverse_map.get(option, option)
        await self.entity_description.async_set_fn(self.coordinator, raw_value)
        await self.coordinator.async_request_refresh()
