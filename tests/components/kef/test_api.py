"""API tests for KEF."""

from __future__ import annotations

import asyncio
import builtins
import copy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.kef.api import (
    LegacyBinaryClient,
    ModernKefClient,
    async_create_client,
)
from custom_components.kef.const import (
    AUTH_MODE_ALL,
    AUTH_MODE_SETDATA,
    EVENT_MODIFY_QUEUE_ENDPOINT,
    EVENT_POLL_QUEUE_ENDPOINT,
    PROBE_PATHS,
)
from custom_components.kef.exceptions import (
    KefAuthenticationRequiredError,
    KefConnectionError,
    KefResponseError,
)
from custom_components.kef.number import NUMBERS, KefNumber
from tests.conftest import (
    ALERT_SNOOZE_TIME_VALUE,
    ALERTS_LIST_VALUE,
    AUTO_SWITCH_HDMI_VALUE,
    CABLE_MODE_VALUE,
    DEFAULT_VOLUME_GLOBAL_VALUE,
    DEVICE_NAME_VALUE,
    DISABLE_ANALYTICS_VALUE,
    DISABLE_APP_ANALYTICS_VALUE,
    DISABLE_FRONT_LED_VALUE,
    DISABLE_FRONT_STANDBY_LED_VALUE,
    DISABLE_TOP_PANEL_VALUE,
    EQ_BUTTON_1_VALUE,
    EQ_BUTTON_2_VALUE,
    EQ_PROFILE_V2_VALUE,
    EQ_PROFILE_VALUE,
    FAVOURITE_BUTTON_VALUE,
    FIRMWARE_UPDATE_STATUS_VALUE,
    FIXED_VOLUME_LEVEL_VALUE,
    HARDWARE_VERSION_VALUE,
    KEF_ID_VALUE,
    MAC_VALUE,
    MASTER_CHANNEL_VALUE,
    MAXIMUM_VOLUME_VALUE,
    MODEL_CODE_VALUE,
    MUTE_VALUE,
    NETWORK_INFO_VALUE,
    NETWORK_PING_VALUE,
    NETWORK_STABILITY_VALUE,
    PER_INPUT_STARTUP_VOLUME_ENABLED_VALUE,
    PLAY_MODE_VALUE,
    PLAY_TIME_VALUE,
    PLAYER_DATA_VALUE,
    PLAYER_NOTIFICATION_VALUE,
    RELEASE_TEXT_VALUE,
    REMOTE_IR_CODE_VALUE,
    REMOTE_IR_VALUE,
    SERIAL_NUMBER_VALUE,
    SOURCE_VALUE,
    SPEAKER_LOCATION_VALUE,
    SPEAKER_STATUS_VALUE,
    SPEED_TEST_AVERAGE_DOWNLOAD_VALUE,
    SPEED_TEST_CURRENT_DOWNLOAD_VALUE,
    SPEED_TEST_PACKET_LOSS_VALUE,
    SPEED_TEST_STATUS_VALUE,
    STANDBY_MODE_VALUE,
    STARTUP_TONE_VALUE,
    STARTUP_VOLUME_ENABLED_VALUE,
    STREAMING_QUALITY_VALUE,
    SUBWOOFER_FORCE_ON_KW1_VALUE,
    SUBWOOFER_FORCE_ON_VALUE,
    TEST_HOST,
    TEST_SNAPSHOT,
    TOP_PANEL_LED_VALUE,
    TOP_PANEL_STANDBY_LED_VALUE,
    UI_LANGUAGE_VALUE,
    USB_CHARGING_VALUE,
    VERSION_VALUE,
    VOLUME_LIMIT_VALUE,
    VOLUME_STEP_SETTING_VALUE,
    VOLUME_VALUE,
    WAKE_UP_SOURCE_VALUE,
)


@pytest.mark.parametrize(
    ("host", "port", "expected", "authority"),
    [
        ("lsxii.local", 80, "http://lsxii.local/api/getData", "lsxii.local:80"),
        ("192.0.2.11", 80, "http://192.0.2.11/api/getData", "192.0.2.11:80"),
        (
            "fd42:241::228",
            80,
            "http://[fd42:241::228]/api/getData",
            "[fd42:241::228]:80",
        ),
        (
            "fd42:241::228",
            8080,
            "http://[fd42:241::228]:8080/api/getData",
            "[fd42:241::228]:8080",
        ),
    ],
)
async def test_modern_http_authority(host, port, expected, authority, hass) -> None:
    """A literal IPv6 host must form a valid URL for all modern requests."""
    client = ModernKefClient(host, async_get_clientsession(hass), port=port)
    assert client._build_url("/getData") == expected
    assert client._http_authority(include_port=True) == authority


@pytest.mark.parametrize(
    ("key", "v1_step", "v1_max", "v2_step", "v2_max"),
    [
        ("treble_amount", 0.375, 3.0, 0.25, 3.0),
        ("high_pass_frequency", 5.0, 100.0, 5.0, 120.0),
        ("sub_out_low_pass_frequency", 10.0, 250.0, 5.0, 250.0),
    ],
)
def test_eq_number_constraints_follow_wire_version(
    key,
    v1_step,
    v1_max,
    v2_step,
    v2_max,
) -> None:
    """Number controls should advertise values each EQ generation can encode."""
    description = next(item for item in NUMBERS if item.key == key)

    def entity_for_version(api_version: str) -> KefNumber:
        snapshot = copy.deepcopy(TEST_SNAPSHOT)
        assert snapshot.eq_profile is not None
        snapshot.eq_profile.api_version = api_version
        coordinator = Mock()
        coordinator.data = snapshot
        coordinator.last_update_success = True
        coordinator.config_entry = SimpleNamespace(domain="kef")
        coordinator.hass = Mock()
        return KefNumber(coordinator, description)

    v1_entity = entity_for_version("v1")
    v2_entity = entity_for_version("v2")

    assert v1_entity.entity_description.native_step == v1_step
    assert v1_entity.entity_description.native_max_value == v1_max
    assert v2_entity.entity_description.native_step == v2_step
    assert v2_entity.entity_description.native_max_value == v2_max


SOURCE_VOLUME_RESPONSES = {
    "settings:/kef/host/defaultVolumeWifi": 30,
    "settings:/kef/host/defaultVolumeBluetooth": 30,
    "settings:/kef/host/defaultVolumeTV": 30,
    "settings:/kef/host/defaultVolumeOptical": 30,
    "settings:/kef/host/defaultVolumeAnalogue": 30,
    "settings:/kef/host/defaultVolumeUSB": 30,
}


