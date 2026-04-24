"""Select platform for KEF configuration controls."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.select import SelectEntity, SelectEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import (
    BASS_EXTENSION_OPTIONS,
    CABLE_MODE_OPTIONS,
    EQ_BUTTON_OPTIONS,
    FAVOURITE_BUTTON_OPTIONS,
    IR_CODE_OPTIONS,
    MASTER_CHANNEL_OPTIONS,
    STANDBY_MODE_OPTIONS,
    STREAMING_QUALITY_OPTIONS,
    WAKE_SOURCE_OPTIONS,
)
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


async def _async_set_cable_mode(
    coordinator: KefCoordinator,
    value: str,
) -> None:
    """Set the cable mode."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_cable_mode(value)


async def _async_set_bass_extension(
    coordinator: KefCoordinator,
    value: str,
) -> None:
    """Set the EQ bass extension."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_bass_extension(value)


async def _async_set_remote_ir_code(
    coordinator: KefCoordinator,
    value: str,
) -> None:
    """Set the IR remote code set."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_remote_ir_code(value)


async def _async_set_streaming_quality(
    coordinator: KefCoordinator,
    value: str,
) -> None:
    """Set the Airable streaming quality."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_streaming_quality(value)


async def _async_set_favourite_button(
    coordinator: KefCoordinator,
    value: str,
) -> None:
    """Set the favourite button action."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_favourite_button_action(value)


async def _async_set_eq_button_1(
    coordinator: KefCoordinator,
    value: str,
) -> None:
    """Set the first EQ button action."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_eq_button_action(1, value)


async def _async_set_eq_button_2(
    coordinator: KefCoordinator,
    value: str,
) -> None:
    """Set the second EQ button action."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_eq_button_action(2, value)


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
    KefSelectDescription(
        key="cable_mode",
        name="Cable mode",
        icon="mdi:cable-data",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.cable_mode,
        async_set_fn=_async_set_cable_mode,
        options_map=CABLE_MODE_OPTIONS,
    ),
    KefSelectDescription(
        key="bass_extension",
        name="Bass extension",
        icon="mdi:waveform",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: (
            data.eq_profile.bass_extension if data.eq_profile else None
        ),
        async_set_fn=_async_set_bass_extension,
        options_map=BASS_EXTENSION_OPTIONS,
    ),
    KefSelectDescription(
        key="remote_ir_code",
        name="IR remote code",
        icon="mdi:remote",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.remote_ir_code,
        async_set_fn=_async_set_remote_ir_code,
        options_map=IR_CODE_OPTIONS,
    ),
    KefSelectDescription(
        key="streaming_quality",
        name="Streaming quality",
        icon="mdi:music-circle",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.streaming_quality,
        async_set_fn=_async_set_streaming_quality,
        options_map=STREAMING_QUALITY_OPTIONS,
    ),
    KefSelectDescription(
        key="favourite_button",
        name="Favourite button",
        icon="mdi:star",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.favourite_button,
        async_set_fn=_async_set_favourite_button,
        options_map=FAVOURITE_BUTTON_OPTIONS,
    ),
    KefSelectDescription(
        key="eq_button_1",
        name="EQ button 1",
        icon="mdi:gesture-tap-button",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.eq_button_1,
        async_set_fn=_async_set_eq_button_1,
        options_map=EQ_BUTTON_OPTIONS,
    ),
    KefSelectDescription(
        key="eq_button_2",
        name="EQ button 2",
        icon="mdi:gesture-tap-button",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.eq_button_2,
        async_set_fn=_async_set_eq_button_2,
        options_map=EQ_BUTTON_OPTIONS,
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
