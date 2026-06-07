#!/usr/bin/env python3
"""
Institutional Adversarial Validation Backtest — MarketMate Signal Engine
========================================================================
OPTIMIZED VERSION: Pre-computes swing levels, vectorized operations.

Philosophy: "Try to KILL Strategy #1. If it survives, confidence rises."
"""

import warnings
warnings.filterwarnings("ignore")

import os
import sys
import json
import random
import pickle
import traceback
from datetime import datetime, timezone, timedelta, time
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict

import numpy as np
import pandas as pd
from scipy import stats

RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

OUTPUT_DIR = "/home/z/my-project/download"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── Instrument Universe ──────────────────────────────────────────────────────
INSTRUMENTS = {
    "forex": [
        "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X",
        "NZDUSD=X", "USDCAD=X", "EURJPY=X", "GBPJPY=X", "EURGBP=X"
    ],
    "metals": ["GC=F", "SI=F"],
    "crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"],
    "indices": ["^GSPC", "^NDX", "^DJI", "^GDAXI"],
}

DISPLAY_NAMES = {
    "EURUSD=X": "EURUSD", "GBPUSD=X": "GBPUSD", "USDJPY=X": "USDJPY",
    "USDCHF=X": "USDCHF", "AUDUSD=X": "AUDUSD", "NZDUSD=X": "NZDUSD",
    "USDCAD=X": "USDCAD", "EURJPY=X": "EURJPY", "GBPJPY=X": "GBPJPY",
    "EURGBP=X": "EURGBP",
    "GC=F": "XAUUSD", "SI=F": "XAGUSD",
    "BTC-USD": "BTCUSD", "ETH-USD": "ETHUSD", "SOL-USD": "SOLUSD", "BNB-USD": "BNBUSD",
    "^GSPC": "US500", "^NDX": "NAS100", "^DJI": "US30", "^GDAXI": "GER40",
}

G7_INSTRUMENTS = {"EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X",
                  "GC=F", "GBPJPY=X", "EURJPY=X"}

# ─── Strategy Parameters ──────────────────────────────────────────────────────
EMA_PERIOD = 200
SWING_LOOKBACK = 7
SWEEP_FRESHNESS_CANDLES = 20
MIN_SWEEP_PCT = 0.0005
MIN_FVG_PCT = 0.001
FVG_FRESHNESS_CANDLES = 10
MIN_OB_DISPLACEMENT_CANDLES = 3
OB_EXPIRY_CANDLES = 20
OB_SEARCH_LOOKBACK = 20
ATR_SL_MULTIPLIER = 1.5
ATR_PERIOD = 14
MIN_RR = 1.5

# ─── Cost Model ───────────────────────────────────────────────────────────────
DEFAULT_SPREAD_PCT = {"forex": 0.00015, "metals": 0.0003, "crypto": 0.0005, "indices": 0.0002}
COMMISSION_PCT = 0.00003
SLIPPAGE_PCT = 0.00005

START_DATE = "2020-01-01"
END_DATE = "2025-12-31"
WALK_FORWARD_WINDOWS = [
    ("2020-01-01", "2022-12-31", "2023-01-01", "2023-12-31"),
    ("2020-01-01", "2023-12-31", "2024-01-01", "2024-12-31"),
    ("2020-01-01", "2024-12-31", "2025-01-01", "2025-12-31"),
]
MONTE_CARLO_RUNS = 100_000


# ─── Data Classes ──────────────────────────────────────────────────────────────
@dataclass
class TradeResult:
    symbol: str
    direction: str
    entry_time: Any
    exit_time: Any
    entry_price: float
    exit_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: Optional[float]
    rr: float
    pnl_pct: float
    result: str
    zone_type: str
    confirm_type: str
    confidence: str
    holding_bars: int
    cost_pct: float

@dataclass
class BacktestResult:
    trades: List[TradeResult] = field(default_factory=list)
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0
    win_rate: float = 0.0
    avg_win_pct: float = 0.0
    avg_loss_pct: float = 0.0
    profit_factor: float = 0.0
    expectancy_pct: float = 0.0
    sharpe_ratio: float = 0.0
    sortino_ratio: float = 0.0
    max_drawdown_pct: float = 0.0
    max_consecutive_losses: int = 0
    avg_rr_achieved: float = 0.0
    calmar_ratio: float = 0.0
    avg_holding_bars: float = 0.0
    tp1_hit_rate: float = 0.0
    tp2_hit_rate: float = 0.0
    tp3_hit_rate: float = 0.0
    sl_hit_rate: float = 0.0
    buy_trades: int = 0
    sell_trades: int = 0
    buy_win_rate: float = 0.0
    sell_win_rate: float = 0.0
    per_instrument: Dict = field(default_factory=dict)
    per_asset_class: Dict = field(default_factory=dict)


# ═══════════════════════════════════════════════════════════════════════════════
# PRE-COMPUTATION ENGINE (Key Optimization)
# ═══════════════════════════════════════════════════════════════════════════════

def precompute_features(df: pd.DataFrame) -> Dict:
    """Pre-compute all indicator features for the entire DataFrame at once."""
    n = len(df)
    features = {}
    
    # EMA
    features['ema'] = df['close'].ewm(span=EMA_PERIOD, adjust=False).mean().values
    
    # ATR (Wilder's)
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    tr = np.maximum(high[1:] - low[1:], np.maximum(np.abs(high[1:] - close[:-1]), np.abs(low[1:] - close[:-1])))
    atr = np.zeros(n)
    if len(tr) >= ATR_PERIOD:
        atr[0] = tr[:ATR_PERIOD].mean()
        for i in range(1, len(tr)):
            atr[i] = (atr[i - 1] * (ATR_PERIOD - 1) + tr[min(i, len(tr)-1)]) / ATR_PERIOD
    features['atr'] = atr
    
    # Pre-compute swing highs/lows for the ENTIRE series
    swing_high_mask = np.zeros(n, dtype=bool)
    swing_low_mask = np.zeros(n, dtype=bool)
    lb = SWING_LOOKBACK
    
    highs = df['high'].values
    lows = df['low'].values
    
    for i in range(lb, n - lb):
        # Swing high: highest in [i-lb, i+lb]
        window_h = highs[i - lb: i + lb + 1]
        if highs[i] == window_h.max():
            swing_high_mask[i] = True
        # Swing low: lowest in [i-lb, i+lb]
        window_l = lows[i - lb: i + lb + 1]
        if lows[i] == window_l.min():
            swing_low_mask[i] = True
    
    features['swing_high_mask'] = swing_high_mask
    features['swing_low_mask'] = swing_low_mask
    features['swing_high_prices'] = highs  # Use mask to index
    features['swing_low_prices'] = lows
    
    return features


