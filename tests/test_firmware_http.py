"""Synthetic firmware uploads exercise the complete local HTTP protocol."""

import pytest
from aiohttp import ClientSession, web

from kef_client import KefResponseError, ModernKefClient
from tests.http_server import local_server

pytestmark = pytest.mark.usefixtures("socket_enabled")


@pytest.mark.parametrize("uploaded_state", ["downloaded", "failed", None])
async def test_firmware_upload_requires_downloaded_state_before_install(
    uploaded_state,
    tmp_path,
):
    """Only a confirmed downloaded image permits the subsequent install action."""
    fixture_bytes = b"loopback protocol fixture; never device firmware"
    firmware = tmp_path / "synthetic.swu"
    firmware.write_bytes(fixture_bytes)
    requests = []
    installed = False

    async def handler(request):
        nonlocal installed
        if request.path == "/settings.fcgi":
            assert request.method == "POST"
            assert request.query == {"firmwareupdate": "1"}
            multipart = await request.multipart()
            image = await multipart.next()
            assert image.name == "datafile"
            assert image.filename == "synthetic.swu"
            assert image.headers["Content-Type"] == "application/octet-stream"
            assert await image.read() == fixture_bytes
            assert await multipart.next() is None
            requests.append("upload")
            return web.Response(text="<html>Upload received</html>")
        if request.method == "POST":
            payload = await request.json()
            assert payload == {
                "path": "firmwareupdate:installUpdate",
                "role": "activate",
                "value": {"firmwareUpdateOptions": {"forceSfupdate": True}},
            }
            assert uploaded_state == "downloaded"
            assert not installed
            installed = True
            requests.append("install")
            return web.json_response({})
        if request.query["path"] == "settings:/webserver/authMode":
            return web.json_response([{"type": "string_", "string_": "none"}])
        assert request.query["path"] == "firmwareupdate:updateStatus"
        requests.append("status")
        status = (
            {"state": "installed", "imageDescription": {"version": "synthetic-1"}}
            if installed
            else {"state": uploaded_state}
            if uploaded_state
            else {}
        )
        return web.json_response([{"firmwareUpdateStatus": status}])

    async with local_server(handler) as port, ClientSession() as session:
        client = ModernKefClient("127.0.0.1", session, port=port)
        if uploaded_state == "downloaded":
            result = await client.async_upload_firmware_update(str(firmware))
            assert result.state == "installed"
            assert result.available_version == "synthetic-1"
            assert requests == ["upload", "status", "install", "status"]
        else:
            with pytest.raises(KefResponseError, match="downloaded state"):
                await client.async_upload_firmware_update(str(firmware))
            assert requests == ["upload", "status"]
            assert not installed
        assert firmware.read_bytes() == fixture_bytes
        assert not session.closed