async def test_modern_refresh_parses_snapshot(monkeypatch, hass) -> None:
    """Modern client should parse a full LSX II snapshot."""
    responses = {
        PROBE_PATHS["device_name"]: DEVICE_NAME_VALUE,
        PROBE_PATHS["version"]: VERSION_VALUE,
        PROBE_PATHS["release_text"]: RELEASE_TEXT_VALUE,
        PROBE_PATHS["mac"]: MAC_VALUE,
        PROBE_PATHS["model_code"]: MODEL_CODE_VALUE,
        PROBE_PATHS["serial_number"]: SERIAL_NUMBER_VALUE["string_"],
        PROBE_PATHS["kef_id"]: KEF_ID_VALUE["string_"],
        PROBE_PATHS["hardware_version"]: HARDWARE_VERSION_VALUE["string_"],
        PROBE_PATHS["speaker_status"]: SPEAKER_STATUS_VALUE["kefSpeakerStatus"],
        PROBE_PATHS["source"]: SOURCE_VALUE["kefPhysicalSource"],
        PROBE_PATHS["cable_mode"]: CABLE_MODE_VALUE["kefCableMode"],
        PROBE_PATHS["master_channel"]: MASTER_CHANNEL_VALUE["kefMasterChannelMode"],
        PROBE_PATHS["volume"]: VOLUME_VALUE["i32_"],
        PROBE_PATHS["mute"]: MUTE_VALUE["bool_"],
        PROBE_PATHS["play_mode"]: PLAY_MODE_VALUE["playerPlayMode"],
        PROBE_PATHS["firmware_update_status"]: FIRMWARE_UPDATE_STATUS_VALUE,
        PROBE_PATHS["player_data"]: PLAYER_DATA_VALUE,
        PROBE_PATHS["play_time"]: PLAY_TIME_VALUE["i64_"],
        PROBE_PATHS["eq_profile"]: EQ_PROFILE_VALUE,
        PROBE_PATHS["network_info"]: NETWORK_INFO_VALUE,
        PROBE_PATHS["standby_mode"]: STANDBY_MODE_VALUE["kefStandbyMode"],
        PROBE_PATHS["startup_tone"]: STARTUP_TONE_VALUE["bool_"],
        PROBE_PATHS["auto_switch_hdmi"]: AUTO_SWITCH_HDMI_VALUE["bool_"],
        PROBE_PATHS["disable_front_led"]: DISABLE_FRONT_LED_VALUE["bool_"],
        PROBE_PATHS["disable_front_standby_led"]: (
            DISABLE_FRONT_STANDBY_LED_VALUE["bool_"]
        ),
        PROBE_PATHS["disable_top_panel"]: DISABLE_TOP_PANEL_VALUE["bool_"],
        PROBE_PATHS["top_panel_led"]: TOP_PANEL_LED_VALUE["bool_"],
        PROBE_PATHS["top_panel_standby_led"]: TOP_PANEL_STANDBY_LED_VALUE[
            "bool_"
        ],
        PROBE_PATHS["disable_analytics"]: DISABLE_ANALYTICS_VALUE["bool_"],
        PROBE_PATHS["disable_app_analytics"]: DISABLE_APP_ANALYTICS_VALUE[
            "bool_"
        ],
        PROBE_PATHS["streaming_quality"]: STREAMING_QUALITY_VALUE[
            "airableStreamBitrate"
        ],
        PROBE_PATHS["ui_language"]: UI_LANGUAGE_VALUE["string_"],
        PROBE_PATHS["speaker_location"]: SPEAKER_LOCATION_VALUE["string_"],
        PROBE_PATHS["network_ping"]: NETWORK_PING_VALUE["double_"],
        PROBE_PATHS["network_stability"]: NETWORK_STABILITY_VALUE[
            "kefNetworkStability"
        ],
        PROBE_PATHS["speed_test_status"]: SPEED_TEST_STATUS_VALUE[
            "kefSpeedTestStatus"
        ],
        PROBE_PATHS["speed_test_average_download"]: (
            SPEED_TEST_AVERAGE_DOWNLOAD_VALUE["double_"]
        ),
        PROBE_PATHS["speed_test_current_download"]: (
            SPEED_TEST_CURRENT_DOWNLOAD_VALUE["double_"]
        ),
        PROBE_PATHS["speed_test_packet_loss"]: SPEED_TEST_PACKET_LOSS_VALUE[
            "double_"
        ],
        PROBE_PATHS["alerts_list"]: ALERTS_LIST_VALUE,
        PROBE_PATHS["alert_snooze_time"]: ALERT_SNOOZE_TIME_VALUE["i32_"],
        PROBE_PATHS["player_notification"]: PLAYER_NOTIFICATION_VALUE["bool_"],
        PROBE_PATHS["wake_up_source"]: WAKE_UP_SOURCE_VALUE["kefWakeUpSource"],
        PROBE_PATHS["subwoofer_force_on"]: SUBWOOFER_FORCE_ON_VALUE["bool_"],
        PROBE_PATHS["subwoofer_force_on_kw1"]: (
            SUBWOOFER_FORCE_ON_KW1_VALUE["bool_"]
        ),
        PROBE_PATHS["usb_charging"]: USB_CHARGING_VALUE["bool_"],
        PROBE_PATHS["startup_volume_enabled"]: (
            STARTUP_VOLUME_ENABLED_VALUE["bool_"]
        ),
        PROBE_PATHS["per_input_startup_volume_enabled"]: (
            PER_INPUT_STARTUP_VOLUME_ENABLED_VALUE["bool_"]
        ),
        PROBE_PATHS["default_volume_global"]: DEFAULT_VOLUME_GLOBAL_VALUE["i32_"],
        PROBE_PATHS["maximum_volume"]: MAXIMUM_VOLUME_VALUE["i32_"],
        PROBE_PATHS["volume_step"]: VOLUME_STEP_SETTING_VALUE["i16_"],
        PROBE_PATHS["volume_limit"]: VOLUME_LIMIT_VALUE["bool_"],
        PROBE_PATHS["fixed_volume_level"]: FIXED_VOLUME_LEVEL_VALUE["i32_"],
        PROBE_PATHS["remote_ir"]: REMOTE_IR_VALUE["bool_"],
        PROBE_PATHS["remote_ir_code"]: REMOTE_IR_CODE_VALUE["kefSpeakerIRCode"],
        PROBE_PATHS["favourite_button"]: FAVOURITE_BUTTON_VALUE[
            "kefFavouriteButtonFunction"
        ],
        PROBE_PATHS["eq_button_1"]: EQ_BUTTON_1_VALUE["string_"],
        PROBE_PATHS["eq_button_2"]: EQ_BUTTON_2_VALUE["string_"],
        **SOURCE_VOLUME_RESPONSES,
    }

    async def fake_get_value(self, path, *, typed_key=None):
        return responses[path]

    async def fake_get_optional_value(self, path, *, typed_key=None):
        return responses.get(path)

    monkeypatch.setattr(ModernKefClient, "_get_path_value", fake_get_value)
    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_value",
        fake_get_optional_value,
    )

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    snapshot = await client.async_refresh()

    assert snapshot.device.device_name == "LSX II-Test"
    assert snapshot.device.model == "LSXII"
    assert snapshot.device.serial_number == "TEST-LSX2-0001"
    assert snapshot.device.kef_id == "00000000-0000-4000-8000-000000000001"
    assert snapshot.device.hardware_version == "0.0.0"
    assert snapshot.source == "usb"
    assert snapshot.cable_mode == "wired"
    assert snapshot.master_channel == "right"
    assert snapshot.volume_raw == 80
    assert snapshot.is_muted is False
    assert snapshot.playback is not None
    assert snapshot.playback.state == "playing"
    assert snapshot.playback.album_artist == "KEF Artists"
    assert snapshot.playback.service_id == "usb"
    assert snapshot.playback.codec == "pcm"
    assert snapshot.playback.stream_channels == "2.0"
    assert snapshot.eq_profile is not None
    assert snapshot.eq_profile.profile_id is None
    assert snapshot.eq_profile.balance == 0
    assert snapshot.eq_profile.treble_amount == 0
    assert snapshot.eq_profile.subwoofer_gain == 0
    assert snapshot.eq_profile.high_pass_frequency == 95
    assert snapshot.eq_profile.desk_mode_setting == -3
    assert snapshot.eq_profile.wall_mode_setting == -3
    assert snapshot.eq_profile.audio_polarity == "normal"
    assert snapshot.eq_profile.subwoofer_polarity == "normal"
    assert snapshot.eq_profile.subwoofer_preset == "custom"
    assert snapshot.eq_profile.sub_out_low_pass_frequency == 80
    assert snapshot.eq_profile.subwoofer_out is False
    assert snapshot.firmware_update is not None
    assert snapshot.firmware_update.state == "newUpdateAvailable"
    assert snapshot.firmware_update.available_version == "3.0.135.0x60acbcf"
    assert snapshot.wifi_info is not None
    assert snapshot.wifi_info.ssid == "TestNetwork"
    assert snapshot.wifi_info.signal_level == -49
    assert snapshot.standby_mode == "standby_none"
    assert snapshot.startup_tone_enabled is True
    assert snapshot.auto_switch_hdmi is False
    assert snapshot.front_led_enabled is False
    assert snapshot.standby_led_enabled is True
    assert snapshot.top_panel_enabled is True
    assert snapshot.top_panel_led_enabled is True
    assert snapshot.top_panel_standby_led_enabled is True
    assert snapshot.wake_source == "wakeup_default"
    assert snapshot.subwoofer_wake_enabled is False
    assert snapshot.kw1_wake_enabled is False
    assert snapshot.usb_charging_enabled is False
    assert snapshot.startup_volume_enabled is False
    assert snapshot.per_input_startup_volume_enabled is False
    assert snapshot.default_volume_global == 30
    assert snapshot.default_volume_by_source["wifi"] == 30
    assert snapshot.default_volume_by_source["usb"] == 30
    assert snapshot.maximum_volume == 100
    assert snapshot.volume_step == 1
    assert snapshot.volume_limit_enabled is False
    assert snapshot.fixed_volume_level == 30
    assert snapshot.remote_ir_enabled is True
    assert snapshot.remote_ir_code == "ir_code_set_a"
    assert snapshot.favourite_button == "nextSource"
    assert snapshot.eq_button_1 == "dialogue"
    assert snapshot.eq_button_2 == "night"
    assert snapshot.analytics_enabled is True
    assert snapshot.app_analytics_enabled is True
    assert snapshot.streaming_quality == "unlimited"
    assert snapshot.ui_language == "en_PL"
    assert snapshot.speaker_location == "PL"
    assert snapshot.network_ping_ms == 0.0
    assert snapshot.network_stability == "idle"
    assert snapshot.speed_test_status == "idle"
    assert snapshot.speed_test_average_download == 0.0
    assert snapshot.speed_test_current_download == 0.0
    assert snapshot.speed_test_packet_loss == 0.0
    assert snapshot.alert_alarm_count == 0
    assert snapshot.alert_timer_count == 0
    assert snapshot.alert_snooze_minutes == 10
    assert snapshot.player_notification_active is False
    assert snapshot.source_list == (
        "wifi",
        "bluetooth",
        "tv",
        "optical",
        "analog",
        "usb",
    )


async def test_autodetect_preserves_modern_auth_failures(monkeypatch, hass) -> None:
    """Backend autodetection should not hide modern authentication failures."""

    async def fake_modern_identify(self):
        raise KefAuthenticationRequiredError("password required")

    async def fake_legacy_identify(self):
        raise AssertionError("legacy probing should not run after auth failure")

    monkeypatch.setattr(ModernKefClient, "async_identify", fake_modern_identify)
    monkeypatch.setattr(LegacyBinaryClient, "async_identify", fake_legacy_identify)

    with pytest.raises(KefAuthenticationRequiredError):
        await async_create_client(TEST_HOST, async_get_clientsession(hass))


async def test_modern_set_volume_posts_typed_payload(monkeypatch, hass) -> None:
    """Modern client should post a typed payload when setting volume."""
    captured = {}

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["json_payload"] = json_payload
        return {}

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_volume_raw(42)

    assert captured == {
        "method": "POST",
        "endpoint": "/setData",
        "json_payload": {
            "path": "player:volume",
            "role": "value",
            "value": {"type": "i32_", "i32_": 42},
        },
    }


async def test_modern_set_muted_posts_bool_payload(monkeypatch, hass) -> None:
    """Modern client should post a bool payload when muting."""
    captured = {}

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["json_payload"] = json_payload
        return {}

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_muted(True)

    assert captured == {
        "method": "POST",
        "endpoint": "/setData",
        "json_payload": {
            "path": "settings:/mediaPlayer/mute",
            "role": "value",
            "value": {"type": "bool_", "bool_": True},
        },
    }


async def test_modern_poll_events_creates_queue_and_polls(monkeypatch, hass) -> None:
    """Modern client should subscribe to the event queue before polling it."""
    calls = []

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        calls.append(
            {
                "method": method,
                "endpoint": endpoint,
                "params": params,
                "json_payload": json_payload,
            }
        )
        if endpoint == EVENT_MODIFY_QUEUE_ENDPOINT:
            return "{queue-123}"
        if endpoint == EVENT_POLL_QUEUE_ENDPOINT:
            return [
                {
                    "path": "player:volume",
                    "itemValue": {"type": "i32_", "i32_": 79},
                }
            ]
        raise AssertionError(f"Unexpected endpoint: {endpoint}")

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    events = await client.async_poll_events(timeout=2)

    assert events == [
        {"path": "player:volume", "itemValue": {"type": "i32_", "i32_": 79}}
    ]
    assert calls[0]["method"] == "POST"
    assert calls[0]["endpoint"] == EVENT_MODIFY_QUEUE_ENDPOINT
    assert calls[0]["json_payload"]["subscribe"]
    assert calls[1] == {
        "method": "GET",
        "endpoint": EVENT_POLL_QUEUE_ENDPOINT,
        "params": {"queueId": "{queue-123}", "timeout": 2},
        "json_payload": None,
    }


async def test_modern_reset_event_queue_recreates_subscription(
    monkeypatch,
    hass,
) -> None:
    """Resetting the queue should force the next poll to subscribe again."""
    queue_ids = iter(["{queue-a}", "{queue-b}"])
    polled_with = []

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        if endpoint == EVENT_MODIFY_QUEUE_ENDPOINT:
            return next(queue_ids)
        if endpoint == EVENT_POLL_QUEUE_ENDPOINT:
            polled_with.append(params["queueId"])
            return []
        raise AssertionError(f"Unexpected endpoint: {endpoint}")

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_poll_events(timeout=1)
    await client.async_reset_event_queue()
    await client.async_poll_events(timeout=1)

    assert polled_with == ["{queue-a}", "{queue-b}"]


