"""Shared test data for KEF."""

from __future__ import annotations

from collections.abc import Generator

import pytest

from custom_components.kef.models import (
    KefBackend,
    KefDeviceInfo,
    KefEqProfile,
    KefFirmwareUpdateInfo,
    KefPlaybackInfo,
    KefSnapshot,
    KefWifiInfo,
)

TEST_HOST = "192.0.2.10"
TEST_PORT = 80

DEVICE_NAME_VALUE = {"type": "string_", "string_": "LSX II-04438c"}
VERSION_VALUE = {"type": "string_", "string_": "2.6.120.0xfb95307"}
RELEASE_TEXT_VALUE = {"type": "string_", "string_": "LSXII_V26120"}
MAC_VALUE = {"type": "string_", "string_": "84:17:15:04:43:8C"}
MODEL_CODE_VALUE = {"type": "string_", "string_": "SP4041"}
SERIAL_NUMBER_VALUE = {"type": "string_", "string_": "LSX2G38602R23R1G"}
KEF_ID_VALUE = {"type": "string_", "string_": "283284c1-b02e-417d-b659-e6e1f4d5f2f5"}
HARDWARE_VERSION_VALUE = {"type": "string_", "string_": "0.0.0"}
SPEAKER_STATUS_VALUE = {"type": "kefSpeakerStatus", "kefSpeakerStatus": "powerOn"}
SOURCE_VALUE = {"type": "kefPhysicalSource", "kefPhysicalSource": "usb"}
CABLE_MODE_VALUE = {"type": "kefCableMode", "kefCableMode": "wired"}
MASTER_CHANNEL_VALUE = {
    "type": "kefMasterChannelMode",
    "kefMasterChannelMode": "right",
}
VOLUME_VALUE = {"type": "i32_", "i32_": 80}
MUTE_VALUE = {"type": "bool_", "bool_": False}
PLAY_MODE_VALUE = {"type": "playerPlayMode", "playerPlayMode": "normal"}
FIRMWARE_UPDATE_STATUS_VALUE = {
    "type": "firmwareUpdateStatus",
    "firmwareUpdateStatus": {
        "downloadProgress": 0,
        "state": "newUpdateAvailable",
        "imageDescription": {
            "version": "3.0.135.0x60acbcf",
            "forcedUpdate": False,
            "imageSize": 0,
            "lastForcedVersion": "0.0.0.0x0",
            "url": "https://assets.kef.com/pm/pm_firmware/lsxii/LSXII_V30135.swu",
        },
    },
}
STANDBY_MODE_VALUE = {"type": "kefStandbyMode", "kefStandbyMode": "standby_none"}
STARTUP_TONE_VALUE = {"type": "bool_", "bool_": True}
AUTO_SWITCH_HDMI_VALUE = {"type": "bool_", "bool_": False}
DISABLE_FRONT_LED_VALUE = {"type": "bool_", "bool_": True}
DISABLE_FRONT_STANDBY_LED_VALUE = {"type": "bool_", "bool_": False}
DISABLE_TOP_PANEL_VALUE = {"type": "bool_", "bool_": False}
TOP_PANEL_LED_VALUE = {"type": "bool_", "bool_": True}
TOP_PANEL_STANDBY_LED_VALUE = {"type": "bool_", "bool_": True}
DISABLE_ANALYTICS_VALUE = {"type": "bool_", "bool_": False}
DISABLE_APP_ANALYTICS_VALUE = {"type": "bool_", "bool_": False}
STREAMING_QUALITY_VALUE = {
    "type": "airableStreamBitrate",
    "airableStreamBitrate": "unlimited",
}
UI_LANGUAGE_VALUE = {"type": "string_", "string_": "en_PL"}
SPEAKER_LOCATION_VALUE = {"type": "string_", "string_": "PL"}
NETWORK_PING_VALUE = {"type": "double_", "double_": 0}
NETWORK_STABILITY_VALUE = {
    "type": "kefNetworkStability",
    "kefNetworkStability": "idle",
}
SPEED_TEST_STATUS_VALUE = {
    "type": "kefSpeedTestStatus",
    "kefSpeedTestStatus": "idle",
}
SPEED_TEST_AVERAGE_DOWNLOAD_VALUE = {"type": "double_", "double_": 0}
SPEED_TEST_CURRENT_DOWNLOAD_VALUE = {"type": "double_", "double_": 0}
SPEED_TEST_PACKET_LOSS_VALUE = {"type": "double_", "double_": 0}
ALERTS_LIST_VALUE = {
    "type": "alertsList",
    "alertsList": {"alarms": [], "timers": []},
}
ALERT_SNOOZE_TIME_VALUE = {"type": "i32_", "i32_": 10}
PLAYER_NOTIFICATION_VALUE = {"type": "bool_", "bool_": False}
WAKE_UP_SOURCE_VALUE = {
    "type": "kefWakeUpSource",
    "kefWakeUpSource": "wakeup_default",
}
SUBWOOFER_FORCE_ON_VALUE = {"type": "bool_", "bool_": False}
SUBWOOFER_FORCE_ON_KW1_VALUE = {"type": "bool_", "bool_": False}
USB_CHARGING_VALUE = {"type": "bool_", "bool_": False}
STARTUP_VOLUME_ENABLED_VALUE = {"type": "bool_", "bool_": False}
PER_INPUT_STARTUP_VOLUME_ENABLED_VALUE = {"type": "bool_", "bool_": False}
DEFAULT_VOLUME_GLOBAL_VALUE = {"type": "i32_", "i32_": 30}
MAXIMUM_VOLUME_VALUE = {"type": "i32_", "i32_": 100}
VOLUME_STEP_SETTING_VALUE = {"type": "i16_", "i16_": 1}
VOLUME_LIMIT_VALUE = {"type": "bool_", "bool_": False}
FIXED_VOLUME_LEVEL_VALUE = {"type": "i32_", "i32_": 30}
REMOTE_IR_VALUE = {"type": "bool_", "bool_": True}
REMOTE_IR_CODE_VALUE = {
    "type": "kefSpeakerIRCode",
    "kefSpeakerIRCode": "ir_code_set_a",
}
FAVOURITE_BUTTON_VALUE = {
    "type": "kefFavouriteButtonFunction",
    "kefFavouriteButtonFunction": "nextSource",
}
EQ_BUTTON_1_VALUE = {"type": "string_", "string_": "dialogue"}
EQ_BUTTON_2_VALUE = {"type": "string_", "string_": "night"}
PLAYER_DATA_VALUE = {
    "trackRoles": {
        "title": "usb",
        "mediaData": {
            "metaData": {
                "artist": "KEF",
                "album": "USB Demo",
                "albumArtist": "KEF Artists",
                "serviceID": "usb",
            },
            "activeResource": {
                "codec": "pcm",
                "sampleFrequency": 48000,
                "streamSampleRate": 48000,
                "streamChannels": "2.0",
                "nrAudioChannels": 2,
            },
        },
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
            "isKW1": False,
            "subwooferCount": 0,
            "subEnableStereo": False,
            "subwooferPreset": "custom",
            "subOutLPFreq": 8,
            "deskModeSetting": 14,
        },
    },
}
EQ_PROFILE_V2_VALUE = {
    "type": "kefEqProfileV2",
    "kefEqProfileV2": {
        "isExpertMode": False,
        "profileName": "",
        "profileId": "",
        "trebleAmount": 0,
        "subwooferPolarity": "normal",
        "bassExtension": "standard",
        "wallModeSetting": -3,
        "highPassModeFreq": 95,
        "audioPolarity": "normal",
        "deskMode": False,
        "subwooferGain": 0,
        "phaseCorrection": True,
        "wallMode": False,
        "balance": 0,
        "highPassMode": False,
        "isKW1": False,
        "subwooferCount": 0,
        "subEnableStereo": False,
        "subwooferPreset": "custom",
        "subOutLPFreq": 80,
        "deskModeSetting": -3,
        "subwooferOut": True,
        "soundProfile": "default",
        "dialogueMode": False,
        "wallMounted": False,
    },
}
NETWORK_INFO_VALUE = {
    "networkInfo": {
        "wireless": {
            "signalLevel": -49,
            "ssid": "EvotecLab",
            "frequency": 5180,
            "bssid": "AA:BB:CC:DD:EE:FF",
        }
    }
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
    serial_number="LSX2G38602R23R1G",
    kef_id="283284c1-b02e-417d-b659-e6e1f4d5f2f5",
    hardware_version="0.0.0",
    host=TEST_HOST,
    port=TEST_PORT,
)

