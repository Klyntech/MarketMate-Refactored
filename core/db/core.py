"""
marketmate/db/core.py
─────────────────────
MongoDB-only persistence layer with in-memory LRU cache.

Migrated from db/mongo_manager.py. This is the single shared connection
manager for all MongoDB operations — no SQLite, no reconciliation.

Components:
  1. MongoConnectionManager  — shared Motor client with auto-reconnect
  2. LRUCache                — in-memory TTL cache for hot-path queries
  3. mongo_manager singleton — one pool, one reconnect path
"""

from __future__ import annotations

import asyncio
import time
from collections import OrderedDict
from datetime import datetime, timezone
from typing import Any, Optional

from signal_engine.core.config import cfg
from signal_engine.core.logger import get_logger

log = get_logger("db.core")

try:
    from motor.motor_asyncio import AsyncIOMotorClient, AsyncIOMotorDatabase
    _MOTOR_AVAILABLE = True
except ImportError:
    _MOTOR_AVAILABLE = False
    AsyncIOMotorClient = None  # type: ignore[assignment,misc]
    AsyncIOMotorDatabase = None  # type: ignore[assignment,misc]
    log.warning("motor_not_installed",
                hint="pip install motor pymongo — MongoDB disabled system-wide")


# ═══════════════════════════════════════════════════════════════════════════════
# In-Memory LRU Cache with TTL
# ═══════════════════════════════════════════════════════════════════════════════

class LRUCache:
    """
    Thread-safe (asyncio-safe) LRU cache with per-key TTL.

    Used for hot-path queries that are called frequently but rarely change:
      - get_daily_trade_count   (changes once per signal insertion)
      - get_consecutive_losses  (changes once per trade close)
      - get_open_signals        (changes on signal open/close)

    Parameters:
      max_size : maximum number of entries before eviction
      default_ttl : default time-to-live in seconds for cache entries
    """

    def __init__(self, max_size: int = 256, default_ttl: float = 30.0) -> None:
        self._max_size = max_size
        self._default_ttl = default_ttl
        self._store: OrderedDict[str, tuple[Any, float]] = OrderedDict()
        self._lock = asyncio.Lock()

    async def get(self, key: str) -> Optional[Any]:
        """Return cached value if present and not expired, else None."""
        async with self._lock:
            entry = self._store.get(key)
            if entry is None:
                return None
            value, expires_at = entry
            if time.monotonic() > expires_at:
                # Expired — remove and return miss
                del self._store[key]
                return None
            # Move to end (most recently used)
            self._store.move_to_end(key)
            return value

    async def set(
        self,
        key: str,
        value: Any,
        ttl: Optional[float] = None,
    ) -> None:
        """Store a value with optional TTL (defaults to default_ttl)."""
        async with self._lock:
            expires_at = time.monotonic() + (ttl if ttl is not None else self._default_ttl)
            # If key already exists, remove it first so we can re-insert at end
            if key in self._store:
                del self._store[key]
            self._store[key] = (value, expires_at)
            # Evict oldest entries if over capacity
            while len(self._store) > self._max_size:
                self._store.popitem(last=False)

    async def invalidate(self, key: str) -> None:
        """Remove a specific key from the cache."""
        async with self._lock:
            self._store.pop(key, None)

    async def invalidate_prefix(self, prefix: str) -> None:
        """Remove all keys starting with the given prefix."""
        async with self._lock:
            keys_to_remove = [k for k in self._store if k.startswith(prefix)]
            for k in keys_to_remove:
                del self._store[k]

    async def clear(self) -> None:
        """Remove all entries."""
        async with self._lock:
            self._store.clear()

    @property
    def size(self) -> int:
        return len(self._store)


# ─── Shared cache instance ────────────────────────────────────────────────────
# Hot-path cache for queries that are called on every tick/scan cycle but
# whose results change infrequently (e.g. daily trade count, consecutive losses).
db_cache = LRUCache(max_size=256, default_ttl=30.0)


# ═══════════════════════════════════════════════════════════════════════════════
# MongoConnectionManager
# ═══════════════════════════════════════════════════════════════════════════════

