"""
marketmate/core/healthcheck.py
───────────────────────────────
Minimal async HTTP health check server.
Used by Docker HEALTHCHECK and uptime monitors (UptimeRobot, etc.)

Runs on PORT env var (default 3000).
GET /health -> 200 OK {"status": "ok", "uptime_s": 12345}
GET /        -> 200 OK (simple ping)

Launch from main.py alongside the scan loop.

Migrated from ``utils/healthcheck.py`` — import path updated to
``marketmate.core.logger``.
"""

from __future__ import annotations
import asyncio
import json
import time
from aiohttp import web

from marketmate.core.logger import get_logger

log = get_logger("healthcheck")

_START_TIME = time.time()


async def _health_handler(request: web.Request) -> web.Response:
    uptime = int(time.time() - _START_TIME)
    return web.Response(
        status=200,
        content_type="application/json",
        text=json.dumps({"status": "ok", "uptime_s": uptime}),
    )


async def _ping_handler(request: web.Request) -> web.Response:
    return web.Response(status=200, text="ok")


async def start_healthcheck(port: int = 3000) -> None:
    """
    Start the health check server as a background task.
    Call with: asyncio.create_task(start_healthcheck())
    """
    app = web.Application()
    app.router.add_get("/health", _health_handler)
    app.router.add_get("/",       _ping_handler)

    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", port)
    await site.start()
    log.info("healthcheck_server_started", port=port)
