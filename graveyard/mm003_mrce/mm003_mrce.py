"""
MM-003: MRCE-A — Mean Reversion Compression Expansion (Aggressive)
════════════════════════════════════════════════════════════════════
Fades VCE breakouts — when price breaks out of compression,
this strategy expects a fake-out and enters against the breakout.

Based on the finding that MRCE was the only profitable MM-002 variant
(Sharpe 0.23, PF 1.11, 100% MC survival).

Key Logic:
  1. Detect compression (same as VCE)
  2. When price breaks out, wait for reversal candle
  3. Enter AGAINST the breakout direction
  4. Stop beyond the breakout extreme
  5. TP at the opposite side of compression range
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class MRCEAggressive(Strategy):
    STRATEGY_ID = "MM-003"
    STRATEGY_NAME = "MRCE-A Mean Reversion Compression Expansion"
    STRATEGY_TYPE = "mean_reversion"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "atr_short": 7,
            "atr_long": 50,
            "compression_ratio": 0.7,
            "reversal_bars": 2,        # Bars confirming reversal after breakout
            "atr_sl_mult": 1.5,
            "atr_tp_mult": 1.0,        # TP at opposite compression boundary
            "ema_trend": 100,
            "compression_min_bars": 5,
            "risk_reward_min": 1.0,
            "session_filter": True,
            "max_daily_trades": 3,
            "fakeout_pct": 0.3,        # Min % of breakout that must be reversed
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "atr_short": (5, 14, 1),
            "atr_long": (30, 80, 5),
            "compression_ratio": (0.5, 0.9, 0.05),
            "atr_sl_mult": (1.0, 2.5, 0.1),
            "reversal_bars": (1, 4, 1),
            "ema_trend": (50, 200, 25),
            "fakeout_pct": (0.1, 0.5, 0.05),
        }

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values

        df['atr_short'] = self.atr(highs, lows, closes, self.params['atr_short'])
        df['atr_long'] = self.atr(highs, lows, closes, self.params['atr_long'])
        df['vol_ratio'] = df['atr_short'] / df['atr_long']
        df['compressed'] = df['vol_ratio'] < self.params['compression_ratio']

        df['comp_high'] = np.nan
        df['comp_low'] = np.nan
        comp_start = None
        for i in range(len(df)):
            if df['compressed'].iloc[i]:
                if comp_start is None:
                    comp_start = i
                df['comp_high'].iloc[i] = np.max(highs[comp_start:i+1])
                df['comp_low'].iloc[i] = np.min(lows[comp_start:i+1])
            else:
                comp_start = None

        df['ema_trend'] = self.ema(closes, self.params['ema_trend'])

        if hasattr(df.index, 'hour'):
            hours = df.index.hour
            df['in_session'] = ((hours >= 7) & (hours < 17)) & (df.index.weekday < 5)

        return df

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        df = self.compute_indicators(df)
        signals = []

        comp_bars = 0
        comp_high = 0.0
        comp_low = float('inf')
        breakout_dir = None
        breakout_bar = 0
        daily_trades = 0
        last_date = None

        n = len(df)
        min_start = max(p['atr_long'] + 10, p['ema_trend'] + 10)

        for i in range(min_start, n - 1):
            if p['session_filter'] and not df.iloc[i].get('in_session', True):
                continue

            cur_date = df.index[i].date() if hasattr(df.index[i], 'date') else None
            if cur_date != last_date:
                daily_trades = 0
                last_date = cur_date
            if daily_trades >= p['max_daily_trades']:
                continue

            row = df.iloc[i]
            if pd.isna(row.get('vol_ratio')):
                continue

            # Track compression
            if row['compressed']:
                comp_bars += 1
                comp_high = max(comp_high, row['high'])
                comp_low = min(comp_low, row['low'])
                breakout_dir = None
            else:
                # Check if we just broke out of compression
                if comp_bars >= p['compression_min_bars'] and comp_low < float('inf'):
                    if row['close'] > comp_high:
                        breakout_dir = "UP"
                        breakout_bar = i
                    elif row['close'] < comp_low:
                        breakout_dir = "DOWN"
                        breakout_bar = i

                # Check for fakeout reversal after breakout
                if breakout_dir is not None and (i - breakout_bar) >= p['reversal_bars']:
                    bars_since = i - breakout_bar

                    if breakout_dir == "UP":
                        # Fakeout: price reversed back below comp_high
                        fakeout_dist = comp_high - comp_low
                        reversal_dist = comp_high - row['close']
                        if (row['close'] < comp_high and
                            reversal_dist >= fakeout_dist * p['fakeout_pct']):
                            atr_val = row['atr_short']
                            if pd.isna(atr_val) or atr_val <= 0:
                                breakout_dir = None
                                comp_bars = 0
                                continue

                            entry = row['close']
                            sl = comp_high + atr_val * p['atr_sl_mult'] * 0.3
                            tp = comp_low + (comp_high - comp_low) * 0.2  # Near comp low
                            rr = (entry - tp) / (sl - entry) if (sl - entry) > 0 else 0

                            if rr >= p['risk_reward_min']:
                                signals.append(TradeSignal(
                                    symbol=symbol, direction="SELL",
                                    entry_price=entry, stop_loss=sl, take_profit=tp,
                                    strategy_id=self.STRATEGY_ID,
                                    confidence=min(1.0, comp_bars / 15),
                                    rr_ratio=rr,
                                    metadata={"type": "up_fakeout", "comp_bars": comp_bars,
                                             "reversal_bars": bars_since}
                                ))
                                daily_trades += 1
                                breakout_dir = None

                    elif breakout_dir == "DOWN":
                        fakeout_dist = comp_high - comp_low
                        reversal_dist = row['close'] - comp_low
                        if (row['close'] > comp_low and
                            reversal_dist >= fakeout_dist * p['fakeout_pct']):
                            atr_val = row['atr_short']
                            if pd.isna(atr_val) or atr_val <= 0:
                                breakout_dir = None
                                comp_bars = 0
                                continue

                            entry = row['close']
                            sl = comp_low - atr_val * p['atr_sl_mult'] * 0.3
                            tp = comp_high - (comp_high - comp_low) * 0.2
                            rr = (tp - entry) / (entry - sl) if (entry - sl) > 0 else 0

                            if rr >= p['risk_reward_min']:
                                signals.append(TradeSignal(
                                    symbol=symbol, direction="BUY",
                                    entry_price=entry, stop_loss=sl, take_profit=tp,
                                    strategy_id=self.STRATEGY_ID,
                                    confidence=min(1.0, comp_bars / 15),
                                    rr_ratio=rr,
                                    metadata={"type": "down_fakeout", "comp_bars": comp_bars,
                                             "reversal_bars": bars_since}
                                ))
                                daily_trades += 1
                                breakout_dir = None

                if not row['compressed']:
                    comp_bars = 0
                    comp_high = 0.0
                    comp_low = float('inf')

        return signals
