"""
MM Strategy Library v2 — All 17 strategies in optimized form.
Every strategy now uses self._sig() to ensure entry_time and entry_bar
are always set, fixing the zero-trade issue.
"""

from __future__ import annotations
import numpy as np
import pandas as pd
from typing import Dict, Any, Tuple, List
from .base import Strategy, TradeSignal


class VCEAgressive(Strategy):
    """MM-002: Volatility Compression Expansion - Aggressive breakout after compression."""
    STRATEGY_ID = "MM-002"
    STRATEGY_NAME = "VCE-A Volatility Compression Expansion"
    STRATEGY_TYPE = "breakout"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"atr_short": 7, "atr_long": 50, "compression_ratio": 0.7,
                "atr_sl_mult": 1.2, "atr_tp_mult": 2.5, "ema_trend": 100,
                "compression_min_bars": 3, "risk_reward_min": 1.2,
                "session_filter": False, "max_daily_trades": 5}

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {"atr_short": (5, 14, 1), "atr_long": (30, 80, 5),
                "compression_ratio": (0.5, 0.9, 0.05), "atr_sl_mult": (0.8, 2.0, 0.1),
                "atr_tp_mult": (1.5, 4.0, 0.5), "ema_trend": (50, 200, 25)}

    def generate_signals(self, df, symbol=""):
        p = self.params
        closes, highs, lows = df['close'].values, df['high'].values, df['low'].values
        atr_s = self.atr(highs, lows, closes, p['atr_short'])
        atr_l = self.atr(highs, lows, closes, p['atr_long'])
        ema = self.ema(closes, p['ema_trend'])

        signals = []
        comp_bars = 0
        comp_high, comp_low = 0.0, float('inf')
        daily_trades, last_date = 0, None
        min_start = max(p['atr_long'], p['ema_trend']) + 10

        for i in range(min_start, len(df) - 1):
            if pd.isna(atr_l[i]) or pd.isna(atr_s[i]):
                continue

            vol_ratio = atr_s[i] / atr_l[i] if atr_l[i] > 0 else 1.0
            compressed = vol_ratio < p['compression_ratio']

            if compressed:
                comp_bars += 1
                comp_high = max(comp_high, highs[i])
                comp_low = min(comp_low, lows[i])
            else:
                if comp_bars >= p['compression_min_bars'] and comp_low < float('inf'):
                    # Bullish breakout
                    if closes[i] > comp_high and closes[i] > ema[i]:
                        sl = closes[i] - atr_s[i] * p['atr_sl_mult']
                        tp = closes[i] + atr_s[i] * p['atr_tp_mult']
                        tp2 = closes[i] + atr_s[i] * p['atr_tp_mult'] * 1.5
                        rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                        if rr >= p['risk_reward_min']:
                            signals.append(self._sig(symbol, "BUY", closes[i], sl, tp, df, i,
                                                     tp2=tp2, rr=rr, metadata={"comp_bars": comp_bars, "vol_ratio": vol_ratio}))
                            daily_trades += 1

                    # Bearish breakout
                    elif closes[i] < comp_low and closes[i] < ema[i]:
                        sl = closes[i] + atr_s[i] * p['atr_sl_mult']
                        tp = closes[i] - atr_s[i] * p['atr_tp_mult']
                        tp2 = closes[i] - atr_s[i] * p['atr_tp_mult'] * 1.5
                        rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                        if rr >= p['risk_reward_min']:
                            signals.append(self._sig(symbol, "SELL", closes[i], sl, tp, df, i,
                                                     tp2=tp2, rr=rr, metadata={"comp_bars": comp_bars, "vol_ratio": vol_ratio}))
                            daily_trades += 1

                comp_bars = 0
                comp_high, comp_low = 0.0, float('inf')

        return signals


