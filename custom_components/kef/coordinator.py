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
    CONF_SCAN_INTERVAL,
    CONF_TCP_PORT,
    DEFAULT_SCAN_INTERVAL_SECONDS,
)
from .exceptions import KefAuthenticationRequiredError, KefError
from .models import KefBackend, KefSnapshot

_LOGGER = logging.getLogger(__name__)

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
        super().__init__(
            hass,
            _LOGGER,
            config_entry=entry,
            name="kef",
            update_interval=timedelta(
                seconds=entry.options.get(
                    CONF_SCAN_INTERVAL,
                    DEFAULT_SCAN_INTERVAL_SECONDS,
                )
            ),
        )

    async def _async_update_data(self) -> KefSnapshot:
        """Fetch data from the device."""
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
        try:
            snapshot = await self.client.async_refresh()
        except KefAuthenticationRequiredError as err:
            raise ConfigEntryAuthFailed(str(err)) from err
        except KefError as err:
            raise UpdateFailed(str(err)) from err
        self.last_device_update_at = dt_util.utcnow()
        return self._merge_local_changes(snapshot, started_at)

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
                await asyncio.sleep(5)
