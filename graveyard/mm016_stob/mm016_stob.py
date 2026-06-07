"""
MM-016: STOB — Stochastic Extreme Reversal
═══════════════════════════════════════════
Trades when Stochastic reaches extreme levels and
crosses back, signaling exhaustion and reversal.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class StochasticExtreme(Strategy):
    STRATEGY_ID = "MM-016"
    STRATEGY_NAME = "Stochastic Extreme Reversal"
    STRATEGY_TYPE = "reversal"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "k_period": 14,
            "d_period": 3,
            "ob_level": 80,              # Overbought
            "os_level": 20,              # Oversold
            "atr_period": 14,
            "atr_sl_mult": 1.2,
            "atr_tp_mult": 2.5,
            "cross_confirm": True,        # Require %K/%D cross
            "risk_reward_min": 1.5,
            "session_filter": True,
            "max_daily_trades": 3,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "k_period": (10, 21, 1),
            "d_period": (2, 5, 1),
            "ob_level": (70, 85, 5),
            "os_level": (15, 30, 5),
            "atr_sl_mult": (0.8, 2.0, 0.1),
            "atr_tp_mult": (1.5, 4.0, 0.5),
        }

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        df = df.copy()
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values

        atr_vals = self.atr(highs, lows, closes, p['atr_period'])
        k, d = self.stochastic(highs, lows, closes, p['k_period'], p['d_period'])

        signals = []
        daily_trades = 0
        last_date = None
        min_start = max(p['k_period'], p['atr_period']) + 10

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

            # Bullish: K was oversold, now crossing above D
            if (k[i] < p['os_level'] + 10 and k[i] > d[i] and k[i-1] <= d[i-1]):
                if p['cross_confirm'] and not (k[i] > d[i] and k[i-1] <= d[i-1]):
                    continue

                sl = closes[i] - atr_val * p['atr_sl_mult']
                tp = closes[i] + atr_val * p['atr_tp_mult']
                rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(TradeSignal(
                        symbol=symbol, direction="BUY",
                        entry_price=closes[i], stop_loss=sl, take_profit=tp,
                        strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                        metadata={"k": k[i], "d": d[i], "type": "oversold_cross"}
                    ))
                    daily_trades += 1

            # Bearish: K was overbought, now crossing below D
            elif (k[i] > p['ob_level'] - 10 and k[i] < d[i] and k[i-1] >= d[i-1]):
                if p['cross_confirm'] and not (k[i] < d[i] and k[i-1] >= d[i-1]):
                    continue

                sl = closes[i] + atr_val * p['atr_sl_mult']
                tp = closes[i] - atr_val * p['atr_tp_mult']
                rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(TradeSignal(
                        symbol=symbol, direction="SELL",
                        entry_price=closes[i], stop_loss=sl, take_profit=tp,
                        strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                        metadata={"k": k[i], "d": d[i], "type": "overbought_cross"}
                    ))
                    daily_trades += 1

        return signals