async def test_modern_turn_on_prefers_last_active_source(monkeypatch, hass) -> None:
    """Modern turn-on should reuse the last active source when known."""
    selected = []
    mapping = {
        PROBE_PATHS["device_name"]: DEVICE_NAME_VALUE,
        PROBE_PATHS["version"]: VERSION_VALUE,
        PROBE_PATHS["release_text"]: RELEASE_TEXT_VALUE,
        PROBE_PATHS["mac"]: MAC_VALUE,
        PROBE_PATHS["model_code"]: MODEL_CODE_VALUE,
        PROBE_PATHS["speaker_status"]: "standby",
        PROBE_PATHS["source"]: "standby",
        PROBE_PATHS["cable_mode"]: CABLE_MODE_VALUE["kefCableMode"],
        PROBE_PATHS["master_channel"]: MASTER_CHANNEL_VALUE["kefMasterChannelMode"],
        PROBE_PATHS["volume"]: 80,
        PROBE_PATHS["mute"]: False,
        PROBE_PATHS["play_mode"]: PLAY_MODE_VALUE["playerPlayMode"],
        PROBE_PATHS["firmware_update_status"]: FIRMWARE_UPDATE_STATUS_VALUE,
        PROBE_PATHS["player_data"]: PLAYER_DATA_VALUE,
        PROBE_PATHS["play_time"]: PLAY_TIME_VALUE["i64_"],
        PROBE_PATHS["eq_profile"]: EQ_PROFILE_VALUE,
        PROBE_PATHS["network_info"]: NETWORK_INFO_VALUE,
        PROBE_PATHS["standby_mode"]: STANDBY_MODE_VALUE["kefStandbyMode"],
        PROBE_PATHS["startup_tone"]: STARTUP_TONE_VALUE["bool_"],
        PROBE_PATHS["auto_switch_hdmi"]: AUTO_SWITCH_HDMI_VALUE["bool_"],
        PROBE_PATHS["disable_front_led"]: DISABLE_FRONT_LED_VALUE["bool_"],
        PROBE_PATHS["disable_front_standby_led"]: (
            DISABLE_FRONT_STANDBY_LED_VALUE["bool_"]
        ),
        PROBE_PATHS["disable_top_panel"]: DISABLE_TOP_PANEL_VALUE["bool_"],
        PROBE_PATHS["wake_up_source"]: WAKE_UP_SOURCE_VALUE["kefWakeUpSource"],
        PROBE_PATHS["subwoofer_force_on"]: SUBWOOFER_FORCE_ON_VALUE["bool_"],
        PROBE_PATHS["subwoofer_force_on_kw1"]: (
            SUBWOOFER_FORCE_ON_KW1_VALUE["bool_"]
        ),
        PROBE_PATHS["usb_charging"]: USB_CHARGING_VALUE["bool_"],
        PROBE_PATHS["startup_volume_enabled"]: STARTUP_VOLUME_ENABLED_VALUE["bool_"],
        PROBE_PATHS["per_input_startup_volume_enabled"]: (
            PER_INPUT_STARTUP_VOLUME_ENABLED_VALUE["bool_"]
        ),
        PROBE_PATHS["default_volume_global"]: DEFAULT_VOLUME_GLOBAL_VALUE["i32_"],
        PROBE_PATHS["maximum_volume"]: MAXIMUM_VOLUME_VALUE["i32_"],
        PROBE_PATHS["volume_step"]: VOLUME_STEP_SETTING_VALUE["i16_"],
        PROBE_PATHS["volume_limit"]: VOLUME_LIMIT_VALUE["bool_"],
        PROBE_PATHS["fixed_volume_level"]: FIXED_VOLUME_LEVEL_VALUE["i32_"],
        **SOURCE_VOLUME_RESPONSES,
    }

    async def fake_refresh(self):
        self._last_active_source = "usb"
        return await ModernKefClient.async_refresh(self)

    async def fake_get_value(self, path, *, typed_key=None):
        return mapping[path]

    async def fake_get_optional_value(self, path, *, typed_key=None):
        return mapping.get(path)

    async def fake_select_source(self, source):
        selected.append(source)

    monkeypatch.setattr(ModernKefClient, "_get_path_value", fake_get_value)
    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_value",
        fake_get_optional_value,
    )
    monkeypatch.setattr(ModernKefClient, "async_select_source", fake_select_source)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    client._last_active_source = "usb"
    await client.async_turn_on()

    assert selected == ["usb"]


async def test_modern_unknown_model_uses_default_sources(monkeypatch, hass) -> None:
    """Unknown modern models should fall back to the full source set."""
    responses = {
        PROBE_PATHS["device_name"]: DEVICE_NAME_VALUE,
        PROBE_PATHS["version"]: VERSION_VALUE,
        PROBE_PATHS["release_text"]: {"type": "string_", "string_": "MYSTERY_V1"},
        PROBE_PATHS["mac"]: MAC_VALUE,
        PROBE_PATHS["model_code"]: MODEL_CODE_VALUE,
        PROBE_PATHS["speaker_status"]: SPEAKER_STATUS_VALUE["kefSpeakerStatus"],
        PROBE_PATHS["source"]: SOURCE_VALUE["kefPhysicalSource"],
        PROBE_PATHS["cable_mode"]: CABLE_MODE_VALUE["kefCableMode"],
        PROBE_PATHS["master_channel"]: MASTER_CHANNEL_VALUE["kefMasterChannelMode"],
        PROBE_PATHS["volume"]: VOLUME_VALUE["i32_"],
        PROBE_PATHS["mute"]: MUTE_VALUE["bool_"],
        PROBE_PATHS["play_mode"]: PLAY_MODE_VALUE["playerPlayMode"],
        PROBE_PATHS["firmware_update_status"]: FIRMWARE_UPDATE_STATUS_VALUE,
        PROBE_PATHS["player_data"]: PLAYER_DATA_VALUE,
        PROBE_PATHS["play_time"]: PLAY_TIME_VALUE["i64_"],
        PROBE_PATHS["eq_profile"]: EQ_PROFILE_VALUE,
        PROBE_PATHS["network_info"]: NETWORK_INFO_VALUE,
        PROBE_PATHS["standby_mode"]: STANDBY_MODE_VALUE["kefStandbyMode"],
        PROBE_PATHS["startup_tone"]: STARTUP_TONE_VALUE["bool_"],
        PROBE_PATHS["auto_switch_hdmi"]: AUTO_SWITCH_HDMI_VALUE["bool_"],
        PROBE_PATHS["disable_front_led"]: DISABLE_FRONT_LED_VALUE["bool_"],
        PROBE_PATHS["disable_front_standby_led"]: (
            DISABLE_FRONT_STANDBY_LED_VALUE["bool_"]
        ),
        PROBE_PATHS["disable_top_panel"]: DISABLE_TOP_PANEL_VALUE["bool_"],
        PROBE_PATHS["wake_up_source"]: WAKE_UP_SOURCE_VALUE["kefWakeUpSource"],
        PROBE_PATHS["subwoofer_force_on"]: SUBWOOFER_FORCE_ON_VALUE["bool_"],
        PROBE_PATHS["subwoofer_force_on_kw1"]: (
            SUBWOOFER_FORCE_ON_KW1_VALUE["bool_"]
        ),
        PROBE_PATHS["usb_charging"]: USB_CHARGING_VALUE["bool_"],
        PROBE_PATHS["startup_volume_enabled"]: (
            STARTUP_VOLUME_ENABLED_VALUE["bool_"]
        ),
        PROBE_PATHS["per_input_startup_volume_enabled"]: (
            PER_INPUT_STARTUP_VOLUME_ENABLED_VALUE["bool_"]
        ),
        PROBE_PATHS["default_volume_global"]: DEFAULT_VOLUME_GLOBAL_VALUE["i32_"],
        PROBE_PATHS["maximum_volume"]: MAXIMUM_VOLUME_VALUE["i32_"],
        PROBE_PATHS["volume_step"]: VOLUME_STEP_SETTING_VALUE["i16_"],
        PROBE_PATHS["volume_limit"]: VOLUME_LIMIT_VALUE["bool_"],
        PROBE_PATHS["fixed_volume_level"]: FIXED_VOLUME_LEVEL_VALUE["i32_"],
        **SOURCE_VOLUME_RESPONSES,
    }

    async def fake_get_value(self, path, *, typed_key=None):
        return responses[path]

    async def fake_get_optional_value(self, path, *, typed_key=None):
        return responses.get(path)

    monkeypatch.setattr(ModernKefClient, "_get_path_value", fake_get_value)
    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_value",
        fake_get_optional_value,
    )

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    snapshot = await client.async_refresh()

    assert snapshot.device.model == "MYSTERY"
    assert snapshot.source_list == (
        "wifi",
        "bluetooth",
        "tv",
        "optical",
        "coaxial",
        "analog",
        "usb",
    )


def test_lsxiilt_model_uses_the_limited_source_set() -> None:
    """Real LSX II LT firmware identifiers must not fall back to extra inputs."""
    assert ModernKefClient._source_list_for_model("LSXIILT") == (
        "wifi",
        "bluetooth",
        "tv",
        "optical",
        "usb",
    )


