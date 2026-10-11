"""Legacy controls preserve volume and speaker settings on the binary wire."""

import pytest

from custom_components.kef.kef_client.client import LegacyBinaryClient
from custom_components.kef.kef_client.exceptions import KefResponseError
from tests.test_legacy_transport import legacy_server

pytestmark = pytest.mark.usefixtures("socket_enabled")


@pytest.mark.parametrize(
    ("volume", "muted", "expected"),
    [(42, True, 170), (170, False, 42), (0, True, 128), (128, False, 0),
     (170, True, 170), (42, False, 42)],
)
async def test_mute_preserves_volume_and_uses_the_mute_bit(volume, muted, expected):
    """Mute toggles the high bit without changing the stored volume."""
    async def handler(reader, writer):
        command = received[-1]
        if command[0] == ord("G"):
            writer.write(bytes([82, command[1], 129, volume, 255]))
        else:
            writer.write(b"R\x11\xff")
        await writer.drain()
        assert await reader.read() == b""

    async with legacy_server(handler, command_length=None) as (
        port, received, disconnected
    ):
        await LegacyBinaryClient("127.0.0.1", port=port).async_set_muted(muted)
        assert received == [b"G%\x80", bytes([83, 37, 129, expected])]


@pytest.mark.parametrize(
    ("current", "action", "expected_codes", "options"),
    [(226, "source", [107], {}), (226, "on", [98], {}),
     (98, "off", [226], {}), (66, "off", [82, 210], {}), (194, "off", [], {}),
     (98, "source", [75], {"standby_time": 20}),
     (98, "source", [91], {"standby_time": 60}),
     (82, "source", [107], {"standby_time": None})],
)
async def test_source_and_power_preserve_settings(
    current, action, expected_codes, options,
):
    """Keep R/L and standby bits, including the safe power-off sequence."""
    async def handler(reader, writer):
        command = received[-1]
        if command[0] == ord("G"):
            writer.write(bytes([82, command[1], 129, current, 255]))
        else:
            writer.write(b"R\x11\xff")
        await writer.drain()
        assert await reader.read() == b""

    async with legacy_server(handler, command_length=None) as (
        port, received, disconnected
    ):
        client = LegacyBinaryClient("127.0.0.1", port=port, **options)
        if action == "source":
            await client.async_select_source("Opt")
        elif action == "on":
            await client.async_turn_on()
        else:
            await client.async_turn_off()
        assert received == [b"G0\x80"] + [
            bytes([83, 48, 129, code]) for code in expected_codes
        ]


@pytest.mark.parametrize("action", ["mute", "source"])
async def test_unknown_settings_prevent_control_writes(action):
    """Do not write a guessed volume or source after an unknown state reply."""
    async def handler(reader, writer):
        command = received[-1]
        writer.write(bytes([82, command[1], 129, 255, 255]))
        await writer.drain()
        assert await reader.read() == b""

    async with legacy_server(handler, command_length=None) as (
        port, received, disconnected
    ):
        client = LegacyBinaryClient("127.0.0.1", port=port)
        with pytest.raises(KefResponseError):
            if action == "mute":
                await client.async_set_muted(True)
            else:
                await client.async_select_source("Opt")
        assert received == [b"G%\x80" if action == "mute" else b"G0\x80"]
