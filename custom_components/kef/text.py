"""Text platform for KEF configuration controls."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.text import TextEntity, TextEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import KefConfigEntry, KefCoordinator
from .entity import KefEntity
from .models import KefBackend, KefSnapshot


async def _async_set_ui_language(
    coordinator: KefCoordinator,
    value: str,
) -> None:
    """Set the speaker UI language."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_ui_language(value.strip())


async def _async_set_speaker_location(
    coordinator: KefCoordinator,
    value: str,
) -> None:
    """Set the speaker country or region code."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_speaker_location(value.strip().upper())


@dataclass(frozen=True, kw_only=True)
class KefTextDescription(TextEntityDescription):
    """Describe a KEF configuration text entity."""

    value_fn: Callable[[KefSnapshot], str | None]
    async_set_fn: Callable[[KefCoordinator, str], Awaitable[None]]


TEXTS: tuple[KefTextDescription, ...] = (
    KefTextDescription(
        key="ui_language",
        name="UI language",
        icon="mdi:translate",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.ui_language,
        async_set_fn=_async_set_ui_language,
    ),
    KefTextDescription(
        key="speaker_location",
        name="Speaker location",
        icon="mdi:map-marker",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.speaker_location,
        async_set_fn=_async_set_speaker_location,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KefConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEF configuration text entities."""
    coordinator = entry.runtime_data
    if coordinator.data.device.backend is not KefBackend.MODERN:
        return

    entities = [
        KefText(coordinator, description)
        for description in TEXTS
        if description.value_fn(coordinator.data) is not None
    ]
    async_add_entities(entities)


class KefText(KefEntity, CoordinatorEntity[KefCoordinator], TextEntity):
    """Coordinator-backed KEF configuration text entity."""

    entity_description: KefTextDescription

    def __init__(
        self,
        coordinator: KefCoordinator,
        description: KefTextDescription,
    ) -> None:
        """Initialize the text entity."""
        CoordinatorEntity.__init__(self, coordinator)
        KefEntity.__init__(self, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.data.device.unique_id}_{description.key}"
        )
        self._attr_name = description.name

    @property
    def native_value(self) -> str | None:
        """Return the current value."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_set_value(self, value: str) -> None:
        """Set the text value."""
        await self.entity_description.async_set_fn(self.coordinator, value)
        await self.coordinator.async_request_refresh()
