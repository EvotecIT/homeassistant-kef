"""Loopback HTTP boundary shared by client and Home Assistant tests."""

from contextlib import asynccontextmanager

from aiohttp import web


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