class MRCEAggressive(Strategy):
    """MM-003: Mean Reversion Compression Expansion - Fades VCE breakouts."""
    STRATEGY_ID = "MM-003"
    STRATEGY_NAME = "MRCE-A Mean Reversion Compression Expansion"
    STRATEGY_TYPE = "mean_reversion"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"atr_short": 7, "atr_long": 50, "compression_ratio": 0.75,
                "atr_sl_mult": 1.0, "fakeout_min_pct": 0.2,
                "ema_trend": 100, "compression_min_bars": 3,
                "risk_reward_min": 0.8, "session_filter": False, "max_daily_trades": 5}

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {"atr_short": (5, 14, 1), "compression_ratio": (0.5, 0.9, 0.05),
                "atr_sl_mult": (0.5, 1.5, 0.1), "fakeout_min_pct": (0.1, 0.5, 0.1)}

    def generate_signals(self, df, symbol=""):
        p = self.params
        closes, highs, lows = df['close'].values, df['high'].values, df['low'].values
        atr_s = self.atr(highs, lows, closes, p['atr_short'])
        atr_l = self.atr(highs, lows, closes, p['atr_long'])
        ema = self.ema(closes, p['ema_trend'])

        signals = []
        comp_bars = 0
        comp_high, comp_low = 0.0, float('inf')
        breakout_dir = None
        breakout_bar = 0
        breakout_level = 0.0
        min_start = max(p['atr_long'], p['ema_trend']) + 10

        for i in range(min_start, len(df) - 1):
            if pd.isna(atr_l[i]) or pd.isna(atr_s[i]):
                continue

            vol_ratio = atr_s[i] / atr_l[i] if atr_l[i] > 0 else 1.0
            compressed = vol_ratio < p['compression_ratio']

            if compressed:
                comp_bars += 1
                comp_high = max(comp_high, highs[i])
                comp_low = min(comp_low, lows[i])
                breakout_dir = None
            else:
                # Detect breakout from compression
                if comp_bars >= p['compression_min_bars'] and comp_low < float('inf'):
                    if closes[i] > comp_high:
                        breakout_dir = "UP"
                        breakout_bar = i
                        breakout_level = comp_high
                    elif closes[i] < comp_low:
                        breakout_dir = "DOWN"
                        breakout_bar = i
                        breakout_level = comp_low

                # Check for fakeout reversal
                if breakout_dir is not None and i > breakout_bar + 1:
                    comp_range = comp_high - comp_low

                    if breakout_dir == "UP" and closes[i] < comp_high:
                        reversal = comp_high - closes[i]
                        if reversal >= comp_range * p['fakeout_min_pct']:
                            sl = comp_high + atr_s[i] * p['atr_sl_mult'] * 0.3
                            tp = comp_low + comp_range * 0.2
                            rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                            if rr >= p['risk_reward_min']:
                                signals.append(self._sig(symbol, "SELL", closes[i], sl, tp, df, i,
                                                         rr=rr, metadata={"type": "up_fakeout"}))
                            breakout_dir = None

                    elif breakout_dir == "DOWN" and closes[i] > comp_low:
                        reversal = closes[i] - comp_low
                        if reversal >= comp_range * p['fakeout_min_pct']:
                            sl = comp_low - atr_s[i] * p['atr_sl_mult'] * 0.3
                            tp = comp_high - comp_range * 0.2
                            rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                            if rr >= p['risk_reward_min']:
                                signals.append(self._sig(symbol, "BUY", closes[i], sl, tp, df, i,
                                                         rr=rr, metadata={"type": "down_fakeout"}))
                            breakout_dir = None

                if not compressed:
                    comp_bars = 0
                    comp_high, comp_low = 0.0, float('inf')

        return signals


class MomentumBreakout(Strategy):
    """MM-004: Donchian channel breakout with RSI momentum + volume confirmation."""
    STRATEGY_ID = "MM-004"
    STRATEGY_NAME = "Momentum Breakout"
    STRATEGY_TYPE = "breakout"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"channel_period": 20, "atr_period": 14, "atr_sl_mult": 1.5,
                "atr_tp_mult": 3.0, "rsi_period": 14, "rsi_buy_min": 50,
                "rsi_sell_max": 50, "volume_ma_period": 20, "volume_mult": 1.0,
                "risk_reward_min": 1.2, "session_filter": False, "max_daily_trades": 5}

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {"channel_period": (10, 40, 5), "atr_sl_mult": (1.0, 2.5, 0.1),
                "atr_tp_mult": (2.0, 5.0, 0.5), "volume_mult": (0.5, 1.5, 0.25)}

    def generate_signals(self, df, symbol=""):
        p = self.params
        closes, highs, lows = df['close'].values, df['high'].values, df['low'].values
        vols = df['volume'].values if 'volume' in df.columns else np.ones(len(df))
        atr_v = self.atr(highs, lows, closes, p['atr_period'])
        rsi_v = self.rsi(closes, p['rsi_period'])
        vol_ma = self.sma(vols.astype(float), p['volume_ma_period'])

        signals = []
        min_start = max(p['channel_period'], p['atr_period'], p['rsi_period']) + 10

        for i in range(min_start, len(df) - 1):
            if pd.isna(atr_v[i]) or pd.isna(rsi_v[i]):
                continue

            ch_high = np.max(highs[i - p['channel_period'] + 1:i])
            ch_low = np.min(lows[i - p['channel_period'] + 1:i])
            vol_ok = pd.isna(vol_ma[i]) or vols[i] > vol_ma[i] * p['volume_mult'] or vol_ma[i] == 0

            # Bullish breakout
            if closes[i] > ch_high and rsi_v[i] > p['rsi_buy_min'] and vol_ok:
                sl = closes[i] - atr_v[i] * p['atr_sl_mult']
                tp = closes[i] + atr_v[i] * p['atr_tp_mult']
                rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(symbol, "BUY", closes[i], sl, tp, df, i,
                                             rr=rr, metadata={"rsi": round(rsi_v[i], 1)}))

            # Bearish breakout
            elif closes[i] < ch_low and rsi_v[i] < p['rsi_sell_max'] and vol_ok:
                sl = closes[i] + atr_v[i] * p['atr_sl_mult']
                tp = closes[i] - atr_v[i] * p['atr_tp_mult']
                rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(symbol, "SELL", closes[i], sl, tp, df, i,
                                             rr=rr, metadata={"rsi": round(rsi_v[i], 1)}))

        return signals


