"""Config-flow tests for KEF."""

from __future__ import annotations

from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant import config_entries
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_HOST, CONF_PASSWORD, CONF_PORT
from homeassistant.data_entry_flow import FlowResultType, InvalidData
from homeassistant.helpers.service_info.zeroconf import ZeroconfServiceInfo
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef.const import (
    AIRPLAY_ZEROCONF_TYPE,
    CONF_BACKEND,
    CONF_DEVICE_ID,
    CONF_DISCOVERY_ID,
    CONF_ENABLE_DIAGNOSTICS,
    CONF_OFFLINE_RETRY_INTERVAL,
    CONF_SCAN_INTERVAL,
    CONF_TCP_PORT,
    DOMAIN,
)
from custom_components.kef.exceptions import (
    KefAuthenticationRequiredError,
    KefConnectionError,
    KefUnsupportedDeviceError,
)
from custom_components.kef.models import KefBackend, KefDeviceInfo
from tests.conftest import TEST_DEVICE_INFO, TEST_HOST


@pytest.fixture(autouse=True)
def mock_entry_lifecycle(monkeypatch) -> None:
    """Keep config-flow tests focused on flow behavior across HA versions."""
    monkeypatch.setattr(
        "custom_components.kef.async_setup_entry",
        AsyncMock(return_value=True),
    )
    monkeypatch.setattr(
        "custom_components.kef.async_unload_entry",
        AsyncMock(return_value=True),
    )


