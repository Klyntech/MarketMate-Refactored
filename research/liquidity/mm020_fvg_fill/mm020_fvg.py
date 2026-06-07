"""
MM-020: FVG-01 — Fair Value Gap Fill
═══════════════════════════════════════
A Fair Value Gap is a 3-candle imbalance where the wick of candle 1 and
the wick of candle 3 don't overlap. Price frequently returns to fill these
gaps. Uses EMA(200) as a higher-timeframe bias filter — only trades FVGs
in the direction of the trend.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class FairValueGapFill(Strategy):
    STRATEGY_ID = "MM-020"
    STRATEGY_NAME = "Fair Value Gap Fill"
    STRATEGY_TYPE = "mean_reversion"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "ema_period": 200,
            "fvg_max_age": 15,
            "atr_period": 14,
            "sl_atr_buffer": 0.2,
            "min_rr": 1.5,
            "min_fvg_size_atr": 0.3,
            "session_filter": True,
            "max_daily_trades": 2,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "ema_period": (100, 300, 10),
            "fvg_max_age": (10, 25, 1),
            "min_rr": (1.0, 2.0, 0.1),
            "min_fvg_size_atr": (0.2, 0.5, 0.05),
        }

    # ── Signal Generation ─────────────────────────────────────────────

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values

        atr_vals = self.atr(highs, lows, closes, p["atr_period"])
        ema_vals = self.ema(closes, p["ema_period"])
        sh_idx, sh_prices, sl_idx, sl_prices = self.find_swing_points(
            highs, lows, 7
        )

        signals: List[TradeSignal] = []
        daily_trades = 0
        last_date = None

        # Active FVGs: list of dicts
        # direction, fvg_high, fvg_low, fvg_mid, bar_idx, ema_direction
        active_fvgs: List[Dict[str, Any]] = []

        min_start = max(p["ema_period"], p["atr_period"]) + 10

        for i in range(min_start, len(df)):
            # ── Session & daily limit ─────────────────────────────────
            if p["session_filter"] and hasattr(df.index, "hour"):
                h = df.index[i].hour
                if not (7 <= h < 17 and df.index[i].weekday() < 5):
                    active_fvgs = [
                        fvg for fvg in active_fvgs
                        if (i - fvg["bar_idx"]) <= p["fvg_max_age"]
                    ]
                    continue

            cur_date = df.index[i].date() if hasattr(df.index[i], "date") else None
            if cur_date != last_date:
                daily_trades = 0
                last_date = cur_date
            if daily_trades >= p["max_daily_trades"]:
                continue

            if pd.isna(atr_vals[i]):
                continue
            atr_val = atr_vals[i]

            # ── Age out expired FVGs ──────────────────────────────────
            active_fvgs = [
                fvg for fvg in active_fvgs
                if (i - fvg["bar_idx"]) <= p["fvg_max_age"]
            ]

            # ── Detect new FVGs (requires at least 3 candles) ─────────
            if i >= 2:
                # Bullish FVG: low of candle[i] > high of candle[i-2]
                if lows[i] > highs[i - 2]:
                    fvg_high = lows[i]
                    fvg_low = highs[i - 2]
                    fvg_size = fvg_high - fvg_low

                    # Minimum FVG size filter
                    if fvg_size >= atr_val * p["min_fvg_size_atr"]:
                        fvg_mid = (fvg_high + fvg_low) / 2.0
                        # EMA bias: only bullish FVGs when above EMA
                        if closes[i] > ema_vals[i]:
                            active_fvgs.append({
                                "direction": "BUY",
                                "fvg_high": fvg_high,
                                "fvg_low": fvg_low,
                                "fvg_mid": fvg_mid,
                                "bar_idx": i,
                                "ema_direction": "bullish",
                            })

                # Bearish FVG: high of candle[i] < low of candle[i-2]
                if highs[i] < lows[i - 2]:
                    fvg_high = lows[i - 2]
                    fvg_low = highs[i]
                    fvg_size = fvg_high - fvg_low

                    # Minimum FVG size filter
                    if fvg_size >= atr_val * p["min_fvg_size_atr"]:
                        fvg_mid = (fvg_high + fvg_low) / 2.0
                        # EMA bias: only bearish FVGs when below EMA
                        if closes[i] < ema_vals[i]:
                            active_fvgs.append({
                                "direction": "SELL",
                                "fvg_high": fvg_high,
                                "fvg_low": fvg_low,
                                "fvg_mid": fvg_mid,
                                "bar_idx": i,
                                "ema_direction": "bearish",
                            })

            # ── Remove filled FVGs (price crossed through completely) ──
            fvgs_to_remove: List[int] = []
            for fvg_idx, fvg in enumerate(active_fvgs):
                if fvg["direction"] == "BUY":
                    # Filled if close goes below FVG low (full invalidation)
                    if closes[i] < fvg["fvg_low"]:
                        fvgs_to_remove.append(fvg_idx)
                elif fvg["direction"] == "SELL":
                    # Filled if close goes above FVG high (full invalidation)
                    if closes[i] > fvg["fvg_high"]:
                        fvgs_to_remove.append(fvg_idx)

            # ── Check FVG midpoint retests ────────────────────────────
            for fvg_idx, fvg in enumerate(active_fvgs):
                if fvg_idx in fvgs_to_remove:
                    continue
                # Skip FVGs that just formed (need at least 1 bar delay)
                if i - fvg["bar_idx"] < 1:
                    continue

                triggered = False

                if fvg["direction"] == "BUY":
                    # Price returns to FVG midpoint: low touches midpoint
                    if lows[i] <= fvg["fvg_mid"]:
                        entry = closes[i]
                        sl = fvg["fvg_low"] - atr_val * p["sl_atr_buffer"]
                        # TP: opposite end of FVG zone (top)
                        tp = fvg["fvg_high"]
                        # TP2: next swing high above FVG high, or extend
                        tp2 = fvg["fvg_high"] + (fvg["fvg_high"] - fvg["fvg_low"])
                        for j in range(len(sh_idx)):
                            if sh_idx[j] > fvg["bar_idx"] and sh_prices[j] > fvg["fvg_high"]:
                                tp2 = sh_prices[j]
                                break

                        risk = entry - sl
                        reward = tp - entry
                        rr = reward / risk if risk > 0 else 0

                        if rr >= p["min_rr"]:
                            signals.append(self._sig(
                                symbol=symbol, direction="BUY",
                                entry_price=entry, sl=sl, tp=tp,
                                df=df, bar_idx=i,
                                tp2=tp2, rr=rr,
                                metadata={
                                    "fvg_high": fvg["fvg_high"],
                                    "fvg_low": fvg["fvg_low"],
                                    "fvg_mid": fvg["fvg_mid"],
                                    "fvg_bar": fvg["bar_idx"],
                                    "type": "bullish_fvg_fill",
                                },
                            ))
                            daily_trades += 1
                            triggered = True

                elif fvg["direction"] == "SELL":
                    # Price returns to FVG midpoint: high touches midpoint
                    if highs[i] >= fvg["fvg_mid"]:
                        entry = closes[i]
                        sl = fvg["fvg_high"] + atr_val * p["sl_atr_buffer"]
                        # TP: opposite end of FVG zone (bottom)
                        tp = fvg["fvg_low"]
                        # TP2: next swing low below FVG low, or extend
                        tp2 = fvg["fvg_low"] - (fvg["fvg_high"] - fvg["fvg_low"])
                        for j in range(len(sl_idx)):
                            if sl_idx[j] > fvg["bar_idx"] and sl_prices[j] < fvg["fvg_low"]:
                                tp2 = sl_prices[j]
                                break

                        risk = sl - entry
                        reward = entry - tp
                        rr = reward / risk if risk > 0 else 0

                        if rr >= p["min_rr"]:
                            signals.append(self._sig(
                                symbol=symbol, direction="SELL",
                                entry_price=entry, sl=sl, tp=tp,
                                df=df, bar_idx=i,
                                tp2=tp2, rr=rr,
                                metadata={
                                    "fvg_high": fvg["fvg_high"],
                                    "fvg_low": fvg["fvg_low"],
                                    "fvg_mid": fvg["fvg_mid"],
                                    "fvg_bar": fvg["bar_idx"],
                                    "type": "bearish_fvg_fill",
                                },
                            ))
                            daily_trades += 1
                            triggered = True

                if triggered:
                    fvgs_to_remove.append(fvg_idx)

            # Remove consumed / filled / expired FVGs
            for idx in sorted(set(fvgs_to_remove), reverse=True):
                if idx < len(active_fvgs):
                    active_fvgs.pop(idx)

        return signals
