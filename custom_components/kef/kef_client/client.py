"""Client helpers for KEF local APIs."""

from __future__ import annotations

import asyncio
import base64
import copy
import hashlib
import hmac
import json
import logging
import os
import socket
import time
from abc import ABC, abstractmethod
from collections.abc import Mapping
from typing import Any
from urllib.parse import urlencode

import aiohttp
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from .const import (
    API_ROOT,
    AUTH_MODE_ALL,
    AUTH_MODE_NONE,
    AUTH_MODE_SETDATA,
    DEFAULT_LEGACY_PORT,
    DEFAULT_MODERN_SOURCE_LIST,
    DEFAULT_PORT,
    DEFAULT_VOLUME_SOURCE_SUFFIX,
    EVENT_MODIFY_QUEUE_ENDPOINT,
    EVENT_POLL_QUEUE_ENDPOINT,
    EVENT_SUBSCRIPTIONS,
    GET_DATA_ENDPOINT,
    LEGACY_SOURCE_LIST,
    MODERN_MODEL_SOURCE_MAP,
    PROBE_PATHS,
    SET_DATA_ENDPOINT,
    STATE_OFF,
)
from .exceptions import (
    KefAuthenticationRequiredError,
    KefConnectionError,
    KefError,
    KefResponseError,
    KefUnsupportedDeviceError,
)
from .models import (
    KefBackend,
    KefDeviceInfo,
    KefEqProfile,
    KefFirmwareUpdateInfo,
    KefPlaybackInfo,
    KefSnapshot,
    KefWifiInfo,
)

_LOGGER = logging.getLogger(__name__)

_LEGACY_RESPONSE_OK = 17
_LEGACY_GET_START = ord("G")
_LEGACY_SET_START = ord("S")
_LEGACY_GET_END = 128
_LEGACY_SET_MID = 129
_FIRMWARE_UPDATE_PENDING_STATES = {
    "checkingForUpdate",
    "checkingForUpdates",
    "downloading",
    "downloadInProgress",
    "downloadingUpdate",
}

_INPUT_SOURCES_BASE = {
    "Bluetooth": 9,
    "Bluetooth_paired": 15,
    "Aux": 10,
    "Opt": 11,
    "Usb": 12,
    "Wifi": 2,
}

_STANDBY_OPTIONS = [20, 60, None]
_INPUT_SOURCES: dict[str, dict[int | None, tuple[int, int]]] = {}
_INPUT_SOURCES_RESPONSE: dict[int, tuple[str, int | None, str]] = {}
for source, code in _INPUT_SOURCES_BASE.items():
    source_map = {
        option: code + index * 16
        for index, option in enumerate(_STANDBY_OPTIONS)
    }
    _INPUT_SOURCES[source] = {
        option: (lr, lr + 64) for option, lr in source_map.items()
    }
for source, mapping in _INPUT_SOURCES.items():
    normalized_source = source.replace("_paired", "")
    for standby_time, (lr, rl) in mapping.items():
        _INPUT_SOURCES_RESPONSE[lr] = (normalized_source, standby_time, "L/R")
        _INPUT_SOURCES_RESPONSE[rl] = (normalized_source, standby_time, "R/L")
_INPUT_SOURCES_RESPONSE[48] = _INPUT_SOURCES_RESPONSE[82]


class BaseKefClient(ABC):
    """Base KEF backend interface."""

    def __init__(self, host: str) -> None:
        """Initialize the backend."""
        self._host = host

    @property
    @abstractmethod
    def backend(self) -> KefBackend:
        """Return the backend type."""

    @abstractmethod
    async def async_identify(self) -> KefDeviceInfo:
        """Probe the speaker and return device information."""

    @abstractmethod
    async def async_refresh(self) -> KefSnapshot:
        """Fetch the current device state."""

    @abstractmethod
    async def async_turn_on(self) -> None:
        """Turn on the speaker."""

    @abstractmethod
    async def async_turn_off(self) -> None:
        """Turn off the speaker."""

    @abstractmethod
    async def async_set_volume_raw(self, volume: int) -> None:
        """Set the raw 0..100 volume value."""

    @abstractmethod
    async def async_toggle_play_pause(self) -> None:
        """Toggle play/pause."""

    @abstractmethod
    async def async_set_muted(self, muted: bool) -> None:
        """Set the muted state."""

    @abstractmethod
    async def async_next_track(self) -> None:
        """Skip to the next track."""

    @abstractmethod
    async def async_previous_track(self) -> None:
        """Go to the previous track."""

    @abstractmethod
    async def async_select_source(self, source: str) -> None:
        """Select the active source."""

    @abstractmethod
    async def async_set_standby_mode(self, mode: str) -> None:
        """Set the automatic standby mode."""

    @abstractmethod
    async def async_set_startup_tone_enabled(self, enabled: bool) -> None:
        """Enable or disable the startup tone."""

    @abstractmethod
    async def async_set_auto_switch_hdmi_enabled(self, enabled: bool) -> None:
        """Enable or disable HDMI auto switching."""

    @abstractmethod
    async def async_set_front_led_enabled(self, enabled: bool) -> None:
        """Enable or disable the front LED."""

    @abstractmethod
    async def async_set_standby_led_enabled(self, enabled: bool) -> None:
        """Enable or disable the standby LED."""

    @abstractmethod
    async def async_set_top_panel_enabled(self, enabled: bool) -> None:
        """Enable or disable the top touch panel."""

    @abstractmethod
    async def async_set_top_panel_led_enabled(self, enabled: bool) -> None:
        """Enable or disable the top-panel LED while the speaker is active."""

    @abstractmethod
    async def async_set_top_panel_standby_led_enabled(self, enabled: bool) -> None:
        """Enable or disable the top-panel LED while the speaker is in standby."""

    @abstractmethod
    async def async_set_wake_source(self, source: str) -> None:
        """Set the wake source."""

    @abstractmethod
    async def async_set_subwoofer_wake_enabled(self, enabled: bool) -> None:
        """Enable or disable wired subwoofer wake on startup."""

    @abstractmethod
    async def async_set_kw1_wake_enabled(self, enabled: bool) -> None:
        """Enable or disable KW1 subwoofer wake on startup."""

    @abstractmethod
    async def async_set_usb_charging_enabled(self, enabled: bool) -> None:
        """Enable or disable USB charging."""

    @abstractmethod
    async def async_set_startup_volume_enabled(self, enabled: bool) -> None:
        """Enable or disable startup volume mode."""

    @abstractmethod
    async def async_set_per_input_startup_volume_enabled(
        self,
        enabled: bool,
    ) -> None:
        """Enable or disable per-input startup volumes."""

    @abstractmethod
    async def async_set_default_volume_global(self, volume: int) -> None:
        """Set the global startup volume."""

    @abstractmethod
    async def async_set_maximum_volume(self, volume: int) -> None:
        """Set the maximum allowed volume."""

    @abstractmethod
    async def async_set_volume_step(self, step: int) -> None:
        """Set the volume step size."""

    @abstractmethod
    async def async_set_volume_limit_enabled(self, enabled: bool) -> None:
        """Enable or disable the volume limiter."""

    @abstractmethod
    async def async_set_default_volume_for_source(
        self,
        source: str,
        volume: int,
    ) -> None:
        """Set the startup volume for a specific source."""

    @abstractmethod
    async def async_set_cable_mode(self, mode: str) -> None:
        """Set the speaker pair cable mode."""

    @abstractmethod
    async def async_set_balance(self, value: int) -> None:
        """Set the EQ balance."""

    @abstractmethod
    async def async_set_bass_extension(self, value: str) -> None:
        """Set the EQ bass extension."""

    @abstractmethod
    async def async_set_treble_amount(self, value: int) -> None:
        """Set the EQ treble amount."""

    @abstractmethod
    async def async_set_subwoofer_gain(self, value: int) -> None:
        """Set the EQ subwoofer gain."""

    @abstractmethod
    async def async_set_desk_mode_enabled(self, enabled: bool) -> None:
        """Enable or disable desk mode."""

    @abstractmethod
    async def async_set_wall_mode_enabled(self, enabled: bool) -> None:
        """Enable or disable wall mode."""

    @abstractmethod
    async def async_set_phase_correction_enabled(self, enabled: bool) -> None:
        """Enable or disable phase correction."""

    @abstractmethod
    async def async_set_high_pass_mode_enabled(self, enabled: bool) -> None:
        """Enable or disable high-pass mode."""

    @abstractmethod
    async def async_set_high_pass_frequency(self, value: int) -> None:
        """Set the high-pass frequency step."""

    @abstractmethod
    async def async_set_master_channel(self, channel: str) -> None:
        """Set the master channel assignment."""

    @abstractmethod
    async def async_set_fixed_volume_level(self, volume: int) -> None:
        """Set the fixed-volume level."""

    @abstractmethod
    async def async_set_remote_ir_enabled(self, enabled: bool) -> None:
        """Enable or disable IR remote control."""

    @abstractmethod
    async def async_set_remote_ir_code(self, code: str) -> None:
        """Set the IR remote code set."""

    @abstractmethod
    async def async_set_favourite_button_action(self, action: str) -> None:
        """Set the favourite button action."""

    @abstractmethod
    async def async_set_eq_button_action(self, button: int, action: str) -> None:
        """Set the EQ button action."""

    @abstractmethod
    async def async_set_analytics_enabled(self, enabled: bool) -> None:
        """Enable or disable KEF analytics."""

    @abstractmethod
    async def async_set_app_analytics_enabled(self, enabled: bool) -> None:
        """Enable or disable app analytics."""

    @abstractmethod
    async def async_set_streaming_quality(self, quality: str) -> None:
        """Set the Airable streaming quality."""

    @abstractmethod
    async def async_set_ui_language(self, language: str) -> None:
        """Set the speaker UI language."""

    @abstractmethod
    async def async_set_speaker_location(self, location: str) -> None:
        """Set the speaker country or region code."""

    @abstractmethod
    async def async_get_firmware_update_status(self) -> KefFirmwareUpdateInfo | None:
        """Get the current firmware-update status."""

    @abstractmethod
    async def async_check_for_firmware_update(self) -> KefFirmwareUpdateInfo | None:
        """Trigger a firmware check and return the resulting status."""

    @abstractmethod
    async def async_install_firmware_update(self) -> KefFirmwareUpdateInfo | None:
        """Trigger firmware installation and return the latest known status."""

    @abstractmethod
    async def async_upload_firmware_update(
        self,
        file_path: str,
    ) -> KefFirmwareUpdateInfo | None:
        """Upload a firmware image to the speaker and trigger installation."""

    async def async_poll_events(self, timeout: int = 10) -> list[dict[str, Any]]:
        """Poll live device events when supported."""
        return []

    async def async_reset_event_queue(self) -> None:
        """Reset any live event queue state when supported."""
        return None


