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
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_modern_value(cls, value: dict[str, Any]) -> KefEqProfile:
        """Build an EQ profile from the modern API payload."""
        profile = value.get("kefEqProfile", {})
        dsp_info = profile.get("dspInfo", {})
        return cls(
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
    source_list: tuple[str, ...]
    default_volume_by_source: dict[str, int] = field(default_factory=dict)

    @property
    def is_power_on(self) -> bool:
        """Return whether the speaker is on."""
        return self.speaker_status not in (None, "standby")
