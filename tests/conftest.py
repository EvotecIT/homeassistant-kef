"""Shared test data for KEF."""

from __future__ import annotations

from custom_components.kef.models import (
    KefBackend,
    KefDeviceInfo,
    KefEqProfile,
    KefPlaybackInfo,
    KefSnapshot,
)

TEST_HOST = "192.0.2.10"
TEST_PORT = 80

DEVICE_NAME_VALUE = {"type": "string_", "string_": "LSX II-04438c"}
VERSION_VALUE = {"type": "string_", "string_": "2.6.120.0xfb95307"}
RELEASE_TEXT_VALUE = {"type": "string_", "string_": "LSXII_V26120"}
MAC_VALUE = {"type": "string_", "string_": "84:17:15:04:43:8C"}
MODEL_CODE_VALUE = {"type": "string_", "string_": "SP4041"}
SPEAKER_STATUS_VALUE = {"type": "kefSpeakerStatus", "kefSpeakerStatus": "powerOn"}
SOURCE_VALUE = {"type": "kefPhysicalSource", "kefPhysicalSource": "usb"}
VOLUME_VALUE = {"type": "i32_", "i32_": 80}
MUTE_VALUE = {"type": "bool_", "bool_": False}
PLAY_MODE_VALUE = {"type": "playerPlayMode", "playerPlayMode": "normal"}
PLAYER_DATA_VALUE = {
    "trackRoles": {
        "title": "usb",
        "mediaData": {"metaData": {"serviceID": "usb"}},
        "audioType": "audioBroadcast",
        "type": "audio",
        "path": "kef:/playlogic/usb",
    },
    "controls": {"pause": False, "next_": False, "previous": False},
    "state": "playing",
    "error": "",
}
PLAY_TIME_VALUE = {"type": "i64_", "i64_": -1}
EQ_PROFILE_VALUE = {
    "type": "kefEqProfile",
    "kefEqProfile": {
        "isExpertMode": False,
        "profileName": "",
        "profileId": "",
        "dspInfo": {
            "trebleAmount": 8,
            "subwooferPolarity": "normal",
            "bassExtension": "standard",
            "wallModeSetting": 14,
            "highPassModeFreq": 9,
            "audioPolarity": "normal",
            "deskMode": False,
            "subwooferGain": 10,
            "phaseCorrection": True,
            "wallMode": False,
            "balance": 30,
            "highPassMode": False,
        },
    },
}

TEST_DEVICE_INFO = KefDeviceInfo(
    backend=KefBackend.MODERN,
    unique_id="kef-84:17:15:04:43:8c",
    device_name="LSX II-04438c",
    model="LSXII",
    mac_address="84:17:15:04:43:8C",
    firmware_version="2.6.120.0xfb95307",
    release_text="LSXII_V26120",
    model_code="SP4041",
    host=TEST_HOST,
    port=TEST_PORT,
)

TEST_SNAPSHOT = KefSnapshot(
    device=TEST_DEVICE_INFO,
    speaker_status="powerOn",
    source="usb",
    volume_raw=80,
    volume_level=0.8,
    is_muted=False,
    play_mode="normal",
    playback=KefPlaybackInfo(state="playing", title="usb", service_id="usb"),
    eq_profile=KefEqProfile.from_modern_value(EQ_PROFILE_VALUE),
    source_list=("wifi", "bluetooth", "tv", "optical", "coaxial", "analog", "usb"),
)
