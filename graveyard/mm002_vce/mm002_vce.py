"""
MM-002: VCE-A — Volatility Compression Expansion (Aggressive)
═══════════════════════════════════════════════════════════════
Detects periods of low volatility (compression) and enters
on expansion breakouts with ATR-based stops.

Designed for ETHUSD but works on any trending instrument.
This is the PAPER TRADING version — generates signals but
does NOT execute live trades.

Key Logic:
  1. Measure volatility via ATR ratio (short ATR / long ATR)
  2. When ratio < threshold → market in compression
  3. Wait for price to break above/below compression range
  4. Enter in breakout direction with tight ATR stop
  5. Trail stop on expansion
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List, Optional
from .base import Strategy, TradeSignal


class VCEAgressive(Strategy):
    STRATEGY_ID = "MM-002"
    STRATEGY_NAME = "VCE-A Volatility Compression Expansion"
    STRATEGY_TYPE = "breakout"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "atr_short": 7,          # Short ATR period
            "atr_long": 50,          # Long ATR period (baseline)
            "compression_ratio": 0.7, # Short/Long ATR ratio threshold
            "breakout_bars": 3,       # Bars to confirm breakout
            "atr_sl_mult": 1.2,       # ATR stop-loss multiplier
            "atr_tp_mult": 2.5,       # ATR take-profit multiplier
            "atr_tp2_mult": 4.0,      # ATR TP2 multiplier
            "ema_trend": 100,         # EMA for trend filter
            "compression_min_bars": 5, # Min bars in compression before valid
            "risk_reward_min": 1.5,   # Minimum R:R to take trade
            "session_filter": True,   # Only trade London/NY sessions
            "max_daily_trades": 3,    # Max trades per day
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "atr_short": (5, 14, 1),
            "atr_long": (30, 80, 5),
            "compression_ratio": (0.5, 0.9, 0.05),
            "atr_sl_mult": (0.8, 2.0, 0.1),
            "atr_tp_mult": (1.5, 4.0, 0.5),
            "ema_trend": (50, 200, 25),
            "compression_min_bars": (3, 10, 1),
        }

    def compute_indicators(self, df: pd.DataFrame) -> pd.DataFrame:
        df = df.copy()
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values

        # Short and long ATR
        df['atr_short'] = self.atr(highs, lows, closes, self.params['atr_short'])
        df['atr_long'] = self.atr(highs, lows, closes, self.params['atr_long'])

        # Compression ratio
        df['vol_ratio'] = df['atr_short'] / df['atr_long']

        # Compression flag
        df['compressed'] = df['vol_ratio'] < self.params['compression_ratio']

        # Compression range (high/low during compression)
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

        # Trend EMA
        df['ema_trend'] = self.ema(closes, self.params['ema_trend'])

        # Session filter
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
        daily_trades = 0
        last_date = None

        n = len(df)
        min_start = max(p['atr_long'] + 10, p['ema_trend'] + 10)

        for i in range(min_start, n - 1):
            # Session filter
            if p['session_filter'] and not df.iloc[i].get('in_session', True):
                continue

            # Daily trade limit
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
            else:
                # Was in compression long enough? Check for breakout
                if comp_bars >= p['compression_min_bars'] and comp_low < float('inf'):
                    # Bullish breakout: close above compression high
                    if row['close'] > comp_high:
                        # Trend filter: price above EMA
                        if row['close'] > row['ema_trend']:
                            atr_val = row['atr_short']
                            if pd.isna(atr_val) or atr_val <= 0:
                                comp_bars = 0
                                comp_high = 0
                                comp_low = float('inf')
                                continue

                            sl = row['close'] - atr_val * p['atr_sl_mult']
                            tp = row['close'] + atr_val * p['atr_tp_mult']
                            tp2 = row['close'] + atr_val * p['atr_tp2_mult']
                            rr = (tp - row['close']) / (row['close'] - sl) if (row['close'] - sl) > 0 else 0

                            if rr >= p['risk_reward_min']:
                                sig = TradeSignal(
                                    symbol=symbol,
                                    direction="BUY",
                                    entry_price=row['close'],
                                    stop_loss=sl,
                                    take_profit=tp,
                                    tp2=tp2,
                                    strategy_id=self.STRATEGY_ID,
                                    confidence=min(1.0, comp_bars / 15),
                                    rr_ratio=rr,
                                    metadata={
                                        "compression_bars": comp_bars,
                                        "comp_range_pct": (comp_high - comp_low) / comp_low * 100,
                                        "vol_ratio": row['vol_ratio'],
                                        "atr": atr_val,
                                    }
                                )
                                if row.get('entry_time') is not None or hasattr(df.index[i], 'isoformat'):
                                    sig.entry_time = df.index[i]
                                signals.append(sig)
                                daily_trades += 1

                    # Bearish breakout: close below compression low
                    elif row['close'] < comp_low:
                        # Trend filter: price below EMA
                        if row['close'] < row['ema_trend']:
                            atr_val = row['atr_short']
                            if pd.isna(atr_val) or atr_val <= 0:
                                comp_bars = 0
                                comp_high = 0
                                comp_low = float('inf')
                                continue

                            sl = row['close'] + atr_val * p['atr_sl_mult']
                            tp = row['close'] - atr_val * p['atr_tp_mult']
                            tp2 = row['close'] - atr_val * p['atr_tp2_mult']
                            rr = (row['close'] - tp) / (sl - row['close']) if (sl - row['close']) > 0 else 0

                            if rr >= p['risk_reward_min']:
                                sig = TradeSignal(
                                    symbol=symbol,
                                    direction="SELL",
                                    entry_price=row['close'],
                                    stop_loss=sl,
                                    take_profit=tp,
                                    tp2=tp2,
                                    strategy_id=self.STRATEGY_ID,
                                    confidence=min(1.0, comp_bars / 15),
                                    rr_ratio=rr,
                                    metadata={
                                        "compression_bars": comp_bars,
                                        "comp_range_pct": (comp_high - comp_low) / comp_low * 100,
                                        "vol_ratio": row['vol_ratio'],
                                        "atr": atr_val,
                                    }
                                )
                                if hasattr(df.index[i], 'isoformat'):
                                    sig.entry_time = df.index[i]
                                signals.append(sig)
                                daily_trades += 1

                # Reset compression tracking
                comp_bars = 0
                comp_high = 0.0
                comp_low = float('inf')

        return signals
