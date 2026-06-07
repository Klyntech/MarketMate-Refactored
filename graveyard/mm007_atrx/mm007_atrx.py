"""
MM-007: ATRX — ATR Breakout Expansion
══════════════════════════════════════
Enters when ATR expands rapidly from a low baseline,
indicating a volatility breakout. Direction from price action.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class ATRBreakout(Strategy):
    STRATEGY_ID = "MM-007"
    STRATEGY_NAME = "ATR Breakout Expansion"
    STRATEGY_TYPE = "breakout"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "atr_short": 7,
            "atr_long": 50,
            "expansion_ratio": 1.5,      # Short ATR must be > Long ATR * ratio
            "atr_sl_mult": 1.3,
            "atr_tp_mult": 3.0,
            "lookback_period": 5,         # Bars for high/low breakout
            "ema_trend": 50,
            "risk_reward_min": 1.5,
            "session_filter": True,
            "max_daily_trades": 3,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "atr_short": (5, 14, 1),
            "atr_long": (30, 80, 5),
            "expansion_ratio": (1.2, 2.0, 0.1),
            "atr_sl_mult": (1.0, 2.0, 0.1),
            "atr_tp_mult": (2.0, 5.0, 0.5),
            "lookback_period": (3, 10, 1),
        }

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        df = df.copy()
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values

        atr_s = self.atr(highs, lows, closes, p['atr_short'])
        atr_l = self.atr(highs, lows, closes, p['atr_long'])
        ema = self.ema(closes, p['ema_trend'])

        signals = []
        daily_trades = 0
        last_date = None
        min_start = max(p['atr_long'], p['ema_trend']) + 10

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

            if pd.isna(atr_s[i]) or pd.isna(atr_l[i]):
                continue

            # ATR expansion detected
            if atr_s[i] > atr_l[i] * p['expansion_ratio']:
                lb = p['lookback_period']
                range_high = np.max(highs[i-lb:i])
                range_low = np.min(lows[i-lb:i])

                # Bullish: breakout above range + above EMA
                if closes[i] > range_high and closes[i] > ema[i]:
                    sl = closes[i] - atr_s[i] * p['atr_sl_mult']
                    tp = closes[i] + atr_s[i] * p['atr_tp_mult']
                    rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(TradeSignal(
                            symbol=symbol, direction="BUY",
                            entry_price=closes[i], stop_loss=sl, take_profit=tp,
                            strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                            metadata={"expansion": atr_s[i]/atr_l[i]}
                        ))
                        daily_trades += 1

                # Bearish: breakout below range + below EMA
                elif closes[i] < range_low and closes[i] < ema[i]:
                    sl = closes[i] + atr_s[i] * p['atr_sl_mult']
                    tp = closes[i] - atr_s[i] * p['atr_tp_mult']
                    rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(TradeSignal(
                            symbol=symbol, direction="SELL",
                            entry_price=closes[i], stop_loss=sl, take_profit=tp,
                            strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                            metadata={"expansion": atr_s[i]/atr_l[i]}
                        ))
                        daily_trades += 1

        return signals
