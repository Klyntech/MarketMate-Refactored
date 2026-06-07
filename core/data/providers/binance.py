"""
marketmate/data/providers/binance.py
─────────────────────────────────────
Binance REST klines provider.

Extracted from data/market_data.py's ``_fetch_binance`` function.
Binance provides free, high-quality, crypto-native OHLCV data with
native support for all common intraday timeframes.

No API key is required for public klines data.
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

log = get_logger("data.providers.binance")

# ─── Interval mapping ─────────────────────────────────────────────────────────

_BINANCE_INTERVAL = {
    "1d": "1d",
    "4h": "4h",
    "1h": "1h",
    "15m": "15m",
    "5m": "5m",
    "1m": "1m",
}


class BinanceProvider(DataProvider):
    """
    Binance REST klines endpoint (no auth required for public data).

    Skipped automatically for forex/metal symbols not listed on Binance
    via the ``resolve_symbol`` mechanism inherited from ``DataProvider``.
    """

    @property
    def name(self) -> str:
        return "binance"

    @property
    def supported_timeframes(self) -> list[str]:
        return list(_BINANCE_INTERVAL.keys())

    @property
    def priority(self) -> int:
        # Highest priority — free, high-quality, native 4H/M15/M5
        return 1

    def can_serve(self, symbol: str, timeframe: str) -> bool:
        """
        Binance can serve a request if it supports both the symbol and
        has a native interval mapping for the requested timeframe.
        """
        return (
            self.supports_symbol(symbol)
            and timeframe in _BINANCE_INTERVAL
        )

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
        Fetch OHLCV candles from Binance klines endpoint.

        Args:
            symbol:   Canonical symbol, e.g. "BTCUSDT".
            timeframe: Candle interval, e.g. "4h", "15m".
            limit:     Maximum number of candles to return.

        Returns:
            DataFrame with columns [timestamp, open, high, low, close, volume].

        Raises:
            ValueError: If symbol or timeframe is unsupported.
            aiohttp.ClientError: On network failure (retried via tenacity).
        """
        binance_symbol = self.resolve_symbol(symbol)
        if binance_symbol is None:
            raise ValueError(f"Binance does not support symbol: {symbol}")

        binance_interval = _BINANCE_INTERVAL.get(timeframe)
        if binance_interval is None:
            raise ValueError(
                f"Binance does not support timeframe: {timeframe}"
            )

        url = "https://api.binance.com/api/v3/klines"
        params = {
            "symbol": binance_symbol.upper().replace("/", ""),
            "interval": binance_interval,
            "limit": limit,
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=cfg.data.request_timeout),
            ) as resp:
                resp.raise_for_status()
                raw = await resp.json()

        rows = []
        for k in raw:
            rows.append({
                "timestamp": pd.Timestamp(k[0], unit="ms", tz="UTC"),
                "open":   float(k[1]),
                "high":   float(k[2]),
                "low":    float(k[3]),
                "close":  float(k[4]),
                "volume": float(k[5]),
            })

        df = pd.DataFrame(rows)
        log.debug(
            "binance_fetched",
            symbol=symbol,
            timeframe=timeframe,
            candles=len(df),
        )
        return df
