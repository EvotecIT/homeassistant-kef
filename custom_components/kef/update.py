"""Update platform for KEF firmware updates."""

from __future__ import annotations

from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import KefConfigEntry, KefCoordinator
from .entity import KefEntity
from .models import KefBackend

_IN_PROGRESS_STATES = {
    "checkingForUpdate",
    "checkingForUpdates",
    "downloading",
    "downloadInProgress",
    "installing",
    "updateInProgress",
}


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KefConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the KEF update entity."""
    coordinator = entry.runtime_data
    if coordinator.data.device.backend is not KefBackend.MODERN:
        return
    async_add_entities([KefFirmwareUpdateEntity(coordinator)])


class KefFirmwareUpdateEntity(
    KefEntity,
    CoordinatorEntity[KefCoordinator],
    UpdateEntity,
):
    """Coordinator-backed KEF firmware update entity."""

    _attr_supported_features = UpdateEntityFeature.INSTALL

    def __init__(self, coordinator: KefCoordinator) -> None:
        """Initialize the update entity."""
        CoordinatorEntity.__init__(self, coordinator)
        KefEntity.__init__(self, coordinator)
        self._attr_unique_id = f"{coordinator.data.device.unique_id}_firmware"
        self._attr_name = "Firmware"

    @property
    def installed_version(self) -> str | None:
        """Return the currently installed firmware version."""
        return self.coordinator.data.device.firmware_version

    @property
    def latest_version(self) -> str | None:
        """Return the latest available firmware version."""
        update = self.coordinator.data.firmware_update
        if update is None or not update.is_available:
            return self.installed_version
        return update.available_version or self.installed_version

    @property
    def in_progress(self) -> bool | int | None:
        """Return whether a firmware operation is currently active."""
        update = self.coordinator.data.firmware_update
        if update is None or update.state not in _IN_PROGRESS_STATES:
            return False
        if update.download_progress is not None:
            return update.download_progress
        return True

    @property
    def release_url(self) -> str | None:
        """Return the firmware package URL when exposed by the speaker."""
        update = self.coordinator.data.firmware_update
        return update.url if update is not None else None

    @property
    def release_summary(self) -> str | None:
        """Return a short summary of the current firmware state."""
        update = self.coordinator.data.firmware_update
        return update.state if update is not None else None

    async def async_install(
        self,
        version: str | None,
        backup: bool,
        **kwargs,
    ) -> None:
        """Install the available firmware update."""
        await self.coordinator.client.async_install_firmware_update()
        await self.coordinator.async_request_refresh()
