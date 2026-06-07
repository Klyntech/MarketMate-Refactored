"""
MM-019: OBR-01 — Order Block Retest
═══════════════════════════════════════
An order block is the last opposing candle before a strong impulsive move
that breaks structure. Price frequently returns to mitigate that zone before
continuing. Requires a liquidity sweep before the OB for validity, and
a pin bar or engulfing candle on retest for confirmation.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class OrderBlockRetest(Strategy):
    STRATEGY_ID = "MM-019"
    STRATEGY_NAME = "Order Block Retest"
    STRATEGY_TYPE = "reversal"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "swing_lookback": 7,
            "ob_max_age": 20,
            "atr_period": 14,
            "atr_sl_buffer": 0.3,
            "atr_tp_mult": 2.0,
            "min_rr": 1.5,
            "session_filter": True,
            "max_daily_trades": 2,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "swing_lookback": (5, 10, 1),
            "ob_max_age": (10, 30, 1),
            "atr_sl_buffer": (0.1, 0.5, 0.05),
            "atr_tp_mult": (1.5, 3.0, 0.1),
        }

    # ── Helpers ────────────────────────────────────────────────────────

    @staticmethod
    def _is_pin_bar_bullish(opn: float, high: float, low: float, close: float) -> bool:
        """Pin bar with long lower wick, body at top."""
        body = abs(close - opn)
        lower_wick = min(opn, close) - low
        upper_wick = high - max(opn, close)
        if body < 1e-10:
            return False
        return lower_wick > 2.0 * body and lower_wick > upper_wick

    @staticmethod
    def _is_pin_bar_bearish(opn: float, high: float, low: float, close: float) -> bool:
        """Pin bar with long upper wick, body at bottom."""
        body = abs(close - opn)
        upper_wick = high - max(opn, close)
        lower_wick = min(opn, close) - low
        if body < 1e-10:
            return False
        return upper_wick > 2.0 * body and upper_wick > lower_wick

    @staticmethod
    def _is_bullish_engulf(opn: float, close: float,
                           prev_opn: float, prev_close: float) -> bool:
        """Current bullish candle body engulfs prior candle body."""
        cur_body_low = min(opn, close)
        cur_body_high = max(opn, close)
        prev_body_low = min(prev_opn, prev_close)
        prev_body_high = max(prev_opn, prev_close)
        return (close > opn
                and cur_body_low <= prev_body_low
                and cur_body_high >= prev_body_high
                and (cur_body_high - cur_body_low) > (prev_body_high - prev_body_low))

    @staticmethod
    def _is_bearish_engulf(opn: float, close: float,
                           prev_opn: float, prev_close: float) -> bool:
        """Current bearish candle body engulfs prior candle body."""
        cur_body_low = min(opn, close)
        cur_body_high = max(opn, close)
        prev_body_low = min(prev_opn, prev_close)
        prev_body_high = max(prev_opn, prev_close)
        return (close < opn
                and cur_body_low <= prev_body_low
                and cur_body_high >= prev_body_high
                and (cur_body_high - cur_body_low) > (prev_body_high - prev_body_low))

    # ── Signal Generation ─────────────────────────────────────────────

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values
        opens = df["open"].values

        atr_vals = self.atr(highs, lows, closes, p["atr_period"])
        sh_idx, sh_prices, sl_idx, sl_prices = self.find_swing_points(
            highs, lows, p["swing_lookback"]
        )

        signals: List[TradeSignal] = []
        daily_trades = 0
        last_date = None

        # Active OBs: list of dicts with direction, ob_high, ob_low, bar_idx, sweep_level
        active_obs: List[Dict[str, Any]] = []

        min_start = max(p["swing_lookback"] * 2 + 1, p["atr_period"]) + 10
        lookback = p["swing_lookback"]

        for i in range(min_start, len(df)):
            # ── Session & daily limit ─────────────────────────────────
            if p["session_filter"] and hasattr(df.index, "hour"):
                h = df.index[i].hour
                if not (7 <= h < 17 and df.index[i].weekday() < 5):
                    # Still age OBs even outside session
                    active_obs = [
                        ob for ob in active_obs
                        if (i - ob["bar_idx"]) <= p["ob_max_age"]
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

            # ── Age out expired OBs ───────────────────────────────────
            active_obs = [
                ob for ob in active_obs
                if (i - ob["bar_idx"]) <= p["ob_max_age"]
            ]

            # ── Detect BOS and create new OBs ─────────────────────────
            # Get swing levels that are before the current bar
            recent_sh = [(int(sh_idx[j]), float(sh_prices[j]))
                         for j in range(len(sh_idx)) if sh_idx[j] < i]
            recent_sl = [(int(sl_idx[j]), float(sl_prices[j]))
                         for j in range(len(sl_idx)) if sl_idx[j] < i]

            # Bullish BOS: close breaks above the most recent swing high
            if recent_sh:
                last_sh_bar, last_sh_price = recent_sh[-1]
                if closes[i] > last_sh_price and closes[i - 1] <= last_sh_price:
                    # Check for liquidity sweep before this BOS:
                    # Price must have swept a prior swing low before the bullish move
                    sweep_found = False
                    sweep_level = 0.0
                    check_start = max(last_sh_bar, i - lookback * 3)
                    for k in range(check_start, i):
                        for sl_bar, sl_price in recent_sl:
                            if sl_bar < k:
                                # Wick below swing low then close above = sweep
                                if lows[k] < sl_price and closes[k] > sl_price:
                                    sweep_found = True
                                    sweep_level = sl_price
                                    break
                        if sweep_found:
                            break

                    if sweep_found:
                        # Find the order block: last bearish candle before the BOS move
                        # Search backwards from BOS bar
                        ob_bar = None
                        for k in range(i - 1, max(i - lookback * 2, 0), -1):
                            if closes[k] < opens[k]:  # bearish candle
                                ob_bar = k
                                break
                        if ob_bar is not None:
                            active_obs.append({
                                "direction": "BUY",
                                "ob_high": max(opens[ob_bar], closes[ob_bar]),
                                "ob_low": min(opens[ob_bar], closes[ob_bar]),
                                "bar_idx": ob_bar,
                                "sweep_level": sweep_level,
                                "bos_bar": i,
                            })

            # Bearish BOS: close breaks below the most recent swing low
            if recent_sl:
                last_sl_bar, last_sl_price = recent_sl[-1]
                if closes[i] < last_sl_price and closes[i - 1] >= last_sl_price:
                    # Check for liquidity sweep before this BOS:
                    # Price must have swept a prior swing high before the bearish move
                    sweep_found = False
                    sweep_level = 0.0
                    check_start = max(last_sl_bar, i - lookback * 3)
                    for k in range(check_start, i):
                        for sh_bar, sh_price in recent_sh:
                            if sh_bar < k:
                                # Wick above swing high then close below = sweep
                                if highs[k] > sh_price and closes[k] < sh_price:
                                    sweep_found = True
                                    sweep_level = sh_price
                                    break
                        if sweep_found:
                            break

                    if sweep_found:
                        # Find the order block: last bullish candle before the BOS move
                        ob_bar = None
                        for k in range(i - 1, max(i - lookback * 2, 0), -1):
                            if closes[k] > opens[k]:  # bullish candle
                                ob_bar = k
                                break
                        if ob_bar is not None:
                            active_obs.append({
                                "direction": "SELL",
                                "ob_high": max(opens[ob_bar], closes[ob_bar]),
                                "ob_low": min(opens[ob_bar], closes[ob_bar]),
                                "bar_idx": ob_bar,
                                "sweep_level": sweep_level,
                                "bos_bar": i,
                            })

            # ── Check OB retests with confirmation ─────────────────────
            obs_to_remove = []
            for ob_idx, ob in enumerate(active_obs):
                age = i - ob["bar_idx"]
                if age > p["ob_max_age"]:
                    obs_to_remove.append(ob_idx)
                    continue

                # Skip if we haven't moved past the BOS bar yet
                if i <= ob.get("bos_bar", 0):
                    continue

                confirmed = False

                if ob["direction"] == "BUY":
                    # Retest: low touches OB zone
                    if lows[i] <= ob["ob_high"] and lows[i] >= ob["ob_low"]:
                        # Check confirmation: pin bar or engulf
                        if self._is_pin_bar_bullish(
                            opens[i], highs[i], lows[i], closes[i]
                        ):
                            confirmed = True
                        elif i > 0 and self._is_bullish_engulf(
                            opens[i], closes[i], opens[i - 1], closes[i - 1]
                        ):
                            confirmed = True

                    # Also check if low enters the zone from below
                    elif lows[i] < ob["ob_low"] and closes[i] > ob["ob_low"]:
                        # Wick into OB with bullish close
                        if self._is_pin_bar_bullish(
                            opens[i], highs[i], lows[i], closes[i]
                        ):
                            confirmed = True

                    if confirmed:
                        entry = closes[i]
                        sl = ob["ob_low"] - atr_val * p["atr_sl_buffer"]
                        # TP: next swing high above entry, or ATR-based
                        tp_target = None
                        for sh_bar, sh_price in recent_sh:
                            if sh_price > entry and sh_bar > ob.get("bos_bar", 0):
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
                                    "ob_high": ob["ob_high"],
                                    "ob_low": ob["ob_low"],
                                    "ob_bar": ob["bar_idx"],
                                    "sweep_level": ob["sweep_level"],
                                    "type": "bullish_ob_retest",
                                },
                            ))
                            daily_trades += 1
                            obs_to_remove.append(ob_idx)

                elif ob["direction"] == "SELL":
                    # Retest: high touches OB zone
                    if highs[i] >= ob["ob_low"] and highs[i] <= ob["ob_high"]:
                        # Check confirmation: pin bar or engulf
                        if self._is_pin_bar_bearish(
                            opens[i], highs[i], lows[i], closes[i]
                        ):
                            confirmed = True
                        elif i > 0 and self._is_bearish_engulf(
                            opens[i], closes[i], opens[i - 1], closes[i - 1]
                        ):
                            confirmed = True

                    # Also check if high enters the zone from above
                    elif highs[i] > ob["ob_high"] and closes[i] < ob["ob_high"]:
                        # Wick into OB with bearish close
                        if self._is_pin_bar_bearish(
                            opens[i], highs[i], lows[i], closes[i]
                        ):
                            confirmed = True

                    if confirmed:
                        entry = closes[i]
                        sl = ob["ob_high"] + atr_val * p["atr_sl_buffer"]
                        # TP: next swing low below entry, or ATR-based
                        tp_target = None
                        for sl_bar, sl_price in recent_sl:
                            if sl_price < entry and sl_bar > ob.get("bos_bar", 0):
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
                                    "ob_high": ob["ob_high"],
                                    "ob_low": ob["ob_low"],
                                    "ob_bar": ob["bar_idx"],
                                    "sweep_level": ob["sweep_level"],
                                    "type": "bearish_ob_retest",
                                },
                            ))
                            daily_trades += 1
                            obs_to_remove.append(ob_idx)

            # Remove consumed / expired OBs (reverse order to keep indices valid)
            for idx in sorted(set(obs_to_remove), reverse=True):
                if idx < len(active_obs):
                    active_obs.pop(idx)

        return signals
