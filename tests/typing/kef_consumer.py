"""Static-only installed API contract; this module is never executed."""

from typing import assert_type

from aiohttp import ClientSession

from kef_client import (
    BaseKefClient,
    KefDeviceInfo,
    ModernKefClient,
    async_create_client,
)
from kef_client.client import ModernKefClient as ModuleClient
from kef_client.const import DEFAULT_PORT
from kef_client.exceptions import KefConnectionError
from kef_client.models import KefSnapshot


async def read(session: ClientSession) -> int | None:
    assert_type(DEFAULT_PORT, int)
    client = ModernKefClient('127.0.0.1', session)
    assert_type(await client.async_identify(), KefDeviceInfo)
    assert_type(await client.async_refresh(), KefSnapshot)
    assert_type(await async_create_client('127.0.0.1', session), BaseKefClient)
    await client.async_set_volume_raw("loud")  # type: ignore[arg-type]
    other: ModuleClient = client
    try:
        return await other.async_get_volume_raw()
    except KefConnectionError:
        return None
