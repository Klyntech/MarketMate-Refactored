"""
MM-015: MHST — MACD Histogram Shift
════════════════════════════════════
Trades momentum shifts detected by MACD histogram
divergences and zero-line crossovers.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class MACDHistogram(Strategy):
    STRATEGY_ID = "MM-015"
    STRATEGY_NAME = "MACD Histogram Shift"
    STRATEGY_TYPE = "momentum"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "fast_period": 12,
            "slow_period": 26,
            "signal_period": 9,
            "atr_period": 14,
            "atr_sl_mult": 1.5,
            "atr_tp_mult": 3.0,
            "hist_shift_bars": 2,        # Bars confirming histogram shift
            "zero_line_trade": True,      # Trade zero-line crossovers
            "risk_reward_min": 1.5,
            "session_filter": True,
            "max_daily_trades": 3,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "fast_period": (8, 16, 2),
            "slow_period": (20, 34, 2),
            "signal_period": (7, 12, 1),
            "atr_sl_mult": (1.0, 2.5, 0.1),
            "atr_tp_mult": (2.0, 5.0, 0.5),
        }

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        df = df.copy()
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values

        atr_vals = self.atr(highs, lows, closes, p['atr_period'])
        macd_line, signal_line, histogram = self.macd(
            closes, p['fast_period'], p['slow_period'], p['signal_period'])

        signals = []
        daily_trades = 0
        last_date = None
        min_start = max(p['slow_period'] + p['signal_period'], p['atr_period']) + 10

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

            # Bullish: histogram shifting up from negative territory
            if (histogram[i] > histogram[i-1] and
                histogram[i-1] > histogram[i-2] and
                histogram[i] < 0 and
                histogram[i-2] < histogram[i-1]):

                # Zero-line crossover
                if p['zero_line_trade'] and histogram[i-1] < 0 and histogram[i] >= 0:
                    sl = closes[i] - atr_val * p['atr_sl_mult']
                    tp = closes[i] + atr_val * p['atr_tp_mult']
                    rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(TradeSignal(
                            symbol=symbol, direction="BUY",
                            entry_price=closes[i], stop_loss=sl, take_profit=tp,
                            strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                            metadata={"type": "zero_cross_bull", "hist": histogram[i]}
                        ))
                        daily_trades += 1

                # Just momentum shift (histogram rising while negative)
                elif histogram[i] > histogram[i-p['hist_shift_bars']]:
                    sl = closes[i] - atr_val * p['atr_sl_mult']
                    tp = closes[i] + atr_val * p['atr_tp_mult']
                    rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(TradeSignal(
                            symbol=symbol, direction="BUY",
                            entry_price=closes[i], stop_loss=sl, take_profit=tp,
                            strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                            metadata={"type": "hist_shift_bull", "hist": histogram[i]}
                        ))
                        daily_trades += 1

            # Bearish: histogram shifting down from positive territory
            elif (histogram[i] < histogram[i-1] and
                  histogram[i-1] < histogram[i-2] and
                  histogram[i] > 0):

                if p['zero_line_trade'] and histogram[i-1] > 0 and histogram[i] <= 0:
                    sl = closes[i] + atr_val * p['atr_sl_mult']
                    tp = closes[i] - atr_val * p['atr_tp_mult']
                    rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(TradeSignal(
                            symbol=symbol, direction="SELL",
                            entry_price=closes[i], stop_loss=sl, take_profit=tp,
                            strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                            metadata={"type": "zero_cross_bear", "hist": histogram[i]}
                        ))
                        daily_trades += 1

                elif histogram[i] < histogram[i-p['hist_shift_bars']]:
                    sl = closes[i] + atr_val * p['atr_sl_mult']
                    tp = closes[i] - atr_val * p['atr_tp_mult']
                    rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(TradeSignal(
                            symbol=symbol, direction="SELL",
                            entry_price=closes[i], stop_loss=sl, take_profit=tp,
                            strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                            metadata={"type": "hist_shift_bear", "hist": histogram[i]}
                        ))
                        daily_trades += 1

        return signals
