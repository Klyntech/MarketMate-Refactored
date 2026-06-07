"""
MM-012: GPFL — Gap Fill Weekend
═══════════════════════════════
Trades the gap between Friday close and Monday open.
Statistical edge: most gaps fill within the first session.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class GapFill(Strategy):
    STRATEGY_ID = "MM-012"
    STRATEGY_NAME = "Gap Fill Weekend"
    STRATEGY_TYPE = "mean_reversion"
    # INSTRUMENT LOCKED: Only run on these instruments
    ALLOWED_INSTRUMENTS = ["NAS100", "US30", "GBPUSD"]

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "min_gap_pct": 0.15,         # Min gap size as % of price
            "atr_period": 14,
            "atr_sl_mult": 1.5,
            "max_fill_bars": 12,         # Max bars to wait for gap fill
            "risk_reward_min": 1.0,
            "session_filter": False,      # Gap trades happen at Monday open
            "max_daily_trades": 1,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "min_gap_pct": (0.05, 0.5, 0.05),
            "atr_sl_mult": (1.0, 2.5, 0.1),
            "max_fill_bars": (6, 24, 3),
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

        signals = []
        daily_trades = 0
        last_date = None
        gap_trade_taken = False

        min_start = p['atr_period'] + 10

        for i in range(min_start, len(df) - 1):
            cur_date = df.index[i].date() if hasattr(df.index[i], 'date') else None
            if cur_date != last_date:
                daily_trades = 0
                last_date = cur_date
                gap_trade_taken = False

            if pd.isna(atr_vals[i]):
                continue

            # Detect Monday (weekday 0) gap
            if not hasattr(df.index, 'weekday'):
                continue

            if df.index[i].weekday() != 0 or gap_trade_taken or daily_trades >= p['max_daily_trades']:
                continue

            # Find Friday close
            friday_close = None
            for j in range(i - 10, i):
                if df.index[j].weekday() == 4:  # Friday
                    friday_close = closes[j]

            if friday_close is None:
                continue

            gap = closes[i] - friday_close
            gap_pct = abs(gap) / friday_close * 100

            if gap_pct < p['min_gap_pct']:
                continue

            atr_val = atr_vals[i]

            # Gap up: sell to fill
            if gap > 0:
                sl = closes[i] + atr_val * p['atr_sl_mult']
                tp = friday_close  # Fill to Friday close
                rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(
                        symbol, "SELL", closes[i], sl, tp, df, i,
                        rr=rr, metadata={"gap_pct": gap_pct, "gap_type": "up"}
                    ))
                    daily_trades += 1
                    gap_trade_taken = True

            # Gap down: buy to fill
            elif gap < 0:
                sl = closes[i] - atr_val * p['atr_sl_mult']
                tp = friday_close
                rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(
                        symbol, "BUY", closes[i], sl, tp, df, i,
                        rr=rr, metadata={"gap_pct": gap_pct, "gap_type": "down"}
                    ))
                    daily_trades += 1
                    gap_trade_taken = True

        return signals
