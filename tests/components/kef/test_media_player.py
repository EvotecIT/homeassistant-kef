"""Media-player behavior tests for KEF."""

from __future__ import annotations

import asyncio
from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

from homeassistant.components.media_player import MediaPlayerEntityFeature
from homeassistant.exceptions import HomeAssistantError

from custom_components.kef.exceptions import (
    KefAuthenticationRequiredError,
    KefError,
)
from custom_components.kef.media_player import KefMediaPlayer
from tests.conftest import TEST_SNAPSHOT


def _build_player(snapshot):
    """Create a media-player entity with a lightweight coordinator stub."""
    coordinator = Mock()
    coordinator.data = snapshot
    coordinator.last_update_success = True
    coordinator.config_entry = SimpleNamespace(
        domain="kef",
        async_start_reauth=Mock(),
    )
    coordinator.hass = Mock()
    return KefMediaPlayer(coordinator)


def _wire_volume_writes(player, device_volume=None):
    """Stub a speaker that holds its own level, and a coordinator that publishes.

    ``async_apply_local_change`` on the real coordinator replaces ``data`` and
    notifies listeners; the plain Mock coordinator used here would swallow it,
    which is exactly the behavior these tests need to observe.
    """
    device = {
        "volume": device_volume
        if device_volume is not None
        else (player.coordinator.data.volume_raw or 0)
    }
    written: list[int] = []

    async def _write(raw_volume: int) -> None:
        written.append(raw_volume)
        device["volume"] = raw_volume

    async def _read() -> int:
        return device["volume"]

    def _apply(**changes) -> None:
        player.coordinator.data = replace(player.coordinator.data, **changes)

    player.coordinator.client = SimpleNamespace(
        async_set_volume_raw=AsyncMock(side_effect=_write),
        async_get_volume_raw=AsyncMock(side_effect=_read),
        async_set_muted=AsyncMock(),
    )
    player.coordinator.async_apply_local_change = Mock(side_effect=_apply)
    player.coordinator.async_request_refresh = AsyncMock()
    return written, device


def test_unavailable_player_has_no_media_state() -> None:
    """Unavailable speakers should rely on entity availability, not a media state."""
    player = _build_player(deepcopy(TEST_SNAPSHOT))
    player.coordinator.last_update_success = False

    assert player.available is False
    assert player.state is None
    assert player.entity_picture == player.media_image_url


def test_modern_supported_features_hide_unsupported_transport_controls() -> None:
    """Modern sources should only expose transport controls when KEF says they work."""
    snapshot = deepcopy(TEST_SNAPSHOT)
    assert snapshot.playback is not None
    snapshot.playback.controls = {"pause": False, "next": False, "previous": False}

    player = _build_player(snapshot)

    assert player.supported_features & MediaPlayerEntityFeature.TURN_ON
    assert not player.supported_features & MediaPlayerEntityFeature.PLAY
    assert not player.supported_features & MediaPlayerEntityFeature.PAUSE
    assert not player.supported_features & MediaPlayerEntityFeature.NEXT_TRACK
    assert not player.supported_features & MediaPlayerEntityFeature.PREVIOUS_TRACK


def test_modern_supported_features_expose_transport_controls_when_available() -> None:
    """Modern sources should expose transport controls when KEF marks them usable."""
    snapshot = deepcopy(TEST_SNAPSHOT)
    assert snapshot.playback is not None
    snapshot.playback.controls = {"pause": True, "next": True, "previous": True}

    player = _build_player(snapshot)

    assert player.supported_features & MediaPlayerEntityFeature.PLAY
    assert player.supported_features & MediaPlayerEntityFeature.PAUSE
    assert player.supported_features & MediaPlayerEntityFeature.NEXT_TRACK
    assert player.supported_features & MediaPlayerEntityFeature.PREVIOUS_TRACK


def test_legacy_supported_features_keep_transport_controls() -> None:
    """Legacy speakers should continue to expose the classic transport controls."""
    snapshot = deepcopy(TEST_SNAPSHOT)
    snapshot.device.backend = snapshot.device.backend.LEGACY
    assert snapshot.playback is not None
    snapshot.playback.controls = {}

    player = _build_player(snapshot)

    assert player.supported_features & MediaPlayerEntityFeature.PLAY
    assert player.supported_features & MediaPlayerEntityFeature.PAUSE
    assert player.supported_features & MediaPlayerEntityFeature.NEXT_TRACK
    assert player.supported_features & MediaPlayerEntityFeature.PREVIOUS_TRACK


