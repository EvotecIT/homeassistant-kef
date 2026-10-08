"""Real TCP contracts for legacy command acknowledgements and cleanup."""

import asyncio
from contextlib import asynccontextmanager

import pytest

from custom_components.kef.kef_client.client import LegacyBinaryClient
from custom_components.kef.kef_client.exceptions import (
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
            received.append(await reader.readexactly(command_length))
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
        with pytest.raises(KefResponseError):
            await client.async_set_volume_raw(42)
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
        with pytest.raises(KefConnectionError):
            action = (
                client.async_get_volume_raw()
                if operation == "read" else client.async_set_volume_raw(42)
            )
            await asyncio.wait_for(action, 3)
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
    ("wire_volume", "split"), [(42, 1), (42, 2), (42, 3), (82, 4), (170, 4)]
)
async def test_get_volume_waits_for_a_complete_packet(wire_volume, split):
    async def handler(reader, writer):
        reply = bytes([82, 37, wire_volume, 255])
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


@pytest.mark.parametrize("reply", [b"", b"R", b"R%", b"R%*", b"R0*\xff"])
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


async def test_get_volume_selects_matching_packet_from_combined_reply():
    async def handler(reader, writer):
        # The other query's value and the requested volume can both equal 'R'.
        writer.write(bytes([82, 48, 82, 255, 82, 37, 82, 255]))
        await writer.drain()
        assert await reader.read() == b""

    async with legacy_server(handler, command_length=3) as (
        port, received, disconnected
    ):
        client = LegacyBinaryClient("127.0.0.1", port=port)
        assert await client.async_get_volume_raw() == 82
        await asyncio.wait_for(disconnected.wait(), 1)
        assert received == [bytes([71, 37, 128])]
