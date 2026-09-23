"""Config flow for KEF."""

from __future__ import annotations

import ipaddress
import logging
from typing import Any

import voluptuous as vol
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    SOURCE_ZEROCONF,
    ConfigFlow,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from .api import async_create_client
from .const import (
    AIRPLAY_ZEROCONF_TYPE,
    CONF_BACKEND,
    CONF_DEVICE_ID,
    CONF_DISCOVERY_ID,
    CONF_ENABLE_DIAGNOSTICS,
    CONF_SCAN_INTERVAL,
    CONF_TCP_PORT,
    DEFAULT_ENABLE_DIAGNOSTICS,
    DEFAULT_LEGACY_PORT,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    MAX_SCAN_INTERVAL_SECONDS,
    MIN_SCAN_INTERVAL_SECONDS,
)
from .exceptions import (
    KefAuthenticationRequiredError,
    KefError,
    KefUnsupportedDeviceError,
)
from .models import KefBackend

_LOGGER = logging.getLogger(__name__)


class KefConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a KEF config flow."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry):
        """Return the options flow."""
        return KefOptionsFlow()

    def __init__(self) -> None:
        """Initialize the flow."""
        self._host = ""
        self._password = ""
        self._title = "KEF"
        self._errors: dict[str, str] = {}
        self._entry_data: dict[str, Any] = {}
        self._entry_title = "KEF"
        self._discovery_id: str | None = None

    async def async_step_user(self, user_input: dict[str, Any] | None = None):
        """Handle manual setup."""
        self._errors = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._password = user_input.get(CONF_PASSWORD, "")
            if await self._async_validate_host():
                return self.async_create_entry(
                    title=self._entry_title,
                    data=self._entry_data,
                )

        return self.async_show_form(
            step_id="user",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST): str,
                    vol.Optional(CONF_PASSWORD, default=self._password): str,
                }
            ),
            errors=self._errors,
        )

    async def async_step_reconfigure(self, user_input: dict[str, Any] | None = None):
        """Handle reconfiguration."""
        self._errors = {}
        entry = self._get_reconfigure_entry()

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._password = user_input.get(
                CONF_PASSWORD,
                entry.options.get(CONF_PASSWORD, entry.data.get(CONF_PASSWORD, "")),
            )
            if await self._async_validate_host():
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=self._entry_data,
                    options={**entry.options, CONF_PASSWORD: self._password},
                )

        return self.async_show_form(
            step_id="reconfigure",
            data_schema=vol.Schema(
                {
                    vol.Required(CONF_HOST, default=entry.data[CONF_HOST]): str,
                    vol.Optional(
                        CONF_PASSWORD,
                        default=entry.options.get(
                            CONF_PASSWORD,
                            entry.data.get(CONF_PASSWORD, ""),
                        ),
                    ): str,
                }
            ),
            errors=self._errors,
        )

    async def async_step_reauth(self, entry_data: dict[str, Any]):
        """Handle a request to update KEF credentials."""
        entry = self._get_reauth_entry()
        self._host = entry.data[CONF_HOST]
        self._password = entry.options.get(
            CONF_PASSWORD,
            entry.data.get(CONF_PASSWORD, ""),
        )
        self._title = entry.title
        return await self.async_step_reauth_confirm()

    async def async_step_reauth_confirm(
        self,
        user_input: dict[str, Any] | None = None,
    ):
        """Confirm updated KEF credentials."""
        self._errors = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            self._host = entry.data[CONF_HOST]
            self._password = user_input.get(CONF_PASSWORD, "")
            if await self._async_validate_host():
                return self.async_update_reload_and_abort(
                    entry,
                    data_updates=self._entry_data,
                    options={**entry.options, CONF_PASSWORD: self._password},
                )

        return self.async_show_form(
            step_id="reauth_confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PASSWORD, default=self._password): str,
                }
            ),
            errors=self._errors,
            description_placeholders={"title": self._title},
            last_step=True,
        )

    async def async_step_zeroconf(self, discovery_info: ZeroconfServiceInfo):
        """Handle zeroconf discovery."""
        if discovery_info.type != AIRPLAY_ZEROCONF_TYPE:
            return self.async_abort(reason="unsupported")

        manufacturer = str(discovery_info.properties.get("manufacturer", ""))
        model = str(discovery_info.properties.get("model", ""))
        discovery_unique_id = self._discovery_unique_id(discovery_info)
        self._discovery_id = discovery_unique_id

        if "KEF" not in manufacturer and "LS" not in model:
            return self.async_abort(reason="unsupported")

        # Keep the advertised name so Home Assistant's mDNS resolver can try
        # both address families and follow address changes after setup.
        self._host = discovery_info.hostname.rstrip(".") or discovery_info.host
        self._title = discovery_info.name.removesuffix(f".{discovery_info.type}")

        legacy_host = self._legacy_ipv4_host(discovery_info)
        if discovery_unique_id:
            entries = self.hass.config_entries.async_entries(DOMAIN)
            existing = next(
                (
                    entry for entry in entries
                    if entry.unique_id == discovery_unique_id
                    or entry.data.get(CONF_DISCOVERY_ID) == discovery_unique_id
                ),
                None,
            )
            if existing is None and legacy_host is not None:
                # Older legacy entries only had an address-derived ID. Link
                # one while its saved address is still advertised, so later
                # address changes can use the persisted AirPlay identifier.
                matches = [
                    entry for entry in entries
                    if entry.data.get(CONF_BACKEND) == KefBackend.LEGACY.value
                    and entry.data.get(CONF_HOST)
                    in (*discovery_info.ip_addresses, legacy_host)
                ]
                if len(matches) == 1:
                    existing = matches[0]
            if existing is not None:
                updates = {CONF_HOST: self._host}
                if existing.data.get(CONF_BACKEND) == KefBackend.LEGACY.value:
                    if legacy_host is None:
                        await self.async_set_unique_id(existing.unique_id)
                        self._abort_if_unique_id_configured()
                    updates = {
                        CONF_HOST: legacy_host,
                        CONF_DISCOVERY_ID: discovery_unique_id,
                    }
                await self.async_set_unique_id(existing.unique_id)
                self._abort_if_unique_id_configured(updates=updates)
            await self.async_set_unique_id(discovery_unique_id)

        # AirPlay TXT records don't reliably carry a per-device name, so resolve
        # the speaker's real name via its local API for a usable discovery card.
        session = async_get_clientsession(self.hass)
        try:
            client = await async_create_client(
                self._host,
                session,
                password=self._password,
            )
            device = await client.async_identify()
        except KefAuthenticationRequiredError as err:
            _LOGGER.debug(
                "Could not resolve speaker identity for %s: %s",
                self._host,
                err,
            )
            device = None
        except KefError as err:
            _LOGGER.debug("Could not probe %s: %s", self._host, err)
            device = None
            if legacy_host is not None:
                try:
                    client = await async_create_client(
                        legacy_host,
                        session,
                        backend=KefBackend.LEGACY,
                        password=self._password,
                    )
                    device = await client.async_identify()
                except KefError as legacy_err:
                    _LOGGER.debug(
                        "Could not probe legacy KEF at %s: %s",
                        legacy_host,
                        legacy_err,
                    )

        if device is not None:
            if device.backend is KefBackend.LEGACY:
                if legacy_host is None:
                    return self.async_abort(reason="unsupported")
                self._host = legacy_host
            resolved_name = device.device_name.strip()
            resolved_model = device.model.strip()
            if resolved_name.casefold() != "kef":
                self._title = resolved_name
                if resolved_model.casefold() not in {"", "kef", "kef legacy"}:
                    self._title = f"{resolved_name} ({resolved_model})"

        self.context["title_placeholders"] = {"title": self._title}
        return await self.async_step_confirm()

    @staticmethod
    def _discovery_unique_id(discovery_info: ZeroconfServiceInfo) -> str | None:
        """Return the configured-entry unique ID for a zeroconf discovery."""
        device_id = str(discovery_info.properties.get("deviceid", "")).strip()
        if device_id:
            return f"kef-{device_id.lower()}"

        serial = str(discovery_info.properties.get("serialNumber", "")).strip()
        return serial or None

    @staticmethod
    def _legacy_ipv4_host(discovery_info: ZeroconfServiceInfo) -> str | None:
        """Pick an IPv4 address for the legacy client's IPv4-only socket."""
        for host in (*discovery_info.ip_addresses, discovery_info.host):
            try:
                if isinstance(ipaddress.ip_address(host), ipaddress.IPv4Address):
                    return host
            except ValueError:
                continue
        return None

    async def async_step_confirm(self, user_input: dict[str, Any] | None = None):
        """Confirm a discovered speaker."""
        self._errors = {}

        if user_input is not None:
            self._password = user_input.get(CONF_PASSWORD, "")
            if await self._async_validate_host():
                return self.async_create_entry(
                    title=self._entry_title,
                    data=self._entry_data,
                )

        return self.async_show_form(
            step_id="confirm",
            data_schema=vol.Schema(
                {
                    vol.Optional(CONF_PASSWORD, default=self._password): str,
                }
            ),
            errors=self._errors,
            description_placeholders={"title": self._title},
            last_step=True,
        )

    async def _async_validate_host(self) -> bool:
        """Validate a host and create entry data."""
        session = async_get_clientsession(self.hass)

        try:
            client = await async_create_client(
                self._host,
                session,
                password=self._password,
            )
            device = await client.async_identify()
        except KefAuthenticationRequiredError:
            self._errors["base"] = "invalid_auth"
            return None
        except KefUnsupportedDeviceError:
            self._errors["base"] = "unsupported"
            return None
        except KefError:
            self._errors["base"] = "cannot_connect"
            return None

        entry_unique_id = device.unique_id
        stored_device_id = device.unique_id
        if device.backend is KefBackend.LEGACY:
            if self.source == SOURCE_ZEROCONF and self._discovery_id:
                entry_unique_id = self._discovery_id
                stored_device_id = entry_unique_id
            elif self.source == SOURCE_RECONFIGURE:
                entry = self._get_reconfigure_entry()
                if entry.data.get(CONF_BACKEND) == KefBackend.LEGACY.value:
                    entry_unique_id = entry.unique_id or device.unique_id
                    stored_device_id = entry.data.get(CONF_DEVICE_ID, entry_unique_id)

        await self.async_set_unique_id(entry_unique_id)
        if self.source in {SOURCE_REAUTH, SOURCE_RECONFIGURE}:
            self._abort_if_unique_id_mismatch()
        else:
            self._abort_if_unique_id_configured(updates={CONF_HOST: self._host})

        self._entry_data = {
            CONF_HOST: self._host,
            CONF_PORT: device.port or DEFAULT_PORT,
            CONF_TCP_PORT: DEFAULT_LEGACY_PORT,
            CONF_BACKEND: device.backend.value,
            CONF_DEVICE_ID: stored_device_id,
            CONF_PASSWORD: self._password,
        }
        if device.backend is KefBackend.LEGACY and self._discovery_id:
            self._entry_data[CONF_DISCOVERY_ID] = self._discovery_id
        self._entry_title = device.device_name
        return True


class KefOptionsFlow(OptionsFlow):
    """Handle KEF options."""

    async def async_step_init(self, user_input: dict[str, Any] | None = None):
        """Manage the integration options."""
        if user_input is not None:
            return self.async_create_entry(title="", data=user_input)

        return self.async_show_form(
            step_id="init",
            data_schema=vol.Schema(
                {
                    vol.Optional(
                        CONF_PASSWORD,
                        default=self.config_entry.options.get(
                            CONF_PASSWORD,
                            self.config_entry.data.get(CONF_PASSWORD, ""),
                        ),
                    ): str,
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
                }
            ),
        )
