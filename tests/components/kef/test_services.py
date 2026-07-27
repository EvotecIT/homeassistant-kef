"""Service tests for KEF."""

from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.const import ATTR_ENTITY_ID, Platform
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef import (
    ATTR_FIRMWARE_FILE_PATH,
    SERVICE_INSTALL_FIRMWARE_FILE,
    _async_register_services,
)
from custom_components.kef.const import DOMAIN
from custom_components.kef.exceptions import KefAuthenticationRequiredError


async def test_install_firmware_file_service_uploads_to_update_entity(hass) -> None:
    """The firmware upload service should call the selected KEF coordinator."""
    config_entry = MockConfigEntry(domain=DOMAIN, title="KEF")
    config_entry.add_to_hass(hass)

    client = SimpleNamespace(async_upload_firmware_update=AsyncMock())
    coordinator = SimpleNamespace(
        client=client,
        async_request_refresh=AsyncMock(),
    )
    config_entry.runtime_data = coordinator

    registry = er.async_get(hass)
    entity_entry = registry.async_get_or_create(
        Platform.UPDATE,
        DOMAIN,
        "kef-02:00:00:00:00:01_firmware",
        config_entry=config_entry,
        suggested_object_id="kef_firmware",
    )

    _async_register_services(hass)

    await hass.services.async_call(
        DOMAIN,
        SERVICE_INSTALL_FIRMWARE_FILE,
        {
            ATTR_ENTITY_ID: entity_entry.entity_id,
            ATTR_FIRMWARE_FILE_PATH: "/config/firmware/LSXII_V30135.swu",
        },
        blocking=True,
    )

    client.async_upload_firmware_update.assert_awaited_once_with(
        "/config/firmware/LSXII_V30135.swu"
    )
    coordinator.async_request_refresh.assert_awaited_once_with()


async def test_install_firmware_file_auth_failure_starts_reauth(hass) -> None:
    """Firmware upload auth failures should trigger reauth cleanly."""
    config_entry = MockConfigEntry(domain=DOMAIN, title="KEF")
    config_entry.add_to_hass(hass)
    config_entry.async_start_reauth = Mock()

    client = SimpleNamespace(
        async_upload_firmware_update=AsyncMock(
            side_effect=KefAuthenticationRequiredError("password required")
        )
    )
    coordinator = SimpleNamespace(
        client=client,
        async_request_refresh=AsyncMock(),
    )
    config_entry.runtime_data = coordinator

    registry = er.async_get(hass)
    entity_entry = registry.async_get_or_create(
        Platform.UPDATE,
        DOMAIN,
        "kef-02:00:00:00:00:01_firmware",
        config_entry=config_entry,
        suggested_object_id="kef_firmware",
    )

    _async_register_services(hass)

    with pytest.raises(HomeAssistantError, match="valid web UI password"):
        await hass.services.async_call(
            DOMAIN,
            SERVICE_INSTALL_FIRMWARE_FILE,
            {
                ATTR_ENTITY_ID: entity_entry.entity_id,
                ATTR_FIRMWARE_FILE_PATH: "/config/firmware/LSXII_V30135.swu",
            },
            blocking=True,
        )

    config_entry.async_start_reauth.assert_called_once_with(hass)
    coordinator.async_request_refresh.assert_not_awaited()
