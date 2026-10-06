"""Failed setup and credential repair cannot replace a configured speaker."""

from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest
from homeassistant import config_entries
from homeassistant.const import CONF_HOST, CONF_PASSWORD
from homeassistant.data_entry_flow import FlowResultType
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef.const import CONF_BACKEND, CONF_DEVICE_ID, DOMAIN
from custom_components.kef.exceptions import (
    KefAuthenticationRequiredError,
    KefConnectionError,
    KefUnsupportedDeviceError,
)
from tests.conftest import TEST_DEVICE_INFO, TEST_HOST

try:
    from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
except ImportError:  # Minimum HA exposes the same discovery contract here.
    from homeassistant.components.zeroconf import ZeroconfServiceInfo


def discovery_info(*, service="_airplay._tcp.local.", manufacturer="KEF", ipv4=True):
    addresses = ["192.0.2.11"] if ipv4 else ["fd00::11"]
    return ZeroconfServiceInfo(
        ip_address=addresses[0],
        ip_addresses=addresses,
        hostname="speaker.local.",
        type=service,
        name=f"Speaker.{service}",
        port=7000,
        properties={"manufacturer": manufacturer, "deviceid": "02:00:00:00:00:11"},
    )


@pytest.mark.parametrize("source", ["user", "reauth", "reconfigure"])
@pytest.mark.parametrize(
    ("failure", "error"),
    [
        (KefAuthenticationRequiredError, "invalid_auth"),
        (KefConnectionError, "cannot_connect"),
        (KefUnsupportedDeviceError, "unsupported"),
    ],
)
async def test_failed_validation_preserves_credentials(
    hass, monkeypatch, source, failure, error
):
    original = {
        CONF_HOST: TEST_HOST,
        CONF_PASSWORD: "saved-password",
        CONF_BACKEND: "modern",
        CONF_DEVICE_ID: TEST_DEVICE_INFO.unique_id,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_DEVICE_INFO.unique_id,
        data=original,
        options={CONF_PASSWORD: "saved-option-password"},
    )
    if source != "user":
        entry.add_to_hass(hass)
    reload = AsyncMock()
    monkeypatch.setattr(hass.config_entries, "async_reload", reload)
    monkeypatch.setattr(
        "custom_components.kef.config_flow.async_create_client",
        AsyncMock(side_effect=failure("unavailable")),
    )
    context = {"source": source}
    if source != "user":
        context["entry_id"] = entry.entry_id
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context=context,
        data=original if source == "reauth" else None,
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "unverified-password"}
        if source == "reauth"
        else {
            CONF_HOST: TEST_HOST,
            CONF_PASSWORD: "unverified-password",
        },
    )
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert entry.data == original
    assert entry.options == {CONF_PASSWORD: "saved-option-password"}
    reload.assert_not_awaited()
    if source == "user":
        assert not hass.config_entries.async_entries(DOMAIN)


@pytest.mark.parametrize("source", ["reauth", "reconfigure"])
async def test_wrong_speaker_cannot_replace_existing_entry(hass, monkeypatch, source):
    original = {
        CONF_HOST: TEST_HOST,
        CONF_PASSWORD: "saved-password",
        CONF_BACKEND: "modern",
        CONF_DEVICE_ID: TEST_DEVICE_INFO.unique_id,
    }
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_DEVICE_INFO.unique_id,
        data=original,
        options={CONF_PASSWORD: "saved-option-password"},
    )
    entry.add_to_hass(hass)
    reload = AsyncMock()
    monkeypatch.setattr(hass.config_entries, "async_reload", reload)
    device = replace(TEST_DEVICE_INFO, unique_id="different-speaker")
    monkeypatch.setattr(
        "custom_components.kef.config_flow.async_create_client",
        AsyncMock(
            return_value=SimpleNamespace(
                async_identify=AsyncMock(return_value=device),
            )
        ),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": source, "entry_id": entry.entry_id},
        data=original if source == config_entries.SOURCE_REAUTH else None,
    )
    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "other-password"}
        if source == "reauth"
        else {
            CONF_HOST: "192.0.2.99",
            CONF_PASSWORD: "other-password",
        },
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unique_id_mismatch"
    assert entry.unique_id == TEST_DEVICE_INFO.unique_id
    assert entry.data == original
    assert entry.options == {CONF_PASSWORD: "saved-option-password"}
    reload.assert_not_awaited()


