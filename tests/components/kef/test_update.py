"""Update-entity tests for KEF."""

from __future__ import annotations

from dataclasses import replace
from datetime import timedelta
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest
from homeassistant.setup import async_setup_component
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import (
    MockEntityPlatform,
    async_fire_time_changed,
)

from custom_components.kef.exceptions import (
    KefAuthenticationRequiredError,
    KefConnectionError,
)
from custom_components.kef.models import KefFirmwareUpdateInfo
from custom_components.kef.update import KefFirmwareUpdateEntity, nightly_check_time
from tests.conftest import TEST_DEVICE_INFO


def test_firmware_latest_version_reports_downloaded_update() -> None:
    """Downloaded firmware should still expose the pending version."""
    entity = KefFirmwareUpdateEntity.__new__(KefFirmwareUpdateEntity)
    entity.coordinator = SimpleNamespace(
        data=SimpleNamespace(
            device=TEST_DEVICE_INFO,
            firmware_update=KefFirmwareUpdateInfo(
                state="downloaded",
                available_version="3.0.135.0x60acbcf",
            ),
        ),
    )

    assert entity.installed_version == TEST_DEVICE_INFO.firmware_version
    assert entity.latest_version == "3.0.135.0x60acbcf"


def test_firmware_update_reports_downloading_update_in_progress() -> None:
    """Downloading-update firmware state should be exposed as in progress."""
    entity = KefFirmwareUpdateEntity.__new__(KefFirmwareUpdateEntity)
    entity.coordinator = SimpleNamespace(
        data=SimpleNamespace(
            device=TEST_DEVICE_INFO,
            firmware_update=KefFirmwareUpdateInfo(state="downloadingUpdate"),
        ),
    )

    assert entity.in_progress is True


class _PlatformUpdateEntity(KefFirmwareUpdateEntity):
    """The real entity without device info, for the platform tests.

    Recent Home Assistant versions read `device_info` when an entity is added,
    and the real one needs a real config entry. These tests are about the
    update step and the schedule, not about the device registry.
    """

    device_info = None


def _checking_entity(
    *,
    model: str = "LSXII",
    state: str | None = "idle",
    last_update_success: bool = True,
    check: AsyncMock | None = None,
    entity_class: type[KefFirmwareUpdateEntity] = KefFirmwareUpdateEntity,
):
    """Create an update entity with a fake coordinator and client."""
    entity = entity_class.__new__(entity_class)
    entity.coordinator = SimpleNamespace(
        data=SimpleNamespace(
            device=replace(TEST_DEVICE_INFO, model=model),
            firmware_update=(
                KefFirmwareUpdateInfo(state=state) if state is not None else None
            ),
        ),
        client=SimpleNamespace(
            async_check_for_firmware_update=check or AsyncMock(),
        ),
        async_request_refresh=AsyncMock(),
        last_update_success=last_update_success,
        config_entry=SimpleNamespace(title="Bedroom", domain="kef"),
    )
    return entity


@pytest.mark.parametrize(
    "unique_id",
    [f"84:17:15:0{n}:00:0{n}_firmware" for n in range(10)] + ["", "x"],
)
def test_nightly_check_time_is_inside_the_speakers_own_window(unique_id) -> None:
    """Every speaker is asked between 02:30 and 04:00, when they update themselves."""
    assert (2, 30) <= nightly_check_time(unique_id) < (4, 0)


def test_nightly_check_time_is_stable_and_spread_between_speakers() -> None:
    """A speaker keeps its time, and the speakers are not all asked at once."""
    ids = [f"84:17:15:0{n}:00:0{n}_firmware" for n in range(7)]

    assert nightly_check_time(ids[0]) == nightly_check_time(ids[0])
    assert len({nightly_check_time(unique_id) for unique_id in ids}) > 1


def test_update_entity_does_not_poll() -> None:
    """The check runs on its nightly schedule, not on an interval."""
    assert _checking_entity().should_poll is False


async def test_update_asks_the_speaker_to_check_then_refreshes() -> None:
    """The update step must reach the speaker, not only re-read its status."""
    entity = _checking_entity()

    await entity.async_update()

    entity.coordinator.client.async_check_for_firmware_update.assert_awaited_once()
    entity.coordinator.async_request_refresh.assert_awaited_once()


async def test_update_checks_when_the_speaker_reports_no_update_info() -> None:
    """A speaker that has not reported update info yet can still be asked."""
    entity = _checking_entity(state=None)

    await entity.async_update()

    entity.coordinator.client.async_check_for_firmware_update.assert_awaited_once()