TEST_SNAPSHOT = KefSnapshot(
    device=TEST_DEVICE_INFO,
    speaker_status="powerOn",
    source="usb",
    cable_mode="wired",
    master_channel="right",
    volume_raw=80,
    volume_level=0.8,
    is_muted=False,
    play_mode="normal",
    playback=KefPlaybackInfo(
        state="playing",
        title="usb",
        artist="KEF",
        album="USB Demo",
        album_artist="KEF Artists",
        service_id="usb",
        codec="pcm",
        sample_frequency=48000,
        stream_sample_rate=48000,
        stream_channels="2.0",
        audio_channels=2,
    ),
    eq_profile=KefEqProfile.from_modern_value(EQ_PROFILE_VALUE),
    firmware_update=KefFirmwareUpdateInfo.from_modern_value(
        FIRMWARE_UPDATE_STATUS_VALUE
    ),
    wifi_info=KefWifiInfo.from_modern_value(NETWORK_INFO_VALUE),
    standby_mode="standby_none",
    startup_tone_enabled=True,
    auto_switch_hdmi=False,
    front_led_enabled=False,
    standby_led_enabled=True,
    top_panel_enabled=True,
    top_panel_led_enabled=True,
    top_panel_standby_led_enabled=True,
    wake_source="wakeup_default",
    subwoofer_wake_enabled=False,
    kw1_wake_enabled=False,
    usb_charging_enabled=False,
    startup_volume_enabled=False,
    per_input_startup_volume_enabled=False,
    default_volume_global=30,
    maximum_volume=100,
    volume_step=1,
    volume_limit_enabled=False,
    fixed_volume_level=30,
    remote_ir_enabled=True,
    remote_ir_code="ir_code_set_a",
    favourite_button="nextSource",
    eq_button_1="dialogue",
    eq_button_2="night",
    analytics_enabled=True,
    app_analytics_enabled=True,
    streaming_quality="unlimited",
    ui_language="en_PL",
    speaker_location="PL",
    network_ping_ms=0.0,
    network_stability="idle",
    speed_test_status="idle",
    speed_test_average_download=0.0,
    speed_test_current_download=0.0,
    speed_test_packet_loss=0.0,
    alert_alarm_count=0,
    alert_timer_count=0,
    alert_snooze_minutes=10,
    player_notification_active=False,
    source_list=("wifi", "bluetooth", "tv", "optical", "coaxial", "analog", "usb"),
    default_volume_by_source={
        "wifi": 30,
        "bluetooth": 30,
        "tv": 30,
        "optical": 30,
        "usb": 30,
        "analog": 30,
    },
)


@pytest.fixture(autouse=True)
def auto_enable_custom_integrations(
    enable_custom_integrations: None,
) -> Generator[None]:
    """Enable loading custom integrations in tests."""
    yield
