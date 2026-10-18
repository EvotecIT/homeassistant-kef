"""Optional speaker data stays unknown while reported values retain their units."""

from copy import deepcopy

import pytest

from custom_components.kef.kef_client.models import (
    KefCalibrationStatus,
    KefEqProfile,
    KefFirmwareUpdateInfo,
    KefWifiInfo,
)


@pytest.mark.parametrize(
    "payload",
    [{}, {"firmwareUpdateStatus": {}}, {"firmwareUpdateStatus": "unavailable"}],
    ids=["missing", "empty", "non-object"],
)
def test_absent_firmware_status_is_unknown(payload):
    """No status report must not turn into an available or completed update."""
    assert KefFirmwareUpdateInfo.from_modern_value(payload) is None


def test_incomplete_firmware_image_preserves_reported_state():
    """Progress remains useful even when firmware omits its image description."""
    status = {"state": "downloading", "downloadProgress": 0, "imageDescription": None}
    info = KefFirmwareUpdateInfo.from_modern_value({"firmwareUpdateStatus": status})
    assert info is not None
    assert info.state == "downloading"
    assert info.download_progress == 0
    assert not info.is_available
    assert info.available_version is None
    assert info.forced_update is None
    assert info.image_size is None
    assert info.last_forced_version is None
    assert info.url is None
    assert info.raw == status


@pytest.mark.parametrize(
    "payload",
    [{}, {"networkInfo": {}}, {"networkInfo": {"wireless": {}}},
     {"networkInfo": {"wireless": None}}],
    ids=["missing-network", "missing-wireless", "empty-wireless", "no-wireless"],
)
def test_absent_wifi_details_are_unknown(payload):
    """A wired or unreported connection has no fabricated Wi-Fi measurements."""
    assert KefWifiInfo.from_modern_value(payload) is None


def test_empty_calibration_is_unknown():
    """An empty calibration report differs from a reported uncalibrated result."""
    assert KefCalibrationStatus.from_modern_value({}) is None
    uncalibrated = KefCalibrationStatus.from_modern_value({"isCalibrated": False})
    assert uncalibrated is not None
    assert uncalibrated.is_calibrated is False
    assert uncalibrated.year is None
    assert uncalibrated.stability is None


def test_partial_v1_profile_preserves_native_zero_and_missing_settings():
    """Partial firmware reports keep real zero/False values and unknown omissions."""
    payload = {
        "kefEqProfile": {
            "profileName": "",
            "dspInfo": {"balance": 30, "wallMode": False, "wallModeSetting": None},
        }
    }
    original = deepcopy(payload)
    profile = KefEqProfile.from_modern_value(payload)
    assert profile.api_version == "v1"
    assert profile.balance == 0
    assert profile.wall_mode is False
    assert profile.profile_name is None
    assert profile.profile_id is None
    assert profile.wall_mode_setting is None
    assert profile.treble_amount is None
    assert profile.subwoofer_gain is None
    assert profile.high_pass_frequency is None
    assert profile.desk_mode_setting is None
    assert profile.sub_out_low_pass_frequency is None
    assert profile.subwoofer_out is None
    assert payload == original


def test_invalid_v2_profile_is_unknown():
    """The V2 discriminator remains intact when no profile object is reported."""
    profile = KefEqProfile.from_modern_value(
        {"type": "kefEqProfileV2", "kefEqProfileV2": None}
    )
    assert profile.api_version == "v2"
    assert profile.raw == {}
    assert profile.profile_name is None
    assert profile.profile_id is None
    assert profile.balance is None
    assert profile.subwoofer_out is None
