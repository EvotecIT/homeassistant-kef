"""Model-specific configuration entity tests for KEF."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from custom_components.kef.select import async_setup_entry as async_setup_selects
from custom_components.kef.switch import async_setup_entry as async_setup_switches
from tests.conftest import TEST_SNAPSHOT


async def _entity_keys_for_model(model: str) -> tuple[set[str], set[str]]:
    """Return switch and select keys created for a modern model."""
    snapshot = deepcopy(TEST_SNAPSHOT)
    snapshot.device.model = model
    coordinator = Mock()
    coordinator.data = snapshot
    coordinator.last_update_success = True
    coordinator.config_entry = SimpleNamespace(domain="kef")
    coordinator.hass = Mock()
    entry = SimpleNamespace(runtime_data=coordinator)

    switches = []
    selects = []
    await async_setup_switches(Mock(), entry, switches.extend)
    await async_setup_selects(Mock(), entry, selects.extend)
    return (
        {entity.entity_description.key for entity in switches},
        {entity.entity_description.key for entity in selects},
    )


@pytest.mark.parametrize("model", ["LSX2LT", "LSXIILT"])
async def test_lsx_ii_lt_hides_only_known_unsupported_controls(model: str) -> None:
    """Both observed model identifiers should produce the same capability UI."""
    switches, selects = await _entity_keys_for_model(model)

    unsupported_switches = {
        "front_led",
        "top_panel",
        "top_panel_led",
        "top_panel_standby_led",
    }
    assert unsupported_switches.isdisjoint(switches)
    assert {"desk_mode", "wall_mode"} <= switches
    assert "cable_mode" not in selects
    assert "master_channel" in selects


async def test_xio_keeps_top_panel_controls_and_hides_pair_controls() -> None:
    """The soundbar should expose its physical panel without stereo-pair settings."""
    switches, selects = await _entity_keys_for_model("XIO")

    assert {"top_panel", "top_panel_led", "top_panel_standby_led"} <= switches
    assert {"front_led", "desk_mode", "wall_mode"}.isdisjoint(switches)
    assert {"master_channel", "cable_mode"}.isdisjoint(selects)


async def test_unverified_ls60_placement_controls_remain_visible() -> None:
    """Do not hide settings solely from form-factor assumptions."""
    switches, selects = await _entity_keys_for_model("LS60")

    assert {"desk_mode", "wall_mode", "front_led"} <= switches
    assert {"top_panel", "top_panel_led", "top_panel_standby_led"}.isdisjoint(
        switches
    )
    assert {"master_channel", "cable_mode"} <= selects


async def test_unknown_models_keep_all_reported_controls() -> None:
    """A new model should default to the values actually reported by its API."""
    switches, selects = await _entity_keys_for_model("FUTURE")

    assert {"front_led", "top_panel", "desk_mode", "wall_mode"} <= switches
    assert {"master_channel", "cable_mode"} <= selects
