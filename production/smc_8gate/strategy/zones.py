"""
signal_engine/strategy/zones.py
─────────────────────────────
Gate 6: Entry Zone Identification

Migrated from strategy/entry_zones.py with updated imports to use
signal_engine.strategy.models.

Two valid zone types:

A) ORDER BLOCK (OB)
   - Last opposing candle before a strong displacement move
   - Displacement = N consecutive candles in the same direction after the OB
   - Zone: [low, high] of the OB candle
   - Expiry: invalidated after ob_expiry_candles candles re-enter the zone

B) FAIR VALUE GAP (FVG)
   - Definition (canonical 3-candle pattern):
       Bullish FVG: candle1.high < candle3.low   (gap above c1, below c3)
       Bearish FVG: candle1.low  > candle3.high  (gap below c1, above c3)
     where candle2 is the impulse candle (ignored for zone boundaries).
   - Minimum gap size: (gap_high - gap_low) / candle2.close ≥ min_fvg_pct
   - Only FVGs formed within the last fvg_freshness_candles are accepted
   - candle3 must not be the current (last) candle — needs to be complete

All thresholds read from cfg (config/settings.py) — none hardcoded.
"""

from __future__ import annotations
from typing import Optional

import pandas as pd

from signal_engine.core.config import cfg
from signal_engine.strategy.models import EntryZone
from signal_engine.core.logger import get_logger

log = get_logger("entry_zones")


# ─── Order Block ─────────────────────────────────────────────────────────────

def find_order_block(
    df: pd.DataFrame,
    direction: str,
    min_displacement_candles: int = None,
    expiry_candles: int = None,
    search_lookback: int = 20,
) -> Optional[EntryZone]:
    """
    Find the most recent valid Order Block.

    Bullish OB: last bearish candle (close < open) before a bullish displacement.
    Bearish OB: last bullish candle (close > open) before a bearish displacement.
    Zone bounds = [low, high] of the OB candle.
    """
    min_displacement_candles = (
        min_displacement_candles or cfg.strategy.min_ob_displacement_candles
    )
    expiry_candles = expiry_candles or cfg.strategy.ob_expiry_candles

    n            = len(df)
    search_start = max(0, n - search_lookback)

    for i in range(n - min_displacement_candles - 2, search_start, -1):
        candle            = df.iloc[i]
        is_bullish_candle = float(candle["close"]) > float(candle["open"])
        is_bearish_candle = float(candle["close"]) < float(candle["open"])

        if direction == "bullish" and is_bearish_candle:
            if not _has_bullish_displacement(df, i + 1, min_displacement_candles):
                continue
            if _count_zone_entries(df, i + 1, float(candle["low"]),
                                   float(candle["high"])) >= expiry_candles:
                log.debug("ob_expired", idx=i)
                continue
            zone = EntryZone(
                zone_type    = "order_block",
                direction    = "bullish",
                zone_high    = float(candle["high"]),
                zone_low     = float(candle["low"]),
                candle_idx   = i,
                expiry_candle= i + expiry_candles,
            )
            log.info("order_block_found", direction="bullish",
                     zone_high=round(zone.zone_high, 4),
                     zone_low=round(zone.zone_low, 4), candle_idx=i)
            return zone

        elif direction == "bearish" and is_bullish_candle:
            if not _has_bearish_displacement(df, i + 1, min_displacement_candles):
                continue
            if _count_zone_entries(df, i + 1, float(candle["low"]),
                                   float(candle["high"])) >= expiry_candles:
                log.debug("ob_expired", idx=i)
                continue
            zone = EntryZone(
                zone_type    = "order_block",
                direction    = "bearish",
                zone_high    = float(candle["high"]),
                zone_low     = float(candle["low"]),
                candle_idx   = i,
                expiry_candle= i + expiry_candles,
            )
            log.info("order_block_found", direction="bearish",
                     zone_high=round(zone.zone_high, 4),
                     zone_low=round(zone.zone_low, 4), candle_idx=i)
            return zone

    log.debug("no_order_block_found", direction=direction)
    return None


# ─── Fair Value Gap ───────────────────────────────────────────────────────────