@pytest.mark.parametrize(
    ("host", "dns_result", "reason"),
    [
        ("192.0.2.22", None, None),
        ("speaker.local", "192.0.2.11", "already_configured"),
        ("speaker.local", "192.0.2.22", None),
        ("speaker.local", OSError("DNS unavailable"), None),
    ],
)
async def test_legacy_manual_setup_checks_ipv4_aliases_at_dns_boundary(
    hass,
    monkeypatch,
    host,
    dns_result,
    reason,
):
    import asyncio
    import socket

    from custom_components.kef.models import KefBackend

    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="existing-legacy-speaker",
        data={CONF_HOST: "192.0.2.11", CONF_BACKEND: "legacy"},
    )
    entry.add_to_hass(hass)
    device = replace(
        TEST_DEVICE_INFO,
        backend=KefBackend.LEGACY,
        unique_id="new-legacy-speaker",
        host=host,
    )
    monkeypatch.setattr(
        "custom_components.kef.config_flow.async_create_client",
        AsyncMock(
            return_value=SimpleNamespace(
                async_identify=AsyncMock(return_value=device),
            )
        ),
    )
    resolver = AsyncMock()
    if isinstance(dns_result, Exception):
        resolver.side_effect = dns_result
    else:
        resolver.return_value = [
            (socket.AF_INET, socket.SOCK_STREAM, 6, "", (dns_result, 0))
        ]
    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", resolver)
    monkeypatch.setattr(
        "custom_components.kef.async_setup_entry",
        AsyncMock(return_value=True),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "user"},
        data={CONF_HOST: host},
    )
    if reason:
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == reason
    else:
        assert result["type"] is FlowResultType.CREATE_ENTRY
        assert result["data"][CONF_HOST] == host
    if dns_result is None:
        resolver.assert_not_awaited()
    else:
        resolver.assert_awaited_once_with(host, None, family=socket.AF_INET)
    assert entry.data == {CONF_HOST: "192.0.2.11", CONF_BACKEND: "legacy"}


@pytest.mark.parametrize(
    ("service", "manufacturer"),
    [
        ("_unrelated._tcp.local.", "KEF"),
        ("_airplay._tcp.local.", "Other manufacturer"),
    ],
)
async def test_unrelated_discovery_never_probes_device(
    hass, monkeypatch, service, manufacturer
):
    probe = AsyncMock()
    monkeypatch.setattr("custom_components.kef.config_flow.async_create_client", probe)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=discovery_info(service=service, manufacturer=manufacturer),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "unsupported"
    probe.assert_not_awaited()


async def test_ipv6_only_rediscovery_preserves_legacy_ipv4_host(hass, monkeypatch):
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="kef-02:00:00:00:00:11",
        data={CONF_HOST: "192.0.2.11", CONF_BACKEND: "legacy"},
    )
    entry.add_to_hass(hass)
    probe = AsyncMock()
    monkeypatch.setattr("custom_components.kef.config_flow.async_create_client", probe)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=discovery_info(ipv4=False),
    )
    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data == {CONF_HOST: "192.0.2.11", CONF_BACKEND: "legacy"}
    probe.assert_not_awaited()


@pytest.mark.parametrize(
    ("failure", "error"),
    [
        (KefConnectionError, "cannot_connect"),
        (KefUnsupportedDeviceError, "unsupported"),
    ],
)
async def test_discovery_confirmation_keeps_form_after_both_transports_fail(
    hass,
    monkeypatch,
    failure,
    error,
):
    probe = AsyncMock(side_effect=failure("offline"))
    monkeypatch.setattr("custom_components.kef.config_flow.async_create_client", probe)
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": "zeroconf"},
        data=discovery_info(),
    )
    assert result["type"] is FlowResultType.FORM
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.FORM
    assert result["errors"] == {"base": error}
    assert not hass.config_entries.async_entries(DOMAIN)
    assert [call.args[0] for call in probe.await_args_list] == [
        "speaker.local",
        "192.0.2.11",
        "speaker.local",
        "192.0.2.11",
    ]


@pytest.mark.parametrize("legacy_identified", [False, True])
async def test_ipv6_only_discovery_does_not_use_legacy_address(
    hass, monkeypatch, legacy_identified
):
    """Discovery must not configure an IPv4-only client without an IPv4 address."""
    from custom_components.kef.models import KefBackend

    probe = AsyncMock()
    if legacy_identified:
        probe.return_value = SimpleNamespace(
            async_identify=AsyncMock(return_value=replace(
                TEST_DEVICE_INFO, backend=KefBackend.LEGACY,
            )),
        )
    else:
        probe.side_effect = KefConnectionError("offline")
    monkeypatch.setattr("custom_components.kef.config_flow.async_create_client", probe)

    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=discovery_info(ipv4=False),
    )

    if legacy_identified:
        assert result["type"] is FlowResultType.ABORT
        assert result["reason"] == "unsupported"
    else:
        assert result["type"] is FlowResultType.FORM
        assert result["step_id"] == "confirm"
    assert probe.await_count == 1
    assert probe.await_args.args[0] == "speaker.local"
    assert not hass.config_entries.async_entries(DOMAIN)


async def test_discovery_without_advertised_identity_uses_probed_speaker(
    hass, monkeypatch,
):
    """A sparse mDNS advertisement uses the identity returned by the device API."""
    discovery = discovery_info()
    discovery.properties.pop("deviceid")
    device = replace(TEST_DEVICE_INFO, device_name="KEF")
    probe = AsyncMock(return_value=SimpleNamespace(
        async_identify=AsyncMock(return_value=device),
    ))
    monkeypatch.setattr("custom_components.kef.config_flow.async_create_client", probe)
    monkeypatch.setattr(
        "custom_components.kef.async_setup_entry", AsyncMock(return_value=True),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN, context={"source": "zeroconf"}, data=discovery,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_DEVICE_ID] == TEST_DEVICE_INFO.unique_id
    assert result["result"].unique_id == TEST_DEVICE_INFO.unique_id
    assert result["data"][CONF_HOST] == "speaker.local"
