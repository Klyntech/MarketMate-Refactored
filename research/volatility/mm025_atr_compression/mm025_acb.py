"""
MM-025: ACB-01 — ATR Compression Breakout v2
══════════════════════════════════════════════
Detects volatility compression (declining ATR) followed by an
expansion bar with volume confirmation. Trades the breakout
of the N-bar high/low with ATR-based stops and targets.

Includes 4-bar spike retrace rule and session gating.

Instrument tiering: crypto (BTCUSD, ETHUSD) = full size;
XAUUSD = moderate; forex = EXCLUDED (documented in metadata).
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class ATRCompressionBreakout(Strategy):
    STRATEGY_ID = "MM-025"
    STRATEGY_NAME = "ATR Compression Breakout v2"
    STRATEGY_TYPE = "breakout"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {
            "atr_period": 14,
            "compression_bars": 3,         # Min consecutive declining ATR bars
            "volume_mult": 1.5,            # Volume must exceed this * 20-bar avg
            "lookback": 20,                # Lookback for N-bar high/low breakout
            "tp_atr_mult": 2.5,
            "tp2_atr_mult": 4.0,
            "sl_atr_mult": 1.0,
            "spike_retrace_pct": 0.5,      # 50% retrace of breakout candle body
            "spike_check_bars": 4,         # Bars to check for spike retrace
            "max_hold_bars": 8,            # Time stop: exit after this many bars
            "min_rr": 1.5,
            "session_filter": True,
            "max_daily_trades": 2,
        }

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {
            "atr_period": (10, 20, 1),
            "compression_bars": (2, 5, 1),
            "volume_mult": (1.2, 2.0, 0.1),
            "tp_atr_mult": (2.0, 4.0, 0.5),
            "sl_atr_mult": (0.8, 1.5, 0.1),
        }

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        p = self.params
        df = df.copy()
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values
        opens = df['open'].values
        volumes = df['volume'].values if 'volume' in df.columns else np.ones(len(df))

        atr_vals = self.atr(highs, lows, closes, p['atr_period'])
        vol_avg = self.sma(volumes.astype(float), p['lookback'])

        signals = []
        daily_trades = 0
        last_date = None

        # Instrument tiering — documented in metadata
        instrument_tier = self._classify_instrument(symbol)

        min_start = max(p['atr_period'], p['lookback']) + 10

        for i in range(min_start, len(df) - 1):
            if not hasattr(df.index, 'hour'):
                continue

            ts = df.index[i]
            h = ts.hour
            wd = ts.weekday()
            cur_date = ts.date() if hasattr(ts, 'date') else None

            # ── New day reset ──────────────────────────────────────
            if cur_date != last_date:
                daily_trades = 0
                last_date = cur_date

            # ── Session gate ───────────────────────────────────────
            if p['session_filter']:
                if wd >= 5:
                    continue
                # London open (07:00-10:00 GMT) or NY open (13:30-16:30 GMT)
                in_london = 7 <= h < 10
                in_ny = (h == 13 and ts.minute >= 30) or (14 <= h <= 16)
                if not (in_london or in_ny):
                    continue

            if daily_trades >= p['max_daily_trades']:
                continue

            # ── Pre-condition 1: ATR declining for compression_bars ──
            comp_bars = p['compression_bars']
            if i < comp_bars + 1:
                continue

            atr_declining = True
            for k in range(1, comp_bars + 1):
                if pd.isna(atr_vals[i - k]) or pd.isna(atr_vals[i - k - 1]):
                    atr_declining = False
                    break
                if atr_vals[i - k] > atr_vals[i - k - 1]:
                    atr_declining = False
                    break
            if not atr_declining:
                continue

            # ── Pre-condition 2: ATR expanding on current bar ──────
            if pd.isna(atr_vals[i]) or pd.isna(atr_vals[i - 1]):
                continue
            if atr_vals[i] <= atr_vals[i - 1]:
                continue

            # ── Pre-condition 3: Volume confirmation ───────────────
            if pd.isna(vol_avg[i]):
                continue
            if volumes[i] < vol_avg[i] * p['volume_mult']:
                continue

            # ── Pre-condition 4: N-bar breakout ────────────────────
            lb = p['lookback']
            if i < lb:
                continue

            n_bar_high = np.max(highs[i - lb:i])
            n_bar_low = np.min(lows[i - lb:i])
            atr_val = atr_vals[i]

            # Long breakout: close above N-bar high
            if closes[i] > n_bar_high:
                entry = closes[i]
                sl = entry - atr_val * p['sl_atr_mult']
                tp1 = entry + atr_val * p['tp_atr_mult']
                tp2 = entry + atr_val * p['tp2_atr_mult']
                risk = entry - sl
                reward = tp1 - entry
                rr = reward / risk if risk > 0 else 0

                if rr >= p['min_rr']:
                    # 4-bar spike retrace tracking in metadata
                    breakout_body = abs(closes[i] - opens[i])
                    retrace_level = entry - breakout_body * p['spike_retrace_pct']

                    signals.append(self._sig(
                        symbol, "BUY", entry, sl, tp1, df, i,
                        tp2=tp2, rr=rr,
                        metadata={
                            "n_bar_high": float(n_bar_high),
                            "n_bar_low": float(n_bar_low),
                            "atr_value": float(atr_val),
                            "volume_ratio": float(volumes[i] / vol_avg[i]) if vol_avg[i] > 0 else 0,
                            "breakout_type": "above_n_bar_high",
                            "instrument_tier": instrument_tier,
                            "max_hold_bars": p['max_hold_bars'],
                            "spike_retrace_pct": p['spike_retrace_pct'],
                            "spike_check_bars": p['spike_check_bars'],
                            "spike_retrace_level": float(retrace_level),
                            "breakout_body": float(breakout_body),
                        }
                    ))
                    daily_trades += 1

            # Short breakout: close below N-bar low
            elif closes[i] < n_bar_low:
                entry = closes[i]
                sl = entry + atr_val * p['sl_atr_mult']
                tp1 = entry - atr_val * p['tp_atr_mult']
                tp2 = entry - atr_val * p['tp2_atr_mult']
                risk = sl - entry
                reward = entry - tp1
                rr = reward / risk if risk > 0 else 0

                if rr >= p['min_rr']:
                    breakout_body = abs(closes[i] - opens[i])
                    retrace_level = entry + breakout_body * p['spike_retrace_pct']

                    signals.append(self._sig(
                        symbol, "SELL", entry, sl, tp1, df, i,
                        tp2=tp2, rr=rr,
                        metadata={
                            "n_bar_high": float(n_bar_high),
                            "n_bar_low": float(n_bar_low),
                            "atr_value": float(atr_val),
                            "volume_ratio": float(volumes[i] / vol_avg[i]) if vol_avg[i] > 0 else 0,
                            "breakout_type": "below_n_bar_low",
                            "instrument_tier": instrument_tier,
                            "max_hold_bars": p['max_hold_bars'],
                            "spike_retrace_pct": p['spike_retrace_pct'],
                            "spike_check_bars": p['spike_check_bars'],
                            "spike_retrace_level": float(retrace_level),
                            "breakout_body": float(breakout_body),
                        }
                    ))
                    daily_trades += 1

        return signals

    @staticmethod
    def _classify_instrument(symbol: str) -> str:
        """Classify instrument for position sizing tiering."""
        s = symbol.upper().replace("/", "").replace("-", "")
        crypto = {"BTCUSD", "ETHUSD"}
        metals = {"XAUUSD", "XAGUSD"}
        if s in crypto:
            return "crypto_full"
        elif s in metals:
            return "metals_moderate"
        else:
            return "forex_excluded"
