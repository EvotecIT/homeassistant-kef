"""Media-player platform for KEF."""

from __future__ import annotations

from homeassistant.components.media_player import (
    MediaPlayerEntity,
    MediaPlayerEntityFeature,
    MediaPlayerState,
    MediaType,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import KefConfigEntry, KefCoordinator
from .entity import KefEntity


async def async_setup_entry(
    hass: HomeAssistant,
    entry: KefConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up the KEF media player."""
    coordinator = entry.runtime_data
    async_add_entities([KefMediaPlayer(coordinator)])


class KefMediaPlayer(KefEntity, CoordinatorEntity[KefCoordinator], MediaPlayerEntity):
    """Representation of a KEF speaker."""

    _attr_icon = "mdi:speaker-wireless"
    _attr_supported_features = (
        MediaPlayerEntityFeature.TURN_ON
        | MediaPlayerEntityFeature.TURN_OFF
        | MediaPlayerEntityFeature.VOLUME_SET
        | MediaPlayerEntityFeature.VOLUME_STEP
        | MediaPlayerEntityFeature.VOLUME_MUTE
        | MediaPlayerEntityFeature.SELECT_SOURCE
        | MediaPlayerEntityFeature.PLAY
        | MediaPlayerEntityFeature.PAUSE
        | MediaPlayerEntityFeature.NEXT_TRACK
        | MediaPlayerEntityFeature.PREVIOUS_TRACK
    )

    def __init__(self, coordinator: KefCoordinator) -> None:
        """Initialize the entity."""
        CoordinatorEntity.__init__(self, coordinator)
        KefEntity.__init__(self, coordinator)
        self._attr_unique_id = coordinator.data.device.unique_id
        self._attr_name = None
        self._last_volume_before_mute = coordinator.data.volume_raw or 15

    @property
    def available(self) -> bool:
        """Return whether the entity is available."""
        return self.coordinator.last_update_success

    @property
    def source_list(self) -> list[str]:
        """Return the list of supported sources."""
        return list(self.coordinator.data.source_list)

    @property
    def state(self) -> MediaPlayerState | None:
        """Return the current player state."""
        data = self.coordinator.data
        if not self.available:
            return MediaPlayerState.UNAVAILABLE
        if not data.is_power_on:
            return MediaPlayerState.OFF
        if data.playback is None or data.playback.state is None:
            return MediaPlayerState.ON
        if data.playback.state == "playing":
            return MediaPlayerState.PLAYING
        if data.playback.state == "paused":
            return MediaPlayerState.PAUSED
        return MediaPlayerState.ON

    @property
    def volume_level(self) -> float | None:
        """Return the volume level."""
        return self.coordinator.data.volume_level

    @property
    def is_volume_muted(self) -> bool | None:
        """Return whether the speaker is muted."""
        return self.coordinator.data.is_muted

    @property
    def source(self) -> str | None:
        """Return the active source."""
        return self.coordinator.data.source

    @property
    def media_title(self) -> str | None:
        """Return the current title."""
        playback = self.coordinator.data.playback
        return playback.title if playback is not None else None

    @property
    def media_artist(self) -> str | None:
        """Return the current artist."""
        playback = self.coordinator.data.playback
        return playback.artist if playback is not None else None

    @property
    def media_album_name(self) -> str | None:
        """Return the current album."""
        playback = self.coordinator.data.playback
        return playback.album if playback is not None else None

    @property
    def media_image_url(self) -> str | None:
        """Return the artwork URL."""
        playback = self.coordinator.data.playback
        return playback.image_url if playback is not None else None

    @property
    def media_content_type(self) -> MediaType | None:
        """Return the media type."""
        playback = self.coordinator.data.playback
        if playback is None:
            return None
        if playback.title or playback.artist or playback.service_id:
            return MediaType.MUSIC
        return None

    @property
    def media_position(self) -> int | None:
        """Return the playback position in seconds."""
        playback = self.coordinator.data.playback
        if playback is None or playback.position_ms is None or playback.position_ms < 0:
            return None
        return playback.position_ms // 1000

    @property
    def media_duration(self) -> int | None:
        """Return the media duration in seconds."""
        playback = self.coordinator.data.playback
        if playback is None or playback.duration_ms is None:
            return None
        return playback.duration_ms // 1000

    @property
    def extra_state_attributes(self) -> dict[str, object]:
        """Return extra state attributes."""
        snapshot = self.coordinator.data
        playback = snapshot.playback
        eq_profile = snapshot.eq_profile
        return {
            "backend": snapshot.device.backend.value,
            "speaker_status": snapshot.speaker_status,
            "cable_mode": snapshot.cable_mode,
            "master_channel": snapshot.master_channel,
            "play_mode": snapshot.play_mode,
            "service_id": playback.service_id if playback else None,
            "album_artist": playback.album_artist if playback else None,
            "codec": playback.codec if playback else None,
            "sample_frequency": playback.sample_frequency if playback else None,
            "stream_sample_rate": playback.stream_sample_rate if playback else None,
            "stream_channels": playback.stream_channels if playback else None,
            "audio_channels": playback.audio_channels if playback else None,
            "controls": playback.controls if playback else {},
            "firmware_version": snapshot.device.firmware_version,
            "release_text": snapshot.device.release_text,
            "model_code": snapshot.device.model_code,
            "mac_address": snapshot.device.mac_address,
            "wifi_signal_level": (
                snapshot.wifi_info.signal_level if snapshot.wifi_info else None
            ),
            "wifi_ssid": snapshot.wifi_info.ssid if snapshot.wifi_info else None,
            "wifi_frequency": (
                snapshot.wifi_info.frequency if snapshot.wifi_info else None
            ),
            "wifi_bssid": snapshot.wifi_info.bssid if snapshot.wifi_info else None,
            "eq_profile_name": eq_profile.profile_name if eq_profile else None,
            "eq_expert_mode": eq_profile.is_expert_mode if eq_profile else None,
            "standby_mode": snapshot.standby_mode,
            "startup_tone_enabled": snapshot.startup_tone_enabled,
            "auto_switch_hdmi": snapshot.auto_switch_hdmi,
            "front_led_enabled": snapshot.front_led_enabled,
            "standby_led_enabled": snapshot.standby_led_enabled,
            "top_panel_enabled": snapshot.top_panel_enabled,
            "wake_source": snapshot.wake_source,
            "subwoofer_wake_enabled": snapshot.subwoofer_wake_enabled,
            "kw1_wake_enabled": snapshot.kw1_wake_enabled,
            "usb_charging_enabled": snapshot.usb_charging_enabled,
            "startup_volume_enabled": snapshot.startup_volume_enabled,
            "per_input_startup_volume_enabled": (
                snapshot.per_input_startup_volume_enabled
            ),
            "default_volume_global": snapshot.default_volume_global,
            "default_volume_by_source": snapshot.default_volume_by_source,
            "maximum_volume": snapshot.maximum_volume,
            "volume_step": snapshot.volume_step,
            "volume_limit_enabled": snapshot.volume_limit_enabled,
            "fixed_volume_level": snapshot.fixed_volume_level,
        }

    async def async_turn_on(self) -> None:
        """Turn on the speaker."""
        await self.coordinator.client.async_turn_on()
        await self.coordinator.async_request_refresh()

    async def async_turn_off(self) -> None:
        """Turn off the speaker."""
        await self.coordinator.client.async_turn_off()
        await self.coordinator.async_request_refresh()

    async def async_set_volume_level(self, volume: float) -> None:
        """Set the volume level."""
        raw_volume = round(max(0.0, min(1.0, volume)) * 100)
        if raw_volume > 0:
            self._last_volume_before_mute = raw_volume
        await self.coordinator.client.async_set_volume_raw(raw_volume)
        await self.coordinator.async_request_refresh()

    async def async_volume_up(self) -> None:
        """Raise the volume."""
        current = self.coordinator.data.volume_raw or 0
        await self.coordinator.client.async_set_volume_raw(min(100, current + 4))
        await self.coordinator.async_request_refresh()

    async def async_volume_down(self) -> None:
        """Lower the volume."""
        current = self.coordinator.data.volume_raw or 0
        await self.coordinator.client.async_set_volume_raw(max(0, current - 4))
        await self.coordinator.async_request_refresh()

    async def async_mute_volume(self, mute: bool) -> None:
        """Mute or unmute the speaker."""
        current = self.coordinator.data.volume_raw or 0
        if not mute and current == 0:
            self._last_volume_before_mute = max(1, self._last_volume_before_mute)
        await self.coordinator.client.async_set_muted(mute)
        await self.coordinator.async_request_refresh()

    async def async_select_source(self, source: str) -> None:
        """Select the input source."""
        await self.coordinator.client.async_select_source(source)
        await self.coordinator.async_request_refresh()

    async def async_media_play(self) -> None:
        """Play or resume playback."""
        if self.state != MediaPlayerState.PLAYING:
            await self.coordinator.client.async_toggle_play_pause()
            await self.coordinator.async_request_refresh()

    async def async_media_pause(self) -> None:
        """Pause playback."""
        if self.state == MediaPlayerState.PLAYING:
            await self.coordinator.client.async_toggle_play_pause()
            await self.coordinator.async_request_refresh()

    async def async_media_next_track(self) -> None:
        """Skip to the next track."""
        await self.coordinator.client.async_next_track()
        await self.coordinator.async_request_refresh()

    async def async_media_previous_track(self) -> None:
        """Go to the previous track."""
        await self.coordinator.client.async_previous_track()
        await self.coordinator.async_request_refresh()