async def test_modern_optional_network_info_is_absent_when_unavailable(
    monkeypatch, hass
) -> None:
    """Missing network info should not break refreshes."""
    responses = {
        PROBE_PATHS["device_name"]: DEVICE_NAME_VALUE,
        PROBE_PATHS["version"]: VERSION_VALUE,
        PROBE_PATHS["release_text"]: RELEASE_TEXT_VALUE,
        PROBE_PATHS["mac"]: MAC_VALUE,
        PROBE_PATHS["model_code"]: MODEL_CODE_VALUE,
        PROBE_PATHS["speaker_status"]: SPEAKER_STATUS_VALUE["kefSpeakerStatus"],
        PROBE_PATHS["source"]: SOURCE_VALUE["kefPhysicalSource"],
        PROBE_PATHS["cable_mode"]: CABLE_MODE_VALUE["kefCableMode"],
        PROBE_PATHS["master_channel"]: MASTER_CHANNEL_VALUE["kefMasterChannelMode"],
        PROBE_PATHS["volume"]: VOLUME_VALUE["i32_"],
        PROBE_PATHS["mute"]: MUTE_VALUE["bool_"],
        PROBE_PATHS["play_mode"]: PLAY_MODE_VALUE["playerPlayMode"],
        PROBE_PATHS["firmware_update_status"]: FIRMWARE_UPDATE_STATUS_VALUE,
        PROBE_PATHS["player_data"]: PLAYER_DATA_VALUE,
        PROBE_PATHS["play_time"]: PLAY_TIME_VALUE["i64_"],
        PROBE_PATHS["eq_profile"]: EQ_PROFILE_VALUE,
        PROBE_PATHS["standby_mode"]: STANDBY_MODE_VALUE["kefStandbyMode"],
        PROBE_PATHS["startup_tone"]: STARTUP_TONE_VALUE["bool_"],
        PROBE_PATHS["auto_switch_hdmi"]: AUTO_SWITCH_HDMI_VALUE["bool_"],
        PROBE_PATHS["disable_front_led"]: DISABLE_FRONT_LED_VALUE["bool_"],
        PROBE_PATHS["disable_front_standby_led"]: (
            DISABLE_FRONT_STANDBY_LED_VALUE["bool_"]
        ),
        PROBE_PATHS["disable_top_panel"]: DISABLE_TOP_PANEL_VALUE["bool_"],
        PROBE_PATHS["wake_up_source"]: WAKE_UP_SOURCE_VALUE["kefWakeUpSource"],
        PROBE_PATHS["subwoofer_force_on"]: SUBWOOFER_FORCE_ON_VALUE["bool_"],
        PROBE_PATHS["subwoofer_force_on_kw1"]: (
            SUBWOOFER_FORCE_ON_KW1_VALUE["bool_"]
        ),
        PROBE_PATHS["usb_charging"]: USB_CHARGING_VALUE["bool_"],
        PROBE_PATHS["startup_volume_enabled"]: (
            STARTUP_VOLUME_ENABLED_VALUE["bool_"]
        ),
        PROBE_PATHS["per_input_startup_volume_enabled"]: (
            PER_INPUT_STARTUP_VOLUME_ENABLED_VALUE["bool_"]
        ),
        PROBE_PATHS["default_volume_global"]: DEFAULT_VOLUME_GLOBAL_VALUE["i32_"],
        PROBE_PATHS["maximum_volume"]: MAXIMUM_VOLUME_VALUE["i32_"],
        PROBE_PATHS["volume_step"]: VOLUME_STEP_SETTING_VALUE["i16_"],
        PROBE_PATHS["volume_limit"]: VOLUME_LIMIT_VALUE["bool_"],
        PROBE_PATHS["fixed_volume_level"]: FIXED_VOLUME_LEVEL_VALUE["i32_"],
        **SOURCE_VOLUME_RESPONSES,
    }

    async def fake_get_value(self, path, *, typed_key=None):
        return responses[path]

    async def fake_get_optional_value(self, path, *, typed_key=None):
        if path == PROBE_PATHS["network_info"]:
            return None
        return responses.get(path)

    monkeypatch.setattr(ModernKefClient, "_get_path_value", fake_get_value)
    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_value",
        fake_get_optional_value,
    )

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    snapshot = await client.async_refresh()

    assert snapshot.wifi_info is None


async def test_modern_set_standby_mode_posts_typed_payload(monkeypatch, hass) -> None:
    """Modern client should post a typed payload when setting standby mode."""
    captured = {}

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["json_payload"] = json_payload
        return {}

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_standby_mode("standby_20mins")

    assert captured == {
        "method": "POST",
        "endpoint": "/setData",
        "json_payload": {
            "path": "settings:/kef/host/standbyMode",
            "role": "value",
            "value": {
                "type": "kefStandbyMode",
                "kefStandbyMode": "standby_20mins",
            },
        },
    }


async def test_modern_set_wake_source_posts_typed_payload(monkeypatch, hass) -> None:
    """Modern client should post a typed payload when setting wake source."""
    captured = {}

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["json_payload"] = json_payload
        return {}

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_wake_source("wifi")

    assert captured == {
        "method": "POST",
        "endpoint": "/setData",
        "json_payload": {
            "path": "settings:/kef/host/wakeUpSource",
            "role": "value",
            "value": {
                "type": "kefWakeUpSource",
                "kefWakeUpSource": "wifi",
            },
        },
    }


async def test_modern_set_front_led_posts_typed_payload(monkeypatch, hass) -> None:
    """Modern client should post an inverted bool payload when setting front LED."""
    captured = {}

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["json_payload"] = json_payload
        return {}

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_front_led_enabled(True)

    assert captured == {
        "method": "POST",
        "endpoint": "/setData",
        "json_payload": {
            "path": "settings:/kef/host/disableFrontLED",
            "role": "value",
            "value": {"type": "bool_", "bool_": False},
        },
    }


async def test_modern_set_subwoofer_wake_posts_typed_payload(
    monkeypatch, hass
) -> None:
    """Modern client should post a bool payload for wired subwoofer wake."""
    captured = {}

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["json_payload"] = json_payload
        return {}

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_subwoofer_wake_enabled(True)

    assert captured == {
        "method": "POST",
        "endpoint": "/setData",
        "json_payload": {
            "path": "settings:/kef/host/subwooferForceOn",
            "role": "value",
            "value": {"type": "bool_", "bool_": True},
        },
    }


async def test_modern_set_kw1_wake_posts_typed_payload(monkeypatch, hass) -> None:
    """Modern client should post a bool payload for KW1 wake."""
    captured = {}

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["json_payload"] = json_payload
        return {}

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_kw1_wake_enabled(True)

    assert captured == {
        "method": "POST",
        "endpoint": "/setData",
        "json_payload": {
            "path": "settings:/kef/host/subwooferForceOnKW1",
            "role": "value",
            "value": {"type": "bool_", "bool_": True},
        },
    }


async def test_modern_set_default_volume_global_posts_typed_payload(
    monkeypatch, hass
) -> None:
    """Modern client should post a typed payload when setting startup volume."""
    captured = {}

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["json_payload"] = json_payload
        return {}

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_default_volume_global(35)

    assert captured == {
        "method": "POST",
        "endpoint": "/setData",
        "json_payload": {
            "path": "settings:/kef/host/defaultVolumeGlobal",
            "role": "value",
            "value": {"type": "i32_", "i32_": 35},
        },
    }


async def test_modern_set_volume_step_posts_typed_payload(monkeypatch, hass) -> None:
    """Modern client should post a typed payload when setting volume step."""
    captured = {}

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["json_payload"] = json_payload
        return {}

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_volume_step(2)

    assert captured == {
        "method": "POST",
        "endpoint": "/setData",
        "json_payload": {
            "path": "settings:/kef/host/volumeStep",
            "role": "value",
            "value": {"type": "i16_", "i16_": 2},
        },
    }


async def test_modern_set_volume_limit_posts_typed_payload(monkeypatch, hass) -> None:
    """Modern client should post a typed payload when toggling volume limit."""
    captured = {}

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["json_payload"] = json_payload
        return {}

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_volume_limit_enabled(True)

    assert captured == {
        "method": "POST",
        "endpoint": "/setData",
        "json_payload": {
            "path": "settings:/kef/host/volumeLimit",
            "role": "value",
            "value": {"type": "bool_", "bool_": True},
        },
    }


async def test_modern_set_source_volume_posts_typed_payload(monkeypatch, hass) -> None:
    """Modern client should post a typed payload for source startup volume."""
    captured = {}

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["json_payload"] = json_payload
        return {}

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_default_volume_for_source("usb", 35)

    assert captured == {
        "method": "POST",
        "endpoint": "/setData",
        "json_payload": {
            "path": "settings:/kef/host/defaultVolumeUSB",
            "role": "value",
            "value": {"type": "i32_", "i32_": 35},
        },
    }


async def test_modern_set_master_channel_posts_typed_payload(monkeypatch, hass) -> None:
    """Modern client should post a typed payload for master channel."""
    captured = {}

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["json_payload"] = json_payload
        return {}

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_master_channel("left")

    assert captured == {
        "method": "POST",
        "endpoint": "/setData",
        "json_payload": {
            "path": "settings:/kef/host/masterChannelMode",
            "role": "value",
            "value": {
                "type": "kefMasterChannelMode",
                "kefMasterChannelMode": "left",
            },
        },
    }


async def test_modern_set_cable_mode_posts_typed_payload(monkeypatch, hass) -> None:
    """Modern client should post a typed payload for cable mode."""
    captured = {}

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["json_payload"] = json_payload
        return {}

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_cable_mode("wireless")

    assert captured == {
        "method": "POST",
        "endpoint": "/setData",
        "json_payload": {
            "path": "settings:/kef/host/cableMode",
            "role": "value",
            "value": {
                "type": "kefCableMode",
                "kefCableMode": "wireless",
            },
        },
    }


async def test_modern_set_fixed_volume_level_posts_typed_payload(
    monkeypatch, hass
) -> None:
    """Modern client should post a typed payload for fixed volume."""
    captured = {}

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["json_payload"] = json_payload
        return {}

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_fixed_volume_level(29)

    assert captured == {
        "method": "POST",
        "endpoint": "/setData",
        "json_payload": {
            "path": "settings:/kef/host/remote/userFixedVolume",
            "role": "value",
            "value": {"type": "i32_", "i32_": 29},
        },
    }


async def test_modern_set_streaming_quality_posts_typed_payload(
    monkeypatch, hass
) -> None:
    """Modern client should post a typed payload for streaming quality."""
    captured = {}

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        captured["method"] = method
        captured["endpoint"] = endpoint
        captured["json_payload"] = json_payload
        return {}

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_streaming_quality("unlimited")

    assert captured == {
        "method": "POST",
        "endpoint": "/setData",
        "json_payload": {
            "path": "settings:/airable/bitrate",
            "role": "value",
            "value": {
                "type": "airableStreamBitrate",
                "airableStreamBitrate": "unlimited",
            },
        },
    }


async def test_modern_set_button_actions_post_typed_payloads(
    monkeypatch,
    hass,
) -> None:
    """Modern client should post typed payloads for remote button actions."""
    captured = []

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        captured.append((method, endpoint, json_payload))
        return {}

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_favourite_button_action("nextSource")
    await client.async_set_eq_button_action(1, "dialogue")
    await client.async_set_eq_button_action(2, "night")

    assert captured == [
        (
            "POST",
            "/setData",
            {
                "path": "settings:/kef/host/remote/favouriteButton",
                "role": "value",
                "value": {
                    "type": "kefFavouriteButtonFunction",
                    "kefFavouriteButtonFunction": "nextSource",
                },
            },
        ),
        (
            "POST",
            "/setData",
            {
                "path": "settings:/kef/host/remote/eqButton1",
                "role": "value",
                "value": {"type": "string_", "string_": "dialogue"},
            },
        ),
        (
            "POST",
            "/setData",
            {
                "path": "settings:/kef/host/remote/eqButton2",
                "role": "value",
                "value": {"type": "string_", "string_": "night"},
            },
        ),
    ]


