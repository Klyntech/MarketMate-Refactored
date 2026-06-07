"""
marketmate/data/providers/alpha_vantage.py
───────────────────────────────────────────
Alpha Vantage OHLCV provider.

Extracted from data/market_data.py's ``_fetch_alpha_vantage`` function.

Key notes:
  - Alpha Vantage has NO native 4h endpoint. "4h" is fetched as "60min"
    and then resampled to true 4h OHLCV candles inside fetch().
  - Free tier is limited to 25 requests/day.
  - Daily endpoint uses TIME_SERIES_DAILY with full outputsize.

The resampling logic (1h -> 4h) is performed locally after fetching
to ensure downstream bias logic sees correct granularity.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import aiohttp
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from signal_engine.core.config import cfg
from signal_engine.core.logger import get_logger
from signal_engine.data.providers.base import DataProvider
from signal_engine.data.transformers import resample_candles

log = get_logger("data.providers.alpha_vantage")

# ─── Interval mapping ─────────────────────────────────────────────────────────
# NOTE: Alpha Vantage has NO native 4h endpoint. "4h" is fetched as "60min"
# and then resampled to true 4h OHLCV candles inside fetch().

_AV_INTERVAL = {
    "1d": None,        # uses TIME_SERIES_DAILY (separate endpoint)
    "4h": "60min",     # fetched as 1h, resampled to 4h in fetch()
    "1h": "60min",
    "15m": "15min",
    "5m":  "5min",
    "1m":  "1min",
}

# Timeframes that Alpha Vantage can natively provide (before resampling)
_NATIVE_TIMEFRAMES = ["1d", "1h", "15m", "5m", "1m"]

# Timeframes that require resampling from a native timeframe
_RESAMPLE_MAP = {
    "4h": "1h",  # 4h is resampled from 1h data
}


class AlphaVantageProvider(DataProvider):
    """
    Alpha Vantage OHLCV data provider.

    Supports daily and intraday timeframes. The "4h" timeframe is
    served by fetching 1h candles and resampling to 4h.
    """

    @property
    def name(self) -> str:
        return "alpha_vantage"

    @property
    def supported_timeframes(self) -> list[str]:
        """Native timeframes only (4h requires resampling)."""
        return list(_NATIVE_TIMEFRAMES)

    @property
    def priority(self) -> int:
        # Lowest priority — 25 req/day free tier limit
        return 3

    def can_serve(self, symbol: str, timeframe: str) -> bool:
        """
        Alpha Vantage can serve if:
          1. It supports the symbol (via resolve_symbol)
          2. API key is configured
          3. The timeframe has an AV interval mapping (native or resample)
        """
        if not cfg.data.alpha_vantage_key:
            return False
        if not self.supports_symbol(symbol):
            return False
        return timeframe in _AV_INTERVAL

    @retry(
        stop=stop_after_attempt(cfg.data.max_retries),
        wait=wait_exponential(
            multiplier=cfg.data.retry_backoff_base,
            min=1, max=30,
        ),
        retry=retry_if_exception_type((aiohttp.ClientError, asyncio.TimeoutError)),
        reraise=True,
    )
    async def fetch(
        self,
        symbol: str,
        timeframe: str,
        limit: int,
    ) -> pd.DataFrame:
        """
        Fetch OHLCV candles from Alpha Vantage.

        For "4h" requests, 1h candles are fetched and then resampled
        to true 4h candles.

        Args:
            symbol:    Canonical symbol, e.g. "XAUUSD".
            timeframe: Candle interval, e.g. "4h", "1d".
            limit:     Maximum number of candles to return.

        Returns:
            DataFrame with columns [timestamp, open, high, low, close, volume].

        Raises:
            ValueError: If symbol/timeframe unsupported or API key missing.
        """
        if not cfg.data.alpha_vantage_key:
            raise ValueError("Alpha Vantage key not set.")

        av_symbol = self.resolve_symbol(symbol)
        if av_symbol is None:
            raise ValueError(f"Alpha Vantage does not support symbol: {symbol}")

        av_interval = _AV_INTERVAL.get(timeframe)
        if av_interval is None and timeframe != "1d":
            raise ValueError(
                f"Alpha Vantage does not support timeframe: {timeframe}"
            )

        # Determine if resampling will be needed
        needs_resample = (
            timeframe in _RESAMPLE_MAP
            and av_interval is not None
        )

        # ── Daily endpoint ─────────────────────────────────────────────────
        if timeframe == "1d":
            params = {
                "function":   "TIME_SERIES_DAILY",
                "symbol":     av_symbol,
                "outputsize": "full",
                "apikey":     cfg.data.alpha_vantage_key,
            }
        # ── Intraday endpoint ──────────────────────────────────────────────
        elif av_interval:
            params = {
                "function":   "TIME_SERIES_INTRADAY",
                "symbol":     av_symbol,
                "interval":   av_interval,
                "outputsize": "full",
                "apikey":     cfg.data.alpha_vantage_key,
            }
        else:
            raise ValueError(
                f"Alpha Vantage does not support interval: {timeframe}"
            )

        url = "https://www.alphavantage.co/query"
        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=cfg.data.request_timeout),
            ) as resp:
                resp.raise_for_status()
                raw = await resp.json()

        # Find the time series key
        ts_key = next((k for k in raw if "Time Series" in k), None)
        if not ts_key:
            raise ValueError(f"AV unexpected response: {list(raw.keys())}")

        rows = []
        for ts, vals in raw[ts_key].items():
            rows.append({
                "timestamp": pd.Timestamp(ts, tz="UTC"),
                "open":   float(vals["1. open"]),
                "high":   float(vals["2. high"]),
                "low":    float(vals["3. low"]),
                "close":  float(vals["4. close"]),
                "volume": float(vals.get("5. volume", 0)),
            })

        df = pd.DataFrame(sorted(rows, key=lambda x: x["timestamp"]))

        # ── Resample 1h → 4h when the requested interval is "4h" ───────────
        if needs_resample:
            log.debug(
                "alpha_vantage_resampling",
                symbol=symbol,
                from_tf=_RESAMPLE_MAP[timeframe],
                to_tf=timeframe,
                candles_in=len(df),
            )
            df = resample_candles(df, timeframe)
            log.debug(
                "alpha_vantage_resampled_4h",
                symbol=symbol,
                candles_1h_raw=len(rows),
                candles_4h=len(df),
            )

        # Trim to the requested limit AFTER resampling (not before — we need
        # the full raw data to produce enough resampled candles).
        df = df.tail(limit).reset_index(drop=True)

        log.debug(
            "alpha_vantage_fetched",
            symbol=symbol,
            timeframe=timeframe,
            candles=len(df),
        )
        return df
