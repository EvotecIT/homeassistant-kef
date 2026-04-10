"""Diagnostics support for KEF."""

from __future__ import annotations

from dataclasses import asdict

from homeassistant.components.diagnostics import async_redact_data

from .coordinator import KefConfigEntry

TO_REDACT = {"host", "mac_address", "ip", "bssid", "ssid", "dns", "gateways"}


async def async_get_config_entry_diagnostics(hass, entry: KefConfigEntry):
    """Return diagnostics for a config entry."""
    snapshot = entry.runtime_data.data
    data = {
        "entry": dict(entry.data),
        "options": dict(entry.options),
        "device": asdict(snapshot.device),
        "speaker_status": snapshot.speaker_status,
        "source": snapshot.source,
        "volume_raw": snapshot.volume_raw,
        "is_muted": snapshot.is_muted,
        "play_mode": snapshot.play_mode,
        "playback": asdict(snapshot.playback) if snapshot.playback else None,
        "eq_profile": asdict(snapshot.eq_profile) if snapshot.eq_profile else None,
        "wifi_info": asdict(snapshot.wifi_info) if snapshot.wifi_info else None,
        "standby_mode": snapshot.standby_mode,
        "startup_tone_enabled": snapshot.startup_tone_enabled,
        "auto_switch_hdmi": snapshot.auto_switch_hdmi,
        "standby_led_enabled": snapshot.standby_led_enabled,
        "top_panel_enabled": snapshot.top_panel_enabled,
        "wake_source": snapshot.wake_source,
        "usb_charging_enabled": snapshot.usb_charging_enabled,
        "startup_volume_enabled": snapshot.startup_volume_enabled,
        "per_input_startup_volume_enabled": (
            snapshot.per_input_startup_volume_enabled
        ),
        "default_volume_global": snapshot.default_volume_global,
        "default_volume_by_source": dict(snapshot.default_volume_by_source),
        "maximum_volume": snapshot.maximum_volume,
        "volume_step": snapshot.volume_step,
        "volume_limit_enabled": snapshot.volume_limit_enabled,
    }
    return async_redact_data(data, TO_REDACT)
