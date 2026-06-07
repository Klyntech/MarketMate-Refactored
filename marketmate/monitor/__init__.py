"""
marketmate.monitor
──────────────────
Playwright-based browser health monitoring for MarketMate.

Provides real-browser checks (page load, SSL, JS errors, performance)
that go beyond simple HTTP pings — useful for monitoring dashboards,
API health endpoints, and user-facing pages.

Components:
  BrowserMonitor — async Playwright browser for health & perf checks

Quick start:
  monitor = BrowserMonitor(headless=True)
  await monitor.start()
  result = await monitor.check_page("https://example.com")
  await monitor.stop()
"""

from marketmate.monitor.browser import BrowserMonitor

__all__ = [
    "BrowserMonitor",
]
