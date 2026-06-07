"""
MM-024: NYR-01 — NY Reversal
════════════════════════════
Identifies reversals at London session extremes when the NY
session opens. Price near London high/low + candlestick
confirmation (engulf / pin bar) triggers fade trades toward
the London midpoint or opposite extreme.

Best instruments: EURUSD, GBPUSD, XAUUSD, NAS100
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class NYReversal(Strategy):
    STRATEGY_ID = "MM-024"
    STRATEGY_NAME = "NY Reversal"
    STRATEGY_TYPE = "reversal"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "atr_period": 14,
            "proximity_atr_mult": 0.1,    # Within this * ATR of London extreme
            "sl_atr_mult": 0.05,          # SL beyond London extreme by this * ATR
            "min_rr": 1.0,
            "session_filter": True,
            "max_daily_trades": 1,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "atr_period": (10, 20, 1),
            "proximity_atr_mult": (0.05, 0.3, 0.05),
            "sl_atr_mult": (0.02, 0.15, 0.01),
            "min_rr": (0.5, 2.0, 0.25),
        }

    # ── Candlestick pattern helpers ────────────────────────────────

    @staticmethod
    def _is_bullish_engulf(opens: np.ndarray, closes: np.ndarray, i: int) -> bool:
        """Prior candle bearish, current candle bullish and body engulfs prior body."""
        if i < 1:
            return False
        prev_body_top = max(opens[i - 1], closes[i - 1])
        prev_body_bot = min(opens[i - 1], closes[i - 1])
        curr_body_top = max(opens[i], closes[i])
        curr_body_bot = min(opens[i], closes[i])
        return (
            closes[i - 1] < opens[i - 1]        # prior bearish
            and closes[i] > opens[i]             # current bullish
            and curr_body_bot <= prev_body_top    # current engulfs prior
            and curr_body_top >= prev_body_bot
        )

    @staticmethod
    def _is_bearish_engulf(opens: np.ndarray, closes: np.ndarray, i: int) -> bool:
        """Prior candle bullish, current candle bearish and body engulfs prior body."""
        if i < 1:
            return False
        prev_body_top = max(opens[i - 1], closes[i - 1])
        prev_body_bot = min(opens[i - 1], closes[i - 1])
        curr_body_top = max(opens[i], closes[i])
        curr_body_bot = min(opens[i], closes[i])
        return (
            closes[i - 1] > opens[i - 1]        # prior bullish
            and closes[i] < opens[i]             # current bearish
            and curr_body_top >= prev_body_bot    # current engulfs prior
            and curr_body_bot <= prev_body_top
        )

    @staticmethod
    def _is_bullish_pin(opens: np.ndarray, highs: np.ndarray,
                        lows: np.ndarray, closes: np.ndarray, i: int,
                        wick_mult: float = 2.0) -> bool:
        """Pin bar with long lower wick, body at top. Wick >= wick_mult * body."""
        body = abs(closes[i] - opens[i])
        if body == 0:
            return False
        body_top = max(closes[i], opens[i])
        lower_wick = body_top - lows[i]
        return lower_wick >= wick_mult * body

    @staticmethod
    def _is_bearish_pin(opens: np.ndarray, highs: np.ndarray,
                        lows: np.ndarray, closes: np.ndarray, i: int,
                        wick_mult: float = 2.0) -> bool:
        """Pin bar with long upper wick, body at bottom. Wick >= wick_mult * body."""
        body = abs(closes[i] - opens[i])
        if body == 0:
            return False
        body_bot = min(closes[i], opens[i])
        upper_wick = highs[i] - body_bot
        return upper_wick >= wick_mult * body

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        df = df.copy()
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        opens = df['open'].values

        atr_vals = self.atr(highs, lows, closes, p['atr_period'])

        signals = []
        daily_trades = 0
        last_date = None

        # ── State tracked per day ──────────────────────────────────
        london_high = None
        london_low = None
        london_mid = None

        min_start = p['atr_period'] + 20

        for i in range(min_start, len(df) - 1):
            if not hasattr(df.index, 'hour'):
                continue

            ts = df.index[i]
            h = ts.hour
            m = ts.minute
            wd = ts.weekday()
            cur_date = ts.date() if hasattr(ts, 'date') else None

            # ── New day reset ──────────────────────────────────────
            if cur_date != last_date:
                daily_trades = 0
                london_high = None
                london_low = None
                london_mid = None
                last_date = cur_date

            if pd.isna(atr_vals[i]):
                continue
            atr_val = atr_vals[i]

            # ── Track London session high/low (07:00-12:00 GMT) ───
            if 7 <= h < 12 and wd < 5:
                if london_high is None:
                    london_high = highs[i]
                    london_low = lows[i]
                else:
                    london_high = max(london_high, highs[i])
                    london_low = min(london_low, lows[i])
                london_mid = (london_high + london_low) / 2.0
                continue  # Don't signal during London session tracking

            if london_high is None or london_low is None or london_mid is None:
                continue

            # ── NY session: check for reversal setup (13:00-14:30 GMT) ──
            if p['session_filter']:
                if wd >= 5:
                    continue
                # Entry window: 13:00 to 14:30 GMT
                if h < 13 or (h == 14 and m > 30) or h > 14:
                    continue

            if daily_trades >= p['max_daily_trades']:
                continue

            proximity = atr_val * p['proximity_atr_mult']

            # ── Short setup: price near London high ────────────────
            if closes[i] >= london_high - proximity:
                # Need bearish confirmation
                bearish_engulf = self._is_bearish_engulf(opens, closes, i)
                bearish_pin = self._is_bearish_pin(opens, highs, lows, closes, i)

                if bearish_engulf or bearish_pin:
                    entry = closes[i]
                    sl = london_high + atr_val * p['sl_atr_mult']
                    tp1 = london_mid
                    tp2 = london_low
                    risk = sl - entry
                    reward = entry - tp1
                    rr = reward / risk if risk > 0 else 0

                    if rr >= p['min_rr']:
                        signals.append(self._sig(
                            symbol, "SELL", entry, sl, tp1, df, i,
                            tp2=tp2, rr=rr,
                            metadata={
                                "london_high": float(london_high),
                                "london_low": float(london_low),
                                "london_mid": float(london_mid),
                                "confirmation": "bearish_engulf" if bearish_engulf else "bearish_pin",
                                "setup": "near_london_high",
                            }
                        ))
                        daily_trades += 1

            # ── Long setup: price near London low ──────────────────
            elif closes[i] <= london_low + proximity:
                # Need bullish confirmation
                bullish_engulf = self._is_bullish_engulf(opens, closes, i)
                bullish_pin = self._is_bullish_pin(opens, highs, lows, closes, i)

                if bullish_engulf or bullish_pin:
                    entry = closes[i]
                    sl = london_low - atr_val * p['sl_atr_mult']
                    tp1 = london_mid
                    tp2 = london_high
                    risk = entry - sl
                    reward = tp1 - entry
                    rr = reward / risk if risk > 0 else 0

                    if rr >= p['min_rr']:
                        signals.append(self._sig(
                            symbol, "BUY", entry, sl, tp1, df, i,
                            tp2=tp2, rr=rr,
                            metadata={
                                "london_high": float(london_high),
                                "london_low": float(london_low),
                                "london_mid": float(london_mid),
                                "confirmation": "bullish_engulf" if bullish_engulf else "bullish_pin",
                                "setup": "near_london_low",
                            }
                        ))
                        daily_trades += 1

        return signals
