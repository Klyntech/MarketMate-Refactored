"""
MM-014: FBRT — Fibonacci Retracement Entry
═══════════════════════════════════════════
Identifies swing moves and enters on Fibonacci pullback levels.
Uses 0.618 (Golden Ratio) as primary entry zone.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class FibonacciRetracement(Strategy):
    STRATEGY_ID = "MM-014"
    STRATEGY_NAME = "Fibonacci Retracement Entry"
    STRATEGY_TYPE = "trend"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "swing_lookback": 10,
            "fib_level": 0.618,          # Primary fib entry level
            "fib_zone_width": 0.05,       # Zone around fib level (%)
            "atr_period": 14,
            "atr_sl_mult": 1.2,
            "atr_tp_mult": 2.5,
            "min_swing_pct": 1.0,         # Min swing size % to consider
            "risk_reward_min": 1.5,
            "session_filter": True,
            "max_daily_trades": 3,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "fib_level": (0.382, 0.786, 0.118),
            "fib_zone_width": (0.02, 0.1, 0.01),
            "atr_sl_mult": (0.8, 2.0, 0.1),
            "atr_tp_mult": (2.0, 5.0, 0.5),
            "min_swing_pct": (0.5, 3.0, 0.5),
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

            # Find the most recent swing
            recent_sh = sh_idx[sh_idx < i]
            recent_sl = sl_idx[sl_idx < i]

            if len(recent_sh) < 1 or len(recent_sl) < 1:
                continue

            # Bullish: swing low to swing high, retrace to fib
            last_sh_bar = recent_sh[-1]
            last_sl_bar = recent_sl[sl_idx < last_sh_bar]
            if len(last_sl_bar) > 0:
                last_sl_bar = last_sl_bar[-1]
                swing_high = sh_prices[recent_sh[-1] == sh_idx][0] if len(sh_prices) > 0 else highs[last_sh_bar]
                swing_low = sl_prices[recent_sl[-1] == sl_idx][0] if len(sl_prices) > 0 else lows[last_sl_bar]

                swing_pct = (swing_high - swing_low) / swing_low * 100
                if swing_pct >= p['min_swing_pct']:
                    fib_price = swing_high - (swing_high - swing_low) * p['fib_level']
                    zone_width = fib_price * p['fib_zone_width'] / 100

                    if abs(closes[i] - fib_price) <= zone_width and closes[i] > closes[i-1]:
                        sl = swing_low - atr_val * p['atr_sl_mult'] * 0.5
                        tp = swing_high + (swing_high - swing_low) * 0.272  # 127.2% ext
                        rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                        if rr >= p['risk_reward_min']:
                            signals.append(TradeSignal(
                                symbol=symbol, direction="BUY",
                                entry_price=closes[i], stop_loss=sl, take_profit=tp,
                                strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                                metadata={"fib_level": p['fib_level'], "fib_price": fib_price}
                            ))
                            daily_trades += 1

            # Bearish: swing high to swing low, retrace to fib
            last_sl_bar2 = recent_sl[-1]
            last_sh_bar2 = sh_idx[sh_idx < last_sl_bar2]
            if len(last_sh_bar2) > 0:
                last_sh_bar2 = last_sh_bar2[-1]
                swing_high2 = sh_prices[sh_idx == last_sh_bar2]
                swing_low2 = sl_prices[sl_idx == last_sl_bar2]

                if len(swing_high2) > 0 and len(swing_low2) > 0:
                    sh2, sl2 = swing_high2[0], swing_low2[0]
                    swing_pct2 = (sh2 - sl2) / sl2 * 100
                    if swing_pct2 >= p['min_swing_pct']:
                        fib_price2 = sl2 + (sh2 - sl2) * p['fib_level']
                        zone_width2 = fib_price2 * p['fib_zone_width'] / 100

                        if abs(closes[i] - fib_price2) <= zone_width2 and closes[i] < closes[i-1]:
                            s_sl = sh2 + atr_val * p['atr_sl_mult'] * 0.5
                            s_tp = sl2 - (sh2 - sl2) * 0.272
                            rr = (closes[i] - s_tp) / (s_sl - closes[i]) if (s_sl - closes[i]) > 0 else 0
                            if rr >= p['risk_reward_min']:
                                signals.append(TradeSignal(
                                    symbol=symbol, direction="SELL",
                                    entry_price=closes[i], stop_loss=s_sl, take_profit=s_tp,
                                    strategy_id=self.STRATEGY_ID, rr_ratio=rr,
                                    metadata={"fib_level": p['fib_level'], "fib_price": fib_price2}
                                ))
                                daily_trades += 1

        return signals