class RSIDivergence(Strategy):
    """MM-005: RSI Divergence Reversal."""
    STRATEGY_ID = "MM-005"
    STRATEGY_NAME = "RSI Divergence Reversal"
    STRATEGY_TYPE = "reversal"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"rsi_period": 14, "divergence_lookback": 30, "rsi_ob": 70,
                "rsi_os": 30, "atr_period": 14, "atr_sl_mult": 1.5,
                "atr_tp_mult": 2.5, "risk_reward_min": 1.0, "session_filter": False, "max_daily_trades": 3}

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {"rsi_period": (10, 21, 1), "atr_sl_mult": (1.0, 2.5, 0.1),
                "atr_tp_mult": (1.5, 4.0, 0.5), "rsi_ob": (60, 80, 5), "rsi_os": (20, 40, 5)}

    def generate_signals(self, df, symbol=""):
        p = self.params
        closes, highs, lows = df['close'].values, df['high'].values, df['low'].values
        atr_v = self.atr(highs, lows, closes, p['atr_period'])
        rsi_v = self.rsi(closes, p['rsi_period'])
        sh_i, sh_p, sl_i, sl_p = self.find_swing_points(highs, lows, 5)

        signals = []
        min_start = max(p['rsi_period'], p['atr_period'], p['divergence_lookback']) + 10

        for i in range(min_start, len(df) - 1):
            if pd.isna(atr_v[i]) or pd.isna(rsi_v[i]):
                continue

            lb = p['divergence_lookback']
            recent_sh = sh_i[(sh_i >= i - lb) & (sh_i < i)]
            recent_sl = sl_i[(sl_i >= i - lb) & (sl_i < i)]

            # Bearish divergence
            if len(recent_sh) >= 2:
                p1, p2 = recent_sh[-2], recent_sh[-1]
                if highs[p2] > highs[p1] and rsi_v[p2] < rsi_v[p1] and rsi_v[p2] > p['rsi_ob']:
                    sl = highs[p2] + atr_v[i] * p['atr_sl_mult'] * 0.3
                    tp = closes[i] - atr_v[i] * p['atr_tp_mult']
                    rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(self._sig(symbol, "SELL", closes[i], sl, tp, df, i,
                                                 rr=rr, metadata={"type": "bearish_div"}))

            # Bullish divergence
            if len(recent_sl) >= 2:
                p1, p2 = recent_sl[-2], recent_sl[-1]
                if lows[p2] < lows[p1] and rsi_v[p2] > rsi_v[p1] and rsi_v[p2] < p['rsi_os']:
                    sl = lows[p2] - atr_v[i] * p['atr_sl_mult'] * 0.3
                    tp = closes[i] + atr_v[i] * p['atr_tp_mult']
                    rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(self._sig(symbol, "BUY", closes[i], sl, tp, df, i,
                                                 rr=rr, metadata={"type": "bullish_div"}))

        return signals


class BollingerBounce(Strategy):
    """MM-006: Bollinger Band mean reversion."""
    STRATEGY_ID = "MM-006"
    STRATEGY_NAME = "Bollinger Bounce Mean Reversion"
    STRATEGY_TYPE = "mean_reversion"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"bb_period": 20, "bb_std": 2.0, "atr_period": 14, "atr_sl_mult": 1.0,
                "tp_at_middle": True, "rsi_period": 14, "rsi_os": 30, "rsi_ob": 70,
                "risk_reward_min": 0.8, "session_filter": False, "max_daily_trades": 5}

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {"bb_period": (15, 30, 5), "bb_std": (1.5, 3.0, 0.25),
                "atr_sl_mult": (0.5, 2.0, 0.1)}

    def generate_signals(self, df, symbol=""):
        p = self.params
        closes, highs, lows = df['close'].values, df['high'].values, df['low'].values
        upper, middle, lower = self.bollinger_bands(closes, p['bb_period'], p['bb_std'])
        atr_v = self.atr(highs, lows, closes, p['atr_period'])
        rsi_v = self.rsi(closes, p['rsi_period'])

        signals = []
        min_start = max(p['bb_period'], p['atr_period'], p['rsi_period']) + 10

        for i in range(min_start, len(df) - 1):
            if pd.isna(upper[i]) or pd.isna(lower[i]) or pd.isna(atr_v[i]):
                continue

            # Buy: touch lower band + RSI oversold
            if lows[i] <= lower[i] and rsi_v[i] < p['rsi_os']:
                sl = lows[i] - atr_v[i] * p['atr_sl_mult']
                tp = middle[i] if p['tp_at_middle'] else closes[i] + atr_v[i] * 2.0
                rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(symbol, "BUY", closes[i], sl, tp, df, i, rr=rr,
                                             metadata={"type": "lower_bounce"}))

            # Sell: touch upper band + RSI overbought
            elif highs[i] >= upper[i] and rsi_v[i] > p['rsi_ob']:
                sl = highs[i] + atr_v[i] * p['atr_sl_mult']
                tp = middle[i] if p['tp_at_middle'] else closes[i] - atr_v[i] * 2.0
                rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(symbol, "SELL", closes[i], sl, tp, df, i, rr=rr,
                                             metadata={"type": "upper_bounce"}))

        return signals