class MongoConnectionManager:
    """
    Manages a shared AsyncIOMotorClient with auto-reconnect.

    All public methods are safe to call at any time:
      - connect()   → call once at startup
      - get_db()    → call before every collection access
      - ping()      → manual health check
      - close()     → call once at shutdown
      - status      → property for /health endpoint
    """

    # Reconnection tuning — adjust via subclass if needed
    PING_INTERVAL_S    = 60    # seconds between health pings
    BASE_BACKOFF_S     = 2     # starting backoff on failure
    MAX_BACKOFF_S      = 60    # cap for exponential backoff
    CONNECT_TIMEOUT_MS = 5_000
    SOCKET_TIMEOUT_MS  = 15_000

    def __init__(self) -> None:
        self._client:     Optional[AsyncIOMotorClient]  = None
        self._db:         Optional[AsyncIOMotorDatabase] = None
        self._connected:  bool = False
        self._enabled:    bool = _MOTOR_AVAILABLE
        self._last_ping:  Optional[datetime] = None
        self._reconnect_count: int = 0
        self._lock = asyncio.Lock()
        self._health_task: Optional[asyncio.Task] = None

    # ── Public API ────────────────────────────────────────────────────────────

    async def connect(self) -> bool:
        """
        Open the shared Motor connection and start the health-ping loop.
        Returns True on success. Safe to call multiple times — idempotent
        once connected.
        """
        if not self._enabled:
            log.warning("mongo_manager_disabled", reason="motor not installed")
            return False

        success = await self._do_connect()

        # Start the background health loop (only once)
        if success and (
            self._health_task is None or self._health_task.done()
        ):
            self._health_task = asyncio.create_task(
                self._health_loop(), name="mongo_health_ping"
            )

        return success

    async def get_db(self) -> Optional[AsyncIOMotorDatabase]:
        """
        Return the Motor database, or None when MongoDB is unavailable.

        If disconnected, attempts ONE reconnect before returning.
        Never raises — always safe to call from any context.
        """
        if not self._enabled:
            return None

        if not self._connected or self._db is None:
            # Single reconnect attempt — health loop handles sustained outages
            await self._do_connect()

        return self._db if self._connected else None

    async def ping(self) -> bool:
        """
        Send a lightweight admin ping to verify connectivity.
        Updates _connected and _last_ping in-place.
        Returns True if the server responded, False otherwise.
        """
        if not self._enabled or self._client is None:
            return False
        try:
            await self._client.admin.command(
                "ping",
                serverSelectionTimeoutMS=self.CONNECT_TIMEOUT_MS,
            )
            self._connected = True
            self._last_ping = datetime.now(timezone.utc)
            return True
        except Exception as exc:
            log.warning("mongo_ping_failed", error=str(exc))
            self._connected = False
            return False

    async def close(self) -> None:
        """
        Cancel the health loop and close the Motor client.
        Called from lifespan finally block.
        """
        if self._health_task and not self._health_task.done():
            self._health_task.cancel()
            try:
                await self._health_task
            except asyncio.CancelledError:
                pass

        if self._client:
            self._client.close()

        self._connected = False
        self._db        = None
        self._client    = None
        log.info("mongo_manager_closed")

    @property
    def status(self) -> dict:
        """
        Return a serialisable status snapshot for the /health endpoint.
        Keys: connected, enabled, reconnect_count, last_ping (ISO string).
        """
        return {
            "connected":       self._connected,
            "enabled":         self._enabled,
            "reconnect_count": self._reconnect_count,
            "last_ping":       (
                self._last_ping.isoformat()
                if self._last_ping else None
            ),
        }

    # ── Internal ──────────────────────────────────────────────────────────────

    async def _do_connect(self) -> bool:
        """
        Attempt one connection to MongoDB.
        Lock-protected so concurrent callers don't spawn multiple clients.
        """
        async with self._lock:
            # Re-check inside lock — another coroutine may have connected
            if self._connected and self._db is not None:
                return True

            if not self._enabled:
                return False

            try:
                # Close any stale client before creating a new one
                if self._client is not None:
                    try:
                        self._client.close()
                    except Exception:
                        pass

                self._client = AsyncIOMotorClient(
                    cfg.mongo.uri,
                    maxPoolSize=cfg.mongo.max_pool_size,
                    waitQueueTimeoutMS=cfg.mongo.wait_queue_timeout_ms,
                    serverSelectionTimeoutMS=cfg.mongo.server_timeout_ms,
                    connectTimeoutMS=self.CONNECT_TIMEOUT_MS,
                    socketTimeoutMS=self.SOCKET_TIMEOUT_MS,
                    retryWrites=True,
                )
                self._db = self._client[cfg.mongo.db_name]

                # Verify it's actually reachable (raises on failure)
                await self._client.admin.command(
                    "ping",
                    serverSelectionTimeoutMS=cfg.mongo.server_timeout_ms,
                )

                self._connected = True
                self._last_ping = datetime.now(timezone.utc)
                self._reconnect_count += 1

                # SECURITY: Don't log credentials from the URI.
                # Sanitize: only show scheme and hostname, never user:password
                try:
                    from urllib.parse import urlparse
                    _parsed = urlparse(cfg.mongo.uri)
                    _safe_uri = f"{_parsed.scheme}://***@{_parsed.hostname}"
                except Exception:
                    _safe_uri = cfg.mongo.uri[:10] + "...(sanitized)"

                log.info(
                    "mongo_connected",
                    db=cfg.mongo.db_name,
                    uri=_safe_uri,
                    attempt=self._reconnect_count,
                )
                return True

            except Exception as exc:
                self._connected = False
                self._db        = None
                log.warning(
                    "mongo_connect_failed",
                    error=str(exc),
                    attempt=self._reconnect_count + 1,
                    hint="MongoDB-only mode — system cannot persist data until MongoDB recovers",
                )
                return False

    async def _health_loop(self) -> None:
        """
        Background task: ping MongoDB on a fixed interval.
        On failure: exponential-backoff reconnect until success.

        Timeline example (BASE=2, MAX=60, PING=60):
          t=0    → connect()
          t=60   → ping OK
          t=120  → ping FAIL → sleep 2s → reconnect attempt
          t=122  → reconnect FAIL → sleep 4s → reconnect attempt
          t=126  → reconnect FAIL → sleep 8s → reconnect attempt
          t=134  → reconnect OK  → reset backoff → resume 60s pings
        """
        log.info("mongo_health_loop_started", ping_interval_s=self.PING_INTERVAL_S)
        backoff = self.BASE_BACKOFF_S

        while True:
            try:
                await asyncio.sleep(self.PING_INTERVAL_S)

                if not self._enabled:
                    break

                alive = await self.ping()

                if alive:
                    backoff = self.BASE_BACKOFF_S   # reset on success
                    log.debug("mongo_health_ok",
                              last_ping=self._last_ping.isoformat()
                              if self._last_ping else "n/a")
                else:
                    # Begin exponential-backoff reconnect loop
                    while not self._connected:
                        log.warning(
                            "mongo_reconnecting",
                            backoff_s=backoff,
                            reconnect_count=self._reconnect_count,
                        )
                        await asyncio.sleep(backoff)
                        success = await self._do_connect()
                        if success:
                            log.info("mongo_reconnected",
                                     reconnect_count=self._reconnect_count)
                            backoff = self.BASE_BACKOFF_S
                            break
                        backoff = min(backoff * 2, self.MAX_BACKOFF_S)

            except asyncio.CancelledError:
                log.info("mongo_health_loop_cancelled")
                break
            except Exception as exc:
                # Unexpected error in the loop itself — log and continue
                log.error("mongo_health_loop_error", error=str(exc))
                await asyncio.sleep(self.BASE_BACKOFF_S)


# ─── Singleton ────────────────────────────────────────────────────────────────
# All repositories share this single manager instance, so only one Motor
# client pool exists across the entire application.

mongo_manager = MongoConnectionManager()
