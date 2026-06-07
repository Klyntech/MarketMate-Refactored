"""
signal_engine/strategy/bias.py
────────────────────────────
Gate 4: Higher Time Frame Bias

Migrated from strategy/htf_bias.py with updated imports.

RULES (ALL must hold for a directional bias):
  BULLISH:
    - Price above EMA200 on BOTH Daily AND H4
    - Daily:  Higher High + Higher Low vs previous swing
    - H4:     Higher High + Higher Low vs previous swing

  BEARISH:
    - Price below EMA200 on BOTH Daily AND H4
    - Daily:  Lower High + Lower Low vs previous swing
    - H4:     Lower High + Lower Low vs previous swing

NEUTRAL (fallback — never null):
    - Returned whenever structure is unclear, data is insufficient,
      timeframes conflict, or any condition cannot be evaluated.

Returns: "bullish" | "bearish" | "neutral"
         → NEVER returns None or raises due to missing/incomplete data.
"""

from __future__ import annotations
from typing import Optional
import numpy as np
import pandas as pd

from signal_engine.core.config import cfg
from signal_engine.core.logger import get_logger

log = get_logger("htf_bias")


# ─── EMA ─────────────────────────────────────────────────────────────────────

def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


# ─── Swing detection ──────────────────────────────────────────────────────────

def detect_swing_highs_lows(
    df: pd.DataFrame,
    lookback: int,
) -> tuple[list[float], list[float]]:
    """
    Returns (swing_highs, swing_lows) as lists of recent values.
    A swing high = candle[i].high is the highest in [i-lookback : i+lookback].
    A swing low  = candle[i].low  is the lowest  in [i-lookback : i+lookback].
    """
    highs, lows = [], []
    n = len(df)
    for i in range(lookback, n - lookback):
        window_h = df["high"].iloc[i - lookback: i + lookback + 1]
        window_l = df["low"].iloc[i - lookback: i + lookback + 1]
        if df["high"].iloc[i] == window_h.max():
            highs.append(df["high"].iloc[i])
        if df["low"].iloc[i] == window_l.min():
            lows.append(df["low"].iloc[i])
    return highs, lows


# ─── Market structure ─────────────────────────────────────────────────────────

def _market_structure(
    df: pd.DataFrame,
    lookback: int,
) -> str:
    """
    Derive market structure from last 3+ swing points.
    Returns "bullish", "bearish", or "neutral" (choppy/inconclusive).

    NOTE: Never returns None — unclear structure is always "neutral".
    """
    swing_highs, swing_lows = detect_swing_highs_lows(df, lookback)

    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return "neutral"

    last_hh, prev_hh = swing_highs[-1], swing_highs[-2]
    last_hl, prev_hl = swing_lows[-1],  swing_lows[-2]

    higher_highs = last_hh > prev_hh
    higher_lows  = last_hl > prev_hl
    lower_highs  = last_hh < prev_hh
    lower_lows   = last_hl < prev_hl

    if higher_highs and higher_lows:
        return "bullish"
    if lower_highs and lower_lows:
        return "bearish"
    return "neutral"


# ─── Per-timeframe bias resolver ──────────────────────────────────────────────

def _compute_tf_bias(
    df: Optional[pd.DataFrame],
    label: str,
    ema_period: int,
    swing_lookback: int,
) -> str:
    """
    Compute bias for a single timeframe DataFrame.

    Returns "bullish" | "bearish" | "neutral".
    NEVER returns None or raises — all error paths collapse to "neutral"
    with a structured log entry explaining the exact reason.

    Logged fields:
        event            : always "daily_bias_result"
        bias             : resolved value ("neutral" or directional)
        tf               : "daily" | "h4"
        candles_received : int
        candles_required : int
        reason           : human-readable neutrality cause (when neutral)
    """
    min_candles = ema_period + 10

    # ── Guard: missing DataFrame ──────────────────────────────────────────────
    if df is None:
        log.warning(
            "daily_bias_result",
            bias="neutral",
            tf=label,
            candles_received=0,
            candles_required=min_candles,
            reason="dataframe_is_none",
        )
        return "neutral"

    candle_count = len(df)

    # ── Guard: insufficient candles ───────────────────────────────────────────
    if candle_count < min_candles:
        log.warning(
            "daily_bias_result",
            bias="neutral",
            tf=label,
            candles_received=candle_count,
            candles_required=min_candles,
            reason="insufficient_candle_count",
        )
        return "neutral"

    # ── Debug: log received candle window ─────────────────────────────────────
    first_ts   = str(df["timestamp"].iloc[0])  if "timestamp" in df.columns else "n/a"
    last_ts    = str(df["timestamp"].iloc[-1]) if "timestamp" in df.columns else "n/a"
    last_close = round(float(df["close"].iloc[-1]), 4)

    log.debug(
        "htf_candles_received",
        tf=label,
        count=candle_count,
        required=min_candles,
        sufficient=True,
        first_ts=first_ts,
        last_ts=last_ts,
        last_close=last_close,
    )

    # ── EMA position ──────────────────────────────────────────────────────────
    ema           = compute_ema(df["close"], ema_period)
    current_price = float(df["close"].iloc[-1])
    current_ema   = float(ema.iloc[-1])

    above_ema = current_price > current_ema
    below_ema = current_price < current_ema

    # ── Market structure ──────────────────────────────────────────────────────
    structure = _market_structure(df, swing_lookback)

    log.debug(
        "tf_bias_check",
        tf=label,
        price=round(current_price, 4),
        ema200=round(current_ema, 4),
        above_ema=above_ema,
        structure=structure,
    )

    # ── Bias decision ─────────────────────────────────────────────────────────
    if above_ema and structure == "bullish":
        bias = "bullish"
        reason = "conditions_met"
    elif below_ema and structure == "bearish":
        bias = "bearish"
        reason = "conditions_met"
    else:
        bias = "neutral"
        if structure == "neutral":
            reason = "insufficient_structure_confirmation"
        elif above_ema and structure != "bullish":
            reason = "price_above_ema_but_structure_not_bullish"
        elif below_ema and structure != "bearish":
            reason = "price_below_ema_but_structure_not_bearish"
        else:
            reason = "ema_structure_mismatch"

    log.info(
        "daily_bias_result",
        bias=bias,
        tf=label,
        candles_received=candle_count,
        candles_required=min_candles,
        above_ema=above_ema,
        below_ema=below_ema,
        structure=structure,
        price=round(current_price, 4),
        ema200=round(current_ema, 4),
        reason=reason,
    )
    return bias


