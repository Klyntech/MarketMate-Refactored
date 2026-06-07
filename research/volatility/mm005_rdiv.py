"""
MM-005: RDIV — RSI Divergence Reversal
═══════════════════════════════════════
Detects bearish/bullish divergence between price and RSI,
then enters on confirmation candle with ATR-based stops.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class RSIDivergence(Strategy):
    STRATEGY_ID = "MM-005"
    STRATEGY_NAME = "RSI Divergence Reversal"
    STRATEGY_TYPE = "reversal"
    # INSTRUMENT LOCKED: Only run on these instruments
    ALLOWED_INSTRUMENTS = ["EURUSD", "XAGUSD"]

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "rsi_period": 14,
            "divergence_lookback": 30,    # Bars to look back for divergence
            "rsi_ob": 70,                 # Overbought threshold
            "rsi_os": 30,                 # Oversold threshold
            "atr_period": 14,
            "atr_sl_mult": 1.5,
            "atr_tp_mult": 2.5,
            "confirm_candle": True,       # Require confirmation candle
            "risk_reward_min": 1.5,
            "session_filter": True,
            "max_daily_trades": 2,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "rsi_period": (10, 21, 1),
            "divergence_lookback": (20, 50, 5),
            "atr_sl_mult": (1.0, 2.5, 0.1),
            "atr_tp_mult": (1.5, 4.0, 0.5),
            "rsi_ob": (65, 80, 5),
            "rsi_os": (20, 35, 5),
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
        rsi_vals = self.rsi(closes, p['rsi_period'])
        sh_idx, sh_prices, sl_idx, sl_prices = self.find_swing_points(highs, lows, 5)

        signals = []
        daily_trades = 0
        last_date = None
        min_start = max(p['rsi_period'], p['atr_period'], p['divergence_lookback']) + 10

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

            if pd.isna(atr_vals[i]) or pd.isna(rsi_vals[i]):
                continue

            atr_val = atr_vals[i]
            lb = p['divergence_lookback']

            # Bearish divergence: price higher high, RSI lower high
            recent_sh = sh_idx[(sh_idx >= i - lb) & (sh_idx < i)]
            if len(recent_sh) >= 2:
                p1, p2 = recent_sh[-2], recent_sh[-1]
                if (highs[p2] > highs[p1] and rsi_vals[p2] < rsi_vals[p1] and
                    rsi_vals[p2] > p['rsi_ob']):
                    if closes[i] < closes[i-1]:  # Confirmation candle
                        sl = highs[p2] + atr_val * p['atr_sl_mult'] * 0.3
                        tp = closes[i] - atr_val * p['atr_tp_mult']
                        rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                        if rr >= p['risk_reward_min']:
                            signals.append(self._sig(
                                symbol, "SELL", closes[i], sl, tp, df, i,
                                rr=rr, metadata={"divergence": "bearish", "rsi": rsi_vals[i]}
                            ))
                            daily_trades += 1
                            continue

            # Bullish divergence: price lower low, RSI higher low
            recent_sl = sl_idx[(sl_idx >= i - lb) & (sl_idx < i)]
            if len(recent_sl) >= 2:
                p1, p2 = recent_sl[-2], recent_sl[-1]
                if (lows[p2] < lows[p1] and rsi_vals[p2] > rsi_vals[p1] and
                    rsi_vals[p2] < p['rsi_os']):
                    if closes[i] > closes[i-1]:  # Confirmation
                        sl = lows[p2] - atr_val * p['atr_sl_mult'] * 0.3
                        tp = closes[i] + atr_val * p['atr_tp_mult']
                        rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                        if rr >= p['risk_reward_min']:
                            signals.append(self._sig(
                                symbol, "BUY", closes[i], sl, tp, df, i,
                                rr=rr, metadata={"divergence": "bullish", "rsi": rsi_vals[i]}
                            ))
                            daily_trades += 1

        return signals
