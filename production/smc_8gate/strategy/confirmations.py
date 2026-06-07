"""
signal_engine/strategy/confirmations.py
──────────────────────────────────────
Gate 7: Lower Time Frame Confirmation

Migrated from strategy/ltf_confirm.py with updated imports to use
signal_engine.strategy.models.

Requires ONE of the following on M5 or M15:

  Break of Structure (BOS):
    - In a bullish context: price breaks above the most recent swing high
      while still respecting the HTF bias (continuation)
    - In a bearish context: price breaks below the most recent swing low

  Change of Character (CHoCH):
    - In a bullish context: after making lower lows, price now makes a
      higher high → shift from bearish to bullish micro-structure
    - In a bearish context: after making higher highs, price now makes a
      lower low → shift from bullish to bearish micro-structure

Returns a ConfirmResult or None.
"""

from __future__ import annotations
from typing import Optional
import pandas as pd

from signal_engine.core.config import cfg
from signal_engine.strategy.models import ConfirmResult
from signal_engine.core.logger import get_logger

log = get_logger("ltf_confirm")


def check_ltf_confirmation(
    m15_df: pd.DataFrame,
    m5_df: pd.DataFrame,
    bias: str,
    lookback: int = None,
) -> Optional[ConfirmResult]:
    """
    Check both M15 and M5 for BOS or CHoCH.
    M15 checked first (stronger signal); M5 as fallback.
    """
    lookback = lookback or cfg.data.swing_lookback

    for tf, df in [("M15", m15_df), ("M5", m5_df)]:
        if df is None or len(df) < lookback * 2 + 5:
            log.debug("ltf_insufficient_data", tf=tf)
            continue

        result = _check_bos(df, bias, lookback, tf)
        if result:
            return result

        result = _check_choch(df, bias, lookback, tf)
        if result:
            return result

    log.debug("no_ltf_confirmation", bias=bias)
    return None


def _check_bos(
    df: pd.DataFrame,
    bias: str,
    lookback: int,
    tf: str,
) -> Optional[ConfirmResult]:
    """
    Break of Structure:
    - Bullish BOS: latest close breaks above the most recent swing high
    - Bearish BOS: latest close breaks below the most recent swing low
    """
    n = len(df)
    # Find swing levels in all but the last 3 candles (no look-ahead)
    structure = df.iloc[: n - 3]
    recent    = df.iloc[n - 3 : n]

    swing_highs = _swing_highs(structure, lookback)
    swing_lows  = _swing_lows(structure, lookback)

    if not swing_highs or not swing_lows:
        return None

    latest_close = float(df.iloc[-1]["close"])
    last_high    = swing_highs[-1]
    last_low     = swing_lows[-1]

    if bias == "bullish" and latest_close > last_high:
        log.info("BOS_confirmed", direction="bullish", tf=tf,
                 break_level=round(last_high, 4))
        return ConfirmResult(
            signal_type="BOS",
            direction="bullish",
            break_level=last_high,
            confirm_candle=n - 1,
            timeframe=tf,
        )

    if bias == "bearish" and latest_close < last_low:
        log.info("BOS_confirmed", direction="bearish", tf=tf,
                 break_level=round(last_low, 4))
        return ConfirmResult(
            signal_type="BOS",
            direction="bearish",
            break_level=last_low,
            confirm_candle=n - 1,
            timeframe=tf,
        )

    return None


def _check_choch(
    df: pd.DataFrame,
    bias: str,
    lookback: int,
    tf: str,
) -> Optional[ConfirmResult]:
    """
    Change of Character:
    - Bullish CHoCH: was making LH+LL, now makes HH → flip to bullish
    - Bearish CHoCH: was making HH+HL, now makes LL → flip to bearish
    """
    n = len(df)
    if n < lookback * 4 + 5:
        return None

    # Split into two halves: earlier (prior structure) and recent
    mid         = n // 2
    prior_df    = df.iloc[:mid]
    recent_df   = df.iloc[mid:]

    prior_highs = _swing_highs(prior_df, lookback)
    prior_lows  = _swing_lows(prior_df, lookback)
    recent_highs = _swing_highs(recent_df, lookback)
    recent_lows  = _swing_lows(recent_df, lookback)

    if not prior_highs or not prior_lows or not recent_highs or not recent_lows:
        return None

    prior_was_bearish = (
        prior_highs[-1] < prior_highs[0]  # lower highs in prior
        if len(prior_highs) >= 2 else False
    )
    prior_was_bullish = (
        prior_highs[-1] > prior_highs[0]
        if len(prior_highs) >= 2 else False
    )

    latest_high = recent_highs[-1]
    latest_low  = recent_lows[-1]

    # Bullish CHoCH: prior was bearish (LH+LL), now making a HH
    if bias == "bullish" and prior_was_bearish and latest_high > prior_highs[-1]:
        log.info("CHoCH_confirmed", direction="bullish", tf=tf,
                 break_level=round(prior_highs[-1], 4))
        return ConfirmResult(
            signal_type="CHoCH",
            direction="bullish",
            break_level=prior_highs[-1],
            confirm_candle=n - 1,
            timeframe=tf,
        )

    # Bearish CHoCH: prior was bullish (HH+HL), now making a LL
    if bias == "bearish" and prior_was_bullish and latest_low < prior_lows[-1]:
        log.info("CHoCH_confirmed", direction="bearish", tf=tf,
                 break_level=round(prior_lows[-1], 4))
        return ConfirmResult(
            signal_type="CHoCH",
            direction="bearish",
            break_level=prior_lows[-1],
            confirm_candle=n - 1,
            timeframe=tf,
        )

    return None


# ─── Internal helpers ────────────────────────────────────────────────────────

def _swing_highs(df: pd.DataFrame, lookback: int) -> list[float]:
    highs, n = [], len(df)
    for i in range(lookback, n - lookback):
        win = df["high"].iloc[i - lookback: i + lookback + 1]
        if float(df["high"].iloc[i]) == float(win.max()):
            highs.append(float(df["high"].iloc[i]))
    return highs


def _swing_lows(df: pd.DataFrame, lookback: int) -> list[float]:
    lows, n = [], len(df)
    for i in range(lookback, n - lookback):
        win = df["low"].iloc[i - lookback: i + lookback + 1]
        if float(df["low"].iloc[i]) == float(win.min()):
            lows.append(float(df["low"].iloc[i]))
    return lows
