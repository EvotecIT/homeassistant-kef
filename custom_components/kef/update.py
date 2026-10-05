"""Update platform for KEF firmware updates."""

from __future__ import annotations

import logging
import time
import zlib
from datetime import datetime
from typing import Any

import aiohttp
from homeassistant.components.update import (
    UpdateEntity,
    UpdateEntityFeature,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.event import async_track_time_change
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import KefConfigEntry, KefCoordinator
from .entity import KefEntity
from .exceptions import KefAuthenticationRequiredError, KefError
from .models import KefBackend
from .release_notes import (
    RELEASE_NOTES_URL,
    FirmwareRelease,
    find_release,
    format_release,
    parse_release_notes,
    release_notes_url,
)

# Ask HA to serialize action calls within this platform for each entry.
PARALLEL_UPDATES = 1

_LOGGER = logging.getLogger(__name__)

# Once a night, each speaker is asked to look for a newer firmware image. The
# window matches when the speakers run their own overnight update cycle
# (installs were seen between 02:30 and 04:00), and every speaker gets its own
# fixed minute in it so they are not all asked at the same moment.
_CHECK_WINDOW_START_MINUTE = 2 * 60 + 30
_CHECK_WINDOW_MINUTES = 90

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

# Never ask a speaker to check while it is already handling an image.
_NO_CHECK_STATES = _IN_PROGRESS_STATES | {"downloaded"}


def nightly_check_time(unique_id: str) -> tuple[int, int]:
    """Return the (hour, minute) of a speaker's nightly check.

    The minute inside the window is derived from the unique ID, so a speaker
    always gets the same time and different speakers get different ones.
    """
    offset = zlib.crc32(unique_id.encode()) % _CHECK_WINDOW_MINUTES
    hour, minute = divmod(_CHECK_WINDOW_START_MINUTE + offset, 60)
    return hour, minute


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
        UpdateEntityFeature.INSTALL
        | UpdateEntityFeature.RELEASE_NOTES
        | UpdateEntityFeature.PROGRESS
    )

    def __init__(self, coordinator: KefCoordinator) -> None:
        """Initialize the update entity."""
        CoordinatorEntity.__init__(self, coordinator)
        KefEntity.__init__(self, coordinator)
        self._attr_unique_id = f"{coordinator.data.device.unique_id}_firmware"
        self._attr_translation_key = "firmware"
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
    def in_progress(self) -> bool:
        """Return whether a firmware operation is currently active."""
        update = self.coordinator.data.firmware_update
        if update is None or update.state not in _IN_PROGRESS_STATES:
            return False
        return True

    @property
    def update_percentage(self) -> int | None:
        """Return the percentage while a firmware operation is active."""
        update = self.coordinator.data.firmware_update
        if update is None or not self.in_progress:
            return None
        return update.download_progress

    @property
    def release_url(self) -> str | None:
        """Return KEF's release notes page for this model.

        Home Assistant opens this as "Read release announcements", so it must
        be a page. The speaker's own update URL is the firmware image, which
        a browser would download.
        """
        if self.coordinator.data.firmware_update is None:
            return None
        return release_notes_url(self.coordinator.data.device.model)

    @property
    def release_summary(self) -> str | None:
        """Return a short summary of the current firmware state."""
        update = self.coordinator.data.firmware_update
        return update.state if update is not None else None

    async def async_added_to_hass(self) -> None:
        """Schedule the nightly firmware check."""
        await super().async_added_to_hass()
        hour, minute = nightly_check_time(self.unique_id or "")
        _LOGGER.debug(
            "Nightly firmware check for %s scheduled at %02d:%02d",
            self.coordinator.config_entry.title,
            hour,
            minute,
        )
        self.async_on_remove(
            async_track_time_change(
                self.hass,
                self._async_nightly_check,
                hour=hour,
                minute=minute,
                second=0,
            )
        )

    async def _async_nightly_check(self, now: datetime) -> None:
        """Run the scheduled check."""
        await self.async_update()

    async def async_update(self) -> None:
        """Ask the speaker to check for firmware, then refresh its status.

        Home Assistant calls this for "Check for updates" in Settings >
        Updates and for the homeassistant.update_entity service, and the
        nightly schedule calls it too.
        The coordinator's own update step only re-reads the status, which
        never makes the speaker look for a new image. Only the speaker's main
        firmware check is used; the XIO's wireless subwoofer module has its own
        separate check (kef:ble/*), which this integration never activates.
        """
        if not self.enabled:
            return
        if self._can_check_firmware():
            _LOGGER.debug(
                "Asking KEF speaker %s to check for firmware",
                self.coordinator.config_entry.title,
            )
            try:
                await self.client.async_check_for_firmware_update()
            except KefAuthenticationRequiredError:
                self.coordinator.config_entry.async_start_reauth(self.hass)
            except KefError as err:
                _LOGGER.debug("KEF firmware check failed: %s", err)
        await self.coordinator.async_request_refresh()

    def _can_check_firmware(self) -> bool:
        """Return whether the speaker can safely be asked to check now."""
        if not self.coordinator.last_update_success:
            return False
        update = self.coordinator.data.firmware_update
        return update is None or update.state not in _NO_CHECK_STATES

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
        **kwargs: Any,
    ) -> None:
        """Install the available firmware update."""
        await self.async_call_kef(
            self.client.async_install_firmware_update
        )
        await self.coordinator.async_request_refresh()
