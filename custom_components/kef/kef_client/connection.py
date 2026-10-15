"""Bounded legacy connection recovery and protocol-probe context."""

from __future__ import annotations

import asyncio
import socket
from typing import TYPE_CHECKING

from .exceptions import KefError

if TYPE_CHECKING:
    from .client import BaseKefClient
    from .models import KefDeviceInfo


async def async_open_legacy_connection(
    host: str, port: int, timeout: float,
) -> tuple[asyncio.StreamReader, asyncio.StreamWriter]:
    """Retry refusal before sending bytes while a speaker releases its socket."""
    deadline = asyncio.get_running_loop().time() + timeout
    attempt = 0
    while True:
        attempt += 1
        remaining = max(0.0, deadline - asyncio.get_running_loop().time())
        try:
            return await asyncio.wait_for(
                asyncio.open_connection(host, port, family=socket.AF_INET),
                timeout=remaining,
            )
        except ConnectionRefusedError:
            if attempt == 4 or deadline - asyncio.get_running_loop().time() <= 0.5:
                raise
            await asyncio.sleep(0.5)


async def async_probe(client: BaseKefClient, port: int) -> KefDeviceInfo:
    """Identify a backend and retain only safe protocol context on failure."""
    try:
        return await client.async_identify()
    except KefError as error:
        error.backend = client.backend.value
        error.port = port
        error.operation = error.operation or "identify"
        raise