class ATRBreakout(Strategy):
    """MM-007: ATR expansion breakout."""
    STRATEGY_ID = "MM-007"
    STRATEGY_NAME = "ATR Breakout Expansion"
    STRATEGY_TYPE = "breakout"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"atr_short": 7, "atr_long": 50, "expansion_ratio": 1.3,
                "atr_sl_mult": 1.3, "atr_tp_mult": 3.0, "lookback_period": 5,
                "ema_trend": 50, "risk_reward_min": 1.2, "session_filter": False, "max_daily_trades": 5}

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {"expansion_ratio": (1.1, 2.0, 0.1), "atr_sl_mult": (1.0, 2.0, 0.1),
                "atr_tp_mult": (2.0, 5.0, 0.5)}

    def generate_signals(self, df, symbol=""):
        p = self.params
        closes, highs, lows = df['close'].values, df['high'].values, df['low'].values
        atr_s = self.atr(highs, lows, closes, p['atr_short'])
        atr_l = self.atr(highs, lows, closes, p['atr_long'])
        ema = self.ema(closes, p['ema_trend'])

        signals = []
        min_start = max(p['atr_long'], p['ema_trend']) + 10

        for i in range(min_start, len(df) - 1):
            if pd.isna(atr_s[i]) or pd.isna(atr_l[i]):
                continue

            if atr_l[i] > 0 and atr_s[i] > atr_l[i] * p['expansion_ratio']:
                lb = p['lookback_period']
                rh = np.max(highs[i-lb:i])
                rl = np.min(lows[i-lb:i])

                if closes[i] > rh and closes[i] > ema[i]:
                    sl = closes[i] - atr_s[i] * p['atr_sl_mult']
                    tp = closes[i] + atr_s[i] * p['atr_tp_mult']
                    rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(self._sig(symbol, "BUY", closes[i], sl, tp, df, i,
                                                 rr=rr, metadata={"expansion": round(atr_s[i]/atr_l[i], 2)}))

                elif closes[i] < rl and closes[i] < ema[i]:
                    sl = closes[i] + atr_s[i] * p['atr_sl_mult']
                    tp = closes[i] - atr_s[i] * p['atr_tp_mult']
                    rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(self._sig(symbol, "SELL", closes[i], sl, tp, df, i,
                                                 rr=rr, metadata={"expansion": round(atr_s[i]/atr_l[i], 2)}))

        return signals


class EMACrossover(Strategy):
    """MM-008: EMA fast/slow crossover trend following."""
    STRATEGY_ID = "MM-008"
    STRATEGY_NAME = "EMA Crossover Trend"
    STRATEGY_TYPE = "trend"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"fast_ema": 9, "slow_ema": 21, "trend_ema": 100,
                "atr_period": 14, "atr_sl_mult": 1.5, "atr_tp_mult": 3.0,
                "risk_reward_min": 1.2, "session_filter": False, "max_daily_trades": 5}

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {"fast_ema": (5, 20, 1), "slow_ema": (15, 50, 5),
                "atr_sl_mult": (1.0, 2.5, 0.1), "atr_tp_mult": (2.0, 5.0, 0.5)}

    def generate_signals(self, df, symbol=""):
        p = self.params
        closes, highs, lows = df['close'].values, df['high'].values, df['low'].values
        fast = self.ema(closes, p['fast_ema'])
        slow = self.ema(closes, p['slow_ema'])
        trend = self.ema(closes, p['trend_ema'])
        atr_v = self.atr(highs, lows, closes, p['atr_period'])

        signals = []
        min_start = max(p['slow_ema'], p['trend_ema'], p['atr_period']) + 10

        for i in range(min_start, len(df) - 1):
            if pd.isna(atr_v[i]):
                continue

            # Golden cross + above trend
            if fast[i] > slow[i] and fast[i-1] <= slow[i-1] and closes[i] > trend[i]:
                sl = closes[i] - atr_v[i] * p['atr_sl_mult']
                tp = closes[i] + atr_v[i] * p['atr_tp_mult']
                rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(symbol, "BUY", closes[i], sl, tp, df, i, rr=rr))

            # Death cross + below trend
            elif fast[i] < slow[i] and fast[i-1] >= slow[i-1] and closes[i] < trend[i]:
                sl = closes[i] + atr_v[i] * p['atr_sl_mult']
                tp = closes[i] - atr_v[i] * p['atr_tp_mult']
                rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(symbol, "SELL", closes[i], sl, tp, df, i, rr=rr))

        return signals


class LiquiditySweepReversal(Strategy):
    """MM-009: Fades liquidity sweeps (smart money concept)."""
    STRATEGY_ID = "MM-009"
    STRATEGY_NAME = "Liquidity Sweep Quick Reversal"
    STRATEGY_TYPE = "reversal"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"swing_lookback": 5, "sweep_pct": 0.0003, "reversal_bars": 2,
                "atr_period": 14, "atr_sl_mult": 1.2, "atr_tp_mult": 2.0,
                "risk_reward_min": 0.8, "session_filter": False, "max_daily_trades": 5}

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {"swing_lookback": (3, 10, 1), "atr_sl_mult": (0.8, 2.0, 0.1),
                "atr_tp_mult": (1.5, 4.0, 0.5)}

    def generate_signals(self, df, symbol=""):
        p = self.params
        closes, highs, lows = df['close'].values, df['high'].values, df['low'].values
        atr_v = self.atr(highs, lows, closes, p['atr_period'])
        sh_i, sh_p, sl_i, sl_p = self.find_swing_points(highs, lows, p['swing_lookback'])

        signals = []
        pending = None
        min_start = max(p['swing_lookback'] * 2, p['atr_period']) + 10

        for i in range(min_start, len(df) - 1):
            if pd.isna(atr_v[i]):
                continue

            # Detect sweeps
            recent_sh = sh_i[sh_i < i]
            recent_sl = sl_i[sl_i < i]

            if len(recent_sh) > 0 and highs[i] > sh_p[len(recent_sh)-1] and closes[i] < sh_p[len(recent_sh)-1]:
                pending = ("SELL", sh_p[len(recent_sh)-1], i)

            if len(recent_sl) > 0 and lows[i] < sl_p[len(recent_sl)-1] and closes[i] > sl_p[len(recent_sl)-1]:
                pending = ("BUY", sl_p[len(recent_sl)-1], i)

            # Confirm reversal
            if pending is not None:
                d, level, bar = pending
                if i - bar >= p['reversal_bars']:
                    if d == "BUY" and closes[i] > closes[bar]:
                        sl = level - atr_v[i] * p['atr_sl_mult']
                        tp = closes[i] + atr_v[i] * p['atr_tp_mult']
                        rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                        if rr >= p['risk_reward_min']:
                            signals.append(self._sig(symbol, "BUY", closes[i], sl, tp, df, i, rr=rr))
                        pending = None
                    elif d == "SELL" and closes[i] < closes[bar]:
                        sl = level + atr_v[i] * p['atr_sl_mult']
                        tp = closes[i] - atr_v[i] * p['atr_tp_mult']
                        rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                        if rr >= p['risk_reward_min']:
                            signals.append(self._sig(symbol, "SELL", closes[i], sl, tp, df, i, rr=rr))
                        pending = None

                if pending and i - bar > 10:
                    pending = None

        return signals