def get_market_structure_at(features: Dict, idx: int, lookback_struct: int = 50) -> str:
    """Get market structure at a given index using pre-computed swings."""
    start = max(SWING_LOOKBACK, idx - lookback_struct)
    end = idx + 1
    
    sh_mask = features['swing_high_mask'][start:end]
    sl_mask = features['swing_low_mask'][start:end]
    
    sh_indices = np.where(sh_mask)[0]
    sl_indices = np.where(sl_mask)[0]
    
    if len(sh_indices) < 2 or len(sl_indices) < 2:
        return "neutral"
    
    # Get prices of last 2 swing highs/lows
    last_hh = features['swing_high_prices'][sh_indices[-1] + start]
    prev_hh = features['swing_high_prices'][sh_indices[-2] + start]
    last_hl = features['swing_low_prices'][sl_indices[-1] + start]
    prev_hl = features['swing_low_prices'][sl_indices[-2] + start]
    
    if last_hh > prev_hh and last_hl > prev_hl:
        return "bullish"
    if last_hh < prev_hh and last_hl < prev_hl:
        return "bearish"
    return "neutral"


def get_bias_at(features: Dict, idx: int) -> str:
    """Get HTF bias at a given index."""
    if idx < EMA_PERIOD + 10:
        return "neutral"
    
    price = features['swing_high_prices'][idx]  # close prices stored here
    # Actually use close
    ema_val = features['ema'][idx]
    close_val = features['swing_high_prices'][idx]  # Wrong! Need close
    
    return "neutral"  # placeholder