async def test_modern_set_language_and_location_post_string_payloads(
    monkeypatch,
    hass,
) -> None:
    """Modern client should post string payloads for regional settings."""
    captured = []

    async def fake_request(self, method, endpoint, *, params=None, json_payload=None):
        captured.append((method, endpoint, json_payload))
        return {}

    monkeypatch.setattr(ModernKefClient, "_request_json", fake_request)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_ui_language("en_PL")
    await client.async_set_speaker_location("PL")

    assert captured == [
        (
            "POST",
            "/setData",
            {
                "path": "settings:/ui/language",
                "role": "value",
                "value": {"type": "string_", "string_": "en_PL"},
            },
        ),
        (
            "POST",
            "/setData",
            {
                "path": "settings:/kef/host/speakerLocation",
                "role": "value",
                "value": {"type": "string_", "string_": "PL"},
            },
        ),
    ]


async def test_modern_set_desk_mode_posts_typed_eq_wrapper(monkeypatch, hass) -> None:
    """Desk mode writes should round-trip through the typed EQ wrapper."""
    captured = {}

    async def fake_get_path_item(self, path, *, roles="value"):
        assert path == PROBE_PATHS["eq_profile"]
        return {
            "type": "kefEqProfile",
            "kefEqProfile": copy.deepcopy(EQ_PROFILE_VALUE["kefEqProfile"]),
        }

    async def fake_set_data(self, path, *, role, value):
        captured["path"] = path
        captured["role"] = role
        captured["value"] = value

    monkeypatch.setattr(ModernKefClient, "_get_path_item", fake_get_path_item)
    monkeypatch.setattr(ModernKefClient, "_set_data", fake_set_data)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_desk_mode_enabled(True)

    assert captured["path"] == PROBE_PATHS["eq_profile"]
    assert captured["role"] == "value"
    assert captured["value"]["type"] == "kefEqProfile"
    assert captured["value"]["kefEqProfile"]["dspInfo"]["deskMode"] is True


async def test_modern_set_balance_posts_typed_eq_wrapper(monkeypatch, hass) -> None:
    """Balance writes should update the typed EQ wrapper."""
    captured = {}

    async def fake_get_path_item(self, path, *, roles="value"):
        assert path == PROBE_PATHS["eq_profile"]
        return {
            "type": "kefEqProfile",
            "kefEqProfile": copy.deepcopy(EQ_PROFILE_VALUE["kefEqProfile"]),
        }

    async def fake_set_data(self, path, *, role, value):
        captured["path"] = path
        captured["role"] = role
        captured["value"] = value

    monkeypatch.setattr(ModernKefClient, "_get_path_item", fake_get_path_item)
    monkeypatch.setattr(ModernKefClient, "_set_data", fake_set_data)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_balance(15)

    assert captured["value"]["kefEqProfile"]["dspInfo"]["balance"] == 45


@pytest.mark.parametrize(
    ("method", "native_value", "wire_key", "expected_wire_value"),
    [
        ("async_set_balance", -1, "balance", 29),
        ("async_set_treble_amount", 0.25, "trebleAmount", 9),
        ("async_set_subwoofer_gain", -2, "subwooferGain", 8),
        ("async_set_high_pass_frequency", 95, "highPassModeFreq", 9),
        ("async_set_sub_out_low_pass_frequency", 80, "subOutLPFreq", 8),
        ("async_set_desk_mode_db", -3, "deskModeSetting", 14),
        ("async_set_wall_mode_db", -3.5, "wallModeSetting", 13),
        ("async_set_kw1_enabled", True, "isKW1", True),
    ],
)
async def test_modern_v1_eq_writes_translate_native_units(
    monkeypatch,
    hass,
    method,
    native_value,
    wire_key,
    expected_wire_value,
) -> None:
    """Physical HA units should be translated to the v1 EQ wire scale."""
    captured = {}
    original_dsp_info = copy.deepcopy(EQ_PROFILE_VALUE["kefEqProfile"]["dspInfo"])

    async def fake_get_optional_path_item(self, path, *, roles="value"):
        assert path == PROBE_PATHS["eq_profile"]
        return {
            "type": "kefEqProfile",
            "kefEqProfile": copy.deepcopy(EQ_PROFILE_VALUE["kefEqProfile"]),
        }

    async def fake_set_data(self, path, *, role, value):
        captured["path"] = path
        captured["role"] = role
        captured["value"] = value

    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_item",
        fake_get_optional_path_item,
    )
    monkeypatch.setattr(ModernKefClient, "_set_data", fake_set_data)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await getattr(client, method)(native_value)

    assert captured["path"] == PROBE_PATHS["eq_profile"]
    assert captured["role"] == "value"
    dsp_info = captured["value"]["kefEqProfile"]["dspInfo"]
    expected_dsp_info = copy.deepcopy(original_dsp_info)
    expected_dsp_info[wire_key] = expected_wire_value
    assert dsp_info == expected_dsp_info


@pytest.mark.parametrize(
    ("method", "requested", "wire_key", "expected_applied"),
    [
        ("async_set_treble_amount", 1.4, "trebleAmount", 1.5),
        ("async_set_desk_mode_db", -3.6, "deskModeSetting", -3.5),
        ("async_set_wall_mode_db", -3.6, "wallModeSetting", -3.5),
        ("async_set_high_pass_frequency", 67.5, "highPassModeFreq", 70.0),
        (
            "async_set_sub_out_low_pass_frequency",
            57.5,
            "subOutLPFreq",
            60.0,
        ),
    ],
)
async def test_modern_v1_eq_writes_return_representable_value(
    monkeypatch,
    hass,
    method,
    requested,
    wire_key,
    expected_applied,
) -> None:
    """EQ setters should return the physical value encoded on a v1 speaker."""

    async def fake_get_optional_path_item(self, path, *, roles="value"):
        assert path == PROBE_PATHS["eq_profile"]
        return copy.deepcopy(EQ_PROFILE_VALUE)

    async def fake_set_data(self, path, *, role, value):
        return None

    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_item",
        fake_get_optional_path_item,
    )
    monkeypatch.setattr(ModernKefClient, "_set_data", fake_set_data)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))

    applied = await getattr(client, method)(requested)

    assert applied[wire_key] == expected_applied


async def test_modern_eq_writes_are_serialized(monkeypatch, hass) -> None:
    """Concurrent full-profile writes must preserve both requested changes."""
    device_profile = copy.deepcopy(EQ_PROFILE_V2_VALUE)
    first_read_started = asyncio.Event()
    release_first_read = asyncio.Event()
    read_count = 0

    async def fake_get_optional_path_item(self, path, *, roles="value"):
        assert path == PROBE_PATHS["eq_profile"]
        return None

    async def fake_get_path_item(self, path, *, roles="value"):
        nonlocal read_count
        assert path == PROBE_PATHS["eq_profile_v2"]
        read_count += 1
        snapshot = copy.deepcopy(device_profile)
        if read_count == 1:
            first_read_started.set()
            await release_first_read.wait()
        return snapshot

    async def fake_set_data(self, path, *, role, value):
        nonlocal device_profile
        assert path == PROBE_PATHS["eq_profile_v2"]
        device_profile = copy.deepcopy(value)

    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_item",
        fake_get_optional_path_item,
    )
    monkeypatch.setattr(ModernKefClient, "_get_path_item", fake_get_path_item)
    monkeypatch.setattr(ModernKefClient, "_set_data", fake_set_data)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    desk_task = asyncio.create_task(client.async_set_desk_mode_enabled(True))
    await first_read_started.wait()
    wall_task = asyncio.create_task(client.async_set_wall_mode_enabled(True))
    await asyncio.sleep(0)
    release_first_read.set()
    await asyncio.gather(desk_task, wall_task)

    written = device_profile["kefEqProfileV2"]
    assert written["deskMode"] is True
    assert written["wallMode"] is True
    assert read_count == 2


async def test_modern_v1_eq_write_preserves_noncanonical_unrelated_fields(
    monkeypatch,
    hass,
) -> None:
    """A v1 write should leave every unrelated wire value exactly unchanged."""
    captured = {}
    original_dsp_info = copy.deepcopy(EQ_PROFILE_VALUE["kefEqProfile"]["dspInfo"])
    original_dsp_info["trebleAmount"] = 8.5
    original_dsp_info["subOutLPFreq"] = None
    original_dsp_info["futureFirmwareCode"] = {"value": 999}
    original_dsp_info.pop("wallModeSetting")

    async def fake_get_optional_path_item(self, path, *, roles="value"):
        assert path == PROBE_PATHS["eq_profile"]
        return {
            "type": "kefEqProfile",
            "kefEqProfile": {
                **copy.deepcopy(EQ_PROFILE_VALUE["kefEqProfile"]),
                "dspInfo": copy.deepcopy(original_dsp_info),
            },
        }

    async def fake_set_data(self, path, *, role, value):
        captured["value"] = value

    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_item",
        fake_get_optional_path_item,
    )
    monkeypatch.setattr(ModernKefClient, "_set_data", fake_set_data)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_balance(-1)

    expected_dsp_info = copy.deepcopy(original_dsp_info)
    expected_dsp_info["balance"] = 29
    assert captured["value"]["kefEqProfile"]["dspInfo"] == expected_dsp_info


async def test_modern_set_bass_extension_posts_typed_eq_wrapper(
    monkeypatch, hass
) -> None:
    """Bass-extension writes should update the typed EQ wrapper."""
    captured = {}

    async def fake_get_path_item(self, path, *, roles="value"):
        assert path == PROBE_PATHS["eq_profile"]
        return {
            "type": "kefEqProfile",
            "kefEqProfile": copy.deepcopy(EQ_PROFILE_VALUE["kefEqProfile"]),
        }

    async def fake_set_data(self, path, *, role, value):
        captured["path"] = path
        captured["role"] = role
        captured["value"] = value

    monkeypatch.setattr(ModernKefClient, "_get_path_item", fake_get_path_item)
    monkeypatch.setattr(ModernKefClient, "_set_data", fake_set_data)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_bass_extension("extra")

    assert captured["value"]["kefEqProfile"]["dspInfo"]["bassExtension"] == "extra"


