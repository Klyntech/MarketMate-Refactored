"""
marketmate/data/cache.py
────────────────────────
MongoDB-backed OHLCV candle cache with freshness sentinel.

Migrated from ``data/candle_store.py`` into the ``marketmate.data`` package.
All imports updated to use ``marketmate.`` prefix.

Architecture
────────────
  get_candles()          <- public entry point for all consumers
      |
      +- MongoDB hit?  -> return DataFrame instantly (no API call)
      |
      +- cache miss   -> fetch via engine -> store in MongoDB -> return DataFrame

Collection: ``candles``
Document schema:
  symbol      str       e.g. "XAUUSD"
  interval    str       "1d" | "4h" | "15m" | "5m" | ...
  timestamp   ISODate   candle open time (UTC)
  open        double
  high        double
  low         double
  close       double
  volume      double
  source      str       "twelve_data" | "binance" | "alpha_vantage" | "api" | "live"
  fetched_at  ISODate   wall-clock time this row was stored

Indexes:
  Unique compound  { symbol, interval, timestamp } -- deduplication + range speed
  TTL              { timestamp }  expireAfterSeconds = 94_608_000  (3 years)

Candle Freshness Sentinel (Phase 1 Enhancement):
  Checks the age of the most recent candle per (symbol, interval) before
  returning cached data. If the most recent candle is stale beyond a
  configurable threshold, the cache is bypassed and fresh data is fetched.
"""

from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Optional

import pandas as pd
from pymongo import ASCENDING

from marketmate.core.logger import get_logger

log = get_logger("data.cache")

# 3 years in seconds
_TTL_SECONDS = 3 * 365 * 24 * 60 * 60  # 94_608_000

# Guard flag: once indexes are created, skip the Atlas round-trip on every call.
_indexes_created = False

# ─── Phase 1: Candle Freshness Sentinel ──────────────────────────────────────
# Maximum age of the most recent candle before cache is considered stale.
# Prevents the system from using data that no longer reflects market reality
# after deployments, API outages, or long periods of inactivity.
FRESHNESS_THRESHOLDS: dict[str, timedelta] = {
    # Two full 4H bars missed = definitely stale
    "4h":  timedelta(hours=8),
    # 30 minutes = 6 x 5M bars missed — enough to miss a whole setup
    "5m":  timedelta(minutes=30),
    # 30 minutes = 2 x 15M bars missed
    "15m": timedelta(minutes=30),
    # 1D: allow up to 28 hours (covers a full day + small buffer)
    "1d":  timedelta(hours=28),
    # 1H: 3 hours = 3 bars missed
    "1h":  timedelta(hours=3),
}

# Default freshness threshold for intervals not listed above
DEFAULT_FRESHNESS = timedelta(hours=2)


def _get_freshness_threshold(interval: str) -> timedelta:
    """Return the staleness threshold for the given interval."""
    return FRESHNESS_THRESHOLDS.get(interval, DEFAULT_FRESHNESS)


def _is_stale(docs: list[dict], interval: str) -> bool:
    """
    Check whether the most recent candle in a list of documents is stale.

    A candle is stale if its ``fetched_at`` (or ``timestamp`` as fallback)
    is older than the freshness threshold for that interval.

    Returns True if the data should be considered stale and bypassed.
    """
    if not docs:
        return True

    now = datetime.now(timezone.utc)
    threshold = _get_freshness_threshold(interval)

    # Use fetched_at (wall-clock time when data was stored) for freshness,
    # falling back to the candle timestamp itself if fetched_at is missing.
    most_recent = docs[-1]
    ts = most_recent.get("fetched_at") or most_recent.get("timestamp")

    if ts is None:
        return True

    # Ensure timezone-aware
    if hasattr(ts, "to_pydatetime"):
        ts = ts.to_pydatetime()
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)

    age = now - ts
    is_stale = age > threshold

    if is_stale:
        log.warning(
            "candle_cache_stale",
            interval=interval,
            age_minutes=round(age.total_seconds() / 60, 1),
            threshold_minutes=round(threshold.total_seconds() / 60, 1),
            hint="Bypassing stale cache — fetching fresh data from API",
        )

    return is_stale


