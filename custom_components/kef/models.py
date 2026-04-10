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
    album: str | None = None
    image_url: str | None = None
    service_id: str | None = None
    duration_ms: int | None = None
    position_ms: int | None = None
    controls: dict[str, bool] = field(default_factory=dict)


@dataclass(slots=True)
class KefEqProfile:
    """Flattened modern KEF EQ information."""

    is_expert_mode: bool | None = None
    profile_name: str | None = None
    balance: int | None = None
    bass_extension: str | None = None
    treble_amount: int | None = None
    subwoofer_gain: int | None = None
    high_pass_mode: bool | None = None
    high_pass_frequency: int | None = None
    desk_mode: bool | None = None
    wall_mode: bool | None = None
    phase_correction: bool | None = None
    raw: dict[str, Any] = field(default_factory=dict)

    @classmethod
    def from_modern_value(cls, value: dict[str, Any]) -> KefEqProfile:
        """Build an EQ profile from the modern API payload."""
        profile = value.get("kefEqProfile", {})
        dsp_info = profile.get("dspInfo", {})
        return cls(
            is_expert_mode=profile.get("isExpertMode"),
            profile_name=profile.get("profileName") or None,
            balance=dsp_info.get("balance"),
            bass_extension=dsp_info.get("bassExtension"),
            treble_amount=dsp_info.get("trebleAmount"),
            subwoofer_gain=dsp_info.get("subwooferGain"),
            high_pass_mode=dsp_info.get("highPassMode"),
            high_pass_frequency=dsp_info.get("highPassModeFreq"),
            desk_mode=dsp_info.get("deskMode"),
            wall_mode=dsp_info.get("wallMode"),
            phase_correction=dsp_info.get("phaseCorrection"),
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
    volume_raw: int | None
    volume_level: float | None
    is_muted: bool | None
    play_mode: str | None
    playback: KefPlaybackInfo | None
    eq_profile: KefEqProfile | None
    source_list: tuple[str, ...]

    @property
    def is_power_on(self) -> bool:
        """Return whether the speaker is on."""
        return self.speaker_status not in (None, "standby")
