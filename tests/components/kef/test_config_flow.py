"""Config-flow tests for KEF."""

from __future__ import annotations

from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PORT
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo

from custom_components.kef.const import (
    AIRPLAY_ZEROCONF_TYPE,
    CONF_BACKEND,
    CONF_DEVICE_ID,
    CONF_TCP_PORT,
    DOMAIN,
)
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
        tcp_port=None,
    ):
        assert host == TEST_HOST
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

    assert result["type"] is config_entries.FlowResultType.CREATE_ENTRY
    assert result["title"] == "LSX II-04438c"
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: 80,
        CONF_TCP_PORT: 50001,
        CONF_BACKEND: "modern",
        CONF_DEVICE_ID: "kef-84:17:15:04:43:8c",
    }


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

    assert result["type"] is config_entries.FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert result["description_placeholders"] == {"title": "Living Room LSX II"}
