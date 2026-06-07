"""
MM-021: MSS-01 — Market Structure Shift Entry
═══════════════════════════════════════════════
After a liquidity sweep, the first Market Structure Shift confirms the
reversal is institutional. This strategy detects the sweep, waits for
a BOS in the opposite direction (MSS), and enters on the next candle
open after MSS confirmation.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List, Optional
from .base import Strategy, TradeSignal


class MarketStructureShift(Strategy):
    STRATEGY_ID = "MM-021"
    STRATEGY_NAME = "Market Structure Shift Entry"
    STRATEGY_TYPE = "reversal"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "swing_lookback": 7,
            "mss_max_bars": 8,
            "atr_period": 14,
            "atr_tp_mult": 2.0,
            "min_rr": 1.5,
            "session_filter": True,
            "max_daily_trades": 2,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "swing_lookback": (5, 10, 1),
            "mss_max_bars": (5, 12, 1),
            "atr_tp_mult": (1.5, 3.0, 0.1),
            "min_rr": (1.0, 2.0, 0.1),
        }

    # ── Signal Generation ─────────────────────────────────────────────

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values

        atr_vals = self.atr(highs, lows, closes, p["atr_period"])
        sh_idx, sh_prices, sl_idx, sl_prices = self.find_swing_points(
            highs, lows, p["swing_lookback"]
        )

        signals: List[TradeSignal] = []
        daily_trades = 0
        last_date = None

        # Pending sweep event: (direction, sweep_level, sweep_wick, bar_idx)
        # direction = "BUY" after low sweep, "SELL" after high sweep
        pending_sweep: Optional[Dict[str, Any]] = None

        min_start = max(p["swing_lookback"] * 2 + 1, p["atr_period"]) + 10

        for i in range(min_start, len(df)):
            # ── Session & daily limit ─────────────────────────────────
            if p["session_filter"] and hasattr(df.index, "hour"):
                h = df.index[i].hour
                if not (7 <= h < 17 and df.index[i].weekday() < 5):
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

            # ── Get recent swing levels ───────────────────────────────
            recent_sh = [(int(sh_idx[j]), float(sh_prices[j]))
                         for j in range(len(sh_idx)) if sh_idx[j] < i]
            recent_sl = [(int(sl_idx[j]), float(sl_prices[j]))
                         for j in range(len(sl_idx)) if sl_idx[j] < i]

            # ── Detect liquidity sweeps ───────────────────────────────

            # High sweep: price wicks above a swing high then closes below it
            if len(recent_sh) > 0:
                last_sh_bar, last_sh_price = recent_sh[-1]
                if highs[i] > last_sh_price and closes[i] < last_sh_price:
                    pending_sweep = {
                        "direction": "SELL",
                        "sweep_level": last_sh_price,
                        "sweep_wick": highs[i],  # The extreme of the sweep
                        "bar_idx": i,
                    }

            # Low sweep: price wicks below a swing low then closes above it
            if len(recent_sl) > 0:
                last_sl_bar, last_sl_price = recent_sl[-1]
                if lows[i] < last_sl_price and closes[i] > last_sl_price:
                    pending_sweep = {
                        "direction": "BUY",
                        "sweep_level": last_sl_price,
                        "sweep_wick": lows[i],  # The extreme of the sweep
                        "bar_idx": i,
                    }

            # ── Check pending sweep for MSS confirmation ──────────────
            if pending_sweep is not None:
                bars_since_sweep = i - pending_sweep["bar_idx"]

                # Expire stale sweeps
                if bars_since_sweep > p["mss_max_bars"]:
                    pending_sweep = None
                    continue

                mss_confirmed = False

                if pending_sweep["direction"] == "BUY":
                    # After a low sweep, look for BOS above a swing high
                    # (bullish MSS: price breaks above a swing high)
                    for sh_bar, sh_price in recent_sh:
                        if sh_bar > pending_sweep["bar_idx"]:
                            if closes[i] > sh_price and closes[i - 1] <= sh_price:
                                mss_confirmed = True
                                break
                        # Also check if current bar itself is the BOS
                        if sh_bar <= pending_sweep["bar_idx"]:
                            if closes[i] > sh_price and (i > pending_sweep["bar_idx"] + 1):
                                # BOS of a swing high that was before the sweep
                                mss_confirmed = True
                                break

                    # Simplified MSS: close breaks above the most recent swing
                    # high that formed after the sweep
                    if not mss_confirmed and recent_sh:
                        # Find swing highs formed after the sweep
                        post_sweep_sh = [(b, pr) for b, pr in recent_sh
                                         if b > pending_sweep["bar_idx"]]
                        if post_sweep_sh:
                            _, highest_sh = max(post_sweep_sh, key=lambda x: x[1])
                            if closes[i] > highest_sh:
                                mss_confirmed = True

                    if mss_confirmed:
                        entry = closes[i]
                        sl = pending_sweep["sweep_wick"] - atr_val * 0.1  # Just below sweep wick
                        # TP: next swing high above entry, or ATR-based
                        tp_target = None
                        for sh_bar, sh_price in recent_sh:
                            if sh_price > entry:
                                tp_target = sh_price
                                break
                        if tp_target is None:
                            tp_target = entry + atr_val * p["atr_tp_mult"]
                        tp = tp_target
                        tp2 = entry + atr_val * 3.0

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
                                    "sweep_level": pending_sweep["sweep_level"],
                                    "sweep_wick": pending_sweep["sweep_wick"],
                                    "sweep_bar": pending_sweep["bar_idx"],
                                    "type": "bullish_mss",
                                },
                            ))
                            daily_trades += 1
                        pending_sweep = None

                elif pending_sweep["direction"] == "SELL":
                    # After a high sweep, look for BOS below a swing low
                    # (bearish MSS: price breaks below a swing low)
                    for sl_bar, sl_price in recent_sl:
                        if sl_bar > pending_sweep["bar_idx"]:
                            if closes[i] < sl_price and closes[i - 1] >= sl_price:
                                mss_confirmed = True
                                break
                        if sl_bar <= pending_sweep["bar_idx"]:
                            if closes[i] < sl_price and (i > pending_sweep["bar_idx"] + 1):
                                mss_confirmed = True
                                break

                    # Simplified MSS: close breaks below the most recent swing
                    # low that formed after the sweep
                    if not mss_confirmed and recent_sl:
                        post_sweep_sl = [(b, pr) for b, pr in recent_sl
                                         if b > pending_sweep["bar_idx"]]
                        if post_sweep_sl:
                            _, lowest_sl = min(post_sweep_sl, key=lambda x: x[1])
                            if closes[i] < lowest_sl:
                                mss_confirmed = True

                    if mss_confirmed:
                        entry = closes[i]
                        sl = pending_sweep["sweep_wick"] + atr_val * 0.1  # Just above sweep wick
                        # TP: next swing low below entry, or ATR-based
                        tp_target = None
                        for sl_bar, sl_price in recent_sl:
                            if sl_price < entry:
                                tp_target = sl_price
                                break
                        if tp_target is None:
                            tp_target = entry - atr_val * p["atr_tp_mult"]
                        tp = tp_target
                        tp2 = entry - atr_val * 3.0

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
                                    "sweep_level": pending_sweep["sweep_level"],
                                    "sweep_wick": pending_sweep["sweep_wick"],
                                    "sweep_bar": pending_sweep["bar_idx"],
                                    "type": "bearish_mss",
                                },
                            ))
                            daily_trades += 1
                        pending_sweep = None

        return signals
