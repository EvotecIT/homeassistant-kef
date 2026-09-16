"""Button platform for KEF actions."""

from __future__ import annotations

from homeassistant.components.button import ButtonEntity
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import model_supports_feature
from .coordinator import KefConfigEntry, KefCoordinator
from .entity import KefEntity
from .models import KefBackend

BUTTON_MODEL_FEATURES = {"start_calibration": "xio"}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KefConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up KEF buttons."""
    coordinator = entry.runtime_data
    if coordinator.data.device.backend is not KefBackend.MODERN:
        return
    if not model_supports_feature(
        coordinator.data.device.model,
        BUTTON_MODEL_FEATURES["start_calibration"],
    ):
        return
    async_add_entities([KefStartCalibrationButton(coordinator)])


class KefStartCalibrationButton(
    KefEntity,
    CoordinatorEntity[KefCoordinator],
    ButtonEntity,
):
    """Button to start room calibration (XIO only)."""

    _attr_icon = "mdi:tune"

    def __init__(self, coordinator: KefCoordinator) -> None:
        """Initialize the button."""
        CoordinatorEntity.__init__(self, coordinator)
        KefEntity.__init__(self, coordinator)
        self._attr_unique_id = f"{coordinator.data.device.unique_id}_start_calibration"
        self._attr_name = "DSP: Start calibration"

    async def async_press(self) -> None:
        """Start room calibration."""
        await self.async_call_kef(self.coordinator.client.async_start_calibration)
        await self.coordinator.async_request_refresh()
