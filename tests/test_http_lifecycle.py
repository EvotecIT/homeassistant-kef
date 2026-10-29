"""Real stalled and interrupted reads retain the caller's HTTP session."""

import asyncio

import pytest
from aiohttp import ClientSession, web

from kef_client import KefConnectionError, ModernKefClient
from tests.http_server import local_server

pytestmark = pytest.mark.usefixtures("socket_enabled")


@pytest.mark.parametrize(
    "interruption", ["timeout", "cancel", "disconnect", "partial_body"]
)
async def test_interrupted_http_read_releases_response_and_recovers(interruption):
    """Deadlines, cancellation and disconnects allow a subsequent public read."""
    entered = asyncio.Event()
    release = asyncio.Event()
    interrupting = True
    reads = []

    async def handler(request):
        if request.query["path"] == "settings:/webserver/authMode":
            return web.json_response([{"type": "string_", "string_": "none"}])
        assert request.query["path"] == "player:volume"
        reads.append("volume")
        if interrupting:
            entered.set()
            if interruption == "disconnect":
                request.transport.abort()
                return web.Response()
            if interruption == "partial_body":
                response = web.StreamResponse()
                response.content_type = "application/json"
                await response.prepare(request)
                await response.write(b'[{"type": "i32_", ')
                await release.wait()
                return response
            await release.wait()
        return web.json_response([{"type": "i32_", "i32_": 42}])

    async with local_server(handler) as port, ClientSession() as session:
        client = ModernKefClient(
            "127.0.0.1",
            session,
            port=port,
            request_timeout=0.05,
        )
        task = asyncio.create_task(client.async_get_volume_raw())
        try:
            await asyncio.wait_for(entered.wait(), 5)
            if interruption == "cancel":
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
            else:
                with pytest.raises(KefConnectionError) as error:
                    await asyncio.wait_for(task, 5)
                assert error.value.backend == "modern"
                assert error.value.port == port
                assert error.value.operation == "request"
        finally:
            release.set()
            if not task.done():
                task.cancel()
                with pytest.raises(asyncio.CancelledError):
                    await task
        assert not session.closed
        interrupting = False
        assert await client.async_get_volume_raw() == 42
        assert reads[-1] == "volume"
        assert not session.closed
