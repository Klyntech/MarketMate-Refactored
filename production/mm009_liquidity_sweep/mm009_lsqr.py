"""
MM-009: LSQR — Liquidity Sweep Quick Reversal
══════════════════════════════════════════════
Detects when price sweeps a liquidity level (swing high/low)
and immediately reverses. Fast mean-reversion on sweeps.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class LiquiditySweepReversal(Strategy):
    STRATEGY_ID = "MM-009"
    STRATEGY_NAME = "Liquidity Sweep Quick Reversal"
    STRATEGY_TYPE = "reversal"
    # INSTRUMENT LOCKED: Only run on these instruments
    ALLOWED_INSTRUMENTS = ["NAS100", "ETHUSD", "XAGUSD", "US30"]

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "swing_lookback": 5,
            "sweep_pct": 0.0005,        # Min sweep distance as % of price
            "reversal_bars": 2,          # Bars confirming reversal after sweep
            "atr_period": 14,
            "atr_sl_mult": 1.2,
            "atr_tp_mult": 2.0,
            "ema_trend": 100,
            "risk_reward_min": 1.0,
            "session_filter": True,
            "max_daily_trades": 3,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "swing_lookback": (3, 10, 1),
            "reversal_bars": (1, 5, 1),
            "atr_sl_mult": (0.8, 2.0, 0.1),
            "atr_tp_mult": (1.5, 4.0, 0.5),
            "sweep_pct": (0.0002, 0.002, 0.0002),
        }

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        # Instrument lock: skip if not in allowed list
        if symbol and symbol not in self.ALLOWED_INSTRUMENTS:
            return []
        p = self.params
        df = df.copy()
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values

        atr_vals = self.atr(highs, lows, closes, p['atr_period'])
        ema = self.ema(closes, p['ema_trend'])
        sh_idx, sh_prices, sl_idx, sl_prices = self.find_swing_points(
            highs, lows, p['swing_lookback'])

        signals = []
        daily_trades = 0
        last_date = None
        min_start = max(p['swing_lookback'] * 2, p['atr_period'], p['ema_trend']) + 10

        # Track sweep events
        pending_sweep = None  # (direction, sweep_level, bar_idx)

        for i in range(min_start, len(df) - 1):
            if p['session_filter'] and hasattr(df.index, 'hour'):
                h = df.index[i].hour
                if not ((7 <= h < 17) and df.index[i].weekday() < 5):
                    continue

            cur_date = df.index[i].date() if hasattr(df.index[i], 'date') else None
            if cur_date != last_date:
                daily_trades = 0
                last_date = cur_date
            if daily_trades >= p['max_daily_trades']:
                continue

            if pd.isna(atr_vals[i]):
                continue
            atr_val = atr_vals[i]

            # Check for new sweep
            recent_sh = sh_idx[sh_idx < i]
            recent_sl = sl_idx[sl_idx < i]

            # High sweep: price went above a swing high then closed below it
            if len(recent_sh) > 0:
                last_sh = sh_prices[len(recent_sh) - 1]
                if highs[i] > last_sh and closes[i] < last_sh:
                    dist = highs[i] - last_sh
                    if dist >= last_sh * p['sweep_pct']:
                        pending_sweep = ("SELL", last_sh, i)

            # Low sweep: price went below a swing low then closed above it
            if len(recent_sl) > 0:
                last_sl = sl_prices[len(recent_sl) - 1]
                if lows[i] < last_sl and closes[i] > last_sl:
                    dist = last_sl - lows[i]
                    if dist >= last_sl * p['sweep_pct']:
                        pending_sweep = ("BUY", last_sl, i)

            # Check pending sweep for reversal confirmation
            if pending_sweep is not None:
                dirn, level, bar = pending_sweep
                bars_since = i - bar

                if bars_since >= p['reversal_bars']:
                    if dirn == "BUY" and closes[i] > closes[bar]:
                        # Bullish reversal confirmed
                        sl = level - atr_val * p['atr_sl_mult']
                        tp = closes[i] + atr_val * p['atr_tp_mult']
                        rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                        if rr >= p['risk_reward_min']:
                            signals.append(self._sig(
                                symbol, "BUY", closes[i], sl, tp, df, i,
                                rr=rr, metadata={"sweep_level": level, "type": "low_sweep_reversal"}
                            ))
                            daily_trades += 1
                        pending_sweep = None

                    elif dirn == "SELL" and closes[i] < closes[bar]:
                        # Bearish reversal confirmed
                        sl = level + atr_val * p['atr_sl_mult']
                        tp = closes[i] - atr_val * p['atr_tp_mult']
                        rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                        if rr >= p['risk_reward_min']:
                            signals.append(self._sig(
                                symbol, "SELL", closes[i], sl, tp, df, i,
                                rr=rr, metadata={"sweep_level": level, "type": "high_sweep_reversal"}
                            ))
                            daily_trades += 1
                        pending_sweep = None

                # Expire old sweeps
                if bars_since > 10:
                    pending_sweep = None

        return signals
