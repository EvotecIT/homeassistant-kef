"""Parse KEF's published firmware release notes page."""

from __future__ import annotations

import html
import re
from dataclasses import dataclass

RELEASE_NOTES_URL = "https://assets.kef.com/pm/pm_firmware/release_notes.html"

# Speaker-reported model identifiers mapped to the page's section ids.
_MODEL_SECTIONS = {
    "LSX2": "lsxii",
    "LSXII": "lsxii",
    "LSX2LT": "lsxiilt",
    "LSXIILT": "lsxiilt",
    "LS50W2": "ls50wii",
    "LS50WII": "ls50wii",
    "LS60": "ls60w",
    "LS60W": "ls60w",
    "XIO": "xio",
}

# The page is hand-maintained and not always well-formed (unclosed <li>,
# "</dl" without ">"), so releases are matched per <dt>/<dd> pair and notes
# are split on <li> start tags instead of relying on closing tags.
_SECTION_RE = re.compile(
    r'<section\s+id="([^"]+)"[^>]*>(.*?)(?=<section\s|</article>|\Z)', re.DOTALL
)
_RELEASE_RE = re.compile(r"<dt[^>]*>(.*?)</dt>\s*<dd[^>]*>(.*?)</dd>", re.DOTALL)
_VERSION_RE = re.compile(r"Version\s+(\d+(?:\.\d+)*)")
_LI_RE = re.compile(r"<li[^>]*>", re.IGNORECASE)
_TAG_RE = re.compile(r"<[^>]*>")


@dataclass(frozen=True, slots=True)
class FirmwareRelease:
    """One firmware release listed on KEF's release notes page."""

    date: str
    version: str
    notes: tuple[str, ...]


def _clean(fragment: str) -> str:
    """Strip markup and collapse whitespace."""
    return " ".join(html.unescape(_TAG_RE.sub(" ", fragment)).split())


def parse_release_notes(page: str) -> dict[str, list[FirmwareRelease]]:
    """Return releases per page section id, newest first as published."""
    sections: dict[str, list[FirmwareRelease]] = {}
    for section_id, body in _SECTION_RE.findall(page):
        releases = []
        for date, details in _RELEASE_RE.findall(body):
            version = _VERSION_RE.search(details)
            if version is None:
                continue
            notes = tuple(
                note
                for note in (_clean(item) for item in _LI_RE.split(details)[1:])
                if note
            )
            releases.append(FirmwareRelease(_clean(date), version.group(1), notes))
        if releases:
            sections[section_id] = releases
    return sections


def _version_parts(version: str) -> tuple[int, ...]:
    """Return numeric version parts, ignoring the speaker's build hash suffix."""
    version = re.sub(r"\.0x[0-9a-fA-F]+$", "", version.strip())
    match = re.match(r"\d+(?:\.\d+)*", version)
    return tuple(int(part) for part in match.group(0).split(".")) if match else ()


def find_release(
    releases: dict[str, list[FirmwareRelease]],
    model: str,
    version: str | None,
) -> FirmwareRelease | None:
    """Return the published release matching a speaker-reported version.

    The page sometimes lists only major.minor ("1.3") and sometimes the full
    version ("1.4.135"), so the most specific entry that is a prefix of the
    speaker's version wins.
    """
    section = _MODEL_SECTIONS.get(model.upper())
    if section is None or not version:
        return None
    wanted = _version_parts(version)
    best: FirmwareRelease | None = None
    for release in releases.get(section, []):
        parts = _version_parts(release.version)
        if parts and wanted[: len(parts)] == parts:
            if best is None or len(parts) > len(_version_parts(best.version)):
                best = release
    return best


def format_release(release: FirmwareRelease) -> str:
    """Render a release as Markdown for the update dialog."""
    lines = [f"**Version {release.version}** ({release.date})", ""]
    lines.extend(f"- {note}" for note in release.notes)
    return "\n".join(lines)
