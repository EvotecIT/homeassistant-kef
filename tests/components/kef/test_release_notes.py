"""Release-notes parsing and update-entity integration tests for KEF."""

from __future__ import annotations

from types import SimpleNamespace

import aiohttp
import pytest

from custom_components.kef.models import KefFirmwareUpdateInfo
from custom_components.kef.release_notes import (
    RELEASE_NOTES_URL,
    find_release,
    format_release,
    parse_release_notes,
    release_notes_url,
)
from custom_components.kef.update import KefFirmwareUpdateEntity

# Trimmed from the live page, keeping its real quirks: an unclosed <li> in the
# XIO 1.3 entry, a "</dl" without ">", mixed full and major.minor versions, and
# an app changelog section that is not a speaker.
PAGE = """
<nav><a href="#lsxii" class="link">LSX II</a><a href="#xio" class="link">XIO</a></nav>
<article>
  <section id="kef-connect-ios">
    <h3>KEF Connect iOS</h3>
    <dl><dt>31-Aug-2026</dt><dd>iOS Version 1.31.0
      <ul><li>Minor improvements, bug and crash fixes</li></ul></dd></dl>
  </section>
  <section id="lsxii">
    <h3>LSX II Firmware</h3>
    <dl>
      <dt>16-Sept-2026</dt>
      <dd>
        Version 3.0.138
        <ul>
          <li>Fixed Roon playback issue</li>
          <li>Fixed DSD playback issue</li>
        </ul>
      </dd>
    </dl>
    <dl>
      <dt>23-Apr-2026</dt>
      <dd>
        Version 3.0
        <ul>
          <li>Qobuz Connect support</li>
          <li>Wi&#8209;Fi driver updated</li>
        </ul>
      </dd>
    </dl
  </section>
  <section id="xio">
    <h3>XIO Soundbar Firmware</h3>
    <dl>
      <dt>26-May-2026</dt>
      <dd>
        Version 1.4.135
        <ul>
          <li>AirPlay library updated</li>
        </ul>
      </dd>
    </dl>
    <dl>
      <dt>14-Oct-2025</dt>
      <dd>
        Version 1.3
        <ul>
          <li>Improve KW2 connection</li>
          <li>Improved accidental wake-up after TV goes into Standby
          <li>Various improvements, bug and crash fixes</li>
        </ul>
      </dd>
    </dl>
  </section>
</article>
"""


def test_parse_release_notes_groups_releases_by_section() -> None:
    """Every section with versioned releases is parsed, newest first."""
    releases = parse_release_notes(PAGE)

    assert [r.version for r in releases["lsxii"]] == ["3.0.138", "3.0"]
    assert [r.version for r in releases["xio"]] == ["1.4.135", "1.3"]
    assert releases["lsxii"][0].date == "16-Sept-2026"
    assert releases["lsxii"][1].notes == (
        "Qobuz Connect support",
        "Wi‑Fi driver updated",
    )


def test_parse_release_notes_tolerates_unclosed_list_items() -> None:
    """An unclosed <li> must not merge two notes together."""
    xio_1_3 = parse_release_notes(PAGE)["xio"][1]

    assert xio_1_3.notes == (
        "Improve KW2 connection",
        "Improved accidental wake-up after TV goes into Standby",
        "Various improvements, bug and crash fixes",
    )


def test_find_release_prefers_the_most_specific_match() -> None:
    """A speaker version matches its exact entry before a major.minor one."""
    releases = parse_release_notes(PAGE)

    exact = find_release(releases, "LSXII", "3.0.138.0xabc1234")
    assert exact is not None and exact.version == "3.0.138"

    line = find_release(releases, "LSX2", "3.0.137.0xf884312")
    assert line is not None and line.version == "3.0"


def test_find_release_returns_none_without_a_match() -> None:
    """Unknown models, unlisted versions, and missing versions yield no notes."""
    releases = parse_release_notes(PAGE)

    assert find_release(releases, "XIO", "2.0.1.0xabc") is None
    assert find_release(releases, "LSXIILT", "2.1.86.0xdc74e88") is None
    assert find_release(releases, "FUTURE", "1.0.0") is None
    assert find_release(releases, "XIO", None) is None


