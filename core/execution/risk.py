"""
marketmate/execution/risk.py
─────────────────────────────
Risk Management Module

Migrated from risk/manager.py. No logic changes — only import paths
updated to use the ``marketmate.`` package prefix.

Responsibilities:
  - ATR-based stop loss calculation
  - Position sizing (fixed % risk)
  - TP level derivation (1:1, 1:2, next liquidity)
  - RR validation
  - Drawdown state tracking
"""

from __future__ import annotations
from typing import Optional
import pandas as pd
import numpy as np

from signal_engine.core.config import cfg
from signal_engine.core.logger import get_logger

log = get_logger("risk")


class RiskManager:
    def __init__(self) -> None:
        self._account_size    = cfg.risk.account_size
        self._risk_pct        = cfg.risk.risk_per_trade_pct / 100.0
        self._atr_multiplier  = cfg.risk.atr_sl_multiplier
        self._atr_period      = cfg.risk.atr_period
        self._min_rr          = cfg.strategy.min_rr

    # ── ATR ──────────────────────────────────────────────────────────────────

    def compute_atr(self, df: pd.DataFrame) -> float:
        """
        Wilder's ATR over `atr_period` candles.
        Uses the last N rows.
        """
        period = self._atr_period
        if len(df) < period + 1:
            raise ValueError("Not enough candles to compute ATR.")

        high  = df["high"].values
        low   = df["low"].values
        close = df["close"].values

        tr = np.maximum(
            high[1:] - low[1:],
            np.maximum(
                np.abs(high[1:] - close[:-1]),
                np.abs(low[1:]  - close[:-1]),
            )
        )
        # Wilder's smoothing
        atr = np.zeros(len(tr))
        atr[0] = tr[:period].mean()
        for i in range(1, len(tr)):
            atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period

        result = float(atr[-1])
        log.debug("atr_computed", atr=round(result, 6))
        return result

    # ── RR Calculation ────────────────────────────────────────────────────────

    def calculate_rr(
        self,
        direction: str,
        entry_zone_high: float,
        entry_zone_low: float,
        current_price: float,
        h4_df: pd.DataFrame,
    ) -> Optional[dict]:
        """
        Derive entry, SL, TPs and validate RR.

        Entry:
          - BULLISH: midpoint of zone (conservative) or zone_low (aggressive)
          - BEARISH: midpoint of zone or zone_high

        Stop Loss:
          - ATR-based: entry ± (ATR × multiplier)
          - Must sit below zone_low (bull) or above zone_high (bear)

        Take Profits:
          - TP1: 1:1 RR
          - TP2: 1:2 RR
          - TP3: next significant liquidity level (swing high/low)
        """
        try:
            atr = self.compute_atr(h4_df)
        except ValueError as e:
            log.warning("atr_failed", error=str(e))
            return None

        zone_mid = (entry_zone_high + entry_zone_low) / 2

        if direction == "bullish":
            entry = zone_mid
            # SL: below zone low, padded by ATR × multiplier
            sl_raw    = entry_zone_low - (atr * self._atr_multiplier)
            sl        = min(sl_raw, entry_zone_low * 0.998)   # min 0.2% below zone
            sl_dist   = abs(entry - sl)
            tp1       = entry + sl_dist * 1.0
            tp2       = entry + sl_dist * 2.0
            # TP3 must be BEYOND TP2, not merely beyond entry.
            # Passing tp2 as the minimum threshold prevents returning
            # a level that is closer to entry than TP2 already is.
            tp3       = self._next_liquidity_level(h4_df, "bullish", entry, beyond=tp2)
            rr        = (tp2 - entry) / sl_dist if sl_dist > 0 else 0

        elif direction == "bearish":
            entry = zone_mid
            sl_raw    = entry_zone_high + (atr * self._atr_multiplier)
            sl        = max(sl_raw, entry_zone_high * 1.002)
            sl_dist   = abs(sl - entry)
            tp1       = entry - sl_dist * 1.0
            tp2       = entry - sl_dist * 2.0
            # TP3 must be BEYOND TP2 — below tp2 on a SELL, not just below entry.
            tp3       = self._next_liquidity_level(h4_df, "bearish", entry, beyond=tp2)
            rr        = (entry - tp2) / sl_dist if sl_dist > 0 else 0
        else:
            return None

        if rr < self._min_rr:
            log.debug("rr_insufficient", rr=round(rr, 2), min_rr=self._min_rr)
            return None

        return {
            "entry": round(entry, 6),
            "sl":    round(sl, 6),
            "tp1":   round(tp1, 6),
            "tp2":   round(tp2, 6),
            "tp3":   round(tp3, 6) if tp3 else None,
            "rr":    round(rr, 2),
            "atr":   round(atr, 6),
        }

    # ── Position Sizing ───────────────────────────────────────────────────────

    def position_size(self, stop_loss_distance: float) -> float:
        """
        Fixed fractional position sizing.
        Risk amount = account_size × risk_pct
        Position size = risk_amount / stop_loss_distance

        Returns size in base units (e.g., BTC for BTCUSDT).
        """
        if stop_loss_distance <= 0:
            log.warning("invalid_sl_distance", value=stop_loss_distance)
            return 0.0

        risk_amount   = self._account_size * self._risk_pct
        pos_size      = risk_amount / stop_loss_distance

        log.debug(
            "position_size_calc",
            account=self._account_size,
            risk_pct=cfg.risk.risk_per_trade_pct,
            risk_usd=round(risk_amount, 2),
            sl_dist=round(stop_loss_distance, 6),
            pos_size=round(pos_size, 6),
        )
        return round(pos_size, 6)

    # ── Next Liquidity (TP3) ──────────────────────────────────────────────────

    def _next_liquidity_level(
        self,
        df: pd.DataFrame,
        direction: str,
        entry: float,
        beyond: Optional[float] = None,
    ) -> Optional[float]:
        """
        Find the next significant swing high (bullish) or swing low (bearish)
        that sits beyond `beyond` (defaults to entry if not provided).

        FIX: `beyond` should be TP2 — ensures TP3 is always further than TP2
        and is never returned as a level inside or near the entry zone.

        Bullish: returns the lowest swing HIGH that is above `beyond`
        Bearish: returns the highest swing LOW that is below `beyond`
        """
        lookback = cfg.data.swing_lookback
        n        = len(df)

        highs, lows = [], []
        for i in range(lookback, n - lookback):
            win_h = df["high"].iloc[i - lookback: i + lookback + 1]
            win_l = df["low"].iloc[i - lookback: i + lookback + 1]
            if float(df["high"].iloc[i]) == float(win_h.max()):
                highs.append(float(df["high"].iloc[i]))
            if float(df["low"].iloc[i]) == float(win_l.min()):
                lows.append(float(df["low"].iloc[i]))

        if direction == "bullish":
            threshold  = beyond if beyond is not None else entry
            candidates = sorted([h for h in highs if h > threshold])
            return candidates[0] if candidates else None

        if direction == "bearish":
            threshold  = beyond if beyond is not None else entry
            candidates = sorted([l for l in lows if l < threshold], reverse=True)
            return candidates[0] if candidates else None

        return None