class VolumeProfileMomentum(Strategy):
    """MM-010: Volume spike + price breakout momentum."""
    STRATEGY_ID = "MM-010"
    STRATEGY_NAME = "Volume Profile Momentum"
    STRATEGY_TYPE = "hybrid"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"volume_ma_period": 20, "volume_spike_mult": 1.5,
                "atr_period": 14, "atr_sl_mult": 1.5, "atr_tp_mult": 3.0,
                "price_lookback": 10, "risk_reward_min": 1.2, "session_filter": False, "max_daily_trades": 5}

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {"volume_spike_mult": (1.0, 3.0, 0.25), "atr_sl_mult": (1.0, 2.5, 0.1)}

    def generate_signals(self, df, symbol=""):
        p = self.params
        closes, highs, lows = df['close'].values, df['high'].values, df['low'].values
        vols = df['volume'].values.astype(float) if 'volume' in df.columns else np.ones(len(df))
        atr_v = self.atr(highs, lows, closes, p['atr_period'])
        vol_ma = self.sma(vols, p['volume_ma_period'])

        signals = []
        min_start = max(p['volume_ma_period'], p['atr_period'], p['price_lookback']) + 10

        for i in range(min_start, len(df) - 1):
            if pd.isna(atr_v[i]):
                continue

            vol_ok = pd.isna(vol_ma[i]) or vols[i] > vol_ma[i] * p['volume_spike_mult'] or vol_ma[i] == 0
            if not vol_ok:
                continue

            lb = p['price_lookback']
            if closes[i] > np.max(closes[i-lb:i]):
                sl = closes[i] - atr_v[i] * p['atr_sl_mult']
                tp = closes[i] + atr_v[i] * p['atr_tp_mult']
                rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(symbol, "BUY", closes[i], sl, tp, df, i, rr=rr))

            elif closes[i] < np.min(closes[i-lb:i]):
                sl = closes[i] + atr_v[i] * p['atr_sl_mult']
                tp = closes[i] - atr_v[i] * p['atr_tp_mult']
                rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(symbol, "SELL", closes[i], sl, tp, df, i, rr=rr))

        return signals


class SessionMomentum(Strategy):
    """MM-011: London/NY session directional momentum."""
    STRATEGY_ID = "MM-011"
    STRATEGY_NAME = "Session Momentum Bias"
    STRATEGY_TYPE = "trend"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"london_open": 7, "ny_open": 12, "bias_hours": 2,
                "atr_period": 14, "atr_sl_mult": 1.0, "atr_tp_mult": 2.0,
                "min_move_pct": 0.05, "risk_reward_min": 1.0,
                "session_filter": False, "max_daily_trades": 3}

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {"atr_sl_mult": (0.5, 2.0, 0.1), "atr_tp_mult": (1.5, 4.0, 0.5)}

    def generate_signals(self, df, symbol=""):
        p = self.params
        closes, highs, lows = df['close'].values, df['high'].values, df['low'].values
        atr_v = self.atr(highs, lows, closes, p['atr_period'])

        signals = []
        session_bias = None
        bias_bar = -1
        min_start = p['atr_period'] + 10

        for i in range(min_start, len(df) - 1):
            if pd.isna(atr_v[i]):
                continue
            if not hasattr(df.index, 'hour'):
                continue

            h = df.index[i].hour
            wd = df.index[i].weekday
            if wd >= 5:
                session_bias = None
                continue

            # Set bias at London open + bias_hours
            if h == p['london_open'] + p['bias_hours'] and session_bias is None:
                for j in range(i - 20, i):
                    if df.index[j].hour == p['london_open']:
                        move = closes[i] - closes[j]
                        move_pct = abs(move) / closes[j] * 100
                        if move_pct >= p['min_move_pct']:
                            session_bias = "BUY" if move > 0 else "SELL"
                            bias_bar = i
                        break

            # Reset bias at end of day
            if h >= 21:
                session_bias = None

            # Trade in session direction
            if session_bias and i > bias_bar and (p['london_open'] <= h < 17):
                if session_bias == "BUY" and closes[i] > closes[i-1]:
                    sl = closes[i] - atr_v[i] * p['atr_sl_mult']
                    tp = closes[i] + atr_v[i] * p['atr_tp_mult']
                    rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(self._sig(symbol, "BUY", closes[i], sl, tp, df, i, rr=rr))

                elif session_bias == "SELL" and closes[i] < closes[i-1]:
                    sl = closes[i] + atr_v[i] * p['atr_sl_mult']
                    tp = closes[i] - atr_v[i] * p['atr_tp_mult']
                    rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(self._sig(symbol, "SELL", closes[i], sl, tp, df, i, rr=rr))

        return signals


