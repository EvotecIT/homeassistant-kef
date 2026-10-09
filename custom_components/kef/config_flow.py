"""Config flow for KEF."""

from __future__ import annotations

import asyncio
import ipaddress
import logging
import socket
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import (
    SOURCE_REAUTH,
    SOURCE_RECONFIGURE,
    SOURCE_ZEROCONF,
    ConfigEntry,
    ConfigEntryState,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.selector import (
    NumberSelector,
    NumberSelectorConfig,
    NumberSelectorMode,
)

from .api import async_create_client
from .const import (
    AIRPLAY_ZEROCONF_TYPE,
    CONF_BACKEND,
    CONF_DEVICE_ID,
    CONF_DISCOVERY_ID,
    CONF_ENABLE_DIAGNOSTICS,
    CONF_OFFLINE_RETRY_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_TCP_PORT,
    DEFAULT_ENABLE_DIAGNOSTICS,
    DEFAULT_LEGACY_PORT,
    DEFAULT_OFFLINE_RETRY_INTERVAL_SECONDS,
    DEFAULT_PORT,
    DEFAULT_SCAN_INTERVAL_SECONDS,
    DOMAIN,
    MAX_OFFLINE_RETRY_INTERVAL_SECONDS,
    MAX_SCAN_INTERVAL_SECONDS,
    MIN_OFFLINE_RETRY_INTERVAL_SECONDS,
    MIN_SCAN_INTERVAL_SECONDS,
)
from .exceptions import (
    KefAuthenticationRequiredError,
    KefError,
    KefUnsupportedDeviceError,
)
from .models import KefBackend

_LOGGER = logging.getLogger(__name__)


if TYPE_CHECKING:
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

class KefConfigFlow(ConfigFlow, domain=DOMAIN):
    """Handle a KEF config flow."""

    VERSION = 1

    @staticmethod
    def async_get_options_flow(config_entry: ConfigEntry) -> KefOptionsFlow:
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
        self._discovery_ipv4_host: str | None = None

    async def async_step_user(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
        """Handle manual setup."""
        self._errors = {}

        if user_input is not None:
            self._host = user_input[CONF_HOST]
            self._password = user_input.get(CONF_PASSWORD, "")
            if await self._async_validate_host():
                if (
                    self._entry_data[CONF_BACKEND] == KefBackend.LEGACY.value
                    and await self._async_legacy_host_configured()
                ):
                    return self.async_abort(reason="already_configured")
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

    async def async_step_reconfigure(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
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
                return self._async_update_connection_and_abort(entry)

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

    async def async_step_reauth(self, entry_data: dict[str, Any]) -> ConfigFlowResult:
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
    ) -> ConfigFlowResult:
        """Confirm updated KEF credentials."""
        self._errors = {}
        entry = self._get_reauth_entry()

        if user_input is not None:
            self._host = entry.data[CONF_HOST]
            self._password = user_input.get(CONF_PASSWORD, "")
            if await self._async_validate_host():
                return self._async_update_connection_and_abort(entry)

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

    def _async_update_connection_and_abort(
        self, entry: ConfigEntry,
    ) -> ConfigFlowResult:
        """Persist a validated connection and reload through one owner."""
        changed = self.hass.config_entries.async_update_entry(
            entry,
            data={**entry.data, **self._entry_data},
            options={**entry.options, CONF_PASSWORD: self._password},
        )
        # A loaded entry's update listener owns changed-data reloads. Repairs
        # with unchanged data, or no registered listener, still need one reload.
        if not changed or not entry.update_listeners:
            self.hass.config_entries.async_schedule_reload(entry.entry_id)
        reason = (
            "reconfigure_successful"
            if self.source == SOURCE_RECONFIGURE
            else "reauth_successful"
        )
        return self.async_abort(reason=reason)

    async def async_step_zeroconf(
        self, discovery_info: ZeroconfServiceInfo,
    ) -> ConfigFlowResult:
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
        self._host = discovery_info.hostname.rstrip(".") or str(discovery_info.host)
        self._title = discovery_info.name.removesuffix(f".{discovery_info.type}")

        legacy_host = self._legacy_ipv4_host(discovery_info)
        self._discovery_ipv4_host = legacy_host
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
                # Link an old legacy entry only before it has an AirPlay ID.
                # An address may later be assigned to another speaker.
                advertised_hosts = {
                    str(host).rstrip(".").casefold()
                    for host in (*discovery_info.ip_addresses, legacy_host, self._host)
                }
                matches = [
                    entry for entry in entries
                    if entry.data.get(CONF_BACKEND) == KefBackend.LEGACY.value
                    and not entry.data.get(CONF_DISCOVERY_ID)
                    and str(entry.data.get(CONF_HOST, "")).rstrip(".").casefold()
                    in advertised_hosts
                ]
                if len(matches) == 1:
                    existing = matches[0]
            if existing is not None:
                updates = {CONF_HOST: self._host}
                if existing.data.get(CONF_BACKEND) == KefBackend.LEGACY.value:
                    if legacy_host is None:
                        await self.async_set_unique_id(existing.unique_id)
                        self._abort_if_unique_id_configured()
                    else:
                        updates = {
                            CONF_HOST: legacy_host,
                            CONF_DISCOVERY_ID: discovery_unique_id,
                        }
                if existing.state is ConfigEntryState.LOADED:
                    # The announcement means the speaker is reachable again;
                    # skip the rest of the offline retry wait.
                    existing.runtime_data.async_device_seen()
                await self.async_set_unique_id(existing.unique_id)
                self._abort_if_unique_id_configured(
                    updates=updates, reload_on_update=False
                )
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
            if isinstance(ipaddress.ip_address(host), ipaddress.IPv4Address):
                return str(host)
        return None

    @staticmethod
    async def _async_ipv4_addresses(host: str) -> set[str]:
        """Resolve the addresses an IPv4-only legacy socket can reach."""
        try:
            address = ipaddress.ip_address(host)
        except ValueError:
            try:
                results = await asyncio.get_running_loop().getaddrinfo(
                    host, None, family=socket.AF_INET
                )
            except OSError:
                return set()
            return {str(result[4][0]) for result in results}
        return {str(address)} if isinstance(address, ipaddress.IPv4Address) else set()

    async def _async_legacy_host_configured(self) -> bool:
        """Check a manually added legacy host against configured IPv4 aliases."""
        entries = [
            entry
            for entry in self.hass.config_entries.async_entries(DOMAIN)
            if entry.data.get(CONF_BACKEND) == KefBackend.LEGACY.value
        ]
        host = self._host.rstrip(".").casefold()
        addresses: set[str] | None = None
        for entry in entries:
            saved_host = str(entry.data.get(CONF_HOST, "")).rstrip(".").casefold()
            if host == saved_host:
                return True
            if addresses is None:
                addresses = await self._async_ipv4_addresses(self._host)
            if addresses and addresses & await self._async_ipv4_addresses(saved_host):
                return True
        return False

    async def async_step_confirm(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
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
            return False
        except KefError as err:
            if self.source == SOURCE_ZEROCONF and self._discovery_ipv4_host:
                try:
                    client = await async_create_client(
                        self._discovery_ipv4_host,
                        session,
                        backend=KefBackend.LEGACY,
                        password=self._password,
                    )
                    device = await client.async_identify()
                except KefError as legacy_err:
                    self._errors["base"] = (
                        "unsupported"
                        if isinstance(legacy_err, KefUnsupportedDeviceError)
                        else "cannot_connect"
                    )
                    return False
                self._host = self._discovery_ipv4_host
            else:
                self._errors["base"] = (
                    "unsupported"
                    if isinstance(err, KefUnsupportedDeviceError)
                    else "cannot_connect"
                )
                return False

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
            self._abort_if_unique_id_configured(
                updates={CONF_HOST: self._host}, reload_on_update=False
            )

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


def _seconds_slider(minimum: int, maximum: int, *, step: int) -> vol.All:
    """Return a seconds slider that stores a whole number."""
    return vol.All(
        NumberSelector(
            NumberSelectorConfig(
                min=minimum,
                max=maximum,
                step=step,
                mode=NumberSelectorMode.SLIDER,
                unit_of_measurement="s",
            )
        ),
        vol.Coerce(int),
    )


class KefOptionsFlow(OptionsFlow):
    """Handle KEF options."""

    async def async_step_init(
        self, user_input: dict[str, Any] | None = None,
    ) -> ConfigFlowResult:
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
                    ): _seconds_slider(
                        MIN_SCAN_INTERVAL_SECONDS, MAX_SCAN_INTERVAL_SECONDS, step=1
                    ),
                    vol.Optional(
                        CONF_OFFLINE_RETRY_INTERVAL,
                        default=self.config_entry.options.get(
                            CONF_OFFLINE_RETRY_INTERVAL,
                            DEFAULT_OFFLINE_RETRY_INTERVAL_SECONDS,
                        ),
                    ): _seconds_slider(
                        MIN_OFFLINE_RETRY_INTERVAL_SECONDS,
                        MAX_OFFLINE_RETRY_INTERVAL_SECONDS,
                        step=1,
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
