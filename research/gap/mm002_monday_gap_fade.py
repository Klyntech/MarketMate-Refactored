"""
MM-002: MGF-01 — Monday Gap Fade
═════════════════════════════════
Fades the weekend gap between Friday close and Monday open.
Statistical edge: most gaps fill within 1-2 trading days.
Gap must exceed 0.3x ATR to filter noise.

Best instruments: EURUSD, GBPUSD, XAUUSD
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class MondayGapFade(Strategy):
    STRATEGY_ID = "MM-002"
    STRATEGY_NAME = "Monday Gap Fade"
    STRATEGY_TYPE = "mean_reversion"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "atr_period": 14,
            "min_gap_atr_mult": 0.3,      # Gap must exceed this * ATR
            "sl_atr_mult": 1.0,            # SL beyond entry by this * ATR
            "max_hold_bars": 36,           # Time stop ~2 trading days (H4)
            "max_daily_trades": 1,
            "session_filter": False,        # Gap trades happen at Monday open
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "min_gap_atr_mult": (0.2, 0.5, 0.05),
            "sl_atr_mult": (0.8, 1.5, 0.1),
        }

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        df = df.copy()
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        opens = df['open'].values

        atr_vals = self.atr(highs, lows, closes, p['atr_period'])

        signals = []
        last_date = None

        # Track the last Friday close seen
        friday_close = None
        # Track whether we already took a gap trade this week
        week_trade_taken = False
        current_week_number = None

        min_start = p['atr_period'] + 10

        for i in range(min_start, len(df) - 1):
            if not hasattr(df.index, 'weekday'):
                continue

            ts = df.index[i]
            wd = ts.weekday()
            cur_date = ts.date() if hasattr(ts, 'date') else None

            # ── Track Friday close ─────────────────────────────────
            if wd == 4:  # Friday
                # Keep updating to the last bar of Friday
                friday_close = closes[i]
                # Reset weekly trade flag for the upcoming week
                iso_week = ts.isocalendar()[1] if hasattr(ts, 'isocalendar') else None
                if iso_week != current_week_number:
                    current_week_number = iso_week
                    week_trade_taken = False

            # ── Skip non-Mondays ───────────────────────────────────
            if wd != 0:
                continue

            if friday_close is None:
                continue

            if pd.isna(atr_vals[i]):
                continue

            # ── One trade per week ─────────────────────────────────
            if week_trade_taken:
                continue

            atr_val = atr_vals[i]
            gap = opens[i] - friday_close       # Positive = gap up, negative = gap down
            gap_atr = abs(gap) / atr_val if atr_val > 0 else 0

            # Gap must be significant enough
            if gap_atr < p['min_gap_atr_mult']:
                continue

            entry = opens[i]

            # ── Gap up: short toward Friday close ──────────────────
            if gap > 0:
                sl = entry + atr_val * p['sl_atr_mult']
                tp = friday_close               # Gap fill target
                risk = sl - entry
                reward = entry - tp
                rr = reward / risk if risk > 0 else 0

                signals.append(self._sig(
                    symbol, "SELL", entry, sl, tp, df, i,
                    rr=rr,
                    metadata={
                        "friday_close": float(friday_close),
                        "gap_size": float(gap),
                        "gap_atr": float(gap_atr),
                        "gap_type": "up",
                        "max_hold_bars": p['max_hold_bars'],
                        "max_risk_pct": 0.5,
                    }
                ))
                week_trade_taken = True

            # ── Gap down: long toward Friday close ─────────────────
            elif gap < 0:
                sl = entry - atr_val * p['sl_atr_mult']
                tp = friday_close               # Gap fill target
                risk = entry - sl
                reward = tp - entry
                rr = reward / risk if risk > 0 else 0

                signals.append(self._sig(
                    symbol, "BUY", entry, sl, tp, df, i,
                    rr=rr,
                    metadata={
                        "friday_close": float(friday_close),
                        "gap_size": float(gap),
                        "gap_atr": float(gap_atr),
                        "gap_type": "down",
                        "max_hold_bars": p['max_hold_bars'],
                        "max_risk_pct": 0.5,
                    }
                ))
                week_trade_taken = True

        return signals
