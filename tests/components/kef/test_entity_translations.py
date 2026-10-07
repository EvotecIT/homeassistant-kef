"""Host-loaded entity translations retain KEF names and registry identity."""

from copy import deepcopy
from dataclasses import replace
from unittest.mock import patch

import pytest
from homeassistant.const import CONF_HOST
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.icon import async_get_icons
from homeassistant.helpers.translation import async_get_translations
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef.const import CONF_BACKEND, CONF_ENABLE_DIAGNOSTICS, DOMAIN
from custom_components.kef.coordinator import KefCoordinator
from tests.conftest import TEST_HOST, TEST_SNAPSHOT


@pytest.mark.parametrize("language", ["en", "fr"])
@pytest.mark.parametrize("model", ["LSXII", "XIO"])
async def test_host_translations_preserve_labels_and_custom_names(
    hass, language, model
):
    """Both model families resolve labels, placeholders, and English fallback."""
    hass.config.language = language
    snapshot = deepcopy(TEST_SNAPSHOT)
    snapshot.device = replace(snapshot.device, model=model)
    entry = MockConfigEntry(
        domain=DOMAIN,
        title=snapshot.device.device_name,
        unique_id=snapshot.device.unique_id,
        data={CONF_HOST: TEST_HOST, CONF_BACKEND: snapshot.device.backend},
        options={CONF_ENABLE_DIAGNOSTICS: True},
    )
    entry.add_to_hass(hass)
    registry = er.async_get(hass)
    old = registry.async_get_or_create(
        "number",
        DOMAIN,
        f"{snapshot.device.unique_id}_maximum_volume",
        config_entry=entry,
        suggested_object_id="living_room_volume_limit",
        original_name="VOL: Maximum volume",
    )
    registry.async_update_entity(old.entity_id, name="Family volume limit")

    async def refresh(coordinator):
        coordinator.async_set_updated_data(snapshot)

    with patch.object(KefCoordinator, "async_config_entry_first_refresh", refresh):
        assert await hass.config_entries.async_setup(entry.entry_id)
        await hass.async_block_till_done()

    translations = await async_get_translations(hass, language, "entity", {DOMAIN})
    children = [
        child
        for child in er.async_entries_for_config_entry(registry, entry.entry_id)
        if child.domain not in {"media_player", "binary_sensor"}
    ]
    assert len(children) > 50
    for child in children:
        assert child.translation_key
        key = f"component.kef.entity.{child.domain}.{child.translation_key}.name"
        placeholders = {}
        if child.translation_key == "source_startup_volume":
            source = child.unique_id.rsplit("_", 1)[1]
            placeholders["source"] = {
                "wifi": "Wi-Fi",
                "bluetooth": "Bluetooth",
                "tv": "TV",
                "optical": "Optical",
                "usb": "USB",
                "analog": "Analog",
            }[source]
        expected = translations[key].format(**placeholders)
        assert child.original_name == expected
        assert expected

    icons = (await async_get_icons(hass, "entity", {DOMAIN}))[DOMAIN]
    assert icons["number"]["source_startup_volume"]["default"] == (
        "mdi:volume-medium"
    )
    assert icons["text"]["ui_language"]["default"] == "mdi:translate"
    if model == "XIO":
        assert icons["button"]["start_calibration"]["default"] == (
            "mdi:tune"
        )
    player = next(
        item for item in er.async_entries_for_config_entry(registry, entry.entry_id)
        if item.domain == "media_player"
    )
    assert hass.states.get(player.entity_id).attributes["device_class"] == "speaker"

    current = registry.async_get(old.entity_id)
    assert current.unique_id == old.unique_id
    assert current.original_name == "VOL: Maximum volume"
    assert current.name == "Family volume limit"
    assert (
        hass.states.get(old.entity_id).attributes["friendly_name"]
        == "Family volume limit"
    )
    source_id = registry.async_get_entity_id(
        "number", DOMAIN, f"{snapshot.device.unique_id}_default_volume_wifi"
    )
    assert registry.async_get(source_id).original_name == "VOL: Wi-Fi startup volume"
    if model == "XIO":
        button_id = registry.async_get_entity_id(
            "button", DOMAIN, f"{snapshot.device.unique_id}_start_calibration"
        )
        assert registry.async_get(button_id).original_name == "DSP: Start calibration"
    assert await hass.config_entries.async_unload(entry.entry_id)
