"""
marketmate/data/providers/twelve_data.py
─────────────────────────────────────────
Twelve Data OHLCV provider.

Extracted from data/market_data.py's ``_fetch_twelve`` function.

Key notes:
  - Free tier: 800 requests/day.
  - Supports both crypto and forex/metal pairs.
  - Requires slash notation for some symbols (e.g. "XAU/USD").
  - Has native 4h support — preferred over Alpha Vantage for forex/metal.
"""

from __future__ import annotations

import asyncio
from typing import Optional

import aiohttp
import pandas as pd
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.data.providers.base import DataProvider

log = get_logger("data.providers.twelve_data")

# ─── Interval mapping ─────────────────────────────────────────────────────────

_TWELVE_INTERVAL = {
    "1d": "1day",
    "4h": "4h",
    "1h": "1h",
    "15m": "15min",
    "5m": "5min",
    "1m": "1min",
}


class TwelveDataProvider(DataProvider):
    """
    Twelve Data time series provider.

    Has native 4h support, making it the preferred provider for
    forex/metal pairs on H4 timeframes (Binance doesn't list those).
    """

    @property
    def name(self) -> str:
        return "twelve_data"

    @property
    def supported_timeframes(self) -> list[str]:
        return list(_TWELVE_INTERVAL.keys())

    @property
    def priority(self) -> int:
        # Second priority — free tier has generous limits (800/day)
        # and native 4h support for forex/metals
        return 2

    def can_serve(self, symbol: str, timeframe: str) -> bool:
        """
        Twelve Data can serve if:
          1. It supports the symbol (via resolve_symbol)
          2. API key is configured
          3. The timeframe has a Twelve Data interval mapping
        """
        if not cfg.data.twelve_data_key:
            return False
        if not self.supports_symbol(symbol):
            return False
        return timeframe in _TWELVE_INTERVAL

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
        Fetch OHLCV candles from Twelve Data time_series endpoint.

        Args:
            symbol:    Canonical symbol, e.g. "XAUUSD".
            timeframe: Candle interval, e.g. "4h", "1d".
            limit:     Maximum number of candles to return.

        Returns:
            DataFrame with columns [timestamp, open, high, low, close, volume].

        Raises:
            ValueError: If symbol/timeframe unsupported or API key missing.
        """
        td_interval = _TWELVE_INTERVAL.get(timeframe)
        if not td_interval:
            raise ValueError(
                f"Twelve Data does not support timeframe: {timeframe}"
            )

        if not cfg.data.twelve_data_key:
            raise ValueError("Twelve Data API key not set.")

        twelve_symbol = self.resolve_symbol(symbol)
        if twelve_symbol is None:
            raise ValueError(f"Twelve Data does not support symbol: {symbol}")

        url = "https://api.twelvedata.com/time_series"
        params = {
            "symbol": twelve_symbol,
            "interval": td_interval,
            "outputsize": limit,
            "apikey": cfg.data.twelve_data_key,
            "format": "JSON",
            "timezone": "UTC",
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=cfg.data.request_timeout),
            ) as resp:
                resp.raise_for_status()
                raw = await resp.json()

        if "values" not in raw:
            raise ValueError(
                f"Twelve Data error: {raw.get('message', 'unknown')}"
            )

        rows = []
        for v in reversed(raw["values"]):
            rows.append({
                "timestamp": pd.Timestamp(v["datetime"], tz="UTC"),
                "open":   float(v["open"]),
                "high":   float(v["high"]),
                "low":    float(v["low"]),
                "close":  float(v["close"]),
                "volume": float(v.get("volume", 0)),
            })

        df = pd.DataFrame(rows)
        log.debug(
            "twelve_data_fetched",
            symbol=symbol,
            timeframe=timeframe,
            candles=len(df),
        )
        return df
