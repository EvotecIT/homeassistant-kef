"""Borrowed HTTP session policy does not alter KEF authentication handling."""

import gzip
import json

import pytest
from aiohttp import ClientSession, web

from kef_client.client import ModernKefClient
from kef_client.const import PROBE_PATHS
from kef_client.exceptions import KefAuthenticationRequiredError, KefError
from tests.http_server import local_server

pytestmark = pytest.mark.usefixtures("socket_enabled")


@pytest.mark.parametrize(
    ("source", "remembered", "selected", "status"),
    [
        ("usb", "wifi", None, 200),
        ("standby", "usb", "usb", 200),
        ("standby", None, "wifi", 200),
        ("standby", "usb", "usb", 503),
    ],
)
async def test_turn_on_keeps_active_input_or_wakes_once(
    source, remembered, selected, status,
):
    """Power actions preserve active input and select once only from standby."""
    requests = []

    async def handler(request):
        if request.method == "GET":
            path = request.query["path"]
            if path == PROBE_PATHS["webserver_auth_mode"]:
                return web.json_response([{"type": "string_", "string_": "none"}])
            assert path == PROBE_PATHS["source"]
            return web.json_response([
                {"type": "kefPhysicalSource", "kefPhysicalSource": source},
            ])
        requests.append((request.path, await request.json()))
        return web.json_response({}, status=status)

    async with local_server(handler) as port, ClientSession() as session:
        client = ModernKefClient("127.0.0.1", session, port=port)
        client._last_active_source = remembered
        if status == 200:
            await client.async_turn_on()
        else:
            with pytest.raises(KefError):
                await client.async_turn_on()
        expected = [] if selected is None else [
            ("/api/setData", {
                "path": "settings:/kef/play/physicalSource",
                "role": "value",
                "value": {"type": "kefPhysicalSource", "kefPhysicalSource": selected},
            })
        ]
        assert requests == expected
        assert not session.closed


async def test_failed_source_selection_does_not_change_wake_input():
    """A rejected input change cannot redirect a later standby wake."""
    selected = []

    async def handler(request):
        if request.method == "GET":
            item = (
                {"type": "string_", "string_": "none"}
                if request.query["path"] == PROBE_PATHS["webserver_auth_mode"]
                else {"type": "kefPhysicalSource", "kefPhysicalSource": "standby"}
            )
            return web.json_response([item])
        value = (await request.json())["value"]["kefPhysicalSource"]
        selected.append(value)
        return web.json_response({}, status=503 if value == "tv" else 200)

    async with local_server(handler) as port, ClientSession() as session:
        client = ModernKefClient("127.0.0.1", session, port=port)
        await client.async_select_source("usb")
        with pytest.raises(KefError):
            await client.async_select_source("tv")
        await client.async_turn_on()
    assert selected == ["usb", "tv", "usb"]


@pytest.mark.parametrize("status", [401, 403])
@pytest.mark.parametrize("operation", ["read", "upload"])
async def test_borrowed_status_policy_preserves_auth_errors(
    status, operation, tmp_path
):
    async def handler(request):
        await request.read()
        return web.Response(status=status)

    async with (
        local_server(handler) as port,
        ClientSession(raise_for_status=True) as session,
    ):
        client = ModernKefClient("127.0.0.1", session, port=port)
        with pytest.raises(KefAuthenticationRequiredError):
            if operation == "read":
                await client.async_get_volume_raw()
            else:
                firmware = tmp_path / "local-test.bin"
                firmware.write_bytes(b"local server fixture, never device firmware")
                await client.async_upload_firmware_update(str(firmware))
        assert not session.closed


async def test_borrowed_decompression_policy_preserves_typed_json():
    async def handler(request):
        item = (
            {"type": "string_", "string_": "none"}
            if request.query.get("path") == PROBE_PATHS["webserver_auth_mode"]
            else {"type": "i32_", "i32_": 42}
        )
        return web.Response(
            body=gzip.compress(json.dumps([item]).encode()),
            headers={"Content-Encoding": "gzip"},
        )

    async with (
        local_server(handler) as port,
        ClientSession(auto_decompress=False) as session,
    ):
        client = ModernKefClient("127.0.0.1", session, port=port)
        assert await client.async_get_volume_raw() == 42
        assert not session.closed
