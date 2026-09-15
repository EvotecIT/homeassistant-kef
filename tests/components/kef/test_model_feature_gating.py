"""Model-specific configuration entity tests for KEF."""

from __future__ import annotations

from copy import deepcopy
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from homeassistant.const import Platform
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef import _async_cleanup_optional_entities
from custom_components.kef.const import DOMAIN
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


@pytest.mark.parametrize("model", ["LS60", "LS60W"])
async def test_ls60_hides_desk_mode_but_keeps_unverified_controls_visible(
    model: str,
) -> None:
    """Hide only the confirmed-unsupported desk_mode; leave the rest visible."""
    switches, selects = await _entity_keys_for_model(model)

    assert "desk_mode" not in switches
    assert {"wall_mode", "front_led"} <= switches
    assert {"top_panel", "top_panel_led", "top_panel_standby_led"}.isdisjoint(
        switches
    )
    assert {"master_channel", "cable_mode"} <= selects


@pytest.mark.parametrize("model", ["LS50W2", "LS50WII"])
async def test_ls50_wireless_ii_keeps_top_panel_controls(model: str) -> None:
    """LS50 Wireless II supports top-panel locking in its speaker preferences."""
    switches, _selects = await _entity_keys_for_model(model)

    assert {"top_panel", "top_panel_led", "top_panel_standby_led"} <= switches


async def test_unknown_models_keep_all_reported_controls() -> None:
    """A new model should default to the values actually reported by its API."""
    switches, selects = await _entity_keys_for_model("FUTURE")

    assert {"front_led", "top_panel", "desk_mode", "wall_mode"} <= switches
    assert {"master_channel", "cable_mode"} <= selects


async def test_cleanup_removes_only_model_unsupported_registry_entries(hass) -> None:
    """An upgrade should retire gated controls without touching supported ones."""
    snapshot = deepcopy(TEST_SNAPSHOT)
    snapshot.device.model = "XIO"
    coordinator = SimpleNamespace(data=snapshot)
    entry = MockConfigEntry(domain=DOMAIN, title="XIO")
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    unique_id_prefix = f"{snapshot.device.unique_id}_"

    entries = {
        "front_led": registry.async_get_or_create(
            Platform.SWITCH,
            DOMAIN,
            f"{unique_id_prefix}front_led",
            config_entry=entry,
        ),
        "top_panel": registry.async_get_or_create(
            Platform.SWITCH,
            DOMAIN,
            f"{unique_id_prefix}top_panel",
            config_entry=entry,
        ),
        "cable_mode": registry.async_get_or_create(
            Platform.SELECT,
            DOMAIN,
            f"{unique_id_prefix}cable_mode",
            config_entry=entry,
        ),
        "standby_mode": registry.async_get_or_create(
            Platform.SELECT,
            DOMAIN,
            f"{unique_id_prefix}standby_mode",
            config_entry=entry,
        ),
    }

    await _async_cleanup_optional_entities(hass, entry, coordinator)

    assert registry.async_get(entries["front_led"].entity_id) is None
    assert registry.async_get(entries["cable_mode"].entity_id) is None
    assert registry.async_get(entries["top_panel"].entity_id) is not None
    assert registry.async_get(entries["standby_mode"].entity_id) is not None
