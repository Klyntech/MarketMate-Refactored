"""
MM-006: BBNC — Bollinger Bounce Mean Reversion
═══════════════════════════════════════════════
Enters when price touches outer Bollinger Band then
reverses with confirmation. Classic mean reversion.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class BollingerBounce(Strategy):
    STRATEGY_ID = "MM-006"
    STRATEGY_NAME = "Bollinger Bounce Mean Reversion"
    STRATEGY_TYPE = "mean_reversion"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "bb_period": 20,
            "bb_std": 2.0,
            "atr_period": 14,
            "atr_sl_mult": 1.0,
            "tp_at_middle": True,       # TP at middle band
            "rsi_period": 14,
            "rsi_os": 25,               # RSI oversold for buy bounce
            "rsi_ob": 75,               # RSI overbought for sell bounce
            "confirm_candles": 1,       # Candles confirming reversal
            "risk_reward_min": 1.0,
            "session_filter": True,
            "max_daily_trades": 3,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "bb_period": (15, 30, 5),
            "bb_std": (1.5, 3.0, 0.25),
            "atr_sl_mult": (0.5, 2.0, 0.1),
            "rsi_os": (15, 35, 5),
            "rsi_ob": (65, 85, 5),
        }

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        df = df.copy()
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values

        upper, middle, lower = self.bollinger_bands(closes, p['bb_period'], p['bb_std'])
        atr_vals = self.atr(highs, lows, closes, p['atr_period'])
        rsi_vals = self.rsi(closes, p['rsi_period'])

        signals = []
        daily_trades = 0
        last_date = None
        min_start = max(p['bb_period'], p['atr_period'], p['rsi_period']) + 10

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

            if pd.isna(upper[i]) or pd.isna(lower[i]) or pd.isna(atr_vals[i]):
                continue

            atr_val = atr_vals[i]

            # Buy: touched lower band and reversed
            if lows[i] <= lower[i] and closes[i] > lower[i] and rsi_vals[i] < p['rsi_os']:
                if p['confirm_candles'] > 0 and i > 0:
                    if closes[i] <= closes[i-1]:
                        continue

                sl = lows[i] - atr_val * p['atr_sl_mult']
                tp = middle[i] if p['tp_at_middle'] else closes[i] + atr_val * 2.0
                rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(TradeSignal(
                        symbol=symbol, direction="BUY",
                        entry_price=closes[i], stop_loss=sl, take_profit=tp,
                        strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                        metadata={"type": "lower_bounce", "rsi": rsi_vals[i]}
                    ))
                    daily_trades += 1

            # Sell: touched upper band and reversed
            elif highs[i] >= upper[i] and closes[i] < upper[i] and rsi_vals[i] > p['rsi_ob']:
                if p['confirm_candles'] > 0 and i > 0:
                    if closes[i] >= closes[i-1]:
                        continue

                sl = highs[i] + atr_val * p['atr_sl_mult']
                tp = middle[i] if p['tp_at_middle'] else closes[i] - atr_val * 2.0
                rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(TradeSignal(
                        symbol=symbol, direction="SELL",
                        entry_price=closes[i], stop_loss=sl, take_profit=tp,
                        strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                        metadata={"type": "upper_bounce", "rsi": rsi_vals[i]}
                    ))
                    daily_trades += 1

        return signals
