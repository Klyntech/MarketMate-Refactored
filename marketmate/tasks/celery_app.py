"""
marketmate/tasks/celery_app.py
────────────────────────────────
Celery app configuration and background tasks for MarketMate.

Provides six Celery tasks for offloading heavy or I/O-bound work:
  1. run_mate_ops_cycle   — Run a MATE-Ops observation cycle
  2. run_health_check     — Run a health check and store results
  3. pull_ollama_model    — Pull an Ollama model by name
  4. clear_redis_cache    — Clear Redis cache by pattern
  5. send_telegram_alert  — Send a Telegram notification
  6. run_browser_check    — Run a Playwright browser check on a URL

When Celery is not installed (or the broker is unreachable), tasks
degrade to synchronous stubs so the rest of the application keeps
working.  Set ``CELERY_BROKER_URL`` and ``CELERY_RESULT_BACKEND``
environment variables to enable the full async queue.
"""

from __future__ import annotations

import os
from typing import Any, Dict

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger

log = get_logger("tasks.celery_app")

# ─── Celery availability guard ──────────────────────────────────────────────────

celery_available: bool = False
celery_app: Any = None

try:
    from celery import Celery  # type: ignore[import-untyped]

    _broker_url = os.environ.get("CELERY_BROKER_URL", "redis://localhost:6379/1")
    _result_backend = os.environ.get("CELERY_RESULT_BACKEND", "redis://localhost:6379/2")

    celery_app = Celery(
        "marketmate",
        broker=_broker_url,
        backend=_result_backend,
    )

    celery_app.conf.update(
        task_serializer="json",
        result_serializer="json",
        accept_content=["json"],
        timezone="UTC",
        enable_utc=True,
        task_track_started=True,
        result_expires=3600,
    )

    celery_available = True
    log.info("celery_configured", broker=_broker_url)

except ImportError:
    log.warning(
        "celery_not_installed",
        hint="Install with: pip install celery. Tasks will run synchronously.",
    )
except Exception as exc:
    log.warning("celery_setup_failed", error=str(exc))


# ─── Helper: run coroutine synchronously inside a Celery worker ────────────────

def _run_async(coro):  # pragma: no cover — event loop management
    """Run an async coroutine from a synchronous Celery task.

    Creates a new event loop per invocation so it works even when
    the worker process doesn't have a running loop.
    """
    import asyncio

    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        # We're inside an existing loop — use nest_asyncio or spawn
        import concurrent.futures

        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as pool:
            future = pool.submit(asyncio.run, coro)
            return future.result()
    else:
        return asyncio.run(coro)


# ─── Task definitions (Celery installed) ────────────────────────────────────────