# ─── Internal helpers ────────────────────────────────────────────────────────

async def _get_col(mongo_manager):
    """Return the Motor candles collection, or None when MongoDB is unavailable."""
    try:
        db = await mongo_manager.get_db()
        return db["candles"] if db is not None else None
    except Exception as exc:
        log.warning("candle_store_col_unavailable", error=str(exc))
        return None


async def _ensure_indexes(col) -> None:
    """Create indexes on first use. Skipped after the first successful call."""
    global _indexes_created
    if _indexes_created:
        return
    try:
        # Unique compound index: deduplication + fast range queries
        await col.create_index(
            [("symbol", ASCENDING), ("interval", ASCENDING), ("timestamp", ASCENDING)],
            unique=True,
            name="symbol_interval_timestamp_unique",
        )
        # TTL index: auto-expire candles older than 3 years
        await col.create_index(
            [("timestamp", ASCENDING)],
            expireAfterSeconds=_TTL_SECONDS,
            name="candle_ttl_3yr",
        )
        _indexes_created = True
        log.debug("candle_indexes_ensured")
    except Exception as exc:
        log.warning("candle_index_warning", error=str(exc))


def _df_to_docs(df: pd.DataFrame, symbol: str, interval: str, source: str) -> list[dict]:
    """Convert a validated OHLCV DataFrame into a list of MongoDB documents."""
    now = datetime.now(timezone.utc)
    docs = []
    for row in df.itertuples(index=False):
        ts = row.timestamp
        # Ensure timezone-aware datetime for MongoDB
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        docs.append({
            "symbol":     symbol,
            "interval":   interval,
            "timestamp":  ts,
            "open":       float(row.open),
            "high":       float(row.high),
            "low":        float(row.low),
            "close":      float(row.close),
            "volume":     float(row.volume),
            "source":     source,
            "fetched_at": now,
        })
    return docs


async def _store_candles(col, docs: list[dict]) -> int:
    """
    Upsert candle documents into MongoDB.
    Uses update_one with $setOnInsert so that existing candles are never
    overwritten -- the unique index is the deduplication guard.
    Returns the number of new candles inserted.

    If the MongoClient has been closed (e.g. during shutdown), the loop
    aborts early to avoid a flood of identical warnings.
    """
    if not docs:
        return 0
    inserted = 0
    client_closed = False
    for doc in docs:
        try:
            result = await col.update_one(
                {
                    "symbol":    doc["symbol"],
                    "interval":  doc["interval"],
                    "timestamp": doc["timestamp"],
                },
                {"$setOnInsert": doc},
                upsert=True,
            )
            if result.upserted_id is not None:
                inserted += 1
        except Exception as exc:
            err_msg = str(exc)
            log.warning("candle_store_insert_failed",
                        symbol=doc["symbol"], ts=str(doc["timestamp"]), error=err_msg)
            # Abort early if MongoClient was closed during shutdown
            if "after close" in err_msg.lower():
                client_closed = True
                break
    if client_closed:
        log.warning("candle_store_aborted", reason="MongoClient closed — skipping remaining inserts")
    return inserted


def _docs_to_df(docs: list[dict]) -> pd.DataFrame:
    """Convert a list of MongoDB candle documents into a clean DataFrame."""
    rows = []
    for d in docs:
        ts = d["timestamp"]
        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)
        rows.append({
            "timestamp": pd.Timestamp(ts),
            "open":      float(d["open"]),
            "high":      float(d["high"]),
            "low":       float(d["low"]),
            "close":     float(d["close"]),
            "volume":    float(d["volume"]),
        })
    df = pd.DataFrame(rows).sort_values("timestamp").reset_index(drop=True)
    return df


# ─── Public API ──────────────────────────────────────────────────────────────

