"""Real TCP contracts for legacy command acknowledgements and cleanup."""

import asyncio
from contextlib import asynccontextmanager

import pytest

from custom_components.kef.kef_client.client import LegacyBinaryClient
from custom_components.kef.kef_client.exceptions import (
    KefCommandRejectedError,
    KefConnectionError,
    KefResponseError,
)

pytestmark = pytest.mark.usefixtures("socket_enabled")


@asynccontextmanager
async def legacy_server(handler, *, command_length=4):
    tasks = []
    received = []
    disconnected = asyncio.Event()

    async def connection(reader, writer):
        try:
            if command_length is None:
                start = await reader.readexactly(1)
                command = start + await reader.readexactly(2 if start == b"G" else 3)
            else:
                command = await reader.readexactly(command_length)
            received.append(command)
            await handler(reader, writer)
        finally:
            writer.close()
            await writer.wait_closed()
            disconnected.set()

    def accept(reader, writer):
        tasks.append(asyncio.create_task(connection(reader, writer)))

    server = await asyncio.start_server(accept, "127.0.0.1", 0)
    try:
        yield server.sockets[0].getsockname()[1], received, disconnected
    finally:
        server.close()
        await server.wait_closed()
        for task in tasks:
            if not task.done():
                task.cancel()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for result in results:
            if isinstance(result, Exception):
                raise result


@pytest.mark.parametrize("split", [1, 2, 3])
async def test_set_volume_accepts_acknowledgement_across_tcp_reads(split):
    async def handler(reader, writer):
        reply = bytes([82, 17, 255])
        writer.write(reply[:split])
        await writer.drain()
        await asyncio.sleep(0.03)
        writer.write(reply[split:])
        await writer.drain()
        assert await reader.read() == b""

    async with legacy_server(handler) as (port, received, disconnected):
        client = LegacyBinaryClient("127.0.0.1", port=port)
        await client.async_set_volume_raw(42)
        await asyncio.wait_for(disconnected.wait(), 1)
        assert received == [bytes([83, 37, 129, 42])]


@pytest.mark.parametrize("reply", [b"", b"R\x11", b"R\x12\xff"])
async def test_eof_without_acknowledgement_is_a_response_error(reply):
    async def handler(reader, writer):
        writer.write(reply)
        await writer.drain()

    async with legacy_server(handler) as (port, received, disconnected):
        client = LegacyBinaryClient("127.0.0.1", port=port)
        with pytest.raises(KefResponseError) as raised:
            await client.async_set_volume_raw(42)
        assert raised.value.command == "write_volume"
        assert raised.value.phase == "waiting_for_acknowledgement"
        assert raised.value.connection_attempts == 1
        await asyncio.wait_for(disconnected.wait(), 1)
        assert len(received) == 1


@pytest.mark.parametrize("operation", ["read", "write"])
async def test_partial_data_does_not_restart_reply_deadline(operation):
    chunks_sent = []

    async def handler(reader, writer):
        while True:
            writer.write(b"R")
            await writer.drain()
            chunks_sent.append(b"R")
            try:
                if await asyncio.wait_for(reader.read(1), 0.05) == b"":
                    return
            except TimeoutError:
                pass

    async with legacy_server(
        handler, command_length=3 if operation == "read" else 4
    ) as (port, received, disconnected):
        client = LegacyBinaryClient("127.0.0.1", port=port, request_timeout=1)
        with pytest.raises(KefConnectionError) as raised:
            action = (
                client.async_get_volume_raw()
                if operation == "read" else client.async_set_volume_raw(42)
            )
            await asyncio.wait_for(action, 3)
        assert raised.value.command == f"{operation}_volume"
        assert raised.value.phase == (
            "reading_response" if operation == "read"
            else "waiting_for_acknowledgement"
        )
        assert raised.value.connection_attempts == 1
        await asyncio.wait_for(disconnected.wait(), 1)
        assert len(received) == 1
        assert len(chunks_sent) >= 2


@pytest.mark.parametrize("operation", ["read", "write"])
async def test_cancelling_reply_wait_closes_connection(operation):
    waiting = asyncio.Event()

    async def handler(reader, writer):
        writer.write(b"R")
        await writer.drain()
        waiting.set()
        assert await reader.read() == b""

    async with legacy_server(
        handler, command_length=3 if operation == "read" else 4
    ) as (port, received, disconnected):
        client = LegacyBinaryClient("127.0.0.1", port=port)
        action = (
            client.async_get_volume_raw()
            if operation == "read" else client.async_set_volume_raw(42)
        )
        task = asyncio.create_task(action)
        try:
            await asyncio.wait_for(waiting.wait(), 1)
            await asyncio.sleep(0.01)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            await asyncio.wait_for(disconnected.wait(), 1)
            assert len(received) == 1
        finally:
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)


