"""Config-flow tests for KEF."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef.const import (
    AIRPLAY_ZEROCONF_TYPE,
    CONF_BACKEND,
    CONF_DEVICE_ID,
    CONF_TCP_PORT,
    DOMAIN,
)
from custom_components.kef.exceptions import KefAuthenticationRequiredError
from tests.conftest import TEST_DEVICE_INFO, TEST_HOST


class _FakeClient:
    """Fake client for config-flow tests."""

    async def async_identify(self):
        """Return canned device information."""
        return TEST_DEVICE_INFO


async def test_user_flow_creates_modern_entry(monkeypatch, hass) -> None:
    """Manual setup should create a config entry."""

    async def fake_create_client(
        host,
        session,
        *,
        backend=None,
        port=None,
        password=None,
        tcp_port=None,
    ):
        assert host == TEST_HOST
        assert password == ""
        return _FakeClient()

    monkeypatch.setattr(
        "custom_components.kef.config_flow.async_create_client",
        fake_create_client,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: TEST_HOST},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["title"] == "LSX II-04438c"
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: 80,
        CONF_TCP_PORT: 50001,
        CONF_BACKEND: "modern",
        CONF_DEVICE_ID: "kef-84:17:15:04:43:8c",
        CONF_PASSWORD: "",
    }


async def test_user_flow_stores_web_password(monkeypatch, hass) -> None:
    """Manual setup should persist the optional web UI password."""

    async def fake_create_client(
        host,
        session,
        *,
        backend=None,
        port=None,
        password=None,
        tcp_port=None,
    ):
        assert host == TEST_HOST
        assert password == "secret"
        return _FakeClient()

    monkeypatch.setattr(
        "custom_components.kef.config_flow.async_create_client",
        fake_create_client,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: TEST_HOST, CONF_PASSWORD: "secret"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PASSWORD] == "secret"


async def test_user_flow_surfaces_invalid_auth(monkeypatch, hass) -> None:
    """Auth failures should be shown as invalid credentials."""

    async def fake_create_client(
        host,
        session,
        *,
        backend=None,
        port=None,
        password=None,
        tcp_port=None,
    ):
        raise KefAuthenticationRequiredError("bad password")

    monkeypatch.setattr(
        "custom_components.kef.config_flow.async_create_client",
        fake_create_client,
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: TEST_HOST, CONF_PASSWORD: "wrong"},
    )

    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": "invalid_auth"}


async def test_zeroconf_confirm_provides_title_placeholder(monkeypatch, hass) -> None:
    """Discovered setup should provide the translated confirm placeholder."""

    discovery_info = ZeroconfServiceInfo(
        ip_address="192.0.2.11",
        ip_addresses=["192.0.2.11"],
        hostname="lsxii.local.",
        type=AIRPLAY_ZEROCONF_TYPE,
        name="Living Room LSX II._airplay._tcp.local.",
        port=7000,
        properties={
            "manufacturer": "KEF",
            "model": "LSX II",
            "serialNumber": "AA-BB-CC",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"title": "Living Room LSX II"}


async def test_zeroconf_confirm_accepts_web_password(monkeypatch, hass) -> None:
    """Discovered setup should let users enter a web UI password."""

    async def fake_create_client(
        host,
        session,
        *,
        backend=None,
        port=None,
        password=None,
        tcp_port=None,
    ):
        assert host == "192.0.2.11"
        assert password == "secret"
        return _FakeClient()

    monkeypatch.setattr(
        "custom_components.kef.config_flow.async_create_client",
        fake_create_client,
    )

    discovery_info = ZeroconfServiceInfo(
        ip_address="192.0.2.11",
        ip_addresses=["192.0.2.11"],
        hostname="lsxii.local.",
        type=AIRPLAY_ZEROCONF_TYPE,
        name="Living Room LSX II._airplay._tcp.local.",
        port=7000,
        properties={
            "manufacturer": "KEF",
            "model": "LSX II",
            "serialNumber": "AA-BB-CC",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "secret"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PASSWORD] == "secret"


async def test_reconfigure_updates_password_options(monkeypatch, hass) -> None:
    """Reconfigure should update options password when options already had one."""

    async def fake_create_client(
        host,
        session,
        *,
        backend=None,
        port=None,
        password=None,
        tcp_port=None,
    ):
        assert host == TEST_HOST
        assert password == "new-secret"
        return _FakeClient()

    monkeypatch.setattr(
        "custom_components.kef.config_flow.async_create_client",
        fake_create_client,
    )

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_DEVICE_INFO.unique_id,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: 80,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
            CONF_DEVICE_ID: TEST_DEVICE_INFO.unique_id,
            CONF_PASSWORD: "old-data-secret",
        },
        options={CONF_PASSWORD: "old-options-secret"},
        title=TEST_DEVICE_INFO.device_name,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
        data={CONF_HOST: TEST_HOST, CONF_PASSWORD: "new-secret"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert entry.data[CONF_PASSWORD] == "new-secret"
    assert entry.options[CONF_PASSWORD] == "new-secret"


async def test_zeroconf_updates_existing_entry_using_deviceid(hass) -> None:
    """Discovered speakers should match the configured MAC-based unique ID."""

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_DEVICE_INFO.unique_id,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: 80,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
            CONF_DEVICE_ID: TEST_DEVICE_INFO.unique_id,
        },
        title=TEST_DEVICE_INFO.device_name,
    )
    entry.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address="192.0.2.11",
        ip_addresses=["192.0.2.11"],
        hostname="lsxii.local.",
        type=AIRPLAY_ZEROCONF_TYPE,
        name="Living Room LSX II._airplay._tcp.local.",
        port=7000,
        properties={
            "manufacturer": "KEF",
            "model": "LSX II",
            "deviceid": "84:17:15:04:43:8C",
            "serialNumber": "AA-BB-CC",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.0.2.11"
