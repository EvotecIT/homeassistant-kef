"""Shared entity helpers for KEF."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import replace
from typing import Any, TypeVar

from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.device_registry import DeviceInfo
from yarl import URL

from .api import BaseKefClient
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

    @property
    def client(self) -> BaseKefClient:
        """Return the initialized client for an entity action."""
        client = self.coordinator.client
        if client is None:
            raise HomeAssistantError("KEF speaker is not initialized")
        return client

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
    def device_info(self) -> DeviceInfo:
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
            "configuration_url": str(
                URL.build(scheme="http", host=device.host.strip("[]"), port=device.port)
            ) if device.host else None,
        }


def apply_eq_profile_change(coordinator: KefCoordinator, **changes: Any) -> None:
    """Publish an eq_profile field change a write just made itself.

    Mirrors coordinator.async_apply_local_change for fields nested inside
    eq_profile rather than top-level KefSnapshot fields, so a write shows
    up immediately instead of flickering back to the stale value until
    the next poll (or the in-flight refresh, which can race the speaker
    not having applied the change yet).
    """
    eq_profile = coordinator.data.eq_profile
    if eq_profile is None:
        return
    coordinator.async_apply_local_change(eq_profile=replace(eq_profile, **changes))