async def test_volume_auth_failure_starts_reauth() -> None:
    """Runtime auth failures should start reauth and raise a HA error."""
    snapshot = deepcopy(TEST_SNAPSHOT)
    player = _build_player(snapshot)
    player.coordinator.client = SimpleNamespace(
        async_set_volume_raw=AsyncMock(
            side_effect=KefAuthenticationRequiredError("bad password")
        )
    )
    player.coordinator.async_request_refresh = AsyncMock()

    try:
        await player.async_set_volume_level(0.5)
    except HomeAssistantError as err:
        assert "valid web UI password" in str(err)
    else:
        raise AssertionError("Expected HomeAssistantError")

    player.coordinator.config_entry.async_start_reauth.assert_called_once_with(
        player.coordinator.hass
    )
    player.coordinator.async_request_refresh.assert_not_awaited()


async def test_repeated_volume_steps_do_not_reuse_a_stale_level() -> None:
    """Each step must build on the level the previous step wrote."""
    snapshot = deepcopy(TEST_SNAPSHOT)
    snapshot.volume_raw = 40
    snapshot.volume_level = 0.40
    player = _build_player(snapshot)
    written, _device = _wire_volume_writes(player)

    await player.async_volume_up()
    await player.async_volume_up()
    await player.async_volume_up()
    await player.async_volume_down()

    assert written == [44, 48, 52, 48]
    assert player.coordinator.data.volume_raw == 48
    assert player.coordinator.data.volume_level == 0.48


async def test_volume_commands_do_not_wait_for_a_refresh() -> None:
    """Volume writes must not block on a poll; the coordinator reconciles later."""
    snapshot = deepcopy(TEST_SNAPSHOT)
    snapshot.volume_raw = 40
    player = _build_player(snapshot)
    _wire_volume_writes(player)

    await player.async_volume_up()
    await player.async_set_volume_level(0.7)
    await player.async_mute_volume(True)

    player.coordinator.async_request_refresh.assert_not_awaited()


async def test_volume_step_is_a_no_op_at_the_limits() -> None:
    """Stepping past a limit should not send a redundant write."""
    snapshot = deepcopy(TEST_SNAPSHOT)
    snapshot.volume_raw = 100
    player = _build_player(snapshot)
    written, device = _wire_volume_writes(player, device_volume=100)

    await player.async_volume_up()
    assert written == []

    device["volume"] = 0  # the limit is the speaker's level, not the cached one
    await player.async_volume_down()
    assert written == []


async def test_set_volume_level_publishes_the_written_level() -> None:
    """An absolute set should also become the base for the next step."""
    snapshot = deepcopy(TEST_SNAPSHOT)
    snapshot.volume_raw = 40
    player = _build_player(snapshot)
    written, _device = _wire_volume_writes(player)

    await player.async_set_volume_level(0.7)
    await player.async_volume_up()

    assert written == [70, 74]


async def test_mute_publishes_the_new_mute_state() -> None:
    """Mute toggles read back their own write instead of a stale poll."""
    snapshot = deepcopy(TEST_SNAPSHOT)
    snapshot.is_muted = False
    player = _build_player(snapshot)
    _wire_volume_writes(player)

    await player.async_mute_volume(True)
    assert player.coordinator.data.is_muted is True

    await player.async_mute_volume(False)
    assert player.coordinator.data.is_muted is False


async def test_steps_read_the_speaker_not_the_cached_level() -> None:
    """A level changed outside HA must not be overwritten by a stale step."""
    snapshot = deepcopy(TEST_SNAPSHOT)
    snapshot.volume_raw = 40  # what HA still believes
    player = _build_player(snapshot)
    written, _device = _wire_volume_writes(player, device_volume=20)  # reality

    await player.async_volume_up()

    assert written == [24]


async def test_concurrent_steps_do_not_collide() -> None:
    """Overlapping presses must not both read the same level."""
    snapshot = deepcopy(TEST_SNAPSHOT)
    snapshot.volume_raw = 40
    player = _build_player(snapshot)
    written, device = _wire_volume_writes(player, device_volume=40)

    await asyncio.gather(*(player.async_volume_up() for _ in range(3)))

    assert written == [44, 48, 52]
    assert device["volume"] == 52


async def test_step_falls_back_to_the_cached_level_when_the_read_fails() -> None:
    """A failed read shouldn't fail the command; the write still surfaces errors."""
    snapshot = deepcopy(TEST_SNAPSHOT)
    snapshot.volume_raw = 40
    player = _build_player(snapshot)
    written, _device = _wire_volume_writes(player)
    player.coordinator.client.async_get_volume_raw = AsyncMock(
        side_effect=KefError("read failed")
    )

    await player.async_volume_up()

    assert written == [44]
