"""
marketmate/state/store.py
───────────────────────────
Dual-layer state persistence: Redis hot + MongoDB warm.

Hot layer (Redis):
  - Current InstrumentState per symbol
  - Sub-millisecond reads for API queries and MATE context
  - TTL-based expiration (default: 1 hour, refreshed on every scan)

Warm layer (MongoDB):
  - Historical state snapshots at configurable intervals
  - Time-series indexed for efficient range queries
  - Supports historical replay and ML training data generation

Cold layer (MongoDB training_data collection):
  - Aggregated statistical snapshots for model training
  - Managed by the existing training logger

New in v8.0.0 (Intelligence Infrastructure).
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.state.models import (
    InstrumentState,
    MarketStateVector,
    StateDiff,
)

log = get_logger("state_store")


# ─── Redis Hot Layer ──────────────────────────────────────────────────────────

class RedisStateStore:
    """
    Redis-backed hot storage for current instrument states.

    Stores the latest InstrumentState for each symbol as a JSON string.
    Reads are O(1) with sub-millisecond latency. TTL ensures stale
    data is automatically cleaned up if the engine stops updating.
    """

    KEY_PREFIX = "mm:state"
    MARKET_KEY = "mm:state:market"

    def __init__(self) -> None:
        self._redis = None
        self._unavailable_logged = False

    async def _get_redis(self):
        """Lazy Redis connection."""
        if self._redis is None:
            try:
                import redis.asyncio as aioredis
                if cfg.redis.url:
                    self._redis = aioredis.from_url(
                        cfg.redis.url,
                        max_connections=cfg.redis.max_connections,
                        decode_responses=True,
                    )
                    self._unavailable_logged = False
                else:
                    if not self._unavailable_logged:
                        log.info("state_store_redis_no_url", hint="Redis URL not configured — using in-memory fallback")
                        self._unavailable_logged = True
            except ImportError:
                if not self._unavailable_logged:
                    log.info("state_store_redis_not_available", hint="redis package not installed — using in-memory fallback")
                    self._unavailable_logged = True
            except Exception as exc:
                if not self._unavailable_logged:
                    log.error("state_store_redis_connection_failed", error=str(exc))
                    self._unavailable_logged = True
        return self._redis

    async def save_instrument_state(self, state: InstrumentState) -> bool:
        """Save current InstrumentState to Redis."""
        r = await self._get_redis()
        if r is None:
            return False

        try:
            key = f"{self.KEY_PREFIX}:{state.symbol}"
            value = state.model_dump_json()
            ttl = cfg.redis.default_ttl
            await r.setex(key, ttl, value)
            log.debug(
                "state_saved_to_redis",
                symbol=state.symbol,
                ttl=ttl,
                size_bytes=len(value),
            )
            return True
        except Exception as exc:
            log.error("state_save_redis_failed", symbol=state.symbol, error=str(exc))
            return False

    async def load_instrument_state(self, symbol: str) -> Optional[InstrumentState]:
        """Load current InstrumentState from Redis."""
        r = await self._get_redis()
        if r is None:
            return None

        try:
            key = f"{self.KEY_PREFIX}:{symbol}"
            value = await r.get(key)
            if value is None:
                return None
            return InstrumentState.model_validate_json(value)
        except Exception as exc:
            log.error("state_load_redis_failed", symbol=symbol, error=str(exc))
            return None

    async def save_market_state(self, state: MarketStateVector) -> bool:
        """Save the complete MarketStateVector to Redis."""
        r = await self._get_redis()
        if r is None:
            return False

        try:
            value = state.model_dump_json()
            ttl = cfg.redis.default_ttl
            await r.setex(self.MARKET_KEY, ttl, value)
            return True
        except Exception as exc:
            log.error("market_state_save_redis_failed", error=str(exc))
            return False

    async def load_market_state(self) -> Optional[MarketStateVector]:
        """Load the complete MarketStateVector from Redis."""
        r = await self._get_redis()
        if r is None:
            return None

        try:
            value = await r.get(self.MARKET_KEY)
            if value is None:
                return None
            return MarketStateVector.model_validate_json(value)
        except Exception as exc:
            log.error("market_state_load_redis_failed", error=str(exc))
            return None

    async def save_state_diff(self, diff: StateDiff) -> bool:
        """Save a StateDiff to Redis (recent diffs per symbol)."""
        r = await self._get_redis()
        if r is None:
            return False

        try:
            key = f"{self.KEY_PREFIX}:diffs:{diff.symbol}"
            value = diff.model_dump_json()
            # Keep last 50 diffs per symbol as a Redis list
            await r.lpush(key, value)
            await r.ltrim(key, 0, 49)
            await r.expire(key, cfg.redis.default_ttl)
            return True
        except Exception as exc:
            log.error("state_diff_save_redis_failed", symbol=diff.symbol, error=str(exc))
            return False


# ─── MongoDB Warm Layer ───────────────────────────────────────────────────────

class MongoStateStore:
    """
    MongoDB-backed warm storage for historical state snapshots.

    Stores InstrumentState snapshots at configurable intervals
    (default: every 15 minutes during active sessions, hourly otherwise).
    Time-series indexed for efficient range queries.
    """

    COLLECTION_SNAPSHOTS = "state_snapshots"
    COLLECTION_DIFFS = "state_diffs"

    def __init__(self) -> None:
        self._db = None

    async def _get_db(self):
        """Lazy MongoDB connection."""
        if self._db is None:
            try:
                from marketmate.db.core import mongo_manager
                self._db = await mongo_manager.get_db()
            except Exception as exc:
                log.error("state_store_mongo_connection_failed", error=str(exc))
        return self._db

    async def save_snapshot(self, state: InstrumentState) -> bool:
        """Save an InstrumentState snapshot to MongoDB."""
        db = await self._get_db()
        if db is None:
            return False

        try:
            collection = db[self.COLLECTION_SNAPSHOTS]
            doc = state.model_dump()
            # Convert datetime objects to ISO strings for MongoDB
            doc["_saved_at"] = datetime.now(timezone.utc)
            await collection.insert_one(doc)

            # Create time-series index if not exists
            await collection.create_index([("symbol", 1), ("last_scan_at", -1)])
            log.debug("state_snapshot_saved_mongo", symbol=state.symbol)
            return True
        except Exception as exc:
            log.error("state_snapshot_save_mongo_failed", symbol=state.symbol, error=str(exc))
            return False

    async def save_state_diff(self, diff: StateDiff) -> bool:
        """Save a StateDiff to MongoDB."""
        db = await self._get_db()
        if db is None:
            return False

        try:
            collection = db[self.COLLECTION_DIFFS]
            doc = diff.model_dump()
            doc["_saved_at"] = datetime.now(timezone.utc)
            await collection.insert_one(doc)

            # Create index on symbol + timestamp
            await collection.create_index([("symbol", 1), ("timestamp", -1)])
            log.debug("state_diff_saved_mongo", symbol=diff.symbol,
                       material=diff.has_material_change)
            return True
        except Exception as exc:
            log.error("state_diff_save_mongo_failed", symbol=diff.symbol, error=str(exc))
            return False

    async def load_historical_states(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        limit: int = 100,
    ) -> List[InstrumentState]:
        """
        Load historical InstrumentState snapshots from MongoDB.

        Args:
            symbol: Instrument symbol
            start: Start of time range
            end: End of time range
            limit: Maximum number of snapshots to return

        Returns:
            List of InstrumentState objects, newest first
        """
        db = await self._get_db()
        if db is None:
            return []

        try:
            collection = db[self.COLLECTION_SNAPSHOTS]
            query = {
                "symbol": symbol,
                "last_scan_at": {"$gte": start, "$lte": end},
            }
            cursor = collection.find(query).sort("last_scan_at", -1).limit(limit)
            results = []
            async for doc in cursor:
                doc.pop("_id", None)
                doc.pop("_saved_at", None)
                try:
                    results.append(InstrumentState.model_validate(doc))
                except Exception:
                    pass  # Skip malformed docs
            return results
        except Exception as exc:
            log.error("state_history_load_mongo_failed", symbol=symbol, error=str(exc))
            return []


# ─── Composite Store ──────────────────────────────────────────────────────────

class StateStore:
    """
    Dual-layer state store combining Redis hot + MongoDB warm.

    Provides a single interface for state persistence with
    automatic layer selection based on operation type.
    """

    def __init__(self) -> None:
        self.redis = RedisStateStore()
        self.mongo = MongoStateStore()

    async def save_current_state(self, state: InstrumentState) -> None:
        """Save current state to both layers."""
        # Always save to Redis (hot layer)
        await self.redis.save_instrument_state(state)
        # MongoDB (warm layer) is saved at intervals, not on every scan

    async def load_current_state(self, symbol: str) -> Optional[InstrumentState]:
        """Load current state from Redis (hot layer)."""
        return await self.redis.load_instrument_state(symbol)

    async def save_market_state(self, state: MarketStateVector) -> None:
        """Save complete market state to Redis."""
        await self.redis.save_market_state(state)

    async def load_market_state(self) -> Optional[MarketStateVector]:
        """Load complete market state from Redis."""
        return await self.redis.load_market_state()

    async def save_snapshot(self, state: InstrumentState) -> None:
        """Save a state snapshot to MongoDB (warm layer)."""
        await self.mongo.save_snapshot(state)

    async def save_diff(self, diff: StateDiff) -> None:
        """Save a state diff to both layers."""
        await self.redis.save_state_diff(diff)
        if diff.has_material_change:
            await self.mongo.save_state_diff(diff)

    async def load_historical_states(
        self,
        symbol: str,
        start: datetime,
        end: datetime,
        limit: int = 100,
    ) -> List[InstrumentState]:
        """Load historical state snapshots from MongoDB."""
        return await self.mongo.load_historical_states(symbol, start, end, limit)


# ─── Singleton ────────────────────────────────────────────────────────────────

_state_store: Optional[StateStore] = None


def get_state_store() -> StateStore:
    """Get or create the singleton StateStore."""
    global _state_store
    if _state_store is None:
        _state_store = StateStore()
    return _state_store