class ModernKefClient(BaseKefClient):
    """Modern HTTP client for LSX II-era KEF speakers."""

    backend = KefBackend.MODERN

    def __init__(
        self,
        host: str,
        session: aiohttp.ClientSession,
        *,
        port: int = DEFAULT_PORT,
        password: str | None = None,
        request_timeout: float = 4.0,
    ) -> None:
        """Initialize the client."""
        super().__init__(host)
        self._session = session
        self._port = port
        self._password = password or ""
        self._request_timeout = request_timeout
        self._last_active_source: str | None = None
        self._event_queue_id: str | None = None
        self._auth_mode: str | None = None

    async def async_identify(self) -> KefDeviceInfo:
        """Probe the modern HTTP API."""
        device_name = await self._get_path_value(PROBE_PATHS["device_name"])
        firmware_version = await self._get_path_value(PROBE_PATHS["version"])
        release_text = await self._get_path_value(PROBE_PATHS["release_text"])
        mac_address = await self._get_path_value(PROBE_PATHS["mac"])
        model_code = await self._get_path_value(PROBE_PATHS["model_code"])
        serial_number = await self._get_optional_path_value(
            PROBE_PATHS["serial_number"],
            typed_key="string_",
        )
        kef_id = await self._get_optional_path_value(
            PROBE_PATHS["kef_id"],
            typed_key="string_",
        )
        hardware_version = await self._get_optional_path_value(
            PROBE_PATHS["hardware_version"],
            typed_key="string_",
        )

        release_value = self._extract_string(release_text)
        model = (
            release_value.split("_", 1)[0]
            if release_value and "_" in release_value
            else "KEF"
        )
        mac_value = self._extract_string(mac_address)
        unique_id = (
            f"kef-{mac_value.lower()}" if mac_value else f"kef-modern-{self._host}"
        )

        return KefDeviceInfo(
            backend=self.backend,
            unique_id=unique_id,
            device_name=self._extract_string(device_name) or "KEF",
            model=model,
            mac_address=mac_value,
            firmware_version=self._extract_string(firmware_version),
            release_text=release_value,
            model_code=self._extract_string(model_code),
            serial_number=self._extract_string(serial_number),
            kef_id=self._extract_string(kef_id),
            hardware_version=self._extract_string(hardware_version),
            host=self._host,
            port=self._port,
        )

    async def async_refresh(self) -> KefSnapshot:
        """Fetch the current state from the speaker."""
        device = await self.async_identify()
        speaker_status = self._extract_string(
            await self._get_path_value(
                PROBE_PATHS["speaker_status"],
                typed_key="kefSpeakerStatus",
            )
        )
        source = self._extract_string(
            await self._get_path_value(
                PROBE_PATHS["source"],
                typed_key="kefPhysicalSource",
            )
        )
        cable_mode = self._extract_string(
            await self._get_optional_path_value(
                PROBE_PATHS["cable_mode"],
                typed_key="kefCableMode",
            )
        )
        master_channel = self._extract_string(
            await self._get_optional_path_value(
                PROBE_PATHS["master_channel"],
                typed_key="kefMasterChannelMode",
            )
        )
        volume_raw = self._extract_int(
            await self._get_path_value(PROBE_PATHS["volume"], typed_key="i32_")
        )
        is_muted = self._extract_bool(
            await self._get_path_value(PROBE_PATHS["mute"], typed_key="bool_")
        )
        play_mode = self._extract_string(
            await self._get_path_value(
                PROBE_PATHS["play_mode"],
                typed_key="playerPlayMode",
            )
        )
        firmware_update = await self._get_optional_path_value(
            PROBE_PATHS["firmware_update_status"]
        )
        player_data = await self._get_optional_path_value(PROBE_PATHS["player_data"])
        play_time = await self._get_optional_path_value(
            PROBE_PATHS["play_time"],
            typed_key="i64_",
        )
        eq_profile = await self._get_optional_path_value(PROBE_PATHS["eq_profile"])
        if eq_profile is None:
            eq_profile = await self._get_optional_path_value(
                PROBE_PATHS["eq_profile_v2"]
            )
        network_info = await self._get_optional_path_value(PROBE_PATHS["network_info"])
        standby_mode = self._extract_string(
            await self._get_optional_path_value(
                PROBE_PATHS["standby_mode"],
                typed_key="kefStandbyMode",
            )
        )
        startup_tone_enabled = self._extract_bool(
            await self._get_optional_path_value(
                PROBE_PATHS["startup_tone"],
                typed_key="bool_",
            )
        )
        auto_switch_hdmi = self._extract_bool(
            await self._get_optional_path_value(
                PROBE_PATHS["auto_switch_hdmi"],
                typed_key="bool_",
            )
        )
        front_led_disabled = self._extract_bool(
            await self._get_optional_path_value(
                PROBE_PATHS["disable_front_led"],
                typed_key="bool_",
            )
        )
        standby_led_disabled = self._extract_bool(
            await self._get_optional_path_value(
                PROBE_PATHS["disable_front_standby_led"],
                typed_key="bool_",
            )
        )
        top_panel_disabled = self._extract_bool(
            await self._get_optional_path_value(
                PROBE_PATHS["disable_top_panel"],
                typed_key="bool_",
            )
        )
        top_panel_led_enabled = self._extract_bool(
            await self._get_optional_path_value(
                PROBE_PATHS["top_panel_led"],
                typed_key="bool_",
            )
        )
        top_panel_standby_led_enabled = self._extract_bool(
            await self._get_optional_path_value(
                PROBE_PATHS["top_panel_standby_led"],
                typed_key="bool_",
            )
        )
        wake_source = self._extract_string(
            await self._get_optional_path_value(
                PROBE_PATHS["wake_up_source"],
                typed_key="kefWakeUpSource",
            )
        )
        subwoofer_wake_enabled = self._extract_bool(
            await self._get_optional_path_value(
                PROBE_PATHS["subwoofer_force_on"],
                typed_key="bool_",
            )
        )
        kw1_wake_enabled = self._extract_bool(
            await self._get_optional_path_value(
                PROBE_PATHS["subwoofer_force_on_kw1"],
                typed_key="bool_",
            )
        )
        usb_charging_enabled = self._extract_bool(
            await self._get_optional_path_value(
                PROBE_PATHS["usb_charging"],
                typed_key="bool_",
            )
        )
        startup_volume_enabled = self._extract_bool(
            await self._get_optional_path_value(
                PROBE_PATHS["startup_volume_enabled"],
                typed_key="bool_",
            )
        )
        per_input_startup_volume_enabled = self._extract_bool(
            await self._get_optional_path_value(
                PROBE_PATHS["per_input_startup_volume_enabled"],
                typed_key="bool_",
            )
        )
        source_list = self._source_list_for_model(device.model)
        default_volume_global = self._extract_int(
            await self._get_optional_path_value(
                PROBE_PATHS["default_volume_global"],
                typed_key="i32_",
            )
        )
        default_volume_by_source = await self._async_get_default_volume_by_source(
            source_list
        )
        maximum_volume = self._extract_int(
            await self._get_optional_path_value(
                PROBE_PATHS["maximum_volume"],
                typed_key="i32_",
            )
        )
        volume_step = self._extract_int(
            await self._get_optional_path_value(
                PROBE_PATHS["volume_step"],
                typed_key="i16_",
            )
        )
        volume_limit_enabled = self._extract_bool(
            await self._get_optional_path_value(
                PROBE_PATHS["volume_limit"],
                typed_key="bool_",
            )
        )
        fixed_volume_level = self._extract_int(
            await self._get_optional_path_value(
                PROBE_PATHS["fixed_volume_level"],
                typed_key="i32_",
            )
        )
        remote_ir_enabled = self._extract_bool(
            await self._get_optional_path_value(
                PROBE_PATHS["remote_ir"],
                typed_key="bool_",
            )
        )
        remote_ir_code = self._extract_string(
            await self._get_optional_path_value(
                PROBE_PATHS["remote_ir_code"],
                typed_key="kefSpeakerIRCode",
            )
        )
        favourite_button = self._extract_string(
            await self._get_optional_path_value(
                PROBE_PATHS["favourite_button"],
                typed_key="kefFavouriteButtonFunction",
            )
        )
        eq_button_1 = self._extract_string(
            await self._get_optional_path_value(
                PROBE_PATHS["eq_button_1"],
                typed_key="string_",
            )
        )
        eq_button_2 = self._extract_string(
            await self._get_optional_path_value(
                PROBE_PATHS["eq_button_2"],
                typed_key="string_",
            )
        )
        analytics_disabled = self._extract_bool(
            await self._get_optional_path_value(
                PROBE_PATHS["disable_analytics"],
                typed_key="bool_",
            )
        )
        app_analytics_disabled = self._extract_bool(
            await self._get_optional_path_value(
                PROBE_PATHS["disable_app_analytics"],
                typed_key="bool_",
            )
        )
        streaming_quality = self._extract_string(
            await self._get_optional_path_value(
                PROBE_PATHS["streaming_quality"],
                typed_key="airableStreamBitrate",
            )
        )
        ui_language = self._extract_string(
            await self._get_optional_path_value(
                PROBE_PATHS["ui_language"],
                typed_key="string_",
            )
        )
        speaker_location = self._extract_string(
            await self._get_optional_path_value(
                PROBE_PATHS["speaker_location"],
                typed_key="string_",
            )
        )
        network_ping_ms = self._extract_float(
            await self._get_optional_path_value(
                PROBE_PATHS["network_ping"],
                typed_key="double_",
            )
        )
        network_stability = self._extract_string(
            await self._get_optional_path_value(
                PROBE_PATHS["network_stability"],
                typed_key="kefNetworkStability",
            )
        )
        speed_test_status = self._extract_string(
            await self._get_optional_path_value(
                PROBE_PATHS["speed_test_status"],
                typed_key="kefSpeedTestStatus",
            )
        )
        speed_test_average_download = self._extract_float(
            await self._get_optional_path_value(
                PROBE_PATHS["speed_test_average_download"],
                typed_key="double_",
            )
        )
        speed_test_current_download = self._extract_float(
            await self._get_optional_path_value(
                PROBE_PATHS["speed_test_current_download"],
                typed_key="double_",
            )
        )
        speed_test_packet_loss = self._extract_float(
            await self._get_optional_path_value(
                PROBE_PATHS["speed_test_packet_loss"],
                typed_key="double_",
            )
        )
        alerts_list = await self._get_optional_path_value(
            PROBE_PATHS["alerts_list"],
        )
        alert_counts = self._extract_alert_counts(alerts_list)
        alert_snooze_minutes = self._extract_int(
            await self._get_optional_path_value(
                PROBE_PATHS["alert_snooze_time"],
                typed_key="i32_",
            )
        )
        player_notification_active = self._extract_bool(
            await self._get_optional_path_value(
                PROBE_PATHS["player_notification"],
                typed_key="bool_",
            )
        )
        if source not in (None, STATE_OFF):
            self._last_active_source = source

        return KefSnapshot(
            device=device,
            speaker_status=speaker_status or STATE_OFF,
            source=source,
            cable_mode=cable_mode,
            master_channel=master_channel,
            volume_raw=volume_raw,
            volume_level=None if volume_raw is None else volume_raw / 100.0,
            is_muted=is_muted,
            play_mode=play_mode,
            playback=self._parse_playback(player_data, play_time),
            eq_profile=(
                KefEqProfile.from_modern_value(eq_profile)
                if isinstance(eq_profile, dict)
                else None
            ),
            firmware_update=(
                KefFirmwareUpdateInfo.from_modern_value(firmware_update)
                if isinstance(firmware_update, dict)
                else None
            ),
            wifi_info=(
                KefWifiInfo.from_modern_value(network_info)
                if isinstance(network_info, dict)
                else None
            ),
            standby_mode=standby_mode,
            startup_tone_enabled=startup_tone_enabled,
            auto_switch_hdmi=auto_switch_hdmi,
            front_led_enabled=(
                None if front_led_disabled is None else not front_led_disabled
            ),
            standby_led_enabled=(
                None if standby_led_disabled is None else not standby_led_disabled
            ),
            top_panel_enabled=(
                None if top_panel_disabled is None else not top_panel_disabled
            ),
            top_panel_led_enabled=top_panel_led_enabled,
            top_panel_standby_led_enabled=top_panel_standby_led_enabled,
            wake_source=wake_source,
            subwoofer_wake_enabled=subwoofer_wake_enabled,
            kw1_wake_enabled=kw1_wake_enabled,
            usb_charging_enabled=usb_charging_enabled,
            startup_volume_enabled=startup_volume_enabled,
            per_input_startup_volume_enabled=per_input_startup_volume_enabled,
            default_volume_global=default_volume_global,
            maximum_volume=maximum_volume,
            volume_step=volume_step,
            volume_limit_enabled=volume_limit_enabled,
            fixed_volume_level=(
                None
                if fixed_volume_level is None or fixed_volume_level < 0
                else fixed_volume_level
            ),
            remote_ir_enabled=remote_ir_enabled,
            remote_ir_code=remote_ir_code,
            favourite_button=favourite_button,
            eq_button_1=eq_button_1,
            eq_button_2=eq_button_2,
            analytics_enabled=(
                None if analytics_disabled is None else not analytics_disabled
            ),
            app_analytics_enabled=(
                None
                if app_analytics_disabled is None
                else not app_analytics_disabled
            ),
            streaming_quality=streaming_quality,
            ui_language=ui_language,
            speaker_location=speaker_location,
            network_ping_ms=network_ping_ms,
            network_stability=network_stability,
            speed_test_status=speed_test_status,
            speed_test_average_download=speed_test_average_download,
            speed_test_current_download=speed_test_current_download,
            speed_test_packet_loss=speed_test_packet_loss,
            alert_alarm_count=alert_counts[0],
            alert_timer_count=alert_counts[1],
            alert_snooze_minutes=alert_snooze_minutes,
            player_notification_active=player_notification_active,
            source_list=source_list,
            default_volume_by_source=default_volume_by_source,
        )

    async def async_turn_on(self) -> None:
        """Turn on the speaker by selecting a reasonable source."""
        snapshot = await self.async_refresh()
        target_source = self._last_active_source
        if target_source in (None, STATE_OFF):
            current_source = snapshot.source
            target_source = (
                current_source if current_source not in (None, STATE_OFF) else "wifi"
            )
        await self.async_select_source(target_source)

    async def async_turn_off(self) -> None:
        """Turn off the speaker."""
        await self._set_data(
            PROBE_PATHS["source"],
            role="value",
            value={"type": "kefPhysicalSource", "kefPhysicalSource": STATE_OFF},
        )

    async def async_set_volume_raw(self, volume: int) -> None:
        """Set the raw volume level."""
        await self._set_data(
            PROBE_PATHS["volume"],
            role="value",
            value={"type": "i32_", "i32_": max(0, min(100, volume))},
        )

    async def async_toggle_play_pause(self) -> None:
        """Toggle play/pause."""
        await self._set_data(
            "player:player/control",
            role="activate",
            value={"control": "pause"},
        )

    async def async_set_muted(self, muted: bool) -> None:
        """Set the muted state."""
        await self._set_data(
            "settings:/mediaPlayer/mute",
            role="value",
            value={"type": "bool_", "bool_": muted},
        )

    async def async_next_track(self) -> None:
        """Go to the next track."""
        await self._set_data(
            "player:player/control",
            role="activate",
            value={"control": "next"},
        )

    async def async_previous_track(self) -> None:
        """Go to the previous track."""
        await self._set_data(
            "player:player/control",
            role="activate",
            value={"control": "previous"},
        )

    async def async_select_source(self, source: str) -> None:
        """Select the active source."""
        if source != STATE_OFF:
            self._last_active_source = source
        await self._set_data(
            PROBE_PATHS["source"],
            role="value",
            value={"type": "kefPhysicalSource", "kefPhysicalSource": source},
        )

    async def async_set_standby_mode(self, mode: str) -> None:
        """Set the automatic standby mode."""
        await self._set_data(
            PROBE_PATHS["standby_mode"],
            role="value",
            value={"type": "kefStandbyMode", "kefStandbyMode": mode},
        )

    async def async_set_startup_tone_enabled(self, enabled: bool) -> None:
        """Enable or disable the startup tone."""
        await self._set_data(
            PROBE_PATHS["startup_tone"],
            role="value",
            value={"type": "bool_", "bool_": enabled},
        )

    async def async_set_auto_switch_hdmi_enabled(self, enabled: bool) -> None:
        """Enable or disable HDMI auto switching."""
        await self._set_data(
            PROBE_PATHS["auto_switch_hdmi"],
            role="value",
            value={"type": "bool_", "bool_": enabled},
        )

    async def async_set_front_led_enabled(self, enabled: bool) -> None:
        """Enable or disable the front LED."""
        await self._set_data(
            PROBE_PATHS["disable_front_led"],
            role="value",
            value={"type": "bool_", "bool_": not enabled},
        )

    async def async_set_standby_led_enabled(self, enabled: bool) -> None:
        """Enable or disable the standby LED."""
        await self._set_data(
            PROBE_PATHS["disable_front_standby_led"],
            role="value",
            value={"type": "bool_", "bool_": not enabled},
        )

    async def async_set_top_panel_enabled(self, enabled: bool) -> None:
        """Enable or disable the top touch panel."""
        await self._set_data(
            PROBE_PATHS["disable_top_panel"],
            role="value",
            value={"type": "bool_", "bool_": not enabled},
        )

    async def async_set_top_panel_led_enabled(self, enabled: bool) -> None:
        """Enable or disable the top-panel LED while the speaker is active."""
        await self._set_data(
            PROBE_PATHS["top_panel_led"],
            role="value",
            value={"type": "bool_", "bool_": enabled},
        )

    async def async_set_top_panel_standby_led_enabled(self, enabled: bool) -> None:
        """Enable or disable the top-panel LED while the speaker is in standby."""
        await self._set_data(
            PROBE_PATHS["top_panel_standby_led"],
            role="value",
            value={"type": "bool_", "bool_": enabled},
        )

    async def async_set_wake_source(self, source: str) -> None:
        """Set the wake source."""
        await self._set_data(
            PROBE_PATHS["wake_up_source"],
            role="value",
            value={"type": "kefWakeUpSource", "kefWakeUpSource": source},
        )

    async def async_set_subwoofer_wake_enabled(self, enabled: bool) -> None:
        """Enable or disable wired subwoofer wake on startup."""
        await self._set_data(
            PROBE_PATHS["subwoofer_force_on"],
            role="value",
            value={"type": "bool_", "bool_": enabled},
        )

    async def async_set_kw1_wake_enabled(self, enabled: bool) -> None:
        """Enable or disable KW1 subwoofer wake on startup."""
        await self._set_data(
            PROBE_PATHS["subwoofer_force_on_kw1"],
            role="value",
            value={"type": "bool_", "bool_": enabled},
        )

    async def async_set_usb_charging_enabled(self, enabled: bool) -> None:
        """Enable or disable USB charging."""
        await self._set_data(
            PROBE_PATHS["usb_charging"],
            role="value",
            value={"type": "bool_", "bool_": enabled},
        )

    async def async_set_startup_volume_enabled(self, enabled: bool) -> None:
        """Enable or disable startup volume mode."""
        await self._set_data(
            PROBE_PATHS["startup_volume_enabled"],
            role="value",
            value={"type": "bool_", "bool_": enabled},
        )

    async def async_set_per_input_startup_volume_enabled(
        self,
        enabled: bool,
    ) -> None:
        """Enable or disable per-input startup volumes."""
        await self._set_data(
            PROBE_PATHS["per_input_startup_volume_enabled"],
            role="value",
            value={"type": "bool_", "bool_": enabled},
        )

    async def async_set_default_volume_global(self, volume: int) -> None:
        """Set the global startup volume."""
        await self._set_data(
            PROBE_PATHS["default_volume_global"],
            role="value",
            value={"type": "i32_", "i32_": max(0, min(100, volume))},
        )

    async def async_set_maximum_volume(self, volume: int) -> None:
        """Set the maximum allowed volume."""
        await self._set_data(
            PROBE_PATHS["maximum_volume"],
            role="value",
            value={"type": "i32_", "i32_": max(0, min(100, volume))},
        )

    async def async_set_volume_step(self, step: int) -> None:
        """Set the volume step size."""
        await self._set_data(
            PROBE_PATHS["volume_step"],
            role="value",
            value={"type": "i16_", "i16_": max(1, min(10, step))},
        )

    async def async_set_volume_limit_enabled(self, enabled: bool) -> None:
        """Enable or disable the volume limiter."""
        await self._set_data(
            PROBE_PATHS["volume_limit"],
            role="value",
            value={"type": "bool_", "bool_": enabled},
        )

    async def async_set_default_volume_for_source(
        self,
        source: str,
        volume: int,
    ) -> None:
        """Set the startup volume for a specific source."""
        await self._set_data(
            self._default_volume_path_for_source(source),
            role="value",
            value={"type": "i32_", "i32_": max(0, min(100, volume))},
        )

    async def async_set_cable_mode(self, mode: str) -> None:
        """Set the speaker pair cable mode."""
        await self._set_data(
            PROBE_PATHS["cable_mode"],
            role="value",
            value={"type": "kefCableMode", "kefCableMode": mode},
        )

    async def async_set_balance(self, value: int) -> None:
        """Set the EQ balance."""
        await self._update_eq_profile(
            lambda dsp: dsp.__setitem__("balance", max(0, min(60, value)))
        )

    async def async_set_bass_extension(self, value: str) -> None:
        """Set the EQ bass extension."""
        await self._update_eq_profile(
            lambda dsp: dsp.__setitem__("bassExtension", value)
        )

    async def async_set_treble_amount(self, value: int) -> None:
        """Set the EQ treble amount."""
        await self._update_eq_profile(
            lambda dsp: dsp.__setitem__("trebleAmount", max(0, min(16, value)))
        )

    async def async_set_subwoofer_gain(self, value: int) -> None:
        """Set the EQ subwoofer gain."""
        await self._update_eq_profile(
            lambda dsp: dsp.__setitem__("subwooferGain", max(0, min(20, value)))
        )

    async def async_set_desk_mode_enabled(self, enabled: bool) -> None:
        """Enable or disable desk mode."""
        await self._update_eq_profile(
            lambda dsp: dsp.__setitem__("deskMode", enabled)
        )

    async def async_set_wall_mode_enabled(self, enabled: bool) -> None:
        """Enable or disable wall mode."""
        await self._update_eq_profile(
            lambda dsp: dsp.__setitem__("wallMode", enabled)
        )

    async def async_set_phase_correction_enabled(self, enabled: bool) -> None:
        """Enable or disable phase correction."""
        await self._update_eq_profile(
            lambda dsp: dsp.__setitem__("phaseCorrection", enabled)
        )

    async def async_set_high_pass_mode_enabled(self, enabled: bool) -> None:
        """Enable or disable high-pass mode."""
        await self._update_eq_profile(
            lambda dsp: dsp.__setitem__("highPassMode", enabled)
        )

    async def async_set_high_pass_frequency(self, value: int) -> None:
        """Set the high-pass frequency step."""
        await self._update_eq_profile(
            lambda dsp: dsp.__setitem__("highPassModeFreq", max(0, min(10, value)))
        )

    async def async_set_master_channel(self, channel: str) -> None:
        """Set the master channel assignment."""
        await self._set_data(
            PROBE_PATHS["master_channel"],
            role="value",
            value={"type": "kefMasterChannelMode", "kefMasterChannelMode": channel},
        )

    async def async_set_fixed_volume_level(self, volume: int) -> None:
        """Set the fixed-volume level."""
        await self._set_data(
            PROBE_PATHS["fixed_volume_level"],
            role="value",
            value={"type": "i32_", "i32_": max(0, min(100, volume))},
        )

    async def async_set_remote_ir_enabled(self, enabled: bool) -> None:
        """Enable or disable IR remote control."""
        await self._set_data(
            PROBE_PATHS["remote_ir"],
            role="value",
            value={"type": "bool_", "bool_": enabled},
        )

    async def async_set_remote_ir_code(self, code: str) -> None:
        """Set the IR remote code set."""
        await self._set_data(
            PROBE_PATHS["remote_ir_code"],
            role="value",
            value={"type": "kefSpeakerIRCode", "kefSpeakerIRCode": code},
        )

    async def async_set_favourite_button_action(self, action: str) -> None:
        """Set the favourite button action."""
        await self._set_data(
            PROBE_PATHS["favourite_button"],
            role="value",
            value={
                "type": "kefFavouriteButtonFunction",
                "kefFavouriteButtonFunction": action,
            },
        )

    async def async_set_eq_button_action(self, button: int, action: str) -> None:
        """Set the EQ button action."""
        if button not in (1, 2):
            raise KefUnsupportedDeviceError("Only EQ buttons 1 and 2 are supported")
        await self._set_data(
            PROBE_PATHS[f"eq_button_{button}"],
            role="value",
            value={"type": "string_", "string_": action},
        )

    async def async_set_analytics_enabled(self, enabled: bool) -> None:
        """Enable or disable KEF analytics."""
        await self._set_data(
            PROBE_PATHS["disable_analytics"],
            role="value",
            value={"type": "bool_", "bool_": not enabled},
        )

    async def async_set_app_analytics_enabled(self, enabled: bool) -> None:
        """Enable or disable app analytics."""
        await self._set_data(
            PROBE_PATHS["disable_app_analytics"],
            role="value",
            value={"type": "bool_", "bool_": not enabled},
        )

    async def async_set_streaming_quality(self, quality: str) -> None:
        """Set the Airable streaming quality."""
        await self._set_data(
            PROBE_PATHS["streaming_quality"],
            role="value",
            value={
                "type": "airableStreamBitrate",
                "airableStreamBitrate": quality,
            },
        )

    async def async_set_ui_language(self, language: str) -> None:
        """Set the speaker UI language."""
        await self._set_data(
            PROBE_PATHS["ui_language"],
            role="value",
            value={"type": "string_", "string_": language},
        )

    async def async_set_speaker_location(self, location: str) -> None:
        """Set the speaker country or region code."""
        await self._set_data(
            PROBE_PATHS["speaker_location"],
            role="value",
            value={"type": "string_", "string_": location},
        )

    async def async_get_firmware_update_status(self) -> KefFirmwareUpdateInfo | None:
        """Get the current firmware-update status."""
        payload = await self._get_optional_path_value(
            PROBE_PATHS["firmware_update_status"]
        )
        if not isinstance(payload, dict):
            return None
        return KefFirmwareUpdateInfo.from_modern_value(payload)

    async def async_check_for_firmware_update(self) -> KefFirmwareUpdateInfo | None:
        """Ask the speaker to check for a newer firmware image."""
        try:
            await self._activate_path("firmwareupdate:checkForUpdate")
        except KefConnectionError as err:
            _LOGGER.debug(
                "KEF firmware check activation timed out; polling status anyway: %s",
                err,
            )
        return await self._poll_firmware_update_status()

    async def async_install_firmware_update(self) -> KefFirmwareUpdateInfo | None:
        """Trigger firmware installation for an already available update."""
        status = await self.async_get_firmware_update_status()
        if status is None or status.state in {None, "idle"}:
            status = await self.async_check_for_firmware_update()

        if status is not None and status.state == "downloaded":
            return await self._async_install_downloaded_firmware_update()

        if status is not None and status.state in _FIRMWARE_UPDATE_PENDING_STATES:
            status = await self._poll_firmware_update_status(
                attempts=120,
                delay_seconds=1.0,
            )
            if status is not None and status.state == "downloaded":
                return await self._async_install_downloaded_firmware_update()
            return status

        if status is not None and not status.is_available:
            return status

        await self._activate_path("firmwareupdate:downloadNewUpdate")
        status = await self._poll_firmware_update_status(
            attempts=120,
            delay_seconds=1.0,
        )
        if status is not None and status.state == "downloaded":
            return await self._async_install_downloaded_firmware_update()
        return status

    async def async_upload_firmware_update(
        self,
        file_path: str,
    ) -> KefFirmwareUpdateInfo | None:
        """Upload a firmware image through the speaker settings page."""
        upload_url = f"http://{self._host}:{self._port}/settings.fcgi?firmwareupdate=1"
        form = aiohttp.FormData()

        try:
            firmware_file = open(file_path, "rb")
        except OSError as err:
            raise KefConnectionError(
                f"Unable to read firmware file {file_path}: {err}"
            ) from err

        with firmware_file:
            form.add_field(
                "datafile",
                firmware_file,
                filename=os.path.basename(file_path),
                content_type="application/octet-stream",
            )
            try:
                async with self._session.post(
                    upload_url,
                    data=form,
                    allow_redirects=False,
                    timeout=aiohttp.ClientTimeout(total=None),
                ) as response:
                    await response.text()
            except aiohttp.ClientError as err:
                raise KefConnectionError(str(err)) from err
            except TimeoutError as err:
                raise KefConnectionError(
                    "Firmware upload to the KEF speaker timed out"
                ) from err

        if response.status >= 400:
            if response.status in {401, 403}:
                raise KefAuthenticationRequiredError(
                    "KEF speaker requires authentication before firmware upload "
                    "can be used"
                )
            raise KefResponseError(f"KEF speaker returned HTTP {response.status}")

        location = response.headers.get("Location", "")
        if response.status in {301, 302, 303, 307, 308}:
            if "login" in location.lower() or location.endswith(".fcgi"):
                raise KefAuthenticationRequiredError(
                    "KEF speaker requires authentication before firmware upload "
                    "can be used"
                )
            raise KefResponseError(
                f"KEF speaker redirected firmware upload to {location}"
            )

        status = await self._poll_firmware_update_status(
            attempts=120,
            delay_seconds=1.0,
        )
        if status is None or status.state != "downloaded":
            raise KefResponseError("Firmware upload did not reach the downloaded state")

        return await self._async_install_downloaded_firmware_update()

    async def _async_install_downloaded_firmware_update(
        self,
    ) -> KefFirmwareUpdateInfo | None:
        """Install a firmware package that has already reached downloaded state."""
        await self._activate_path(
            "firmwareupdate:installUpdate",
            {"firmwareUpdateOptions": {"forceSfupdate": True}},
        )
        return await self._poll_firmware_update_status(
            attempts=10,
            delay_seconds=1.0,
        )

    async def async_poll_events(self, timeout: int = 10) -> list[dict[str, Any]]:
        """Poll the KEF event queue and return any pending updates."""
        queue_id = await self._async_ensure_event_queue()
        payload = await self._request_json(
            "GET",
            EVENT_POLL_QUEUE_ENDPOINT,
            params={
                "queueId": queue_id,
                "timeout": max(1, timeout),
            },
        )
        if not isinstance(payload, list):
            raise KefResponseError("Unexpected KEF event queue payload")
        return [event for event in payload if isinstance(event, dict)]

    async def async_reset_event_queue(self) -> None:
        """Drop the cached event queue id so it will be recreated on next poll."""
        self._event_queue_id = None

    async def _get_optional_path_value(
        self,
        path: str,
        *,
        typed_key: str | None = None,
    ) -> dict[str, Any] | Any | None:
        """Get a value from an optional path."""
        try:
            return await self._get_path_value(path, typed_key=typed_key)
        except KefError:
            return None

    async def _get_value(
        self,
        path: str,
        *,
        typed_key: str | None = None,
    ) -> dict[str, Any] | Any:
        """Backward-compatible wrapper for tests and call sites."""
        return await self._get_path_value(path, typed_key=typed_key)

    async def _get_path_value(
        self,
        path: str,
        *,
        typed_key: str | None = None,
    ) -> dict[str, Any] | Any:
        """Get the current value for a path."""
        value = await self._get_path_item(path, roles="value")
        if typed_key is None:
            return value
        if not isinstance(value, dict):
            raise KefResponseError(f"Unexpected KEF value type for {path}")
        return value.get(typed_key)

    async def _get_path_item(self, path: str, *, roles: str = "value") -> Any:
        """Fetch a raw item from a KEF API path."""
        payload = await self._request_json(
            "GET",
            GET_DATA_ENDPOINT,
            params={"path": path, "roles": roles, "_nocache": "1"},
        )
        if not isinstance(payload, list) or not payload:
            raise KefResponseError(f"Unexpected KEF payload for {path}")
        return payload[0]

    async def _update_eq_profile(self, mutator) -> None:
        """Fetch, mutate, and write back the typed EQ profile wrapper."""
        payload = await self._get_optional_path_item(
            PROBE_PATHS["eq_profile"],
            roles="value",
        )
        if payload is None:
            await self._update_eq_profile_v2(mutator)
            return

        if not isinstance(payload, dict) or payload.get("type") != "kefEqProfile":
            raise KefResponseError("Unexpected KEF EQ profile payload")

        wrapper = copy.deepcopy(payload)
        profile = wrapper.get("kefEqProfile")
        if not isinstance(profile, dict):
            raise KefResponseError("Unexpected KEF EQ profile wrapper")

        dsp_info = profile.get("dspInfo")
        if not isinstance(dsp_info, dict):
            raise KefResponseError("Unexpected KEF EQ dspInfo payload")

        mutator(dsp_info)
        await self._set_data(PROBE_PATHS["eq_profile"], role="value", value=wrapper)

    async def _update_eq_profile_v2(self, mutator) -> None:
        """Fetch, mutate, and write back the modern v2 EQ profile wrapper."""
        payload = await self._get_path_item(PROBE_PATHS["eq_profile_v2"], roles="value")
        if not isinstance(payload, dict) or payload.get("type") != "kefEqProfileV2":
            raise KefResponseError("Unexpected KEF EQ profile v2 payload")

        wrapper = copy.deepcopy(payload)
        profile = wrapper.get("kefEqProfileV2")
        if not isinstance(profile, dict):
            raise KefResponseError("Unexpected KEF EQ profile v2 wrapper")

        compat_dsp = self._eq_profile_v2_to_legacy_dsp(profile)
        mutator(compat_dsp)
        self._apply_legacy_dsp_to_eq_profile_v2(compat_dsp, profile)
        await self._set_data(PROBE_PATHS["eq_profile_v2"], role="value", value=wrapper)

    async def _get_optional_path_item(self, path: str, *, roles: str = "value") -> Any:
        """Fetch an optional raw item from a KEF API path."""
        try:
            return await self._get_path_item(path, roles=roles)
        except KefError:
            return None

    @staticmethod
    def _eq_profile_v2_to_legacy_dsp(profile: dict[str, Any]) -> dict[str, Any]:
        """Map v2 direct dB/Hz values to the existing HA control scale."""
        return {
            "balance": ModernKefClient._v2_balance_to_legacy(profile.get("balance")),
            "bassExtension": profile.get("bassExtension"),
            "trebleAmount": ModernKefClient._v2_treble_to_legacy(
                profile.get("trebleAmount")
            ),
            "subwooferGain": ModernKefClient._v2_gain_to_legacy(
                profile.get("subwooferGain")
            ),
            "deskMode": profile.get("deskMode"),
            "wallMode": profile.get("wallMode"),
            "phaseCorrection": profile.get("phaseCorrection"),
            "highPassMode": profile.get("highPassMode"),
            "highPassModeFreq": ModernKefClient._v2_high_pass_to_legacy(
                profile.get("highPassModeFreq")
            ),
        }

    @staticmethod
    def _apply_legacy_dsp_to_eq_profile_v2(
        compat_dsp: dict[str, Any],
        profile: dict[str, Any],
    ) -> None:
        """Apply existing HA control-scale values back to a v2 EQ profile."""
        if compat_dsp.get("balance") is not None:
            profile["balance"] = max(0, min(60, compat_dsp["balance"])) - 30
        if compat_dsp.get("bassExtension") is not None:
            profile["bassExtension"] = compat_dsp["bassExtension"]
        if compat_dsp.get("trebleAmount") is not None:
            legacy = max(0, min(16, compat_dsp["trebleAmount"]))
            profile["trebleAmount"] = round(((legacy / 16.0) * 6.0) - 3.0, 2)
        if compat_dsp.get("subwooferGain") is not None:
            profile["subwooferGain"] = max(0, min(20, compat_dsp["subwooferGain"])) - 10
        if compat_dsp.get("deskMode") is not None:
            profile["deskMode"] = compat_dsp["deskMode"]
        if compat_dsp.get("wallMode") is not None:
            profile["wallMode"] = compat_dsp["wallMode"]
        if compat_dsp.get("phaseCorrection") is not None:
            profile["phaseCorrection"] = compat_dsp["phaseCorrection"]
        if compat_dsp.get("highPassMode") is not None:
            profile["highPassMode"] = compat_dsp["highPassMode"]
        if compat_dsp.get("highPassModeFreq") is not None:
            legacy = max(0, min(10, compat_dsp["highPassModeFreq"]))
            profile["highPassModeFreq"] = 50 + legacy * 5

    @staticmethod
    def _v2_balance_to_legacy(value: Any) -> int | None:
        """Convert v2 -30..30 balance into the existing 0..60 UI scale."""
        return None if value is None else round(float(value)) + 30

    @staticmethod
    def _v2_treble_to_legacy(value: Any) -> int | None:
        """Convert v2 -3..3 dB treble into the existing 0..16 UI scale."""
        return None if value is None else round((float(value) + 3.0) / 6.0 * 16)

    @staticmethod
    def _v2_gain_to_legacy(value: Any) -> int | None:
        """Convert v2 -10..10 dB gain into the existing 0..20 UI scale."""
        return None if value is None else round(float(value)) + 10

    @staticmethod
    def _v2_high_pass_to_legacy(value: Any) -> int | None:
        """Convert v2 Hz high-pass frequency into the existing 0..10 step."""
        return None if value is None else round((float(value) - 50.0) / 5.0)

    async def _set_data(self, path: str, *, role: str, value: Any) -> None:
        """Set a value on the speaker."""
        await self._request_json(
            "POST",
            SET_DATA_ENDPOINT,
            json_payload={"path": path, "role": role, "value": value},
        )

    async def _activate_path(self, path: str, value: Any | None = None) -> Any:
        """Trigger an activate-style KEF API path."""
        payload_value = value
        if payload_value is None:
            payload_value = {}

        return await self._request_json(
            "POST",
            SET_DATA_ENDPOINT,
            json_payload={"path": path, "role": "activate", "value": payload_value},
        )

    async def _poll_firmware_update_status(
        self,
        *,
        attempts: int = 10,
        delay_seconds: float = 1.0,
    ) -> KefFirmwareUpdateInfo | None:
        """Poll firmware status for a short period after a trigger call."""
        last_status: KefFirmwareUpdateInfo | None = None
        for _ in range(max(1, attempts)):
            last_status = await self.async_get_firmware_update_status()
            if last_status is None:
                return None
            if last_status.state not in _FIRMWARE_UPDATE_PENDING_STATES:
                return last_status
            await asyncio.sleep(delay_seconds)
        return last_status

    async def _async_ensure_event_queue(self) -> str:
        """Create or reuse the KEF event queue."""
        if self._event_queue_id is not None:
            return self._event_queue_id

        payload = await self._request_json(
            "POST",
            EVENT_MODIFY_QUEUE_ENDPOINT,
            json_payload={
                "subscribe": list(EVENT_SUBSCRIPTIONS),
                "unsubscribe": [],
            },
        )
        if not isinstance(payload, str) or not payload:
            raise KefResponseError("Unexpected KEF queue id payload")
        self._event_queue_id = payload
        return payload

    async def _request_json(
        self,
        method: str,
        endpoint: str,
        *,
        params: Mapping[str, object] | None = None,
        json_payload: Mapping[str, object] | None = None,
    ) -> Any:
        """Issue an HTTP request to the speaker."""
        path = self._extract_nsdk_path(
            endpoint,
            params=params,
            json_payload=json_payload,
        )

        use_secure = await self._should_use_secure_request(
            method,
            endpoint,
            path=path,
        )
        try:
            if use_secure:
                return await self._request_json_secure(
                    method,
                    endpoint,
                    params=params,
                    json_payload=json_payload,
                )
            return await self._request_json_plain(
                method,
                endpoint,
                params=params,
                json_payload=json_payload,
            )
        except KefAuthenticationRequiredError:
            if use_secure or endpoint not in {GET_DATA_ENDPOINT, SET_DATA_ENDPOINT}:
                raise
            self._auth_mode = None
            if await self._should_use_secure_request(method, endpoint, path=path):
                return await self._request_json_secure(
                    method,
                    endpoint,
                    params=params,
                    json_payload=json_payload,
                )
            raise

    async def _should_use_secure_request(
        self,
        method: str,
        endpoint: str,
        *,
        path: str | None,
    ) -> bool:
        """Return whether this request should use the authenticated API."""
        if endpoint not in {GET_DATA_ENDPOINT, SET_DATA_ENDPOINT}:
            return False

        if path == PROBE_PATHS["webserver_auth_mode"] and self._auth_mode is None:
            return False

        auth_mode = await self._get_webserver_auth_mode()
        if method == "GET":
            return auth_mode == AUTH_MODE_ALL
        if method == "POST":
            return auth_mode in {AUTH_MODE_SETDATA, AUTH_MODE_ALL}
        return False

    async def _get_webserver_auth_mode(self) -> str:
        """Return the active KEF webserver auth mode."""
        if self._auth_mode is not None:
            return self._auth_mode

        auth_mode_params = {
            "path": PROBE_PATHS["webserver_auth_mode"],
            "roles": "value",
            "_nocache": "1",
        }
        try:
            payload = await self._request_json_plain(
                "GET",
                GET_DATA_ENDPOINT,
                params=auth_mode_params,
            )
        except KefAuthenticationRequiredError:
            payload = await self._request_json_secure(
                "GET",
                GET_DATA_ENDPOINT,
                params=auth_mode_params,
            )
        except KefError:
            self._auth_mode = AUTH_MODE_NONE
            return self._auth_mode

        auth_mode = AUTH_MODE_NONE
        if isinstance(payload, list) and payload:
            auth_mode = self._extract_string(payload[0]) or AUTH_MODE_NONE
        elif isinstance(payload, dict):
            value = payload.get("value")
            auth_mode = self._extract_string(value) or AUTH_MODE_NONE

        if auth_mode not in {AUTH_MODE_NONE, AUTH_MODE_SETDATA, AUTH_MODE_ALL}:
            auth_mode = AUTH_MODE_NONE

        self._auth_mode = auth_mode
        return auth_mode

    async def _request_json_plain(
        self,
        method: str,
        endpoint: str,
        *,
        params: Mapping[str, object] | None = None,
        json_payload: Mapping[str, object] | None = None,
    ) -> Any:
        """Issue a plain-text JSON request to the speaker."""
        url = self._build_url(endpoint, params=params)
        body = None
        headers: dict[str, str] = {}
        if json_payload is not None:
            body = json.dumps(json_payload)
            headers["Content-Type"] = "application/json"
        return await self._execute_json_request(
            method,
            url,
            endpoint=endpoint,
            body=body,
            headers=headers or None,
            authenticated=False,
        )

    async def _request_json_secure(
        self,
        method: str,
        endpoint: str,
        *,
        params: Mapping[str, object] | None = None,
        json_payload: Mapping[str, object] | None = None,
    ) -> Any:
        """Issue an authenticated request using the KEF HMAC/AES scheme."""
        url = self._build_url(endpoint, params=params)
        headers: dict[str, str] = {}
        body = None
        salt_b64, key = self._build_secure_key()
        if method == "POST":
            if json_payload is None:
                raise KefResponseError(
                    "Missing KEF JSON payload for authenticated POST"
                )
            path = self._extract_nsdk_path(
                endpoint,
                params=params,
                json_payload=json_payload,
            )
            if path is None:
                raise KefResponseError(
                    "Missing KEF API path for authenticated POST"
                )
            role = str(json_payload.get("role", "value"))
            wrapped_value = self._wrap_nsdk_value(json_payload.get("value"))
            encrypted_value = self._encrypt_secure_value(wrapped_value, key)
            body = json.dumps(
                {
                    "path": path,
                    "role": role,
                    "value": encrypted_value,
                },
                separators=(",", ":"),
            )
            headers["Content-Type"] = "application/json"

        headers["Authorization"] = self._build_secure_authorization(
            method,
            url,
            salt_b64=salt_b64,
            key=key,
            body=body,
        )
        return await self._execute_json_request(
            method,
            url,
            endpoint=endpoint,
            body=body,
            headers=headers,
            authenticated=True,
        )

    async def _execute_json_request(
        self,
        method: str,
        url: str,
        *,
        endpoint: str,
        body: str | None = None,
        headers: Mapping[str, str] | None = None,
        authenticated: bool,
    ) -> Any:
        """Execute a request and parse the JSON response."""
        kwargs: dict[str, object] = {
            "allow_redirects": False,
            "timeout": aiohttp.ClientTimeout(total=self._request_timeout),
        }
        if headers:
            kwargs["headers"] = dict(headers)
        if body is not None:
            kwargs["data"] = body

        try:
            async with self._session.request(method, url, **kwargs) as response:
                text = await response.text()
        except aiohttp.ClientError as err:
            raise KefConnectionError(str(err)) from err
        except TimeoutError as err:
            raise KefConnectionError("Request to KEF speaker timed out") from err

        location = response.headers.get("Location", "")
        if response.status in {301, 302, 303, 307, 308}:
            if "login" in location.lower() or location.endswith(".fcgi"):
                raise KefAuthenticationRequiredError(
                    "KEF speaker requires authentication before the local API "
                    "can be used"
                )
            raise KefResponseError(f"KEF speaker redirected {endpoint} to {location}")

        if response.status in {401, 403}:
            if authenticated:
                if self._password:
                    raise KefAuthenticationRequiredError(
                        "KEF speaker rejected the configured API password"
                    )
                raise KefAuthenticationRequiredError(
                    "KEF speaker requires a web UI password for authenticated "
                    "local API writes"
                )
            raise KefAuthenticationRequiredError(
                "KEF speaker rejected the request and may require authentication"
            )

        if not text.strip():
            if response.status >= 400:
                raise KefResponseError(f"KEF speaker returned HTTP {response.status}")
            return {}

        stripped = text.lstrip()
        if stripped.startswith("<!DOCTYPE html") or stripped.startswith("<html"):
            raise KefAuthenticationRequiredError(
                "KEF speaker returned HTML instead of JSON; the local API may "
                "require authentication"
            )

        try:
            data = json.loads(text)
        except json.JSONDecodeError as err:
            if response.status >= 400:
                raise KefResponseError(
                    f"KEF speaker returned HTTP {response.status}"
                ) from err
            raise KefResponseError(
                f"KEF speaker returned non-JSON data for {endpoint}"
            ) from err

        if response.status >= 400:
            if isinstance(data, dict) and data.get("error"):
                error = data["error"]
                message = error.get("message") if isinstance(error, dict) else None
                raise KefResponseError(message or "KEF API returned an error")
            raise KefResponseError(f"KEF speaker returned HTTP {response.status}")

        if isinstance(data, dict) and data.get("error"):
            error = data["error"]
            message = error.get("message") if isinstance(error, dict) else None
            raise KefResponseError(message or "KEF API returned an error")

        _LOGGER.debug("KEF modern %s %s -> %s", method, url, data)
        return data

    def _build_secure_authorization(
        self,
        method: str,
        url: str,
        *,
        salt_b64: str,
        key: bytes,
        body: str | None = None,
    ) -> str:
        """Build the KEF HMAC/AES authorization header."""
        username = "user"
        timestamp = str(int(time.time() * 1000))
        if method == "GET":
            message = f"{username}.{salt_b64}.{timestamp}.{url}"
        else:
            message = f"{username}.{salt_b64}.{timestamp}.{url}.{body or ''}"
        signature = base64.b64encode(
            hmac.new(key, message.encode("utf-8"), hashlib.sha256).digest()
        ).decode("ascii")
        username_b64 = base64.b64encode(username.encode("utf-8")).decode("ascii")
        return (
            f"HMAC_SHA256_AES256 {username_b64}.{salt_b64}.{timestamp}.{signature}"
        )

    def _build_secure_key(self) -> tuple[str, bytes]:
        """Create the per-request KEF salt and AES/HMAC key."""
        salt = os.urandom(6)
        salt_b64 = base64.b64encode(salt).decode("ascii")
        key = hashlib.sha256(salt + self._password.encode("utf-8")).digest()
        return salt_b64, key

    @staticmethod
    def _encrypt_secure_value(value: Any, key: bytes) -> str:
        """Encrypt the KEF request payload value for an authenticated POST."""
        plaintext = (
            value
            if isinstance(value, str)
            else json.dumps(value, separators=(",", ":"))
        )
        plaintext_bytes = plaintext.encode("utf-8")
        pad_len = 16 - (len(plaintext_bytes) % 16)
        padded = plaintext_bytes + bytes([pad_len]) * pad_len
        iv = os.urandom(16)
        cipher = Cipher(algorithms.AES(key), modes.CBC(iv)).encryptor()
        ciphertext = cipher.update(padded) + cipher.finalize()
        return base64.b64encode(iv + ciphertext).decode("ascii")

    @staticmethod
    def _wrap_nsdk_value(value: Any) -> Any:
        """Wrap primitive values using the KEF nSDK type envelope."""
        if isinstance(value, bool):
            return {"type": "bool_", "bool_": value}
        if isinstance(value, str):
            return {"type": "string_", "string_": value}
        if isinstance(value, int):
            return {"type": "i32_", "i32_": value}
        return value

    @staticmethod
    def _extract_nsdk_path(
        endpoint: str,
        *,
        params: Mapping[str, object] | None = None,
        json_payload: Mapping[str, object] | None = None,
    ) -> str | None:
        """Return the nSDK path carried by a GET/POST KEF API request."""
        if endpoint == GET_DATA_ENDPOINT and params is not None:
            path = params.get("path")
            return str(path) if path is not None else None
        if endpoint == SET_DATA_ENDPOINT and json_payload is not None:
            path = json_payload.get("path")
            return str(path) if path is not None else None
        return None

    async def _async_get_default_volume_by_source(
        self,
        source_list: tuple[str, ...],
    ) -> dict[str, int]:
        """Fetch startup-volume values for each supported source."""
        values: dict[str, int] = {}
        for source in source_list:
            try:
                value = self._extract_int(
                    await self._get_optional_path_value(
                        self._default_volume_path_for_source(source),
                        typed_key="i32_",
                    )
                )
            except KefError:
                value = None
            if value is not None:
                values[source] = value
        return values

    def _build_url(
        self,
        endpoint: str,
        *,
        params: Mapping[str, object] | None = None,
    ) -> str:
        """Build the request URL."""
        endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        authority = self._host
        if self._port != DEFAULT_PORT:
            authority = f"{authority}:{self._port}"
        url = f"http://{authority}{API_ROOT}{endpoint}"
        if not params:
            return url
        query = urlencode(
            [(key, str(value)) for key, value in params.items()],
            doseq=True,
        )
        return f"{url}?{query}"

    @staticmethod
    def _default_volume_path_for_source(source: str) -> str:
        """Return the API path for a source-specific startup volume."""
        suffix = DEFAULT_VOLUME_SOURCE_SUFFIX.get(source)
        if suffix is None:
            raise KefUnsupportedDeviceError(
                f"Unsupported startup-volume source: {source}"
            )
        return f"settings:/kef/host/defaultVolume{suffix}"

    @staticmethod
    def _extract_string(value: dict[str, Any] | Any | None) -> str | None:
        """Extract a string from a typed or raw value."""
        if value is None:
            return None
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for key in (
                "string_",
                "kefSpeakerStatus",
                "kefPhysicalSource",
                "playerPlayMode",
                "kefStandbyMode",
                "kefWakeUpSource",
                "webserverAuthMode",
                "kefCableMode",
                "kefMasterChannelMode",
                "airableStreamBitrate",
                "kefFavouriteButtonFunction",
                "kefNetworkStability",
                "kefSpeedTestStatus",
            ):
                raw = value.get(key)
                if isinstance(raw, str):
                    return raw
        return None

    @staticmethod
    def _extract_float(value: dict[str, Any] | Any | None) -> float | None:
        """Extract a float from a typed or raw value."""
        if isinstance(value, int | float):
            return float(value)
        if isinstance(value, dict):
            raw = value.get("double_")
            if isinstance(raw, int | float):
                return float(raw)
        return None

    @staticmethod
    def _extract_int(value: dict[str, Any] | Any | None) -> int | None:
        """Extract an integer from a typed or raw value."""
        if isinstance(value, int):
            return value
        if isinstance(value, dict):
            for key in ("i32_", "i16_"):
                raw = value.get(key)
                if isinstance(raw, int):
                    return raw
        return None

    @staticmethod
    def _extract_bool(value: dict[str, Any] | Any | None) -> bool | None:
        """Extract a boolean from a typed or raw value."""
        if isinstance(value, bool):
            return value
        if isinstance(value, dict):
            raw = value.get("bool_")
            if isinstance(raw, bool):
                return raw
        return None

    def _parse_playback(
        self,
        player_data: dict[str, Any] | Any | None,
        play_time: dict[str, Any] | Any | None,
    ) -> KefPlaybackInfo | None:
        """Parse the current playback object."""
        if not isinstance(player_data, dict):
            return None

        track_roles = player_data.get("trackRoles", {})
        metadata = track_roles.get("mediaData", {}).get("metaData", {})
        active_resource = track_roles.get("mediaData", {}).get("activeResource", {})
        status = player_data.get("status", {})
        controls = player_data.get("controls", {})
        position_ms = play_time if isinstance(play_time, int) else None
        if position_ms == -1:
            position_ms = None

        normalized_controls: dict[str, bool] = {}
        if isinstance(controls, dict):
            for key, value in controls.items():
                if isinstance(value, bool):
                    normalized_controls[key.removesuffix("_")] = value

        return KefPlaybackInfo(
            state=player_data.get("state"),
            title=track_roles.get("title"),
            artist=metadata.get("artist"),
            album_artist=metadata.get("albumArtist") or metadata.get("artist"),
            album=metadata.get("album"),
            image_url=track_roles.get("icon"),
            service_id=metadata.get("serviceID"),
            codec=(
                active_resource.get("codec")
                if isinstance(active_resource, dict)
                else None
            ),
            sample_frequency=(
                active_resource.get("sampleFrequency")
                if isinstance(active_resource, dict)
                else None
            ),
            stream_sample_rate=(
                active_resource.get("streamSampleRate")
                if isinstance(active_resource, dict)
                else None
            ),
            stream_channels=(
                active_resource.get("streamChannels")
                if isinstance(active_resource, dict)
                else None
            ),
            audio_channels=(
                active_resource.get("nrAudioChannels")
                if isinstance(active_resource, dict)
                else None
            ),
            duration_ms=status.get("duration") if isinstance(status, dict) else None,
            position_ms=position_ms,
            controls=normalized_controls,
        )

    @staticmethod
    def _extract_alert_counts(
        value: dict[str, Any] | Any | None,
    ) -> tuple[int | None, int | None]:
        """Extract alarm and timer counts from an alerts list payload."""
        if not isinstance(value, dict):
            return (None, None)
        alerts = value.get("alertsList")
        if not isinstance(alerts, dict):
            return (None, None)
        alarms = alerts.get("alarms")
        timers = alerts.get("timers")
        alarm_count = len(alarms) if isinstance(alarms, list) else None
        timer_count = len(timers) if isinstance(timers, list) else None
        return (alarm_count, timer_count)

    @staticmethod
    def _source_list_for_model(model: str) -> tuple[str, ...]:
        """Return the supported sources for a modern KEF model."""
        normalized = model.upper()
        return MODERN_MODEL_SOURCE_MAP.get(normalized, DEFAULT_MODERN_SOURCE_LIST)


