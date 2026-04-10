"""Coordinator for KEF data updates."""

from __future__ import annotations

import asyncio
import logging
from datetime import timedelta

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .api import async_create_client
from .const import (
    CONF_BACKEND,
    CONF_SCAN_INTERVAL,
    CONF_TCP_PORT,
    DEFAULT_SCAN_INTERVAL_SECONDS,
)
from .exceptions import KefError
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
                tcp_port=self.config_entry.data.get(CONF_TCP_PORT),
            )

        try:
            return await self.client.async_refresh()
        except KefError as err:
            raise UpdateFailed(str(err)) from err

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
