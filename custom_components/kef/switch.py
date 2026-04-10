"""Switch platform for KEF configuration controls."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from homeassistant.components.switch import SwitchEntity, SwitchEntityDescription
from homeassistant.const import EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import KefConfigEntry, KefCoordinator
from .entity import KefEntity
from .models import KefBackend, KefSnapshot


async def _async_set_startup_tone(
    coordinator: KefCoordinator,
    enabled: bool,
) -> None:
    """Set the startup tone state."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_startup_tone_enabled(enabled)


async def _async_set_auto_switch_hdmi(
    coordinator: KefCoordinator,
    enabled: bool,
) -> None:
    """Set HDMI auto switching."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_auto_switch_hdmi_enabled(enabled)


async def _async_set_standby_led(
    coordinator: KefCoordinator,
    enabled: bool,
) -> None:
    """Set the standby LED state."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_standby_led_enabled(enabled)


async def _async_set_front_led(
    coordinator: KefCoordinator,
    enabled: bool,
) -> None:
    """Set the front LED state."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_front_led_enabled(enabled)


async def _async_set_top_panel(
    coordinator: KefCoordinator,
    enabled: bool,
) -> None:
    """Set the top-panel enabled state."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_top_panel_enabled(enabled)


async def _async_set_usb_charging(
    coordinator: KefCoordinator,
    enabled: bool,
) -> None:
    """Set the USB charging state."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_usb_charging_enabled(enabled)


async def _async_set_startup_volume(
    coordinator: KefCoordinator,
    enabled: bool,
) -> None:
    """Set whether startup volume is enabled."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_startup_volume_enabled(enabled)


async def _async_set_per_input_startup_volume(
    coordinator: KefCoordinator,
    enabled: bool,
) -> None:
    """Set whether per-input startup volume is enabled."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_per_input_startup_volume_enabled(enabled)


async def _async_set_volume_limit(
    coordinator: KefCoordinator,
    enabled: bool,
) -> None:
    """Set whether the volume limiter is enabled."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_volume_limit_enabled(enabled)


async def _async_set_subwoofer_wake(
    coordinator: KefCoordinator,
    enabled: bool,
) -> None:
    """Set wired subwoofer wake-on-startup."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_subwoofer_wake_enabled(enabled)


async def _async_set_kw1_wake(
    coordinator: KefCoordinator,
    enabled: bool,
) -> None:
    """Set KW1 subwoofer wake-on-startup."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_kw1_wake_enabled(enabled)


async def _async_set_desk_mode(
    coordinator: KefCoordinator,
    enabled: bool,
) -> None:
    """Set the desk mode state."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_desk_mode_enabled(enabled)


async def _async_set_wall_mode(
    coordinator: KefCoordinator,
    enabled: bool,
) -> None:
    """Set the wall mode state."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_wall_mode_enabled(enabled)


