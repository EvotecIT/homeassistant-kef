"""API tests for KEF."""

from __future__ import annotations

from homeassistant.helpers.aiohttp_client import async_get_clientsession

from custom_components.kef.api import ModernKefClient
from custom_components.kef.const import PROBE_PATHS
from tests.conftest import (
    AUTO_SWITCH_HDMI_VALUE,
    DEFAULT_VOLUME_GLOBAL_VALUE,
    DEVICE_NAME_VALUE,
    DISABLE_FRONT_STANDBY_LED_VALUE,
    DISABLE_TOP_PANEL_VALUE,
    EQ_PROFILE_VALUE,
    MAC_VALUE,
    MAXIMUM_VOLUME_VALUE,
    MODEL_CODE_VALUE,
    MUTE_VALUE,
    NETWORK_INFO_VALUE,
    PER_INPUT_STARTUP_VOLUME_ENABLED_VALUE,
    PLAY_MODE_VALUE,
    PLAY_TIME_VALUE,
    PLAYER_DATA_VALUE,
    RELEASE_TEXT_VALUE,
    SOURCE_VALUE,
    SPEAKER_STATUS_VALUE,
    STANDBY_MODE_VALUE,
    STARTUP_TONE_VALUE,
    STARTUP_VOLUME_ENABLED_VALUE,
    TEST_HOST,
    USB_CHARGING_VALUE,
    VERSION_VALUE,
    VOLUME_LIMIT_VALUE,
    VOLUME_STEP_SETTING_VALUE,
    VOLUME_VALUE,
    WAKE_UP_SOURCE_VALUE,
)

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
        PROBE_PATHS["speaker_status"]: SPEAKER_STATUS_VALUE["kefSpeakerStatus"],
        PROBE_PATHS["source"]: SOURCE_VALUE["kefPhysicalSource"],
        PROBE_PATHS["volume"]: VOLUME_VALUE["i32_"],
        PROBE_PATHS["mute"]: MUTE_VALUE["bool_"],
        PROBE_PATHS["play_mode"]: PLAY_MODE_VALUE["playerPlayMode"],
        PROBE_PATHS["player_data"]: PLAYER_DATA_VALUE,
        PROBE_PATHS["play_time"]: PLAY_TIME_VALUE["i64_"],
        PROBE_PATHS["eq_profile"]: EQ_PROFILE_VALUE,
        PROBE_PATHS["network_info"]: NETWORK_INFO_VALUE,
        PROBE_PATHS["standby_mode"]: STANDBY_MODE_VALUE["kefStandbyMode"],
        PROBE_PATHS["startup_tone"]: STARTUP_TONE_VALUE["bool_"],
        PROBE_PATHS["auto_switch_hdmi"]: AUTO_SWITCH_HDMI_VALUE["bool_"],
        PROBE_PATHS["disable_front_standby_led"]: (
            DISABLE_FRONT_STANDBY_LED_VALUE["bool_"]
        ),
        PROBE_PATHS["disable_top_panel"]: DISABLE_TOP_PANEL_VALUE["bool_"],
        PROBE_PATHS["wake_up_source"]: WAKE_UP_SOURCE_VALUE["kefWakeUpSource"],
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

    assert snapshot.device.device_name == "LSX II-04438c"
    assert snapshot.device.model == "LSXII"
    assert snapshot.source == "usb"
    assert snapshot.volume_raw == 80
    assert snapshot.is_muted is False
    assert snapshot.playback is not None
    assert snapshot.playback.state == "playing"
    assert snapshot.playback.album_artist == "KEF Artists"
    assert snapshot.playback.service_id == "usb"
    assert snapshot.playback.codec == "pcm"
    assert snapshot.playback.stream_channels == "2.0"
    assert snapshot.eq_profile is not None
    assert snapshot.eq_profile.balance == 30
    assert snapshot.wifi_info is not None
    assert snapshot.wifi_info.ssid == "EvotecLab"
    assert snapshot.wifi_info.signal_level == -49
    assert snapshot.standby_mode == "standby_none"
    assert snapshot.startup_tone_enabled is True
    assert snapshot.auto_switch_hdmi is False
    assert snapshot.standby_led_enabled is True
    assert snapshot.top_panel_enabled is True
    assert snapshot.wake_source == "wakeup_default"
    assert snapshot.usb_charging_enabled is False
    assert snapshot.startup_volume_enabled is False
    assert snapshot.per_input_startup_volume_enabled is False
    assert snapshot.default_volume_global == 30
    assert snapshot.default_volume_by_source["wifi"] == 30
    assert snapshot.default_volume_by_source["usb"] == 30
    assert snapshot.maximum_volume == 100
    assert snapshot.volume_step == 1
    assert snapshot.volume_limit_enabled is False
    assert snapshot.source_list == (
        "wifi",
        "bluetooth",
        "tv",
        "optical",
        "analog",
        "usb",
    )


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
        PROBE_PATHS["volume"]: 80,
        PROBE_PATHS["mute"]: False,
        PROBE_PATHS["play_mode"]: PLAY_MODE_VALUE["playerPlayMode"],
        PROBE_PATHS["player_data"]: PLAYER_DATA_VALUE,
        PROBE_PATHS["play_time"]: PLAY_TIME_VALUE["i64_"],
        PROBE_PATHS["eq_profile"]: EQ_PROFILE_VALUE,
        PROBE_PATHS["network_info"]: NETWORK_INFO_VALUE,
        PROBE_PATHS["standby_mode"]: STANDBY_MODE_VALUE["kefStandbyMode"],
        PROBE_PATHS["startup_tone"]: STARTUP_TONE_VALUE["bool_"],
        PROBE_PATHS["auto_switch_hdmi"]: AUTO_SWITCH_HDMI_VALUE["bool_"],
        PROBE_PATHS["disable_front_standby_led"]: (
            DISABLE_FRONT_STANDBY_LED_VALUE["bool_"]
        ),
        PROBE_PATHS["disable_top_panel"]: DISABLE_TOP_PANEL_VALUE["bool_"],
        PROBE_PATHS["wake_up_source"]: WAKE_UP_SOURCE_VALUE["kefWakeUpSource"],
        PROBE_PATHS["usb_charging"]: USB_CHARGING_VALUE["bool_"],
        PROBE_PATHS["startup_volume_enabled"]: STARTUP_VOLUME_ENABLED_VALUE["bool_"],
        PROBE_PATHS["per_input_startup_volume_enabled"]: (
            PER_INPUT_STARTUP_VOLUME_ENABLED_VALUE["bool_"]
        ),
        PROBE_PATHS["default_volume_global"]: DEFAULT_VOLUME_GLOBAL_VALUE["i32_"],
        PROBE_PATHS["maximum_volume"]: MAXIMUM_VOLUME_VALUE["i32_"],
        PROBE_PATHS["volume_step"]: VOLUME_STEP_SETTING_VALUE["i16_"],
        PROBE_PATHS["volume_limit"]: VOLUME_LIMIT_VALUE["bool_"],
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
        PROBE_PATHS["volume"]: VOLUME_VALUE["i32_"],
        PROBE_PATHS["mute"]: MUTE_VALUE["bool_"],
        PROBE_PATHS["play_mode"]: PLAY_MODE_VALUE["playerPlayMode"],
        PROBE_PATHS["player_data"]: PLAYER_DATA_VALUE,
        PROBE_PATHS["play_time"]: PLAY_TIME_VALUE["i64_"],
        PROBE_PATHS["eq_profile"]: EQ_PROFILE_VALUE,
        PROBE_PATHS["network_info"]: NETWORK_INFO_VALUE,
        PROBE_PATHS["standby_mode"]: STANDBY_MODE_VALUE["kefStandbyMode"],
        PROBE_PATHS["startup_tone"]: STARTUP_TONE_VALUE["bool_"],
        PROBE_PATHS["auto_switch_hdmi"]: AUTO_SWITCH_HDMI_VALUE["bool_"],
        PROBE_PATHS["disable_front_standby_led"]: (
            DISABLE_FRONT_STANDBY_LED_VALUE["bool_"]
        ),
        PROBE_PATHS["disable_top_panel"]: DISABLE_TOP_PANEL_VALUE["bool_"],
        PROBE_PATHS["wake_up_source"]: WAKE_UP_SOURCE_VALUE["kefWakeUpSource"],
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
        PROBE_PATHS["volume"]: VOLUME_VALUE["i32_"],
        PROBE_PATHS["mute"]: MUTE_VALUE["bool_"],
        PROBE_PATHS["play_mode"]: PLAY_MODE_VALUE["playerPlayMode"],
        PROBE_PATHS["player_data"]: PLAYER_DATA_VALUE,
        PROBE_PATHS["play_time"]: PLAY_TIME_VALUE["i64_"],
        PROBE_PATHS["eq_profile"]: EQ_PROFILE_VALUE,
        PROBE_PATHS["standby_mode"]: STANDBY_MODE_VALUE["kefStandbyMode"],
        PROBE_PATHS["startup_tone"]: STARTUP_TONE_VALUE["bool_"],
        PROBE_PATHS["auto_switch_hdmi"]: AUTO_SWITCH_HDMI_VALUE["bool_"],
        PROBE_PATHS["disable_front_standby_led"]: (
            DISABLE_FRONT_STANDBY_LED_VALUE["bool_"]
        ),
        PROBE_PATHS["disable_top_panel"]: DISABLE_TOP_PANEL_VALUE["bool_"],
        PROBE_PATHS["wake_up_source"]: WAKE_UP_SOURCE_VALUE["kefWakeUpSource"],
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
