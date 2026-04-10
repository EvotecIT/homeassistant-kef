"""Media-player behavior tests for KEF."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

from homeassistant.components.media_player import MediaPlayerEntityFeature

from custom_components.kef.media_player import KefMediaPlayer
from tests.conftest import TEST_SNAPSHOT


def _build_player(snapshot):
    """Create a media-player entity with a lightweight coordinator stub."""
    coordinator = Mock()
    coordinator.data = snapshot
    coordinator.last_update_success = True
    coordinator.config_entry = SimpleNamespace(domain="kef")
    return KefMediaPlayer(coordinator)


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