def test_format_release_renders_markdown() -> None:
    """Release notes render as a heading line followed by bullets."""
    release = parse_release_notes(PAGE)["xio"][0]

    assert format_release(release) == (
        "**Version 1.4.135** (26-May-2026)\n\n- AirPlay library updated"
    )


@pytest.mark.parametrize(
    ("model", "section"),
    [
        ("LSXII", "lsxii"),
        ("LSX2", "lsxii"),
        ("LSXIILT", "lsxiilt"),
        ("LS50WII", "ls50wii"),
        ("LS60W", "ls60w"),
        ("xio", "xio"),
    ],
)
def test_release_notes_url_points_at_the_model_section(model, section) -> None:
    """A known model opens its own section of KEF's page."""
    assert release_notes_url(model) == f"{RELEASE_NOTES_URL}#{section}"


def test_release_notes_url_falls_back_to_the_page_for_unknown_models() -> None:
    """An unknown model still gets a page, just not a section anchor."""
    assert release_notes_url("UNKNOWN") == RELEASE_NOTES_URL


def _update_entity(hass, firmware_version: str, available: str | None = None):
    """Create an XIO firmware update entity backed by a static snapshot."""
    entity = KefFirmwareUpdateEntity.__new__(KefFirmwareUpdateEntity)
    entity.hass = hass
    entity._releases = None
    entity._releases_fetched_at = 0.0
    entity.coordinator = SimpleNamespace(
        data=SimpleNamespace(
            device=SimpleNamespace(model="XIO", firmware_version=firmware_version),
            firmware_update=KefFirmwareUpdateInfo(
                state="newUpdateAvailable" if available else "idle",
                available_version=available,
            ),
        ),
    )
    return entity


def test_update_entity_release_url_is_a_page_not_the_firmware_image(hass) -> None:
    """The release announcements link must not be the .swu download."""
    entity = _update_entity(hass, "1.4.135", available="1.4.136")
    entity.coordinator.data.firmware_update = KefFirmwareUpdateInfo(
        state="downloaded",
        available_version="1.4.136",
        url="https://assets.kef.com/pm/pm_firmware/xio/XIO_V14136-signed.swu",
    )

    assert entity.release_url == f"{RELEASE_NOTES_URL}#xio"


def test_update_entity_has_no_release_url_without_update_info(hass) -> None:
    """No firmware-update data from the speaker means no link."""
    entity = _update_entity(hass, "1.4.135")
    entity.coordinator.data.firmware_update = None

    assert entity.release_url is None


async def test_update_entity_returns_notes_for_the_reported_version(
    hass, aioclient_mock
) -> None:
    """The dialog shows notes for the version the speaker offers."""
    aioclient_mock.get(RELEASE_NOTES_URL, text=PAGE)
    entity = _update_entity(hass, "1.3.99.0x1", available="1.4.135.0xd4e9dfd")

    notes = await entity.async_release_notes()

    assert notes is not None
    assert notes.startswith("**Version 1.4.135**")


async def test_update_entity_caches_the_page(hass, aioclient_mock) -> None:
    """Opening the dialog repeatedly fetches the page once."""
    aioclient_mock.get(RELEASE_NOTES_URL, text=PAGE)
    entity = _update_entity(hass, "1.4.135.0xd4e9dfd")

    await entity.async_release_notes()
    await entity.async_release_notes()

    assert aioclient_mock.call_count == 1


async def test_update_entity_has_no_notes_when_the_page_is_unreachable(
    hass, aioclient_mock
) -> None:
    """A failed fetch means no notes, never an error in the dialog."""
    aioclient_mock.get(RELEASE_NOTES_URL, exc=aiohttp.ClientError("offline"))
    entity = _update_entity(hass, "1.4.135.0xd4e9dfd")

    assert await entity.async_release_notes() is None


async def test_update_entity_has_no_notes_on_http_error(hass, aioclient_mock) -> None:
    """A non-success response is treated the same as unreachable."""
    aioclient_mock.get(RELEASE_NOTES_URL, status=503)
    entity = _update_entity(hass, "1.4.135.0xd4e9dfd")

    assert await entity.async_release_notes() is None
