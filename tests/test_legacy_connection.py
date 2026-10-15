"""Legacy speakers can refuse new connections briefly between commands."""

import asyncio
from unittest.mock import AsyncMock, Mock, patch

import aiohttp
import pytest

from custom_components.kef.kef_client.client import (
    LegacyBinaryClient,
    ModernKefClient,
    async_create_client,
)
from custom_components.kef.kef_client.exceptions import KefConnectionError
from tests.test_legacy_transport import legacy_server

pytestmark = pytest.mark.usefixtures("socket_enabled")


@pytest.mark.parametrize(
    ("failure", "operation"),
    [(aiohttp.ConnectionTimeoutError, "connect"),
     (aiohttp.SocketTimeoutError, "request")],
    ids=["connect-timeout", "read-timeout"],
)
async def test_modern_timeout_diagnostics_distinguish_connect_and_read(
    failure, operation,
):
    """The download context must not imply a connection for a connect timeout."""
    session = Mock()
    session.request.side_effect = failure("private host or URL")
    with pytest.raises(KefConnectionError) as raised:
        await ModernKefClient("192.0.2.42", session).async_identify()
    assert raised.value.operation == operation
    assert raised.value.backend == "modern"
    assert raised.value.port == 80


async def test_setup_recovers_when_reidentification_connection_is_refused(hass):
    """A successful factory probe must survive the speaker releasing its socket."""
    from homeassistant.helpers.aiohttp_client import async_get_clientsession

    async def handler(reader, writer):
        writer.write(b"R0\x81\x22\xff")
        await writer.drain()
        assert await reader.read() == b""

    open_connection = asyncio.open_connection
    attempts = 0

    async def connect(*args, **kwargs):
        nonlocal attempts
        attempts += 1
        if attempts in (2, 3):
            raise ConnectionRefusedError(111, "speaker releasing its connection")
        return await open_connection(*args, **kwargs)

    async with legacy_server(handler, command_length=3) as (port, received, _):
        with patch("asyncio.open_connection", side_effect=connect):
            client = await async_create_client(
                "127.0.0.1", async_get_clientsession(hass),
                backend="legacy", tcp_port=port,
            )
            device = await client.async_identify()
        assert device.backend.value == "legacy"
        assert device.port == port
        assert received == [b"G0\x80", b"G0\x80"]
        assert attempts == 4


async def test_permanent_refusal_is_bounded_and_keeps_socket_error():
    """An unavailable control service cannot keep setup waiting indefinitely."""
    connect = AsyncMock(side_effect=ConnectionRefusedError(111, "private host"))
    client = LegacyBinaryClient("192.0.2.42", request_timeout=0.05)
    with patch("asyncio.open_connection", connect):
        with pytest.raises(KefConnectionError) as raised:
            await asyncio.wait_for(client.async_identify(), 1)
    assert connect.await_count == 1
    assert isinstance(raised.value.__cause__, ConnectionRefusedError)
    assert raised.value.backend == "legacy"
    assert raised.value.port == 50001
    assert raised.value.operation == "connect"


async def test_connection_timeout_is_reported_as_a_connection_error():
    """A socket that never connects must not escape as an unhandled timeout."""
    async def connect(*args, **kwargs):
        await asyncio.Event().wait()

    with patch("asyncio.open_connection", side_effect=connect):
        client = LegacyBinaryClient("192.0.2.42", request_timeout=0.01)
        with pytest.raises(KefConnectionError) as raised:
            await asyncio.wait_for(client.async_identify(), 1)
    assert isinstance(raised.value.__cause__, TimeoutError)
    assert raised.value.operation == "connect"


async def test_other_connection_errors_are_not_retried():
    connect = AsyncMock(side_effect=OSError(101, "network unreachable"))
    with patch("asyncio.open_connection", connect):
        with pytest.raises(KefConnectionError) as raised:
            await LegacyBinaryClient("192.0.2.42").async_identify()
    assert connect.await_count == 1
    assert raised.value.__cause__.errno == 101


async def test_cancelling_connection_retry_stops_before_sending_commands():
    refused = asyncio.Event()

    async def connect(*args, **kwargs):
        refused.set()
        raise ConnectionRefusedError(111, "private host")

    client = LegacyBinaryClient("192.0.2.42")
    with patch("asyncio.open_connection", side_effect=connect) as mocked:
        task = asyncio.create_task(client.async_set_volume_raw(42))
        try:
            await asyncio.wait_for(refused.wait(), 1)
            task.cancel()
            with pytest.raises(asyncio.CancelledError):
                await task
            assert mocked.call_count == 1
        finally:
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)


async def test_concurrent_legacy_commands_do_not_overlap_connections():
    """Only one command may occupy the original speaker's control service."""
    active = 0
    peak = 0

    async def handler(reader, writer):
        nonlocal active, peak
        active += 1
        peak = max(peak, active)
        await asyncio.sleep(0.03)
        writer.write(b"R\x11\xff")
        await writer.drain()
        active -= 1
        assert await reader.read() == b""

    async with legacy_server(handler) as (port, received, _):
        client = LegacyBinaryClient("127.0.0.1", port=port)
        await asyncio.gather(
            client.async_set_volume_raw(42), client.async_set_volume_raw(43),
        )
        assert peak == 1
        assert len(received) == 2
