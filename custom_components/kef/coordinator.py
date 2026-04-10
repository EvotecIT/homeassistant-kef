"""Coordinator for KEF data updates."""

from __future__ import annotations

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
from .models import KefSnapshot

_LOGGER = logging.getLogger(__name__)

type KefConfigEntry = ConfigEntry["KefCoordinator"]


class KefCoordinator(DataUpdateCoordinator[KefSnapshot]):
    """Coordinate KEF API updates."""

    config_entry: KefConfigEntry

    def __init__(self, hass, entry: KefConfigEntry) -> None:
        """Initialize the coordinator."""
        self._session = async_get_clientsession(hass)
        self.client = None
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