# ═══════════════════════════════════════════════════════════════════════════════
# OPTIMIZED BACKTEST ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def run_backtest_optimized(
    data: Dict[str, pd.DataFrame],
    instruments: Optional[List[str]] = None,
    skip_g7: bool = False,
    randomize_entries: bool = False,
    shift_entries: int = 0,
    spread_multiplier: float = 1.0,
    skip_g7_instruments: bool = False,
    use_tp3: bool = True,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None,
    max_holding_bars: int = 60,
) -> BacktestResult:
    """
    Optimized backtest with pre-computed features.
    """
    result = BacktestResult()
    all_trades = []
    per_instrument = {}
    per_asset_class = defaultdict(list)

    if instruments is None:
        instruments = []
        for asset_class, syms in INSTRUMENTS.items():
            instruments.extend(syms)

    if skip_g7_instruments:
        instruments = [s for s in instruments if s not in G7_INSTRUMENTS]

    for symbol in instruments:
        if symbol not in data or data[symbol] is None or data[symbol].empty:
            continue

        df = data[symbol].copy()
        display_name = DISPLAY_NAMES.get(symbol, symbol)

        # Determine asset class
        asset_class = "forex"
        for ac, syms in INSTRUMENTS.items():
            if symbol in syms:
                asset_class = ac
                break

        base_spread = DEFAULT_SPREAD_PCT.get(asset_class, 0.0002) * spread_multiplier

        # Filter date range
        if start_date:
            df = df[df['timestamp'] >= pd.Timestamp(start_date)]
        if end_date:
            df = df[df['timestamp'] <= pd.Timestamp(end_date)]

        if len(df) < EMA_PERIOD + 50:
            continue

        # Pre-compute all features
        features = {}
        close = df['close'].values
        high = df['high'].values
        low = df['low'].values
        open_ = df['open'].values
        n = len(df)
        
        # EMA
        features['ema'] = df['close'].ewm(span=EMA_PERIOD, adjust=False).mean().values
        
        # ATR
        tr = np.zeros(n)
        tr[0] = high[0] - low[0]
        for i in range(1, n):
            tr[i] = max(high[i] - low[i], abs(high[i] - close[i-1]), abs(low[i] - close[i-1]))
        atr = np.zeros(n)
        if n > ATR_PERIOD:
            atr[ATR_PERIOD] = np.mean(tr[1:ATR_PERIOD+1])
            for i in range(ATR_PERIOD + 1, n):
                atr[i] = (atr[i-1] * (ATR_PERIOD - 1) + tr[i]) / ATR_PERIOD
        features['atr'] = atr
        
        # Pre-compute swing masks
        lb = SWING_LOOKBACK
        sh_mask = np.zeros(n, dtype=bool)
        sl_mask = np.zeros(n, dtype=bool)
        for i in range(lb, n - lb):
            if high[i] == high[i - lb: i + lb + 1].max():
                sh_mask[i] = True
            if low[i] == low[i - lb: i + lb + 1].min():
                sl_mask[i] = True

        # Cooldown tracking
        last_signal_idx = {}
        COOLDOWN_BARS = 8

        symbol_trades = []

        for i in range(EMA_PERIOD + 30, n - 5):
            # ── G4: HTF Bias ───────────────────────────────────────────────
            price = close[i]
            ema_val = features['ema'][i]
            above_ema = price > ema_val
            below_ema = price < ema_val

            # Market structure from recent swings
            struct_start = max(lb, i - 50)
            sh_in_window = np.where(sh_mask[struct_start:i+1])[0]
            sl_in_window = np.where(sl_mask[struct_start:i+1])[0]
            
            structure = "neutral"
            if len(sh_in_window) >= 2 and len(sl_in_window) >= 2:
                last_hh = high[sh_in_window[-1] + struct_start]
                prev_hh = high[sh_in_window[-2] + struct_start]
                last_hl = low[sl_in_window[-1] + struct_start]
                prev_hl = low[sl_in_window[-2] + struct_start]
                if last_hh > prev_hh and last_hl > prev_hl:
                    structure = "bullish"
                elif last_hh < prev_hh and last_hl < prev_hl:
                    structure = "bearish"

            # Bias resolution (simplified: single TF since we only have daily)
            if above_ema and structure == "bullish":
                bias = "bullish"
            elif below_ema and structure == "bearish":
                bias = "bearish"
            else:
                continue  # G4 fails: neutral

            # ── G5: Liquidity Sweep ────────────────────────────────────────
            structure_end = i - SWEEP_FRESHNESS_CANDLES
            if structure_end < lb * 2:
                continue

            sweep = None
            if bias == "bullish":
                # Look for swing lows that were swept
                sl_before = np.where(sl_mask[lb:structure_end])[0] + lb
                if len(sl_before) > 0:
                    swing_low_levels = sorted([low[idx] for idx in sl_before])
                    # Check recent candles for sweep
                    for j in range(i, max(structure_end, i - SWEEP_FRESHNESS_CANDLES - 1), -1):
                        candles_ago = i - j
                        for level in swing_low_levels[-3:]:  # Check last 3 levels
                            if low[j] < level:
                                sweep_dist = level - low[j]
                                if sweep_dist >= level * MIN_SWEEP_PCT:
                                    close_inside = close[j] > level
                                    sweep = {
                                        'swept_level': level, 'candles_ago': candles_ago,
                                        'close_inside': close_inside,
                                        'strength': 'strong' if close_inside else 'weak',
                                        'sweep_distance': sweep_dist,
                                    }
                                    break
                        if sweep:
                            break

            elif bias == "bearish":
                sh_before = np.where(sh_mask[lb:structure_end])[0] + lb
                if len(sh_before) > 0:
                    swing_high_levels = sorted([high[idx] for idx in sh_before])
                    for j in range(i, max(structure_end, i - SWEEP_FRESHNESS_CANDLES - 1), -1):
                        candles_ago = i - j
                        for level in swing_high_levels[:3]:  # Check first 3 (lowest highs)
                            if high[j] > level:
                                sweep_dist = high[j] - level
                                if sweep_dist >= level * MIN_SWEEP_PCT:
                                    close_inside = close[j] < level
                                    sweep = {
                                        'swept_level': level, 'candles_ago': candles_ago,
                                        'close_inside': close_inside,
                                        'strength': 'strong' if close_inside else 'weak',
                                        'sweep_distance': sweep_dist,
                                    }
                                    break
                        if sweep:
                            break

            if sweep is None:
                continue

            # ── G6: Entry Zone ─────────────────────────────────────────────
            zone = None
            search_start = max(0, i - OB_SEARCH_LOOKBACK)
            
            # Try Order Block first
            for z_i in range(i - 2, search_start, -1):
                candle_open = open_[z_i]
                candle_close = close[z_i]
                candle_high = high[z_i]
                candle_low = low[z_i]
                is_bullish_candle = candle_close > candle_open
                is_bearish_candle = candle_close < candle_open

                if bias == "bullish" and is_bearish_candle:
                    # Check displacement
                    seg_start = z_i + 1
                    seg_end = min(seg_start + MIN_OB_DISPLACEMENT_CANDLES, i + 1)
                    segment = df.iloc[seg_start:seg_end]
                    if len(segment) >= MIN_OB_DISPLACEMENT_CANDLES:
                        bullish_count = (segment['close'] > segment['open']).sum()
                        if bullish_count >= max(2, MIN_OB_DISPLACEMENT_CANDLES - 1):
                            # Check expiry
                            entries_count = 0
                            for ei in range(z_i + 1, i + 1):
                                if low[ei] <= candle_high and high[ei] >= candle_low:
                                    entries_count += 1
                            if entries_count < OB_EXPIRY_CANDLES:
                                zone = {
                                    'zone_type': 'order_block', 'direction': 'bullish',
                                    'zone_high': candle_high, 'zone_low': candle_low,
                                    'zone_mid': (candle_high + candle_low) / 2,
                                }
                                break

                elif bias == "bearish" and is_bullish_candle:
                    seg_start = z_i + 1
                    seg_end = min(seg_start + MIN_OB_DISPLACEMENT_CANDLES, i + 1)
                    segment = df.iloc[seg_start:seg_end]
                    if len(segment) >= MIN_OB_DISPLACEMENT_CANDLES:
                        bearish_count = (segment['close'] < segment['open']).sum()
                        if bearish_count >= max(2, MIN_OB_DISPLACEMENT_CANDLES - 1):
                            entries_count = 0
                            for ei in range(z_i + 1, i + 1):
                                if low[ei] <= candle_high and high[ei] >= candle_low:
                                    entries_count += 1
                            if entries_count < OB_EXPIRY_CANDLES:
                                zone = {
                                    'zone_type': 'order_block', 'direction': 'bearish',
                                    'zone_high': candle_high, 'zone_low': candle_low,
                                    'zone_mid': (candle_high + candle_low) / 2,
                                }
                                break

            # Try FVG if no OB found
            if zone is None:
                search_end_fvg = min(i, n - 2)
                search_start_fvg = max(1, i - FVG_FRESHNESS_CANDLES - 1)
                for fi in range(search_end_fvg - 1, search_start_fvg, -1):
                    if fi - 1 < 0 or fi + 1 >= n:
                        continue
                    c1_high = high[fi - 1]
                    c1_low = low[fi - 1]
                    c2_close = close[fi]
                    c3_low = low[fi + 1]
                    c3_high = high[fi + 1]
                    
                    if c2_close <= 0:
                        continue
                    
                    if bias == "bullish":
                        gap_low = c1_high
                        gap_high = c3_low
                        if gap_high > gap_low:
                            gap_pct = (gap_high - gap_low) / c2_close
                            if gap_pct >= MIN_FVG_PCT:
                                zone = {
                                    'zone_type': 'fvg', 'direction': 'bullish',
                                    'zone_high': gap_high, 'zone_low': gap_low,
                                    'zone_mid': (gap_high + gap_low) / 2,
                                }
                                break
                    
                    elif bias == "bearish":
                        gap_high = c1_low
                        gap_low = c3_high
                        if gap_high > gap_low:
                            gap_pct = (gap_high - gap_low) / c2_close
                            if gap_pct >= MIN_FVG_PCT:
                                zone = {
                                    'zone_type': 'fvg', 'direction': 'bearish',
                                    'zone_high': gap_high, 'zone_low': gap_low,
                                    'zone_mid': (gap_high + gap_low) / 2,
                                }
                                break

            if zone is None:
                continue

            # ── G7: LTF Confirmation (optional) ────────────────────────────
            confirm_type = "BOS"
            if not skip_g7:
                # Check for structure break in last few bars
                confirmed = False
                if bias == "bullish":
                    # Check if close broke above recent swing high
                    recent_sh = np.where(sh_mask[max(0, i-20):i])[0]
                    if len(recent_sh) > 0:
                        last_sh_price = high[recent_sh[-1] + max(0, i-20)]
                        if close[i] > last_sh_price:
                            confirmed = True
                            confirm_type = "BOS"
                    # Check for CHoCH
                    if not confirmed and i >= 50:
                        mid = i // 2
                        prior_sh = np.where(sh_mask[lb:mid])[0] + lb
                        recent_sh2 = np.where(sh_mask[mid:i])[0] + mid
                        if len(prior_sh) >= 2 and len(recent_sh2) >= 1:
                            if high[prior_sh[-1]] < high[prior_sh[0]]:  # prior was bearish (LH)
                                if high[recent_sh2[-1]] > high[prior_sh[-1]]:
                                    confirmed = True
                                    confirm_type = "CHoCH"
                elif bias == "bearish":
                    recent_sl = np.where(sl_mask[max(0, i-20):i])[0]
                    if len(recent_sl) > 0:
                        last_sl_price = low[recent_sl[-1] + max(0, i-20)]
                        if close[i] < last_sl_price:
                            confirmed = True
                            confirm_type = "BOS"
                    if not confirmed and i >= 50:
                        mid = i // 2
                        prior_sl = np.where(sl_mask[lb:mid])[0] + lb
                        recent_sl2 = np.where(sl_mask[mid:i])[0] + mid
                        if len(prior_sl) >= 2 and len(recent_sl2) >= 1:
                            if low[prior_sl[-1]] > low[prior_sl[0]]:  # prior was bullish (HL)
                                if low[recent_sl2[-1]] < low[prior_sl[-1]]:
                                    confirmed = True
                                    confirm_type = "CHoCH"
                
                if not confirmed:
                    continue  # G7 fails

            # ── G8: RR Validation ───────────────────────────────────────────
            atr_val = features['atr'][i]
            if atr_val <= 0:
                continue

            zone_mid = zone['zone_mid']
            zone_high = zone['zone_high']
            zone_low = zone['zone_low']

            if bias == "bullish":
                entry = zone_mid
                sl_raw = zone_low - (atr_val * ATR_SL_MULTIPLIER)
                sl = min(sl_raw, zone_low * 0.998)
                sl_dist = abs(entry - sl)
                if sl_dist <= 0:
                    continue
                tp1 = entry + sl_dist * 1.0
                tp2 = entry + sl_dist * 2.0
                # TP3: next swing high beyond tp2
                tp3 = None
                if use_tp3:
                    sh_after = np.where(sh_mask[lb:i])[0] + lb
                    candidates = sorted([high[idx] for idx in sh_after if high[idx] > tp2])
                    tp3 = candidates[0] if candidates else None
                rr = (tp2 - entry) / sl_dist
            else:
                entry = zone_mid
                sl_raw = zone_high + (atr_val * ATR_SL_MULTIPLIER)
                sl = max(sl_raw, zone_high * 1.002)
                sl_dist = abs(sl - entry)
                if sl_dist <= 0:
                    continue
                tp1 = entry - sl_dist * 1.0
                tp2 = entry - sl_dist * 2.0
                tp3 = None
                if use_tp3:
                    sl_after = np.where(sl_mask[lb:i])[0] + lb
                    candidates = sorted([low[idx] for idx in sl_after if low[idx] < tp2], reverse=True)
                    tp3 = candidates[0] if candidates else None
                rr = (entry - tp2) / sl_dist

            if rr < MIN_RR:
                continue

            # Cooldown
            direction = "BUY" if bias == "bullish" else "SELL"
            cd_key = (symbol, direction)
            if cd_key in last_signal_idx:
                if i - last_signal_idx[cd_key] < COOLDOWN_BARS:
                    continue

            # Entry shift / randomize
            entry_idx = i + shift_entries
            if randomize_entries:
                entry_idx = i + random.randint(-5, 5)
                entry_idx = max(EMA_PERIOD + 30, min(entry_idx, n - 3))
            if entry_idx >= n - 2 or entry_idx < EMA_PERIOD + 30:
                continue

            # Simulate exit
            future_start = entry_idx + 1
            future_end = min(future_start + max_holding_bars, n)
            future_close = close[future_start:future_end]
            future_high = high[future_start:future_end]
            future_low = low[future_start:future_end]

            if len(future_close) < 2:
                continue

            cost = base_spread + COMMISSION_PCT + SLIPPAGE_PCT * 2

            trade_result = _simulate_exit(
                direction, entry, sl, tp1, tp2, tp3,
                future_high, future_low, future_close, cost, use_tp3
            )

            result_type, exit_price, holding_bars = trade_result

            if direction == "BUY":
                actual_entry = entry * (1 + SLIPPAGE_PCT)
                pnl_pct = (exit_price - actual_entry) / actual_entry - cost
            else:
                actual_entry = entry * (1 - SLIPPAGE_PCT)
                pnl_pct = (actual_entry - exit_price) / actual_entry - cost

            # Confidence
            score = 0.3
            if sweep.get('close_inside', False):
                score += 0.3
            recency = max(0.0, 1.0 - (sweep.get('candles_ago', 20) / 20.0))
            score += recency * 0.2
            if zone['zone_type'] == 'order_block' and confirm_type == "CHoCH":
                score += 0.2
            elif zone['zone_type'] == 'order_block':
                score += 0.15
            confidence = "HIGH" if score >= 0.70 else ("MEDIUM" if score >= 0.45 else "LOW")

            trade = TradeResult(
                symbol=display_name, direction=direction,
                entry_time=df['timestamp'].iloc[entry_idx],
                exit_time=df['timestamp'].iloc[min(entry_idx + holding_bars, n - 1)],
                entry_price=entry, exit_price=exit_price,
                stop_loss=sl, tp1=tp1, tp2=tp2, tp3=tp3,
                rr=round(rr, 2), pnl_pct=round(pnl_pct, 6),
                result=result_type, zone_type=zone['zone_type'],
                confirm_type=confirm_type, confidence=confidence,
                holding_bars=holding_bars, cost_pct=round(cost, 6)
            )

            symbol_trades.append(trade)
            last_signal_idx[cd_key] = i

        per_instrument[display_name] = len(symbol_trades)
        all_trades.extend(symbol_trades)
        for t in symbol_trades:
            per_asset_class[asset_class].append(t)

    # ── Aggregate Metrics ──────────────────────────────────────────────────
    result.trades = all_trades
    result.total_trades = len(all_trades)
    result.per_instrument = per_instrument

    if not all_trades:
        return result

    wins = [t for t in all_trades if t.pnl_pct > 0]
    losses = [t for t in all_trades if t.pnl_pct <= 0]
    result.winning_trades = len(wins)
    result.losing_trades = len(losses)
    result.win_rate = len(wins) / len(all_trades)
    result.avg_win_pct = np.mean([t.pnl_pct for t in wins]) * 100 if wins else 0
    result.avg_loss_pct = np.mean([t.pnl_pct for t in losses]) * 100 if losses else 0

    gross_profit = sum(t.pnl_pct for t in wins) if wins else 0
    gross_loss = abs(sum(t.pnl_pct for t in losses)) if losses else 1e-10
    result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    result.expectancy_pct = np.mean([t.pnl_pct for t in all_trades]) * 100

    returns = np.array([t.pnl_pct for t in all_trades])
    if len(returns) > 1 and np.std(returns) > 0:
        result.sharpe_ratio = float((np.mean(returns) / np.std(returns)) * np.sqrt(252))
        downside = returns[returns < 0]
        if len(downside) > 0 and np.std(downside) > 0:
            result.sortino_ratio = float((np.mean(returns) / np.std(downside)) * np.sqrt(252))

    equity_curve = np.cumsum(returns) + 1.0
    peak = np.maximum.accumulate(equity_curve)
    drawdown = (peak - equity_curve) / peak
    result.max_drawdown_pct = float(np.max(drawdown)) * 100 if len(drawdown) > 0 else 0

    consec = max_consec = 0
    for t in all_trades:
        if t.pnl_pct <= 0:
            consec += 1
            max_consec = max(max_consec, consec)
        else:
            consec = 0
    result.max_consecutive_losses = max_consec

    result.avg_rr_achieved = float(np.mean([t.rr for t in all_trades]))
    result.avg_holding_bars = float(np.mean([t.holding_bars for t in all_trades]))

    tp1_hits = sum(1 for t in all_trades if t.result in ("TP1", "TP2", "TP3"))
    tp2_hits = sum(1 for t in all_trades if t.result in ("TP2", "TP3"))
    tp3_hits = sum(1 for t in all_trades if t.result == "TP3")
    sl_hits = sum(1 for t in all_trades if t.result == "SL")
    result.tp1_hit_rate = tp1_hits / len(all_trades)
    result.tp2_hit_rate = tp2_hits / len(all_trades)
    result.tp3_hit_rate = tp3_hits / len(all_trades)
    result.sl_hit_rate = sl_hits / len(all_trades)

    buys = [t for t in all_trades if t.direction == "BUY"]
    sells = [t for t in all_trades if t.direction == "SELL"]
    result.buy_trades = len(buys)
    result.sell_trades = len(sells)
    result.buy_win_rate = sum(1 for t in buys if t.pnl_pct > 0) / len(buys) if buys else 0
    result.sell_win_rate = sum(1 for t in sells if t.pnl_pct > 0) / len(sells) if sells else 0

    annual_return = result.expectancy_pct * 252
    result.calmar_ratio = annual_return / result.max_drawdown_pct if result.max_drawdown_pct > 0 else 0

    for ac, trades_list in per_asset_class.items():
        ac_wins = [t for t in trades_list if t.pnl_pct > 0]
        result.per_asset_class[ac] = {
            'count': len(trades_list),
            'win_rate': len(ac_wins) / len(trades_list) if trades_list else 0,
            'avg_pnl_pct': float(np.mean([t.pnl_pct for t in trades_list])) * 100 if trades_list else 0,
        }

    return result