async def _async_set_phase_correction(
    coordinator: KefCoordinator,
    enabled: bool,
) -> None:
    """Set the phase correction state."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_phase_correction_enabled(enabled)


async def _async_set_high_pass_mode(
    coordinator: KefCoordinator,
    enabled: bool,
) -> None:
    """Set the high-pass mode state."""
    client = coordinator.client
    if client is None:
        return
    await client.async_set_high_pass_mode_enabled(enabled)


@dataclass(frozen=True, kw_only=True)
class KefSwitchDescription(SwitchEntityDescription):
    """Describe a KEF configuration switch."""

    value_fn: Callable[[KefSnapshot], bool | None]
    async_set_fn: Callable[[KefCoordinator, bool], Awaitable[None]]


SWITCHES: tuple[KefSwitchDescription, ...] = (
    KefSwitchDescription(
        key="startup_tone",
        name="Startup tone",
        icon="mdi:music-note",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.startup_tone_enabled,
        async_set_fn=_async_set_startup_tone,
    ),
    KefSwitchDescription(
        key="auto_switch_hdmi",
        name="Auto-switch to HDMI",
        icon="mdi:video-switch",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.auto_switch_hdmi,
        async_set_fn=_async_set_auto_switch_hdmi,
    ),
    KefSwitchDescription(
        key="front_led",
        name="Front LED",
        icon="mdi:led-strip-variant",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.front_led_enabled,
        async_set_fn=_async_set_front_led,
    ),
    KefSwitchDescription(
        key="standby_led",
        name="Standby LED",
        icon="mdi:led-outline",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.standby_led_enabled,
        async_set_fn=_async_set_standby_led,
    ),
    KefSwitchDescription(
        key="top_panel",
        name="Top touch panel",
        icon="mdi:gesture-tap-button",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.top_panel_enabled,
        async_set_fn=_async_set_top_panel,
    ),
    KefSwitchDescription(
        key="usb_charging",
        name="USB charging",
        icon="mdi:usb-port",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.usb_charging_enabled,
        async_set_fn=_async_set_usb_charging,
    ),
    KefSwitchDescription(
        key="startup_volume",
        name="Use startup volume",
        icon="mdi:volume-source",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.startup_volume_enabled,
        async_set_fn=_async_set_startup_volume,
    ),
    KefSwitchDescription(
        key="per_input_startup_volume",
        name="Per-input startup volumes",
        icon="mdi:tune-variant",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.per_input_startup_volume_enabled,
        async_set_fn=_async_set_per_input_startup_volume,
    ),
    KefSwitchDescription(
        key="volume_limit",
        name="Volume limiter",
        icon="mdi:volume-off",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.volume_limit_enabled,
        async_set_fn=_async_set_volume_limit,
    ),
    KefSwitchDescription(
        key="subwoofer_wake",
        name="Wake subwoofer on startup",
        icon="mdi:speaker-wireless",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.subwoofer_wake_enabled,
        async_set_fn=_async_set_subwoofer_wake,
    ),
    KefSwitchDescription(
        key="kw1_wake",
        name="Wake KW1 subwoofer on startup",
        icon="mdi:speaker-wireless",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.kw1_wake_enabled,
        async_set_fn=_async_set_kw1_wake,
    ),
    KefSwitchDescription(
        key="desk_mode",
        name="Desk mode",
        icon="mdi:desk",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.eq_profile.desk_mode if data.eq_profile else None,
        async_set_fn=_async_set_desk_mode,
    ),
    KefSwitchDescription(
        key="wall_mode",
        name="Wall mode",
        icon="mdi:wall",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: data.eq_profile.wall_mode if data.eq_profile else None,
        async_set_fn=_async_set_wall_mode,
    ),
    KefSwitchDescription(
        key="phase_correction",
        name="Phase correction",
        icon="mdi:waveform",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: (
            data.eq_profile.phase_correction if data.eq_profile else None
        ),
        async_set_fn=_async_set_phase_correction,
    ),
    KefSwitchDescription(
        key="high_pass_mode",
        name="High-pass mode",
        icon="mdi:chart-bell-curve-cumulative",
        entity_category=EntityCategory.CONFIG,
        value_fn=lambda data: (
            data.eq_profile.high_pass_mode if data.eq_profile else None
        ),
        async_set_fn=_async_set_high_pass_mode,
    ),
)


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KefConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEF configuration switches."""
    coordinator = entry.runtime_data
    if coordinator.data.device.backend is not KefBackend.MODERN:
        return

    entities = [
        KefSwitch(coordinator, description)
        for description in SWITCHES
        if description.value_fn(coordinator.data) is not None
    ]
    async_add_entities(entities)


class KefSwitch(KefEntity, CoordinatorEntity[KefCoordinator], SwitchEntity):
    """Coordinator-backed KEF configuration switch."""

    entity_description: KefSwitchDescription

    def __init__(
        self,
        coordinator: KefCoordinator,
        description: KefSwitchDescription,
    ) -> None:
        """Initialize the switch."""
        CoordinatorEntity.__init__(self, coordinator)
        KefEntity.__init__(self, coordinator)
        self.entity_description = description
        self._attr_unique_id = (
            f"{coordinator.data.device.unique_id}_{description.key}"
        )
        self._attr_name = description.name

    @property
    def is_on(self) -> bool | None:
        """Return whether the switch is on."""
        return self.entity_description.value_fn(self.coordinator.data)

    async def async_turn_on(self, **kwargs) -> None:
        """Turn the switch on."""
        await self.entity_description.async_set_fn(self.coordinator, True)
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self, **kwargs) -> None:
        """Turn the switch off."""
        await self.entity_description.async_set_fn(self.coordinator, False)
        await self.coordinator.async_request_refresh()