async def test_modern_refresh_falls_back_to_eq_profile_v2(
    monkeypatch,
    hass,
) -> None:
    """Modern client should parse the newer v2 EQ profile when v1 is absent."""
    responses = {
        PROBE_PATHS["device_name"]: DEVICE_NAME_VALUE,
        PROBE_PATHS["version"]: VERSION_VALUE,
        PROBE_PATHS["release_text"]: RELEASE_TEXT_VALUE,
        PROBE_PATHS["mac"]: MAC_VALUE,
        PROBE_PATHS["model_code"]: MODEL_CODE_VALUE,
        PROBE_PATHS["speaker_status"]: SPEAKER_STATUS_VALUE["kefSpeakerStatus"],
        PROBE_PATHS["source"]: SOURCE_VALUE["kefPhysicalSource"],
        PROBE_PATHS["volume"]: VOLUME_VALUE["i32_"],
        PROBE_PATHS["mute"]: MUTE_VALUE["bool_"],
        PROBE_PATHS["play_mode"]: PLAY_MODE_VALUE["playerPlayMode"],
        PROBE_PATHS["eq_profile_v2"]: EQ_PROFILE_V2_VALUE,
        PROBE_PATHS["calibration_status"]: {
            "kefDspCalibrationStatus": {
                "isCalibrated": True,
                "year": 2026,
                "month": 9,
                "day": 16,
                "stability": 95,
            }
        },
        PROBE_PATHS["calibration_result"]: {"double_": -2.5},
    }

    async def fake_get_path_value(self, path, *, typed_key=None):
        if path == PROBE_PATHS["eq_profile"]:
            raise KefResponseError("missing")
        if path not in responses:
            raise KefResponseError("missing")
        value = responses[path]
        if typed_key is None:
            return value
        if isinstance(value, dict):
            return value.get(typed_key)
        return value

    monkeypatch.setattr(ModernKefClient, "_get_path_value", fake_get_path_value)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    snapshot = await client.async_refresh()

    assert snapshot.eq_profile is not None
    assert snapshot.eq_profile.api_version == "v2"
    assert snapshot.eq_profile.balance == 0
    assert snapshot.eq_profile.treble_amount == 0
    assert snapshot.eq_profile.subwoofer_gain == 0
    assert snapshot.eq_profile.high_pass_frequency == 95
    assert snapshot.eq_profile.desk_mode_setting == -3
    assert snapshot.eq_profile.wall_mode_setting == -3
    assert snapshot.eq_profile.sub_out_low_pass_frequency == 80
    assert snapshot.eq_profile.sound_profile == "default"
    assert snapshot.calibration_status is not None
    assert snapshot.calibration_status.is_calibrated is True
    assert snapshot.calibration_status.year == 2026
    assert snapshot.calibration_status.month == 9
    assert snapshot.calibration_status.day == 16
    assert snapshot.calibration_status.stability == 95
    assert snapshot.calibration_result == -2.5


async def test_modern_set_subwoofer_preset_updates_complete_v2_profile(
    monkeypatch,
    hass,
) -> None:
    """A known preset should atomically update its label and tuning values."""
    captured = {}
    profile = copy.deepcopy(EQ_PROFILE_V2_VALUE)
    profile_value = profile["kefEqProfileV2"]
    profile_value["isKW1"] = False
    profile_value["subwooferCount"] = 1
    profile_value["futureFirmwareCode"] = {"value": 999}

    async def fake_get_optional_path_item(self, path, *, roles="value"):
        assert path == PROBE_PATHS["eq_profile"]
        return None

    async def fake_get_path_item(self, path, *, roles="value"):
        assert path == PROBE_PATHS["eq_profile_v2"]
        return copy.deepcopy(profile)

    async def fake_set_data(self, path, *, role, value):
        captured["path"] = path
        captured["role"] = role
        captured["value"] = value

    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_item",
        fake_get_optional_path_item,
    )
    monkeypatch.setattr(ModernKefClient, "_get_path_item", fake_get_path_item)
    monkeypatch.setattr(ModernKefClient, "_set_data", fake_set_data)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    applied = await client.async_set_subwoofer_preset("kc62", "XIO")

    assert applied == {"gain": -1.0, "lowpass": 55.0, "highpass": 67.5}
    assert captured["path"] == PROBE_PATHS["eq_profile_v2"]
    assert captured["role"] == "value"
    updated = captured["value"]["kefEqProfileV2"]
    assert updated["subwooferPreset"] == "kc62"
    assert updated["subwooferGain"] == -1.0
    assert updated["subOutLPFreq"] == 55.0
    assert updated["highPassModeFreq"] == 67.5
    assert updated["futureFirmwareCode"] == {"value": 999}

    applied["gain"] = 999
    assert await client.async_set_subwoofer_preset("kc62", "XIO") == {
        "gain": -1.0,
        "lowpass": 55.0,
        "highpass": 67.5,
    }


@pytest.mark.parametrize("model", ["LSX2", "LSXII", "LSX2LT", "LSXIILT"])
async def test_subwoofer_preset_table_supports_observed_lsx_aliases(
    monkeypatch,
    hass,
    model,
) -> None:
    """Equivalent LSX II model identifiers should apply the same preset."""
    profile = copy.deepcopy(EQ_PROFILE_V2_VALUE)
    profile["kefEqProfileV2"]["isKW1"] = False
    profile["kefEqProfileV2"]["subwooferCount"] = 1

    async def fake_get_optional_path_item(self, path, *, roles="value"):
        return None

    async def fake_get_path_item(self, path, *, roles="value"):
        return copy.deepcopy(profile)

    async def fake_set_data(self, path, *, role, value):
        return None

    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_item",
        fake_get_optional_path_item,
    )
    monkeypatch.setattr(ModernKefClient, "_get_path_item", fake_get_path_item)
    monkeypatch.setattr(ModernKefClient, "_set_data", fake_set_data)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))

    assert await client.async_set_subwoofer_preset("kc62", model) == {
        "gain": -1.0,
        "lowpass": 55.0,
        "highpass": 67.5,
    }


@pytest.mark.parametrize(
    ("method_name", "input_value", "wire_key", "expected_value"),
    [
        ("async_set_subwoofer_gain", -2, "subwooferGain", -2),
        (
            "async_set_sub_out_low_pass_frequency",
            57.5,
            "subOutLPFreq",
            57.5,
        ),
        ("async_set_high_pass_frequency", 65.0, "highPassModeFreq", 65.0),
    ],
)
async def test_manual_subwoofer_tuning_resets_named_preset(
    monkeypatch,
    hass,
    method_name,
    input_value,
    wire_key,
    expected_value,
) -> None:
    """Manual tuning must stop advertising a preset the values no longer match."""
    captured = {}
    profile = copy.deepcopy(EQ_PROFILE_V2_VALUE)
    profile["kefEqProfileV2"]["subwooferPreset"] = "kc62"
    profile["kefEqProfileV2"]["futureFirmwareCode"] = {"value": 999}

    async def fake_get_optional_path_item(self, path, *, roles="value"):
        return None

    async def fake_get_path_item(self, path, *, roles="value"):
        return copy.deepcopy(profile)

    async def fake_set_data(self, path, *, role, value):
        captured["value"] = value

    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_item",
        fake_get_optional_path_item,
    )
    monkeypatch.setattr(ModernKefClient, "_get_path_item", fake_get_path_item)
    monkeypatch.setattr(ModernKefClient, "_set_data", fake_set_data)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await getattr(client, method_name)(input_value)

    updated = captured["value"]["kefEqProfileV2"]
    assert updated[wire_key] == expected_value
    assert updated["subwooferPreset"] == "custom"
    assert updated["futureFirmwareCode"] == {"value": 999}


@pytest.mark.parametrize(
    ("method_name", "input_value", "wire_key"),
    [
        ("async_set_subwoofer_polarity", "inverted", "subwooferPolarity"),
        ("async_set_audio_polarity", "inverted", "audioPolarity"),
        ("async_set_sub_enable_stereo", True, "subEnableStereo"),
        ("async_set_sound_profile", "movie", "soundProfile"),
    ],
)
async def test_new_eq_setters_preserve_v2_profile_fields(
    monkeypatch,
    hass,
    method_name,
    input_value,
    wire_key,
) -> None:
    """New EQ setters should change one field without dropping future data."""
    captured = {}
    profile = copy.deepcopy(EQ_PROFILE_V2_VALUE)
    profile["kefEqProfileV2"]["futureFirmwareCode"] = {"value": 999}

    async def fake_get_optional_path_item(self, path, *, roles="value"):
        return None

    async def fake_get_path_item(self, path, *, roles="value"):
        return copy.deepcopy(profile)

    async def fake_set_data(self, path, *, role, value):
        captured["value"] = value

    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_item",
        fake_get_optional_path_item,
    )
    monkeypatch.setattr(ModernKefClient, "_get_path_item", fake_get_path_item)
    monkeypatch.setattr(ModernKefClient, "_set_data", fake_set_data)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await getattr(client, method_name)(input_value)

    updated = captured["value"]["kefEqProfileV2"]
    assert updated[wire_key] == input_value
    assert updated["futureFirmwareCode"] == {"value": 999}


@pytest.mark.parametrize(
    ("method_name", "input_value", "wire_key"),
    [
        ("async_set_subwoofer_polarity", "inverted", "subwooferPolarity"),
        ("async_set_audio_polarity", "inverted", "audioPolarity"),
        ("async_set_sub_enable_stereo", True, "subEnableStereo"),
    ],
)
async def test_new_eq_setters_preserve_v1_profile_fields(
    monkeypatch,
    hass,
    method_name,
    input_value,
    wire_key,
) -> None:
    """Features present in v1 should preserve that profile's wire contract."""
    captured = {}
    profile = copy.deepcopy(EQ_PROFILE_VALUE)
    profile["kefEqProfile"]["dspInfo"]["futureFirmwareCode"] = {"value": 999}

    async def fake_get_optional_path_item(self, path, *, roles="value"):
        return copy.deepcopy(profile)

    async def fake_set_data(self, path, *, role, value):
        captured["value"] = value

    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_item",
        fake_get_optional_path_item,
    )
    monkeypatch.setattr(ModernKefClient, "_set_data", fake_set_data)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await getattr(client, method_name)(input_value)

    updated = captured["value"]["kefEqProfile"]["dspInfo"]
    assert updated[wire_key] == input_value
    assert updated["futureFirmwareCode"] == {"value": 999}


async def test_unknown_model_preset_updates_v1_label_without_guessing_values(
    monkeypatch,
    hass,
) -> None:
    """Models without a verified table should retain all existing v1 tuning."""
    captured = {}
    profile = copy.deepcopy(EQ_PROFILE_VALUE)
    original_dsp = copy.deepcopy(profile["kefEqProfile"]["dspInfo"])

    async def fake_get_optional_path_item(self, path, *, roles="value"):
        return copy.deepcopy(profile)

    async def fake_set_data(self, path, *, role, value):
        captured["value"] = value

    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_item",
        fake_get_optional_path_item,
    )
    monkeypatch.setattr(ModernKefClient, "_set_data", fake_set_data)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    applied = await client.async_set_subwoofer_preset("kc62", "LS50WII")

    assert applied is None
    updated = captured["value"]["kefEqProfile"]["dspInfo"]
    assert updated["subwooferPreset"] == "kc62"
    original_dsp["subwooferPreset"] = "kc62"
    assert updated == original_dsp


