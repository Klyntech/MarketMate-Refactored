"""
MM-003: KLF-01 — Key Level Defensive Fade
═══════════════════════════════════════════
Identifies weekly key levels (high/low of prior N trading days)
and trades wick rejections at those levels. Price must wick
through the level but close back inside — a defensive fade
with tight ATR-based stops and fast exits.

Best instruments: XAUUSD, EURUSD, NAS100
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List, Set
from .base import Strategy, TradeSignal


class KeyLevelDefensiveFade(Strategy):
    STRATEGY_ID = "MM-003"
    STRATEGY_NAME = "Key Level Defensive Fade"
    STRATEGY_TYPE = "reversal"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "atr_period": 14,
            "tp_atr_mult": 1.0,            # TP = 1x ATR (fast exit)
            "sl_atr_mult": 0.5,            # SL = 0.5x ATR beyond the wick
            "min_rr": 1.5,
            "weekly_lookback": 5,           # Trading days for weekly window
            "session_filter": True,
            "max_daily_trades": 1,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "tp_atr_mult": (0.8, 1.5, 0.1),
            "sl_atr_mult": (0.3, 0.8, 0.05),
            "min_rr": (1.0, 2.0, 0.25),
        }

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        df = df.copy()
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values

        atr_vals = self.atr(highs, lows, closes, p['atr_period'])

        signals = []
        daily_trades = 0
        last_date = None

        # Track which levels have already been traded this week
        # to enforce "max 1 trade per level per week"
        traded_levels: Set[float] = set()

        # We estimate ~24 bars per trading day on H1, ~6 on H4.
        # Use a heuristic: weekly_lookback * estimated_bars_per_day
        # For flexibility, we'll compute rolling weekly high/low directly
        # using a lookback of weekly_lookback * bars_per_day.
        # We'll estimate bars_per_day from the data's frequency.
        bars_per_day = self._estimate_bars_per_day(df)
        weekly_bars = p['weekly_lookback'] * bars_per_day

        min_start = max(p['atr_period'], weekly_bars) + 10

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
                last_date = cur_date

            # ── Weekly reset: clear traded levels on Monday ───────
            if wd == 0 and (last_date is None or ts.date() != last_date):
                traded_levels = set()

            # ── Session gate: 07:00-17:00 GMT weekdays ────────────
            if p['session_filter']:
                if wd >= 5:
                    continue
                if not (7 <= h < 17):
                    continue

            if daily_trades >= p['max_daily_trades']:
                continue

            if pd.isna(atr_vals[i]):
                continue
            atr_val = atr_vals[i]

            # ── Compute rolling weekly key levels ──────────────────
            start_idx = max(0, i - int(weekly_bars))
            weekly_high = np.max(highs[start_idx:i])
            weekly_low = np.min(lows[start_idx:i])

            # ── Wick rejection above weekly high ───────────────────
            # High wicks through level but close is back below it
            if highs[i] > weekly_high and closes[i] < weekly_high:
                # Check we haven't already traded this level
                level_key = round(weekly_high, 6)
                if level_key not in traded_levels:
                    entry = closes[i]
                    # SL beyond the wick
                    sl = highs[i] + atr_val * p['sl_atr_mult']
                    tp = entry - atr_val * p['tp_atr_mult']
                    risk = sl - entry
                    reward = entry - tp
                    rr = reward / risk if risk > 0 else 0

                    if rr >= p['min_rr']:
                        traded_levels.add(level_key)
                        signals.append(self._sig(
                            symbol, "SELL", entry, sl, tp, df, i,
                            rr=rr,
                            metadata={
                                "key_level": float(weekly_high),
                                "level_type": "weekly_high",
                                "wick_high": float(highs[i]),
                                "rejection_type": "wick_above_close_below",
                            }
                        ))
                        daily_trades += 1

            # ── Wick rejection below weekly low ────────────────────
            # Low wicks through level but close is back above it
            if lows[i] < weekly_low and closes[i] > weekly_low:
                level_key = round(weekly_low, 6)
                if level_key not in traded_levels:
                    entry = closes[i]
                    sl = lows[i] - atr_val * p['sl_atr_mult']
                    tp = entry + atr_val * p['tp_atr_mult']
                    risk = entry - sl
                    reward = tp - entry
                    rr = reward / risk if risk > 0 else 0

                    if rr >= p['min_rr']:
                        traded_levels.add(level_key)
                        signals.append(self._sig(
                            symbol, "BUY", entry, sl, tp, df, i,
                            rr=rr,
                            metadata={
                                "key_level": float(weekly_low),
                                "level_type": "weekly_low",
                                "wick_low": float(lows[i]),
                                "rejection_type": "wick_below_close_above",
                            }
                        ))
                        daily_trades += 1

        return signals

    @staticmethod
    def _estimate_bars_per_day(df: pd.DataFrame) -> int:
        """Estimate the number of bars per trading day from the DataFrame index."""
        if len(df) < 2:
            return 24  # Default assumption: H1
        # Sample the first 100 bars to estimate frequency
        sample_end = min(100, len(df) - 1)
        time_diffs = []
        for j in range(1, sample_end):
            diff = df.index[j] - df.index[j - 1]
            total_seconds = diff.total_seconds()
            if total_seconds > 0:
                time_diffs.append(total_seconds)
        if not time_diffs:
            return 24
        avg_seconds = np.median(time_diffs)
        # Bars per day = seconds_in_trading_day / avg_bar_seconds
        # Assume ~24h of bars for crypto, ~8h for forex/metals
        # Use 86400 (24h) as denominator for simplicity
        bars_per_day = max(1, round(86400.0 / avg_seconds))
        return bars_per_day
