"""
MM-010: VPMO — Volume Profile Momentum
═══════════════════════════════════════
Uses volume analysis to detect high-volume nodes and
trades momentum away from them.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class VolumeProfileMomentum(Strategy):
    STRATEGY_ID = "MM-010"
    STRATEGY_NAME = "Volume Profile Momentum"
    STRATEGY_TYPE = "hybrid"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "volume_ma_period": 20,
            "volume_spike_mult": 2.0,
            "atr_period": 14,
            "atr_sl_mult": 1.5,
            "atr_tp_mult": 3.0,
            "price_lookback": 10,
            "risk_reward_min": 1.5,
            "session_filter": True,
            "max_daily_trades": 3,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "volume_spike_mult": (1.5, 3.0, 0.25),
            "atr_sl_mult": (1.0, 2.5, 0.1),
            "atr_tp_mult": (2.0, 5.0, 0.5),
            "price_lookback": (5, 20, 5),
        }

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        df = df.copy()
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        volumes = df['volume'].values if 'volume' in df.columns else np.ones(len(df))

        atr_vals = self.atr(highs, lows, closes, p['atr_period'])
        vol_ma = self.sma(volumes, p['volume_ma_period'])

        signals = []
        daily_trades = 0
        last_date = None
        min_start = max(p['volume_ma_period'], p['atr_period'], p['price_lookback']) + 10

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

            if pd.isna(atr_vals[i]) or pd.isna(vol_ma[i]):
                continue

            atr_val = atr_vals[i]
            vol_spike = volumes[i] > vol_ma[i] * p['volume_spike_mult']

            if not vol_spike:
                continue

            lb = p['price_lookback']
            # Bullish: volume spike + close above recent high
            if closes[i] > np.max(closes[i-lb:i]):
                sl = closes[i] - atr_val * p['atr_sl_mult']
                tp = closes[i] + atr_val * p['atr_tp_mult']
                rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(TradeSignal(
                        symbol=symbol, direction="BUY",
                        entry_price=closes[i], stop_loss=sl, take_profit=tp,
                        strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                        metadata={"vol_spike": volumes[i]/vol_ma[i]}
                    ))
                    daily_trades += 1

            # Bearish: volume spike + close below recent low
            elif closes[i] < np.min(closes[i-lb:i]):
                sl = closes[i] + atr_val * p['atr_sl_mult']
                tp = closes[i] - atr_val * p['atr_tp_mult']
                rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(TradeSignal(
                        symbol=symbol, direction="SELL",
                        entry_price=closes[i], stop_loss=sl, take_profit=tp,
                        strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                        metadata={"vol_spike": volumes[i]/vol_ma[i]}
                    ))
                    daily_trades += 1

        return signals