class GapFill(Strategy):
    """MM-012: Weekend gap fill trade."""
    STRATEGY_ID = "MM-012"
    STRATEGY_NAME = "Gap Fill Weekend"
    STRATEGY_TYPE = "mean_reversion"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"min_gap_pct": 0.1, "atr_period": 14, "atr_sl_mult": 1.5,
                "risk_reward_min": 0.8, "session_filter": False, "max_daily_trades": 1}

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {"min_gap_pct": (0.05, 0.5, 0.05), "atr_sl_mult": (1.0, 2.5, 0.1)}

    def generate_signals(self, df, symbol=""):
        p = self.params
        closes, highs, lows = df['close'].values, df['high'].values, df['low'].values
        atr_v = self.atr(highs, lows, closes, p['atr_period'])
        signals = []
        min_start = p['atr_period'] + 10
        gap_taken = False
        last_date = None

        for i in range(min_start, len(df) - 1):
            if pd.isna(atr_v[i]):
                continue
            cur_date = df.index[i].date() if hasattr(df.index[i], 'date') else None
            if cur_date != last_date:
                last_date = cur_date
                gap_taken = False
            if not hasattr(df.index, 'weekday') or df.index[i].weekday() != 0 or gap_taken:
                continue

            friday_close = None
            for j in range(i - 10, i):
                if df.index[j].weekday() == 4:
                    friday_close = closes[j]

            if friday_close is None:
                continue
            gap = closes[i] - friday_close
            gap_pct = abs(gap) / friday_close * 100
            if gap_pct < p['min_gap_pct']:
                continue

            if gap > 0:
                sl = closes[i] + atr_v[i] * p['atr_sl_mult']
                tp = friday_close
                rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(symbol, "SELL", closes[i], sl, tp, df, i, rr=rr,
                                             metadata={"gap_pct": round(gap_pct, 2)}))
                    gap_taken = True
            elif gap < 0:
                sl = closes[i] - atr_v[i] * p['atr_sl_mult']
                tp = friday_close
                rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(symbol, "BUY", closes[i], sl, tp, df, i, rr=rr,
                                             metadata={"gap_pct": round(gap_pct, 2)}))
                    gap_taken = True

        return signals


class SupportResistanceBounce(Strategy):
    """MM-013: S/R level bounce trading."""
    STRATEGY_ID = "MM-013"
    STRATEGY_NAME = "Support/Resistance Bounce"
    STRATEGY_TYPE = "mean_reversion"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"swing_lookback": 7, "proximity_atr_mult": 0.5,
                "atr_period": 14, "atr_sl_mult": 1.0, "atr_tp_mult": 2.0,
                "risk_reward_min": 1.0, "session_filter": False, "max_daily_trades": 5}

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {"atr_sl_mult": (0.5, 2.0, 0.1), "atr_tp_mult": (1.5, 4.0, 0.5)}

    def generate_signals(self, df, symbol=""):
        p = self.params
        closes, highs, lows = df['close'].values, df['high'].values, df['low'].values
        atr_v = self.atr(highs, lows, closes, p['atr_period'])
        sh_i, sh_p, sl_i, sl_p = self.find_swing_points(highs, lows, p['swing_lookback'])

        signals = []
        min_start = max(p['swing_lookback'] * 2, p['atr_period']) + 10
        daily = 0
        last_d = None

        for i in range(min_start, len(df) - 1):
            if pd.isna(atr_v[i]):
                continue

            # Daily limit
            d = df.index[i].date() if hasattr(df.index[i], 'date') else None
            if d != last_d:
                daily = 0
                last_d = d
            if daily >= p['max_daily_trades']:
                continue

            prox = atr_v[i] * p['proximity_atr_mult']
            recent_sh = sh_i[sh_i < i]
            recent_sl = sl_i[sl_i < i]

            # Support bounce
            if len(recent_sl) > 0:
                level = sl_p[len(recent_sl)-1]
                if abs(closes[i] - level) <= prox and lows[i] <= level and closes[i] > level:
                    sl = level - atr_v[i] * p['atr_sl_mult']
                    tp = closes[i] + atr_v[i] * p['atr_tp_mult']
                    rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(self._sig(symbol, "BUY", closes[i], sl, tp, df, i, rr=rr))
                        daily += 1

            # Resistance rejection
            if len(recent_sh) > 0:
                level = sh_p[len(recent_sh)-1]
                if abs(closes[i] - level) <= prox and highs[i] >= level and closes[i] < level:
                    sl = level + atr_v[i] * p['atr_sl_mult']
                    tp = closes[i] - atr_v[i] * p['atr_tp_mult']
                    rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(self._sig(symbol, "SELL", closes[i], sl, tp, df, i, rr=rr))
                        daily += 1

        return signals


