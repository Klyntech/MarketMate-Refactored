"""
marketmate/data/engine.py
─────────────────────────
Unified market data manager with provider priority system.

MarketDataEngine is the single entry point for all OHLCV data access
in the new architecture. It:

  1. Manages a priority-ordered list of data providers
  2. Automatically selects the best provider for each request
  3. Handles provider fallback gracefully (try next provider if current fails)
  4. Integrates caching via the CandleCache layer
  5. Validates all data before returning
  6. Normalizes outputs for consistent downstream consumption

Provider Selection Logic
────────────────────────
  - Providers with **native** support for the requested timeframe are
    preferred (lower effective priority number).
  - Providers that require resampling are deprioritized but still usable.
  - Providers that cannot serve the symbol at all are excluded.
  - If all providers fail, a RuntimeError is raised.

Migration Note
──────────────
The legacy ``fetch_ohlcv()`` function signature is preserved as a
module-level convenience function for backward compatibility during
migration. New code should use ``MarketDataEngine.fetch_candles()``
directly.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

import pandas as pd

from signal_engine.core.config import cfg
from signal_engine.core.logger import get_logger
from signal_engine.data.providers.base import DataProvider
from signal_engine.data.providers import get_available_providers
from signal_engine.data.validators import validate_ohlcv, validate_freshness
from signal_engine.data.transformers import (
    resample_candles,
    normalize_outputs,
    handle_timezone,
)
from signal_engine.data import cache as candle_cache

log = get_logger("data.engine")


class MarketDataEngine:
    """
    Unified market data manager with provider priority and caching.

    Initialized with the application config and a MongoConnectionManager
    instance. All data access flows through this engine.

    Usage:
        engine = MarketDataEngine(config=cfg, mongo_manager=mongo_mgr)
        df = await engine.fetch_candles("XAUUSD", "4h", limit=250)
    """

    def __init__(
        self,
        config=None,
        mongo_manager=None,
    ) -> None:
        """
        Initialize the MarketDataEngine.

        Args:
            config:         Application Config object (defaults to ``cfg``).
            mongo_manager:  MongoConnectionManager instance for caching.
                            If None, caching is disabled and all requests
                            go directly to providers.
        """
        self._config = config or cfg
        self._mongo_manager = mongo_manager

        # Instantiate all available providers, sorted by priority
        self._providers: list[DataProvider] = get_available_providers()
        log.info(
            "engine_initialized",
            providers=[p.name for p in self._providers],
            mongo_enabled=mongo_manager is not None,
        )

    # ── Core fetch ────────────────────────────────────────────────────────

    async def fetch_candles(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candles with automatic provider selection and fallback.

        Provider selection:
          1. Filter providers that can serve the symbol
          2. Sort: native timeframe support first, then by priority
          3. Try each provider in order; fall back on failure
          4. Validate the result before returning

        Args:
            symbol:    Canonical symbol, e.g. "XAUUSD", "BTCUSDT".
            timeframe: Candle interval, e.g. "4h", "15m", "1d".
            limit:     Maximum number of candles to return.

        Returns:
            Validated, normalized DataFrame with columns
            [timestamp, open, high, low, close, volume].

        Raises:
            RuntimeError: If all providers fail.
        """
        # ── Try cache first ────────────────────────────────────────────────
        if self._mongo_manager is not None:
            try:
                df = await candle_cache.get_candles(
                    symbol=symbol,
                    interval=timeframe,
                    mongo_manager=self._mongo_manager,
                    fetch_fn=self._fetch_from_providers,
                    limit=limit,
                )
                if df is not None and not df.empty:
                    return self.normalize_outputs(df)
            except Exception as exc:
                log.warning(
                    "cache_read_failed",
                    symbol=symbol,
                    timeframe=timeframe,
                    error=str(exc),
                )

        # ── Direct provider fetch (cache miss or disabled) ─────────────────
        df = await self._fetch_from_providers(symbol, timeframe, limit)
        return self.normalize_outputs(df)

    async def _fetch_from_providers(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> pd.DataFrame:
        """
        Try each provider in priority order until one succeeds.

        Provider selection prefers:
          1. Providers with native timeframe support (no resampling needed)
          2. Providers that can resample from a native timeframe
          3. Lower priority number within each tier

        Returns a validated DataFrame or raises RuntimeError.
        """
        # ── Classify providers ────────────────────────────────────────────
        native_providers = []
        resample_providers = []

        for provider in self._providers:
            if not provider.can_serve(symbol, timeframe):
                continue

            if provider.supports_timeframe(timeframe):
                native_providers.append(provider)
            else:
                # Provider can serve the symbol but not the timeframe natively
                # — check if resampling is possible
                resample_providers.append(provider)

        # Sort each tier by priority (lower = higher preference)
        native_providers.sort(key=lambda p: p.priority)
        resample_providers.sort(key=lambda p: p.priority)

        # Build ordered provider list: native first, then resample
        ordered = native_providers + resample_providers

        if not ordered:
            raise RuntimeError(
                f"No data providers available for {symbol}/{timeframe}"
            )

        log.debug(
            "provider_selection",
            symbol=symbol,
            timeframe=timeframe,
            native=[p.name for p in native_providers],
            resample=[p.name for p in resample_providers],
        )

        # ── Try each provider ─────────────────────────────────────────────
        last_error: Optional[Exception] = None

        for provider in ordered:
            try:
                needs_resample = not provider.supports_timeframe(timeframe)

                # Determine the fetch timeframe (may differ from requested)
                fetch_tf = self._get_fetch_timeframe(provider, timeframe)
                if fetch_tf is None:
                    log.debug(
                        "provider_cannot_serve_timeframe",
                        provider=provider.name,
                        timeframe=timeframe,
                    )
                    continue

                # Fetch from provider
                df = await provider.fetch(symbol, fetch_tf, limit)

                # Resample if needed
                if needs_resample and fetch_tf != timeframe:
                    log.debug(
                        "resampling_from_provider",
                        provider=provider.name,
                        from_tf=fetch_tf,
                        to_tf=timeframe,
                        candles_in=len(df),
                    )
                    df = self.resample_candles(df, timeframe, source_tf=fetch_tf)
                    # Trim to requested limit after resampling
                    df = df.tail(limit).reset_index(drop=True)

                # Validate
                df = validate_ohlcv(df, symbol, timeframe)

                log.info(
                    "provider_succeeded",
                    provider=provider.name,
                    symbol=symbol,
                    timeframe=timeframe,
                    candles=len(df),
                    resampled=needs_resample,
                )
                return df

            except Exception as exc:
                log.warning(
                    "provider_failed",
                    provider=provider.name,
                    symbol=symbol,
                    timeframe=timeframe,
                    error=str(exc),
                )
                last_error = exc

        raise RuntimeError(
            f"All data providers failed for {symbol}/{timeframe}. "
            f"Last error: {last_error}"
        )

    def _get_fetch_timeframe(
        self,
        provider: DataProvider,
        target_timeframe: str,
    ) -> Optional[str]:
        """
        Determine the timeframe to actually fetch from a provider.

        If the provider natively supports the target timeframe, return it
        directly. Otherwise, find the best native timeframe to resample from.

        Returns None if no suitable timeframe can be found.
        """
        if provider.supports_timeframe(target_timeframe):
            return target_timeframe

        # Try to find a smaller timeframe to resample from
        # Resample mapping: target -> source
        resample_map = {
            "4h": ["1h"],    # 4h from 1h
            "1h": ["15m"],   # 1h from 15m
            "15m": ["5m"],   # 15m from 5m
            "5m": ["1m"],    # 5m from 1m
        }

        source_options = resample_map.get(target_timeframe, [])
        for source_tf in source_options:
            if provider.supports_timeframe(source_tf):
                return source_tf

        return None

    # ── Validation ────────────────────────────────────────────────────────

    def validate_freshness(
        self,
        df: pd.DataFrame,
        max_age: Optional[float] = None,
    ) -> bool:
        """
        Check whether the most recent candle is fresh enough.

        Args:
            df:      OHLCV DataFrame.
            max_age: Maximum age in hours. If None, uses the engine's
                     default based on the cached freshness thresholds.

        Returns:
            True if the data is fresh, False if stale.
        """
        if max_age is None:
            max_age = 8.0  # Default to 8 hours
        return validate_freshness(df, max_age)

    # ── Transformation ────────────────────────────────────────────────────

    def resample_candles(
        self,
        df: pd.DataFrame,
        target_tf: str,
        source_tf: Optional[str] = None,
    ) -> pd.DataFrame:
        """
        Resample candles to a different timeframe.

        Delegates to ``signal_engine.data.transformers.resample_candles``.
        """
        return resample_candles(df, target_tf, source_tf)

    def normalize_outputs(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Normalize DataFrame to consistent column names/types/order.

        Delegates to ``signal_engine.data.transformers.normalize_outputs``.
        """
        return normalize_outputs(df)

    # ── Persistence ───────────────────────────────────────────────────────

    async def persist_candles(
        self,
        symbol: str,
        timeframe: str,
        df: pd.DataFrame,
        source: str = "engine",
    ) -> int:
        """
        Persist candles to the MongoDB cache.

        Args:
            symbol:    Canonical symbol.
            timeframe: Candle interval.
            df:        OHLCV DataFrame to persist.
            source:    Source label for the documents (e.g. "live", "api").

        Returns:
            Number of new candles inserted.

        Raises:
            RuntimeError: If MongoDB is not available.
        """
        if self._mongo_manager is None:
            log.warning("persist_skipped_no_mongo", symbol=symbol)
            return 0

        col = await candle_cache._get_col(self._mongo_manager)
        if col is None:
            log.warning("persist_skipped_no_collection", symbol=symbol)
            return 0

        await candle_cache._ensure_indexes(col)
        docs = candle_cache._df_to_docs(df, symbol, timeframe, source=source)
        inserted = await candle_cache._store_candles(col, docs)

        log.debug(
            "candles_persisted",
            symbol=symbol,
            timeframe=timeframe,
            total=len(docs),
            new=inserted,
        )
        return inserted

    # ── Cache retrieval ───────────────────────────────────────────────────

    async def cache_retrieval(
        self,
        symbol: str,
        timeframe: str,
        limit: int = 100,
    ) -> Optional[pd.DataFrame]:
        """
        Retrieve candles from cache only (no API fallback).

        Returns None if cache is empty or MongoDB is unavailable.

        Args:
            symbol:    Canonical symbol.
            timeframe: Candle interval.
            limit:     Maximum number of candles.

        Returns:
            DataFrame or None.
        """
        if self._mongo_manager is None:
            return None

        try:
            col = await candle_cache._get_col(self._mongo_manager)
            if col is None:
                return None

            await candle_cache._ensure_indexes(col)

            from pymongo import ASCENDING
            query = {"symbol": symbol, "interval": timeframe}
            cursor = col.find(query, {"_id": 0}) \
                         .sort("timestamp", -1) \
                         .limit(limit)
            docs = await cursor.to_list(length=limit)

            if not docs:
                return None

            docs = list(reversed(docs))  # chronological order
            return candle_cache._docs_to_df(docs)

        except Exception as exc:
            log.warning(
                "cache_retrieval_failed",
                symbol=symbol,
                timeframe=timeframe,
                error=str(exc),
            )
            return None

    # ── Convenience methods ───────────────────────────────────────────────

    async def warm_cache(
        self,
        symbol: str,
        intervals: list[str],
        limit: int = 500,
    ) -> None:
        """
        Pre-populate the cache for a symbol across multiple intervals.

        Args:
            symbol:    Canonical symbol.
            intervals: List of timeframes to warm.
            limit:     Number of candles per interval.
        """
        await candle_cache.warm_cache(
            symbol=symbol,
            intervals=intervals,
            mongo_manager=self._mongo_manager,
            fetch_fn=self._fetch_from_providers,
            limit=limit,
        )

    async def store_live_candles(
        self,
        symbol: str,
        dataframes: dict[str, pd.DataFrame],
    ) -> None:
        """
        Persist live scan candles to MongoDB (fire-and-forget).

        Args:
            symbol:     Canonical symbol.
            dataframes: Mapping of interval -> DataFrame.
        """
        await candle_cache.store_live_candles(
            symbol=symbol,
            dataframes=dataframes,
            mongo_manager=self._mongo_manager,
        )

    async def check_freshness(
        self,
        symbol: str,
        timeframe: str,
    ) -> Optional[dict]:
        """
        Check candle freshness for a symbol/timeframe.

        Returns a dict with freshness info, or None if unavailable.
        """
        return await candle_cache.check_candle_freshness(
            symbol=symbol,
            interval=timeframe,
            mongo_manager=self._mongo_manager,
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Backward Compatibility
# ═══════════════════════════════════════════════════════════════════════════════

# Module-level engine singleton — lazily initialized on first use.
_engine: Optional[MarketDataEngine] = None


def _get_engine() -> MarketDataEngine:
    """Return (and lazily create) the module-level engine singleton."""
    global _engine
    if _engine is None:
        try:
            from signal_engine.db.core import mongo_manager
        except ImportError:
            mongo_manager = None
        _engine = MarketDataEngine(config=cfg, mongo_manager=mongo_manager)
    return _engine


async def fetch_ohlcv(
    symbol: str,
    interval: str,
    limit: int = 100,
    session=None,
) -> pd.DataFrame:
    """
    Fetch OHLCV with automatic source fallback.

    Backward-compatible wrapper around MarketDataEngine.fetch_candles().
    The ``session`` parameter is accepted for API compatibility but ignored
    — the engine manages its own HTTP sessions internally.

    Args:
        symbol:   Canonical symbol, e.g. "XAUUSD".
        interval: Candle interval, e.g. "4h", "1d".
        limit:    Maximum number of candles.
        session:  Ignored (kept for backward compatibility).

    Returns:
        Validated DataFrame with columns [timestamp, open, high, low, close, volume].

    Raises:
        RuntimeError: If all providers fail.
    """
    engine = _get_engine()
    return await engine.fetch_candles(symbol, interval, limit)