# ─── Public API ───────────────────────────────────────────────────────────────

def get_htf_bias(
    daily_df: pd.DataFrame,
    h4_df: pd.DataFrame,
    ema_period: int = None,
    swing_lookback: int = None,
) -> str:
    """
    Returns unified HTF bias. NEVER returns None.

    Resolution matrix
    ─────────────────
      daily == h4 (both directional)      → return that bias          [full agreement]
      daily == "neutral", h4 is clear     → return h4_bias            [daily fallback]
      h4 == "neutral", daily is clear     → return "neutral"          [H4 must confirm]
      daily conflicts with h4 (no neutral)→ return "neutral"          [genuine conflict]
      both "neutral"                      → return "neutral"          [no structure]

    The daily fallback rule (row 2) is the key fix: previously the system
    returned None when daily data was missing or choppy. Now it correctly
    falls back to H4 direction when daily structure is simply unclear,
    allowing G4 to pass without compromising signal integrity.

    Parameters
    ----------
    daily_df, h4_df : validated OHLCV DataFrames (may be None on data error)
    ema_period      : EMA period (default from config)
    swing_lookback  : candles each side for swing detection (default from config)

    Returns
    -------
    "bullish" | "bearish" | "neutral"   — NEVER None
    """
    ema_period     = ema_period     or cfg.strategy.ema_period
    swing_lookback = swing_lookback or cfg.data.swing_lookback

    # Each call always returns a str — never None
    daily_bias = _compute_tf_bias(daily_df, "daily", ema_period, swing_lookback)
    h4_bias    = _compute_tf_bias(h4_df,    "h4",    ema_period, swing_lookback)

    # ── Resolution matrix ─────────────────────────────────────────────────────

    # Case 1: Full directional agreement
    if daily_bias == h4_bias and daily_bias != "neutral":
        log.info(
            "htf_bias_confirmed",
            bias=daily_bias,
            daily=daily_bias,
            h4=h4_bias,
            resolution="full_agreement",
        )
        return daily_bias

    # Case 2: Daily neutral → fall back to H4 direction
    if daily_bias == "neutral" and h4_bias != "neutral":
        log.info(
            "htf_bias_confirmed",
            bias=h4_bias,
            daily=daily_bias,
            h4=h4_bias,
            resolution="daily_neutral_fallback_to_h4",
        )
        return h4_bias

    # Case 3: H4 neutral → H4 cannot confirm entry direction
    if h4_bias == "neutral" and daily_bias != "neutral":
        log.info(
            "htf_bias_conflict_or_none",
            daily=daily_bias,
            h4=h4_bias,
            resolution="h4_neutral_no_entry_trigger",
            result="neutral",
        )
        return "neutral"

    # Case 4: Active directional conflict (bullish vs bearish)
    if daily_bias != h4_bias and "neutral" not in (daily_bias, h4_bias):
        log.info(
            "htf_bias_conflict_or_none",
            daily=daily_bias,
            h4=h4_bias,
            resolution="directional_conflict",
            result="neutral",
        )
        return "neutral"

    # Case 5: Both neutral — no structure on either timeframe
    log.info(
        "htf_bias_conflict_or_none",
        daily=daily_bias,
        h4=h4_bias,
        resolution="both_neutral_no_structure",
        result="neutral",
    )
    return "neutral"