@pytest.mark.parametrize(
    "state",
    [
        "checkingForUpdate",
        "downloading",
        "downloadingUpdate",
        "downloaded",
        "installing",
        "updateInProgress",
    ],
)
async def test_update_does_not_interrupt_an_image_in_progress(state) -> None:
    """A speaker that is checking, downloading, or installing is left alone."""
    entity = _checking_entity(state=state)

    await entity.async_update()

    entity.coordinator.client.async_check_for_firmware_update.assert_not_awaited()
    entity.coordinator.async_request_refresh.assert_awaited_once()


async def test_update_does_not_check_an_unreachable_speaker() -> None:
    """An offline speaker is only refreshed, so nothing fails or logs errors."""
    entity = _checking_entity(last_update_success=False)

    await entity.async_update()

    entity.coordinator.client.async_check_for_firmware_update.assert_not_awaited()
    entity.coordinator.async_request_refresh.assert_awaited_once()


@pytest.mark.parametrize("model", ["LSXII", "LSXIILT", "LS50WII", "LS60W", "XIO"])
async def test_update_checks_every_model(model) -> None:
    """The main firmware check is the same on every modern speaker, XIO included."""
    entity = _checking_entity(model=model)

    await entity.async_update()

    entity.coordinator.client.async_check_for_firmware_update.assert_awaited_once()


async def test_update_survives_a_failed_check() -> None:
    """A check that fails is logged at debug level and does not raise."""
    entity = _checking_entity(
        check=AsyncMock(side_effect=KefConnectionError("timed out"))
    )

    await entity.async_update()

    entity.coordinator.async_request_refresh.assert_awaited_once()


async def test_update_does_nothing_for_a_disabled_entity() -> None:
    """A disabled entity ignores manual update requests."""
    entity = _checking_entity()
    entity.registry_entry = SimpleNamespace(disabled=True)

    await entity.async_update()

    entity.coordinator.client.async_check_for_firmware_update.assert_not_awaited()
    entity.coordinator.async_request_refresh.assert_not_awaited()


async def _platform_entity(hass):
    """Add an update entity to Home Assistant's update platform."""
    assert await async_setup_component(hass, "homeassistant", {})
    assert await async_setup_component(hass, "update", {})
    entity = _checking_entity(entity_class=_PlatformUpdateEntity)
    entity.coordinator.async_add_listener = Mock(return_value=Mock())
    entity.coordinator_context = None
    entity.hass = hass
    entity.entity_id = "update.bedroom_firmware"
    entity._attr_unique_id = "84:17:15:03:52:c4_firmware"
    entity._attr_name = "Firmware"
    entity._releases = None
    entity._releases_fetched_at = 0.0
    platform = MockEntityPlatform(hass, domain="update", platform_name="kef")
    await platform.async_add_entities([entity])
    return entity


async def test_homeassistant_update_entity_service_reaches_the_speaker(hass) -> None:
    """"Check for updates" in Settings > Updates calls this service."""
    entity = await _platform_entity(hass)

    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": "update.bedroom_firmware"},
        blocking=True,
    )

    entity.coordinator.client.async_check_for_firmware_update.assert_awaited_once()
    await entity.async_remove()


async def test_firmware_check_starts_reauth_when_reads_still_succeed(hass) -> None:
    """Write-only authentication must prompt reauth despite a successful refresh."""
    entity = await _platform_entity(hass)
    entity.coordinator.config_entry.async_start_reauth = Mock()
    entity.coordinator.client.async_check_for_firmware_update.side_effect = (
        KefAuthenticationRequiredError("API password required for writes")
    )

    await hass.services.async_call(
        "homeassistant",
        "update_entity",
        {"entity_id": entity.entity_id},
        blocking=True,
    )

    entity.coordinator.config_entry.async_start_reauth.assert_called_once_with(hass)
    entity.coordinator.async_request_refresh.assert_awaited_once()
    await entity.async_remove()


async def test_nightly_schedule_asks_the_speaker_to_check(hass) -> None:
    """When the speaker's time arrives, Home Assistant runs the check."""
    entity = await _platform_entity(hass)
    hour, minute = nightly_check_time(entity.unique_id)
    tomorrow = dt_util.now() + timedelta(days=1)
    due = tomorrow.replace(hour=hour, minute=minute, second=1, microsecond=0)

    async_fire_time_changed(hass, due)
    await hass.async_block_till_done()

    entity.coordinator.client.async_check_for_firmware_update.assert_awaited_once()
    entity.coordinator.async_request_refresh.assert_awaited()

    await entity.async_remove()
    async_fire_time_changed(hass, due + timedelta(days=1))
    await hass.async_block_till_done()

    entity.coordinator.client.async_check_for_firmware_update.assert_awaited_once()
