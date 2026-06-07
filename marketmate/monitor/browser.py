"""
marketmate/monitor/browser.py
─────────────────────────────
Playwright-based browser health monitoring for MarketMate.

Runs full browser checks — page load, SSL validity, JS console errors,
Core Web Vitals (LCP, FID, CLS) — against any URL.

Gracefully degrades when Playwright is not installed, returning a
diagnostic dict instead of raising an ImportError.

Usage:
    monitor = BrowserMonitor(headless=True, timeout=30000)
    await monitor.start()
    result = await monitor.check_page("https://example.com")
    await monitor.stop()
"""

from __future__ import annotations

import os
import ssl
import time
import socket
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse

from marketmate.core.logger import get_logger

log = get_logger("monitor.browser")

# ---------------------------------------------------------------------------
# Playwright import guard — every public method checks this flag so that the
# module can be imported safely even when playwright is not installed.
# ---------------------------------------------------------------------------
_PLAYWRIGHT_AVAILABLE: bool = False
_pw_async_api: Any = None

try:
    from playwright.async_api import async_playwright  # type: ignore[import-untyped]
    _PLAYWRIGHT_AVAILABLE = True
    _pw_async_api = async_playwright
except ImportError:
    pass


def _not_installed_result() -> Dict[str, Any]:
    """Standardised dict returned when Playwright is not available."""
    return {
        "error": "playwright not installed",
        "hint": "Install with: pip install playwright && playwright install",
    }


# ---------------------------------------------------------------------------
# BrowserMonitor
# ---------------------------------------------------------------------------

