"""Backend detection distinguishes HTTP error pages from working legacy APIs."""

import pytest
from aiohttp import ClientSession, web

from custom_components.kef.kef_client.client import async_create_client
from custom_components.kef.kef_client.exceptions import KefAuthenticationRequiredError
from custom_components.kef.kef_client.models import KefBackend
from tests.test_http_session import local_server
from tests.test_legacy_transport import legacy_server

pytestmark = pytest.mark.usefixtures("socket_enabled")


@pytest.mark.parametrize("status", [200, 404, 401])
async def test_http_error_page_does_not_hide_working_legacy_speaker(status):
    async def http(request):
        return web.Response(status=status, text="<html>Not found</html>")

    async def tcp(reader, writer):
        writer.write(b"R0\x01\x80")
        await writer.drain()
        assert await reader.read() == b""

    async with (
        local_server(http) as http_port,
        legacy_server(tcp, command_length=3) as (tcp_port, received, disconnected),
        ClientSession() as session,
    ):
        client = await async_create_client(
            "127.0.0.1", session, port=http_port, tcp_port=tcp_port
        )
        assert client.backend is KefBackend.LEGACY
        assert received == [b"G0\x80"]
        await disconnected.wait()


@pytest.mark.parametrize("status", [401, 403])
async def test_failed_legacy_probe_preserves_modern_password_error(status):
    async def http(request):
        return web.Response(status=status)

    async def tcp(reader, writer):
        writer.write(b"not a legacy reply")
        await writer.drain()
        writer.close()

    async with (
        local_server(http) as http_port,
        legacy_server(tcp, command_length=3) as (tcp_port, received, disconnected),
        ClientSession() as session,
    ):
        with pytest.raises(KefAuthenticationRequiredError):
            await async_create_client(
                "127.0.0.1", session, port=http_port, tcp_port=tcp_port,
                password="wrong-password",
            )
        assert received == [b"G0\x80"]
        await disconnected.wait()
