"""Protected local HTTP reads and writes obey the KEF wire contract."""

import base64
import hashlib
import hmac
import json
import socket

import pytest
from aiohttp import ClientSession, TCPConnector, web
from cryptography.hazmat.primitives import padding
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes

from kef_client.client import ModernKefClient
from kef_client.exceptions import KefAuthenticationRequiredError
from tests.http_server import local_server

pytestmark = pytest.mark.usefixtures("socket_enabled")


def verify_authenticated_request(request, body, password):
    """The synthetic speaker verifies the received request, without client helpers."""
    scheme, credentials = request.headers["Authorization"].split(" ", 1)
    assert scheme == "HMAC_SHA256_AES256"
    user, salt, timestamp, signature = credentials.split(".")
    assert base64.b64decode(user, validate=True) == b"user"
    salt_bytes = base64.b64decode(salt, validate=True)
    assert len(salt_bytes) == 6
    assert timestamp.isdecimal()
    key = hashlib.sha256(salt_bytes + password.encode()).digest()
    message = f"user.{salt}.{timestamp}.{request.url}"
    if request.method == "POST":
        message += f".{body}"
    assert hmac.compare_digest(
        base64.b64decode(signature, validate=True),
        hmac.digest(key, message.encode(), "sha256"),
    )
    return key


def decrypt_written_value(value, key):
    """Independently decode the speaker's received AES value."""
    encrypted = base64.b64decode(value, validate=True)
    assert len(encrypted) >= 32
    decryptor = Cipher(algorithms.AES(key), modes.CBC(encrypted[:16])).decryptor()
    padded = decryptor.update(encrypted[16:]) + decryptor.finalize()
    unpadder = padding.PKCS7(128).unpadder()
    plaintext = unpadder.update(padded) + unpadder.finalize()
    return json.loads(plaintext)


@pytest.mark.parametrize(
    ("auth_mode", "protected_probe", "host"),
    [
        pytest.param("setData", False, "127.0.0.1", id="open-probe-setData"),
        pytest.param("all", False, "127.0.0.1", id="open-probe-all"),
        pytest.param("setData", True, "127.0.0.1", id="protected-probe-setData"),
        pytest.param("all", True, "127.0.0.1", id="protected-probe-all"),
        pytest.param("setData", False, "LOCALHOST", id="canonical-hostname"),
    ],
)
async def test_secure_http_roundtrip_preserves_authentication_and_value(
    auth_mode,
    protected_probe,
    host,
):
    """Public commands arrive with valid signatures and decrypt to typed values."""
    password = "synthetic-local-password"
    reads = []
    writes = []
    probe_requests = []

    async def handler(request):
        if request.method == "GET":
            if request.query["path"] == "settings:/webserver/authMode":
                authenticated = "Authorization" in request.headers
                probe_requests.append(authenticated)
                if protected_probe and not authenticated:
                    return web.Response(status=401)
                if authenticated:
                    verify_authenticated_request(request, "", password)
                return web.json_response(
                    [{"type": "webserverAuthMode", "webserverAuthMode": auth_mode}]
                )
            assert request.path == "/api/getData"
            assert request.query["path"] == "player:volume"
            assert request.query["roles"] == "value"
            if auth_mode == "all":
                verify_authenticated_request(request, "", password)
            else:
                assert "Authorization" not in request.headers
            reads.append(request.query["path"])
            return web.json_response([{"type": "i32_", "i32_": 42}])

        assert request.method == "POST"
        assert request.path == "/api/setData"
        assert request.content_type == "application/json"
        body = await request.text()
        key = verify_authenticated_request(request, body, password)
        payload = json.loads(body)
        assert payload["path"] == "player:volume"
        assert payload["role"] == "value"
        writes.append(decrypt_written_value(payload["value"], key))
        return web.json_response({})

    async with (
        local_server(handler) as port,
        ClientSession(connector=TCPConnector(family=socket.AF_INET)) as session,
    ):
        client = ModernKefClient(host, session, port=port, password=password)
        assert await client.async_get_volume_raw() == 42
        await client.async_set_volume_raw(37)
        await client.async_set_volume_raw(38)
        assert reads == ["player:volume"]
        assert writes == [
            {"type": "i32_", "i32_": 37},
            {"type": "i32_", "i32_": 38},
        ]
        assert probe_requests == ([False, True] if protected_probe else [False])
        assert not session.closed


@pytest.mark.parametrize(
    "password",
    ["", "synthetic-password"],
    ids=["missing-password", "rejected-password"],
)
@pytest.mark.parametrize("status", [401, 403])
async def test_secure_http_denial_is_not_replayed(status, password):
    """An authenticated rejection remains an auth error and never repeats a write."""
    writes = []

    async def handler(request):
        if request.method == "GET":
            assert request.query["path"] == "settings:/webserver/authMode"
            return web.json_response(
                [{"type": "webserverAuthMode", "webserverAuthMode": "setData"}]
            )
        body = await request.text()
        verify_authenticated_request(request, body, password)
        writes.append(body)
        return web.Response(status=status)

    async with local_server(handler) as port, ClientSession() as session:
        client = ModernKefClient("127.0.0.1", session, port=port, password=password)
        with pytest.raises(KefAuthenticationRequiredError) as error:
            await client.async_set_volume_raw(37)
        assert len(writes) == 1
        if password:
            assert password not in str(error.value)
        assert not session.closed


@pytest.mark.parametrize("changed_mode", ["setData", "all"])
async def test_changed_authentication_mode_retries_only_the_rejected_plain_write(
    changed_mode,
):
    """A cached open API can switch to protection without duplicating a command."""
    password = "synthetic-local-password"
    mode = "none"
    probes = []
    attempts = []
    writes = []

    async def handler(request):
        if request.method == "GET":
            if request.query["path"] == "settings:/webserver/authMode":
                probes.append(mode)
                return web.json_response(
                    [{"type": "webserverAuthMode", "webserverAuthMode": mode}]
                )
            assert request.query["path"] == "player:volume"
            if mode == "all":
                verify_authenticated_request(request, "", password)
            else:
                assert "Authorization" not in request.headers
            return web.json_response([{"type": "i32_", "i32_": 42}])
        body = await request.text()
        authenticated = "Authorization" in request.headers
        attempts.append(authenticated)
        if not authenticated:
            # Authentication is established by status, even with bad UI text.
            return web.Response(status=401, body=b"\xff")
        key = verify_authenticated_request(request, body, password)
        payload = json.loads(body)
        assert payload["path"] == "player:volume"
        assert payload["role"] == "value"
        writes.append(decrypt_written_value(payload["value"], key))
        return web.json_response({})

    async with local_server(handler) as port, ClientSession() as session:
        client = ModernKefClient("127.0.0.1", session, port=port, password=password)
        assert await client.async_get_volume_raw() == 42
        mode = changed_mode
        await client.async_set_volume_raw(37)
        assert await client.async_get_volume_raw() == 42
        assert probes == ["none", changed_mode]
        assert attempts == [False, True]
        assert writes == [{"type": "i32_", "i32_": 37}]
        assert not session.closed
