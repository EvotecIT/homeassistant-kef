"""Models for the KEF integration."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any


class KefBackend(StrEnum):
    """Supported KEF backends."""

    MODERN = "modern"
    LEGACY = "legacy"


@dataclass(slots=True)
class KefPlaybackInfo:
    """Playback information."""

    state: str | None = None
    title: str | None = None
    artist: str | None = None
    album_artist: str | None = None
    album: str | None = None
    image_url: str | None = None
    service_id: str | None = None
    codec: str | None = None
    sample_frequency: int | None = None
    stream_sample_rate: int | None = None
    stream_channels: str | None = None
    audio_channels: int | None = None
    duration_ms: int | None = None
    position_ms: int | None = None
    controls: dict[str, bool] = field(default_factory=dict)


@dataclass(slots=True)
class KefFirmwareUpdateInfo:
    """Firmware-update information exposed by the modern API."""

    state: str | None = None
    download_progress: int | None = None
    available_version: str | None = None
    forced_update: bool | None = None
    image_size: int | None = None
    last_forced_version: str | None = None
    url: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_modern_value(cls, value: dict[str, Any]) -> KefFirmwareUpdateInfo | None:
        """Build firmware-update info from the modern API payload."""
        update_info = value.get("firmwareUpdateStatus", {})
        if not isinstance(update_info, dict) or not update_info:
            return None

        image = update_info.get("imageDescription", {})
        if not isinstance(image, dict):
            image = {}

        return cls(
            state=update_info.get("state"),
            download_progress=update_info.get("downloadProgress"),
            available_version=image.get("version"),
            forced_update=image.get("forcedUpdate"),
            image_size=image.get("imageSize"),
            last_forced_version=image.get("lastForcedVersion"),
            url=image.get("url"),
            raw=update_info,
        )

    @property
    def is_available(self) -> bool:
        """Return whether a newer firmware image is available."""
        return self.state in {"newUpdateAvailable", "updateAvailable"}


@dataclass(slots=True)
class KefWifiInfo:
    """Flattened KEF Wi-Fi information."""

    signal_level: int | None = None
    ssid: str | None = None
    frequency: int | None = None
    bssid: str | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_modern_value(cls, value: dict[str, Any]) -> KefWifiInfo | None:
        """Build a Wi-Fi info object from the modern API payload."""
        network_info = value.get("networkInfo", {})
        wireless = network_info.get("wireless", {})
        if not isinstance(wireless, dict) or not wireless:
            return None
        return cls(
            signal_level=wireless.get("signalLevel"),
            ssid=wireless.get("ssid"),
            frequency=wireless.get("frequency"),
            bssid=wireless.get("bssid"),
            raw=wireless,
        )


@dataclass(slots=True)
class KefEqProfile:
    """Flattened modern KEF EQ information."""

    api_version: str = "v1"
    is_expert_mode: bool | None = None
    profile_name: str | None = None
    profile_id: str | None = None
    balance: int | None = None
    bass_extension: str | None = None
    treble_amount: int | None = None
    subwoofer_gain: int | None = None
    high_pass_mode: bool | None = None
    high_pass_frequency: int | None = None
    desk_mode: bool | None = None
    desk_mode_setting: int | None = None
    wall_mode: bool | None = None
    wall_mode_setting: int | None = None
    phase_correction: bool | None = None
    audio_polarity: str | None = None
    subwoofer_polarity: str | None = None
    is_kw1: bool | None = None
    subwoofer_count: int | None = None
    sub_enable_stereo: bool | None = None
    subwoofer_preset: str | None = None
    sub_out_low_pass_frequency: int | None = None
    subwoofer_out: bool | None = None
    sound_profile: str | None = None
    dialogue_mode: bool | None = None
    wall_mounted: bool | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_modern_value(cls, value: dict[str, Any]) -> KefEqProfile:
        """Build an EQ profile from the modern API payload."""
        if value.get("type") == "kefEqProfileV2" or "kefEqProfileV2" in value:
            return cls.from_modern_v2_value(value)

        profile = value.get("kefEqProfile", {})
        dsp_info = profile.get("dspInfo", {})
        return cls(
            api_version="v1",
            is_expert_mode=profile.get("isExpertMode"),
            profile_name=profile.get("profileName") or None,
            profile_id=profile.get("profileId") or None,
            balance=dsp_info.get("balance"),
            bass_extension=dsp_info.get("bassExtension"),
            treble_amount=dsp_info.get("trebleAmount"),
            subwoofer_gain=dsp_info.get("subwooferGain"),
            high_pass_mode=dsp_info.get("highPassMode"),
            high_pass_frequency=dsp_info.get("highPassModeFreq"),
            desk_mode=dsp_info.get("deskMode"),
            desk_mode_setting=dsp_info.get("deskModeSetting"),
            wall_mode=dsp_info.get("wallMode"),
            wall_mode_setting=dsp_info.get("wallModeSetting"),
            phase_correction=dsp_info.get("phaseCorrection"),
            audio_polarity=dsp_info.get("audioPolarity"),
            subwoofer_polarity=dsp_info.get("subwooferPolarity"),
            is_kw1=dsp_info.get("isKW1"),
            subwoofer_count=dsp_info.get("subwooferCount"),
            sub_enable_stereo=dsp_info.get("subEnableStereo"),
            subwoofer_preset=dsp_info.get("subwooferPreset"),
            sub_out_low_pass_frequency=dsp_info.get("subOutLPFreq"),
            raw=profile,
        )

    @classmethod
    def from_modern_v2_value(cls, value: dict[str, Any]) -> KefEqProfile:
        """Build an EQ profile from the modern v2 payload."""
        profile = value.get("kefEqProfileV2", {})
        if not isinstance(profile, dict):
            profile = {}
        return cls(
            api_version="v2",
            is_expert_mode=profile.get("isExpertMode"),
            profile_name=profile.get("profileName") or None,
            profile_id=profile.get("profileId") or None,
            balance=cls._balance_to_legacy_scale(profile.get("balance")),
            bass_extension=profile.get("bassExtension"),
            treble_amount=cls._treble_to_legacy_scale(profile.get("trebleAmount")),
            subwoofer_gain=cls._gain_to_legacy_scale(profile.get("subwooferGain")),
            high_pass_mode=profile.get("highPassMode"),
            high_pass_frequency=cls._high_pass_to_legacy_step(
                profile.get("highPassModeFreq")
            ),
            desk_mode=profile.get("deskMode"),
            desk_mode_setting=profile.get("deskModeSetting"),
            wall_mode=profile.get("wallMode"),
            wall_mode_setting=profile.get("wallModeSetting"),
            phase_correction=profile.get("phaseCorrection"),
            audio_polarity=profile.get("audioPolarity"),
            subwoofer_polarity=profile.get("subwooferPolarity"),
            is_kw1=profile.get("isKW1"),
            subwoofer_count=profile.get("subwooferCount"),
            sub_enable_stereo=profile.get("subEnableStereo"),
            subwoofer_preset=profile.get("subwooferPreset"),
            sub_out_low_pass_frequency=profile.get("subOutLPFreq"),
            subwoofer_out=profile.get("subwooferOut"),
            sound_profile=profile.get("soundProfile"),
            dialogue_mode=profile.get("dialogueMode"),
            wall_mounted=profile.get("wallMounted"),
            raw=profile,
        )

    @staticmethod
    def _balance_to_legacy_scale(value: Any) -> int | None:
        """Convert v2 -30..30 balance into the existing 0..60 UI scale."""
        return None if value is None else round(float(value)) + 30

    @staticmethod
    def _treble_to_legacy_scale(value: Any) -> int | None:
        """Convert v2 -3..3 dB treble into the existing 0..16 UI scale."""
        return None if value is None else round((float(value) + 3.0) / 6.0 * 16)

    @staticmethod
    def _gain_to_legacy_scale(value: Any) -> int | None:
        """Convert v2 -10..10 dB gain into the existing 0..20 UI scale."""
        return None if value is None else round(float(value)) + 10

    @staticmethod
    def _high_pass_to_legacy_step(value: Any) -> int | None:
        """Convert v2 Hz high-pass frequency into the existing 0..10 step."""
        return None if value is None else round((float(value) - 50.0) / 5.0)


@dataclass(slots=True)
class KefDeviceInfo:
    """Basic KEF device information."""

    backend: KefBackend
    unique_id: str
    device_name: str
    model: str
    mac_address: str | None = None
    firmware_version: str | None = None
    release_text: str | None = None
    model_code: str | None = None
    serial_number: str | None = None
    kef_id: str | None = None
    hardware_version: str | None = None
    host: str | None = None
    port: int | None = None


@dataclass(slots=True)
class KefSnapshot:
    """Current KEF state."""

    device: KefDeviceInfo
    speaker_status: str | None
    source: str | None
    cable_mode: str | None
    master_channel: str | None
    volume_raw: int | None
    volume_level: float | None
    is_muted: bool | None
    play_mode: str | None
    playback: KefPlaybackInfo | None
    eq_profile: KefEqProfile | None
    firmware_update: KefFirmwareUpdateInfo | None
    wifi_info: KefWifiInfo | None
    standby_mode: str | None
    startup_tone_enabled: bool | None
    auto_switch_hdmi: bool | None
    front_led_enabled: bool | None
    standby_led_enabled: bool | None
    top_panel_enabled: bool | None
    top_panel_led_enabled: bool | None
    top_panel_standby_led_enabled: bool | None
    wake_source: str | None
    subwoofer_wake_enabled: bool | None
    kw1_wake_enabled: bool | None
    usb_charging_enabled: bool | None
    startup_volume_enabled: bool | None
    per_input_startup_volume_enabled: bool | None
    default_volume_global: int | None
    maximum_volume: int | None
    volume_step: int | None
    volume_limit_enabled: bool | None
    fixed_volume_level: int | None
    remote_ir_enabled: bool | None
    remote_ir_code: str | None
    favourite_button: str | None
    eq_button_1: str | None
    eq_button_2: str | None
    analytics_enabled: bool | None
    app_analytics_enabled: bool | None
    streaming_quality: str | None
    ui_language: str | None
    speaker_location: str | None
    network_ping_ms: float | None
    network_stability: str | None
    speed_test_status: str | None
    speed_test_average_download: float | None
    speed_test_current_download: float | None
    speed_test_packet_loss: float | None
    alert_alarm_count: int | None
    alert_timer_count: int | None
    alert_snooze_minutes: int | None
    player_notification_active: bool | None
    source_list: tuple[str, ...]
    default_volume_by_source: dict[str, int] = field(default_factory=dict)

    @property
    def is_power_on(self) -> bool:
        """Return whether the speaker is on."""
        return self.speaker_status not in (None, "standby")
