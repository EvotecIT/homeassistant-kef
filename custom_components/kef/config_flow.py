"""Config flow for KEF."""

from __future__ import annotations

from typing import Any

import voluptuous as vol
from homeassistant.config_entries import ConfigFlow, OptionsFlow
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import async_create_client
from .const import (
    AIRPLAY_ZEROCONF_TYPE,
    CONF_BACKEND,
    CONF_DEVICE_ID,
    CONF_ENABLE_DIAGNOSTICS,
    CONF_ENABLE_EQ_SENSORS,
    CONF_SCAN_INTERVAL,
    CONF_TCP_PORT,
    DEFAULT_ENABLE_DIAGNOSTICS,
    DEFAULT_ENABLE_EQ_SENSORS,
    DEFAULT_LEGACY_PORT,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    MAX_SCAN_INTERVAL_SECONDS,
    MIN_SCAN_INTERVAL_SECONDS,
)
from .exceptions import KefError, KefUnsupportedDeviceError


class KefConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a KEF config flow."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return KefOptionsFlow(config_entry)

    def __init__(self) -> None:
        """Initialize the flow."""
        self._host = ""
        self._title = "KEF"
        self._errors: dict[str, str] = {}
        self._entry_data: dict[str, Any] = {}

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle manual setup."""
        self._errors = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            result = await self._async_validate_host()
            if result is not None:
                return result

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema({vol.Required(CONF_HOST): str}),
            errors=self._errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Handle reconfiguration."""
        self._errors = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            result = await self._async_validate_host()
            if result is not None:
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=self._entry_data,
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str}
            ),
            errors=self._errors,
        )

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo):
        """Handle zeroconf discovery."""
        if discovery_info.type != AIRPLAY_ZEROCONF_TYPE:
            return self.async_abort(reason="unsupported")

        manufacturer = str(discovery_info.properties.get("manufacturer", ""))
        model = str(discovery_info.properties.get("model", ""))
        serial = str(discovery_info.properties.get("serialNumber", ""))

        if "KEF" not in manufacturer and "LS" not in model:
            return self.async_abort(reason="unsupported")

        self._host = discovery_info.host
        self._title = discovery_info.name.removesuffix(f".{discovery_info.type}")

        if serial:
            await self.async_set_unique_id(serial)
            self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        self.context["title_placeholders"] = {"title": self._title}
        return await self.async_step_confirm()

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None):
        """Confirm a discovered speaker."""
        self._errors = {}

        if user_input is not None:
            result = await self._async_validate_host()
            if result is not None:
                return result

        return self.async_show_form(
            step_id="confirm",
            errors=self._errors,
            description_placeholders={"title": self._title},
            last_step=True,
        )

    async def _async_validate_host(self):
        """Validate a host and create entry data."""
        session = async_get_clientsession(self.hass)

        try:
            client = await async_create_client(self._host, session)
            device = await client.async_identify()
        except KefUnsupportedDeviceError:
            self._errors["base"] = "unsupported"
            return None
        except KefError:
            self._errors["base"] = "cannot_connect"
            return None

        await self.async_set_unique_id(device.unique_id)
        self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        self._entry_data = {
            CONF_HOST: self._host,
            CONF_PORT: device.port or DEFAULT_PORT,
            CONF_TCP_PORT: DEFAULT_LEGACY_PORT,
            CONF_BACKEND: device.backend.value,
            CONF_DEVICE_ID: device.unique_id,
        }
        return self.async_create_entry(title=device.device_name, data=self._entry_data)


class KefOptionsFlow(OptionsFlow):
    """Handle KEF options."""

    def __init__(self, config_entry) -> None:
        """Initialize the options flow."""
        self.config_entry = config_entry

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage the integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_SCAN_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_SCAN_INTERVAL,
                            DEFAULT_SCAN_INTERVAL_SECONDS,
                        ),
                    ): vol.All(
                        vol.Coerce(int),
                        vol.Range(
                            min=MIN_SCAN_INTERVAL_SECONDS,
                            max=MAX_SCAN_INTERVAL_SECONDS,
                        ),
                    ),
                    vol.Optional(
                        CONF_ENABLE_DIAGNOSTICS,
                        default=self.config_entry.options.get(
                            CONF_ENABLE_DIAGNOSTICS,
                            DEFAULT_ENABLE_DIAGNOSTICS,
                        ),
                    ): bool,
                    vol.Optional(
                        CONF_ENABLE_EQ_SENSORS,
                        default=self.config_entry.options.get(
                            CONF_ENABLE_EQ_SENSORS,
                            DEFAULT_ENABLE_EQ_SENSORS,
                        ),
                    ): bool,
                }
            ),
        )