async def test_known_model_preset_reports_v1_quantized_values(
    monkeypatch,
    hass,
) -> None:
    """Optimistic v1 values should match what its coarse wire format can store."""
    captured = {}
    profile = copy.deepcopy(EQ_PROFILE_VALUE)
    profile["kefEqProfile"]["dspInfo"]["isKW1"] = False
    profile["kefEqProfile"]["dspInfo"]["subwooferCount"] = 1

    async def fake_get_optional_path_item(self, path, *, roles="value"):
        return copy.deepcopy(profile)

    async def fake_set_data(self, path, *, role, value):
        captured["value"] = value

    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_item",
        fake_get_optional_path_item,
    )
    monkeypatch.setattr(ModernKefClient, "_set_data", fake_set_data)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    applied = await client.async_set_subwoofer_preset("kc62", "LSXII")

    assert applied == {"gain": -1.0, "lowpass": 60.0, "highpass": 70.0}
    updated = captured["value"]["kefEqProfile"]["dspInfo"]
    assert updated["subwooferGain"] == 9
    assert updated["subOutLPFreq"] == 6
    assert updated["highPassModeFreq"] == 4


async def test_modern_start_calibration_activates_xio_path(
    monkeypatch,
    hass,
) -> None:
    """Starting calibration should use the activate role on the XIO path."""
    captured = {}

    async def fake_activate_path(self, path, value=None):
        captured["path"] = path
        captured["value"] = value

    monkeypatch.setattr(ModernKefClient, "_activate_path", fake_activate_path)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_start_calibration()

    assert captured == {"path": PROBE_PATHS["calibration_start"], "value": None}


async def test_modern_calibration_getters_decode_typed_values(
    monkeypatch,
    hass,
) -> None:
    """Direct calibration getters should unwrap their typed API payloads."""
    calibration_status = {
        "isCalibrated": True,
        "year": 2026,
        "month": 9,
        "day": 16,
        "stability": 95,
    }

    async def fake_get_optional_path_item(self, path, *, roles="value"):
        if path == PROBE_PATHS["calibration_status"]:
            return {"kefDspCalibrationStatus": calibration_status}
        if path == PROBE_PATHS["calibration_result"]:
            return {"double_": -2.5}
        raise AssertionError(f"Unexpected path: {path}")

    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_item",
        fake_get_optional_path_item,
    )

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))

    assert await client.async_get_calibration_status() == calibration_status
    assert await client.async_get_calibration_result() == -2.5


async def test_modern_set_treble_updates_eq_profile_v2(
    monkeypatch,
    hass,
) -> None:
    """Modern client should write v2 EQ payloads when v1 is absent."""
    captured = {}

    async def fake_get_optional_path_item(self, path, *, roles="value"):
        assert path == PROBE_PATHS["eq_profile"]
        return None

    async def fake_get_path_item(self, path, *, roles="value"):
        assert path == PROBE_PATHS["eq_profile_v2"]
        return copy.deepcopy(EQ_PROFILE_V2_VALUE)

    async def fake_set_data(self, path, *, role, value):
        captured["path"] = path
        captured["role"] = role
        captured["value"] = value

    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_item",
        fake_get_optional_path_item,
    )
    monkeypatch.setattr(ModernKefClient, "_get_path_item", fake_get_path_item)
    monkeypatch.setattr(ModernKefClient, "_set_data", fake_set_data)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_treble_amount(8)

    assert captured["path"] == PROBE_PATHS["eq_profile_v2"]
    assert captured["role"] == "value"
    assert captured["value"]["type"] == "kefEqProfileV2"
    assert captured["value"]["kefEqProfileV2"]["trebleAmount"] == 3.0


@pytest.mark.parametrize(
    ("initial_count", "enabled", "expected_count"),
    [(0, True, 1), (2, True, 2), (2, False, 0)],
)
async def test_modern_set_subwoofer_updates_v2_profile_without_losing_count(
    monkeypatch,
    hass,
    initial_count,
    enabled,
    expected_count,
) -> None:
    """Subwoofer toggles should preserve an existing positive speaker count."""
    captured = {}
    profile = copy.deepcopy(EQ_PROFILE_V2_VALUE)
    profile["kefEqProfileV2"]["subwooferCount"] = initial_count

    async def fake_get_optional_path_item(self, path, *, roles="value"):
        assert path == PROBE_PATHS["eq_profile"]
        return None

    async def fake_get_path_item(self, path, *, roles="value"):
        assert path == PROBE_PATHS["eq_profile_v2"]
        return copy.deepcopy(profile)

    async def fake_set_data(self, path, *, role, value):
        captured["path"] = path
        captured["role"] = role
        captured["value"] = value

    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_item",
        fake_get_optional_path_item,
    )
    monkeypatch.setattr(ModernKefClient, "_get_path_item", fake_get_path_item)
    monkeypatch.setattr(ModernKefClient, "_set_data", fake_set_data)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_subwoofer_enabled(enabled)

    assert captured["path"] == PROBE_PATHS["eq_profile_v2"]
    assert captured["role"] == "value"
    written_profile = captured["value"]["kefEqProfileV2"]
    assert written_profile["subwooferOut"] is enabled
    assert written_profile["subwooferCount"] == expected_count


@pytest.mark.parametrize(
    ("initial_count", "enabled", "expected_count"),
    [(0, True, 1), (2, True, 2), (2, False, 0)],
)
async def test_modern_set_subwoofer_updates_v1_count_without_v2_field(
    monkeypatch,
    hass,
    initial_count,
    enabled,
    expected_count,
) -> None:
    """The v1 subwoofer control should only use its supported count field."""
    captured = {}
    eq_profile = copy.deepcopy(EQ_PROFILE_VALUE)
    dsp_info = eq_profile["kefEqProfile"]["dspInfo"]
    dsp_info["subwooferCount"] = initial_count

    async def fake_get_optional_path_item(self, path, *, roles="value"):
        assert path == PROBE_PATHS["eq_profile"]
        return copy.deepcopy(eq_profile)

    async def fake_set_data(self, path, *, role, value):
        captured["path"] = path
        captured["role"] = role
        captured["value"] = value

    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_item",
        fake_get_optional_path_item,
    )
    monkeypatch.setattr(ModernKefClient, "_set_data", fake_set_data)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_subwoofer_enabled(enabled)

    expected_dsp_info = copy.deepcopy(dsp_info)
    expected_dsp_info["subwooferCount"] = expected_count
    written_dsp_info = captured["value"]["kefEqProfile"]["dspInfo"]
    assert captured["path"] == PROBE_PATHS["eq_profile"]
    assert captured["role"] == "value"
    assert "subwooferOut" not in written_dsp_info
    assert written_dsp_info == expected_dsp_info


async def test_modern_set_kw1_updates_v2_profile(monkeypatch, hass) -> None:
    """The KW1 switch should update the v2 EQ profile without other changes."""
    captured = {}

    async def fake_get_optional_path_item(self, path, *, roles="value"):
        assert path == PROBE_PATHS["eq_profile"]
        return None

    async def fake_get_path_item(self, path, *, roles="value"):
        assert path == PROBE_PATHS["eq_profile_v2"]
        return copy.deepcopy(EQ_PROFILE_V2_VALUE)

    async def fake_set_data(self, path, *, role, value):
        captured["value"] = value

    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_item",
        fake_get_optional_path_item,
    )
    monkeypatch.setattr(ModernKefClient, "_get_path_item", fake_get_path_item)
    monkeypatch.setattr(ModernKefClient, "_set_data", fake_set_data)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_set_kw1_enabled(True)

    expected_profile = copy.deepcopy(EQ_PROFILE_V2_VALUE["kefEqProfileV2"])
    expected_profile["isKW1"] = True
    assert captured["value"]["kefEqProfileV2"] == expected_profile


async def test_modern_get_firmware_update_status_parses_payload(
    monkeypatch, hass
) -> None:
    """Firmware update status should be parsed into a typed model."""

    async def fake_get_optional_value(self, path, *, typed_key=None):
        assert path == PROBE_PATHS["firmware_update_status"]
        return FIRMWARE_UPDATE_STATUS_VALUE

    monkeypatch.setattr(
        ModernKefClient,
        "_get_optional_path_value",
        fake_get_optional_value,
    )

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    status = await client.async_get_firmware_update_status()

    assert status is not None
    assert status.state == "newUpdateAvailable"
    assert status.available_version == "3.0.135.0x60acbcf"
    assert status.is_available is True


async def test_modern_check_for_firmware_update_activates_path(
    monkeypatch, hass
) -> None:
    """Checking for updates should trigger the activate endpoint and poll status."""
    calls = []

    async def fake_activate(self, path, value=None):
        calls.append(("activate", path, value))
        return {}

    async def fake_poll(self, *, attempts=10, delay_seconds=1.0):
        calls.append(("poll", attempts, delay_seconds))
        return None

    monkeypatch.setattr(ModernKefClient, "_activate_path", fake_activate)
    monkeypatch.setattr(ModernKefClient, "_poll_firmware_update_status", fake_poll)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_check_for_firmware_update()

    assert calls[0] == ("activate", "firmwareupdate:checkForUpdate", None)
    assert calls[1][0] == "poll"


async def test_modern_check_for_firmware_update_polls_after_activation_timeout(
    monkeypatch, hass
) -> None:
    """Timed-out firmware check activations should still poll status."""
    calls = []

    async def fake_activate(self, path, value=None):
        calls.append(("activate", path, value))
        raise KefConnectionError("timeout")

    async def fake_poll(self, *, attempts=10, delay_seconds=1.0):
        calls.append(("poll", attempts, delay_seconds))
        return None

    monkeypatch.setattr(ModernKefClient, "_activate_path", fake_activate)
    monkeypatch.setattr(ModernKefClient, "_poll_firmware_update_status", fake_poll)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_check_for_firmware_update()

    assert calls[0] == ("activate", "firmwareupdate:checkForUpdate", None)
    assert calls[1][0] == "poll"