if celery_available and celery_app is not None:

    @celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
    def run_mate_ops_cycle(self) -> Dict[str, Any]:
        """Run a MATE-Ops Observe->Analyze->Plan->Execute->Verify cycle.

        Returns a summary dict with cycle_id, observations count,
        execution results, and verification status.
        """
        try:
            from marketmate.mate_ops.agent import MATEOpsAgent
            from marketmate.mate_ops.permission_gate import AuthorityLevel, PermissionGate
            from marketmate.core.llm import llm_provider

            gate = PermissionGate(max_authority_level=AuthorityLevel.SAFE_OPS)
            agent = MATEOpsAgent(
                llm_provider=llm_provider,
                authority_level=AuthorityLevel.SAFE_OPS,
                permission_gate=gate,
            )
            result = _run_async(agent.run_cycle())

            return {
                "cycle_id": result.cycle_id,
                "observations": len(result.observations),
                "analysis_preview": result.analysis[:200] if result.analysis else "",
                "actions_planned": len(result.plan.get("actions", [])),
                "execution_results": result.execution_results,
                "verification": result.verification,
                "latency_ms": result.total_latency_ms,
            }
        except Exception as exc:
            log.error("run_mate_ops_cycle_failed", error=str(exc))
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                return {"status": "failed", "error": str(exc)}

    @celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
    def run_health_check(self) -> Dict[str, Any]:
        """Run a health check across all monitored services and return results."""
        try:
            from marketmate.mate_ops.agent import MATEOpsAgent
            from marketmate.mate_ops.permission_gate import AuthorityLevel, PermissionGate

            gate = PermissionGate(max_authority_level=AuthorityLevel.READ_ONLY)
            agent = MATEOpsAgent(authority_level=AuthorityLevel.READ_ONLY, permission_gate=gate)
            result = _run_async(agent.check_health())
            return {"status": "ok", "health": result}
        except Exception as exc:
            log.error("run_health_check_failed", error=str(exc))
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                return {"status": "failed", "error": str(exc)}

    @celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
    def pull_ollama_model(self, model_name: str) -> Dict[str, Any]:
        """Pull an Ollama model by name.

        Sends a pull request to the local Ollama API and waits for
        completion.  Ollama streams progress, but this task returns
        only the final result.
        """
        try:
            import httpx

            ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            ollama_native = ollama_base.replace("/v1", "").rstrip("/")

            def _pull():
                import asyncio

                async def _do():
                    async with httpx.AsyncClient(timeout=600) as client:
                        resp = await client.post(
                            f"{ollama_native}/api/pull",
                            json={"name": model_name, "stream": False},
                        )
                        if resp.status_code == 200:
                            return {"status": "ok", "model": model_name}
                        else:
                            return {
                                "status": "error",
                                "model": model_name,
                                "error": f"Ollama returned HTTP {resp.status_code}",
                                "detail": resp.text[:200],
                            }

                return asyncio.run(_do())

            result = _pull()
            if result.get("status") == "error":
                log.warning("pull_ollama_model_error", model=model_name, error=result.get("error"))
                raise RuntimeError(result.get("error", "Unknown Ollama pull error"))
            return result
        except Exception as exc:
            log.error("pull_ollama_model_failed", model=model_name, error=str(exc))
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                return {"status": "failed", "model": model_name, "error": str(exc)}

    @celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
    def clear_redis_cache(self, pattern: str = "*") -> Dict[str, Any]:
        """Clear Redis cache keys matching *pattern*.

        Uses SCAN + DEL to avoid blocking Redis on large key spaces.
        """
        try:

            def _clear():
                import asyncio

                async def _do():
                    import redis.asyncio as aioredis

                    redis_url = cfg.redis.url or "redis://localhost:6379"
                    async with aioredis.from_url(redis_url, socket_timeout=5) as r:
                        keys = []
                        async for key in r.scan_iter(match=pattern, count=100):
                            keys.append(key)
                        if keys:
                            deleted = await r.delete(*keys)
                            return {
                                "pattern": pattern,
                                "keys_found": len(keys),
                                "keys_deleted": deleted,
                                "status": "success",
                            }
                        return {
                            "pattern": pattern,
                            "keys_found": 0,
                            "keys_deleted": 0,
                            "status": "no_matching_keys",
                        }

                return asyncio.run(_do())

            return _clear()
        except ImportError:
            log.warning("clear_redis_cache_no_redis", hint="pip install redis")
            return {"pattern": pattern, "error": "redis library not installed"}
        except Exception as exc:
            log.error("clear_redis_cache_failed", pattern=pattern, error=str(exc))
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                return {"pattern": pattern, "status": "failed", "error": str(exc)}

    @celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
    def send_telegram_alert(self, message: str, severity: str = "info") -> Dict[str, Any]:
        """Send a Telegram notification to the admin chat."""
        try:
            import httpx

            if not cfg.telegram.bot_token or not cfg.telegram.admin_chat_id:
                return {
                    "status": "skipped",
                    "reason": "Telegram not configured (TELEGRAM_BOT_TOKEN or TELEGRAM_ADMIN_CHAT_ID missing)",
                }

            severity_emoji = {
                "info": "\u2139\ufe0f",
                "warning": "\u26a0\ufe0f",
                "critical": "\U0001f6a8",
            }.get(severity, "\U0001f4e1")

            text = f"{severity_emoji} **MATE-Ops Alert** ({severity.upper()})\n\n{message}"

            url = f"https://api.telegram.org/bot{cfg.telegram.bot_token}/sendMessage"

            def _send():
                import asyncio

                async def _do():
                    async with httpx.AsyncClient(timeout=10) as client:
                        resp = await client.post(
                            url,
                            json={
                                "chat_id": cfg.telegram.admin_chat_id,
                                "text": text,
                                "parse_mode": "Markdown",
                            },
                        )
                        if resp.status_code == 200:
                            return {"status": "sent", "severity": severity}
                        return {
                            "status": "failed",
                            "error": f"Telegram API returned HTTP {resp.status_code}",
                        }

                return asyncio.run(_do())

            return _send()
        except Exception as exc:
            log.error("send_telegram_alert_failed", error=str(exc))
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                return {"status": "failed", "error": str(exc)}

    @celery_app.task(bind=True, max_retries=3, default_retry_delay=60)
    def run_browser_check(self, url: str) -> Dict[str, Any]:
        """Run a Playwright browser check on *url*.

        Returns page load time, status code, SSL validity, and
        any JavaScript console errors detected.
        """
        try:
            from marketmate.monitor.browser import BrowserMonitor

            monitor = BrowserMonitor(headless=True, timeout=30000)

            def _check():
                import asyncio

                async def _do():
                    try:
                        await monitor.start()
                        result = await monitor.check_page(url)
                        return result
                    finally:
                        await monitor.stop()

                return asyncio.run(_do())

            return _check()
        except Exception as exc:
            log.error("run_browser_check_failed", url=url, error=str(exc))
            try:
                raise self.retry(exc=exc)
            except self.MaxRetriesExceededError:
                return {"url": url, "status": "failed", "error": str(exc)}


