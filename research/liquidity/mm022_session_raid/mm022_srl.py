"""
MM-022: SRL-01 — Session High/Low Raid + Reversal
═══════════════════════════════════════════════════
Institutions raid session highs/lows to collect liquidity before the real
move. This strategy tracks the Asian session range (00:00-07:00 GMT),
then watches for a spike through either level at the London open. When
price fails to hold beyond the raided level and closes back inside,
enter in the opposite direction targeting the other side of the range.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List, Optional
from .base import Strategy, TradeSignal


class SessionRaidReversal(Strategy):
    STRATEGY_ID = "MM-022"
    STRATEGY_NAME = "Session High/Low Raid + Reversal"
    STRATEGY_TYPE = "reversal"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "atr_period": 14,
            "volume_mult": 1.3,
            "sl_atr_buffer": 0.3,
            "tp2_range_mult": 1.5,
            "min_rr": 1.0,
            "session_filter": True,
            "max_daily_trades": 1,
            "raid_max_bars": 3,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "volume_mult": (1.1, 1.5, 0.05),
            "sl_atr_buffer": (0.1, 0.5, 0.05),
            "tp2_range_mult": (1.0, 2.5, 0.1),
            "raid_max_bars": (2, 5, 1),
        }

    # ── Signal Generation ─────────────────────────────────────────────

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        closes = df["close"].values
        highs = df["high"].values
        lows = df["low"].values
        volumes = df["volume"].values if "volume" in df.columns else np.ones(len(df))

        atr_vals = self.atr(highs, lows, closes, p["atr_period"])

        # 20-bar average volume for volume spike detection
        vol_avg = np.full(len(df), np.nan)
        for i in range(20, len(df)):
            vol_avg[i] = np.mean(volumes[i - 20:i])

        signals: List[TradeSignal] = []
        daily_trades = 0
        last_date = None

        # Asian session tracking
        asian_high = -np.inf
        asian_low = np.inf
        asian_bars_count = 0
        asian_valid = False

        # Pending raids: list of dicts
        # direction, asian_level, raid_wick, bar_idx, asian_high, asian_low
        pending_raids: List[Dict[str, Any]] = []

        min_start = max(p["atr_period"], 20) + 10

        for i in range(min_start, len(df)):
            # Need datetime index for session logic
            if not hasattr(df.index, "hour"):
                continue

            hour = df.index[i].hour
            weekday = df.index[i].weekday()

            cur_date = df.index[i].date() if hasattr(df.index[i], "date") else None
            if cur_date != last_date:
                daily_trades = 0
                last_date = cur_date
                # Reset Asian session tracking for new day
                asian_high = -np.inf
                asian_low = np.inf
                asian_bars_count = 0
                asian_valid = False
                pending_raids = []

            if pd.isna(atr_vals[i]):
                continue
            atr_val = atr_vals[i]

            # ── Track Asian session (00:00-06:59 GMT) ─────────────────
            if 0 <= hour <= 6 and weekday < 5:
                if highs[i] > asian_high:
                    asian_high = highs[i]
                if lows[i] < asian_low:
                    asian_low = lows[i]
                asian_bars_count += 1
                if asian_bars_count >= 4:
                    asian_valid = True
                continue  # Don't process signals during Asian session

            # ── Skip if Asian range is not valid ───────────────────────
            if not asian_valid:
                continue

            # ── Session filter: only trade during London open window ───
            if p["session_filter"]:
                if not (7 <= hour < 10 and weekday < 5):
                    continue

            if daily_trades >= p["max_daily_trades"]:
                continue

            # ── Check for new raids during London open ────────────────
            asian_range = asian_high - asian_low

            # Bullish raid: price spikes below Asian low (wick below),
            # then we wait for close back above Asian low
            if lows[i] < asian_low and closes[i] >= asian_low:
                # Check confirmation: volume spike OR FVG
                vol_spike = False
                fvg_present = False

                if not pd.isna(vol_avg[i]):
                    vol_spike = volumes[i] > vol_avg[i] * p["volume_mult"]

                # FVG left by the wick: check if there's a gap between
                # current candle low and the candle 2 bars ago high
                if i >= 2:
                    if lows[i] < highs[i - 2]:
                        # There's a gap (FVG)
                        fvg_present = True

                if vol_spike or fvg_present:
                    pending_raids.append({
                        "direction": "BUY",
                        "asian_level": asian_low,
                        "raid_wick": lows[i],
                        "bar_idx": i,
                        "asian_high": asian_high,
                        "asian_low": asian_low,
                        "confirmed": True,  # Already closed back inside
                    })

            # Bearish raid: price spikes above Asian high (wick above),
            # then we wait for close back below Asian high
            if highs[i] > asian_high and closes[i] <= asian_high:
                vol_spike = False
                fvg_present = False

                if not pd.isna(vol_avg[i]):
                    vol_spike = volumes[i] > vol_avg[i] * p["volume_mult"]

                # FVG left by the wick
                if i >= 2:
                    if highs[i] > lows[i - 2]:
                        fvg_present = True

                if vol_spike or fvg_present:
                    pending_raids.append({
                        "direction": "SELL",
                        "asian_level": asian_high,
                        "raid_wick": highs[i],
                        "bar_idx": i,
                        "asian_high": asian_high,
                        "asian_low": asian_low,
                        "confirmed": True,
                    })

            # ── Also detect raids where price spikes but hasn't closed back yet ─
            # (These become pending and we check subsequent bars)
            if highs[i] > asian_high and closes[i] > asian_high:
                # Spike above Asian high, still above — watch for close back below
                vol_spike = False
                fvg_present = False
                if not pd.isna(vol_avg[i]):
                    vol_spike = volumes[i] > vol_avg[i] * p["volume_mult"]
                if i >= 2 and highs[i] > lows[i - 2]:
                    fvg_present = True
                if vol_spike or fvg_present:
                    pending_raids.append({
                        "direction": "SELL",
                        "asian_level": asian_high,
                        "raid_wick": highs[i],
                        "bar_idx": i,
                        "asian_high": asian_high,
                        "asian_low": asian_low,
                        "confirmed": False,
                    })

            if lows[i] < asian_low and closes[i] < asian_low:
                # Spike below Asian low, still below — watch for close back above
                vol_spike = False
                fvg_present = False
                if not pd.isna(vol_avg[i]):
                    vol_spike = volumes[i] > vol_avg[i] * p["volume_mult"]
                if i >= 2 and lows[i] < highs[i - 2]:
                    fvg_present = True
                if vol_spike or fvg_present:
                    pending_raids.append({
                        "direction": "BUY",
                        "asian_level": asian_low,
                        "raid_wick": lows[i],
                        "bar_idx": i,
                        "asian_high": asian_high,
                        "asian_low": asian_low,
                        "confirmed": False,
                    })

            # ── Process pending raids ──────────────────────────────────
            raids_to_remove: List[int] = []

            for raid_idx, raid in enumerate(pending_raids):
                bars_since_raid = i - raid["bar_idx"]

                # Expire old raids
                if bars_since_raid > p["raid_max_bars"]:
                    raids_to_remove.append(raid_idx)
                    continue

                if raid["confirmed"]:
                    # Already confirmed — generate signal immediately
                    entry = closes[i]
                    asian_range_width = raid["asian_high"] - raid["asian_low"]

                    if raid["direction"] == "BUY":
                        sl = raid["raid_wick"] - atr_val * p["sl_atr_buffer"]
                        tp = raid["asian_high"]  # Opposite Asian boundary
                        tp2 = raid["asian_high"] + asian_range_width * p["tp2_range_mult"]

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
                                    "asian_high": raid["asian_high"],
                                    "asian_low": raid["asian_low"],
                                    "raid_wick": raid["raid_wick"],
                                    "asian_bars": asian_bars_count,
                                    "type": "asian_low_raid",
                                },
                            ))
                            daily_trades += 1

                    elif raid["direction"] == "SELL":
                        sl = raid["raid_wick"] + atr_val * p["sl_atr_buffer"]
                        tp = raid["asian_low"]  # Opposite Asian boundary
                        tp2 = raid["asian_low"] - asian_range_width * p["tp2_range_mult"]

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
                                    "asian_high": raid["asian_high"],
                                    "asian_low": raid["asian_low"],
                                    "raid_wick": raid["raid_wick"],
                                    "asian_bars": asian_bars_count,
                                    "type": "asian_high_raid",
                                },
                            ))
                            daily_trades += 1

                    raids_to_remove.append(raid_idx)

                else:
                    # Not yet confirmed — check if price closes back inside
                    if raid["direction"] == "BUY":
                        # Waiting for close back above Asian low
                        if closes[i] >= raid["asian_level"]:
                            raid["confirmed"] = True
                    elif raid["direction"] == "SELL":
                        # Waiting for close back below Asian high
                        if closes[i] <= raid["asian_level"]:
                            raid["confirmed"] = True

            # Remove processed / expired raids
            for idx in sorted(set(raids_to_remove), reverse=True):
                if idx < len(pending_raids):
                    pending_raids.pop(idx)

        return signals
