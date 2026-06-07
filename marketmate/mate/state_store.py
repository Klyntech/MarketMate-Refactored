"""
marketmate.mate.state_store
────────────────────────────
Redis-backed compiled state store for the MATE Intelligence Layer.

Stores precomputed state in Redis so the LLM never has to query
raw databases. Each key is a JSON document containing the compiled
state for a specific domain (symbol, account, performance).

Redis Schema:
  state:symbol:{symbol}     — per-symbol trading state (bias, last signal, etc.)
  signal:active:{symbol}    — active/open signal for a symbol
  account:state             — virtual account state (balance, metrics)
  event:last_id             — last processed event ID (for incremental updates)
  perf:winrate:7d           — 7-day win rate (decimal)
  perf:winrate:30d          — 30-day win rate (decimal)
  perf:avg_rr:7d            — 7-day average R-multiple
  perf:avg_rr:30d           — 30-day average R-multiple
  perf:total_trades:7d      — 7-day total trades
  perf:total_trades:30d     — 30-day total trades
  perf:profit_factor:7d     — 7-day profit factor
  perf:profit_factor:30d    — 30-day profit factor
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from marketmate.core.logger import get_logger

log = get_logger("mate.state_store")

try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False


class RedisStateStore:
    """
    Redis-backed compiled state store.

    All state is stored as JSON strings in Redis with TTL.
    The MATE layer reads from this store exclusively —
    never from raw MongoDB collections.
    """

    def __init__(self) -> None:
        self._client: Optional[Any] = None
        self._enabled: bool = False

    async def connect(self) -> bool:
        """
        Connect to Redis using REDIS_URL environment variable.

        Falls back to in-memory dict if Redis is unavailable.
        """
        import os
        redis_url = os.getenv("REDIS_URL", "")

        if not redis_url or not _REDIS_AVAILABLE:
            log.info(
                "redis_state_disabled",
                reason="REDIS_URL not set or redis package not installed",
                hint="Falling back to in-memory state store",
            )
            self._fallback = {}
            return False

        try:
            self._client = aioredis.from_url(
                redis_url,
                encoding="utf-8",
                decode_responses=True,
                max_connections=5,
            )
            await self._client.ping()
            self._enabled = True
            log.info("redis_state_connected", url_prefix=redis_url[:20] + "...")
            return True
        except Exception as exc:
            log.warning("redis_state_connect_failed", error=str(exc))
            self._fallback = {}
            return False

    async def close(self) -> None:
        """Close the Redis connection."""
        if self._client:
            await self._client.close()
        self._enabled = False

    # ═════════════════════════════════════════════════════════════════════════
    # Read Operations
    # ═════════════════════════════════════════════════════════════════════════

    async def get(self, key: str) -> Optional[Dict[str, Any]]:
        """Get a compiled state value by key."""
        try:
            if self._enabled and self._client:
                value = await self._client.get(key)
                if value:
                    return json.loads(value)
                return None
            else:
                return self._fallback.get(key)
        except Exception as exc:
            log.warning("redis_state_get_failed", key=key, error=str(exc))
            return self._fallback.get(key) if hasattr(self, '_fallback') else None

    async def set(
        self,
        key: str,
        value: Dict[str, Any],
        ttl_seconds: int = 3600,
    ) -> None:
        """Set a compiled state value with TTL."""
        try:
            serialized = json.dumps(value, default=str)
            if self._enabled and self._client:
                await self._client.set(key, serialized, ex=ttl_seconds)
            else:
                self._fallback[key] = value
        except Exception as exc:
            log.warning("redis_state_set_failed", key=key, error=str(exc))
            if hasattr(self, '_fallback'):
                self._fallback[key] = value

    async def delete(self, key: str) -> None:
        """Delete a key."""
        try:
            if self._enabled and self._client:
                await self._client.delete(key)
            elif hasattr(self, '_fallback'):
                self._fallback.pop(key, None)
        except Exception as exc:
            log.warning("redis_state_delete_failed", key=key, error=str(exc))

    # ═════════════════════════════════════════════════════════════════════════
    # Convenience Methods — Symbol State
    # ═════════════════════════════════════════════════════════════════════════

    async def get_symbol_state(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get compiled state for a symbol."""
        return await self.get(f"state:symbol:{symbol}")

    async def set_symbol_state(self, symbol: str, state: Dict[str, Any]) -> None:
        """Set compiled state for a symbol."""
        await self.set(f"state:symbol:{symbol}", state, ttl_seconds=600)

    async def get_active_signal(self, symbol: str) -> Optional[Dict[str, Any]]:
        """Get the active signal for a symbol."""
        return await self.get(f"signal:active:{symbol}")

    async def set_active_signal(self, symbol: str, signal: Dict[str, Any]) -> None:
        """Set the active signal for a symbol."""
        await self.set(f"signal:active:{symbol}", signal, ttl_seconds=1800)

    async def remove_active_signal(self, symbol: str) -> None:
        """Remove the active signal for a symbol (trade closed)."""
        await self.delete(f"signal:active:{symbol}")

    # ═════════════════════════════════════════════════════════════════════════
    # Convenience Methods — Account State
    # ═════════════════════════════════════════════════════════════════════════

    async def get_account_state(self) -> Optional[Dict[str, Any]]:
        """Get compiled virtual account state."""
        return await self.get("account:state")

    async def set_account_state(self, state: Dict[str, Any]) -> None:
        """Set compiled virtual account state."""
        await self.set("account:state", state, ttl_seconds=300)

    # ═════════════════════════════════════════════════════════════════════════
    # Convenience Methods — Performance Metrics
    # ═════════════════════════════════════════════════════════════════════════

    async def get_perf(self, metric: str, window: str = "30d") -> Optional[Any]:
        """Get a performance metric (e.g. winrate, avg_rr)."""
        value = await self.get(f"perf:{metric}:{window}")
        return value

    async def set_perf(
        self, metric: str, window: str, value: Any
    ) -> None:
        """Set a performance metric."""
        await self.set(
            f"perf:{metric}:{window}",
            {"value": value, "updated_at": datetime.now(timezone.utc).isoformat()},
            ttl_seconds=3600,
        )

    # ═════════════════════════════════════════════════════════════════════════
    # Event Tracking
    # ═════════════════════════════════════════════════════════════════════════

    async def get_last_event_id(self) -> Optional[str]:
        """Get the last processed event ID."""
        result = await self.get("event:last_id")
        return result.get("id") if result else None

    async def set_last_event_id(self, event_id: str) -> None:
        """Set the last processed event ID."""
        await self.set("event:last_id", {"id": event_id}, ttl_seconds=86400)


# ─── Singleton ────────────────────────────────────────────────────────────────

redis_state_store = RedisStateStore()