@pytest.mark.parametrize("operation", ["read", "write"])
async def test_missing_reply_is_bounded_by_response_size(operation):
    async def handler(reader, writer):
        writer.write(b"x" * 100)
        await writer.drain()
        assert await reader.read() == b""

    async with legacy_server(
        handler, command_length=3 if operation == "read" else 4
    ) as (port, received, disconnected):
        client = LegacyBinaryClient("127.0.0.1", port=port)
        with pytest.raises(KefResponseError):
            action = (
                client.async_get_volume_raw()
                if operation == "read" else client.async_set_volume_raw(42)
            )
            await asyncio.wait_for(action, 0.5)
        await asyncio.wait_for(disconnected.wait(), 1)
        assert len(received) == 1


@pytest.mark.parametrize(
    ("wire_volume", "split", "trailer"),
    [(42, 1, 255), (42, 2, 255), (42, 3, 255), (42, 4, 255),
     (82, 5, 255), (170, 5, 255), (42, 5, 128)],
)
async def test_get_volume_waits_for_a_complete_packet(wire_volume, split, trailer):
    async def handler(reader, writer):
        reply = bytes([82, 37, 129, wire_volume, trailer])
        writer.write(reply[:split])
        await writer.drain()
        if split < len(reply):
            try:
                assert await asyncio.wait_for(reader.read(), 0.03) == b""
                return
            except TimeoutError:
                writer.write(reply[split:])
                await writer.drain()
        assert await reader.read() == b""

    async with legacy_server(handler, command_length=3) as (
        port, received, disconnected
    ):
        client = LegacyBinaryClient("127.0.0.1", port=port)
        assert await client.async_get_volume_raw() == wire_volume % 128
        await asyncio.wait_for(disconnected.wait(), 1)
        assert received == [bytes([71, 37, 128])]


@pytest.mark.parametrize(
    ("source", "volume", "status", "source_name", "muted"),
    [(34, 60, "powerOn", "Wifi", False), (218, 60, "standby", "Aux", False),
     (218, 170, "standby", "Aux", True),
     (47, 36, "powerOn", "Bluetooth", False)],
)
async def test_refresh_reads_original_speaker_reply_layout(
    source, volume, status, source_name, muted,
):
    """Read source, mute, and playback from five-byte legacy replies."""
    # aiokef issue #15 records R0 81 da 9a and R% 81 3c 44 on an LSX.
    replies = {
        ord("0"): bytes([82, 48, 129, source, 154]),
        ord("%"): bytes([82, 37, 129, volume, 68]),
        ord("1"): bytes([82, 49, 129, 129, 255]),
    }

    async def handler(reader, writer):
        query = received[-1][1]
        writer.write(replies[query])
        await writer.drain()
        assert await reader.read() == b""

    async with legacy_server(handler, command_length=3) as (
        port, received, disconnected
    ):
        snapshot = await LegacyBinaryClient("127.0.0.1", port=port).async_refresh()
        assert snapshot.speaker_status == status
        assert snapshot.source == source_name
        assert snapshot.volume_raw == volume % 128
        assert snapshot.is_muted is muted
        transport_supported = source_name in {"Wifi", "Bluetooth"}
        assert snapshot.playback.state == ("playing" if transport_supported else None)
        expected = [b"G0\x80", b"G0\x80", b"G%\x80"]
        if transport_supported:
            expected.append(b"G1\x80")
        assert received == expected


@pytest.mark.parametrize(("source", "name"), [(43, "Opt"), (42, "Aux"), (44, "Usb")])
async def test_physical_inputs_refresh_without_playback_query(source, name):
    """Captured Optical replies must publish source/volume without querying playback."""
    async def handler(reader, writer):
        query = received[-1][1]
        replies = {
            ord("0"): bytes([82, 48, 129, source, 67]),
            ord("%"): b"R%\x81\x24\x0c",
            ord("1"): b"R\x12\xff",
        }
        writer.write(replies[query])
        await writer.drain()
        assert await reader.read() == b""

    async with legacy_server(handler, command_length=3) as (port, received, _):
        snapshot = await LegacyBinaryClient("127.0.0.1", port=port).async_refresh()
        assert snapshot.source == name
        assert snapshot.volume_raw == 36
        assert snapshot.speaker_status == "powerOn"
        assert snapshot.playback.state is None
        assert received == [b"G0\x80", b"G0\x80", b"G%\x80"]


