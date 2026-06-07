"""
MM-008: EMAC — EMA Crossover Trend
══════════════════════════════════
Classic fast/slow EMA crossover with ATR stops and
trend filter for confirmation.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class EMACrossover(Strategy):
    STRATEGY_ID = "MM-008"
    STRATEGY_NAME = "EMA Crossover Trend"
    STRATEGY_TYPE = "trend"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "fast_ema": 9,
            "slow_ema": 21,
            "trend_ema": 100,
            "atr_period": 14,
            "atr_sl_mult": 1.5,
            "atr_tp_mult": 3.0,
            "risk_reward_min": 1.5,
            "session_filter": True,
            "max_daily_trades": 3,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "fast_ema": (5, 20, 1),
            "slow_ema": (15, 50, 5),
            "trend_ema": (50, 200, 25),
            "atr_sl_mult": (1.0, 2.5, 0.1),
            "atr_tp_mult": (2.0, 5.0, 0.5),
        }

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        df = df.copy()
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values

        fast = self.ema(closes, p['fast_ema'])
        slow = self.ema(closes, p['slow_ema'])
        trend = self.ema(closes, p['trend_ema'])
        atr_vals = self.atr(highs, lows, closes, p['atr_period'])

        signals = []
        daily_trades = 0
        last_date = None
        min_start = max(p['slow_ema'], p['trend_ema'], p['atr_period']) + 10

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

            # Golden cross + above trend EMA
            if fast[i] > slow[i] and fast[i-1] <= slow[i-1] and closes[i] > trend[i]:
                sl = closes[i] - atr_val * p['atr_sl_mult']
                tp = closes[i] + atr_val * p['atr_tp_mult']
                rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(TradeSignal(
                        symbol=symbol, direction="BUY",
                        entry_price=closes[i], stop_loss=sl, take_profit=tp,
                        strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                        metadata={"type": "golden_cross"}
                    ))
                    daily_trades += 1

            # Death cross + below trend EMA
            elif fast[i] < slow[i] and fast[i-1] >= slow[i-1] and closes[i] < trend[i]:
                sl = closes[i] + atr_val * p['atr_sl_mult']
                tp = closes[i] - atr_val * p['atr_tp_mult']
                rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(TradeSignal(
                        symbol=symbol, direction="SELL",
                        entry_price=closes[i], stop_loss=sl, take_profit=tp,
                        strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                        metadata={"type": "death_cross"}
                    ))
                    daily_trades += 1

        return signals