class FibonacciRetracement(Strategy):
    """MM-014: Fibonacci pullback entry."""
    STRATEGY_ID = "MM-014"
    STRATEGY_NAME = "Fibonacci Retracement Entry"
    STRATEGY_TYPE = "trend"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"swing_lookback": 10, "fib_level": 0.618, "fib_zone_atr": 0.3,
                "atr_period": 14, "atr_sl_mult": 1.0, "atr_tp_mult": 2.5,
                "min_swing_pct": 0.5, "risk_reward_min": 1.0,
                "session_filter": False, "max_daily_trades": 5}

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {"fib_level": (0.382, 0.786, 0.118), "atr_sl_mult": (0.8, 2.0, 0.1)}

    def generate_signals(self, df, symbol=""):
        p = self.params
        closes, highs, lows = df['close'].values, df['high'].values, df['low'].values
        atr_v = self.atr(highs, lows, closes, p['atr_period'])
        sh_i, sh_p, sl_i, sl_p = self.find_swing_points(highs, lows, p['swing_lookback'])

        signals = []
        min_start = max(p['swing_lookback'] * 2, p['atr_period']) + 10

        for i in range(min_start, len(df) - 1):
            if pd.isna(atr_v[i]):
                continue

            recent_sh = sh_i[sh_i < i]
            recent_sl = sl_i[sl_i < i]
            if len(recent_sh) < 1 or len(recent_sl) < 1:
                continue

            zone = atr_v[i] * p['fib_zone_atr']

            # Bullish: swing low → swing high, retrace to fib
            s_high = sh_p[len(recent_sh)-1]
            s_low = sl_p[len(recent_sl)-1]
            swing = s_high - s_low
            if abs(swing) / s_low * 100 >= p['min_swing_pct']:
                fib_price = s_high - swing * p['fib_level']
                if abs(closes[i] - fib_price) <= zone:
                    sl = s_low - atr_v[i] * p['atr_sl_mult'] * 0.5
                    tp = s_high + swing * 0.272
                    rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(self._sig(symbol, "BUY", closes[i], sl, tp, df, i, rr=rr))

                # Bearish fib
                fib_price2 = s_low + swing * p['fib_level']
                if abs(closes[i] - fib_price2) <= zone:
                    sl = s_high + atr_v[i] * p['atr_sl_mult'] * 0.5
                    tp = s_low - swing * 0.272
                    rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                    if rr >= p['risk_reward_min']:
                        signals.append(self._sig(symbol, "SELL", closes[i], sl, tp, df, i, rr=rr))

        return signals


class MACDHistogram(Strategy):
    """MM-015: MACD histogram momentum shift."""
    STRATEGY_ID = "MM-015"
    STRATEGY_NAME = "MACD Histogram Shift"
    STRATEGY_TYPE = "momentum"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"fast_period": 12, "slow_period": 26, "signal_period": 9,
                "atr_period": 14, "atr_sl_mult": 1.5, "atr_tp_mult": 3.0,
                "risk_reward_min": 1.0, "session_filter": False, "max_daily_trades": 5}

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {"atr_sl_mult": (1.0, 2.5, 0.1), "atr_tp_mult": (2.0, 5.0, 0.5)}

    def generate_signals(self, df, symbol=""):
        p = self.params
        closes, highs, lows = df['close'].values, df['high'].values, df['low'].values
        atr_v = self.atr(highs, lows, closes, p['atr_period'])
        _, _, hist = self.macd(closes, p['fast_period'], p['slow_period'], p['signal_period'])

        signals = []
        min_start = max(p['slow_period'] + p['signal_period'], p['atr_period']) + 10

        for i in range(min_start, len(df) - 1):
            if pd.isna(atr_v[i]) or i < 3:
                continue

            # Bullish: histogram crosses zero upward
            if hist[i] > 0 and hist[i-1] <= 0:
                sl = closes[i] - atr_v[i] * p['atr_sl_mult']
                tp = closes[i] + atr_v[i] * p['atr_tp_mult']
                rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(symbol, "BUY", closes[i], sl, tp, df, i, rr=rr))

            # Bearish: histogram crosses zero downward
            elif hist[i] < 0 and hist[i-1] >= 0:
                sl = closes[i] + atr_v[i] * p['atr_sl_mult']
                tp = closes[i] - atr_v[i] * p['atr_tp_mult']
                rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(symbol, "SELL", closes[i], sl, tp, df, i, rr=rr))

        return signals


class StochasticExtreme(Strategy):
    """MM-016: Stochastic overbought/oversold reversal."""
    STRATEGY_ID = "MM-016"
    STRATEGY_NAME = "Stochastic Extreme Reversal"
    STRATEGY_TYPE = "reversal"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"k_period": 14, "d_period": 3, "ob_level": 80, "os_level": 20,
                "atr_period": 14, "atr_sl_mult": 1.2, "atr_tp_mult": 2.5,
                "risk_reward_min": 1.0, "session_filter": False, "max_daily_trades": 5}

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {"ob_level": (70, 85, 5), "os_level": (15, 30, 5),
                "atr_sl_mult": (0.8, 2.0, 0.1)}

    def generate_signals(self, df, symbol=""):
        p = self.params
        closes, highs, lows = df['close'].values, df['high'].values, df['low'].values
        atr_v = self.atr(highs, lows, closes, p['atr_period'])
        k, d = self.stochastic(highs, lows, closes, p['k_period'], p['d_period'])

        signals = []
        min_start = max(p['k_period'], p['atr_period']) + 10

        for i in range(min_start, len(df) - 1):
            if pd.isna(atr_v[i]):
                continue

            # Bullish: K crosses above D from oversold
            if k[i] > d[i] and k[i-1] <= d[i-1] and k[i] < p['os_level'] + 15:
                sl = closes[i] - atr_v[i] * p['atr_sl_mult']
                tp = closes[i] + atr_v[i] * p['atr_tp_mult']
                rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(symbol, "BUY", closes[i], sl, tp, df, i, rr=rr))

            # Bearish: K crosses below D from overbought
            elif k[i] < d[i] and k[i-1] >= d[i-1] and k[i] > p['ob_level'] - 15:
                sl = closes[i] + atr_v[i] * p['atr_sl_mult']
                tp = closes[i] - atr_v[i] * p['atr_tp_mult']
                rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(symbol, "SELL", closes[i], sl, tp, df, i, rr=rr))

        return signals


