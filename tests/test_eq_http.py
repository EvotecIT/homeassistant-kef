"""EQ writes preserve the speaker's opaque profile data and reject bad input."""

from copy import deepcopy

import pytest
from aiohttp import ClientSession, web

from kef_client import KefResponseError, ModernKefClient
from tests.http_server import local_server

pytestmark = pytest.mark.usefixtures("socket_enabled")


def profile_fixture(version):
    """Use independent wire units and opaque fields outside the requested edit."""
    if version == 1:
        return {
            "type": "kefEqProfile",
            "kefEqProfile": {
                "dspInfo": {
                    "wallMounted": False,
                    "trebleAmount": 8,
                    "vendorField": {"preserved": [1, 2]},
                },
                "vendorProfileId": "preserved",
            },
            "vendorTopLevel": {"preserved": 42},
        }
    return {
        "type": "kefEqProfileV2",
        "kefEqProfileV2": {
            "wallMounted": False,
            "vendorField": {"preserved": [1, 2]},
        },
        "vendorTopLevel": {"preserved": 42},
    }


@pytest.mark.parametrize("version", [1, 2])
async def test_eq_write_preserves_opaque_fields_and_unchanged_wire_units(version):
    """Changing placement retains every unrelated field in either profile API."""
    original = profile_fixture(version)
    expected = deepcopy(original)
    if version == 1:
        expected["kefEqProfile"]["dspInfo"]["wallMounted"] = True
    else:
        expected["kefEqProfileV2"]["wallMounted"] = True
    reads = []
    writes = []

    async def handler(request):
        if request.method == "POST":
            writes.append(await request.json())
            return web.json_response({})
        path = request.query["path"]
        if path == "settings:/webserver/authMode":
            return web.json_response([{"type": "string_", "string_": "none"}])
        reads.append(path)
        if path == "kef:eqProfile" and version == 2:
            return web.Response(status=404)
        return web.json_response([original])

    async with local_server(handler) as port, ClientSession() as session:
        client = ModernKefClient("127.0.0.1", session, port=port)
        result = await client.async_set_wall_mounted(True)
        assert result["wallMounted"] is True
        assert result["vendorField"] == {"preserved": [1, 2]}
        if version == 1:
            assert result["trebleAmount"] == 0
        expected_path = "kef:eqProfile" if version == 1 else "kef:eqProfile/v2"
        assert writes == [{"path": expected_path, "role": "value", "value": expected}]
        assert reads == (
            ["kef:eqProfile"]
            if version == 1
            else [
                "kef:eqProfile",
                "kef:eqProfile/v2",
            ]
        )
        assert original == profile_fixture(version)
        assert not session.closed


@pytest.mark.parametrize(
    ("malformed", "version", "message"),
    [
        pytest.param({}, 1, "EQ profile payload", id="v1-discriminator"),
        pytest.param(
            {"type": "kefEqProfile", "kefEqProfile": []},
            1,
            "EQ profile wrapper",
            id="v1-wrapper",
        ),
        pytest.param(
            {"type": "kefEqProfile", "kefEqProfile": {"dspInfo": []}},
            1,
            "EQ dspInfo payload",
            id="v1-dsp",
        ),
        pytest.param({}, 2, "EQ profile v2 payload", id="v2-discriminator"),
        pytest.param(
            {"type": "kefEqProfileV2", "kefEqProfileV2": []},
            2,
            "EQ profile v2 wrapper",
            id="v2-wrapper",
        ),
        pytest.param(
            {
                "type": "kefEqProfile",
                "kefEqProfile": {"dspInfo": {"trebleAmount": "not a number"}},
            },
            1,
            "EQ",
            id="v1-invalid-known-value",
        ),
    ],
)
async def test_malformed_eq_response_never_writes_a_profile(
    malformed,
    version,
    message,
):
    """Corrupted profile structure or values must fail before any write."""
    writes = []

    async def handler(request):
        if request.method == "POST":
            writes.append(await request.json())
            return web.json_response({})
        if request.query["path"] == "settings:/webserver/authMode":
            return web.json_response([{"type": "string_", "string_": "none"}])
        if request.query["path"] == "kef:eqProfile" and version == 2:
            return web.Response(status=404)
        return web.json_response([malformed])

    async with local_server(handler) as port, ClientSession() as session:
        client = ModernKefClient("127.0.0.1", session, port=port)
        with pytest.raises(KefResponseError, match=message):
            await client.async_set_wall_mounted(True)
        assert writes == []
        assert not session.closed