async def get_candles(
    symbol: str,
    interval: str,
    mongo_manager,
    fetch_fn,
    limit: Optional[int] = None,
    start_ts: Optional[datetime] = None,
    end_ts: Optional[datetime] = None,
) -> pd.DataFrame:
    """
    Return OHLCV candles as a DataFrame. MongoDB is checked first; the API
    is called only when the cache doesn't have enough data.

    If the cached data is stale (most recent candle is too old for the given
    interval), the cache is bypassed and fresh data is fetched from the API.

    Args:
        symbol:        Canonical symbol, e.g. "XAUUSD".
        interval:      Candle interval -- "1d", "4h", "15m", "5m", etc.
        mongo_manager: MongoConnectionManager instance for DB access.
        fetch_fn:      Async callable(symbol, interval, limit) -> DataFrame
                       Used as the API fallback when cache misses.
        limit:         Maximum number of most-recent candles to return.
        start_ts:      Inclusive start of date range (UTC-aware datetime).
        end_ts:        Inclusive end of date range (UTC-aware datetime).

    Returns:
        DataFrame with columns [timestamp, open, high, low, close, volume].
        Falls back gracefully to a direct API call if MongoDB is unavailable.
    """
    col = await _get_col(mongo_manager)

    # ── Try MongoDB first ────────────────────────────────────────────────────
    if col is not None:
        await _ensure_indexes(col)
        query: dict = {"symbol": symbol, "interval": interval}

        if start_ts is not None or end_ts is not None:
            ts_filter: dict = {}
            if start_ts is not None:
                if start_ts.tzinfo is None:
                    start_ts = start_ts.replace(tzinfo=timezone.utc)
                ts_filter["$gte"] = start_ts
            if end_ts is not None:
                if end_ts.tzinfo is None:
                    end_ts = end_ts.replace(tzinfo=timezone.utc)
                ts_filter["$lte"] = end_ts
            query["timestamp"] = ts_filter

        try:
            if limit is not None and start_ts is None and end_ts is None:
                # For limit-only queries, grab the most recent N candles
                cursor = col.find(query, {"_id": 0}) \
                             .sort("timestamp", -1) \
                             .limit(limit)
                docs = await cursor.to_list(length=limit)
                docs = list(reversed(docs))  # restore chronological order
            else:
                cursor = col.find(query, {"_id": 0}).sort("timestamp", ASCENDING)
                docs = await cursor.to_list(length=100_000)

            enough = (
                (limit is not None and len(docs) >= limit) or
                (start_ts is not None and len(docs) > 0)
            )

            # ── Freshness Sentinel ──────────────────────────────────────────
            # Even if we have enough cached candles, check if the most recent
            # one is stale. If so, bypass the cache and fetch fresh data.
            if enough and not _is_stale(docs, interval):
                log.info("candle_cache_hit",
                         symbol=symbol, interval=interval, count=len(docs))
                return _docs_to_df(docs)

            if enough and _is_stale(docs, interval):
                # Cache hit but stale — force a fresh fetch
                log.info("candle_cache_stale_bypass",
                         symbol=symbol, interval=interval,
                         cached=len(docs), action="fetching_fresh_data")
            else:
                log.info("candle_cache_miss",
                         symbol=symbol, interval=interval,
                         cached=len(docs), requested=limit)

        except Exception as exc:
            log.warning("candle_store_read_failed", error=str(exc))

    # ── API fallback ─────────────────────────────────────────────────────────
    fetch_limit = limit or 500
    log.info("candle_fetching_from_api",
             symbol=symbol, interval=interval, limit=fetch_limit)
    df = await fetch_fn(symbol, interval, fetch_limit)

    # ── Store newly fetched candles ──────────────────────────────────────────
    if col is not None and not df.empty:
        docs = _df_to_docs(df, symbol, interval, source="api")
        inserted = await _store_candles(col, docs)
        log.info("candle_cache_populated",
                 symbol=symbol, interval=interval,
                 fetched=len(docs), new=inserted)

    return df