class HeikinAshiTrend(Strategy):
    """MM-017: Heikin Ashi smooth trend following."""
    STRATEGY_ID = "MM-017"
    STRATEGY_NAME = "Heikin Ashi Trend Follow"
    STRATEGY_TYPE = "trend"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"consecutive_bars": 3, "atr_period": 14, "atr_sl_mult": 1.5,
                "atr_tp_mult": 3.0, "risk_reward_min": 1.0,
                "session_filter": False, "max_daily_trades": 5}

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {"consecutive_bars": (2, 6, 1), "atr_sl_mult": (1.0, 2.5, 0.1)}

    def generate_signals(self, df, symbol=""):
        p = self.params
        closes, highs, lows = df['close'].values, df['high'].values, df['low'].values
        atr_v = self.atr(highs, lows, closes, p['atr_period'])
        ha = self.heikin_ashi(df)
        ha_c, ha_o = ha['close'].values, ha['open'].values

        signals = []
        min_start = p['atr_period'] + 10
        last_dir = None
        last_bar = -999

        for i in range(min_start, len(df) - 1):
            if pd.isna(atr_v[i]):
                continue

            # Count consecutive same-direction HA candles
            bull_count = sum(1 for j in range(max(0, i-p['consecutive_bars']), i+1) if ha_c[j] > ha_o[j])
            bear_count = sum(1 for j in range(max(0, i-p['consecutive_bars']), i+1) if ha_c[j] < ha_o[j])

            # Only signal once per trend change
            if i - last_bar < 5:
                continue

            if bull_count >= p['consecutive_bars'] and last_dir != "BUY":
                sl = lows[i] - atr_v[i] * p['atr_sl_mult']
                tp = closes[i] + atr_v[i] * p['atr_tp_mult']
                rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(symbol, "BUY", closes[i], sl, tp, df, i, rr=rr))
                    last_dir = "BUY"
                    last_bar = i

            elif bear_count >= p['consecutive_bars'] and last_dir != "SELL":
                sl = highs[i] + atr_v[i] * p['atr_sl_mult']
                tp = closes[i] - atr_v[i] * p['atr_tp_mult']
                rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(symbol, "SELL", closes[i], sl, tp, df, i, rr=rr))
                    last_dir = "SELL"
                    last_bar = i

        return signals


class IchimokuCloud(Strategy):
    """MM-018: Ichimoku Cloud TK cross and cloud breakout."""
    STRATEGY_ID = "MM-018"
    STRATEGY_NAME = "Ichimoku Cloud System"
    STRATEGY_TYPE = "hybrid"

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {"tenkan_period": 9, "kijun_period": 26, "senkou_b_period": 52,
                "atr_period": 14, "atr_sl_mult": 1.5, "atr_tp_mult": 3.0,
                "risk_reward_min": 1.0, "session_filter": False, "max_daily_trades": 5}

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {"tenkan_period": (7, 14, 1), "kijun_period": (20, 34, 2),
                "atr_sl_mult": (1.0, 2.5, 0.1)}

    def _donchian_mid(self, highs, lows, period):
        n = len(highs)
        r = np.full(n, np.nan)
        for i in range(period - 1, n):
            r[i] = (np.max(highs[i-period+1:i+1]) + np.min(lows[i-period+1:i+1])) / 2
        return r

    def generate_signals(self, df, symbol=""):
        p = self.params
        closes, highs, lows = df['close'].values, df['high'].values, df['low'].values
        atr_v = self.atr(highs, lows, closes, p['atr_period'])
        tenkan = self._donchian_mid(highs, lows, p['tenkan_period'])
        kijun = self._donchian_mid(highs, lows, p['kijun_period'])
        senkou_a = np.where(~pd.isna(tenkan) & ~pd.isna(kijun), (tenkan + kijun) / 2, np.nan)
        senkou_b = self._donchian_mid(highs, lows, p['senkou_b_period'])

        signals = []
        min_start = max(p['senkou_b_period'], p['atr_period']) + 10

        for i in range(min_start, len(df) - 1):
            if pd.isna(atr_v[i]) or pd.isna(tenkan[i]) or pd.isna(kijun[i]):
                continue

            cloud_top = max(senkou_a[i] or 0, senkou_b[i] or 0)
            cloud_bot = min(senkou_a[i] or 0, senkou_b[i] or 0)

            # TK Cross bullish + above cloud
            if tenkan[i] > kijun[i] and tenkan[i-1] <= kijun[i-1] and closes[i] > cloud_top:
                sl = closes[i] - atr_v[i] * p['atr_sl_mult']
                tp = closes[i] + atr_v[i] * p['atr_tp_mult']
                rr = (tp - closes[i]) / (closes[i] - sl) if (closes[i] - sl) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(symbol, "BUY", closes[i], sl, tp, df, i, rr=rr))

            # TK Cross bearish + below cloud
            elif tenkan[i] < kijun[i] and tenkan[i-1] >= kijun[i-1] and closes[i] < cloud_bot:
                sl = closes[i] + atr_v[i] * p['atr_sl_mult']
                tp = closes[i] - atr_v[i] * p['atr_tp_mult']
                rr = (closes[i] - tp) / (sl - closes[i]) if (sl - closes[i]) > 0 else 0
                if rr >= p['risk_reward_min']:
                    signals.append(self._sig(symbol, "SELL", closes[i], sl, tp, df, i, rr=rr))

        return signals
