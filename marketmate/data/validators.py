"""
marketmate/data/validators.py
─────────────────────────────
Validates incoming OHLCV data and cross-validates against external sources.

Merged from:
  - ``data/validators.py``          — OHLCV integrity validation
  - ``services/data_validator.py``  — Cross-source weekly data validation

All imports updated to use ``marketmate.`` prefix.

Components:
  1. validate_ohlcv()        — Reject malformed/anomalous candles
  2. validate_weekly_data()  — Cross-validate internal vs external data
"""

from __future__ import annotations

import aiohttp
from datetime import datetime, timezone
from typing import Optional

import pandas as pd
import numpy as np

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger

log = get_logger("data.validators")

# ═══════════════════════════════════════════════════════════════════════════════
# OHLCV Integrity Validation
# ═══════════════════════════════════════════════════════════════════════════════

REQUIRED_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]

# Max allowed % change between consecutive closes before flagging spike
MAX_CLOSE_CHANGE_PCT = 0.20  # 20%

# Minimum number of clean candles required for strategy engine
MIN_CANDLES = 20


def validate_ohlcv(df: pd.DataFrame, symbol: str, interval: str) -> pd.DataFrame:
    """
    Returns a cleaned, validated DataFrame.
    Raises ValueError if data is fundamentally unusable.

    Validation checks:
      1. Required columns present
      2. Type coercion for OHLCV columns
      3. Drop rows with NaN OHLC
      4. OHLC integrity (High >= Low, Open/Close within range)
      5. Spike detection (consecutive close change > 20%)
      6. Minimum candle count (>= 20)
    """
    if df is None or df.empty:
        raise ValueError(f"Empty DataFrame for {symbol}/{interval}")

    # ── Column presence ───────────────────────────────────────────────────────
    missing = [c for c in REQUIRED_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing columns {missing} in {symbol}/{interval}")

    df = df.copy()

    # ── Type coercion ─────────────────────────────────────────────────────────
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce")

    # ── Drop rows with NaN OHLC ───────────────────────────────────────────────
    pre_len = len(df)
    df.dropna(subset=["open", "high", "low", "close"], inplace=True)
    if dropped := pre_len - len(df):
        log.warning("dropped_nan_candles", symbol=symbol, count=dropped)

    if df.empty:
        raise ValueError(f"All candles invalid after NaN drop for {symbol}/{interval}")

    # ── OHLC integrity (High >= Low, Open/Close within range) ────────────────
    bad_hl = df["high"] < df["low"]
    if bad_hl.any():
        count = bad_hl.sum()
        log.warning("bad_high_low_candles", symbol=symbol, count=count)
        df = df[~bad_hl]

    bad_open = (df["open"] > df["high"]) | (df["open"] < df["low"])
    bad_close = (df["close"] > df["high"]) | (df["close"] < df["low"])
    bad_ohlc = bad_open | bad_close
    if bad_ohlc.any():
        log.warning("ohlc_integrity_failed", symbol=symbol, count=bad_ohlc.sum())
        df = df[~bad_ohlc]

    # ── Spike detection (consecutive close change > 20%) ─────────────────────
    pct_change = df["close"].pct_change().abs()
    spikes = pct_change > MAX_CLOSE_CHANGE_PCT
    if spikes.any():
        log.warning(
            "price_spikes_detected",
            symbol=symbol,
            interval=interval,
            count=spikes.sum(),
            max_spike_pct=round(float(pct_change.max() * 100), 2),
        )
        # Remove the spike candle itself (the first abnormal one)
        df = df[~spikes]

    # ── Sort ascending by timestamp ───────────────────────────────────────────
    df.sort_values("timestamp", inplace=True)
    df.reset_index(drop=True, inplace=True)

    if len(df) < MIN_CANDLES:
        raise ValueError(
            f"Insufficient clean candles ({len(df)}) for {symbol}/{interval} "
            f"— need ≥{MIN_CANDLES}"
        )

    log.debug("validation_passed", symbol=symbol, interval=interval, candles=len(df))
    return df


def validate_freshness(df: pd.DataFrame, max_age_hours: float = 8.0) -> bool:
    """
    Check whether the most recent candle in a DataFrame is fresh enough.

    Args:
        df:          OHLCV DataFrame with a 'timestamp' column.
        max_age_hours: Maximum acceptable age in hours for the most recent candle.

    Returns:
        True if the most recent candle is within the freshness window,
        False if stale or the DataFrame is empty.
    """
    if df is None or df.empty:
        return False

    try:
        last_ts = df["timestamp"].iloc[-1]
        if hasattr(last_ts, "to_pydatetime"):
            last_ts = last_ts.to_pydatetime()
        if last_ts.tzinfo is None:
            last_ts = last_ts.replace(tzinfo=timezone.utc)

        age = datetime.now(timezone.utc) - last_ts
        return age.total_seconds() <= max_age_hours * 3600
    except Exception as exc:
        log.warning("freshness_validation_failed", error=str(exc))
        return False


# ═══════════════════════════════════════════════════════════════════════════════
# Cross-Source Weekly Data Validation
# ═══════════════════════════════════════════════════════════════════════════════
# Cross-validates internal OHLCV candles against Twelve Data before publishing
# a weekly recap.
#
# Logic:
#   1. Pull daily candles for the target week from the local `candles` collection.
#   2. Fetch the same range directly from Twelve Data (forced — not the multi-
#      source fallback, so the comparison is always against an independent source).
#   3. Compute weekly OHLC from each dataset.
#   4. Calculate % difference for each price point.
#   5. Return passed=True when all differences are within the configured threshold,
#      passed=False otherwise.
#
# If Twelve Data is unreachable the function returns passed=True with
# source=None so the recap is never silently blocked by a network outage.

_TD_URL = "https://api.twelvedata.com/time_series"

# Canonical Twelve Data symbol mapping for cross-validation
_TD_SYMBOL_MAP = {
    "XAUUSD": "XAU/USD",
}


def _td_symbol(symbol: str) -> str:
    return _TD_SYMBOL_MAP.get(symbol.upper(), symbol)


def _weekly_ohlc(candles: list[dict]) -> dict:
    """Reduce a list of daily candle dicts to a single weekly OHLC dict."""
    if not candles:
        return {}
    candles_sorted = sorted(candles, key=lambda c: c["timestamp"])
    return {
        "open":  float(candles_sorted[0]["open"]),
        "high":  max(float(c["high"]) for c in candles_sorted),
        "low":   min(float(c["low"])  for c in candles_sorted),
        "close": float(candles_sorted[-1]["close"]),
    }


def _pct_diff(a: float, b: float) -> float:
    """Return absolute % difference between two prices."""
    if a == 0:
        return 0.0
    return abs((a - b) / a) * 100.0


async def _fetch_td_daily(
    symbol: str,
    start_ts: datetime,
    end_ts: datetime,
    session: aiohttp.ClientSession,
) -> list[dict]:
    """
    Fetch daily candles from Twelve Data for the given date range.
    Returns list of candle dicts or empty list on failure.
    """
    if not cfg.data.twelve_data_key:
        log.warning("validator_td_key_missing")
        return []

    params = {
        "symbol":     _td_symbol(symbol),
        "interval":   "1day",
        "start_date": start_ts.strftime("%Y-%m-%d"),
        "end_date":   end_ts.strftime("%Y-%m-%d"),
        "apikey":     cfg.data.twelve_data_key,
        "format":     "JSON",
        "timezone":   "UTC",
    }
    try:
        async with session.get(
            _TD_URL, params=params,
            timeout=aiohttp.ClientTimeout(total=15),
        ) as resp:
            resp.raise_for_status()
            raw = await resp.json()

        if "values" not in raw:
            log.warning("validator_td_no_values",
                        message=raw.get("message", "unknown"))
            return []

        candles = []
        for v in raw["values"]:
            try:
                candles.append({
                    "timestamp": datetime.fromisoformat(v["datetime"]).replace(
                        tzinfo=timezone.utc
                    ),
                    "open":  float(v["open"]),
                    "high":  float(v["high"]),
                    "low":   float(v["low"]),
                    "close": float(v["close"]),
                })
            except (KeyError, ValueError):
                continue
        return candles

    except Exception as exc:
        log.warning("validator_td_fetch_failed", error=str(exc))
        return []


async def _fetch_internal_daily(
    symbol: str,
    start_ts: datetime,
    end_ts: datetime,
    mongo_manager,
) -> list[dict]:
    """Pull daily candles from the local MongoDB candles collection."""
    try:
        db = await mongo_manager.get_db()
        if db is None:
            return []
        col = db["candles"]
        cursor = col.find(
            {
                "symbol":    symbol,
                "interval":  "1d",
                "timestamp": {"$gte": start_ts, "$lte": end_ts},
            },
            {"_id": 0},
        ).sort("timestamp", 1)
        return await cursor.to_list(length=10)
    except Exception as exc:
        log.warning("validator_internal_fetch_failed", error=str(exc))
        return []


# ─── Public Cross-Validation API ──────────────────────────────────────────────

async def validate_weekly_data(
    symbol: str,
    start_ts: datetime,
    end_ts: datetime,
    mongo_manager=None,
) -> dict:
    """
    Compare internal weekly candles against Twelve Data.

    Args:
        symbol:        Canonical symbol, e.g. "XAUUSD".
        start_ts:      Start of the week (UTC-aware datetime).
        end_ts:        End of the week (UTC-aware datetime).
        mongo_manager: MongoConnectionManager instance for DB access.
                       Falls back to ``marketmate.db.core.mongo_manager``
                       if not provided.

    Returns:
        {
            "passed":     bool,
            "differences": {"open_pct": float, "high_pct": float,
                            "low_pct": float, "close_pct": float},
            "internal":   {"open": float, "high": float,
                           "low": float, "close": float},
            "external":   {"open": float, "high": float,
                           "low": float, "close": float},
            "source":     "twelve_data" | None,
        }
    """
    threshold = cfg.recap.validation_threshold_pct

    # Resolve mongo_manager
    if mongo_manager is None:
        try:
            from marketmate.db.core import mongo_manager as _mm
            mongo_manager = _mm
        except ImportError:
            log.warning("validator_no_mongo_manager")
            mongo_manager = None

    # Ensure timezone-aware
    if start_ts.tzinfo is None:
        start_ts = start_ts.replace(tzinfo=timezone.utc)
    if end_ts.tzinfo is None:
        end_ts = end_ts.replace(tzinfo=timezone.utc)

    # Fetch internal data
    if mongo_manager is not None:
        internal_candles = await _fetch_internal_daily(symbol, start_ts, end_ts, mongo_manager)
    else:
        internal_candles = []

    internal_ohlc = _weekly_ohlc(internal_candles)

    if not internal_ohlc:
        log.warning("validator_no_internal_data",
                    symbol=symbol, start=str(start_ts), end=str(end_ts))
        return {
            "passed": True,  # can't validate without internal data — let it through
            "differences": {},
            "internal":    {},
            "external":    {},
            "source":      None,
        }

    async with aiohttp.ClientSession() as session:
        external_candles = await _fetch_td_daily(symbol, start_ts, end_ts, session)

    if not external_candles:
        # Twelve Data unreachable — pass through to not block recap
        log.warning("validator_external_unavailable",
                    symbol=symbol, hint="recap will proceed without cross-check")
        return {
            "passed":      True,
            "differences": {},
            "internal":    internal_ohlc,
            "external":    {},
            "source":      None,
        }

    external_ohlc = _weekly_ohlc(external_candles)

    differences = {
        "open_pct":  round(_pct_diff(internal_ohlc["open"],  external_ohlc["open"]),  4),
        "high_pct":  round(_pct_diff(internal_ohlc["high"],  external_ohlc["high"]),  4),
        "low_pct":   round(_pct_diff(internal_ohlc["low"],   external_ohlc["low"]),   4),
        "close_pct": round(_pct_diff(internal_ohlc["close"], external_ohlc["close"]), 4),
    }

    passed = all(v <= threshold for v in differences.values())

    log.info(
        "validator_result",
        symbol=symbol,
        passed=passed,
        threshold_pct=threshold,
        **differences,
    )

    return {
        "passed":      passed,
        "differences": differences,
        "internal":    internal_ohlc,
        "external":    external_ohlc,
        "source":      "twelve_data",
    }