class LegacyBinaryClient(BaseKefClient):
    """Minimal binary-protocol client for first-generation KEF speakers."""

    backend = KefBackend.LEGACY

    def __init__(
        self,
        host: str,
        *,
        port: int = DEFAULT_LEGACY_PORT,
        request_timeout: float = 2.0,
        standby_time: int | None = 20,
    ) -> None:
        """Initialize the legacy client."""
        super().__init__(host)
        self._port = port
        self._request_timeout = request_timeout
        self._standby_time = standby_time
        self._last_active_source: str | None = None

    async def async_identify(self) -> KefDeviceInfo:
        """Probe the legacy speaker."""
        await self._send_command(bytes([_LEGACY_GET_START, ord("0"), _LEGACY_GET_END]))
        return KefDeviceInfo(
            backend=self.backend,
            unique_id=f"kef-legacy-{self._host}",
            device_name="KEF",
            model="KEF Legacy",
            host=self._host,
            port=self._port,
        )

    async def async_refresh(self) -> KefSnapshot:
        """Fetch current state from the legacy speaker."""
        device = await self.async_identify()
        source_response = await self._send_command(
            bytes([_LEGACY_GET_START, ord("0"), _LEGACY_GET_END])
        )
        volume_response = await self._send_command(
            bytes([_LEGACY_GET_START, ord("%"), _LEGACY_GET_END])
        )
        play_pause_response = await self._send_command(
            bytes([_LEGACY_GET_START, ord("1"), _LEGACY_GET_END])
        )

        is_on = source_response <= 128
        source_code = source_response % 128
        source = _INPUT_SOURCES_RESPONSE.get(source_code, ("Unknown", None, "L/R"))[0]
        if source not in (None, "Unknown", STATE_OFF):
            self._last_active_source = source
        is_muted = volume_response >= 128
        volume_raw = volume_response % 128

        playback_state = None
        if play_pause_response == 129:
            playback_state = "playing"
        elif play_pause_response == 128:
            playback_state = "paused"

        return KefSnapshot(
            device=device,
            speaker_status="powerOn" if is_on else STATE_OFF,
            source=source,
            cable_mode=None,
            master_channel=None,
            volume_raw=volume_raw,
            volume_level=volume_raw / 100.0,
            is_muted=is_muted,
            play_mode=None,
            playback=KefPlaybackInfo(state=playback_state),
            eq_profile=None,
            firmware_update=None,
            wifi_info=None,
            standby_mode=None,
            startup_tone_enabled=None,
            auto_switch_hdmi=None,
            front_led_enabled=None,
            standby_led_enabled=None,
            top_panel_enabled=None,
            top_panel_led_enabled=None,
            top_panel_standby_led_enabled=None,
            wake_source=None,
            subwoofer_wake_enabled=None,
            kw1_wake_enabled=None,
            usb_charging_enabled=None,
            startup_volume_enabled=None,
            per_input_startup_volume_enabled=None,
            default_volume_global=None,
            maximum_volume=None,
            volume_step=None,
            volume_limit_enabled=None,
            fixed_volume_level=None,
            remote_ir_enabled=None,
            remote_ir_code=None,
            favourite_button=None,
            eq_button_1=None,
            eq_button_2=None,
            analytics_enabled=None,
            app_analytics_enabled=None,
            streaming_quality=None,
            ui_language=None,
            speaker_location=None,
            network_ping_ms=None,
            network_stability=None,
            speed_test_status=None,
            speed_test_average_download=None,
            speed_test_current_download=None,
            speed_test_packet_loss=None,
            alert_alarm_count=None,
            alert_timer_count=None,
            alert_snooze_minutes=None,
            player_notification_active=None,
            source_list=LEGACY_SOURCE_LIST,
            default_volume_by_source={},
        )

    async def async_turn_on(self) -> None:
        """Turn on the speaker."""
        snapshot = await self.async_refresh()
        target_source = self._last_active_source
        if target_source in (None, STATE_OFF, "Unknown"):
            current_source = snapshot.source
            target_source = (
                current_source if current_source not in (None, "Unknown") else "Wifi"
            )
        await self.async_select_source(target_source)

    async def async_turn_off(self) -> None:
        """Turn off the speaker."""
        snapshot = await self.async_refresh()
        state = snapshot.source or "Wifi"
        await self._set_source(state, off=True)

    async def async_set_volume_raw(self, volume: int) -> None:
        """Set the raw volume level."""
        clamped = max(0, min(100, volume))
        await self._send_command(
            bytes([_LEGACY_SET_START, ord("%"), _LEGACY_SET_MID, clamped])
        )

    async def async_toggle_play_pause(self) -> None:
        """Toggle play/pause."""
        await self._send_command(
            bytes([_LEGACY_SET_START, ord("1"), _LEGACY_SET_MID, 129])
        )

    async def async_set_muted(self, muted: bool) -> None:
        """Set the muted state."""
        snapshot = await self.async_refresh()
        if muted:
            await self.async_set_volume_raw(0)
            return

        target_volume = snapshot.volume_raw or 15
        if target_volume == 0:
            target_volume = 15
        await self.async_set_volume_raw(target_volume)

    async def async_next_track(self) -> None:
        """Skip to the next track."""
        await self._send_command(
            bytes([_LEGACY_SET_START, ord("1"), _LEGACY_SET_MID, 130])
        )

    async def async_previous_track(self) -> None:
        """Go to the previous track."""
        await self._send_command(
            bytes([_LEGACY_SET_START, ord("1"), _LEGACY_SET_MID, 131])
        )

    async def async_select_source(self, source: str) -> None:
        """Select the active source."""
        if source not in (None, STATE_OFF):
            self._last_active_source = source
        await self._set_source(source)

    async def async_set_standby_mode(self, mode: str) -> None:
        """Legacy speakers do not expose standby mode settings."""
        raise KefUnsupportedDeviceError("Standby mode is not supported for legacy KEF")

    async def async_set_startup_tone_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose startup tone settings."""
        raise KefUnsupportedDeviceError("Startup tone is not supported for legacy KEF")

    async def async_set_auto_switch_hdmi_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose HDMI auto-switch settings."""
        raise KefUnsupportedDeviceError(
            "HDMI auto switching is not supported for legacy KEF"
        )

    async def async_set_front_led_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose front LED settings."""
        raise KefUnsupportedDeviceError("Front LED is not supported for legacy KEF")

    async def async_set_standby_led_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose standby LED settings."""
        raise KefUnsupportedDeviceError("Standby LED is not supported for legacy KEF")

    async def async_set_top_panel_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose top-panel settings."""
        raise KefUnsupportedDeviceError("Top panel is not supported for legacy KEF")

    async def async_set_top_panel_led_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose top-panel LED settings."""
        raise KefUnsupportedDeviceError(
            "Top-panel LED is not supported for legacy KEF"
        )

    async def async_set_top_panel_standby_led_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose top-panel standby LED settings."""
        raise KefUnsupportedDeviceError(
            "Top-panel standby LED is not supported for legacy KEF"
        )

    async def async_set_wake_source(self, source: str) -> None:
        """Legacy speakers do not expose wake-source settings."""
        raise KefUnsupportedDeviceError("Wake source is not supported for legacy KEF")

    async def async_set_subwoofer_wake_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose wired subwoofer wake settings."""
        raise KefUnsupportedDeviceError(
            "Subwoofer wake on startup is not supported for legacy KEF"
        )

    async def async_set_kw1_wake_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose KW1 subwoofer wake settings."""
        raise KefUnsupportedDeviceError(
            "KW1 wake on startup is not supported for legacy KEF"
        )

    async def async_set_usb_charging_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose USB charging settings."""
        raise KefUnsupportedDeviceError("USB charging is not supported for legacy KEF")

    async def async_set_startup_volume_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose startup-volume settings."""
        raise KefUnsupportedDeviceError(
            "Startup volume is not supported for legacy KEF"
        )

    async def async_set_per_input_startup_volume_enabled(
        self,
        enabled: bool,
    ) -> None:
        """Legacy speakers do not expose per-input startup-volume settings."""
        raise KefUnsupportedDeviceError(
            "Per-input startup volume is not supported for legacy KEF"
        )

    async def async_set_default_volume_global(self, volume: int) -> None:
        """Legacy speakers do not expose global startup-volume settings."""
        raise KefUnsupportedDeviceError(
            "Global startup volume is not supported for legacy KEF"
        )

    async def async_set_maximum_volume(self, volume: int) -> None:
        """Legacy speakers do not expose maximum-volume settings."""
        raise KefUnsupportedDeviceError(
            "Maximum volume is not supported for legacy KEF"
        )

    async def async_set_volume_step(self, step: int) -> None:
        """Legacy speakers do not expose volume-step settings."""
        raise KefUnsupportedDeviceError("Volume step is not supported for legacy KEF")

    async def async_set_volume_limit_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose volume-limiter settings."""
        raise KefUnsupportedDeviceError(
            "Volume limiter is not supported for legacy KEF"
        )

    async def async_set_default_volume_for_source(
        self,
        source: str,
        volume: int,
    ) -> None:
        """Legacy speakers do not expose per-source startup-volume settings."""
        raise KefUnsupportedDeviceError(
            "Per-source startup volume is not supported for legacy KEF"
        )

    async def async_set_cable_mode(self, mode: str) -> None:
        """Legacy speakers do not expose cable-mode configuration."""
        raise KefUnsupportedDeviceError("Cable mode is not supported for legacy KEF")

    async def async_set_balance(self, value: int) -> None:
        """Legacy speakers do not expose EQ balance configuration."""
        raise KefUnsupportedDeviceError("EQ balance is not supported for legacy KEF")

    async def async_set_bass_extension(self, value: str) -> None:
        """Legacy speakers do not expose bass-extension configuration."""
        raise KefUnsupportedDeviceError(
            "Bass extension is not supported for legacy KEF"
        )

    async def async_set_treble_amount(self, value: int) -> None:
        """Legacy speakers do not expose treble configuration."""
        raise KefUnsupportedDeviceError(
            "Treble amount is not supported for legacy KEF"
        )

    async def async_set_subwoofer_gain(self, value: int) -> None:
        """Legacy speakers do not expose subwoofer-gain configuration."""
        raise KefUnsupportedDeviceError(
            "Subwoofer gain is not supported for legacy KEF"
        )

    async def async_set_desk_mode_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose desk-mode configuration."""
        raise KefUnsupportedDeviceError("Desk mode is not supported for legacy KEF")

    async def async_set_wall_mode_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose wall-mode configuration."""
        raise KefUnsupportedDeviceError("Wall mode is not supported for legacy KEF")

    async def async_set_phase_correction_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose phase-correction configuration."""
        raise KefUnsupportedDeviceError(
            "Phase correction is not supported for legacy KEF"
        )

    async def async_set_high_pass_mode_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose high-pass configuration."""
        raise KefUnsupportedDeviceError(
            "High-pass mode is not supported for legacy KEF"
        )

    async def async_set_high_pass_frequency(self, value: int) -> None:
        """Legacy speakers do not expose high-pass-frequency configuration."""
        raise KefUnsupportedDeviceError(
            "High-pass frequency is not supported for legacy KEF"
        )

    async def async_set_master_channel(self, channel: str) -> None:
        """Legacy speakers do not expose master-channel configuration."""
        raise KefUnsupportedDeviceError(
            "Master channel is not supported for legacy KEF"
        )

    async def async_set_fixed_volume_level(self, volume: int) -> None:
        """Legacy speakers do not expose fixed-volume configuration."""
        raise KefUnsupportedDeviceError(
            "Fixed volume is not supported for legacy KEF"
        )

    async def async_set_remote_ir_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose IR remote configuration."""
        raise KefUnsupportedDeviceError(
            "IR remote settings are not supported for legacy KEF"
        )

    async def async_set_remote_ir_code(self, code: str) -> None:
        """Legacy speakers do not expose IR remote code configuration."""
        raise KefUnsupportedDeviceError(
            "IR remote code settings are not supported for legacy KEF"
        )

    async def async_set_favourite_button_action(self, action: str) -> None:
        """Legacy speakers do not expose favourite button configuration."""
        raise KefUnsupportedDeviceError(
            "Favourite button settings are not supported for legacy KEF"
        )

    async def async_set_eq_button_action(self, button: int, action: str) -> None:
        """Legacy speakers do not expose EQ button configuration."""
        raise KefUnsupportedDeviceError(
            "EQ button settings are not supported for legacy KEF"
        )

    async def async_set_analytics_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose analytics settings."""
        raise KefUnsupportedDeviceError(
            "Analytics settings are not supported for legacy KEF"
        )

    async def async_set_app_analytics_enabled(self, enabled: bool) -> None:
        """Legacy speakers do not expose app analytics settings."""
        raise KefUnsupportedDeviceError(
            "App analytics settings are not supported for legacy KEF"
        )

    async def async_set_streaming_quality(self, quality: str) -> None:
        """Legacy speakers do not expose Airable streaming quality settings."""
        raise KefUnsupportedDeviceError(
            "Streaming quality settings are not supported for legacy KEF"
        )

    async def async_set_ui_language(self, language: str) -> None:
        """Legacy speakers do not expose UI language settings."""
        raise KefUnsupportedDeviceError(
            "UI language settings are not supported for legacy KEF"
        )

    async def async_set_speaker_location(self, location: str) -> None:
        """Legacy speakers do not expose speaker location settings."""
        raise KefUnsupportedDeviceError(
            "Speaker location settings are not supported for legacy KEF"
        )

    async def async_get_firmware_update_status(self) -> KefFirmwareUpdateInfo | None:
        """Legacy speakers do not expose firmware-update status."""
        raise KefUnsupportedDeviceError(
            "Firmware updates are not supported for legacy KEF"
        )

    async def async_check_for_firmware_update(self) -> KefFirmwareUpdateInfo | None:
        """Legacy speakers do not expose firmware update checks."""
        raise KefUnsupportedDeviceError(
            "Firmware updates are not supported for legacy KEF"
        )

    async def async_install_firmware_update(self) -> KefFirmwareUpdateInfo | None:
        """Legacy speakers do not expose firmware installation."""
        raise KefUnsupportedDeviceError(
            "Firmware updates are not supported for legacy KEF"
        )

    async def async_upload_firmware_update(
        self,
        file_path: str,
    ) -> KefFirmwareUpdateInfo | None:
        """Legacy speakers do not expose firmware uploads."""
        raise KefUnsupportedDeviceError(
            "Firmware updates are not supported for legacy KEF"
        )

    async def _set_source(self, source: str, *, off: bool = False) -> None:
        """Set the current source."""
        if source not in _INPUT_SOURCES:
            raise KefUnsupportedDeviceError(f"Unsupported legacy source: {source}")
        source_code = _INPUT_SOURCES[source][self._standby_time][0] % 128
        if off:
            source_code += 128
        await self._send_command(
            bytes([_LEGACY_SET_START, ord("0"), _LEGACY_SET_MID, source_code])
        )

    async def _send_command(self, payload: bytes) -> int:
        """Send a command over the legacy binary socket."""
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self._host, self._port, family=socket.AF_INET),
                timeout=self._request_timeout,
            )
        except OSError as err:
            raise KefConnectionError(str(err)) from err

        try:
            writer.write(payload)
            await writer.drain()
            raw_reply = await asyncio.wait_for(
                reader.read(100),
                timeout=self._request_timeout,
            )
        except (OSError, TimeoutError) as err:
            raise KefConnectionError(str(err)) from err
        finally:
            writer.close()
            await writer.wait_closed()

        response = self._parse_response(payload, raw_reply)
        code = response[-2]
        if payload[0] == _LEGACY_SET_START and code != _LEGACY_RESPONSE_OK:
            raise KefResponseError(f"Legacy KEF command failed with code {code}")
        return code

    @staticmethod
    def _parse_response(message: bytes, reply: bytes) -> bytes:
        """Extract the matching response packet."""
        responses = [b"R" + chunk for chunk in reply.split(b"R") if chunk]
        if message[0] == _LEGACY_GET_START:
            query_type = message[1]
            for response in responses:
                if len(response) > 1 and response[1] == query_type:
                    return response
            raise KefResponseError("Legacy KEF query type did not match the response")
        if message[0] == _LEGACY_SET_START:
            ok = bytes([82, 17, 255])
            if ok in responses:
                return ok
            raise KefResponseError("Legacy KEF did not acknowledge the command")
        raise KefResponseError("Legacy KEF returned an unknown response")


