"""
marketmate/data/providers/base.py
──────────────────────────────────
Abstract base class for all OHLCV data providers.

Every provider must implement:
  - fetch(symbol, timeframe, limit) -> DataFrame
  - name (property)
  - supported_timeframes (property)
  - priority (property)

The base class also provides a default ``resolve_symbol`` method that
providers can override for provider-specific symbol mapping.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Optional

import pandas as pd

from signal_engine.core.config import cfg
from signal_engine.core.logger import get_logger

log = get_logger("data.providers.base")

# ─── Provider-aware symbol mapping ──────────────────────────────────────────
#
# Keys are canonical symbols (as used in config/PAIRS env var).
# None means the provider does not support this symbol — skip it entirely.
# Missing keys fall through to the default (use symbol as-is for that provider).

SYMBOL_MAP: dict[str, dict[str, Optional[str]]] = {
    # ─── Metals ────────────────────────────────────────────────────────────
    "XAUUSD": {
        "binance":       None,        # Binance does not list gold/forex
        "yfinance":      "GC=F",      # Gold futures (most liquid, free data)
        "twelve_data":   "XAU/USD",   # Twelve Data requires slash notation
        "alpha_vantage": "XAUUSD",    # AV accepts compact notation
    },
    "XAGUSD": {
        "binance":       None,
        "yfinance":      "SI=F",      # Silver futures
        "twelve_data":   "XAG/USD",
        "alpha_vantage": "XAGUSD",
    },
    # ─── Forex Majors ──────────────────────────────────────────────────────
    "EURUSD": {
        "binance":       None,
        "yfinance":      "EURUSD=X",  # Yahoo Finance forex notation
        "twelve_data":   "EUR/USD",
        "alpha_vantage": "EURUSD",
    },
    "GBPUSD": {
        "binance":       None,
        "yfinance":      "GBPUSD=X",
        "twelve_data":   "GBP/USD",
        "alpha_vantage": "GBPUSD",
    },
    "USDJPY": {
        "binance":       None,
        "yfinance":      "USDJPY=X",
        "twelve_data":   "USD/JPY",
        "alpha_vantage": "USDJPY",
    },
    "USDCHF": {
        "binance":       None,
        "yfinance":      "USDCHF=X",
        "twelve_data":   "USD/CHF",
        "alpha_vantage": "USDCHF",
    },
    "AUDUSD": {
        "binance":       None,
        "yfinance":      "AUDUSD=X",
        "twelve_data":   "AUD/USD",
        "alpha_vantage": "AUDUSD",
    },
    "NZDUSD": {
        "binance":       None,
        "yfinance":      "NZDUSD=X",
        "twelve_data":   "NZD/USD",
        "alpha_vantage": "NZDUSD",
    },
    "USDCAD": {
        "binance":       None,
        "yfinance":      "USDCAD=X",
        "twelve_data":   "USD/CAD",
        "alpha_vantage": "USDCAD",
    },
    # ─── Forex Crosses ─────────────────────────────────────────────────────
    "EURJPY": {
        "binance":       None,
        "yfinance":      "EURJPY=X",
        "twelve_data":   "EUR/JPY",
        "alpha_vantage": "EURJPY",
    },
    "GBPJPY": {
        "binance":       None,
        "yfinance":      "GBPJPY=X",
        "twelve_data":   "GBP/JPY",
        "alpha_vantage": "GBPJPY",
    },
    "EURGBP": {
        "binance":       None,
        "yfinance":      "EURGBP=X",
        "twelve_data":   "EUR/GBP",
        "alpha_vantage": "EURGBP",
    },
    # ─── Crypto ────────────────────────────────────────────────────────────
    "BTCUSD": {
        "binance":       "BTCUSDT",  # Binance uses USDT pairs for crypto
        "yfinance":      "BTC-USD",   # Yahoo Finance crypto notation
        "twelve_data":   "BTC/USD",
        "alpha_vantage": "BTCUSD",
    },
    "ETHUSD": {
        "binance":       "ETHUSDT",  # Binance uses USDT pairs for crypto
        "yfinance":      "ETH-USD",   # Yahoo Finance crypto notation
        "twelve_data":   "ETH/USD",
        "alpha_vantage": "ETHUSD",
    },
    "SOLUSD": {
        "binance":       "SOLUSDT",
        "yfinance":      "SOL-USD",
        "twelve_data":   "SOL/USD",
        "alpha_vantage": None,       # Alpha Vantage may not support SOL
    },
    "BNBUSD": {
        "binance":       "BNBUSDT",
        "yfinance":      "BNB-USD",
        "twelve_data":   "BNB/USD",
        "alpha_vantage": None,       # Alpha Vantage may not support BNB
    },
    # ─── Indices ───────────────────────────────────────────────────────────
    "US500": {
        "binance":       None,
        "yfinance":      "^GSPC",     # S&P 500 index
        "twelve_data":   "SPX",
        "alpha_vantage": None,        # AV doesn't support indices easily
    },
    "NAS100": {
        "binance":       None,
        "yfinance":      "^NDX",      # Nasdaq 100 index
        "twelve_data":   "NDX",
        "alpha_vantage": None,
    },
    "US30": {
        "binance":       None,
        "yfinance":      "^DJI",      # Dow Jones Industrial Average
        "twelve_data":   "DJI",
        "alpha_vantage": None,
    },
    "GER40": {
        "binance":       None,
        "yfinance":      "^GDAXI",    # DAX (German stock index)
        "twelve_data":   "DAX",
        "alpha_vantage": None,
    },
}


class DataProvider(ABC):
    """
    Abstract base class for market data providers.

    Subclasses must implement ``fetch`` and declare their capabilities
    via the ``name``, ``supported_timeframes``, and ``priority`` properties.

    Provider priority determines the order in which providers are tried:
      - Lower number = higher priority (tried first).
      - Providers with native support for a timeframe are preferred
        over those that require resampling.

    The ``resolve_symbol`` method can be overridden to handle provider-specific
    symbol formatting (e.g. Twelve Data's "XAU/USD" vs "XAUUSD").
    """

    # ── Abstract interface ──────────────────────────────────────────────────

    @property
    @abstractmethod
    def name(self) -> str:
        """Unique identifier for this provider (e.g. 'binance')."""

    @property
    @abstractmethod
    def supported_timeframes(self) -> list[str]:
        """
        List of timeframes this provider supports *natively* without
        resampling (e.g. ['1d', '4h', '1h', '15m', '5m', '1m']).
        """

    @property
    @abstractmethod
    def priority(self) -> int:
        """
        Priority for provider selection. Lower = tried first.
        Providers with native timeframe support should have lower priority
        (i.e. higher preference) than those requiring resampling.
        """

    @abstractmethod
    async def fetch(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candles for the given symbol/timeframe.

        Returns a DataFrame with columns:
            [timestamp, open, high, low, close, volume]
        where timestamp is datetime64[UTC] and OHLCV are float64.

        Raises ValueError if the provider cannot serve this request
        (unsupported symbol or timeframe, missing API key, etc.).
        """

    # ── Common helpers ─────────────────────────────────────────────────────

    def resolve_symbol(self, symbol: str) -> Optional[str]:
        """
        Return the provider-specific symbol string, or None if the
        provider does not support this symbol and should be skipped.

        Falls back to the raw symbol for any pair not listed in SYMBOL_MAP
        (e.g. crypto pairs like BTCUSDT work on Binance unchanged).
        """
        mapping = SYMBOL_MAP.get(symbol.upper())
        if mapping is None:
            return symbol  # not in map — use as-is for all providers
        return mapping.get(self.name, symbol)  # None means skip

    def supports_symbol(self, symbol: str) -> bool:
        """Check whether this provider supports the given symbol."""
        return self.resolve_symbol(symbol) is not None

    def supports_timeframe(self, timeframe: str) -> bool:
        """Check whether this provider natively supports the given timeframe."""
        return timeframe in self.supported_timeframes

    def can_serve(self, symbol: str, timeframe: str) -> bool:
        """
        Check whether this provider can serve the request at all
        (supports both the symbol and has at least a resample path).
        Subclasses may override to add additional checks (e.g. API key).
        """
        return self.supports_symbol(symbol)

    def __repr__(self) -> str:
        return (
            f"<{self.__class__.__name__} name={self.name!r} "
            f"priority={self.priority} "
            f"timeframes={self.supported_timeframes}>"
        )
