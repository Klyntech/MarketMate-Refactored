"""
MM-013: SRBN — Support/Resistance Bounce
═════════════════════════════════════════
Identifies key S/R levels from swing points and trades
bounces off them with tight stops.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class SupportResistanceBounce(Strategy):
    STRATEGY_ID = "MM-013"
    STRATEGY_NAME = "Support/Resistance Bounce"
    STRATEGY_TYPE = "mean_reversion"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "swing_lookback": 10,
            "level_touches": 2,           # Min touches to validate S/R level
            "proximity_pct": 0.2,         # How close price must be to S/R (%)
            "atr_period": 14,
            "atr_sl_mult": 1.0,
            "atr_tp_mult": 2.0,
            "risk_reward_min": 1.5,
            "session_filter": True,
            "max_daily_trades": 3,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "swing_lookback": (5, 15, 1),
            "level_touches": (2, 4, 1),
            "proximity_pct": (0.1, 0.5, 0.05),
            "atr_sl_mult": (0.5, 2.0, 0.1),
            "atr_tp_mult": (1.5, 4.0, 0.5),
        }

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        df = df.copy()
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values

        atr_vals = self.atr(highs, lows, closes, p['atr_period'])
        sh_idx, sh_prices, sl_idx, sl_prices = self.find_swing_points(
            highs, lows, p['swing_lookback'])

        # Build S/R levels with touch counts
        resistance_levels = []
        support_levels = []

        for k in range(len(sh_idx)):
            level = sh_prices[k]
            touches = sum(1 for h in highs[:sh_idx[k]] if abs(h - level) / level < p['proximity_pct'] / 100)
            if touches >= p['level_touches'] - 1:
                resistance_levels.append(level)

        for k in range(len(sl_idx)):
            level = sl_prices[k]
            touches = sum(1 for l in lows[:sl_idx[k]] if abs(l - level) / level < p['proximity_pct'] / 100)
            if touches >= p['level_touches'] - 1:
                support_levels.append(level)

        signals = []
        daily_trades = 0
        last_date = None
        min_start = max(p['swing_lookback'] * 2, p['atr_period']) + 10

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

            # Check proximity to support
            for level in support_levels:
                if abs(closes[i] - level) / level * 100 < p['proximity_pct']:
                    if lows[i] <= level and closes[i] > level:  # Bounce
                        sl = level - atr_val * p['atr_sl_mult']
                        tp = closes[i] + atr_val * p['atr_tp_mult']
                        rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                        if rr >= p['risk_reward_min']:
                            signals.append(TradeSignal(
                                symbol=symbol, direction="BUY",
                                entry_price=closes[i], stop_loss=sl, take_profit=tp,
                                strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                                metadata={"level": level, "type": "support_bounce"}
                            ))
                            daily_trades += 1
                            break

            # Check proximity to resistance
            for level in resistance_levels:
                if abs(closes[i] - level) / level * 100 < p['proximity_pct']:
                    if highs[i] >= level and closes[i] < level:  # Rejection
                        sl = level + atr_val * p['atr_sl_mult']
                        tp = closes[i] - atr_val * p['atr_tp_mult']
                        rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                        if rr >= p['risk_reward_min']:
                            signals.append(TradeSignal(
                                symbol=symbol, direction="SELL",
                                entry_price=closes[i], stop_loss=sl, take_profit=tp,
                                strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                                metadata={"level": level, "type": "resistance_rejection"}
                            ))
                            daily_trades += 1
                            break

        return signals
