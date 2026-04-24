"""Update-entity tests for KEF."""

from __future__ import annotations

from types import SimpleNamespace

from custom_components.kef.models import KefFirmwareUpdateInfo
from custom_components.kef.update import KefFirmwareUpdateEntity
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
