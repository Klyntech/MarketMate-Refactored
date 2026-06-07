"""
MM-023: LB-01 — London Breakout
════════════════════════════════
Detects compressed Asian range (00:00-07:00 GMT) and trades the
breakout at London open. Compression filter ensures only tight
ranges trigger signals for explosive momentum potential.

Best instruments: EURUSD, GBPUSD, XAUUSD
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class LondonBreakout(Strategy):
    STRATEGY_ID = "MM-023"
    STRATEGY_NAME = "London Breakout"
    STRATEGY_TYPE = "breakout"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "atr_period": 14,
            "compression_pct": 30,       # Asian range must be < this percentile of 20-day ATR
            "tp1_mult": 1.5,             # TP1 = Asian range width * this, from entry
            "tp2_mult": 2.5,             # TP2 = Asian range width * this, from entry
            "min_rr": 1.0,
            "session_filter": True,
            "max_daily_trades": 1,
            "compression_lookback": 20,   # Days to compute ATR percentile
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "atr_period": (10, 20, 1),
            "compression_pct": (20, 40, 5),
            "tp1_mult": (1.0, 2.5, 0.25),
            "tp2_mult": (2.0, 4.0, 0.5),
            "min_rr": (0.5, 2.0, 0.25),
            "compression_lookback": (10, 30, 5),
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
        daily_trades = 0
        last_date = None

        # ── State tracked per day ──────────────────────────────────
        asian_high = None
        asian_low = None
        asian_range_defined = False
        daily_atr_history = []           # ATR values at end-of-day for percentile

        # We need at least enough bars for ATR warmup and lookback
        min_start = p['atr_period'] + 20

        for i in range(min_start, len(df) - 1):
            if not hasattr(df.index, 'hour'):
                continue

            ts = df.index[i]
            h = ts.hour
            wd = ts.weekday()
            cur_date = ts.date() if hasattr(ts, 'date') else None

            # ── New day reset ──────────────────────────────────────
            if cur_date != last_date:
                daily_trades = 0
                asian_high = None
                asian_low = None
                asian_range_defined = False
                last_date = cur_date

                # Record prior day's final ATR for compression check
                # Look back and collect daily ATR snapshots
                daily_atr_history = []
                seen_dates = set()
                for j in range(max(0, i - p['compression_lookback'] * 24), i):
                    d = df.index[j].date() if hasattr(df.index[j], 'date') else None
                    if d is not None and d not in seen_dates and not pd.isna(atr_vals[j]):
                        seen_dates.add(d)
                        daily_atr_history.append(atr_vals[j])

            # ── Session gate ───────────────────────────────────────
            if p['session_filter']:
                # Only operate on weekdays
                if wd >= 5:
                    continue
                # Only between 07:00 and 09:30 GMT for breakout window
                if not (7 <= h < 10):  # 07:00-09:59 to include 09:30 bar
                    # Still track Asian range outside session
                    pass
                else:
                    # Time stop: no trade after 09:30
                    if h == 9 and ts.minute > 30:
                        continue

            if pd.isna(atr_vals[i]):
                continue
            atr_val = atr_vals[i]

            # ── Build Asian range (00:00-07:00 GMT) ───────────────
            if 0 <= h < 7 and wd < 5:
                if asian_high is None:
                    asian_high = highs[i]
                    asian_low = lows[i]
                else:
                    asian_high = max(asian_high, highs[i])
                    asian_low = min(asian_low, lows[i])
                continue  # Don't generate signals during Asian session

            if asian_high is None or asian_low is None:
                continue

            asian_range_width = asian_high - asian_low
            if asian_range_width <= 0:
                continue

            # ── Compression check: Asian range < compression_pct percentile of daily ATR ──
            if len(daily_atr_history) >= 5:
                atr_threshold = np.percentile(daily_atr_history, p['compression_pct'])
            else:
                # Not enough history — skip compression check, use raw ATR
                atr_threshold = atr_val

            if asian_range_width >= atr_threshold:
                # Range too wide — no compression, skip
                continue

            # ── Breakout detection (07:00-09:30 GMT) ──────────────
            if p['session_filter'] and not (7 <= h <= 9):
                continue
            if h == 9 and ts.minute > 30:
                continue
            if wd >= 5:
                continue
            if daily_trades >= p['max_daily_trades']:
                continue

            # Long breakout: candle closes above Asian high
            if closes[i] > asian_high:
                entry = closes[i]
                sl = asian_low                     # Opposite boundary
                range_width = asian_range_width

                tp1 = entry + range_width * p['tp1_mult']
                tp2 = entry + range_width * p['tp2_mult']
                risk = entry - sl
                reward = tp1 - entry
                rr = reward / risk if risk > 0 else 0

                if rr >= p['min_rr']:
                    signals.append(self._sig(
                        symbol, "BUY", entry, sl, tp1, df, i,
                        tp2=tp2, rr=rr,
                        metadata={
                            "asian_high": float(asian_high),
                            "asian_low": float(asian_low),
                            "asian_range_width": float(range_width),
                            "atr_threshold": float(atr_threshold),
                            "breakout_type": "above_asian_high",
                        }
                    ))
                    daily_trades += 1

            # Short breakout: candle closes below Asian low
            elif closes[i] < asian_low:
                entry = closes[i]
                sl = asian_high                    # Opposite boundary
                range_width = asian_range_width

                tp1 = entry - range_width * p['tp1_mult']
                tp2 = entry - range_width * p['tp2_mult']
                risk = sl - entry
                reward = entry - tp1
                rr = reward / risk if risk > 0 else 0

                if rr >= p['min_rr']:
                    signals.append(self._sig(
                        symbol, "SELL", entry, sl, tp1, df, i,
                        tp2=tp2, rr=rr,
                        metadata={
                            "asian_high": float(asian_high),
                            "asian_low": float(asian_low),
                            "asian_range_width": float(range_width),
                            "atr_threshold": float(atr_threshold),
                            "breakout_type": "below_asian_low",
                        }
                    ))
                    daily_trades += 1

        return signals