def _simulate_exit(
    direction: str, entry: float, sl: float, tp1: float, tp2: float,
    tp3: Optional[float], future_high: np.ndarray, future_low: np.ndarray,
    future_close: np.ndarray, cost: float, use_tp3: bool = True
) -> Tuple[str, float, int]:
    """Fast exit simulation using numpy arrays."""
    n = len(future_close)
    
    if direction == "BUY":
        for bar in range(n):
            # SL check first (conservative)
            if future_low[bar] <= sl:
                return ("SL", sl * (1 - SLIPPAGE_PCT), bar + 1)
            # TP checks (sequential)
            if future_high[bar] >= tp1:
                if future_high[bar] >= tp2:
                    if tp3 and use_tp3 and future_high[bar] >= tp3:
                        return ("TP3", tp3 * (1 - SLIPPAGE_PCT), bar + 1)
                    return ("TP2", tp2 * (1 - SLIPPAGE_PCT), bar + 1)
                return ("TP1", tp1 * (1 - SLIPPAGE_PCT), bar + 1)
        # Timeout
        exit_p = future_close[-1]
        return ("TP1" if exit_p > entry else "SL", exit_p, n)
    
    elif direction == "SELL":
        for bar in range(n):
            if future_high[bar] >= sl:
                return ("SL", sl * (1 + SLIPPAGE_PCT), bar + 1)
            if future_low[bar] <= tp1:
                if future_low[bar] <= tp2:
                    if tp3 and use_tp3 and future_low[bar] <= tp3:
                        return ("TP3", tp3 * (1 + SLIPPAGE_PCT), bar + 1)
                    return ("TP2", tp2 * (1 + SLIPPAGE_PCT), bar + 1)
                return ("TP1", tp1 * (1 + SLIPPAGE_PCT), bar + 1)
        exit_p = future_close[-1]
        return ("TP1" if exit_p < entry else "SL", exit_p, n)

    return ("SL", entry, 0)


