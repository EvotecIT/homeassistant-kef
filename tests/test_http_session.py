"""Borrowed HTTP session policy does not alter KEF authentication handling."""

import gzip
import json
from contextlib import asynccontextmanager

import pytest
from aiohttp import ClientSession, web

from custom_components.kef.kef_client.client import ModernKefClient
from custom_components.kef.kef_client.const import PROBE_PATHS
from custom_components.kef.kef_client.exceptions import KefAuthenticationRequiredError

pytestmark = pytest.mark.usefixtures("socket_enabled")


@asynccontextmanager
async def local_server(handler):
    app = web.Application()
    app.router.add_route("*", "/{tail:.*}", handler)
    runner = web.AppRunner(app, access_log=None)
    await runner.setup()
    try:
        await web.TCPSite(runner, "127.0.0.1", 0).start()
        yield runner.addresses[0][1]
    finally:
        await runner.cleanup()


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
