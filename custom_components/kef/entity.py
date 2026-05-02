"""Shared entity helpers for KEF."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import TypeVar

from homeassistant.exceptions import HomeAssistantError

from .const import AUTH_FAILURE_MESSAGE
from .coordinator import KefCoordinator
from .exceptions import KefAuthenticationRequiredError, KefError

_T = TypeVar("_T")


class KefEntity:
    """Mixin for KEF coordinator entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KefCoordinator) -> None:
        """Initialize the entity."""
        self.coordinator = coordinator

    async def async_call_kef(self, action: Callable[[], Awaitable[_T]]) -> _T:
        """Run a KEF client action and surface integration-friendly errors."""
        try:
            return await action()
        except KefAuthenticationRequiredError as err:
            self.coordinator.config_entry.async_start_reauth(self.coordinator.hass)
            raise HomeAssistantError(AUTH_FAILURE_MESSAGE) from err
        except KefError as err:
            raise HomeAssistantError(str(err)) from err

    @property
    def device_info(self):
        """Return device information."""
        device = self.coordinator.data.device
        return {
            "identifiers": {(self.coordinator.config_entry.domain, device.unique_id)},
            "name": device.device_name,
            "manufacturer": "KEF",
            "model": device.model,
            "model_id": device.model_code,
            "sw_version": device.firmware_version,
            "hw_version": device.hardware_version,
            "serial_number": device.serial_number or device.mac_address,
            "configuration_url": f"http://{device.host}:{device.port}",
        }
