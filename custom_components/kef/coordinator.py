"""Coordinator for KEF data updates."""

from __future__ import annotations

import asyncio
import logging
import time
from dataclasses import replace
from datetime import datetime, timedelta
from typing import Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.core import callback
from homeassistant.exceptions import ConfigEntryAuthFailed
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed
from homeassistant.util import dt as dt_util

from .api import async_create_client
from .const import (
    CONF_BACKEND,
    CONF_DEVICE_ID,
    CONF_OFFLINE_RETRY_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_TCP_PORT,
    DEFAULT_OFFLINE_RETRY_INTERVAL_SECONDS,
    DEFAULT_SCAN_INTERVAL_SECONDS,
)
from .exceptions import KefAuthenticationRequiredError, KefError
from .models import KefBackend, KefSnapshot

_LOGGER = logging.getLogger(__name__)

# Consecutive failed polls before a speaker counts as offline. Earlier failures
# keep the last snapshot so a single timeout does not flip every entity to
# unavailable.
_OFFLINE_FAILURE_THRESHOLD = 3

type KefConfigEntry = ConfigEntry["KefCoordinator"]


class KefCoordinator(DataUpdateCoordinator[KefSnapshot]):
    """Coordinate KEF API updates."""

    config_entry: KefConfigEntry

    def __init__(self, hass, entry: KefConfigEntry) -> None:
        """Initialize the coordinator."""
        self._session = async_get_clientsession(hass)
        self.client = None
        self._event_listener_task: asyncio.Task[None] | None = None
        self._local_changes: dict[str, Any] = {}
        self._local_change_at = 0.0
        self._local_change_refreshes_remaining = 0
        self.last_device_update_at: datetime | None = None
        self._normal_interval = timedelta(
            seconds=entry.options.get(CONF_SCAN_INTERVAL, DEFAULT_SCAN_INTERVAL_SECONDS)
        )
        self._offline_interval = timedelta(
            seconds=entry.options.get(
                CONF_OFFLINE_RETRY_INTERVAL, DEFAULT_OFFLINE_RETRY_INTERVAL_SECONDS
            )
        )
        self._consecutive_failures = 0
        self._online = asyncio.Event()
        self._online.set()
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="kef",
            update_interval=self._normal_interval,
        )

    @property
    def is_offline(self) -> bool:
        """Return whether the speaker stopped responding to repeated polls."""
        return not self._online.is_set()

    async def _async_update_data(self) -> KefSnapshot:
        """Fetch data from the device."""
        try:
            if self.client is None:
                self.client = await async_create_client(
                    self.config_entry.data[CONF_HOST],
                    self._session,
                    backend=self.config_entry.data[CONF_BACKEND],
                    port=self.config_entry.data.get(CONF_PORT),
                    password=self.config_entry.options.get(
                        CONF_PASSWORD,
                        self.config_entry.data.get(CONF_PASSWORD),
                    ),
                    tcp_port=self.config_entry.data.get(CONF_TCP_PORT),
                    async_add_executor_job=self.hass.async_add_executor_job,
                )
            started_at = time.monotonic()
            snapshot = await self.client.async_refresh()
        except KefAuthenticationRequiredError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except KefError as err:
            return self._handle_refresh_failure(err)
        self._handle_refresh_success()
        if snapshot.device.backend is KefBackend.LEGACY:
            stored_id = self.config_entry.data.get(CONF_DEVICE_ID)
            if stored_id and snapshot.device.unique_id != stored_id:
                snapshot = replace(
                    snapshot,
                    device=replace(snapshot.device, unique_id=stored_id),
                )
        self.last_device_update_at = dt_util.utcnow()
        return self._merge_local_changes(snapshot, started_at)

    def _handle_refresh_failure(self, err: KefError) -> KefSnapshot:
        """Tolerate brief failures, then switch to the slower offline retry."""
        self._consecutive_failures += 1
        if self.data is None:
            # Nothing to fall back on yet; Home Assistant retries the setup.
            raise UpdateFailed(str(err)) from err
        if self._consecutive_failures < _OFFLINE_FAILURE_THRESHOLD:
            _LOGGER.debug(
                "KEF speaker %s poll failed (%s of %s), keeping last state: %s",
                self.config_entry.title,
                self._consecutive_failures,
                _OFFLINE_FAILURE_THRESHOLD,
                err,
            )
            return self.data
        if self._online.is_set():
            self._online.clear()
            self.update_interval = self._offline_interval
            _LOGGER.debug(
                "KEF speaker %s is offline, retrying every %s seconds",
                self.config_entry.title,
                int(self._offline_interval.total_seconds()),
            )
        raise UpdateFailed(str(err)) from err

    def _handle_refresh_success(self) -> None:
        """Return to normal polling once the speaker answers again."""
        self._consecutive_failures = 0
        if not self._online.is_set():
            self._online.set()
            self.update_interval = self._normal_interval

    @callback
    def async_device_seen(self) -> None:
        """Retry right away when an offline speaker announces itself again."""
        if not self.is_offline:
            return
        _LOGGER.debug(
            "KEF speaker %s announced itself, retrying now", self.config_entry.title
        )
        self.config_entry.async_create_task(
            self.hass, self.async_request_refresh(), "kef_device_seen_refresh"
        )

    def _merge_local_changes(
        self, snapshot: KefSnapshot, started_at: float
    ) -> KefSnapshot:
        """Stop an in-flight read from undoing a write that landed during it.

        A refresh reads several paths and can take a second or more. If a write
        lands while one is in flight, that read is already out of date for the
        field it touched, and letting it publish would roll the value back --
        and, because commands compute the next absolute value from this data,
        the following command would then recompute from the rolled-back number.
        The first read that starts after the write gets one grace cycle when
        the device still reports the old value. That covers speakers which
        acknowledge a write before their read API reflects it. A matching read
        settles immediately; after the grace cycle, the device wins.
        """
        if not self._local_changes:
            return snapshot
        device_matches = all(
            getattr(snapshot, key) == value
            for key, value in self._local_changes.items()
        )
        if device_matches:
            self._local_changes.clear()
            self._local_change_refreshes_remaining = 0
            return snapshot
        if self._local_change_at > started_at:
            return replace(snapshot, **self._local_changes)
        if self._local_change_refreshes_remaining > 0:
            self._local_change_refreshes_remaining -= 1
            return replace(snapshot, **self._local_changes)
        self._local_changes.clear()
        return snapshot

    @callback
    def async_apply_local_change(self, **changes: Any) -> None:
        """Publish a state change this integration just made itself.

        The KEF API has no relative commands, so entities compute the next
        absolute value from ``self.data``. If a write is only reflected after a
        poll, ``self.data`` stays stale for up to ``update_interval`` and
        repeated commands keep recomputing from the same base. Publishing the
        value we just wrote keeps ``self.data`` usable as the base for the next
        command; the scheduled poll and the event listener still reconcile it
        with the device (see _merge_local_changes for the in-flight case).
        """
        self._local_changes.update(changes)
        self._local_change_at = time.monotonic()
        self._local_change_refreshes_remaining = 1
        if self.data is None:
            return
        self.async_set_updated_data(replace(self.data, **changes))

    async def async_start_event_listener(self) -> None:
        """Start the optional modern KEF event listener."""
        if self.client is None or self.client.backend is not KefBackend.MODERN:
            return
        if (
            self._event_listener_task is not None
            and not self._event_listener_task.done()
        ):
            return
        self._event_listener_task = self.hass.async_create_background_task(
            self._async_event_listener_loop(),
            f"kef_event_listener_{self.config_entry.entry_id}",
        )

    async def async_stop_event_listener(self) -> None:
        """Stop the KEF event listener if it is running."""
        if self._event_listener_task is None:
            return
        self._event_listener_task.cancel()
        try:
            await self._event_listener_task
        except asyncio.CancelledError:
            pass
        finally:
            self._event_listener_task = None
        if self.client is not None:
            await self.client.async_reset_event_queue()

    async def _async_event_listener_loop(self) -> None:
        """Poll the live KEF event queue and trigger targeted refreshes."""
        assert self.client is not None
        timeout = max(1, int(min(self.update_interval.total_seconds(), 15)))
        while True:
            try:
                events = await self.client.async_poll_events(timeout=timeout)
                if events:
                    _LOGGER.debug("KEF event queue delivered %s event(s)", len(events))
                    await self.async_request_refresh()
            except asyncio.CancelledError:
                raise
            except KefError as err:
                _LOGGER.debug(
                    "KEF event queue unavailable, falling back to polling: %s",
                    err,
                )
                await self.client.async_reset_event_queue()
                if self.is_offline:
                    # Polling owns reconnection while offline; resume the queue
                    # as soon as a poll reaches the speaker again.
                    await self._online.wait()
                else:
                    await asyncio.sleep(5)