# ═══════════════════════════════════════════════════════════════════════════════
# RED FLAG DETECTION & VERDICT
# ═══════════════════════════════════════════════════════════════════════════════

def detect_red_flags(result: BacktestResult, label: str = "") -> List[str]:
    flags = []
    if result.total_trades == 0:
        flags.append("ZERO_TRADES: No trades generated")
        return flags
    if result.win_rate > 0.85 and result.total_trades > 50:
        flags.append(f"WIN_RATE_TOO_HIGH: {result.win_rate:.1%} — >85% with >50 trades suggests lookahead")
    if result.sharpe_ratio > 5.0:
        flags.append(f"SHARPE_TOO_HIGH: {result.sharpe_ratio:.2f} — unrealistic for live trading")
    if result.sortino_ratio > 20.0:
        flags.append(f"SORTINO_TOO_HIGH: {result.sortino_ratio:.2f}")
    if result.profit_factor > 3.0 and result.total_trades > 100:
        flags.append(f"PROFIT_FACTOR_SUSPICIOUS: {result.profit_factor:.2f}")
    if result.max_drawdown_pct < 1.0 and result.total_trades > 50:
        flags.append(f"MAX_DD_TOO_LOW: {result.max_drawdown_pct:.2f}%")
    if abs(result.buy_win_rate - result.sell_win_rate) > 0.3:
        flags.append(f"DIRECTIONAL_BIAS: BUY {result.buy_win_rate:.1%} vs SELL {result.sell_win_rate:.1%}")
    if result.tp3_hit_rate > 0.3:
        flags.append(f"TP3_HIT_RATE_HIGH: {result.tp3_hit_rate:.1%}")
    return flags


