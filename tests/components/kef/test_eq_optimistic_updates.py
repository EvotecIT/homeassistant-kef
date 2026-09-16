"""Optimistic EQ entity update tests for KEF."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from custom_components.kef.exceptions import KefError
from custom_components.kef.number import _async_set_subwoofer_gain
from custom_components.kef.select import _async_set_subwoofer_preset
from tests.conftest import TEST_SNAPSHOT


def _coordinator_with_local_updates():
    """Create a lightweight coordinator that publishes local changes."""
    coordinator = Mock()
    coordinator.data = deepcopy(TEST_SNAPSHOT)

    def apply(**changes) -> None:
        coordinator.data = replace(coordinator.data, **changes)

    coordinator.async_apply_local_change = Mock(side_effect=apply)
    return coordinator


async def test_subwoofer_preset_publishes_all_written_values() -> None:
    """Preset selection should immediately publish its complete tuning tuple."""
    coordinator = _coordinator_with_local_updates()
    coordinator.client = SimpleNamespace(
        async_set_subwoofer_preset=AsyncMock(
            return_value={"gain": -1.0, "lowpass": 55.0, "highpass": 67.5}
        )
    )
    assert coordinator.data.eq_profile is not None
    original_balance = coordinator.data.eq_profile.balance

    await _async_set_subwoofer_preset(coordinator, "kc62")

    coordinator.client.async_set_subwoofer_preset.assert_awaited_once_with(
        "kc62", coordinator.data.device.model
    )
    profile = coordinator.data.eq_profile
    assert profile is not None
    assert profile.subwoofer_preset == "kc62"
    assert profile.subwoofer_gain == -1.0
    assert profile.sub_out_low_pass_frequency == 55.0
    assert profile.high_pass_frequency == 67.5
    assert profile.balance == original_balance


async def test_manual_tuning_publishes_custom_preset() -> None:
    """Manual subwoofer tuning should immediately retire the named preset."""
    coordinator = _coordinator_with_local_updates()
    coordinator.client = SimpleNamespace(async_set_subwoofer_gain=AsyncMock())
    assert coordinator.data.eq_profile is not None
    coordinator.data.eq_profile.subwoofer_preset = "kc62"

    await _async_set_subwoofer_gain(coordinator, -2)

    profile = coordinator.data.eq_profile
    assert profile is not None
    assert profile.subwoofer_gain == -2
    assert profile.subwoofer_preset == "custom"


async def test_failed_preset_write_does_not_publish_optimistic_state() -> None:
    """A rejected device write must leave the coordinator snapshot unchanged."""
    coordinator = _coordinator_with_local_updates()
    coordinator.client = SimpleNamespace(
        async_set_subwoofer_preset=AsyncMock(side_effect=KefError("write failed"))
    )
    before = deepcopy(coordinator.data)

    with pytest.raises(KefError, match="write failed"):
        await _async_set_subwoofer_preset(coordinator, "kc62")

    assert coordinator.data == before
    coordinator.async_apply_local_change.assert_not_called()