async def async_create_client(
    host: str,
    session: aiohttp.ClientSession,
    *,
    backend: KefBackend | str | None = None,
    port: int | None = None,
    password: str | None = None,
    tcp_port: int | None = None,
) -> BaseKefClient:
    """Create the appropriate KEF backend client."""
    normalized_backend = KefBackend(backend) if backend is not None else None

    if normalized_backend is KefBackend.MODERN:
        client = ModernKefClient(
            host,
            session,
            port=port or DEFAULT_PORT,
            password=password,
        )
        await client.async_identify()
        return client

    if normalized_backend is KefBackend.LEGACY:
        client = LegacyBinaryClient(host, port=tcp_port or DEFAULT_LEGACY_PORT)
        await client.async_identify()
        return client

    modern_client = ModernKefClient(
        host,
        session,
        port=port or DEFAULT_PORT,
        password=password,
    )
    try:
        await modern_client.async_identify()
    except KefAuthenticationRequiredError:
        raise
    except KefError:
        pass
    else:
        return modern_client

    legacy_client = LegacyBinaryClient(host, port=tcp_port or DEFAULT_LEGACY_PORT)
    try:
        await legacy_client.async_identify()
    except KefError as err:
        raise KefUnsupportedDeviceError(
            f"Unable to detect a supported KEF API on {host}"
        ) from err
    return legacy_client
