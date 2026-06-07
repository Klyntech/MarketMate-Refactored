"""
MM-017: HAKN — Heikin Ashi Trend Follow
════════════════════════════════════════
Uses Heikin Ashi candles for smooth trend identification.
Enters on consecutive same-color candles with ATR stops.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class HeikinAshiTrend(Strategy):
    STRATEGY_ID = "MM-017"
    STRATEGY_NAME = "Heikin Ashi Trend Follow"
    STRATEGY_TYPE = "trend"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "consecutive_bars": 3,        # Min consecutive HA candles same direction
            "atr_period": 14,
            "atr_sl_mult": 1.5,
            "atr_tp_mult": 3.0,
            "ha_wick_ratio": 0.3,         # Max wick/body ratio for strong candle
            "risk_reward_min": 1.5,
            "session_filter": True,
            "max_daily_trades": 3,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "consecutive_bars": (2, 6, 1),
            "atr_sl_mult": (1.0, 2.5, 0.1),
            "atr_tp_mult": (2.0, 5.0, 0.5),
            "ha_wick_ratio": (0.1, 0.5, 0.05),
        }

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        df = df.copy()

        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values

        atr_vals = self.atr(highs, lows, closes, p['atr_period'])

        # Convert to Heikin Ashi
        ha_df = self.heikin_ashi(df)
        ha_closes = ha_df['close'].values
        ha_opens = ha_df['open'].values
        ha_highs = ha_df['high'].values
        ha_lows = ha_df['low'].values

        signals = []
        daily_trades = 0
        last_date = None
        min_start = p['atr_period'] + 10

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

            # Check consecutive bullish HA candles
            bull_count = 0
            bear_count = 0
            for j in range(max(0, i - p['consecutive_bars']), i + 1):
                if ha_closes[j] > ha_opens[j]:  # Bullish HA candle
                    bull_count += 1
                    body = ha_closes[j] - ha_opens[j]
                    upper_wick = ha_highs[j] - ha_closes[j]
                    lower_wick = ha_opens[j] - ha_lows[j]
                    if body > 0 and (upper_wick + lower_wick) / body > p['ha_wick_ratio'] * 2:
                        bull_count = 0  # Wick too long = weak candle
                else:
                    bull_count = 0

            for j in range(max(0, i - p['consecutive_bars']), i + 1):
                if ha_closes[j] < ha_opens[j]:  # Bearish HA candle
                    bear_count += 1
                    body = ha_opens[j] - ha_closes[j]
                    upper_wick = ha_highs[j] - ha_opens[j]
                    lower_wick = ha_closes[j] - ha_lows[j]
                    if body > 0 and (upper_wick + lower_wick) / body > p['ha_wick_ratio'] * 2:
                        bear_count = 0
                else:
                    bear_count = 0

            # Bullish entry
            if bull_count >= p['consecutive_bars']:
                sl = lows[i] - atr_val * p['atr_sl_mult']
                tp = closes[i] + atr_val * p['atr_tp_mult']
                rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(TradeSignal(
                        symbol=symbol, direction="BUY",
                        entry_price=closes[i], stop_loss=sl, take_profit=tp,
                        strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                        metadata={"bull_count": bull_count}
                    ))
                    daily_trades += 1

            # Bearish entry
            elif bear_count >= p['consecutive_bars']:
                sl = highs[i] + atr_val * p['atr_sl_mult']
                tp = closes[i] - atr_val * p['atr_tp_mult']
                rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(TradeSignal(
                        symbol=symbol, direction="SELL",
                        entry_price=closes[i], stop_loss=sl, take_profit=tp,
                        strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                        metadata={"bear_count": bear_count}
                    ))
                    daily_trades += 1

        return signals
