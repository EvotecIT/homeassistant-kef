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
async def legacy_server(handler):
    tasks = []
    received = []
    disconnected = asyncio.Event()

    async def connection(reader, writer):
        try:
            received.append(await reader.readexactly(4))
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


async def test_partial_data_does_not_restart_acknowledgement_deadline():
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

    async with legacy_server(handler) as (port, received, disconnected):
        client = LegacyBinaryClient("127.0.0.1", port=port, request_timeout=1)
        with pytest.raises(KefConnectionError):
            await asyncio.wait_for(client.async_set_volume_raw(42), 3)
        await asyncio.wait_for(disconnected.wait(), 1)
        assert len(received) == 1
        assert len(chunks_sent) >= 2


async def test_cancelling_acknowledgement_wait_closes_connection():
    waiting = asyncio.Event()

    async def handler(reader, writer):
        writer.write(b"R")
        await writer.drain()
        waiting.set()
        assert await reader.read() == b""

    async with legacy_server(handler) as (port, received, disconnected):
        client = LegacyBinaryClient("127.0.0.1", port=port)
        task = asyncio.create_task(client.async_set_volume_raw(42))
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


async def test_missing_acknowledgement_is_bounded_by_response_size():
    async def handler(reader, writer):
        writer.write(b"x" * 100)
        await writer.drain()
        assert await reader.read() == b""

    async with legacy_server(handler) as (port, received, disconnected):
        client = LegacyBinaryClient("127.0.0.1", port=port)
        with pytest.raises(KefResponseError):
            await asyncio.wait_for(client.async_set_volume_raw(42), 0.5)
        await asyncio.wait_for(disconnected.wait(), 1)
        assert len(received) == 1