def classify_verdict(baseline: BacktestResult, test_results: Dict) -> str:
    score = 0
    max_score = 0
    red_flags = detect_red_flags(baseline, "BASELINE")
    
    if len(red_flags) > 3:
        return "COMPLETE_ILLUSION"
    score -= len(red_flags) * 2
    
    if baseline.expectancy_pct <= 0:
        return "COMPLETE_ILLUSION"
    
    # Baseline quality
    max_score += 10
    if 0.5 < baseline.sharpe_ratio < 3.0:
        score += 5
    elif baseline.sharpe_ratio >= 3.0:
        score += 3
    if 0.35 < baseline.win_rate < 0.70:
        score += 3
    if 1.3 < baseline.profit_factor < 3.0:
        score += 2
    
    # Test 1: Remove G7
    max_score += 10
    if 'remove_g7' in test_results:
        r = test_results['remove_g7']
        if r.expectancy_pct > 0:
            score += 5
            if r.win_rate > 0.30: score += 3
            if r.profit_factor > 1.1: score += 2
        else:
            score -= 5
    
    # Test 1b: Remove G7 instruments
    max_score += 10
    if 'remove_g7_instruments' in test_results:
        r = test_results['remove_g7_instruments']
        if r.expectancy_pct > 0: score += 5
        else: score -= 3
    
    # Test 2: Randomize entries
    max_score += 15
    if 'randomize_entries' in test_results:
        r = test_results['randomize_entries']
        if r.expectancy_pct > 0 and r.expectancy_pct >= baseline.expectancy_pct * 0.5:
            score -= 10  # Similar results = fake edge
        elif r.expectancy_pct <= 0:
            score += 10  # Randomized fails = real entry edge
        elif r.expectancy_pct < baseline.expectancy_pct * 0.3:
            score += 8
    
    # Test 3: Shift entries
    max_score += 10
    if 'shift_entries' in test_results:
        r = test_results['shift_entries']
        if r.expectancy_pct > 0: score += 5
        else: score -= 3
    
    # Test 4-5: Spread stress
    max_score += 10
    if 'double_spread' in test_results:
        r = test_results['double_spread']
        if r.expectancy_pct > 0: score += 5
        else: score -= 2
    
    # Test 6: Walk-forward
    max_score += 15
    if 'walk_forward' in test_results:
        wf_results = test_results['walk_forward']
        profitable = sum(1 for r in wf_results.values() if r.expectancy_pct > 0)
        total = len(wf_results)
        if total > 0:
            ratio = profitable / total
            if ratio >= 0.67: score += 10
            elif ratio >= 0.33: score += 5
            else: score -= 5
    
    # Test 7: Monte Carlo
    max_score += 10
    if 'monte_carlo' in test_results:
        mc = test_results['monte_carlo']
        if isinstance(mc, dict) and 'ruin_probability' in mc:
            if mc['ruin_probability'] < 0.05: score += 7
            elif mc['ruin_probability'] < 0.15: score += 4
            elif mc['ruin_probability'] < 0.30: score += 1
            else: score -= 5
    
    # Test 8: Cross-market
    max_score += 10
    if 'cross_market' in test_results:
        cm = test_results['cross_market']
        profitable = sum(1 for r in cm.values() if r.expectancy_pct > 0)
        total = len(cm)
        if total > 0:
            ratio = profitable / total
            if ratio >= 0.75: score += 7
            elif ratio >= 0.50: score += 4
            else: score -= 2
    
    pct = score / max_score if max_score > 0 else 0
    if pct >= 0.70: return "EXCEPTIONAL"
    elif pct >= 0.50: return "STRONG_INSTITUTIONAL"
    elif pct >= 0.25: return "SMALL_REAL_EDGE"
    return "COMPLETE_ILLUSION"


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║  INSTITUTIONAL ADVERSARIAL VALIDATION BACKTEST                      ║")
    print("║  MarketMate Signal Engine — 'Try to KILL Strategy #1'              ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print(f"\n  Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ── Load Data ──────────────────────────────────────────────────────────
    print("\n── Loading historical data ──")
    cache_path = "/home/z/my-project/download/market_data.pkl"
    with open(cache_path, 'rb') as f:
        data = pickle.load(f)
    print(f"  Loaded {len(data)} instruments from cache")

    # ── Baseline ───────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("BASELINE: Full pipeline with realistic costs")
    print("=" * 70)
    baseline = run_backtest_optimized(data, spread_multiplier=1.0)
    _print_result("BASELINE", baseline)

    # ── Adversarial Tests ──────────────────────────────────────────────────
    all_results = {}

    # Test 1: Remove G7
    print("\n" + "=" * 70)
    print("TEST 1: Remove G7 (LTF Confirmation)")
    print("=" * 70)
    all_results['remove_g7'] = run_backtest_optimized(data, skip_g7=True)
    _print_result("REMOVE_G7", all_results['remove_g7'])

    # Test 1b: Remove G7 instruments
    print("\n" + "=" * 70)
    print("TEST 1b: Remove G7 instruments")
    print("=" * 70)
    all_results['remove_g7_instruments'] = run_backtest_optimized(data, skip_g7_instruments=True)
    _print_result("REMOVE_G7_INSTRUMENTS", all_results['remove_g7_instruments'])

    # Test 2: Randomize entries
    print("\n" + "=" * 70)
    print("TEST 2: Randomize entries, keep exits")
    print("=" * 70)
    np.random.seed(RANDOM_SEED + 2)
    random.seed(RANDOM_SEED + 2)
    all_results['randomize_entries'] = run_backtest_optimized(data, randomize_entries=True)
    _print_result("RANDOMIZE_ENTRIES", all_results['randomize_entries'])

    # Test 3: Shift entries +1
    print("\n" + "=" * 70)
    print("TEST 3: Shift entries +1 candle")
    print("=" * 70)
    all_results['shift_entries'] = run_backtest_optimized(data, shift_entries=1)
    _print_result("SHIFT_ENTRIES", all_results['shift_entries'])

    # Test 4: Double spread
    print("\n" + "=" * 70)
    print("TEST 4: Double spread")
    print("=" * 70)
    all_results['double_spread'] = run_backtest_optimized(data, spread_multiplier=2.0)
    _print_result("DOUBLE_SPREAD", all_results['double_spread'])

    # Test 5: Triple spread
    print("\n" + "=" * 70)
    print("TEST 5: Triple spread")
    print("=" * 70)
    all_results['triple_spread'] = run_backtest_optimized(data, spread_multiplier=3.0)
    _print_result("TRIPLE_SPREAD", all_results['triple_spread'])

    # Test 6: Walk-forward
    print("\n" + "=" * 70)
    print("TEST 6: Walk-forward validation")
    print("=" * 70)
    wf_results = {}
    for train_start, train_end, test_start, test_end in WALK_FORWARD_WINDOWS:
        label = f"Test {test_start[:4]}-{test_end[:4]}"
        print(f"\n  Walk-forward: {label}")
        r = run_backtest_optimized(data, start_date=test_start, end_date=test_end)
        wf_results[label] = r
        _print_result(label, r)
    all_results['walk_forward'] = wf_results

    # Test 7: Monte Carlo
    print("\n" + "=" * 70)
    print(f"TEST 7: Monte Carlo ({MONTE_CARLO_RUNS:,} runs)")
    print("=" * 70)
    mc_result = _run_monte_carlo(baseline)
    all_results['monte_carlo'] = mc_result
    print(f"  Mean Final Equity: {mc_result.get('mean_final_equity', 0):.4f}")
    print(f"  Ruin Probability: {mc_result.get('ruin_probability', 0):.2%}")
    print(f"  95th Pctile DD: {mc_result.get('p95_max_drawdown_pct', 0):.2f}%")
    print(f"  Profitable Runs: {mc_result.get('pct_profitable_runs', 0):.2%}")

    # Test 8: Cross-market
    print("\n" + "=" * 70)
    print("TEST 8: Cross-market validation")
    print("=" * 70)
    cm_results = {}
    for ac, symbols in INSTRUMENTS.items():
        available = [s for s in symbols if s in data and data[s] is not None and not data[s].empty]
        if available:
            print(f"\n  Testing {ac.upper()}")
            r = run_backtest_optimized(data, instruments=available)
            cm_results[ac] = r
            _print_result(ac.upper(), r)
    all_results['cross_market'] = cm_results

    # ── Red Flags ──────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("RED FLAG DETECTION")
    print("=" * 70)
    baseline_flags = detect_red_flags(baseline, "BASELINE")
    if baseline_flags:
        print(f"\n  Baseline Red Flags ({len(baseline_flags)}):")
        for flag in baseline_flags:
            print(f"    [!] {flag}")
    else:
        print("\n  No baseline red flags detected.")

    # ── Verdict ────────────────────────────────────────────────────────────
    print("\n" + "=" * 70)
    print("VERDICT CLASSIFICATION")
    print("=" * 70)
    verdict = classify_verdict(baseline, all_results)
    verdict_labels = {
        "COMPLETE_ILLUSION": "COMPLETE ILLUSION — Not tradeable",
        "SMALL_REAL_EDGE": "SMALL REAL EDGE — Modest but genuine",
        "STRONG_INSTITUTIONAL": "STRONG INSTITUTIONAL EDGE — Convincing",
        "EXCEPTIONAL": "EXCEPTIONAL EDGE — Passes all tests",
    }
    print(f"\n  >>> VERDICT: {verdict_labels.get(verdict, verdict)} <<<")

    # ── Save Results ───────────────────────────────────────────────────────
    output = {
        'timestamp': datetime.now().isoformat(),
        'verdict': verdict,
        'red_flags': {'baseline': baseline_flags},
        'baseline': _serialize_result(baseline),
        'tests': {},
    }
    for name, result in all_results.items():
        if isinstance(result, BacktestResult):
            output['tests'][name] = _serialize_result(result)
        elif isinstance(result, dict):
            serialized = {}
            for k, v in result.items():
                if isinstance(v, BacktestResult):
                    serialized[k] = _serialize_result(v)
                else:
                    serialized[k] = v
            output['tests'][name] = serialized

    json_path = os.path.join(OUTPUT_DIR, "adversarial_backtest_results.json")
    with open(json_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"\n  Results saved to: {json_path}")

    # ── Print Summary ─────────────────────────────────────────────────────
    _print_summary(baseline, all_results, verdict, baseline_flags)

    return output


def _run_monte_carlo(baseline: BacktestResult) -> Dict:
    if not baseline.trades:
        return {'error': 'No trades'}
    returns = np.array([t.pnl_pct for t in baseline.trades])
    n_trades = len(returns)
    
    final_equities = np.zeros(MONTE_CARLO_RUNS)
    max_drawdowns = np.zeros(MONTE_CARLO_RUNS)
    ruin_count = 0
    
    for run in range(MONTE_CARLO_RUNS):
        sampled = np.random.choice(returns, size=n_trades, replace=True)
        equity = np.cumsum(sampled) + 1.0
        final_equities[run] = equity[-1]
        peak = np.maximum.accumulate(equity)
        dd = (peak - equity) / peak
        max_drawdowns[run] = np.max(dd)
        if np.min(equity) < 0.80:
            ruin_count += 1
    
    return {
        'mean_final_equity': float(np.mean(final_equities)),
        'median_final_equity': float(np.median(final_equities)),
        'p5_final_equity': float(np.percentile(final_equities, 5)),
        'p95_final_equity': float(np.percentile(final_equities, 95)),
        'mean_max_drawdown_pct': float(np.mean(max_drawdowns) * 100),
        'median_max_drawdown_pct': float(np.median(max_drawdowns) * 100),
        'p95_max_drawdown_pct': float(np.percentile(max_drawdowns, 95) * 100),
        'worst_max_drawdown_pct': float(np.max(max_drawdowns) * 100),
        'ruin_probability': ruin_count / MONTE_CARLO_RUNS,
        'pct_profitable_runs': float(np.mean(final_equities > 1.0)),
    }


def _print_result(label: str, result: BacktestResult):
    if result.total_trades == 0:
        print(f"  {label}: 0 trades")
        return
    print(f"  {label}: {result.total_trades} trades | WR {result.win_rate:.1%} | "
          f"PF {result.profit_factor:.2f} | Exp {result.expectancy_pct:.4f}% | "
          f"Sharpe {result.sharpe_ratio:.2f} | DD {result.max_drawdown_pct:.2f}%")


def _serialize_result(result: BacktestResult) -> dict:
    return {
        'total_trades': result.total_trades,
        'winning_trades': result.winning_trades,
        'losing_trades': result.losing_trades,
        'win_rate': round(result.win_rate, 4),
        'avg_win_pct': round(result.avg_win_pct, 4),
        'avg_loss_pct': round(result.avg_loss_pct, 4),
        'profit_factor': round(result.profit_factor, 4),
        'expectancy_pct': round(result.expectancy_pct, 6),
        'sharpe_ratio': round(result.sharpe_ratio, 4),
        'sortino_ratio': round(result.sortino_ratio, 4),
        'max_drawdown_pct': round(result.max_drawdown_pct, 4),
        'max_consecutive_losses': result.max_consecutive_losses,
        'avg_rr_achieved': round(result.avg_rr_achieved, 4),
        'calmar_ratio': round(result.calmar_ratio, 4),
        'avg_holding_bars': round(result.avg_holding_bars, 2),
        'tp1_hit_rate': round(result.tp1_hit_rate, 4),
        'tp2_hit_rate': round(result.tp2_hit_rate, 4),
        'tp3_hit_rate': round(result.tp3_hit_rate, 4),
        'sl_hit_rate': round(result.sl_hit_rate, 4),
        'buy_trades': result.buy_trades,
        'sell_trades': result.sell_trades,
        'buy_win_rate': round(result.buy_win_rate, 4),
        'sell_win_rate': round(result.sell_win_rate, 4),
        'per_instrument': result.per_instrument,
        'per_asset_class': result.per_asset_class,
    }


def _print_summary(baseline, all_results, verdict, flags):
    print("\n" + "=" * 70)
    print("FINAL SUMMARY")
    print("=" * 70)
    
    print(f"\n  BASELINE:")
    print(f"    Trades: {baseline.total_trades}  |  Win Rate: {baseline.win_rate:.1%}")
    print(f"    Profit Factor: {baseline.profit_factor:.2f}  |  Expectancy: {baseline.expectancy_pct:.4f}%")
    print(f"    Sharpe: {baseline.sharpe_ratio:.2f}  |  Sortino: {baseline.sortino_ratio:.2f}")
    print(f"    Max DD: {baseline.max_drawdown_pct:.2f}%  |  Max Consec Losses: {baseline.max_consecutive_losses}")
    print(f"    TP1: {baseline.tp1_hit_rate:.1%}  |  TP2: {baseline.tp2_hit_rate:.1%}  |  TP3: {baseline.tp3_hit_rate:.1%}  |  SL: {baseline.sl_hit_rate:.1%}")
    
    print(f"\n  ADVERSARIAL COMPARISON:")
    print(f"    {'Test':<25} {'Trades':>7} {'Win%':>7} {'PF':>7} {'Exp%':>10} {'Sharpe':>8}")
    for name, result in all_results.items():
        if isinstance(result, BacktestResult):
            print(f"    {name:<25} {result.total_trades:>7} {result.win_rate*100:>6.1f}% "
                  f"{result.profit_factor:>7.2f} {result.expectancy_pct:>9.4f}% "
                  f"{result.sharpe_ratio:>8.2f}")
    
    if 'monte_carlo' in all_results and isinstance(all_results['monte_carlo'], dict):
        mc = all_results['monte_carlo']
        print(f"\n  MONTE CARLO ({MONTE_CARLO_RUNS:,} runs):")
        print(f"    Mean Equity: {mc.get('mean_final_equity', 0):.4f}")
        print(f"    Ruin Prob: {mc.get('ruin_probability', 0):.2%}")
        print(f"    95th Pctile DD: {mc.get('p95_max_drawdown_pct', 0):.2f}%")
    
    if 'walk_forward' in all_results:
        print(f"\n  WALK-FORWARD:")
        for label, r in all_results['walk_forward'].items():
            if isinstance(r, BacktestResult):
                status = "PROFITABLE" if r.expectancy_pct > 0 else "UNPROFITABLE"
                print(f"    {label}: {status} (Exp={r.expectancy_pct:.4f}%, PF={r.profit_factor:.2f})")
    
    if 'cross_market' in all_results:
        print(f"\n  CROSS-MARKET:")
        for ac, r in all_results['cross_market'].items():
            if isinstance(r, BacktestResult):
                status = "PROFITABLE" if r.expectancy_pct > 0 else "UNPROFITABLE"
                print(f"    {ac.upper()}: {status} ({r.total_trades} trades, WR={r.win_rate:.1%})")
    
    if flags:
        print(f"\n  RED FLAGS ({len(flags)}):")
        for f in flags:
            print(f"    [!] {f}")
    
    vl = {
        "COMPLETE_ILLUSION": "[X] COMPLETE ILLUSION",
        "SMALL_REAL_EDGE": "[~] SMALL REAL EDGE",
        "STRONG_INSTITUTIONAL": "[+] STRONG INSTITUTIONAL EDGE",
        "EXCEPTIONAL": "[++] EXCEPTIONAL EDGE",
    }
    print(f"\n  >>> VERDICT: {vl.get(verdict, verdict)} <<<")
    print()


if __name__ == "__main__":
    results = main()