# ─── Task stubs (Celery NOT installed) ──────────────────────────────────────────
# When Celery is unavailable, provide synchronous fallbacks so that
# callers can use the same function signatures without guarding every
# call site with ``if celery_available``.

else:

    def run_mate_ops_cycle(**kwargs) -> Dict[str, Any]:  # type: ignore[misc]
        """Synchronous stub — Celery not installed."""
        log.warning("celery_task_stub", task="run_mate_ops_cycle", hint="Install celery for async queue")
        try:
            from marketmate.mate_ops.agent import MATEOpsAgent
            from marketmate.mate_ops.permission_gate import AuthorityLevel, PermissionGate
            from marketmate.core.llm import llm_provider

            import asyncio

            gate = PermissionGate(max_authority_level=AuthorityLevel.SAFE_OPS)
            agent = MATEOpsAgent(
                llm_provider=llm_provider,
                authority_level=AuthorityLevel.SAFE_OPS,
                permission_gate=gate,
            )
            result = asyncio.run(agent.run_cycle())
            return {
                "cycle_id": result.cycle_id,
                "observations": len(result.observations),
                "analysis_preview": result.analysis[:200] if result.analysis else "",
                "actions_planned": len(result.plan.get("actions", [])),
                "execution_results": result.execution_results,
                "verification": result.verification,
                "latency_ms": result.total_latency_ms,
                "mode": "synchronous_fallback",
            }
        except Exception as exc:
            log.error("run_mate_ops_cycle_stub_failed", error=str(exc))
            return {"status": "failed", "error": str(exc), "mode": "synchronous_fallback"}

    def run_health_check(**kwargs) -> Dict[str, Any]:  # type: ignore[misc]
        """Synchronous stub — Celery not installed."""
        log.warning("celery_task_stub", task="run_health_check", hint="Install celery for async queue")
        try:
            from marketmate.mate_ops.agent import MATEOpsAgent
            from marketmate.mate_ops.permission_gate import AuthorityLevel, PermissionGate

            import asyncio

            gate = PermissionGate(max_authority_level=AuthorityLevel.READ_ONLY)
            agent = MATEOpsAgent(authority_level=AuthorityLevel.READ_ONLY, permission_gate=gate)
            result = asyncio.run(agent.check_health())
            return {"status": "ok", "health": result, "mode": "synchronous_fallback"}
        except Exception as exc:
            log.error("run_health_check_stub_failed", error=str(exc))
            return {"status": "failed", "error": str(exc), "mode": "synchronous_fallback"}

    def pull_ollama_model(model_name: str, **kwargs) -> Dict[str, Any]:
        """Synchronous stub — Celery not installed."""
        log.warning("celery_task_stub", task="pull_ollama_model", hint="Install celery for async queue")
        try:
            import httpx

            ollama_base = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
            ollama_native = ollama_base.replace("/v1", "").rstrip("/")
            resp = httpx.post(
                f"{ollama_native}/api/pull",
                json={"name": model_name, "stream": False},
                timeout=600,
            )
            if resp.status_code == 200:
                return {"status": "ok", "model": model_name, "mode": "synchronous_fallback"}
            return {
                "status": "error",
                "model": model_name,
                "error": f"Ollama returned HTTP {resp.status_code}",
                "mode": "synchronous_fallback",
            }
        except Exception as exc:
            log.error("pull_ollama_model_stub_failed", model=model_name, error=str(exc))
            return {"status": "failed", "model": model_name, "error": str(exc), "mode": "synchronous_fallback"}

    def clear_redis_cache(pattern: str = "*", **kwargs) -> Dict[str, Any]:
        """Synchronous stub — Celery not installed."""
        log.warning("celery_task_stub", task="clear_redis_cache", hint="Install celery for async queue")
        try:
            import redis

            redis_url = cfg.redis.url or "redis://localhost:6379"
            r = redis.from_url(redis_url, socket_timeout=5)
            keys = list(r.scan_iter(match=pattern, count=100))
            if keys:
                deleted = r.delete(*keys)
                return {
                    "pattern": pattern,
                    "keys_found": len(keys),
                    "keys_deleted": deleted,
                    "status": "success",
                    "mode": "synchronous_fallback",
                }
            return {
                "pattern": pattern,
                "keys_found": 0,
                "keys_deleted": 0,
                "status": "no_matching_keys",
                "mode": "synchronous_fallback",
            }
        except ImportError:
            return {"pattern": pattern, "error": "redis library not installed", "mode": "synchronous_fallback"}
        except Exception as exc:
            log.error("clear_redis_cache_stub_failed", pattern=pattern, error=str(exc))
            return {"pattern": pattern, "status": "failed", "error": str(exc), "mode": "synchronous_fallback"}

    def send_telegram_alert(message: str, severity: str = "info", **kwargs) -> Dict[str, Any]:
        """Synchronous stub — Celery not installed."""
        log.warning("celery_task_stub", task="send_telegram_alert", hint="Install celery for async queue")
        try:
            import httpx

            if not cfg.telegram.bot_token or not cfg.telegram.admin_chat_id:
                return {
                    "status": "skipped",
                    "reason": "Telegram not configured",
                    "mode": "synchronous_fallback",
                }

            severity_emoji = {
                "info": "\u2139\ufe0f",
                "warning": "\u26a0\ufe0f",
                "critical": "\U0001f6a8",
            }.get(severity, "\U0001f4e1")

            text = f"{severity_emoji} **MATE-Ops Alert** ({severity.upper()})\n\n{message}"
            url = f"https://api.telegram.org/bot{cfg.telegram.bot_token}/sendMessage"
            resp = httpx.post(
                url,
                json={
                    "chat_id": cfg.telegram.admin_chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                },
                timeout=10,
            )
            if resp.status_code == 200:
                return {"status": "sent", "severity": severity, "mode": "synchronous_fallback"}
            return {
                "status": "failed",
                "error": f"Telegram API returned HTTP {resp.status_code}",
                "mode": "synchronous_fallback",
            }
        except Exception as exc:
            log.error("send_telegram_alert_stub_failed", error=str(exc))
            return {"status": "failed", "error": str(exc), "mode": "synchronous_fallback"}

    def run_browser_check(url: str, **kwargs) -> Dict[str, Any]:
        """Synchronous stub — Celery not installed."""
        log.warning("celery_task_stub", task="run_browser_check", hint="Install celery for async queue")
        try:
            from marketmate.monitor.browser import BrowserMonitor

            import asyncio

            monitor = BrowserMonitor(headless=True, timeout=30000)

            async def _do():
                try:
                    await monitor.start()
                    return await monitor.check_page(url)
                finally:
                    await monitor.stop()

            result = asyncio.run(_do())
            result["mode"] = "synchronous_fallback"
            return result
        except Exception as exc:
            log.error("run_browser_check_stub_failed", url=url, error=str(exc))
            return {"url": url, "status": "failed", "error": str(exc), "mode": "synchronous_fallback"}
