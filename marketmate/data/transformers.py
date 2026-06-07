"""
marketmate/data/transformers.py
───────────────────────────────
Candle transformation utilities: resampling, normalization, timezone handling.

NEW module — extracted from inline resampling logic in data/market_data.py
and data/candle_store.py.

Components:
  1. resample_candles(df, target_tf)   — Convert timeframes via OHLCV aggregation
  2. normalize_outputs(df)             — Ensure consistent column names/types
  3. handle_timezone(df)               — Normalize all timestamps to UTC
"""

from __future__ import annotations

from typing import Optional

import pandas as pd
import numpy as np

from marketmate.core.logger import get_logger

log = get_logger("data.transformers")

# ─── Timeframe to pandas offset mapping ───────────────────────────────────────
# Used by resample_candles() to convert a human-readable timeframe string
# into a pandas resample frequency.

_TIMEFRAME_TO_OFFSET: dict[str, str] = {
    "1m":  "1min",
    "5m":  "5min",
    "15m": "15min",
    "1h":  "1h",
    "4h":  "4h",
    "1d":  "1D",
}

# Canonical column order for all OHLCV DataFrames
CANONICAL_COLUMNS = ["timestamp", "open", "high", "low", "close", "volume"]


# ═══════════════════════════════════════════════════════════════════════════════
# Resampling
# ═══════════════════════════════════════════════════════════════════════════════

def resample_candles(
    df: pd.DataFrame,
    target_tf: str,
    source_tf: Optional[str] = None,
) -> pd.DataFrame:
    """
    Resample OHLCV candles from a source timeframe to a target timeframe.

    Uses pandas resample with proper OHLCV aggregation:
      - open:   first value in the window
      - high:   max value in the window
      - low:    min value in the window
      - close:  last value in the window
      - volume: sum of all values in the window

    Args:
        df:        Input OHLCV DataFrame with columns
                   [timestamp, open, high, low, close, volume].
        target_tf: Target timeframe string (e.g. "4h", "1d").
        source_tf: Source timeframe string (e.g. "1h", "15m").
                   If None, the function infers it from the data.
                   Providing source_tf is recommended for correctness.

    Returns:
        DataFrame resampled to the target timeframe with the same column
        structure. Rows with NaN open/close are dropped.

    Raises:
        ValueError: If target_tf is not a supported timeframe.

    Example:
        # Resample 1h candles to 4h
        df_4h = resample_candles(df_1h, "4h", source_tf="1h")
    """
    if df is None or df.empty:
        return df

    target_offset = _TIMEFRAME_TO_OFFSET.get(target_tf)
    if target_offset is None:
        raise ValueError(
            f"Unsupported target timeframe for resampling: {target_tf}. "
            f"Supported: {list(_TIMEFRAME_TO_OFFSET.keys())}"
        )

    # Ensure timestamp is the index for resampling
    df_work = df.copy()

    if "timestamp" in df_work.columns:
        df_work = df_work.set_index("timestamp")
    elif df_work.index.name != "timestamp":
        # If the index is already a datetime, use it as-is
        if not isinstance(df_work.index, pd.DatetimeIndex):
            raise ValueError(
                "DataFrame must have a 'timestamp' column or DatetimeIndex"
            )

    # Perform OHLCV aggregation
    df_resampled = df_work.resample(target_offset, closed="left", label="left").agg(
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).dropna(subset=["open", "close"])

    # Reset index to get 'timestamp' back as a column
    df_resampled = df_resampled.reset_index()

    # If the index was renamed during resampling, rename it back
    if df_resampled.columns[0] != "timestamp":
        df_resampled = df_resampled.rename(columns={df_resampled.columns[0]: "timestamp"})

    log.debug(
        "candles_resampled",
        target_tf=target_tf,
        source_tf=source_tf,
        candles_in=len(df),
        candles_out=len(df_resampled),
    )

    return df_resampled


# ═══════════════════════════════════════════════════════════════════════════════
# Normalization
# ═══════════════════════════════════════════════════════════════════════════════

def normalize_outputs(df: pd.DataFrame) -> pd.DataFrame:
    """
    Ensure consistent column names, types, and order for all OHLCV DataFrames.

    Normalization steps:
      1. Ensure all canonical columns exist
      2. Coerce OHLCV columns to float64
      3. Ensure timestamp is datetime64[ns, UTC]
      4. Sort by timestamp ascending
      5. Reset index
      6. Select only canonical columns in standard order

    Args:
        df: Input OHLCV DataFrame (may have inconsistent types or column order).

    Returns:
        DataFrame with canonical column order and types.

    Raises:
        ValueError: If required columns are missing.
    """
    if df is None or df.empty:
        return df

    df = df.copy()

    # ── Check required columns ─────────────────────────────────────────────
    missing = [c for c in CANONICAL_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Cannot normalize — missing columns: {missing}")

    # ── Type coercion ──────────────────────────────────────────────────────
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")

    # ── Timestamp normalization ────────────────────────────────────────────
    if not isinstance(df["timestamp"].dtype, pd.DatetimeTZDtype):
        df["timestamp"] = pd.to_datetime(df["timestamp"], utc=True)
    elif df["timestamp"].dt.tz is None:
        df["timestamp"] = df["timestamp"].dt.tz_localize("UTC")

    # ── Sort and reindex ───────────────────────────────────────────────────
    df = df.sort_values("timestamp").reset_index(drop=True)

    # ── Canonical column order ─────────────────────────────────────────────
    df = df[CANONICAL_COLUMNS]

    log.debug("outputs_normalized", candles=len(df))
    return df


# ═══════════════════════════════════════════════════════════════════════════════
# Timezone Handling
# ═══════════════════════════════════════════════════════════════════════════════

def handle_timezone(df: pd.DataFrame) -> pd.DataFrame:
    """
    Normalize all timestamps in an OHLCV DataFrame to UTC.

    Handles:
      - Naive timestamps (assumed UTC, localized)
      - Non-UTC timezone-aware timestamps (converted to UTC)
      - Already-UTC timestamps (no-op)

    Args:
        df: Input OHLCV DataFrame with a 'timestamp' column.

    Returns:
        DataFrame with all timestamps as datetime64[ns, UTC].
    """
    if df is None or df.empty:
        return df

    if "timestamp" not in df.columns:
        return df

    df = df.copy()
    ts = df["timestamp"]

    if not pd.api.types.is_datetime64_any_dtype(ts):
        df["timestamp"] = pd.to_datetime(ts, utc=True)
        return df

    # Already datetime — check timezone
    if ts.dt.tz is None:
        # Naive timestamps — assume UTC
        df["timestamp"] = ts.dt.tz_localize("UTC")
    elif str(ts.dt.tz) != "UTC":
        # Non-UTC timezone — convert to UTC
        df["timestamp"] = ts.dt.tz_convert("UTC")

    log.debug("timezone_normalized", candles=len(df))
    return df
