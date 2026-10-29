"""Public commands classify real HTTP responses and retain borrowed sessions."""

import pytest
from aiohttp import ClientSession, web

from kef_client.client import ModernKefClient
from kef_client.const import PROBE_PATHS
from kef_client.exceptions import (
    KefAuthenticationRequiredError,
    KefResponseError,
)
from tests.http_server import local_server

pytestmark = pytest.mark.usefixtures("socket_enabled")


async def perform_operation(client, operation, tmp_path):
    """Exercise supported public operations, including a synthetic local upload."""
    if operation == "read":
        return await client.async_get_volume_raw()
    if operation == "write":
        return await client.async_set_volume_raw(37)
    firmware = tmp_path / "synthetic.swu"
    firmware.write_bytes(b"loopback fixture only; never device firmware")
    return await client.async_upload_firmware_update(str(firmware))


@pytest.mark.parametrize("operation", ["read", "write", "upload"])
@pytest.mark.parametrize(
    ("status", "location", "error_type", "message"),
    [
        pytest.param(200, "", KefResponseError, "invalid text", id="invalid-success"),
        pytest.param(503, "", KefResponseError, "HTTP 503", id="invalid-unavailable"),
        pytest.param(
            401, "", KefAuthenticationRequiredError, "authentication", id="unauthorized"
        ),
        pytest.param(
            403, "", KefAuthenticationRequiredError, "authentication", id="forbidden"
        ),
        pytest.param(
            302,
            "/login.fcgi",
            KefAuthenticationRequiredError,
            "authentication",
            id="login",
        ),
        pytest.param(
            307, "/unrelated", KefResponseError, "redirected", id="other-redirect"
        ),
    ],
)
async def test_invalid_http_text_preserves_public_error_and_recovery(
    operation,
    status,
    location,
    error_type,
    message,
    tmp_path,
):
    """Malformed text never escapes the KEF error owner or replays an action."""
    failed_requests = []
    rejecting = True

    async def handler(request):
        await request.read()
        if request.query.get("path") == PROBE_PATHS["webserver_auth_mode"]:
            return web.json_response([{"type": "string_", "string_": "none"}])
        if rejecting:
            failed_requests.append((request.method, request.path))
            return web.Response(
                status=status,
                body=b"\xff",
                content_type="application/json",
                headers={"Location": location} if location else None,
            )
        assert request.method == "GET"
        assert request.query["path"] == "player:volume"
        return web.json_response([{"type": "i32_", "i32_": 42}])

    async with local_server(handler) as port, ClientSession() as session:
        client = ModernKefClient("127.0.0.1", session, port=port)
        with pytest.raises(error_type, match=message) as error:
            await perform_operation(client, operation, tmp_path)
        assert type(error.value) is error_type
        expected = {
            "read": ("GET", "/api/getData"),
            "write": ("POST", "/api/setData"),
            "upload": ("POST", "/settings.fcgi"),
        }
        assert failed_requests == [expected[operation]]
        assert not session.closed
        rejecting = False
        assert await client.async_get_volume_raw() == 42
        assert not session.closed


@pytest.mark.parametrize(
    ("status", "body", "message"),
    [
        pytest.param(503, b"", "KEF speaker returned HTTP 503", id="empty-http-error"),
        pytest.param(
            200,
            b"broken JSON",
            "KEF speaker returned non-JSON data for /setData",
            id="non-json-success",
        ),
        pytest.param(
            503,
            b"unavailable",
            "KEF speaker returned HTTP 503",
            id="non-json-http-error",
        ),
        pytest.param(
            503,
            b'{"error":{"message":"speaker busy"}}',
            "speaker busy",
            id="structured-http-error",
        ),
        pytest.param(
            200,
            b'{"error":{"message":"speaker busy"}}',
            "speaker busy",
            id="structured-api-error",
        ),
        pytest.param(
            200,
            b'{"error":"failure"}',
            "KEF API returned an error",
            id="unstructured-api-error",
        ),
        pytest.param(
            503,
            b'{"error":"failure"}',
            "KEF API returned an error",
            id="unstructured-http-error",
        ),
        pytest.param(
            503, b"[]", "KEF speaker returned HTTP 503", id="http-error-without-message"
        ),
    ],
)
async def test_http_write_response_preserves_api_failure(status, body, message):
    """HTTP and application-level failures cannot be mistaken for a write ACK."""
    writes = []

    async def handler(request):
        await request.read()
        if request.method == "GET":
            assert request.query["path"] == PROBE_PATHS["webserver_auth_mode"]
            return web.json_response([{"type": "string_", "string_": "none"}])
        writes.append(request.path)
        return web.Response(status=status, body=body, content_type="application/json")

    async with local_server(handler) as port, ClientSession() as session:
        client = ModernKefClient("127.0.0.1", session, port=port)
        with pytest.raises(KefResponseError) as error:
            await client.async_set_volume_raw(37)
        assert str(error.value) == message
        assert writes == ["/api/setData"]
        assert not session.closed


async def test_empty_successful_write_is_acknowledged_once():
    """A speaker may acknowledge a successful local write without JSON content."""
    writes = []

    async def handler(request):
        await request.read()
        if request.method == "GET":
            return web.json_response([{"type": "string_", "string_": "none"}])
        writes.append(request.path)
        return web.Response(status=204)

    async with local_server(handler) as port, ClientSession() as session:
        client = ModernKefClient("127.0.0.1", session, port=port)
        await client.async_set_volume_raw(37)
        assert writes == ["/api/setData"]
        assert not session.closed
