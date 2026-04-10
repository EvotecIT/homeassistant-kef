"""Minimal standalone example for the reusable KEF client package."""

from __future__ import annotations

import asyncio
import os

from aiohttp import ClientSession

from kef_client import async_create_client


async def main() -> None:
    host = os.environ.get("KEF_HOST", "192.168.1.20")

    async with ClientSession() as session:
        client = await async_create_client(host, session)
        device = await client.async_identify()
        snapshot = await client.async_refresh()

    print(f"Device: {device.device_name}")
    print(f"Model: {device.model}")
    print(f"Backend: {device.backend}")
    print(f"Source: {snapshot.source}")
    print(f"Volume: {snapshot.volume}")


if __name__ == "__main__":
    asyncio.run(main())