class BrowserMonitor:
    """Async Playwright browser for health & performance monitoring.

    Parameters
    ----------
    headless:
        Run Chromium in headless mode (default ``True``).
    timeout:
        Default navigation / action timeout in milliseconds (default 30000).
    """

    def __init__(self, headless: bool = True, timeout: int = 30000) -> None:
        self.headless: bool = headless
        self.timeout: int = timeout

        # Lazily initialised in ``start()``
        self._playwright: Any = None
        self._browser: Any = None
        self._context: Any = None

    # ── Lifecycle ──────────────────────────────────────────────────────────

    async def start(self) -> None:
        """Launch the Playwright browser instance.

        Safe to call when Playwright is not installed — logs a warning and
        returns without raising.
        """
        if not _PLAYWRIGHT_AVAILABLE:
            log.warning("playwright_not_installed", hint="pip install playwright && playwright install")
            return

        try:
            self._playwright = await _pw_async_api().start()
            self._browser = await self._playwright.chromium.launch(
                headless=self.headless,
            )
            self._context = await self._browser.new_context(
                viewport={"width": 1280, "height": 720},
                ignore_https_errors=False,
            )
            self._context.set_default_timeout(self.timeout)
            log.info("browser_monitor_started", headless=self.headless, timeout=self.timeout)
        except Exception as exc:
            log.error("browser_monitor_start_failed", error=str(exc))
            # Ensure partial state is cleaned up
            await self.stop()
            raise

    async def stop(self) -> None:
        """Close all pages, context, browser, and Playwright itself."""
        try:
            if self._context is not None:
                for page in self._context.pages:
                    try:
                        await page.close()
                    except Exception:
                        pass
                try:
                    await self._context.close()
                except Exception:
                    pass
                self._context = None

            if self._browser is not None:
                try:
                    await self._browser.close()
                except Exception:
                    pass
                self._browser = None

            if self._playwright is not None:
                try:
                    await self._playwright.stop()
                except Exception:
                    pass
                self._playwright = None

            log.info("browser_monitor_stopped")
        except Exception as exc:
            log.error("browser_monitor_stop_error", error=str(exc))

    # ── Core check ─────────────────────────────────────────────────────────

    async def check_page(
        self,
        url: str,
        check_ssl: bool = True,
        check_content: str = "",
    ) -> Dict[str, Any]:
        """Full browser-based page health check.

        Navigates to *url* and collects:

        * HTTP status code (from response)
        * Page title
        * Load time in milliseconds
        * SSL certificate validity (socket-level check)
        * Whether *check_content* substring appears in the page body
        * Any page-level errors

        Parameters
        ----------
        url:
            Fully-qualified URL to check.
        check_ssl:
            Validate the SSL certificate via a socket-level check
            (default ``True``).
        check_content:
            Optional substring to look for in the rendered page content.
            Empty string skips the content check.

        Returns
        -------
        dict
            Keys: ``url``, ``status_code``, ``title``, ``load_time_ms``,
            ``ssl_valid``, ``content_found``, ``errors``.
        """
        if not _PLAYWRIGHT_AVAILABLE:
            return _not_installed_result()

        result: Dict[str, Any] = {
            "url": url,
            "status_code": None,
            "title": None,
            "load_time_ms": None,
            "ssl_valid": None,
            "content_found": None,
            "errors": [],
        }

        page = None
        try:
            page = await self._context.new_page()

            # Collect JS console errors
            js_errors: List[str] = []
            page.on("console", lambda msg: js_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: js_errors.append(str(err)))

            # Measure navigation time
            start_ts = time.monotonic()
            response = await page.goto(url, wait_until="load", timeout=self.timeout)
            elapsed_ms = round((time.monotonic() - start_ts) * 1000)

            result["status_code"] = response.status if response else None
            result["title"] = await page.title()
            result["load_time_ms"] = elapsed_ms

            # SSL check (socket-level, independent of Playwright's TLS handling)
            if check_ssl and url.startswith("https://"):
                result["ssl_valid"] = self._check_ssl(url)
            elif url.startswith("http://"):
                result["ssl_valid"] = None  # not applicable
            else:
                result["ssl_valid"] = None

            # Content check
            if check_content:
                body_text = await page.inner_text("body")
                result["content_found"] = check_content in body_text
            else:
                result["content_found"] = None

            result["errors"] = js_errors if js_errors else []

            log.info(
                "page_check_complete",
                url=url,
                status_code=result["status_code"],
                load_time_ms=elapsed_ms,
                ssl_valid=result["ssl_valid"],
                js_errors=len(js_errors),
            )

        except Exception as exc:
            result["errors"].append(str(exc))
            log.error("page_check_failed", url=url, error=str(exc))
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass

        return result

    # ── Convenience methods ────────────────────────────────────────────────

    async def check_api_health(self, base_url: str = "") -> Dict[str, Any]:
        """Check the MarketMate API ``/health`` endpoint.

        Parameters
        ----------
        base_url:
            Scheme + host (e.g. ``https://api.example.com``). If empty,
            falls back to ``http://localhost:8000``.

        Returns
        -------
        dict
            Same shape as :meth:`check_page`, plus ``healthy`` (bool)
            derived from status code and content.
        """
        if not _PLAYWRIGHT_AVAILABLE:
            return _not_installed_result()

        url = f"{base_url or 'http://localhost:8000'}/health"
        result = await self.check_page(url, check_ssl=True, check_content="ok")
        result["healthy"] = (
            result.get("status_code") == 200
            and result.get("content_found") is not False
        )
        return result

    async def check_dashboard(self, url: str = "") -> Dict[str, Any]:
        """Check Grafana dashboard availability.

        Parameters
        ----------
        url:
            Full Grafana dashboard URL. If empty, falls back to
            ``http://localhost:3001``.

        Returns
        -------
        dict
            Same shape as :meth:`check_page`, plus ``dashboard_available``
            (bool) derived from a successful page load.
        """
        if not _PLAYWRIGHT_AVAILABLE:
            return _not_installed_result()

        target = url or "http://localhost:3001"
        result = await self.check_page(target, check_ssl=True)
        result["dashboard_available"] = (
            result.get("status_code") is not None
            and 200 <= result.get("status_code", 0) < 400
        )
        return result

    async def take_screenshot(
        self,
        url: str,
        path: str = "./data/screenshots/",
    ) -> str:
        """Navigate to *url*, take a full-page screenshot, and save to *path*.

        The filename includes an ISO-8601 timestamp for uniqueness.

        Parameters
        ----------
        url:
            Fully-qualified URL to capture.
        path:
            Directory to save the screenshot (created if needed).

        Returns
        -------
        str
            Absolute path to the saved screenshot PNG.
        """
        if not _PLAYWRIGHT_AVAILABLE:
            log.warning("take_screenshot_failed", reason="playwright not installed")
            return ""

        os.makedirs(path, exist_ok=True)
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        parsed = urlparse(url)
        safe_host = (parsed.hostname or "unknown").replace(".", "_")
        filename = f"{safe_host}_{timestamp}.png"
        filepath = os.path.join(path, filename)

        page = None
        try:
            page = await self._context.new_page()
            await page.goto(url, wait_until="load", timeout=self.timeout)
            await page.screenshot(path=filepath, full_page=True)
            log.info("screenshot_saved", url=url, path=filepath)
        except Exception as exc:
            log.error("screenshot_failed", url=url, error=str(exc))
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass

        return filepath

    async def check_javascript_errors(self, url: str) -> Dict[str, Any]:
        """Navigate to *url* and collect JavaScript console errors.

        Parameters
        ----------
        url:
            Fully-qualified URL to check.

        Returns
        -------
        dict
            Keys: ``url``, ``error_count``, ``errors`` (list of strings),
            ``has_errors`` (bool).
        """
        if not _PLAYWRIGHT_AVAILABLE:
            return _not_installed_result()

        result: Dict[str, Any] = {
            "url": url,
            "error_count": 0,
            "errors": [],
            "has_errors": False,
        }

        page = None
        try:
            page = await self._context.new_page()

            js_errors: List[str] = []
            page.on("console", lambda msg: js_errors.append(msg.text) if msg.type == "error" else None)
            page.on("pageerror", lambda err: js_errors.append(str(err)))

            await page.goto(url, wait_until="load", timeout=self.timeout)
            # Give a short grace period for late errors (e.g. async scripts)
            await page.wait_for_timeout(2000)

            result["errors"] = js_errors
            result["error_count"] = len(js_errors)
            result["has_errors"] = len(js_errors) > 0

            log.info(
                "js_error_check_complete",
                url=url,
                error_count=result["error_count"],
            )
        except Exception as exc:
            result["errors"].append(str(exc))
            result["error_count"] = len(result["errors"])
            result["has_errors"] = True
            log.error("js_error_check_failed", url=url, error=str(exc))
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass

        return result

    async def measure_performance(self, url: str) -> Dict[str, Any]:
        """Measure page-load performance metrics (LCP, FID, CLS).

        Uses the Performance Observer API injected into the page context
        to capture Core Web Vitals.

        Parameters
        ----------
        url:
            Fully-qualified URL to measure.

        Returns
        -------
        dict
            Keys: ``url``, ``lcp`` (ms), ``fid`` (ms), ``cls`` (score),
            ``load_time_ms``, ``errors``.
        """
        if not _PLAYWRIGHT_AVAILABLE:
            return _not_installed_result()

        result: Dict[str, Any] = {
            "url": url,
            "lcp": None,
            "fid": None,
            "cls": None,
            "load_time_ms": None,
            "errors": [],
        }

        # JavaScript snippet to capture Core Web Vitals via Performance
        # Observer.  Each metric is stored on ``window.__cwv`` for retrieval.
        _cwv_script = """
        () => {
            window.__cwv = { lcp: null, fid: null, cls: null };

            // Largest Contentful Paint
            try {
                new PerformanceObserver((entryList) => {
                    const entries = entryList.getEntries();
                    if (entries.length > 0) {
                        window.__cwv.lcp = entries[entries.length - 1].startTime;
                    }
                }).observe({ type: 'largest-contentful-paint', buffered: true });
            } catch (_) {}

            // First Input Delay
            try {
                new PerformanceObserver((entryList) => {
                    const entries = entryList.getEntries();
                    if (entries.length > 0) {
                        window.__cwv.fid = entries[0].processingStart - entries[0].startTime;
                    }
                }).observe({ type: 'first-input', buffered: true });
            } catch (_) {}

            // Cumulative Layout Shift
            try {
                let clsValue = 0;
                new PerformanceObserver((entryList) => {
                    for (const entry of entryList.getEntries()) {
                        if (!entry.hadRecentInput) {
                            clsValue += entry.value;
                        }
                    }
                    window.__cwv.cls = clsValue;
                }).observe({ type: 'layout-shift', buffered: true });
            } catch (_) {}
        }
        """

        page = None
        try:
            page = await self._context.new_page()

            # Inject CWV observers before navigation so we catch early paints
            await page.add_init_script(_cwv_script)

            start_ts = time.monotonic()
            await page.goto(url, wait_until="load", timeout=self.timeout)
            elapsed_ms = round((time.monotonic() - start_ts) * 1000)
            result["load_time_ms"] = elapsed_ms

            # Allow a short grace period for late LCP / layout shifts
            await page.wait_for_timeout(3000)

            # Retrieve captured metrics
            cwv = await page.evaluate("() => window.__cwv")

            if cwv:
                result["lcp"] = round(cwv.get("lcp"), 2) if cwv.get("lcp") is not None else None
                result["fid"] = round(cwv.get("fid"), 2) if cwv.get("fid") is not None else None
                result["cls"] = round(cwv.get("cls"), 4) if cwv.get("cls") is not None else None

            log.info(
                "performance_measurement_complete",
                url=url,
                load_time_ms=elapsed_ms,
                lcp=result["lcp"],
                fid=result["fid"],
                cls=result["cls"],
            )
        except Exception as exc:
            result["errors"].append(str(exc))
            log.error("performance_measurement_failed", url=url, error=str(exc))
        finally:
            if page is not None:
                try:
                    await page.close()
                except Exception:
                    pass

        return result

    # ── Helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _check_ssl(url: str) -> bool:
        """Socket-level SSL certificate validity check.

        Returns ``True`` if the certificate is valid and not expired,
        ``False`` otherwise.  Non-HTTPS URLs return ``None``.
        """
        try:
            parsed = urlparse(url)
            hostname = parsed.hostname
            port = parsed.port or 443

            context = ssl.create_default_context()
            with socket.create_connection((hostname, port), timeout=10) as sock:
                with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                    cert = ssock.getpeercert()
                    # ``getpeercert`` returns ``{}`` if no cert / invalid
                    return bool(cert)
        except Exception:
            return False
