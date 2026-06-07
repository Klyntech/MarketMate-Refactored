"""
marketmate/data/providers/yfinance_provider.py
────────────────────────────────────────────────
Yahoo Finance (yfinance) OHLCV data provider.

Key advantages:
  - Completely free, no API key required
  - Unlimited requests (no rate limits)
  - Supports forex (XAUUSD, EURUSD), crypto (BTC-USD), equities
  - Native 1h, 1d support; 4h available via resampling from 1h

Used as the PRIMARY fallback when TwelveData/AlphaVantage are rate-limited
or when no API keys are configured. It's lower priority than TwelveData
for 4h data (since TwelveData has native 4h) but higher priority for
forex/metals that Binance can't serve.

Symbol mapping:
  XAUUSD  -> GC=F (gold futures) or XAUUSD=X
  EURUSD  -> EURUSD=X
  BTCUSD  -> BTC-USD
  ETHUSD  -> ETH-USD
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone, timedelta
from typing import Optional

import numpy as np
import pandas as pd

from signal_engine.core.config import cfg
from signal_engine.core.logger import get_logger
from signal_engine.data.providers.base import DataProvider, SYMBOL_MAP

log = get_logger("data.providers.yfinance")

# ─── Interval mapping ─────────────────────────────────────────────────────────
# yfinance interval -> internal timeframe mapping
# Note: yfinance uses different interval strings than our internal format.

_YFINANCE_INTERVAL = {
    "1d": "1d",
    "1h": "1h",
    "15m": "15m",
    "5m": "5m",
}

# ─── Symbol mapping for yfinance ──────────────────────────────────────────────
# yfinance uses different ticker formats:
#   Forex: EURUSD=X
#   Gold: GC=F (futures) or XAUUSD=X
#   Crypto: BTC-USD

YFINANCE_SYMBOL_MAP = {
    # Metals
    "XAUUSD": "GC=F",        # Gold futures (most liquid, free data)
    "XAGUSD": "SI=F",        # Silver futures
    # Forex Majors
    "EURUSD": "EURUSD=X",    # EUR/USD forex
    "GBPUSD": "GBPUSD=X",    # GBP/USD forex
    "USDJPY": "USDJPY=X",    # USD/JPY forex
    "USDCHF": "USDCHF=X",    # USD/CHF forex
    "AUDUSD": "AUDUSD=X",    # AUD/USD forex
    "NZDUSD": "NZDUSD=X",    # NZD/USD forex
    "USDCAD": "USDCAD=X",    # USD/CAD forex
    # Forex Crosses
    "EURJPY": "EURJPY=X",    # EUR/JPY forex
    "GBPJPY": "GBPJPY=X",    # GBP/JPY forex
    "EURGBP": "EURGBP=X",    # EUR/GBP forex
    # Crypto
    "BTCUSD": "BTC-USD",     # Bitcoin
    "ETHUSD": "ETH-USD",     # Ethereum
    "SOLUSD": "SOL-USD",     # Solana
    "BNBUSD": "BNB-USD",     # BNB
    # Indices
    "US500":  "^GSPC",       # S&P 500 index
    "NAS100": "^NDX",        # Nasdaq 100 index
    "US30":   "^DJI",        # Dow Jones Industrial Average
    "GER40":  "^GDAXI",      # DAX (German stock index)
}


class YFinanceProvider(DataProvider):
    """
    Yahoo Finance (yfinance) data provider.

    Free, unlimited, no API key required.
    Supports all major forex, metals, and crypto pairs.
    Native 1h/1d/15m/5m support; 4h available via resampling from 1h.
    """

    @property
    def name(self) -> str:
        return "yfinance"

    @property
    def supported_timeframes(self) -> list[str]:
        # Native support; 4h is handled via resampling from 1h
        return list(_YFINANCE_INTERVAL.keys())

    @property
    def priority(self) -> int:
        # Priority 1.5 — higher than AlphaVantage (3), lower than Binance (1)
        # but available for ALL symbols including forex/metals which Binance
        # can't serve. TwelveData is priority 2 but has rate limits.
        # We set this to 1 (same as Binance) because it's free and unlimited.
        return 1

    def can_serve(self, symbol: str, timeframe: str) -> bool:
        """yfinance can serve any symbol it has a mapping for."""
        return self.resolve_symbol(symbol) is not None

    async def fetch(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candles from Yahoo Finance via yfinance library.

        For 4h timeframe, fetches 1h data and resamples to 4h.
        For all other timeframes, fetches directly.

        Args:
            symbol:    Canonical symbol, e.g. "XAUUSD".
            timeframe: Candle interval, e.g. "4h", "1d".
            limit:     Maximum number of candles to return.

        Returns:
            DataFrame with columns [timestamp, open, high, low, close, volume].

        Raises:
            ValueError: If symbol is unsupported or data fetch fails.
        """
        yf_symbol = self.resolve_symbol(symbol)
        if yf_symbol is None:
            raise ValueError(f"yfinance does not support symbol: {symbol}")

        # For 4h, we need to fetch 1h and resample
        actual_tf = timeframe
        resample_to_4h = False
        if timeframe == "4h":
            actual_tf = "1h"
            resample_to_4h = True
            # Need 4x as many 1h candles to get the same number of 4h candles
            fetch_limit = limit * 4
        else:
            fetch_limit = limit

        yf_interval = _YFINANCE_INTERVAL.get(actual_tf)
        if yf_interval is None:
            raise ValueError(
                f"yfinance does not support timeframe: {timeframe}"
            )

        # Calculate date range for yfinance
        # yfinance requires start/end dates or a period string
        # Use max period to get as much data as possible
        period = "max"

        # Run yfinance in a thread (it's synchronous)
        loop = asyncio.get_event_loop()
        df = await loop.run_in_executor(
            None,
            self._fetch_sync,
            yf_symbol,
            yf_interval,
            period,
            fetch_limit,
        )

        if df is None or df.empty:
            raise ValueError(
                f"yfinance returned no data for {yf_symbol}/{actual_tf}"
            )

        # Resample 1h -> 4h if needed
        if resample_to_4h:
            df = self._resample_to_4h(df)
            df = df.tail(limit).reset_index(drop=True)

        log.info(
            "yfinance_fetched",
            symbol=symbol,
            timeframe=timeframe,
            candles=len(df),
            resampled=resample_to_4h,
        )
        return df

    def _fetch_sync(
        self,
        yf_symbol: str,
        interval: str,
        period: str,
        limit: int,
    ) -> Optional[pd.DataFrame]:
        """Synchronous yfinance data fetch (runs in thread pool)."""
        try:
            import yfinance as yf

            ticker = yf.Ticker(yf_symbol)
            hist = ticker.history(period=period, interval=interval)

            if hist.empty:
                return None

            # Normalize column names
            df = pd.DataFrame({
                "timestamp": hist.index,
                "open":   hist["Open"].astype(float),
                "high":   hist["High"].astype(float),
                "low":    hist["Low"].astype(float),
                "close":  hist["Close"].astype(float),
                "volume": hist["Volume"].astype(float),
            }).reset_index(drop=True)

            # Ensure timestamp is UTC
            if df["timestamp"].dt.tz is None:
                df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")
            else:
                df["timestamp"] = df["timestamp"].dt.tz_convert("UTC")

            # Drop any NaN rows
            df = df.dropna(subset=["open", "high", "low", "close"]).reset_index(drop=True)

            # Trim to limit
            if len(df) > limit:
                df = df.tail(limit).reset_index(drop=True)

            return df

        except Exception as exc:
            log.error("yfinance_fetch_error", error=str(exc), symbol=yf_symbol)
            return None

    def _resample_to_4h(self, df: pd.DataFrame) -> pd.DataFrame:
        """Resample 1h candles to 4h candles."""
        df = df.copy()
        df = df.set_index("timestamp")

        resampled = df.resample("4h", label="left", closed="left").agg({
            "open":   "first",
            "high":   "max",
            "low":    "min",
            "close":  "last",
            "volume": "sum",
        }).dropna(subset=["open", "close"])

        resampled = resampled.reset_index()
        return resampled

    def resolve_symbol(self, symbol: str) -> Optional[str]:
        """Return the yfinance ticker symbol, or None if unsupported."""
        return YFINANCE_SYMBOL_MAP.get(symbol.upper())