class _FakeClient:
    """Fake client for config-flow tests."""

    def __init__(self, device: KefDeviceInfo = TEST_DEVICE_INFO) -> None:
        """Initialize the fake client."""
        self.device = device

    async def async_identify(self):
        """Return canned device information."""
        return self.device


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
    assert result["title"] == "LSX II-Test"
    assert result["data"] == {
        CONF_HOST: TEST_HOST,
        CONF_PORT: 80,
        CONF_TCP_PORT: 50001,
        CONF_BACKEND: "modern",
        CONF_DEVICE_ID: "kef-02:00:00:00:00:01",
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


async def test_user_flow_does_not_duplicate_discovered_legacy_host(
    monkeypatch, hass
) -> None:
    """Manual setup should recognize a legacy entry created by discovery."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="kef-02:00:00:00:00:02",
        data={
            CONF_HOST: "192.0.2.11",
            CONF_BACKEND: KefBackend.LEGACY.value,
            CONF_DEVICE_ID: "kef-02:00:00:00:00:02",
            CONF_DISCOVERY_ID: "kef-02:00:00:00:00:02",
        },
    )
    entry.add_to_hass(hass)
    legacy_device = KefDeviceInfo(
        backend=KefBackend.LEGACY,
        unique_id="kef-legacy-192.0.2.11",
        device_name="KEF",
        model="KEF Legacy",
        host="192.0.2.11",
        port=50001,
    )

    async def fake_create_client(host, session, **kwargs):
        assert host == "192.0.2.11"
        return _FakeClient(legacy_device)

    monkeypatch.setattr(
        "custom_components.kef.config_flow.async_create_client",
        fake_create_client,
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "192.0.2.11"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_user_flow_does_not_duplicate_discovered_legacy_ipv4_alias(
    monkeypatch, hass
) -> None:
    """A manually entered mDNS alias is the already discovered IPv4 speaker."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="kef-02:00:00:00:00:02",
        data={
            CONF_HOST: "192.0.2.11",
            CONF_BACKEND: KefBackend.LEGACY.value,
            CONF_DEVICE_ID: "kef-02:00:00:00:00:02",
            CONF_DISCOVERY_ID: "kef-02:00:00:00:00:02",
        },
    )
    entry.add_to_hass(hass)
    legacy_device = KefDeviceInfo(
        backend=KefBackend.LEGACY,
        unique_id="kef-legacy-lsx.local",
        device_name="KEF",
        model="KEF Legacy",
        host="lsx.local",
        port=50001,
    )

    async def fake_create_client(host, session, **kwargs):
        assert host == "lsx.local"
        return _FakeClient(legacy_device)

    async def fake_ipv4_addresses(host):
        return {"192.0.2.11"}

    monkeypatch.setattr(
        "custom_components.kef.config_flow.async_create_client",
        fake_create_client,
    )
    monkeypatch.setattr(
        "custom_components.kef.config_flow.KefConfigFlow._async_ipv4_addresses",
        staticmethod(fake_ipv4_addresses),
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_USER},
        data={CONF_HOST: "lsx.local"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_options_flow_saves_settings(hass) -> None:
    """Options should open and persist through Home Assistant's flow manager."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_DEVICE_INFO.unique_id,
        data={
            CONF_HOST: TEST_HOST,
            CONF_PORT: 80,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
            CONF_DEVICE_ID: TEST_DEVICE_INFO.unique_id,
            CONF_PASSWORD: "",
        },
        title=TEST_DEVICE_INFO.device_name,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "init"

    result = await hass.config_entries.options.async_configure(
        result["flow_id"],
        {
            CONF_PASSWORD: "new-secret",
            CONF_SCAN_INTERVAL: 45.0,
            CONF_OFFLINE_RETRY_INTERVAL: 300.0,
            CONF_ENABLE_DIAGNOSTICS: True,
        },
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options == {
        CONF_PASSWORD: "new-secret",
        CONF_SCAN_INTERVAL: 45,
        CONF_OFFLINE_RETRY_INTERVAL: 300,
        CONF_ENABLE_DIAGNOSTICS: True,
    }
    # Slider selectors return floats; the coordinator expects whole seconds.
    assert type(entry.options[CONF_SCAN_INTERVAL]) is int
    assert type(entry.options[CONF_OFFLINE_RETRY_INTERVAL]) is int


async def test_options_flow_defaults_the_offline_retry_interval(hass) -> None:
    """Saving options without touching the new field stores the 60s default."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_DEVICE_INFO.unique_id,
        data={CONF_HOST: TEST_HOST, CONF_BACKEND: "modern"},
        title=TEST_DEVICE_INFO.device_name,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    result = await hass.config_entries.options.async_configure(
        result["flow_id"], {}
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert entry.options[CONF_OFFLINE_RETRY_INTERVAL] == 60


@pytest.mark.parametrize("interval", [29, 601])
async def test_options_flow_rejects_out_of_range_offline_retry(hass, interval) -> None:
    """The offline retry interval is limited to 30 to 600 seconds."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_DEVICE_INFO.unique_id,
        data={CONF_HOST: TEST_HOST, CONF_BACKEND: "modern"},
        title=TEST_DEVICE_INFO.device_name,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.options.async_init(entry.entry_id)
    with pytest.raises(InvalidData):
        await hass.config_entries.options.async_configure(
            result["flow_id"], {CONF_OFFLINE_RETRY_INTERVAL: interval}
        )


async def test_zeroconf_confirm_provides_title_placeholder(monkeypatch, hass) -> None:
    """Discovered setup should provide the translated confirm placeholder."""

    async def fake_create_client(
        host,
        session,
        *,
        backend=None,
        port=None,
        password=None,
        tcp_port=None,
    ):
        assert host == "lsxii.local"
        assert password == ""
        return _FakeClient()

    monkeypatch.setattr(
        "custom_components.kef.config_flow.async_create_client",
        fake_create_client,
    )

    discovery_info = ZeroconfServiceInfo(
        ip_address="192.0.2.11",
        ip_addresses=["192.0.2.11", "fd42:241::228"],
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
    assert result["description_placeholders"] == {"title": "LSX II-Test (LSXII)"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "lsxii.local"


async def test_zeroconf_preserves_title_for_generic_legacy_identity(
    monkeypatch,
    hass,
) -> None:
    """A generic legacy API identity should not replace the AirPlay name."""
    legacy_device = KefDeviceInfo(
        backend=KefBackend.LEGACY,
        unique_id="kef-legacy-192.0.2.11",
        device_name="KEF",
        model="KEF Legacy",
        host="192.0.2.11",
        port=50001,
    )

    async def fake_create_client(
        host,
        session,
        *,
        backend=None,
        port=None,
        password=None,
        tcp_port=None,
    ):
        if host == "lsx.local":
            raise KefUnsupportedDeviceError("legacy socket cannot resolve mDNS")
        assert host == "192.0.2.11"
        assert password == ""
        return _FakeClient(legacy_device)

    monkeypatch.setattr(
        "custom_components.kef.config_flow.async_create_client",
        fake_create_client,
    )

    discovery_info = ZeroconfServiceInfo(
        ip_address="fd42:241::228",
        ip_addresses=["fd42:241::228", "192.0.2.11"],
        hostname="lsx.local.",
        type=AIRPLAY_ZEROCONF_TYPE,
        name="Living Room LSX._airplay._tcp.local.",
        port=7000,
        properties={
            "manufacturer": "KEF",
            "model": "LSX",
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
    assert result["description_placeholders"] == {"title": "Living Room LSX"}

    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.0.2.11"
    assert result["data"][CONF_DEVICE_ID] == "AA-BB-CC"
    assert result["data"][CONF_DISCOVERY_ID] == "AA-BB-CC"


async def test_zeroconf_confirm_retries_ipv4_after_legacy_speaker_wakes(
    monkeypatch,
    hass,
) -> None:
    """Confirmation can recover when the legacy socket was offline at discovery."""
    legacy_device = KefDeviceInfo(
        backend=KefBackend.LEGACY,
        unique_id="kef-legacy-192.0.2.11",
        device_name="KEF",
        model="KEF Legacy",
        host="192.0.2.11",
        port=50001,
    )
    online = False

    async def fake_create_client(host, session, *, backend=None, **kwargs):
        if host == "lsx.local":
            raise KefUnsupportedDeviceError("legacy socket cannot resolve mDNS")
        assert host == "192.0.2.11"
        assert backend is KefBackend.LEGACY
        if not online:
            raise KefConnectionError("speaker in standby")
        return _FakeClient(legacy_device)

    monkeypatch.setattr(
        "custom_components.kef.config_flow.async_create_client",
        fake_create_client,
    )
    discovery_info = ZeroconfServiceInfo(
        ip_address="fd42:241::228",
        ip_addresses=["fd42:241::228", "192.0.2.11"],
        hostname="lsx.local.",
        type=AIRPLAY_ZEROCONF_TYPE,
        name="Living Room LSX._airplay._tcp.local.",
        port=7000,
        properties={"manufacturer": "KEF", "model": "LSX", "serialNumber": "AA-BB-CC"},
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )
    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"

    online = True
    result = await hass.config_entries.flow.async_configure(result["flow_id"], {})
    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_HOST] == "192.0.2.11"
    assert result["data"][CONF_DEVICE_ID] == "AA-BB-CC"


async def test_zeroconf_confirm_accepts_web_password(monkeypatch, hass) -> None:
    """Discovered setup should let users enter a web UI password."""

    passwords: list[str | None] = []

    async def fake_create_client(
        host,
        session,
        *,
        backend=None,
        port=None,
        password=None,
        tcp_port=None,
    ):
        assert host == "lsxii.local"
        passwords.append(password)
        if password == "":
            raise KefAuthenticationRequiredError("password required")
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

    assert result["type"] is FlowResultType.FORM
    assert result["description_placeholders"] == {"title": "Living Room LSX II"}

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "secret"},
    )

    assert result["type"] is FlowResultType.CREATE_ENTRY
    assert result["data"][CONF_PASSWORD] == "secret"
    assert passwords == ["", "secret"]


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


async def test_reconfigure_legacy_keeps_entity_identity(monkeypatch, hass) -> None:
    """Explicitly changing an old legacy IP must retain its entity IDs."""
    old_id = "kef-legacy-192.0.2.11"
    legacy_device = KefDeviceInfo(
        backend=KefBackend.LEGACY,
        unique_id="kef-legacy-192.0.2.12",
        device_name="KEF",
        model="KEF Legacy",
        host="192.0.2.12",
        port=50001,
    )

    async def fake_create_client(host, session, **kwargs):
        assert host == "192.0.2.12"
        return _FakeClient(legacy_device)

    monkeypatch.setattr(
        "custom_components.kef.config_flow.async_create_client",
        fake_create_client,
    )
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=old_id,
        data={
            CONF_HOST: "192.0.2.11",
            CONF_PORT: 50001,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: KefBackend.LEGACY.value,
            CONF_DEVICE_ID: old_id,
        },
        title="KEF",
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_RECONFIGURE,
            "entry_id": entry.entry_id,
        },
        data={CONF_HOST: "192.0.2.12"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert entry.data[CONF_HOST] == "192.0.2.12"
    assert entry.data[CONF_DEVICE_ID] == old_id
    assert entry.unique_id == old_id


async def test_reauth_updates_password_options(monkeypatch, hass) -> None:
    """Reauth should prompt for and store a replacement web UI password."""

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
        assert password == "fixed-secret"
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
            CONF_PASSWORD: "old-secret",
        },
        options={CONF_PASSWORD: "old-secret"},
        title=TEST_DEVICE_INFO.device_name,
    )
    entry.add_to_hass(hass)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={
            "source": config_entries.SOURCE_REAUTH,
            "entry_id": entry.entry_id,
        },
        data=entry.data,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "reauth_confirm"

    result = await hass.config_entries.flow.async_configure(
        result["flow_id"],
        {CONF_PASSWORD: "fixed-secret"},
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "reauth_successful"
    assert entry.data[CONF_PASSWORD] == "fixed-secret"
    assert entry.options[CONF_PASSWORD] == "fixed-secret"


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
            "deviceid": "02:00:00:00:00:01",
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
    assert entry.data[CONF_HOST] == "lsxii.local"


def _loaded_zeroconf_entry(hass, state: ConfigEntryState) -> MockConfigEntry:
    """Add a configured speaker whose discovery host already matches."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id=TEST_DEVICE_INFO.unique_id,
        data={
            CONF_HOST: "lsxii.local",
            CONF_PORT: 80,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: "modern",
            CONF_DEVICE_ID: TEST_DEVICE_INFO.unique_id,
        },
        title=TEST_DEVICE_INFO.device_name,
    )
    entry.add_to_hass(hass)
    entry.mock_state(hass, state)
    return entry


def _lsxii_announcement() -> ZeroconfServiceInfo:
    return ZeroconfServiceInfo(
        ip_address="192.0.2.11",
        ip_addresses=["192.0.2.11"],
        hostname="lsxii.local.",
        type=AIRPLAY_ZEROCONF_TYPE,
        name="Living Room LSX II._airplay._tcp.local.",
        port=7000,
        properties={
            "manufacturer": "KEF",
            "model": "LSX II",
            "deviceid": "02:00:00:00:00:01",
            "serialNumber": "AA-BB-CC",
        },
    )


async def test_zeroconf_tells_a_loaded_entry_its_speaker_was_seen(hass) -> None:
    """An announcement from a set-up speaker lets an offline one reconnect now."""
    entry = _loaded_zeroconf_entry(hass, ConfigEntryState.LOADED)
    entry.runtime_data = Mock()

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_lsxii_announcement(),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    entry.runtime_data.async_device_seen.assert_called_once_with()


async def test_zeroconf_skips_device_seen_for_an_entry_that_is_not_loaded(
    hass,
) -> None:
    """An entry still retrying setup has no coordinator to notify."""
    _loaded_zeroconf_entry(hass, ConfigEntryState.SETUP_RETRY)

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=_lsxii_announcement(),
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"


async def test_zeroconf_legacy_entry_uses_ipv4_when_ipv6_is_preferred(hass) -> None:
    """Rediscovery must not save IPv6 for an IPv4-only legacy socket."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="kef-legacy-192.0.2.11",
        data={
            CONF_HOST: "192.0.2.11",
            CONF_PORT: 80,
            CONF_TCP_PORT: 50001,
            CONF_BACKEND: KefBackend.LEGACY.value,
            CONF_DEVICE_ID: "kef-legacy-192.0.2.11",
        },
        title="Living Room LSX",
    )
    entry.add_to_hass(hass)

    discovery_info = ZeroconfServiceInfo(
        ip_address="fd42:241::228",
        ip_addresses=["fd42:241::228", "192.0.2.11"],
        hostname="lsx.local.",
        type=AIRPLAY_ZEROCONF_TYPE,
        name="Living Room LSX._airplay._tcp.local.",
        port=7000,
        properties={
            "manufacturer": "KEF",
            "model": "LSX",
            "deviceid": "02:00:00:00:00:02",
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
    assert entry.data[CONF_DISCOVERY_ID] == "kef-02:00:00:00:00:02"

    # A later address change matches the persisted AirPlay ID while keeping
    # the existing entity's address-derived identity stable.
    discovery_info = ZeroconfServiceInfo(
        ip_address="fd42:241::229",
        ip_addresses=["fd42:241::229", "192.0.2.12"],
        hostname="lsx.local.",
        type=AIRPLAY_ZEROCONF_TYPE,
        name="Living Room LSX._airplay._tcp.local.",
        port=7000,
        properties={
            "manufacturer": "KEF",
            "model": "LSX",
            "deviceid": "02:00:00:00:00:02",
        },
    )
    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.ABORT
    assert result["reason"] == "already_configured"
    assert entry.data[CONF_HOST] == "192.0.2.12"
    assert entry.data[CONF_DEVICE_ID] == "kef-legacy-192.0.2.11"


async def test_zeroconf_does_not_reassign_legacy_entry_with_different_airplay_id(
    monkeypatch, hass
) -> None:
    """An address reused by another speaker must not transfer an entry."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="kef-legacy-192.0.2.11",
        data={
            CONF_HOST: "192.0.2.11",
            CONF_BACKEND: KefBackend.LEGACY.value,
            CONF_DEVICE_ID: "kef-legacy-192.0.2.11",
            CONF_DISCOVERY_ID: "kef-02:00:00:00:00:02",
        },
    )
    entry.add_to_hass(hass)

    async def fake_create_client(host, session, **kwargs):
        raise KefConnectionError("speaker asleep")

    monkeypatch.setattr(
        "custom_components.kef.config_flow.async_create_client",
        fake_create_client,
    )
    discovery_info = ZeroconfServiceInfo(
        ip_address="192.0.2.11",
        ip_addresses=["192.0.2.11"],
        hostname="other-lsx.local.",
        type=AIRPLAY_ZEROCONF_TYPE,
        name="Other LSX._airplay._tcp.local.",
        port=7000,
        properties={
            "manufacturer": "KEF",
            "model": "LSX",
            "deviceid": "02:00:00:00:00:03",
        },
    )

    result = await hass.config_entries.flow.async_init(
        DOMAIN,
        context={"source": config_entries.SOURCE_ZEROCONF},
        data=discovery_info,
    )

    assert result["type"] is FlowResultType.FORM
    assert result["step_id"] == "confirm"
    assert entry.data[CONF_HOST] == "192.0.2.11"
    assert entry.data[CONF_DISCOVERY_ID] == "kef-02:00:00:00:00:02"


async def test_zeroconf_links_legacy_entry_saved_by_hostname(hass) -> None:
    """Rediscovery should match a manually configured legacy mDNS host."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        unique_id="kef-legacy-lsx.local",
        data={
            CONF_HOST: "LSX.local",
            CONF_BACKEND: KefBackend.LEGACY.value,
            CONF_DEVICE_ID: "kef-legacy-lsx.local",
        },
    )
    entry.add_to_hass(hass)
    discovery_info = ZeroconfServiceInfo(
        ip_address="fd42:241::228",
        ip_addresses=["fd42:241::228", "192.0.2.11"],
        hostname="lsx.local.",
        type=AIRPLAY_ZEROCONF_TYPE,
        name="Living Room LSX._airplay._tcp.local.",
        port=7000,
        properties={
            "manufacturer": "KEF",
            "model": "LSX",
            "deviceid": "02:00:00:00:00:02",
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
    assert entry.data[CONF_DISCOVERY_ID] == "kef-02:00:00:00:00:02"