async def store_live_candles(
    symbol: str,
    dataframes: dict[str, pd.DataFrame],
    mongo_manager,
) -> None:
    """
    Persist freshly fetched candles from a live scan into MongoDB.

    Called fire-and-forget from GateRunner after each asyncio.gather so
    the candle warehouse grows with every 5-minute scan cycle at zero
    extra API cost.

    Args:
        symbol:        Canonical symbol, e.g. "XAUUSD".
        dataframes:    Mapping of interval -> DataFrame for whichever timeframes
                       the scan successfully fetched (1 to 4 entries).
                       None or empty DataFrames are silently skipped.
        mongo_manager: MongoConnectionManager instance for DB access.

    Never raises -- any failure is logged as a warning so the gate scan
    that called this is never delayed or interrupted.
    """
    col = await _get_col(mongo_manager)
    if col is None:
        return
    await _ensure_indexes(col)
    for interval, df in dataframes.items():
        if df is None or df.empty:
            continue
        try:
            docs = _df_to_docs(df, symbol, interval, source="live")
            inserted = await _store_candles(col, docs)
            log.debug("live_candles_stored",
                      symbol=symbol, interval=interval,
                      total=len(docs), new=inserted)
        except Exception as exc:
            log.warning("live_store_failed",
                        symbol=symbol, interval=interval, error=str(exc))


async def warm_cache(
    symbol: str,
    intervals: list[str],
    mongo_manager,
    fetch_fn,
    limit: int = 500,
) -> None:
    """
    Pre-populate the candle cache for a symbol across multiple intervals.
    Call once on startup or before a batch backtest run.

    Args:
        symbol:        Canonical symbol, e.g. "XAUUSD".
        intervals:     List of timeframes to warm, e.g. ["1d", "4h", "15m"].
        mongo_manager: MongoConnectionManager instance for DB access.
        fetch_fn:      Async callable(symbol, interval, limit) -> DataFrame.
        limit:         Number of candles to fetch per interval.

    Example:
        await warm_cache("XAUUSD", ["1d", "4h", "15m", "5m"], mongo_mgr, engine.fetch_candles)
    """
    for interval in intervals:
        try:
            df = await get_candles(
                symbol, interval, mongo_manager, fetch_fn, limit=limit,
            )
            log.info("cache_warmed",
                     symbol=symbol, interval=interval, candles=len(df))
        except Exception as exc:
            log.warning("cache_warm_failed",
                        symbol=symbol, interval=interval, error=str(exc))


async def check_candle_freshness(
    symbol: str,
    interval: str,
    mongo_manager,
) -> Optional[dict]:
    """
    Public API for checking candle freshness without fetching data.

    Returns a dict with freshness info, or None if MongoDB is unavailable.
    Useful for diagnostics, health checks, and admin alerts.

    Example return:
        {
            "symbol": "XAUUSD",
            "interval": "4h",
            "last_candle_age_minutes": 12.5,
            "threshold_minutes": 480.0,
            "is_stale": False,
        }
    """
    col = await _get_col(mongo_manager)
    if col is None:
        return None

    try:
        # Find the most recent candle
        doc = await col.find_one(
            {"symbol": symbol, "interval": interval},
            sort=[("timestamp", -1)],
        )
        if doc is None:
            return {
                "symbol": symbol,
                "interval": interval,
                "last_candle_age_minutes": None,
                "threshold_minutes": _get_freshness_threshold(interval).total_seconds() / 60,
                "is_stale": True,
                "hint": "No candles found in cache",
            }

        ts = doc.get("fetched_at") or doc.get("timestamp")
        if ts is None:
            return None

        if hasattr(ts, "to_pydatetime"):
            ts = ts.to_pydatetime()
        if ts.tzinfo is None:
            ts = ts.replace(tzinfo=timezone.utc)

        age = datetime.now(timezone.utc) - ts
        threshold = _get_freshness_threshold(interval)

        return {
            "symbol": symbol,
            "interval": interval,
            "last_candle_age_minutes": round(age.total_seconds() / 60, 1),
            "threshold_minutes": round(threshold.total_seconds() / 60, 1),
            "is_stale": age > threshold,
        }
    except Exception as exc:
        log.warning("freshness_check_failed",
                    symbol=symbol, interval=interval, error=str(exc))
        return None


async def connect(mongo_manager) -> None:
    """
    Create indexes on the candles collection at startup.
    Called from db.connect_all() so indexes are ready before any scans.
    Safe to call repeatedly -- MongoDB create_index is idempotent.
    """
    col = await _get_col(mongo_manager)
    if col is not None:
        await _ensure_indexes(col)
        log.info("candle_store_db_ready", collection="candles")
