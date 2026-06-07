"""
marketmate/mate_ops/observer.py
───────────────────────────────
Observation layer: collects telemetry from monitoring sources.

The TelemetryCollector runs health checks against all critical
infrastructure dependencies and returns structured Observation
objects for the MATE-Ops agent to analyze.

Monitored services:
  - MarketMate API (/health endpoint)
  - Ollama (local LLM inference)
  - Redis (state cache + session store)
  - MongoDB (primary database)
  - Telegram Bot API (delivery channel)
  - Prometheus (metrics + alerting)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger

log = get_logger("mate_ops.observer")


# ─── Observation Data ─────────────────────────────────────────────────────────

@dataclass
class Observation:
    """
    A single telemetry observation from a monitoring source.

    Attributes:
        source:   The service or component being observed (e.g. "api", "redis").
        status:   Health status — "ok", "warn", or "error".
        message:  Human-readable description of the observation.
        timestamp: ISO 8601 timestamp of when the observation was taken.
        details:  Additional structured data (latency, error codes, etc.).
    """

    source: str
    status: str  # "ok", "warn", "error"
    message: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    details: Dict[str, Any] = field(default_factory=dict)


# ─── Telemetry Collector ──────────────────────────────────────────────────────

class TelemetryCollector:
    """
    Collects telemetry from all monitoring sources.

    Each check_* method returns an Observation. The collect() method
    runs all checks concurrently and returns the full list.

    All checks are designed to be non-blocking and fast — each has
    a built-in timeout to prevent slow services from blocking the
    observation cycle.
    """

    def __init__(
        self,
        api_base_url: str = "",
        ollama_base_url: str = "http://localhost:11434",
        prometheus_url: str = "",
    ) -> None:
        """
        Initialize the telemetry collector.

        Args:
            api_base_url: Base URL for the MarketMate API health endpoint.
                Defaults to the platform base URL from config.
            ollama_base_url: Base URL for the Ollama API.
            prometheus_url: URL for the Prometheus query endpoint.
        """
        self._api_base_url = api_base_url or cfg.platform.base_url
        self._ollama_base_url = ollama_base_url
        self._prometheus_url = prometheus_url

    # ── Full Collection ───────────────────────────────────────────────────────

    async def collect(self) -> List[Observation]:
        """
        Run all collectors and return observations.

        All checks are run concurrently for speed. Failed checks
        return error-status observations rather than raising — a
        failed check IS the observation.
        """
        import asyncio

        checks = [
            self.check_api_health(),
            self.check_ollama_health(),
            self.check_redis_health(),
            self.check_mongodb_health(),
            self.check_telegram_bot(),
            self.collect_prometheus_metrics(),
        ]

        results = await asyncio.gather(*checks, return_exceptions=True)

        observations: List[Observation] = []
        for result in results:
            if isinstance(result, Observation):
                observations.append(result)
            elif isinstance(result, Exception):
                observations.append(Observation(
                    source="telemetry_collector",
                    status="error",
                    message=f"Collector raised exception: {result}",
                    details={"exception": str(result)},
                ))
            else:
                observations.append(Observation(
                    source="telemetry_collector",
                    status="error",
                    message=f"Unexpected result type: {type(result)}",
                ))

        healthy = sum(1 for o in observations if o.status == "ok")
        degraded = sum(1 for o in observations if o.status == "warn")
        errors = sum(1 for o in observations if o.status == "error")

        log.info(
            "telemetry_collection_complete",
            total=len(observations),
            healthy=healthy,
            degraded=degraded,
            errors=errors,
        )

        return observations

    # ── Individual Checks ─────────────────────────────────────────────────────

    async def check_api_health(self) -> Observation:
        """
        Check MarketMate API health via /health endpoint.

        Expects a 200 response with {"status": "ok"}.
        """
        start = time.monotonic()
        url = f"{self._api_base_url}/health"

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
            latency_ms = round((time.monotonic() - start) * 1000, 1)

            if resp.status_code == 200:
                data = resp.json()
                status = "ok" if data.get("status") == "ok" else "warn"
                return Observation(
                    source="api",
                    status=status,
                    message=f"API health check: {data.get('status', 'unknown')}",
                    details={
                        "latency_ms": latency_ms,
                        "status_code": resp.status_code,
                        "uptime_s": data.get("uptime_s"),
                    },
                )
            else:
                return Observation(
                    source="api",
                    status="error",
                    message=f"API returned HTTP {resp.status_code}",
                    details={
                        "latency_ms": latency_ms,
                        "status_code": resp.status_code,
                    },
                )

        except httpx.TimeoutException:
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            return Observation(
                source="api",
                status="error",
                message="API health check timed out",
                details={"latency_ms": latency_ms, "timeout_s": 10},
            )
        except Exception as exc:
            return Observation(
                source="api",
                status="error",
                message=f"API health check failed: {exc}",
                details={"exception": str(exc)},
            )

    async def check_ollama_health(self) -> Observation:
        """
        Check Ollama service health via /api/tags endpoint.

        Ollama returns a list of available models. We verify
        the service is responding and at least one model is loaded.
        """
        start = time.monotonic()
        url = f"{self._ollama_base_url}/api/tags"

        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.get(url)
            latency_ms = round((time.monotonic() - start) * 1000, 1)

            if resp.status_code == 200:
                data = resp.json()
                models = data.get("models", [])
                model_names = [m.get("name", "") for m in models]

                if models:
                    return Observation(
                        source="ollama",
                        status="ok",
                        message=f"Ollama healthy: {len(models)} model(s) loaded",
                        details={
                            "latency_ms": latency_ms,
                            "model_count": len(models),
                            "models": model_names[:5],  # first 5 to avoid huge payloads
                        },
                    )
                else:
                    return Observation(
                        source="ollama",
                        status="warn",
                        message="Ollama responding but no models loaded",
                        details={"latency_ms": latency_ms, "model_count": 0},
                    )
            else:
                return Observation(
                    source="ollama",
                    status="error",
                    message=f"Ollama returned HTTP {resp.status_code}",
                    details={
                        "latency_ms": latency_ms,
                        "status_code": resp.status_code,
                    },
                )

        except httpx.ConnectError:
            return Observation(
                source="ollama",
                status="error",
                message="Ollama not reachable (connection refused)",
                details={"url": url},
            )
        except httpx.TimeoutException:
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            return Observation(
                source="ollama",
                status="error",
                message="Ollama health check timed out",
                details={"latency_ms": latency_ms, "timeout_s": 15},
            )
        except Exception as exc:
            return Observation(
                source="ollama",
                status="error",
                message=f"Ollama health check failed: {exc}",
                details={"exception": str(exc)},
            )

    async def check_redis_health(self) -> Observation:
        """
        Check Redis health by sending a PING command.

        Uses the Redis URL from config. Falls back to a local
        connection if no URL is configured.
        """
        start = time.monotonic()

        try:
            import redis.asyncio as aioredis

            redis_url = cfg.redis.url or "redis://localhost:6379"
            async with aioredis.from_url(redis_url, socket_timeout=5) as r:
                pong = await r.ping()
                latency_ms = round((time.monotonic() - start) * 1000, 1)

                if pong:
                    # Get some basic info
                    info = {}
                    try:
                        info_raw = await r.info("server")
                        info["redis_version"] = info_raw.get("redis_version", "unknown")
                        info["connected_clients"] = info_raw.get("connected_clients", 0)
                    except Exception:
                        pass

                    return Observation(
                        source="redis",
                        status="ok",
                        message="Redis PING successful",
                        details={"latency_ms": latency_ms, **info},
                    )
                else:
                    return Observation(
                        source="redis",
                        status="error",
                        message="Redis PING returned False",
                        details={"latency_ms": latency_ms},
                    )

        except ImportError:
            return Observation(
                source="redis",
                status="warn",
                message="redis async library not installed",
                details={"hint": "pip install redis"},
            )
        except Exception as exc:
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            return Observation(
                source="redis",
                status="error",
                message=f"Redis health check failed: {exc}",
                details={"latency_ms": latency_ms, "exception": str(exc)},
            )

    async def check_mongodb_health(self) -> Observation:
        """
        Check MongoDB health by running a ping command.

        Uses the MongoDB URI from config.
        """
        start = time.monotonic()

        try:
            from pymongo import AsyncMongoClient  # type: ignore[import-untyped]

            client = AsyncMongoClient(
                cfg.mongo.uri,
                serverSelectionTimeoutMS=cfg.mongo.server_timeout_ms,
            )
            result = await client.admin.command("ping")
            await client.close()
            latency_ms = round((time.monotonic() - start) * 1000, 1)

            if result.get("ok") == 1.0:
                return Observation(
                    source="mongodb",
                    status="ok",
                    message="MongoDB ping successful",
                    details={"latency_ms": latency_ms, "db": cfg.mongo.db_name},
                )
            else:
                return Observation(
                    source="mongodb",
                    status="error",
                    message="MongoDB ping returned not-ok",
                    details={"latency_ms": latency_ms, "result": str(result)},
                )

        except ImportError:
            # Try synchronous pymongo as fallback
            try:
                from pymongo import MongoClient

                client = MongoClient(
                    cfg.mongo.uri,
                    serverSelectionTimeoutMS=cfg.mongo.server_timeout_ms,
                )
                result = client.admin.command("ping")
                client.close()
                latency_ms = round((time.monotonic() - start) * 1000, 1)

                if result.get("ok") == 1.0:
                    return Observation(
                        source="mongodb",
                        status="ok",
                        message="MongoDB ping successful (sync fallback)",
                        details={"latency_ms": latency_ms, "db": cfg.mongo.db_name},
                    )
                else:
                    return Observation(
                        source="mongodb",
                        status="error",
                        message="MongoDB ping returned not-ok (sync fallback)",
                        details={"latency_ms": latency_ms, "result": str(result)},
                    )
            except Exception as exc2:
                return Observation(
                    source="mongodb",
                    status="error",
                    message=f"MongoDB health check failed: {exc2}",
                    details={"exception": str(exc2)},
                )
        except Exception as exc:
            latency_ms = round((time.monotonic() - start) * 1000, 1)
            return Observation(
                source="mongodb",
                status="error",
                message=f"MongoDB health check failed: {exc}",
                details={"latency_ms": latency_ms, "exception": str(exc)},
            )

    async def check_telegram_bot(self) -> Observation:
        """
        Check Telegram Bot API health via getMe endpoint.

        Verifies the bot token is valid and the bot can reach
        the Telegram API.
        """
        start = time.monotonic()

        if not cfg.telegram.bot_token:
            return Observation(
                source="telegram_bot",
                status="warn",
                message="Telegram bot token not configured",
                details={"hint": "Set TELEGRAM_BOT_TOKEN environment variable"},
            )

        try:
            url = f"https://api.telegram.org/bot{cfg.telegram.bot_token}/getMe"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(url)
            latency_ms = round((time.monotonic() - start) * 1000, 1)

            if resp.status_code == 200:
                data = resp.json()
                if data.get("ok"):
                    bot_info = data.get("result", {})
                    return Observation(
                        source="telegram_bot",
                        status="ok",
                        message=f"Telegram bot healthy: @{bot_info.get('username', 'unknown')}",
                        details={
                            "latency_ms": latency_ms,
                            "bot_username": bot_info.get("username"),
                            "bot_id": bot_info.get("id"),
                        },
                    )
                else:
                    return Observation(
                        source="telegram_bot",
                        status="error",
                        message=f"Telegram API returned ok=false: {data.get('description', '')}",
                        details={"latency_ms": latency_ms},
                    )
            else:
                return Observation(
                    source="telegram_bot",
                    status="error",
                    message=f"Telegram API returned HTTP {resp.status_code}",
                    details={
                        "latency_ms": latency_ms,
                        "status_code": resp.status_code,
                    },
                )

        except Exception as exc:
            return Observation(
                source="telegram_bot",
                status="error",
                message=f"Telegram bot check failed: {exc}",
                details={"exception": str(exc)},
            )

    async def collect_prometheus_metrics(self) -> Observation:
        """
        Query Prometheus for key infrastructure metrics.

        Queries a set of standard metrics:
          - API request rate (req/s)
          - Error rate (5xx responses)
          - P95 latency
          - Active connections

        If Prometheus is not configured or unreachable, returns
        a warning-level observation rather than error — Prometheus
        is a nice-to-have, not critical.
        """
        if not self._prometheus_url:
            return Observation(
                source="prometheus",
                status="warn",
                message="Prometheus URL not configured",
                details={"hint": "Set PROMETHEUS_URL environment variable"},
            )

        start = time.monotonic()
        metrics: Dict[str, Any] = {}

        # Key metrics to query
        queries = {
            "api_request_rate": 'rate(http_requests_total[5m])',
            "api_error_rate": 'rate(http_requests_total{status=~"5.."}[5m])',
            "api_p95_latency": 'histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))',
        }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                for metric_name, query in queries.items():
                    try:
                        resp = await client.get(
                            f"{self._prometheus_url}/api/v1/query",
                            params={"query": query},
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            results = data.get("data", {}).get("result", [])
                            if results:
                                metrics[metric_name] = results[0].get("value", [None, "N/A"])[1]
                            else:
                                metrics[metric_name] = "no_data"
                        else:
                            metrics[metric_name] = f"http_{resp.status_code}"
                    except Exception as exc:
                        metrics[metric_name] = f"error: {exc}"

            latency_ms = round((time.monotonic() - start) * 1000, 1)

            has_data = any(v not in ("no_data", "N/A") for v in metrics.values())
            status = "ok" if has_data else "warn"

            return Observation(
                source="prometheus",
                status=status,
                message=f"Prometheus metrics collected: {len(metrics)} queries",
                details={"latency_ms": latency_ms, "metrics": metrics},
            )

        except httpx.ConnectError:
            return Observation(
                source="prometheus",
                status="warn",
                message="Prometheus not reachable",
                details={"url": self._prometheus_url},
            )
        except Exception as exc:
            return Observation(
                source="prometheus",
                status="warn",
                message=f"Prometheus query failed: {exc}",
                details={"exception": str(exc)},
            )


# ─── Singleton ────────────────────────────────────────────────────────────────

telemetry_collector = TelemetryCollector()
