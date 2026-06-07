"""
MM-011: SSMO — Session Momentum Bias
════════════════════════════════════
Trades the directional momentum bias during London and NY sessions.
Uses the first hours of each session to determine direction.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class SessionMomentum(Strategy):
    STRATEGY_ID = "MM-011"
    STRATEGY_NAME = "Session Momentum Bias"
    STRATEGY_TYPE = "trend"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "london_open": 7,
            "london_close": 12,
            "ny_open": 12,
            "ny_close": 17,
            "bias_hours": 2,             # First N hours define session bias
            "atr_period": 14,
            "atr_sl_mult": 1.0,
            "atr_tp_mult": 2.0,
            "min_move_pct": 0.1,         # Min session move % to trade
            "risk_reward_min": 1.5,
            "session_filter": True,
            "max_daily_trades": 2,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "bias_hours": (1, 4, 1),
            "atr_sl_mult": (0.5, 2.0, 0.1),
            "atr_tp_mult": (1.5, 4.0, 0.5),
            "min_move_pct": (0.05, 0.3, 0.05),
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
        session_bias = None
        bias_set_hour = -1

        min_start = p['atr_period'] + 10

        for i in range(min_start, len(df) - 1):
            if not hasattr(df.index, 'hour'):
                continue

            h = df.index[i].hour
            wd = df.index[i].weekday()
            if wd >= 5:
                continue

            cur_date = df.index[i].date()
            if cur_date != last_date:
                daily_trades = 0
                last_date = cur_date
                session_bias = None
                bias_set_hour = -1
            if daily_trades >= p['max_daily_trades']:
                continue

            if pd.isna(atr_vals[i]):
                continue

            # Set session bias from first hours
            if session_bias is None and h == p['london_open'] + p['bias_hours']:
                # London session bias
                session_start_idx = None
                for j in range(i - 20, i):
                    if df.index[j].hour == p['london_open']:
                        session_start_idx = j
                        break
                if session_start_idx is not None:
                    move = closes[i] - closes[session_start_idx]
                    move_pct = abs(move) / closes[session_start_idx] * 100
                    if move_pct >= p['min_move_pct']:
                        session_bias = "BUY" if move > 0 else "SELL"
                        bias_set_hour = h

            # Execute in session direction
            in_london = p['london_open'] <= h < p['london_close']
            in_ny = p['ny_open'] <= h < p['ny_close']

            if session_bias and (in_london or in_ny) and h > bias_set_hour:
                atr_val = atr_vals[i]

                if session_bias == "BUY" and closes[i] > closes[i-1]:
                    sl = closes[i] - atr_val * p['atr_sl_mult']
                    tp = closes[i] + atr_val * p['atr_tp_mult']
                    rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(TradeSignal(
                            symbol=symbol, direction="BUY",
                            entry_price=closes[i], stop_loss=sl, take_profit=tp,
                            strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                            metadata={"session": "london" if in_london else "ny"}
                        ))
                        daily_trades += 1

                elif session_bias == "SELL" and closes[i] < closes[i-1]:
                    sl = closes[i] + atr_val * p['atr_sl_mult']
                    tp = closes[i] - atr_val * p['atr_tp_mult']
                    rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(TradeSignal(
                            symbol=symbol, direction="SELL",
                            entry_price=closes[i], stop_loss=sl, take_profit=tp,
                            strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                            metadata={"session": "london" if in_london else "ny"}
                        ))
                        daily_trades += 1

        return signals