def find_fvg(
    df: pd.DataFrame,
    direction: str,
    min_gap_pct: float = None,
    freshness_candles: int = None,
) -> Optional[EntryZone]:
    """
    Detect the most recent valid Fair Value Gap (price imbalance).

    Pattern uses a strict 3-candle definition:
      candle1 = df.iloc[i - 1]   (before impulse)
      candle2 = df.iloc[i]       (impulse; used as price reference)
      candle3 = df.iloc[i + 1]   (after impulse; must be a completed candle)

    Bullish FVG condition: candle1.high < candle3.low
      Gap zone: [candle1.high, candle3.low]

    Bearish FVG condition: candle1.low > candle3.high
      Gap zone: [candle3.high, candle1.low]

    Rejection rule: gap size as % of candle2.close < min_fvg_pct → rejected.
    Freshness: only FVGs formed within the last `freshness_candles` are valid.
    Look-ahead guard: candle3 index must be ≤ n-2 (a complete, closed candle).
    """
    min_gap_pct       = min_gap_pct       if min_gap_pct       is not None else cfg.strategy.min_fvg_pct
    freshness_candles = freshness_candles if freshness_candles is not None else cfg.strategy.fvg_freshness_candles

    n = len(df)

    # candle3 at index i+1 must be a closed candle, so i+1 ≤ n-2 → i ≤ n-3
    # Search window: from (n - freshness_candles - 1) to (n - 3), newest first.
    search_end   = n - 2           # i+1 = n-1 is the current live candle — excluded
    search_start = max(1, n - freshness_candles - 1)

    for i in range(search_end - 1, search_start - 1, -1):
        c1 = df.iloc[i - 1]   # candle1
        c2 = df.iloc[i]       # candle2 (impulse)
        c3 = df.iloc[i + 1]   # candle3

        ref_price = float(c2["close"])
        if ref_price <= 0:
            continue

        if direction == "bullish":
            gap_low  = float(c1["high"])
            gap_high = float(c3["low"])

            # Strict condition: candle1.high MUST be strictly less than candle3.low
            if gap_high <= gap_low:
                continue

            gap_size_pct = (gap_high - gap_low) / ref_price
            if gap_size_pct < min_gap_pct:
                log.debug("fvg_rejected_too_small", direction="bullish",
                          gap_pct=round(gap_size_pct * 100, 4),
                          min_pct=round(min_gap_pct * 100, 4))
                continue

            zone = EntryZone(
                zone_type  = "fvg",
                direction  = "bullish",
                zone_high  = gap_high,
                zone_low   = gap_low,
                candle_idx = i,
            )
            log.info("fvg_found", direction="bullish",
                     gap_pct=round(gap_size_pct * 100, 3),
                     zone_high=round(gap_high, 4), zone_low=round(gap_low, 4),
                     candle_idx=i)
            return zone

        elif direction == "bearish":
            gap_high = float(c1["low"])
            gap_low  = float(c3["high"])

            # Strict condition: candle1.low MUST be strictly greater than candle3.high
            if gap_high <= gap_low:
                continue

            gap_size_pct = (gap_high - gap_low) / ref_price
            if gap_size_pct < min_gap_pct:
                log.debug("fvg_rejected_too_small", direction="bearish",
                          gap_pct=round(gap_size_pct * 100, 4),
                          min_pct=round(min_gap_pct * 100, 4))
                continue

            zone = EntryZone(
                zone_type  = "fvg",
                direction  = "bearish",
                zone_high  = gap_high,
                zone_low   = gap_low,
                candle_idx = i,
            )
            log.info("fvg_found", direction="bearish",
                     gap_pct=round(gap_size_pct * 100, 3),
                     zone_high=round(gap_high, 4), zone_low=round(gap_low, 4),
                     candle_idx=i)
            return zone

    log.debug("no_fvg_found", direction=direction, freshness=freshness_candles)
    return None


# ─── Public composite ────────────────────────────────────────────────────────

def find_entry_zone(
    df: pd.DataFrame,
    direction: str,
) -> Optional[EntryZone]:
    """
    Try Order Block first (higher institutional weight), then FVG.
    Returns the first valid zone found, or None.
    """
    zone = find_order_block(df, direction)
    if zone:
        return zone
    return find_fvg(df, direction)


# ─── Internal helpers ────────────────────────────────────────────────────────

def _has_bullish_displacement(df: pd.DataFrame, start_idx: int, candles: int) -> bool:
    end_idx  = min(start_idx + candles, len(df))
    segment  = df.iloc[start_idx:end_idx]
    if len(segment) < candles:
        return False
    bullish  = (segment["close"] > segment["open"]).sum()
    return bullish >= max(2, candles - 1)


def _has_bearish_displacement(df: pd.DataFrame, start_idx: int, candles: int) -> bool:
    end_idx  = min(start_idx + candles, len(df))
    segment  = df.iloc[start_idx:end_idx]
    if len(segment) < candles:
        return False
    bearish  = (segment["close"] < segment["open"]).sum()
    return bearish >= max(2, candles - 1)


def _count_zone_entries(
    df: pd.DataFrame,
    from_idx: int,
    zone_low: float,
    zone_high: float,
) -> int:
    """Count candles (since OB formed) that have re-entered the zone."""
    count = 0
    for i in range(from_idx, len(df)):
        c = df.iloc[i]
        if float(c["low"]) <= zone_high and float(c["high"]) >= zone_low:
            count += 1
    return count