async def test_modern_firmware_poll_waits_through_download_state(
    monkeypatch, hass
) -> None:
    """Firmware polling should keep waiting while download is still in progress."""
    states = [
        type("Status", (), {"state": "checkingForUpdate"})(),
        type("Status", (), {"state": "downloading"})(),
        type("Status", (), {"state": "downloaded"})(),
    ]
    calls = []

    async def fake_status(self):
        calls.append("status")
        return states.pop(0)

    async def fake_sleep(delay):
        calls.append(("sleep", delay))

    monkeypatch.setattr(
        ModernKefClient,
        "async_get_firmware_update_status",
        fake_status,
    )
    monkeypatch.setattr(
        "custom_components.kef.kef_client.client.asyncio.sleep",
        fake_sleep,
    )

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    status = await client._poll_firmware_update_status(
        attempts=3,
        delay_seconds=0.1,
    )

    assert status.state == "downloaded"
    assert calls == ["status", ("sleep", 0.1), "status", ("sleep", 0.1), "status"]


async def test_modern_install_firmware_update_tries_primary_endpoint(
    monkeypatch, hass
) -> None:
    """Installing firmware should trigger the online-update download path."""
    calls = []

    async def fake_status(self):
        return None

    async def fake_check(self):
        return type(
            "Status",
            (),
            {"state": "newUpdateAvailable", "is_available": True},
        )()

    async def fake_activate(self, path, value=None):
        calls.append((path, value))
        return {}

    async def fake_poll(self, *, attempts=10, delay_seconds=1.0):
        calls.append(("poll", attempts))
        return None

    monkeypatch.setattr(
        ModernKefClient,
        "async_get_firmware_update_status",
        fake_status,
    )
    monkeypatch.setattr(ModernKefClient, "async_check_for_firmware_update", fake_check)
    monkeypatch.setattr(ModernKefClient, "_activate_path", fake_activate)
    monkeypatch.setattr(ModernKefClient, "_poll_firmware_update_status", fake_poll)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_install_firmware_update()

    assert calls[0] == ("firmwareupdate:downloadNewUpdate", None)
    assert calls[1] == ("poll", 120)


async def test_modern_install_firmware_update_installs_after_download(
    monkeypatch, hass
) -> None:
    """Installing firmware should continue from download to install."""
    calls = []

    async def fake_status(self):
        return None

    async def fake_check(self):
        return type(
            "Status",
            (),
            {"state": "newUpdateAvailable", "is_available": True},
        )()

    async def fake_activate(self, path, value=None):
        calls.append((path, value))
        return {}

    async def fake_poll(self, *, attempts=10, delay_seconds=1.0):
        calls.append(("poll", attempts))
        if attempts == 120:
            return type("Status", (), {"state": "downloaded"})()
        return type("Status", (), {"state": "installing"})()

    monkeypatch.setattr(
        ModernKefClient,
        "async_get_firmware_update_status",
        fake_status,
    )
    monkeypatch.setattr(ModernKefClient, "async_check_for_firmware_update", fake_check)
    monkeypatch.setattr(ModernKefClient, "_activate_path", fake_activate)
    monkeypatch.setattr(ModernKefClient, "_poll_firmware_update_status", fake_poll)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_install_firmware_update()

    assert calls == [
        ("firmwareupdate:downloadNewUpdate", None),
        ("poll", 120),
        (
            "firmwareupdate:installUpdate",
            {"firmwareUpdateOptions": {"forceSfupdate": True}},
        ),
        ("poll", 10),
    ]


async def test_modern_install_firmware_update_waits_for_pending_download(
    monkeypatch, hass
) -> None:
    """Installing firmware should continue when download is already active."""
    calls = []

    async def fake_status(self):
        return type(
            "Status",
            (),
            {"state": "downloadingUpdate", "is_available": False},
        )()

    async def fake_activate(self, path, value=None):
        calls.append((path, value))
        return {}

    async def fake_poll(self, *, attempts=10, delay_seconds=1.0):
        calls.append(("poll", attempts))
        if attempts == 120:
            return type("Status", (), {"state": "downloaded"})()
        return type("Status", (), {"state": "installing"})()

    monkeypatch.setattr(
        ModernKefClient,
        "async_get_firmware_update_status",
        fake_status,
    )
    monkeypatch.setattr(ModernKefClient, "_activate_path", fake_activate)
    monkeypatch.setattr(ModernKefClient, "_poll_firmware_update_status", fake_poll)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    await client.async_install_firmware_update()

    assert calls == [
        ("poll", 120),
        (
            "firmwareupdate:installUpdate",
            {"firmwareUpdateOptions": {"forceSfupdate": True}},
        ),
        ("poll", 10),
    ]


async def test_modern_upload_firmware_update_detects_auth_redirect(
    monkeypatch, tmp_path
) -> None:
    """Firmware upload redirects to login should surface as auth failures."""

    class FakeResponse:
        status = 302
        headers = {"Location": "/login.fcgi"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def text(self):
            return ""

    class FakeSession:
        def post(self, url, *, data, allow_redirects, timeout):
            assert allow_redirects is False
            return FakeResponse()

    async def fake_poll(self, *, attempts=10, delay_seconds=1.0):
        raise AssertionError("auth redirects must fail before polling")

    monkeypatch.setattr(ModernKefClient, "_poll_firmware_update_status", fake_poll)

    firmware_file = tmp_path / "firmware.swu"
    firmware_file.write_bytes(b"firmware")

    client = ModernKefClient(TEST_HOST, FakeSession())

    with pytest.raises(KefAuthenticationRequiredError):
        await client.async_upload_firmware_update(str(firmware_file))


async def test_modern_upload_firmware_update_opens_file_in_executor(
    monkeypatch, tmp_path
) -> None:
    """Firmware uploads should not open local files on the event loop."""

    class FakeResponse:
        status = 302
        headers = {"Location": "/login.fcgi"}

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return None

        async def text(self):
            return ""

    class FakeSession:
        def post(self, url, *, data, allow_redirects, timeout):
            return FakeResponse()

    async def fake_poll(self, *, attempts=10, delay_seconds=1.0):
        raise AssertionError("auth redirects must fail before polling")

    calls = []

    async def fake_executor(func, *args):
        calls.append((func, args))
        return func(*args)

    monkeypatch.setattr(ModernKefClient, "_poll_firmware_update_status", fake_poll)

    firmware_file = tmp_path / "firmware.swu"
    firmware_file.write_bytes(b"firmware")

    client = ModernKefClient(
        TEST_HOST,
        FakeSession(),
        async_add_executor_job=fake_executor,
    )

    with pytest.raises(KefAuthenticationRequiredError):
        await client.async_upload_firmware_update(str(firmware_file))

    assert calls == [(builtins.open, (str(firmware_file), "rb"))]


async def test_modern_upload_firmware_update_wraps_file_open_errors(
    tmp_path,
) -> None:
    """Missing firmware files should raise integration-level KEF errors."""
    client = ModernKefClient(TEST_HOST, object())

    with pytest.raises(KefConnectionError):
        await client.async_upload_firmware_update(str(tmp_path / "missing.swu"))


async def test_modern_request_json_uses_secure_post_for_setdata_mode(
    monkeypatch, hass
) -> None:
    """Authenticated firmware 3.x speakers should encrypt POST writes."""
    calls = []

    async def fake_auth_mode(self):
        return AUTH_MODE_SETDATA

    async def fake_plain(self, method, endpoint, *, params=None, json_payload=None):
        calls.append(("plain", method, endpoint))
        return {}

    async def fake_secure(self, method, endpoint, *, params=None, json_payload=None):
        calls.append(("secure", method, endpoint, json_payload))
        return {"ok": True}

    monkeypatch.setattr(ModernKefClient, "_get_webserver_auth_mode", fake_auth_mode)
    monkeypatch.setattr(ModernKefClient, "_request_json_plain", fake_plain)
    monkeypatch.setattr(ModernKefClient, "_request_json_secure", fake_secure)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    response = await client._request_json(
        "POST",
        "/setData",
        json_payload={
            "path": PROBE_PATHS["cable_mode"],
            "role": "value",
            "value": {"type": "kefCableMode", "kefCableMode": "wired"},
        },
    )

    assert response == {"ok": True}
    assert calls == [
        (
            "secure",
            "POST",
            "/setData",
            {
                "path": PROBE_PATHS["cable_mode"],
                "role": "value",
                "value": {"type": "kefCableMode", "kefCableMode": "wired"},
            },
        )
    ]


async def test_modern_request_json_uses_secure_get_for_all_mode(
    monkeypatch, hass
) -> None:
    """Fully protected speakers should encrypt GET reads too."""
    calls = []

    async def fake_auth_mode(self):
        return AUTH_MODE_ALL

    async def fake_plain(self, method, endpoint, *, params=None, json_payload=None):
        calls.append(("plain", method, endpoint))
        return {}

    async def fake_secure(self, method, endpoint, *, params=None, json_payload=None):
        calls.append(("secure", method, endpoint, params))
        return [{"string_": "3.0.135.0x60acbcf", "type": "string_"}]

    monkeypatch.setattr(ModernKefClient, "_get_webserver_auth_mode", fake_auth_mode)
    monkeypatch.setattr(ModernKefClient, "_request_json_plain", fake_plain)
    monkeypatch.setattr(ModernKefClient, "_request_json_secure", fake_secure)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))
    response = await client._request_json(
        "GET",
        "/getData",
        params={"path": PROBE_PATHS["version"], "roles": "value", "_nocache": "1"},
    )

    assert response == [{"string_": "3.0.135.0x60acbcf", "type": "string_"}]
    assert calls == [
        (
            "secure",
            "GET",
            "/getData",
            {"path": PROBE_PATHS["version"], "roles": "value", "_nocache": "1"},
        )
    ]


async def test_modern_get_webserver_auth_mode_defaults_to_none_on_missing_path(
    monkeypatch, hass
) -> None:
    """Older firmware without the auth path should keep using plain requests."""

    async def fake_plain(self, method, endpoint, *, params=None, json_payload=None):
        raise KefResponseError("missing path")

    monkeypatch.setattr(ModernKefClient, "_request_json_plain", fake_plain)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))

    assert await client._get_webserver_auth_mode() == "none"


async def test_modern_get_webserver_auth_mode_parses_setdata_value(
    monkeypatch, hass
) -> None:
    """The webserver auth probe should parse KEF's typed auth-mode value."""

    async def fake_plain(self, method, endpoint, *, params=None, json_payload=None):
        return [{"webserverAuthMode": AUTH_MODE_SETDATA, "type": "webserverAuthMode"}]

    monkeypatch.setattr(ModernKefClient, "_request_json_plain", fake_plain)

    client = ModernKefClient(TEST_HOST, async_get_clientsession(hass))

    assert await client._get_webserver_auth_mode() == AUTH_MODE_SETDATA
