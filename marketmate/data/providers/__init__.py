"""
marketmate/data/providers/__init__.py
──────────────────────────────────────
Data provider package.

Exports all provider classes and a convenience registry for
auto-discovering available providers.

Convenience functions:
  get_candles()  — fetch OHLCV data via MarketDataEngine (backward-compat)
"""

from marketmate.data.providers.base import DataProvider, SYMBOL_MAP
from marketmate.data.providers.binance import BinanceProvider
from marketmate.data.providers.alpha_vantage import AlphaVantageProvider
from marketmate.data.providers.twelve_data import TwelveDataProvider

# ─── Provider registry ────────────────────────────────────────────────────────
# Ordered by default priority. The engine iterates through this list
# to find providers that can serve a given symbol/timeframe request.

PROVIDER_CLASSES: list[type[DataProvider]] = [
    BinanceProvider,
    TwelveDataProvider,
    AlphaVantageProvider,
]


def get_available_providers() -> list[DataProvider]:
    """
    Instantiate all providers and return those that are usable
    (i.e. have their required API keys configured).

    Returns:
        List of DataProvider instances sorted by priority.
    """
    providers = [cls() for cls in PROVIDER_CLASSES]
    # Sort by priority (lower = higher preference)
    providers.sort(key=lambda p: p.priority)
    return providers


# ─── Convenience function ──────────────────────────────────────────────────────
# Backward-compatible get_candles() that delegates to MarketDataEngine.
# Used by analytics/backtest.py and analytics/weekly_recap.py.

async def get_candles(
    symbol: str,
    timeframe: str,
    limit: int = 100,
    start_ts=None,
    end_ts=None,
) -> "pd.DataFrame":
    """
    Fetch OHLCV candles via MarketDataEngine.

    This is a convenience wrapper that delegates to the engine singleton.
    Accepts optional start_ts/end_ts for date-range queries (used by
    weekly_recap), though the current engine only supports limit-based
    fetching — date range is handled by trimming the result.

    Args:
        symbol:     Canonical symbol, e.g. "XAUUSD".
        timeframe:  Candle interval, e.g. "4h", "1d", "15m".
        limit:      Maximum number of candles to return.
        start_ts:   Optional start datetime (filters result after fetch).
        end_ts:     Optional end datetime (filters result after fetch).

    Returns:
        DataFrame with columns [timestamp, open, high, low, close, volume].
    """
    from marketmate.data.engine import fetch_ohlcv

    # Fetch more data if date-range filtering will be applied
    fetch_limit = limit
    if start_ts is not None or end_ts is not None:
        fetch_limit = max(limit, 2000)

    df = await fetch_ohlcv(symbol, timeframe, limit=fetch_limit)

    # Apply date-range filtering if requested
    if df is not None and not df.empty:
        if start_ts is not None:
            mask = df["timestamp"] >= start_ts
            df = df[mask]
        if end_ts is not None:
            mask = df["timestamp"] <= end_ts
            df = df[mask]
        # Trim to original limit after filtering
        if len(df) > limit:
            df = df.tail(limit).reset_index(drop=True)

    return df


__all__ = [
    "DataProvider",
    "SYMBOL_MAP",
    "BinanceProvider",
    "AlphaVantageProvider",
    "TwelveDataProvider",
    "PROVIDER_CLASSES",
    "get_available_providers",
    "get_candles",
]
