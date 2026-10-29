"""The shared entity contract reports normal pre-refresh initialization state."""

import pytest
from homeassistant.const import CONF_HOST
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.translation import async_get_translations
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.kef import number, select, switch, text
from custom_components.kef.const import CONF_BACKEND, DOMAIN
from custom_components.kef.coordinator import KefCoordinator
from custom_components.kef.entity import KefEntity
from tests.conftest import TEST_HOST


@pytest.fixture
async def uninitialized_coordinator(hass):
    """Use the real constructor state before any first refresh has run."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        data={CONF_HOST: TEST_HOST, CONF_BACKEND: "modern"},
    )
    entry.add_to_hass(hass)
    return KefCoordinator(hass, entry)


async def test_uninitialized_coordinator_client_has_translated_error(
    hass,
    uninitialized_coordinator,
):
    """Before the first refresh, every action's client accessor has one error."""
    coordinator = uninitialized_coordinator
    assert coordinator.client is None
    entity = KefEntity(coordinator)
    with pytest.raises(HomeAssistantError) as error:
        _ = entity.client
    assert error.value.translation_domain == DOMAIN
    assert error.value.translation_key == "not_initialized"
    translations = await async_get_translations(hass, "en", "exceptions", {DOMAIN})
    assert translations[
        "component.kef.exceptions.not_initialized.message"
    ] == str(error.value)
    assert coordinator.client is None


@pytest.mark.parametrize(
    ("action", "value"),
    [
        (number._async_set_maximum_volume, 80),
        (select._async_set_standby_mode, "20 minutes"),
        (switch._async_set_startup_tone, True),
        (text._async_set_ui_language, "en_GB"),
    ],
    ids=["number", "select", "switch", "text"],
)
async def test_uninitialized_setting_action_reports_same_error(
    uninitialized_coordinator, action, value,
):
    """Each settings family reports a setup error instead of silent success."""
    coordinator = uninitialized_coordinator
    with pytest.raises(HomeAssistantError) as error:
        await action(coordinator, value)
    assert error.value.translation_domain == DOMAIN
    assert error.value.translation_key == "not_initialized"
    assert coordinator.client is None
    assert coordinator.data is None
