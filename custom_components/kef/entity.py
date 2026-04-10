"""Shared entity helpers for KEF."""

from __future__ import annotations

from .coordinator import KefCoordinator


class KefEntity:
    """Mixin for KEF coordinator entities."""

    _attr_has_entity_name = True

    def __init__(self, coordinator: KefCoordinator) -> None:
        """Initialize the entity."""
        self.coordinator = coordinator

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
            "serial_number": device.mac_address,
            "configuration_url": f"http://{device.host}:{device.port}",
        }
