"""
MM-004: MOBO — Momentum Breakout
════════════════════════════════
Enters when price breaks above/below a Donchian channel
with volume confirmation and momentum alignment.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class MomentumBreakout(Strategy):
    STRATEGY_ID = "MM-004"
    STRATEGY_NAME = "Momentum Breakout"
    STRATEGY_TYPE = "breakout"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "channel_period": 20,      # Donchian channel lookback
            "atr_period": 14,
            "atr_sl_mult": 1.5,
            "atr_tp_mult": 3.0,
            "rsi_period": 14,
            "rsi_momentum_min": 55,     # RSI must be above this for buys
            "rsi_momentum_max": 45,     # RSI must be below this for sells
            "volume_ma_period": 20,
            "volume_mult": 1.2,         # Volume must be > volume_ma * mult
            "risk_reward_min": 1.5,
            "session_filter": True,
            "max_daily_trades": 3,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "channel_period": (10, 40, 5),
            "atr_sl_mult": (1.0, 2.5, 0.1),
            "atr_tp_mult": (2.0, 5.0, 0.5),
            "rsi_momentum_min": (50, 65, 5),
            "volume_mult": (0.8, 1.5, 0.1),
        }

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        df = df.copy()
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        volumes = df['volume'].values if 'volume' in df.columns else np.ones(len(df))

        # Indicators
        atr_vals = self.atr(highs, lows, closes, p['atr_period'])
        rsi_vals = self.rsi(closes, p['rsi_period'])
        vol_ma = self.sma(volumes, p['volume_ma_period'])

        # Donchian channel
        upper = np.full(len(df), np.nan)
        lower = np.full(len(df), np.nan)
        for i in range(p['channel_period'] - 1, len(df)):
            upper[i] = np.max(highs[i - p['channel_period'] + 1:i + 1])
            lower[i] = np.min(lows[i - p['channel_period'] + 1:i + 1])

        signals = []
        daily_trades = 0
        last_date = None
        min_start = max(p['channel_period'], p['atr_period'], p['rsi_period']) + 10

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

            if pd.isna(upper[i]) or pd.isna(atr_vals[i]) or pd.isna(rsi_vals[i]):
                continue

            atr_val = atr_vals[i]
            vol_ok = not pd.isna(vol_ma[i]) and volumes[i] > vol_ma[i] * p['volume_mult']

            # Bullish breakout
            if closes[i] > upper[i - 1] and rsi_vals[i] > p['rsi_momentum_min']:
                if vol_ok:
                    sl = closes[i] - atr_val * p['atr_sl_mult']
                    tp = closes[i] + atr_val * p['atr_tp_mult']
                    rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(TradeSignal(
                            symbol=symbol, direction="BUY",
                            entry_price=closes[i], stop_loss=sl, take_profit=tp,
                            strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                            metadata={"rsi": rsi_vals[i], "atr": atr_val}
                        ))
                        daily_trades += 1

            # Bearish breakout
            elif closes[i] < lower[i - 1] and rsi_vals[i] < p['rsi_momentum_max']:
                if vol_ok:
                    sl = closes[i] + atr_val * p['atr_sl_mult']
                    tp = closes[i] - atr_val * p['atr_tp_mult']
                    rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(TradeSignal(
                            symbol=symbol, direction="SELL",
                            entry_price=closes[i], stop_loss=sl, take_profit=tp,
                            strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                            metadata={"rsi": rsi_vals[i], "atr": atr_val}
                        ))
                        daily_trades += 1

        return signals
