"""The standalone event stream uses one queue and validates received events."""

import pytest
from aiohttp import ClientSession, web

from kef_client import KefResponseError, ModernKefClient
from tests.http_server import local_server

pytestmark = pytest.mark.usefixtures("socket_enabled")


async def test_event_polls_reuse_queue_and_preserve_event_objects():
    """Repeated public polls retain their subscription and ignore non-events."""
    calls = []
    event = {"path": "player:volume", "value": {"type": "i32_", "i32_": 42}}

    async def handler(request):
        if request.path == "/api/event/modifyQueue":
            assert request.method == "POST"
            payload = await request.json()
            assert payload["unsubscribe"] == []
            assert any(item["path"] == "player:volume" for item in payload["subscribe"])
            calls.append("create")
            return web.json_response("synthetic-queue")
        assert request.path == "/api/event/pollQueue"
        assert request.method == "GET"
        assert request.query["queueId"] == "synthetic-queue"
        calls.append(request.query["timeout"])
        return web.json_response([event, None, "not an event"])

    async with local_server(handler) as port, ClientSession() as session:
        client = ModernKefClient("127.0.0.1", session, port=port)
        assert await client.async_poll_events(timeout=0) == [event]
        assert await client.async_poll_events(timeout=3) == [event]
        assert calls == ["create", "1", "3"]
        assert not session.closed


@pytest.mark.parametrize("malformed", ["empty-id", "object-id", "object-events"])
async def test_event_queue_rejects_invalid_server_payload(malformed):
    """An invalid subscription ID or event collection is a canonical error."""
    calls = []

    async def handler(request):
        if request.method == "POST":
            await request.read()
            calls.append("create")
            payload = (
                "synthetic-queue"
                if malformed == "object-events"
                else ("" if malformed == "empty-id" else {})
            )
            return web.json_response(payload)
        calls.append("poll")
        return web.json_response({"unexpected": []})

    async with local_server(handler) as port, ClientSession() as session:
        client = ModernKefClient("127.0.0.1", session, port=port)
        message = "event queue payload" if malformed == "object-events" else "queue id"
        with pytest.raises(KefResponseError, match=message):
            await client.async_poll_events()
        assert calls == (
            ["create", "poll"] if malformed == "object-events" else ["create"]
        )
        assert not session.closed