@pytest.mark.parametrize("reject", [True, False])
async def test_optional_playback_rejection_preserves_mandatory_state(reject):
    """Playback rejection preserves state; a dropped connection still fails."""
    async def handler(reader, writer):
        query = received[-1][1]
        replies = {ord("0"): b"R0\x81\x22\x7c", ord("%"): b"R%\x81\x24\x0c"}
        if query == ord("1"):
            if not reject:
                return
            reply = b"R\x12\xff"
        else:
            reply = replies[query]
        writer.write(reply)
        await writer.drain()
        assert await reader.read() == b""

    async with legacy_server(handler, command_length=3) as (port, received, _):
        client = LegacyBinaryClient("127.0.0.1", port=port)
        if reject:
            snapshot = await client.async_refresh()
            assert snapshot.source == "Wifi"
            assert snapshot.volume_raw == 36
            assert snapshot.playback.state is None
        else:
            with pytest.raises(KefResponseError) as raised:
                await client.async_refresh()
            assert raised.value.command == "read_playback"
        assert received[-1] == b"G1\x80"


@pytest.mark.parametrize("operation", ["read", "write"])
@pytest.mark.parametrize("split", [1, 2, 3])
async def test_terminal_rejection_closes_connection_without_waiting_or_replay(
    operation, split,
):
    """A complete short rejection is terminal even if the speaker keeps TCP open."""
    async def handler(reader, writer):
        reply = b"R\x12\xff"
        writer.write(reply[:split])
        await writer.drain()
        await asyncio.sleep(0.03)
        writer.write(reply[split:])
        await writer.drain()
        assert await reader.read() == b""

    async with legacy_server(
        handler, command_length=3 if operation == "read" else 4,
    ) as (port, received, disconnected):
        client = LegacyBinaryClient("127.0.0.1", port=port, request_timeout=5)
        with pytest.raises(KefCommandRejectedError) as raised:
            action = (client.async_get_volume_raw() if operation == "read"
                      else client.async_set_volume_raw(42))
            await asyncio.wait_for(action, 1)
        assert raised.value.command == f"{operation}_volume"
        assert raised.value.connection_attempts == 1
        await asyncio.wait_for(disconnected.wait(), 1)
        assert len(received) == 1


@pytest.mark.parametrize("reply", [b"R\x12\xff", b"R0\x81R\x12R\x12\xff"])
def test_rejection_is_recognized_at_packet_boundaries(reply):
    with pytest.raises(KefCommandRejectedError):
        LegacyBinaryClient._parse_response(b"G%\x80", reply)


@pytest.mark.parametrize("reply", [b"R\x12", b"R\x12\x00"])
def test_incomplete_or_invalid_rejection_is_not_a_terminal_rejection(reply):
    with pytest.raises(KefResponseError) as raised:
        LegacyBinaryClient._parse_response(b"G%\x80", reply)
    assert not isinstance(raised.value, KefCommandRejectedError)


@pytest.mark.parametrize(
    "reply", [b"", b"R", b"R%", b"R%\x81", b"R%\x81*", b"R0\x81*\xff",
              b"R%\x80*\xff", b"R0\x81R%R\xff*\xff"]
)
async def test_get_volume_rejects_incomplete_or_unrelated_packets(reply):
    async def handler(reader, writer):
        writer.write(reply)
        await writer.drain()

    async with legacy_server(handler, command_length=3) as (
        port, received, disconnected
    ):
        client = LegacyBinaryClient("127.0.0.1", port=port)
        with pytest.raises(KefResponseError):
            await client.async_get_volume_raw()
        await asyncio.wait_for(disconnected.wait(), 1)
        assert received == [bytes([71, 37, 128])]


@pytest.mark.parametrize(
    ("reply", "volume"),
    [(bytes([82, 48, 129, 82, 255, 82, 37, 129, 82, 255]), 82),
     (bytes([82, 48, 129, 82, 37, 82, 37, 129, 42, 255]), 42),
     (bytes([82, 17, 255, 82, 48, 129, 82, 255,
             82, 37, 129, 42, 255]), 42)],
)
async def test_get_volume_selects_matching_packet_from_combined_reply(reply, volume):
    async def handler(reader, writer):
        # The other query's value and the requested volume can both equal 'R'.
        writer.write(reply)
        await writer.drain()
        assert await reader.read() == b""

    async with legacy_server(handler, command_length=3) as (
        port, received, disconnected
    ):
        client = LegacyBinaryClient("127.0.0.1", port=port)
        assert await client.async_get_volume_raw() == volume
        await asyncio.wait_for(disconnected.wait(), 1)
        assert received == [bytes([71, 37, 128])]
