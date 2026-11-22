"""First-generation DSP reads and writes use the documented TCP values."""

import asyncio
from contextlib import asynccontextmanager
from unittest.mock import AsyncMock, patch

import pytest

from custom_components.kef.kef_client.client import LegacyBinaryClient
from custom_components.kef.kef_client.exceptions import KefResponseError
from tests.test_legacy_transport import legacy_server

pytestmark = pytest.mark.usefixtures("socket_enabled")


@asynccontextmanager
async def dsp_speaker(registers):
    """Serve raw speaker registers without sharing the client's encoding."""

    async def handler(reader, writer):
        command = received[-1]
        register = command[1]
        if command[0] == ord("G"):
            writer.write(bytes([82, register, 129, registers[register], 255]))
        else:
            registers[register] = command[3]
            writer.write(b"R\x11\xff")
        await writer.drain()
        assert await reader.read() == b""

    async with legacy_server(handler, command_length=None) as (
        port,
        received,
        _,
    ):
        yield port, received


@pytest.mark.parametrize(
    ("method", "value", "register", "encoded", "field"),
    [
        ("async_set_desk_mode_db", -6.0, 0x28, 128, "desk_mode_setting"),
        ("async_set_wall_mode_db", -0.5, 0x29, 139, "wall_mode_setting"),
        ("async_set_treble_amount", 1.5, 0x2A, 135, "treble_amount"),
        ("async_set_high_pass_frequency", 120.0, 0x2B, 142, "high_pass_frequency"),
        (
            "async_set_sub_out_low_pass_frequency",
            245.0,
            0x2C,
            169,
            "sub_out_low_pass_frequency",
        ),
        ("async_set_subwoofer_gain", -5, 0x2D, 133, "subwoofer_gain"),
    ],
    ids=["desk", "wall", "treble", "high-pass", "low-pass", "sub-gain"],
)
async def test_legacy_dsp_number_writes_and_reads_back(
    method,
    value,
    register,
    encoded,
    field,
):
    values = {
        ord("0"): 11,
        ord("%"): 42,
        0x27: 0x88,
        **dict.fromkeys(range(0x28, 0x2E), 255),
    }
    async with dsp_speaker(values) as (port, received):
        client = LegacyBinaryClient("127.0.0.1", port=port)
        await getattr(client, method)(value)
        snapshot = await client.async_refresh()

        assert received[0] == bytes([83, register, 129, encoded])
        assert snapshot.source == "Opt"
        assert snapshot.volume_raw == 42
        assert snapshot.eq_profile is not None
        assert getattr(snapshot.eq_profile, field) == value


@pytest.mark.parametrize(
    ("register", "mode_bit", "field", "method", "initial", "fresh", "written"),
    [
        (0x28, 0x01, "desk_mode_setting", "async_set_desk_mode_db",
         (130, -5.0), (136, -2.0), -1.0),
        (0x29, 0x02, "wall_mode_setting", "async_set_wall_mode_db",
         (129, -5.5), (134, -3.0), -4.0),
        (0x2B, 0x08, "high_pass_frequency", "async_set_high_pass_frequency",
         (132, 70), (137, 95), 100),
    ],
    ids=["desk", "wall", "high-pass"],
)
async def test_legacy_dsp_retains_confirmed_value_when_disabled(
    register, mode_bit, field, method, initial, fresh, written,
):
    """An explicit unknown reading falls back only for a disabled mode."""
    values = {
        ord("0"): 11,
        ord("%"): 42,
        0x27: 0x80,
        **dict.fromkeys(range(0x28, 0x2E), 255),
    }
    async with dsp_speaker(values) as (port, _):
        client = LegacyBinaryClient("127.0.0.1", port=port)

        async def read_value():
            profile = (await client.async_refresh()).eq_profile
            assert profile is not None
            return getattr(profile, field)

        assert await read_value() is None

        values[0x27] |= mode_bit
        values[register], initial_value = initial
        assert await read_value() == initial_value

        values[0x27] &= ~mode_bit
        values[register] = 255
        assert await read_value() == initial_value

        values[register], fresh_value = fresh
        assert await read_value() == fresh_value
        values[register] = 255
        assert await read_value() == fresh_value

        await getattr(client, method)(written)
        values[register] = 255
        assert await read_value() == written

        values[0x27] |= mode_bit
        assert await read_value() is None

        values[ord("0")] = 139  # Optical, in standby.
        assert (await client.async_refresh()).eq_profile is None


async def test_concurrent_mode_changes_keep_each_other_and_unrelated_bits():
    values = {
        ord("0"): 11,
        ord("%"): 42,
        0x27: 0x86,
        **dict.fromkeys(range(0x28, 0x2E), 128),
    }
    async with dsp_speaker(values) as (port, received):
        client = LegacyBinaryClient("127.0.0.1", port=port)
        await asyncio.gather(
            client.async_set_desk_mode_enabled(True),
            client.async_set_wall_mode_enabled(False),
            client.async_set_high_pass_mode_enabled(True),
            client.async_set_bass_extension("extra"),
            client.async_set_subwoofer_polarity("inverted"),
        )

        writes = [command[3] for command in received if command[0] == ord("S")]
        assert len(writes) == 5
        assert all(mode & 0x04 for mode in writes)
        assert values[0x27] == 0xDD
        profile = (await client.async_refresh()).eq_profile
        assert profile is not None
        assert (profile.desk_mode, profile.wall_mode, profile.high_pass_mode) == (
            True,
            False,
            True,
        )
        assert profile.bass_extension == "extra"
        assert profile.subwoofer_polarity == "inverted"


@pytest.mark.parametrize("mode", [0x00, 0xFF], ids=["invalid", "unknown"])
async def test_unknown_mode_preserves_basic_controls_and_blocks_mode_write(mode):
    values = {ord("0"): 11, ord("%"): 42, 0x27: mode}
    async with dsp_speaker(values) as (port, received):
        client = LegacyBinaryClient("127.0.0.1", port=port)
        snapshot = await client.async_refresh()
        assert snapshot.eq_profile is None
        assert snapshot.source == "Opt"
        assert snapshot.volume_raw == 42
        with pytest.raises(KefResponseError, match="DSP mode is unavailable"):
            await client.async_set_wall_mode_enabled(True)
        assert received.count(b"G'\x80") == 2
        assert all(command[0] == ord("G") for command in received)


@pytest.mark.parametrize(
    ("method", "value"),
    [
        ("async_set_desk_mode_db", -6.5),
        ("async_set_treble_amount", 0.25),
        ("async_set_high_pass_frequency", float("nan")),
    ],
    ids=["modern-desk-range", "modern-treble-step", "nan"],
)
async def test_invalid_legacy_dsp_value_never_opens_tcp(method, value):
    client = LegacyBinaryClient("127.0.0.1")
    with patch("asyncio.open_connection", new_callable=AsyncMock) as connect:
        with pytest.raises(KefResponseError, match="Unsupported legacy DSP value"):
            await getattr(client, method)(value)
        connect.assert_not_called()
