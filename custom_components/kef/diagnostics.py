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
    }
    return async_redact_data(data, TO_REDACT)
