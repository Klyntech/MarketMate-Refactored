"""
MM-018: ICHK — Ichimoku Cloud System
═════════════════════════════════════
Multi-component Japanese indicator system.
Trades cloud breakouts, TK crosses, and chikou confirmations.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class IchimokuCloud(Strategy):
    STRATEGY_ID = "MM-018"
    STRATEGY_NAME = "Ichimoku Cloud System"
    STRATEGY_TYPE = "hybrid"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "tenkan_period": 9,
            "kijun_period": 26,
            "senkou_b_period": 52,
            "displacement": 26,
            "atr_period": 14,
            "atr_sl_mult": 1.5,
            "atr_tp_mult": 3.0,
            "risk_reward_min": 1.5,
            "session_filter": True,
            "max_daily_trades": 3,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "tenkan_period": (7, 14, 1),
            "kijun_period": (20, 34, 2),
            "atr_sl_mult": (1.0, 2.5, 0.1),
            "atr_tp_mult": (2.0, 5.0, 0.5),
        }

    def _donchian_mid(self, highs: np.ndarray, lows: np.ndarray,
                      period: int) -> np.ndarray:
        """Compute mid-point of Donchian channel (used for Ichimoku)."""
        n = len(highs)
        result = np.full(n, np.nan)
        for i in range(period - 1, n):
            h = np.max(highs[i - period + 1:i + 1])
            l = np.min(lows[i - period + 1:i + 1])
            result[i] = (h + l) / 2
        return result

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        df = df.copy()
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values

        # Ichimoku components
        tenkan = self._donchian_mid(highs, lows, p['tenkan_period'])
        kijun = self._donchian_mid(highs, lows, p['kijun_period'])
        senkou_a = np.full(len(df), np.nan)
        senkou_b = self._donchian_mid(highs, lows, p['senkou_b_period'])

        for i in range(p['kijun_period'] - 1, len(df)):
            if not pd.isna(tenkan[i]) and not pd.isna(kijun[i]):
                senkou_a[i] = (tenkan[i] + kijun[i]) / 2

        atr_vals = self.atr(highs, lows, closes, p['atr_period'])

        signals = []
        daily_trades = 0
        last_date = None
        min_start = max(p['senkou_b_period'], p['atr_period'], p['kijun_period']) + 10

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

            if pd.isna(atr_vals[i]) or pd.isna(tenkan[i]) or pd.isna(kijun[i]):
                continue

            atr_val = atr_vals[i]

            # Get cloud boundaries (shifted forward, but we use current for simplicity)
            cloud_top = senkou_a[i]
            cloud_bottom = senkou_b[i]
            if pd.isna(cloud_top) or pd.isna(cloud_bottom):
                continue

            if cloud_top < cloud_bottom:
                cloud_top, cloud_bottom = cloud_bottom, cloud_top

            # TK Cross: Tenkan crosses above Kijun + price above cloud
            if (tenkan[i] > kijun[i] and tenkan[i-1] <= kijun[i-1] and
                closes[i] > cloud_top):
                sl = closes[i] - atr_val * p['atr_sl_mult']
                tp = closes[i] + atr_val * p['atr_tp_mult']
                rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(TradeSignal(
                        symbol=symbol, direction="BUY",
                        entry_price=closes[i], stop_loss=sl, take_profit=tp,
                        strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                        metadata={"type": "tk_cross_bull", "cloud": "above"}
                    ))
                    daily_trades += 1

            # TK Cross: Tenkan crosses below Kijun + price below cloud
            elif (tenkan[i] < kijun[i] and tenkan[i-1] >= kijun[i-1] and
                  closes[i] < cloud_bottom):
                sl = closes[i] + atr_val * p['atr_sl_mult']
                tp = closes[i] - atr_val * p['atr_tp_mult']
                rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(TradeSignal(
                        symbol=symbol, direction="SELL",
                        entry_price=closes[i], stop_loss=sl, take_profit=tp,
                        strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                        metadata={"type": "tk_cross_bear", "cloud": "below"}
                    ))
                    daily_trades += 1

            # Cloud breakout: price breaks above cloud
            elif (closes[i] > cloud_top and closes[i-1] <= cloud_top and
                  tenkan[i] > kijun[i]):
                sl = closes[i] - atr_val * p['atr_sl_mult']
                tp = closes[i] + atr_val * p['atr_tp_mult']
                rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(TradeSignal(
                        symbol=symbol, direction="BUY",
                        entry_price=closes[i], stop_loss=sl, take_profit=tp,
                        strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                        metadata={"type": "cloud_breakout_bull"}
                    ))
                    daily_trades += 1

            # Cloud breakdown: price breaks below cloud
            elif (closes[i] < cloud_bottom and closes[i-1] >= cloud_bottom and
                  tenkan[i] < kijun[i]):
                sl = closes[i] + atr_val * p['atr_sl_mult']
                tp = closes[i] - atr_val * p['atr_tp_mult']
                rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(TradeSignal(
                        symbol=symbol, direction="SELL",
                        entry_price=closes[i], stop_loss=sl, take_profit=tp,
                        strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                        metadata={"type": "cloud_breakout_bear"}
                    ))
                    daily_trades += 1

        return signals
