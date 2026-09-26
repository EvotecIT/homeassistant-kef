"""Update platform for KEF firmware updates."""

from __future__ import annotations

import logging
import time

import aiohttp
from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import KefConfigEntry, KefCoordinator
from .entity import KefEntity
from .models import KefBackend
from .release_notes import (
    RELEASE_NOTES_URL,
    FirmwareRelease,
    find_release,
    format_release,
    parse_release_notes,
)

_LOGGER = logging.getLogger(__name__)

_RELEASE_NOTES_TIMEOUT = aiohttp.ClientTimeout(total=10)
_RELEASE_NOTES_CACHE_SECONDS = 3600

_IN_PROGRESS_STATES = {
    "checkingForUpdate",
    "checkingForUpdates",
    "downloading",
    "downloadInProgress",
    "downloadingUpdate",
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

    _attr_supported_features = (
        UpdateEntityFeature.INSTALL | UpdateEntityFeature.RELEASE_NOTES
    )

    def __init__(self, coordinator: KefCoordinator) -> None:
        """Initialize the update entity."""
        CoordinatorEntity.__init__(self, coordinator)
        KefEntity.__init__(self, coordinator)
        self._attr_unique_id = f"{coordinator.data.device.unique_id}_firmware"
        self._attr_name = "Firmware"
        self._releases: dict[str, list[FirmwareRelease]] | None = None
        self._releases_fetched_at = 0.0

    @property
    def installed_version(self) -> str | None:
        """Return the currently installed firmware version."""
        return self.coordinator.data.device.firmware_version

    @property
    def latest_version(self) -> str | None:
        """Return the latest available firmware version."""
        update = self.coordinator.data.firmware_update
        if update is None:
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

    async def async_release_notes(self) -> str | None:
        """Return KEF's published notes for the version the speaker reports.

        Only called when the update dialog is opened. Versions and update
        availability always come from the speaker; the notes page is
        informational, so any fetch or parse failure just means no notes.
        """
        releases = await self._async_get_releases()
        if releases is None:
            return None
        release = find_release(
            releases, self.coordinator.data.device.model, self.latest_version
        )
        return format_release(release) if release is not None else None

    async def _async_get_releases(self) -> dict[str, list[FirmwareRelease]] | None:
        """Fetch and parse the release notes page, cached for an hour."""
        now = time.monotonic()
        if (
            self._releases is not None
            and now - self._releases_fetched_at < _RELEASE_NOTES_CACHE_SECONDS
        ):
            return self._releases
        session = async_get_clientsession(self.hass)
        try:
            async with session.get(
                RELEASE_NOTES_URL, timeout=_RELEASE_NOTES_TIMEOUT
            ) as response:
                response.raise_for_status()
                page = await response.text()
        except (aiohttp.ClientError, TimeoutError) as err:
            _LOGGER.debug("KEF release notes unavailable: %s", err)
            return self._releases
        self._releases = parse_release_notes(page)
        self._releases_fetched_at = now
        return self._releases

    async def async_install(
        self,
        version: str | None,
        backup: bool,
        **kwargs,
    ) -> None:
        """Install the available firmware update."""
        await self.async_call_kef(
            self.coordinator.client.async_install_firmware_update
        )
        await self.coordinator.async_request_refresh()
