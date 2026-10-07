"""Privacy and useful-state contracts for downloadable KEF diagnostics."""

from dataclasses import replace
from types import SimpleNamespace

import pytest
from homeassistant.components.diagnostics import REDACTED
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef.const import DOMAIN
from custom_components.kef.diagnostics import async_get_config_entry_diagnostics
from tests.conftest import TEST_SNAPSHOT


@pytest.mark.parametrize("with_optional_state", [True, False])
async def test_diagnostics_hide_identity_and_preserve_operating_state(
    hass, with_optional_state
) -> None:
    """Sharing diagnostics must not expose device identity or private media URLs."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={
            "host": "192.0.2.42",
            "password": "private-password",
            "device_id": "kef-private-id",
            "discovery_id": "private-discovery-id",
        },
        options={"password": "private-option-password", "scan_interval": 30},
    )
    snapshot = replace(
        TEST_SNAPSHOT,
        device=replace(
            TEST_SNAPSHOT.device,
            unique_id="kef-private-id",
            device_name="Private bedroom",
        ),
        playback=(
            replace(TEST_SNAPSHOT.playback, image_url="http://private/art?token=secret")
            if with_optional_state
            else None
        ),
        eq_profile=TEST_SNAPSHOT.eq_profile if with_optional_state else None,
        wifi_info=TEST_SNAPSHOT.wifi_info if with_optional_state else None,
        speaker_location="Private address",
    )
    entry.runtime_data = SimpleNamespace(data=snapshot)

    result = await async_get_config_entry_diagnostics(hass, entry)

    assert all(value == REDACTED for value in result["entry"].values())
    assert result["options"] == {"password": REDACTED, "scan_interval": 30}
    assert result["device"]["unique_id"] == REDACTED
    assert result["device"]["device_name"] == REDACTED
    assert result["device"]["model"] == snapshot.device.model
    assert result["speaker_location"] == REDACTED
    assert result["speaker_status"] == snapshot.speaker_status
    assert result["volume_raw"] == snapshot.volume_raw
    if with_optional_state:
        assert result["playback"]["image_url"] == REDACTED
        assert result["playback"]["title"] == REDACTED
        assert result["playback"]["codec"] == snapshot.playback.codec
        assert result["wifi_info"]["ssid"] == REDACTED
        assert result["wifi_info"]["raw"] == REDACTED
        assert result["eq_profile"]["raw"] == REDACTED
    else:
        assert result["playback"] is None
        assert result["wifi_info"] is None
        assert result["eq_profile"] is None
    assert entry.data["password"] == "private-password"
    assert snapshot.device.unique_id == "kef-private-id"
