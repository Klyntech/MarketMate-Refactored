"""
signal_engine/strategy/liquidity.py
─────────────────────────────────
Gate 5: Liquidity Sweep Detection

Migrated from strategy/liquidity.py with updated imports to use
signal_engine.strategy.models.

Strict, deterministic logic — no ambiguity, no hardcoded thresholds.

Swing definition (strict per-side):
  Swing HIGH at index i:
    df["high"][i] > ALL highs in [i-N … i-1] AND > ALL highs in [i+1 … i+N]
  Swing LOW at index i:
    df["low"][i]  < ALL lows  in [i-N … i-1] AND < ALL lows  in [i+1 … i+N]
  N = cfg.data.swing_lookback

Sweep conditions:
  Bullish bias → sweep of swing LOW  (wick below level, trapped shorts)
  Bearish bias → sweep of swing HIGH (wick above level, trapped longs)

Sweep strength:
  "strong" — candle CLOSES back inside the level after sweeping it
  "weak"   — wick only, candle closes beyond the level

Distance filter:
  |wick_extreme − level| ≥ level × min_sweep_pct
  Rejects micro-sweeps from spread / rounding noise.

Freshness:
  Sweep candle must be within the last sweep_freshness_candles candles.
  Swing levels are computed on candles BEFORE the freshness window (no look-ahead).

Returns SweepResult | None.
"""

from __future__ import annotations
from typing import Optional

import pandas as pd

from signal_engine.core.config import cfg
from signal_engine.strategy.models import SweepResult
from signal_engine.core.logger import get_logger

log = get_logger("liquidity")


# ─── Public API ───────────────────────────────────────────────────────────────

def detect_sweep(
    df: pd.DataFrame,
    bias: str,
    lookback: int = None,
    freshness_candles: int = None,
    min_sweep_pct: float = None,
) -> Optional[SweepResult]:
    """
    Detect a recent, valid liquidity sweep aligned with the HTF bias.

    Parameters
    ----------
    df                : validated OHLCV DataFrame (H4 recommended)
    bias              : "bullish" | "bearish"
    lookback          : candles each side for strict swing detection
    freshness_candles : only accept sweeps within last N candles
    min_sweep_pct     : minimum wick-distance as fraction of level price

    Returns
    -------
    SweepResult | None
    """
    lookback          = lookback          if lookback          is not None else cfg.data.swing_lookback
    freshness_candles = freshness_candles if freshness_candles is not None else cfg.strategy.sweep_freshness_candles
    min_sweep_pct     = min_sweep_pct     if min_sweep_pct     is not None else cfg.strategy.min_sweep_pct

    n = len(df)
    min_required = lookback * 2 + freshness_candles + 1
    if n < min_required:
        log.debug("insufficient_candles_for_sweep", have=n, need=min_required)
        return None

    # Swing levels computed ONLY on the structure window (before freshness zone).
    # This is the look-ahead guard: no future candle data enters swing detection.
    structure_end = n - freshness_candles
    swing_highs = _strict_swing_highs(df.iloc[:structure_end], lookback)
    swing_lows  = _strict_swing_lows(df.iloc[:structure_end], lookback)

    log.debug("swing_levels_computed",
              bias=bias, swing_highs=len(swing_highs),
              swing_lows=len(swing_lows), structure_window=structure_end)

    for i in range(n - 1, structure_end - 1, -1):
        candle      = df.iloc[i]
        candles_ago = n - 1 - i

        if bias == "bullish":
            if not swing_lows:
                break
            # Target: highest swing low (nearest relevant level)
            level  = swing_lows[-1]
            result = _evaluate_low_sweep(candle, level, i, candles_ago, min_sweep_pct)
            if result:
                log.info("sweep_detected", **_log_fields(result))
                return result

        elif bias == "bearish":
            if not swing_highs:
                break
            # Target: lowest swing high (nearest relevant level)
            level  = swing_highs[0]
            result = _evaluate_high_sweep(candle, level, i, candles_ago, min_sweep_pct)
            if result:
                log.info("sweep_detected", **_log_fields(result))
                return result

    log.debug("no_sweep_found", bias=bias,
              swing_highs=len(swing_highs), swing_lows=len(swing_lows))
    return None


# ─── Strict swing point detection ────────────────────────────────────────────

def _strict_swing_highs(df: pd.DataFrame, lookback: int) -> list[float]:
    """
    Return sorted list of swing high prices.
    A swing high at index i requires df["high"][i] to be strictly greater than
    all highs in [i-lookback … i-1] AND all highs in [i+1 … i+lookback].
    """
    highs: list[float] = []
    n = len(df)
    for i in range(lookback, n - lookback):
        h      = float(df["high"].iloc[i])
        before = float(df["high"].iloc[i - lookback: i].max())
        after  = float(df["high"].iloc[i + 1: i + lookback + 1].max())
        if h > before and h > after:
            highs.append(h)
    return sorted(highs)


def _strict_swing_lows(df: pd.DataFrame, lookback: int) -> list[float]:
    """
    Return sorted list of swing low prices.
    A swing low at index i requires df["low"][i] to be strictly less than
    all lows in [i-lookback … i-1] AND all lows in [i+1 … i+lookback].
    """
    lows: list[float] = []
    n = len(df)
    for i in range(lookback, n - lookback):
        l      = float(df["low"].iloc[i])
        before = float(df["low"].iloc[i - lookback: i].min())
        after  = float(df["low"].iloc[i + 1: i + lookback + 1].min())
        if l < before and l < after:
            lows.append(l)
    return sorted(lows)


# ─── Sweep evaluators ─────────────────────────────────────────────────────────

def _evaluate_low_sweep(
    candle: pd.Series,
    level: float,
    idx: int,
    candles_ago: int,
    min_sweep_pct: float,
) -> Optional[SweepResult]:
    """Return SweepResult if candle's low swept below `level` with sufficient distance."""
    low = float(candle["low"])
    if low >= level:
        return None

    sweep_distance = level - low
    if sweep_distance < level * min_sweep_pct:
        return None   # micro-sweep below threshold — reject

    close_inside = float(candle["close"]) > level
    return SweepResult(
        type             = "buy",
        direction        = "bullish",
        swept_level      = level,
        sweep_candle_idx = idx,
        close_inside     = close_inside,
        strength         = "strong" if close_inside else "weak",
        candles_ago      = candles_ago,
        sweep_distance   = round(sweep_distance, 6),
    )


def _evaluate_high_sweep(
    candle: pd.Series,
    level: float,
    idx: int,
    candles_ago: int,
    min_sweep_pct: float,
) -> Optional[SweepResult]:
    """Return SweepResult if candle's high swept above `level` with sufficient distance."""
    high = float(candle["high"])
    if high <= level:
        return None

    sweep_distance = high - level
    if sweep_distance < level * min_sweep_pct:
        return None   # micro-sweep below threshold — reject

    close_inside = float(candle["close"]) < level
    return SweepResult(
        type             = "sell",
        direction        = "bearish",
        swept_level      = level,
        sweep_candle_idx = idx,
        close_inside     = close_inside,
        strength         = "strong" if close_inside else "weak",
        candles_ago      = candles_ago,
        sweep_distance   = round(sweep_distance, 6),
    )


# ─── Log helper ───────────────────────────────────────────────────────────────

def _log_fields(r: SweepResult) -> dict:
    return {
        "type":           r.type,
        "direction":      r.direction,
        "level":          round(r.swept_level, 4),
        "strength":       r.strength,
        "close_inside":   r.close_inside,
        "sweep_distance": r.sweep_distance,
        "candles_ago":    r.candles_ago,
    }
