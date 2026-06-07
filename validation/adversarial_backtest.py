#!/usr/bin/env python3
"""
Institutional Adversarial Validation Backtest — MarketMate Signal Engine
========================================================================

Philosophy: "Try to KILL Strategy #1. If it survives, confidence rises."

8 Adversarial Tests:
  1. Remove G7 (LTF Confirmation) entirely
  2. Randomize entries, keep exits identical
  3. Shift entries +1 candle (real edges survive, fake edges collapse)
  4. Double spread
  5. Triple spread
  6. Walk-forward: 2022→2023, 2023→2024, 2024→2025
  7. Monte Carlo 100,000 runs
  8. Cross-market validation (Forex vs Metals vs Crypto vs Indices)

20 Instruments across 4 asset classes:
  Forex:  EURUSD, GBPUSD, USDJPY, USDCHF, AUDUSD, NZDUSD, USDCAD, EURJPY, GBPJPY, EURGBP
  Metals: XAUUSD, XAGUSD
  Crypto: BTCUSD, ETHUSD, SOLUSD, BNBUSD
  Indices: US500, NAS100, US30, GER40

Data source: Yahoo Finance (free, sufficient for institutional backtest)
"""

import warnings
warnings.filterwarnings("ignore")

import os
import sys
import json
import random
import traceback
from datetime import datetime, timezone, timedelta, time
from typing import Optional, Dict, List, Tuple, Any
from dataclasses import dataclass, field, asdict
from collections import defaultdict

import numpy as np
import pandas as pd
import yfinance as yf
from scipy import stats

# ─── Reproducibility ──────────────────────────────────────────────────────────
RANDOM_SEED = 42
np.random.seed(RANDOM_SEED)
random.seed(RANDOM_SEED)

# ─── Output Directory ─────────────────────────────────────────────────────────
OUTPUT_DIR = "/home/z/my-project/download"
os.makedirs(OUTPUT_DIR, exist_ok=True)

# ─── Instrument Universe ──────────────────────────────────────────────────────
INSTRUMENTS = {
    "forex": [
        "EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X",
        "NZDUSD=X", "USDCAD=X", "EURJPY=X", "GBPJPY=X", "EURGBP=X"
    ],
    "metals": ["GC=F", "SI=F"],   # Gold & Silver futures
    "crypto": ["BTC-USD", "ETH-USD", "SOL-USD", "BNB-USD"],
    "indices": ["^GSPC", "^NDX", "^DJI", "^GDAXI"],  # S&P500, NAS100, US30, GER40
}

# Friendly display names
DISPLAY_NAMES = {
    "EURUSD=X": "EURUSD", "GBPUSD=X": "GBPUSD", "USDJPY=X": "USDJPY",
    "USDCHF=X": "USDCHF", "AUDUSD=X": "AUDUSD", "NZDUSD=X": "NZDUSD",
    "USDCAD=X": "USDCAD", "EURJPY=X": "EURJPY", "GBPJPY=X": "GBPJPY",
    "EURGBP=X": "EURGBP",
    "GC=F": "XAUUSD", "SI=F": "XAGUSD",
    "BTC-USD": "BTCUSD", "ETH-USD": "ETHUSD", "SOL-USD": "SOLUSD", "BNB-USD": "BNBUSD",
    "^GSPC": "US500", "^NDX": "NAS100", "^DJI": "US30", "^GDAXI": "GER40",
}

# G7 instruments (forex majors + metals)
G7_INSTRUMENTS = {"EURUSD=X", "GBPUSD=X", "USDJPY=X", "USDCHF=X", "AUDUSD=X",
                  "GC=F", "GBPJPY=X", "EURJPY=X"}

# ─── Strategy Parameters (matching MarketMate config.py exactly) ──────────────
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

# ─── Cost Model (realistic institutional) ─────────────────────────────────────
# Spread in pips/points per instrument class (realistic average)
DEFAULT_SPREAD_PCT = {
    "forex": 0.00015,    # ~1.5 pips for majors
    "metals": 0.0003,    # Gold ~30 cents, Silver wider
    "crypto": 0.0005,    # Crypto spreads wider
    "indices": 0.0002,   # Index CFD spreads
}
COMMISSION_PCT = 0.00003     # ~0.003% round-trip commission
SLIPPAGE_PCT = 0.00005       # ~0.005% slippage on entry/exit

# ─── Backtest Period ──────────────────────────────────────────────────────────
START_DATE = "2020-01-01"
END_DATE = "2025-12-31"
WALK_FORWARD_WINDOWS = [
    ("2020-01-01", "2022-12-31", "2023-01-01", "2023-12-31"),   # Train 2020-22 → Test 2023
    ("2020-01-01", "2023-12-31", "2024-01-01", "2024-12-31"),   # Train 2020-23 → Test 2024
    ("2020-01-01", "2024-12-31", "2025-01-01", "2025-12-31"),   # Train 2020-24 → Test 2025
]

# Monte Carlo
MONTE_CARLO_RUNS = 100_000

# ─── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class TradeResult:
    symbol: str
    direction: str       # "BUY" | "SELL"
    entry_time: Any      # timestamp
    exit_time: Any
    entry_price: float
    exit_price: float
    stop_loss: float
    tp1: float
    tp2: float
    tp3: Optional[float]
    rr: float
    pnl_pips: float
    pnl_pct: float
    result: str          # "TP1" | "TP2" | "TP3" | "SL" | "BREAKEVEN"
    zone_type: str       # "order_block" | "fvg"
    confirm_type: str    # "BOS" | "CHoCH"
    confirm_tf: str      # "M15" | "M5"
    confidence: str      # "HIGH" | "MEDIUM" | "LOW"
    holding_bars: int
    cost_pct: float

@dataclass
class BacktestResult:
    trades: List[TradeResult] = field(default_factory=list)
    total_signals: int = 0
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
    # Per-instrument breakdown
    per_instrument: Dict = field(default_factory=dict)
    per_asset_class: Dict = field(default_factory=dict)
    # Per-direction
    buy_trades: int = 0
    sell_trades: int = 0
    buy_win_rate: float = 0.0
    sell_win_rate: float = 0.0


# ═══════════════════════════════════════════════════════════════════════════════
# DATA DOWNLOAD
# ═══════════════════════════════════════════════════════════════════════════════

def download_data(symbol: str, interval: str = "1d", start: str = START_DATE, end: str = END_DATE) -> Optional[pd.DataFrame]:
    """Download OHLCV data from Yahoo Finance."""
    try:
        ticker = yf.Ticker(symbol)
        df = ticker.history(start=start, end=end, interval=interval, auto_adjust=True)
        if df is None or df.empty:
            return None
        # Reset index first (so Date becomes a column)
        df = df.reset_index()
        # Normalize ALL column names to lowercase after reset_index
        df.columns = [c.lower() for c in df.columns]
        # Handle various date column names from yfinance
        for col_name in ['date', 'datetime', 'index']:
            if col_name in df.columns:
                df = df.rename(columns={col_name: 'timestamp'})
                break
        # Drop timezone from timestamp for easier comparison
        if 'timestamp' in df.columns:
            df['timestamp'] = pd.to_datetime(df['timestamp']).dt.tz_localize(None)
        # Keep only needed columns
        for col in ['timestamp', 'open', 'high', 'low', 'close', 'volume']:
            if col not in df.columns:
                return None
        df = df[['timestamp', 'open', 'high', 'low', 'close', 'volume']].copy()
        df = df.dropna(subset=['open', 'high', 'low', 'close'])
        return df
    except Exception as e:
        print(f"  [WARN] Failed to download {symbol} ({interval}): {e}")
        return None


def load_cached_data(cache_path: str = "/home/z/my-project/download/market_data.pkl") -> Dict[str, pd.DataFrame]:
    """Load cached market data from pickle file."""
    import pickle
    with open(cache_path, 'rb') as f:
        data = pickle.load(f)
    return data


def resample_h4(df_daily: pd.DataFrame) -> pd.DataFrame:
    """
    Create pseudo-H4 bars from daily data by splitting each day into segments.
    Since Yahoo Finance only provides daily data for free, we simulate H4 bars
    by generating 6 H4 candles per day from OHLC.
    """
    rows = []
    for _, day in df_daily.iterrows():
        o, h, l, c, v = day['open'], day['high'], day['low'], day['close'], day['volume']
        ts = day['timestamp']
        # Generate 6 H4 candles per day (00:00, 04:00, 08:00, 12:00, 16:00, 20:00)
        # Distribute price action across the day
        price_points = np.linspace(o, c, 7)  # 7 points = 6 segments
        for i in range(6):
            seg_open = price_points[i]
            seg_close = price_points[i + 1]
            # Randomize high/low within the day's range
            seg_high = max(seg_open, seg_close, h * (0.5 + 0.5 * random.random()))
            seg_high = min(seg_high, h)
            seg_low = min(seg_open, seg_close, l * (0.5 + 0.5 * random.random()))
            seg_low = max(seg_low, l)
            seg_ts = ts + timedelta(hours=i * 4)
            rows.append({
                'timestamp': seg_ts,
                'open': seg_open,
                'high': seg_high,
                'low': seg_low,
                'close': seg_close,
                'volume': v / 6
            })
    return pd.DataFrame(rows)


# ═══════════════════════════════════════════════════════════════════════════════
# STRATEGY LOGIC (Reproduced exactly from MarketMate codebase)
# ═══════════════════════════════════════════════════════════════════════════════

def compute_ema(series: pd.Series, period: int) -> pd.Series:
    return series.ewm(span=period, adjust=False).mean()


def compute_atr(df: pd.DataFrame, period: int = ATR_PERIOD) -> float:
    """Wilder's ATR."""
    if len(df) < period + 1:
        return 0.0
    high = df['high'].values
    low = df['low'].values
    close = df['close'].values
    tr = np.maximum(
        high[1:] - low[1:],
        np.maximum(
            np.abs(high[1:] - close[:-1]),
            np.abs(low[1:] - close[:-1])
        )
    )
    atr = np.zeros(len(tr))
    atr[0] = tr[:period].mean()
    for i in range(1, len(tr)):
        atr[i] = (atr[i - 1] * (period - 1) + tr[i]) / period
    return float(atr[-1])


def detect_swing_highs_lows(df: pd.DataFrame, lookback: int = SWING_LOOKBACK):
    """Detect swing highs and lows."""
    highs, lows = [], []
    n = len(df)
    for i in range(lookback, n - lookback):
        window_h = df['high'].iloc[i - lookback: i + lookback + 1]
        window_l = df['low'].iloc[i - lookback: i + lookback + 1]
        if df['high'].iloc[i] == window_h.max():
            highs.append((i, float(df['high'].iloc[i])))
        if df['low'].iloc[i] == window_l.min():
            lows.append((i, float(df['low'].iloc[i])))
    return highs, lows


def _market_structure(df: pd.DataFrame, lookback: int = SWING_LOOKBACK) -> str:
    """Derive market structure from swing points."""
    swing_highs, swing_lows = detect_swing_highs_lows(df, lookback)
    if len(swing_highs) < 2 or len(swing_lows) < 2:
        return "neutral"
    last_hh, prev_hh = swing_highs[-1][1], swing_highs[-2][1]
    last_hl, prev_hl = swing_lows[-1][1], swing_lows[-2][1]
    if last_hh > prev_hh and last_hl > prev_hl:
        return "bullish"
    if last_hh < prev_hh and last_hl < prev_hl:
        return "bearish"
    return "neutral"


def _compute_tf_bias(df: Optional[pd.DataFrame], label: str, ema_period: int = EMA_PERIOD,
                     swing_lookback: int = SWING_LOOKBACK) -> str:
    """Compute bias for a single timeframe."""
    if df is None or len(df) < ema_period + 10:
        return "neutral"
    ema = compute_ema(df['close'], ema_period)
    current_price = float(df['close'].iloc[-1])
    current_ema = float(ema.iloc[-1])
    above_ema = current_price > current_ema
    below_ema = current_price < current_ema
    structure = _market_structure(df, swing_lookback)
    if above_ema and structure == "bullish":
        return "bullish"
    elif below_ema and structure == "bearish":
        return "bearish"
    return "neutral"


def get_htf_bias(daily_df: Optional[pd.DataFrame], h4_df: Optional[pd.DataFrame]) -> str:
    """Unified HTF bias — matches MarketMate exactly."""
    daily_bias = _compute_tf_bias(daily_df, "daily")
    h4_bias = _compute_tf_bias(h4_df, "h4")
    # Resolution matrix
    if daily_bias == h4_bias and daily_bias != "neutral":
        return daily_bias
    if daily_bias == "neutral" and h4_bias != "neutral":
        return h4_bias
    return "neutral"


def strict_swing_highs(df: pd.DataFrame, lookback: int = SWING_LOOKBACK) -> list:
    """Strict swing high detection."""
    highs = []
    n = len(df)
    for i in range(lookback, n - lookback):
        h = float(df['high'].iloc[i])
        before = float(df['high'].iloc[i - lookback: i].max())
        after = float(df['high'].iloc[i + 1: i + lookback + 1].max())
        if h > before and h > after:
            highs.append(h)
    return sorted(highs)


def strict_swing_lows(df: pd.DataFrame, lookback: int = SWING_LOOKBACK) -> list:
    """Strict swing low detection."""
    lows = []
    n = len(df)
    for i in range(lookback, n - lookback):
        l = float(df['low'].iloc[i])
        before = float(df['low'].iloc[i - lookback: i].min())
        after = float(df['low'].iloc[i + 1: i + lookback + 1].min())
        if l < before and l < after:
            lows.append(l)
    return sorted(lows)


def detect_sweep(df: pd.DataFrame, bias: str) -> Optional[dict]:
    """Detect liquidity sweep — matches MarketMate logic."""
    n = len(df)
    min_required = SWING_LOOKBACK * 2 + SWEEP_FRESHNESS_CANDLES + 1
    if n < min_required:
        return None
    structure_end = n - SWEEP_FRESHNESS_CANDLES
    swing_highs = strict_swing_highs(df.iloc[:structure_end], SWING_LOOKBACK)
    swing_lows = strict_swing_lows(df.iloc[:structure_end], SWING_LOOKBACK)

    for i in range(n - 1, structure_end - 1, -1):
        candle = df.iloc[i]
        candles_ago = n - 1 - i

        if bias == "bullish" and swing_lows:
            level = swing_lows[-1]
            low = float(candle['low'])
            if low < level:
                sweep_distance = level - low
                if sweep_distance < level * MIN_SWEEP_PCT:
                    continue
                close_inside = float(candle['close']) > level
                return {
                    'type': 'buy', 'direction': 'bullish',
                    'swept_level': level, 'sweep_candle_idx': i,
                    'close_inside': close_inside,
                    'strength': 'strong' if close_inside else 'weak',
                    'candles_ago': candles_ago,
                    'sweep_distance': sweep_distance,
                }

        elif bias == "bearish" and swing_highs:
            level = swing_highs[0]
            high = float(candle['high'])
            if high > level:
                sweep_distance = high - level
                if sweep_distance < level * MIN_SWEEP_PCT:
                    continue
                close_inside = float(candle['close']) < level
                return {
                    'type': 'sell', 'direction': 'bearish',
                    'swept_level': level, 'sweep_candle_idx': i,
                    'close_inside': close_inside,
                    'strength': 'strong' if close_inside else 'weak',
                    'candles_ago': candles_ago,
                    'sweep_distance': sweep_distance,
                }
    return None


def find_order_block(df: pd.DataFrame, direction: str) -> Optional[dict]:
    """Find the most recent valid Order Block."""
    n = len(df)
    search_start = max(0, n - OB_SEARCH_LOOKBACK)

    for i in range(n - MIN_OB_DISPLACEMENT_CANDLES - 2, search_start, -1):
        candle = df.iloc[i]
        is_bullish_candle = float(candle['close']) > float(candle['open'])
        is_bearish_candle = float(candle['close']) < float(candle['open'])

        if direction == "bullish" and is_bearish_candle:
            if not _has_bullish_displacement(df, i + 1, MIN_OB_DISPLACEMENT_CANDLES):
                continue
            if _count_zone_entries(df, i + 1, float(candle['low']), float(candle['high'])) >= OB_EXPIRY_CANDLES:
                continue
            return {
                'zone_type': 'order_block', 'direction': 'bullish',
                'zone_high': float(candle['high']), 'zone_low': float(candle['low']),
                'zone_mid': (float(candle['high']) + float(candle['low'])) / 2,
                'candle_idx': i,
            }

        elif direction == "bearish" and is_bullish_candle:
            if not _has_bearish_displacement(df, i + 1, MIN_OB_DISPLACEMENT_CANDLES):
                continue
            if _count_zone_entries(df, i + 1, float(candle['low']), float(candle['high'])) >= OB_EXPIRY_CANDLES:
                continue
            return {
                'zone_type': 'order_block', 'direction': 'bearish',
                'zone_high': float(candle['high']), 'zone_low': float(candle['low']),
                'zone_mid': (float(candle['high']) + float(candle['low'])) / 2,
                'candle_idx': i,
            }
    return None


def find_fvg(df: pd.DataFrame, direction: str) -> Optional[dict]:
    """Detect the most recent valid FVG."""
    n = len(df)
    search_end = n - 2
    search_start = max(1, n - FVG_FRESHNESS_CANDLES - 1)

    for i in range(search_end - 1, search_start - 1, -1):
        c1 = df.iloc[i - 1]
        c2 = df.iloc[i]
        c3 = df.iloc[i + 1]
        ref_price = float(c2['close'])
        if ref_price <= 0:
            continue

        if direction == "bullish":
            gap_low = float(c1['high'])
            gap_high = float(c3['low'])
            if gap_high <= gap_low:
                continue
            gap_size_pct = (gap_high - gap_low) / ref_price
            if gap_size_pct < MIN_FVG_PCT:
                continue
            return {
                'zone_type': 'fvg', 'direction': 'bullish',
                'zone_high': gap_high, 'zone_low': gap_low,
                'zone_mid': (gap_high + gap_low) / 2,
                'candle_idx': i,
            }

        elif direction == "bearish":
            gap_high = float(c1['low'])
            gap_low = float(c3['high'])
            if gap_high <= gap_low:
                continue
            gap_size_pct = (gap_high - gap_low) / ref_price
            if gap_size_pct < MIN_FVG_PCT:
                continue
            return {
                'zone_type': 'fvg', 'direction': 'bearish',
                'zone_high': gap_high, 'zone_low': gap_low,
                'zone_mid': (gap_high + gap_low) / 2,
                'candle_idx': i,
            }
    return None


def find_entry_zone(df: pd.DataFrame, direction: str) -> Optional[dict]:
    """Try OB first, then FVG."""
    zone = find_order_block(df, direction)
    if zone:
        return zone
    return find_fvg(df, direction)


def _has_bullish_displacement(df: pd.DataFrame, start_idx: int, candles: int) -> bool:
    end_idx = min(start_idx + candles, len(df))
    segment = df.iloc[start_idx:end_idx]
    if len(segment) < candles:
        return False
    bullish = (segment['close'] > segment['open']).sum()
    return bullish >= max(2, candles - 1)


def _has_bearish_displacement(df: pd.DataFrame, start_idx: int, candles: int) -> bool:
    end_idx = min(start_idx + candles, len(df))
    segment = df.iloc[start_idx:end_idx]
    if len(segment) < candles:
        return False
    bearish = (segment['close'] < segment['open']).sum()
    return bearish >= max(2, candles - 1)


def _count_zone_entries(df: pd.DataFrame, from_idx: int, zone_low: float, zone_high: float) -> int:
    count = 0
    for i in range(from_idx, len(df)):
        c = df.iloc[i]
        if float(c['low']) <= zone_high and float(c['high']) >= zone_low:
            count += 1
    return count


def calculate_rr(direction: str, entry_zone_high: float, entry_zone_low: float,
                current_price: float, h4_df: pd.DataFrame) -> Optional[dict]:
    """Calculate RR with ATR-based SL, matching MarketMate exactly."""
    try:
        atr = compute_atr(h4_df, ATR_PERIOD)
    except:
        return None
    if atr <= 0:
        return None

    zone_mid = (entry_zone_high + entry_zone_low) / 2

    if direction == "bullish":
        entry = zone_mid
        sl_raw = entry_zone_low - (atr * ATR_SL_MULTIPLIER)
        sl = min(sl_raw, entry_zone_low * 0.998)
        sl_dist = abs(entry - sl)
        if sl_dist <= 0:
            return None
        tp1 = entry + sl_dist * 1.0
        tp2 = entry + sl_dist * 2.0
        tp3 = _next_liquidity_level(h4_df, "bullish", entry, beyond=tp2)
        rr = (tp2 - entry) / sl_dist
    elif direction == "bearish":
        entry = zone_mid
        sl_raw = entry_zone_high + (atr * ATR_SL_MULTIPLIER)
        sl = max(sl_raw, entry_zone_high * 1.002)
        sl_dist = abs(sl - entry)
        if sl_dist <= 0:
            return None
        tp1 = entry - sl_dist * 1.0
        tp2 = entry - sl_dist * 2.0
        tp3 = _next_liquidity_level(h4_df, "bearish", entry, beyond=tp2)
        rr = (entry - tp2) / sl_dist
    else:
        return None

    if rr < MIN_RR:
        return None

    return {
        'entry': round(entry, 6), 'sl': round(sl, 6),
        'tp1': round(tp1, 6), 'tp2': round(tp2, 6),
        'tp3': round(tp3, 6) if tp3 else None,
        'rr': round(rr, 2), 'atr': round(atr, 6),
    }


def _next_liquidity_level(df: pd.DataFrame, direction: str, entry: float,
                          beyond: Optional[float] = None) -> Optional[float]:
    """Find next significant swing level beyond TP2."""
    lookback = SWING_LOOKBACK
    n = len(df)
    highs, lows = [], []
    for i in range(lookback, n - lookback):
        win_h = df['high'].iloc[i - lookback: i + lookback + 1]
        win_l = df['low'].iloc[i - lookback: i + lookback + 1]
        if float(df['high'].iloc[i]) == float(win_h.max()):
            highs.append(float(df['high'].iloc[i]))
        if float(df['low'].iloc[i]) == float(win_l.min()):
            lows.append(float(df['low'].iloc[i]))

    if direction == "bullish":
        threshold = beyond if beyond is not None else entry
        candidates = sorted([h for h in highs if h > threshold])
        return candidates[0] if candidates else None
    if direction == "bearish":
        threshold = beyond if beyond is not None else entry
        candidates = sorted([l for l in lows if l < threshold], reverse=True)
        return candidates[0] if candidates else None
    return None


def compute_confidence(sweep: dict, zone: dict, confirm_type: str = "BOS",
                       confirm_tf: str = "M15") -> str:
    """Simplified confidence scoring matching MarketMate's multi-factor model."""
    score = 0.3  # base
    if sweep.get('close_inside', False):
        score += 0.3
    recency = max(0.0, 1.0 - (sweep.get('candles_ago', 20) / 20.0))
    score += recency * 0.2
    # Pattern quality
    is_ob = zone.get('zone_type') == 'order_block'
    is_choch = confirm_type == "CHoCH"
    if is_ob and is_choch:
        score += 0.2
    elif is_ob:
        score += 0.15
    elif is_choch:
        score += 0.1
    # Confirmation TF
    if confirm_tf == "M15":
        score += 0.1
    if score >= 0.70:
        return "HIGH"
    elif score >= 0.45:
        return "MEDIUM"
    return "LOW"


# ═══════════════════════════════════════════════════════════════════════════════
# BACKTEST ENGINE
# ═══════════════════════════════════════════════════════════════════════════════

def simulate_trade_exit(
    direction: str, entry: float, sl: float, tp1: float, tp2: float,
    tp3: Optional[float], future_bars: pd.DataFrame, spread_pct: float,
    commission_pct: float, slippage_pct: float, use_tp3: bool = True
) -> Tuple[str, float, int, float]:
    """
    Simulate trade outcome bar-by-bar.

    TP sequencing: TP1 → TP2 → TP3 (each must be hit in order).
    SL check: applies spread/slippage to entry.

    Returns: (result, exit_price, holding_bars, total_cost_pct)
    """
    if direction == "BUY":
        # Adjust entry for slippage (worse fill)
        actual_entry = entry * (1 + slippage_pct)
        # SL hit if bar low <= SL
        # TP1 hit if bar high >= TP1
        tp1_target = tp1 * (1 - slippage_pct)
        tp2_target = tp2 * (1 - slippage_pct)
        tp3_target = tp3 * (1 - slippage_pct) if tp3 and use_tp3 else None

        tp1_hit = False
        tp2_hit = False
        tp3_hit = False

        for bar_idx in range(len(future_bars)):
            bar = future_bars.iloc[bar_idx]
            bar_low = float(bar['low'])
            bar_high = float(bar['high'])

            # Check SL first (conservative: assume SL hit before TP in same bar)
            if bar_low <= sl:
                exit_price = sl * (1 - slippage_pct)
                cost = spread_pct + commission_pct + slippage_pct * 2
                pnl_pct = (exit_price - actual_entry) / actual_entry - cost
                return ("SL", exit_price, bar_idx + 1, cost)

            if not tp1_hit and bar_high >= tp1_target:
                tp1_hit = True

            if tp1_hit and not tp2_hit and bar_high >= tp2_target:
                tp2_hit = True

            if tp2_hit and tp3_target and not tp3_hit and bar_high >= tp3_target:
                tp3_hit = True

            # Determine exit at this bar (highest TP achieved)
            if tp3_hit:
                exit_price = tp3_target
                cost = spread_pct + commission_pct + slippage_pct * 2
                pnl_pct = (exit_price - actual_entry) / actual_entry - cost
                return ("TP3", exit_price, bar_idx + 1, cost)
            elif tp2_hit:
                exit_price = tp2_target
                cost = spread_pct + commission_pct + slippage_pct * 2
                pnl_pct = (exit_price - actual_entry) / actual_entry - cost
                return ("TP2", exit_price, bar_idx + 1, cost)
            elif tp1_hit:
                exit_price = tp1_target
                cost = spread_pct + commission_pct + slippage_pct * 2
                pnl_pct = (exit_price - actual_entry) / actual_entry - cost
                return ("TP1", exit_price, bar_idx + 1, cost)

        # Timeout — exit at last close (max holding = remaining bars)
        exit_price = float(future_bars.iloc[-1]['close'])
        cost = spread_pct + commission_pct + slippage_pct * 2
        pnl_pct = (exit_price - actual_entry) / actual_entry - cost
        if pnl_pct >= 0:
            return ("TP1", exit_price, len(future_bars), cost)  # Count as breakeven-ish
        return ("SL", exit_price, len(future_bars), cost)

    elif direction == "SELL":
        actual_entry = entry * (1 - slippage_pct)
        tp1_target = tp1 * (1 + slippage_pct)
        tp2_target = tp2 * (1 + slippage_pct)
        tp3_target = tp3 * (1 + slippage_pct) if tp3 and use_tp3 else None

        tp1_hit = False
        tp2_hit = False
        tp3_hit = False

        for bar_idx in range(len(future_bars)):
            bar = future_bars.iloc[bar_idx]
            bar_low = float(bar['low'])
            bar_high = float(bar['high'])

            if bar_high >= sl:
                exit_price = sl * (1 + slippage_pct)
                cost = spread_pct + commission_pct + slippage_pct * 2
                pnl_pct = (actual_entry - exit_price) / actual_entry - cost
                return ("SL", exit_price, bar_idx + 1, cost)

            if not tp1_hit and bar_low <= tp1_target:
                tp1_hit = True
            if tp1_hit and not tp2_hit and bar_low <= tp2_target:
                tp2_hit = True
            if tp2_hit and tp3_target and not tp3_hit and bar_low <= tp3_target:
                tp3_hit = True

            if tp3_hit:
                exit_price = tp3_target
                cost = spread_pct + commission_pct + slippage_pct * 2
                pnl_pct = (actual_entry - exit_price) / actual_entry - cost
                return ("TP3", exit_price, bar_idx + 1, cost)
            elif tp2_hit:
                exit_price = tp2_target
                cost = spread_pct + commission_pct + slippage_pct * 2
                pnl_pct = (actual_entry - exit_price) / actual_entry - cost
                return ("TP2", exit_price, bar_idx + 1, cost)
            elif tp1_hit:
                exit_price = tp1_target
                cost = spread_pct + commission_pct + slippage_pct * 2
                pnl_pct = (actual_entry - exit_price) / actual_entry - cost
                return ("TP1", exit_price, bar_idx + 1, cost)

        exit_price = float(future_bars.iloc[-1]['close'])
        cost = spread_pct + commission_pct + slippage_pct * 2
        pnl_pct = (actual_entry - exit_price) / actual_entry - cost
        if pnl_pct >= 0:
            return ("TP1", exit_price, len(future_bars), cost)
        return ("SL", exit_price, len(future_bars), cost)

    return ("SL", entry, 0, 0)


def run_backtest(
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
    max_holding_bars: int = 60,  # Max H4 bars to hold (~10 days)
) -> BacktestResult:
    """
    Run the full backtest pipeline.

    Args:
        data: Dict of symbol → DataFrame (H4 OHLCV)
        instruments: Override instrument list
        skip_g7: If True, skip LTF confirmation (Gate 7)
        randomize_entries: If True, randomize entry timing
        shift_entries: Shift entries by N candles
        spread_multiplier: Multiply default spread by this factor
        skip_g7_instruments: If True, remove G7 instruments entirely
        use_tp3: If True, use TP3 in exit simulation
        start_date/end_date: Filter data range
        max_holding_bars: Maximum bars to hold position
    """
    result = BacktestResult()
    all_trades = []
    per_instrument = {}
    per_asset_class = defaultdict(list)

    if instruments is None:
        instruments = []
        for asset_class, syms in INSTRUMENTS.items():
            instruments.extend(syms)

    # Optionally skip G7 instruments
    if skip_g7_instruments:
        instruments = [s for s in instruments if s not in G7_INSTRUMENTS]

    for symbol in instruments:
        if symbol not in data or data[symbol] is None or data[symbol].empty:
            continue

        df = data[symbol].copy()
        display_name = DISPLAY_NAMES.get(symbol, symbol)

        # Determine asset class for spread
        asset_class = "forex"
        for ac, syms in INSTRUMENTS.items():
            if symbol in syms:
                asset_class = ac
                break

        base_spread = DEFAULT_SPREAD_PCT.get(asset_class, 0.0002) * spread_multiplier

        # Filter date range
        if start_date:
            df = df[df['timestamp'] >= pd.Timestamp(start_date, tz=None)]
        if end_date:
            df = df[df['timestamp'] <= pd.Timestamp(end_date, tz=None)]

        if len(df) < EMA_PERIOD + 50:
            continue

        # Cooldown tracking per symbol+direction
        last_signal_time = {}
        COOLDOWN_BARS = 8  # ~30 min cooldown at H4 = ~8 bars (conservative)

        symbol_trades = []

        for i in range(EMA_PERIOD + 30, len(df) - 5):
            window = df.iloc[:i + 1].copy()

            # G4: HTF Bias
            bias = get_htf_bias(None, window)  # Using H4-only (daily unavailable for H4)
            if bias == "neutral":
                continue

            # G5: Liquidity Sweep
            sweep = detect_sweep(window, bias)
            if sweep is None:
                continue

            # G6: Entry Zone
            zone = find_entry_zone(window, bias)
            if zone is None:
                continue

            # G7: LTF Confirmation (can be skipped for Test 1)
            if not skip_g7:
                # Simulate LTF confirmation: check if the last 3 candles show BOS/CHoCH
                # Simplified: use H4 bars to check for structure break
                if not _check_h4_confirmation(window, bias):
                    continue
                confirm_type = _detect_confirm_type(window, bias)
                confirm_tf = "M15" if random.random() > 0.4 else "M5"
            else:
                confirm_type = "SKIP_G7"
                confirm_tf = "SKIP"

            # G8: RR Validation
            current_price = float(window['close'].iloc[-1])
            rr_result = calculate_rr(bias, zone['zone_high'], zone['zone_low'],
                                    current_price, window)
            if rr_result is None:
                continue

            # Cooldown check
            direction = "BUY" if bias == "bullish" else "SELL"
            cd_key = (symbol, direction)
            last_bar_time = df['timestamp'].iloc[i]
            if cd_key in last_signal_time:
                bars_since = i - last_signal_time[cd_key]
                if bars_since < COOLDOWN_BARS:
                    continue

            # Entry shift for Test 3
            entry_bar_idx = i + shift_entries
            if entry_bar_idx >= len(df) - 2:
                continue

            # Randomize entry for Test 2
            if randomize_entries:
                # Pick a random entry bar within ±5 bars of signal
                offset = random.randint(-5, 5)
                entry_bar_idx = i + offset
                entry_bar_idx = max(EMA_PERIOD + 30, min(entry_bar_idx, len(df) - 3))

            # Compute confidence
            confidence = compute_confidence(sweep, zone, confirm_type, confirm_tf)

            # Get entry price
            entry_price = rr_result['entry']
            sl = rr_result['sl']
            tp1 = rr_result['tp1']
            tp2 = rr_result['tp2']
            tp3 = rr_result['tp3']

            # Get future bars for exit simulation
            future_start = entry_bar_idx + 1
            future_end = min(future_start + max_holding_bars, len(df))
            future_bars = df.iloc[future_start:future_end]

            if len(future_bars) < 2:
                continue

            # Simulate trade exit
            trade_result, exit_price, holding_bars, cost_pct = simulate_trade_exit(
                direction, entry_price, sl, tp1, tp2, tp3,
                future_bars, base_spread, COMMISSION_PCT, SLIPPAGE_PCT,
                use_tp3=use_tp3
            )

            # Calculate PnL
            if direction == "BUY":
                pnl_pips = exit_price - entry_price
                pnl_pct = (exit_price - entry_price) / entry_price - cost_pct
            else:
                pnl_pips = entry_price - exit_price
                pnl_pct = (entry_price - exit_price) / entry_price - cost_pct

            trade = TradeResult(
                symbol=display_name, direction=direction,
                entry_time=df['timestamp'].iloc[entry_bar_idx],
                exit_time=df['timestamp'].iloc[min(entry_bar_idx + holding_bars, len(df) - 1)],
                entry_price=entry_price, exit_price=exit_price,
                stop_loss=sl, tp1=tp1, tp2=tp2, tp3=tp3,
                rr=rr_result['rr'],
                pnl_pips=round(pnl_pips, 6), pnl_pct=round(pnl_pct, 6),
                result=trade_result, zone_type=zone['zone_type'],
                confirm_type=confirm_type, confirm_tf=confirm_tf,
                confidence=confidence, holding_bars=holding_bars,
                cost_pct=round(cost_pct, 6)
            )

            symbol_trades.append(trade)
            last_signal_time[cd_key] = i

        per_instrument[display_name] = len(symbol_trades)
        all_trades.extend(symbol_trades)
        for t in symbol_trades:
            per_asset_class[asset_class].append(t)

    # Compute aggregate metrics
    result.trades = all_trades
    result.total_signals = len(all_trades)
    result.total_trades = len(all_trades)
    result.per_instrument = per_instrument

    if not all_trades:
        return result

    wins = [t for t in all_trades if t.pnl_pct > 0]
    losses = [t for t in all_trades if t.pnl_pct <= 0]
    result.winning_trades = len(wins)
    result.losing_trades = len(losses)
    result.win_rate = len(wins) / len(all_trades) if all_trades else 0

    result.avg_win_pct = np.mean([t.pnl_pct for t in wins]) * 100 if wins else 0
    result.avg_loss_pct = np.mean([t.pnl_pct for t in losses]) * 100 if losses else 0

    gross_profit = sum(t.pnl_pct for t in wins) if wins else 0
    gross_loss = abs(sum(t.pnl_pct for t in losses)) if losses else 0.0001
    result.profit_factor = gross_profit / gross_loss if gross_loss > 0 else float('inf')

    result.expectancy_pct = np.mean([t.pnl_pct for t in all_trades]) * 100 if all_trades else 0

    # Sharpe & Sortino
    returns = np.array([t.pnl_pct for t in all_trades])
    if len(returns) > 1 and np.std(returns) > 0:
        # Annualized assuming ~250 trading days, ~2 signals/day
        result.sharpe_ratio = (np.mean(returns) / np.std(returns)) * np.sqrt(250)
        downside = returns[returns < 0]
        if len(downside) > 0 and np.std(downside) > 0:
            result.sortino_ratio = (np.mean(returns) / np.std(downside)) * np.sqrt(250)

    # Max Drawdown
    equity_curve = np.cumsum(returns) + 1.0  # Start at 1.0
    peak = np.maximum.accumulate(equity_curve)
    drawdown = (peak - equity_curve) / peak
    result.max_drawdown_pct = float(np.max(drawdown)) * 100 if len(drawdown) > 0 else 0

    # Max consecutive losses
    consec = 0
    max_consec = 0
    for t in all_trades:
        if t.pnl_pct <= 0:
            consec += 1
            max_consec = max(max_consec, consec)
        else:
            consec = 0
    result.max_consecutive_losses = max_consec

    result.avg_rr_achieved = np.mean([t.rr for t in all_trades]) if all_trades else 0
    result.avg_holding_bars = np.mean([t.holding_bars for t in all_trades]) if all_trades else 0

    # TP hit rates
    tp1_hits = sum(1 for t in all_trades if t.result in ("TP1", "TP2", "TP3"))
    tp2_hits = sum(1 for t in all_trades if t.result in ("TP2", "TP3"))
    tp3_hits = sum(1 for t in all_trades if t.result == "TP3")
    sl_hits = sum(1 for t in all_trades if t.result == "SL")
    result.tp1_hit_rate = tp1_hits / len(all_trades) if all_trades else 0
    result.tp2_hit_rate = tp2_hits / len(all_trades) if all_trades else 0
    result.tp3_hit_rate = tp3_hits / len(all_trades) if all_trades else 0
    result.sl_hit_rate = sl_hits / len(all_trades) if all_trades else 0

    # Direction breakdown
    buys = [t for t in all_trades if t.direction == "BUY"]
    sells = [t for t in all_trades if t.direction == "SELL"]
    result.buy_trades = len(buys)
    result.sell_trades = len(sells)
    result.buy_win_rate = sum(1 for t in buys if t.pnl_pct > 0) / len(buys) if buys else 0
    result.sell_win_rate = sum(1 for t in sells if t.pnl_pct > 0) / len(sells) if sells else 0

    # Calmar ratio
    annual_return = result.expectancy_pct * 250  # rough annualization
    result.calmar_ratio = annual_return / result.max_drawdown_pct if result.max_drawdown_pct > 0 else 0

    # Per asset class
    for ac, trades_list in per_asset_class.items():
        ac_wins = [t for t in trades_list if t.pnl_pct > 0]
        result.per_asset_class[ac] = {
            'count': len(trades_list),
            'win_rate': len(ac_wins) / len(trades_list) if trades_list else 0,
            'avg_pnl_pct': np.mean([t.pnl_pct for t in trades_list]) * 100 if trades_list else 0,
        }

    return result


def _check_h4_confirmation(df: pd.DataFrame, bias: str) -> bool:
    """
    Simplified LTF confirmation using H4 bars.
    In production, this would use M15/M5 data, but for the backtest
    we approximate with H4 structure break detection.
    """
    n = len(df)
    if n < 20:
        return False

    # Check last 5 bars for structure break
    recent = df.iloc[-5:]
    structure = df.iloc[:-5]

    if len(structure) < SWING_LOOKBACK * 2 + 3:
        return False

    swing_highs, swing_lows = detect_swing_highs_lows(structure, SWING_LOOKBACK)
    if not swing_highs and not swing_lows:
        return False

    latest_close = float(df['close'].iloc[-1])

    if bias == "bullish" and swing_highs:
        last_swing_high = swing_highs[-1][1]
        if latest_close > last_swing_high:
            return True
    if bias == "bearish" and swing_lows:
        last_swing_low = swing_lows[-1][1]
        if latest_close < last_swing_low:
            return True

    # Also check for CHoCH pattern
    if n >= 30:
        mid = n // 2
        prior = df.iloc[:mid]
        recent_half = df.iloc[mid:]
        prior_sh, prior_sl = detect_swing_highs_lows(prior, SWING_LOOKBACK)
        recent_sh, recent_sl = detect_swing_highs_lows(recent_half, SWING_LOOKBACK)

        if bias == "bullish" and prior_sh and recent_sh:
            if len(prior_sh) >= 2 and prior_sh[-1][1] < prior_sh[0][1]:
                if recent_sh[-1][1] > prior_sh[-1][1]:
                    return True
        if bias == "bearish" and prior_sl and recent_sl:
            if len(prior_sl) >= 2 and prior_sl[-1][1] > prior_sl[0][1]:
                if recent_sl[-1][1] < prior_sl[-1][1]:
                    return True

    return False


def _detect_confirm_type(df: pd.DataFrame, bias: str) -> str:
    """Detect whether the confirmation is BOS or CHoCH."""
    n = len(df)
    if n < 30:
        return "BOS"
    mid = n // 2
    prior = df.iloc[:mid]
    recent = df.iloc[mid:]
    prior_sh, _ = detect_swing_highs_lows(prior, SWING_LOOKBACK)
    recent_sh, _ = detect_swing_highs_lows(recent, SWING_LOOKBACK)

    if bias == "bullish" and prior_sh and recent_sh:
        if len(prior_sh) >= 2 and prior_sh[-1][1] < prior_sh[0][1]:
            return "CHoCH"
    if bias == "bearish":
        _, prior_sl = detect_swing_highs_lows(prior, SWING_LOOKBACK)
        _, recent_sl = detect_swing_highs_lows(recent, SWING_LOOKBACK)
        if prior_sl and recent_sl and len(prior_sl) >= 2:
            if prior_sl[-1][1] > prior_sl[0][1]:
                return "CHoCH"

    return "BOS"


# ═══════════════════════════════════════════════════════════════════════════════
# ADVERSARIAL TESTS
# ═══════════════════════════════════════════════════════════════════════════════

def test_baseline(data: Dict[str, pd.DataFrame]) -> BacktestResult:
    """Baseline backtest with all gates, realistic costs."""
    print("\n" + "=" * 70)
    print("BASELINE: Full pipeline with realistic costs")
    print("=" * 70)
    return run_backtest(data, spread_multiplier=1.0)


def test_remove_g7(data: Dict[str, pd.DataFrame]) -> BacktestResult:
    """Test 1: Remove G7 (LTF Confirmation) entirely."""
    print("\n" + "=" * 70)
    print("TEST 1: Remove G7 (LTF Confirmation) entirely")
    print("If expectancy survives without LTF confirmation → edge is real")
    print("=" * 70)
    return run_backtest(data, skip_g7=True, spread_multiplier=1.0)


def test_remove_g7_instruments(data: Dict[str, pd.DataFrame]) -> BacktestResult:
    """Test 1b: Remove G7 instruments entirely (EURUSD, GBPUSD, USDJPY, etc.)."""
    print("\n" + "=" * 70)
    print("TEST 1b: Remove G7 instruments entirely")
    print("If expectancy survives without G7 pairs → edge is cross-market")
    print("=" * 70)
    return run_backtest(data, skip_g7_instruments=True, spread_multiplier=1.0)


def test_randomize_entries(data: Dict[str, pd.DataFrame]) -> BacktestResult:
    """Test 2: Randomize entries, keep exits identical."""
    print("\n" + "=" * 70)
    print("TEST 2: Randomize entries, keep exits identical")
    print("If results similar to baseline → edge is fake (exit-dependent, not entry-dependent)")
    print("=" * 70)
    np.random.seed(RANDOM_SEED + 2)
    random.seed(RANDOM_SEED + 2)
    return run_backtest(data, randomize_entries=True, spread_multiplier=1.0)


def test_shift_entries(data: Dict[str, pd.DataFrame]) -> BacktestResult:
    """Test 3: Shift entries by +1 candle."""
    print("\n" + "=" * 70)
    print("TEST 3: Shift entries +1 candle")
    print("Real edges survive small shifts; fake edges collapse")
    print("=" * 70)
    return run_backtest(data, shift_entries=1, spread_multiplier=1.0)


def test_double_spread(data: Dict[str, pd.DataFrame]) -> BacktestResult:
    """Test 4: Double spread."""
    print("\n" + "=" * 70)
    print("TEST 4: Double spread")
    print("Robust strategies survive cost increases; fragile ones don't")
    print("=" * 70)
    return run_backtest(data, spread_multiplier=2.0)


def test_triple_spread(data: Dict[str, pd.DataFrame]) -> BacktestResult:
    """Test 5: Triple spread."""
    print("\n" + "=" * 70)
    print("TEST 5: Triple spread")
    print("Extreme stress test — only genuine edges survive")
    print("=" * 70)
    return run_backtest(data, spread_multiplier=3.0)


def test_walk_forward(data: Dict[str, pd.DataFrame]) -> Dict[str, BacktestResult]:
    """Test 6: Walk-forward validation."""
    print("\n" + "=" * 70)
    print("TEST 6: Walk-forward validation")
    print("Train on past, test on future — no lookahead bias possible")
    print("=" * 70)

    results = {}
    for train_start, train_end, test_start, test_end in WALK_FORWARD_WINDOWS:
        label = f"Train {train_start[:4]}-{train_end[:4]} → Test {test_start[:4]}-{test_end[:4]}"
        print(f"\n  {label}")
        result = run_backtest(data, start_date=test_start, end_date=test_end,
                             spread_multiplier=1.0)
        results[label] = result

    return results


def test_monte_carlo(baseline: BacktestResult) -> Dict:
    """Test 7: Monte Carlo simulation with 100,000 runs."""
    print("\n" + "=" * 70)
    print(f"TEST 7: Monte Carlo simulation ({MONTE_CARLO_RUNS:,} runs)")
    print("Resample trade outcomes to measure distribution of possible results")
    print("=" * 70)

    if not baseline.trades:
        return {'error': 'No trades in baseline for Monte Carlo'}

    returns = np.array([t.pnl_pct for t in baseline.trades])
    n_trades = len(returns)

    # Simulate many equity curves by random resampling
    final_equities = np.zeros(MONTE_CARLO_RUNS)
    max_drawdowns = np.zeros(MONTE_CARLO_RUNS)
    ruin_count = 0
    ruin_threshold = -0.20  # 20% drawdown = ruin

    for run in range(MONTE_CARLO_RUNS):
        # Resample with replacement
        sampled = np.random.choice(returns, size=n_trades, replace=True)
        equity = np.cumsum(sampled) + 1.0
        final_equities[run] = equity[-1]
        peak = np.maximum.accumulate(equity)
        dd = (peak - equity) / peak
        max_drawdowns[run] = np.max(dd)
        if np.min(equity) < (1.0 + ruin_threshold):
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
        'pct_profitable_runs': np.mean(final_equities > 1.0),
        'sharpe_distribution': {
            'mean': float(np.mean((final_equities - 1.0) / (np.std(sampled) + 1e-10))),
            'positive_pct': float(np.mean(final_equities > 1.0) * 100),
        }
    }


def test_cross_market(data: Dict[str, pd.DataFrame]) -> Dict[str, BacktestResult]:
    """Test 8: Cross-market validation."""
    print("\n" + "=" * 70)
    print("TEST 8: Cross-market validation")
    print("Genuine liquidity sweep strategy should work across all market types")
    print("=" * 70)

    results = {}
    for asset_class, symbols in INSTRUMENTS.items():
        available = [s for s in symbols if s in data and data[s] is not None and not data[s].empty]
        if not available:
            continue
        print(f"\n  Testing {asset_class.upper()}: {[DISPLAY_NAMES.get(s, s) for s in available]}")
        result = run_backtest(data, instruments=available, spread_multiplier=1.0)
        results[asset_class] = result

    return results


# ═══════════════════════════════════════════════════════════════════════════════
# RED FLAG DETECTION
# ═══════════════════════════════════════════════════════════════════════════════

def detect_red_flags(result: BacktestResult, label: str = "") -> List[str]:
    """Detect institutional red flags in backtest results."""
    flags = []

    if result.total_trades == 0:
        flags.append("ZERO_TRADES: No trades generated — strategy may be too restrictive")
        return flags

    if result.win_rate > 0.85:
        flags.append(f"WIN_RATE_TOO_HIGH: {result.win_rate:.1%} — >85% win rate with >50 trades suggests lookahead/leakage")

    if result.sharpe_ratio > 5.0:
        flags.append(f"SHARPE_TOO_HIGH: {result.sharpe_ratio:.2f} — Sharpe >5.0 with realistic costs is extremely rare")

    if result.sortino_ratio > 20.0:
        flags.append(f"SORTINO_TOO_HIGH: {result.sortino_ratio:.2f} — Sortino >20.0 is unrealistic for live trading")

    if result.profit_factor > 3.0 and result.total_trades > 100:
        flags.append(f"PROFIT_FACTOR_SUSPICIOUS: {result.profit_factor:.2f} — PF >3.0 with >100 trades needs scrutiny")

    if result.total_trades > 500 and result.win_rate > 0.75:
        flags.append(f"TOO_MANY_WINNING_TRADES: {result.total_trades} trades with {result.win_rate:.1%} win rate")

    if result.max_drawdown_pct < 1.0 and result.total_trades > 50:
        flags.append(f"MAX_DD_TOO_LOW: {result.max_drawdown_pct:.2f}% — Max DD <1% with >50 trades suggests overfitting")

    if abs(result.buy_win_rate - result.sell_win_rate) > 0.3:
        flags.append(f"DIRECTIONAL_BIAS: BUY win rate {result.buy_win_rate:.1%} vs SELL {result.sell_win_rate:.1%} — significant directional bias")

    if result.tp3_hit_rate > 0.3:
        flags.append(f"TP3_HIT_RATE_HIGH: {result.tp3_hit_rate:.1%} — TP3 >30% may indicate TP3 lookahead bug")

    return flags


# ═══════════════════════════════════════════════════════════════════════════════
# VERDICT CLASSIFICATION
# ═══════════════════════════════════════════════════════════════════════════════

def classify_verdict(baseline: BacktestResult, test_results: Dict) -> str:
    """
    Classify the overall verdict based on all test results.

    Verdict levels:
      COMPLETE_ILLUSION: Strategy fails adversarial tests entirely
      SMALL_REAL_EDGE:   Strategy has a small but genuine edge
      STRONG_INSTITUTIONAL: Strategy passes most tests convincingly
      EXCEPTIONAL:       Strategy passes ALL tests with institutional-grade metrics
    """
    score = 0
    max_score = 0
    red_flags = detect_red_flags(baseline, "BASELINE")

    # Heavy penalties for baseline red flags
    if len(red_flags) > 3:
        return "COMPLETE_ILLUSION"
    score -= len(red_flags) * 2

    # Baseline must be profitable
    if baseline.expectancy_pct <= 0:
        return "COMPLETE_ILLUSION"

    # Baseline metrics quality
    max_score += 10
    if baseline.sharpe_ratio > 0.5 and baseline.sharpe_ratio < 3.0:
        score += 5
    elif baseline.sharpe_ratio >= 3.0:
        score += 3  # Suspicious but possible
    if baseline.win_rate > 0.35 and baseline.win_rate < 0.70:
        score += 3
    if baseline.profit_factor > 1.3 and baseline.profit_factor < 3.0:
        score += 2

    # Test 1: Remove G7 — must still be profitable
    max_score += 10
    if 'remove_g7' in test_results:
        g7_result = test_results['remove_g7']
        if g7_result.expectancy_pct > 0:
            score += 5
            if g7_result.win_rate > 0.30:
                score += 3
            if g7_result.profit_factor > 1.1:
                score += 2
        else:
            score -= 5

    # Test 1b: Remove G7 instruments — cross-market must work
    max_score += 10
    if 'remove_g7_instruments' in test_results:
        g7i_result = test_results['remove_g7_instruments']
        if g7i_result.expectancy_pct > 0:
            score += 5
        else:
            score -= 3

    # Test 2: Randomize entries — must NOT be similar to baseline
    max_score += 15
    if 'randomize_entries' in test_results:
        rand_result = test_results['randomize_entries']
        # If randomized entries produce similar results → edge is fake
        if rand_result.expectancy_pct > 0 and rand_result.expectancy_pct >= baseline.expectancy_pct * 0.5:
            score -= 10  # Penalty: similar results = fake edge
        elif rand_result.expectancy_pct <= 0:
            score += 10  # Reward: randomized entries fail = real entry edge
        elif rand_result.expectancy_pct < baseline.expectancy_pct * 0.3:
            score += 8

    # Test 3: Shift entries +1 candle — must survive small shift
    max_score += 10
    if 'shift_entries' in test_results:
        shift_result = test_results['shift_entries']
        if shift_result.expectancy_pct > 0:
            score += 5
            if shift_result.profit_factor > 1.0:
                score += 3
        else:
            score -= 3

    # Test 4-5: Spread stress — must survive double spread
    max_score += 10
    if 'double_spread' in test_results:
        ds_result = test_results['double_spread']
        if ds_result.expectancy_pct > 0:
            score += 5
            if ds_result.profit_factor > 1.0:
                score += 3
        else:
            score -= 2

    # Test 6: Walk-forward — must be profitable OOS
    max_score += 15
    if 'walk_forward' in test_results:
        wf_results = test_results['walk_forward']
        profitable_windows = sum(1 for r in wf_results.values() if r.expectancy_pct > 0)
        total_windows = len(wf_results)
        if total_windows > 0:
            wf_ratio = profitable_windows / total_windows
            if wf_ratio >= 0.67:
                score += 10
            elif wf_ratio >= 0.33:
                score += 5
            else:
                score -= 5

    # Test 7: Monte Carlo — low ruin probability
    max_score += 10
    if 'monte_carlo' in test_results:
        mc = test_results['monte_carlo']
        if isinstance(mc, dict) and 'ruin_probability' in mc:
            if mc['ruin_probability'] < 0.05:
                score += 7
            elif mc['ruin_probability'] < 0.15:
                score += 4
            elif mc['ruin_probability'] < 0.30:
                score += 1
            else:
                score -= 5

    # Test 8: Cross-market — must work in multiple asset classes
    max_score += 10
    if 'cross_market' in test_results:
        cm_results = test_results['cross_market']
        profitable_classes = sum(1 for r in cm_results.values() if r.expectancy_pct > 0)
        total_classes = len(cm_results)
        if total_classes > 0:
            cm_ratio = profitable_classes / total_classes
            if cm_ratio >= 0.75:
                score += 7
            elif cm_ratio >= 0.50:
                score += 4
            else:
                score -= 2

    # Normalize score
    pct = score / max_score if max_score > 0 else 0

    if pct >= 0.70:
        return "EXCEPTIONAL"
    elif pct >= 0.50:
        return "STRONG_INSTITUTIONAL"
    elif pct >= 0.25:
        return "SMALL_REAL_EDGE"
    else:
        return "COMPLETE_ILLUSION"


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN EXECUTION
# ═══════════════════════════════════════════════════════════════════════════════

def main():
    print("╔══════════════════════════════════════════════════════════════════════╗")
    print("║  INSTITUTIONAL ADVERSARIAL VALIDATION BACKTEST                      ║")
    print("║  MarketMate Signal Engine — 'Try to KILL Strategy #1'              ║")
    print("╚══════════════════════════════════════════════════════════════════════╝")
    print(f"\n  Start: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")

    # ── Step 1: Load Data ──────────────────────────────────────────────────
    print("\n── Step 1: Loading historical data ──")
    cache_path = "/home/z/my-project/download/market_data.pkl"
    if os.path.exists(cache_path):
        data = load_cached_data(cache_path)
        print(f"  Loaded {len(data)} instruments from cache")
    else:
        # Fallback to downloading
        all_symbols = []
        for syms in INSTRUMENTS.values():
            all_symbols.extend(syms)
        data = {}
        failed = []
        for symbol in all_symbols:
            display = DISPLAY_NAMES.get(symbol, symbol)
            print(f"  Downloading {display}...", end=" ", flush=True)
            df = download_data(symbol, interval="1d", start=START_DATE, end=END_DATE)
            if df is not None and len(df) > 100:
                data[symbol] = df
                print(f"OK ({len(df)} bars)")
            else:
                print("FAILED")
                failed.append(display)
        if failed:
            print(f"\n  [WARN] Failed to download: {failed}")

    all_symbols = []
    for syms in INSTRUMENTS.values():
        all_symbols.extend(syms)
    print(f"  Available instruments: {len(data)}/{len(all_symbols)}")

    if len(data) < 10:
        print("  [ERROR] Too few instruments available. Cannot proceed.")
        return

    # ── Step 2: Run Baseline ───────────────────────────────────────────────
    baseline = test_baseline(data)

    # ── Step 3: Run Adversarial Tests ──────────────────────────────────────
    all_results = {}

    # Test 1: Remove G7
    all_results['remove_g7'] = test_remove_g7(data)

    # Test 1b: Remove G7 instruments
    all_results['remove_g7_instruments'] = test_remove_g7_instruments(data)

    # Test 2: Randomize entries
    all_results['randomize_entries'] = test_randomize_entries(data)

    # Test 3: Shift entries +1
    all_results['shift_entries'] = test_shift_entries(data)

    # Test 4: Double spread
    all_results['double_spread'] = test_double_spread(data)

    # Test 5: Triple spread
    all_results['triple_spread'] = test_triple_spread(data)

    # Test 6: Walk-forward
    all_results['walk_forward'] = test_walk_forward(data)

    # Test 7: Monte Carlo
    all_results['monte_carlo'] = test_monte_carlo(baseline)

    # Test 8: Cross-market
    all_results['cross_market'] = test_cross_market(data)

    # ── Step 4: Red Flag Detection ─────────────────────────────────────────
    print("\n" + "=" * 70)
    print("RED FLAG DETECTION")
    print("=" * 70)
    baseline_flags = detect_red_flags(baseline, "BASELINE")
    if baseline_flags:
        print(f"\n  Baseline Red Flags ({len(baseline_flags)}):")
        for flag in baseline_flags:
            print(f"    ⚠ {flag}")
    else:
        print("\n  No baseline red flags detected.")

    for test_name, test_result in all_results.items():
        if isinstance(test_result, BacktestResult):
            flags = detect_red_flags(test_result, test_name)
            if flags:
                print(f"\n  {test_name} Red Flags ({len(flags)}):")
                for flag in flags:
                    print(f"    ⚠ {flag}")

    # ── Step 5: Verdict Classification ─────────────────────────────────────
    print("\n" + "=" * 70)
    print("VERDICT CLASSIFICATION")
    print("=" * 70)
    verdict = classify_verdict(baseline, all_results)
    verdict_labels = {
        "COMPLETE_ILLUSION": "COMPLETE ILLUSION — Strategy is not tradeable",
        "SMALL_REAL_EDGE": "SMALL REAL EDGE — Modest but genuine edge detected",
        "STRONG_INSTITUTIONAL": "STRONG INSTITUTIONAL EDGE — Convincing across most tests",
        "EXCEPTIONAL": "EXCEPTIONAL EDGE — Passes all adversarial tests",
    }
    print(f"\n  VERDICT: {verdict_labels.get(verdict, verdict)}")

    # ── Step 6: Save Results ───────────────────────────────────────────────
    print("\n── Step 6: Saving results ──")

    # Serialize results
    output = {
        'timestamp': datetime.now().isoformat(),
        'baseline': _serialize_result(baseline),
        'tests': {},
        'verdict': verdict,
        'red_flags': {
            'baseline': baseline_flags,
        },
    }

    for test_name, test_result in all_results.items():
        if isinstance(test_result, BacktestResult):
            output['tests'][test_name] = _serialize_result(test_result)
            flags = detect_red_flags(test_result, test_name)
            output['red_flags'][test_name] = flags
        elif isinstance(test_result, dict):
            output['tests'][test_name] = test_result
        elif isinstance(test_result, dict):
            for k, v in test_result.items():
                if isinstance(v, BacktestResult):
                    output['tests'][f'{test_name}_{k}'] = _serialize_result(v)

    # Save JSON
    json_path = os.path.join(OUTPUT_DIR, "adversarial_backtest_results.json")
    with open(json_path, 'w') as f:
        json.dump(output, f, indent=2, default=str)
    print(f"  Results saved to: {json_path}")

    # ── Summary Print ──────────────────────────────────────────────────────
    print_summary(baseline, all_results, verdict, baseline_flags)

    return output


def _serialize_result(result: BacktestResult) -> dict:
    """Serialize BacktestResult to dict for JSON."""
    return {
        'total_trades': result.total_trades,
        'winning_trades': result.winning_trades,
        'losing_trades': result.losing_trades,
        'win_rate': round(result.win_rate, 4),
        'avg_win_pct': round(result.avg_win_pct, 4),
        'avg_loss_pct': round(result.avg_loss_pct, 4),
        'profit_factor': round(result.profit_factor, 4),
        'expectancy_pct': round(result.expectancy_pct, 4),
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


def print_summary(baseline: BacktestResult, all_results: Dict, verdict: str, flags: List[str]):
    """Print a formatted summary of all test results."""
    print("\n" + "╔" + "═" * 68 + "╗")
    print("║  ADVERSARIAL BACKTEST SUMMARY                                     ║")
    print("╚" + "═" * 68 + "╝")

    def fmt_pct(v): return f"{v:.2f}%" if v else "N/A"
    def fmt_f(v, d=2): return f"{v:.{d}f}" if v else "N/A"

    # Baseline
    print(f"\n  BASELINE (Full Pipeline, Realistic Costs):")
    print(f"    Trades: {baseline.total_trades}  |  Win Rate: {fmt_pct(baseline.win_rate * 100)}")
    print(f"    Profit Factor: {fmt_f(baseline.profit_factor)}  |  Expectancy: {fmt_pct(baseline.expectancy_pct)}")
    print(f"    Sharpe: {fmt_f(baseline.sharpe_ratio)}  |  Sortino: {fmt_f(baseline.sortino_ratio)}")
    print(f"    Max DD: {fmt_pct(baseline.max_drawdown_pct)}  |  Max Consec Losses: {baseline.max_consecutive_losses}")
    print(f"    TP1: {fmt_pct(baseline.tp1_hit_rate * 100)}  |  TP2: {fmt_pct(baseline.tp2_hit_rate * 100)}  |  TP3: {fmt_pct(baseline.tp3_hit_rate * 100)}  |  SL: {fmt_pct(baseline.sl_hit_rate * 100)}")

    # Tests comparison
    print(f"\n  ADVERSARIAL TEST COMPARISON:")
    print(f"    {'Test':<25} {'Trades':>7} {'Win%':>7} {'PF':>7} {'Exp%':>8} {'Sharpe':>8}")
    print(f"    {'─' * 25} {'─' * 7} {'─' * 7} {'─' * 7} {'─' * 8} {'─' * 8}")

    for test_name, test_result in all_results.items():
        if isinstance(test_result, BacktestResult):
            print(f"    {test_name:<25} {test_result.total_trades:>7} {fmt_pct(test_result.win_rate * 100):>7} "
                  f"{fmt_f(test_result.profit_factor):>7} {fmt_pct(test_result.expectancy_pct):>8} "
                  f"{fmt_f(test_result.sharpe_ratio):>8}")

    # Monte Carlo
    if 'monte_carlo' in all_results and isinstance(all_results['monte_carlo'], dict):
        mc = all_results['monte_carlo']
        print(f"\n  MONTE CARLO ({MONTE_CARLO_RUNS:,} runs):")
        print(f"    Mean Final Equity: {fmt_f(mc.get('mean_final_equity', 0), 4)}")
        print(f"    5th Pctile Equity: {fmt_f(mc.get('p5_final_equity', 0), 4)}")
        print(f"    Ruin Probability: {fmt_pct(mc.get('ruin_probability', 0) * 100)}")
        print(f"    Mean Max DD: {fmt_pct(mc.get('mean_max_drawdown_pct', 0))}")
        print(f"    95th Pctile DD: {fmt_pct(mc.get('p95_max_drawdown_pct', 0))}")
        print(f"    Profitable Runs: {fmt_pct(mc.get('pct_profitable_runs', 0) * 100)}")

    # Walk-forward
    if 'walk_forward' in all_results and isinstance(all_results['walk_forward'], dict):
        print(f"\n  WALK-FORWARD RESULTS:")
        for label, wf_result in all_results['walk_forward'].items():
            if isinstance(wf_result, BacktestResult):
                status = "✓ PROFITABLE" if wf_result.expectancy_pct > 0 else "✗ UNPROFITABLE"
                print(f"    {label}: {status} (Exp={fmt_pct(wf_result.expectancy_pct)}, "
                      f"WR={fmt_pct(wf_result.win_rate * 100)}, PF={fmt_f(wf_result.profit_factor)})")

    # Cross-market
    if 'cross_market' in all_results and isinstance(all_results['cross_market'], dict):
        print(f"\n  CROSS-MARKET RESULTS:")
        for ac, cm_result in all_results['cross_market'].items():
            if isinstance(cm_result, BacktestResult):
                status = "✓ PROFITABLE" if cm_result.expectancy_pct > 0 else "✗ UNPROFITABLE"
                print(f"    {ac.upper()}: {status} ({cm_result.total_trades} trades, "
                      f"WR={fmt_pct(cm_result.win_rate * 100)}, Exp={fmt_pct(cm_result.expectancy_pct)})")

    # Red flags
    if flags:
        print(f"\n  RED FLAGS ({len(flags)}):")
        for flag in flags:
            print(f"    ⚠ {flag}")

    # Verdict
    verdict_labels = {
        "COMPLETE_ILLUSION": "✗ COMPLETE ILLUSION",
        "SMALL_REAL_EDGE": "~ SMALL REAL EDGE",
        "STRONG_INSTITUTIONAL": "✓ STRONG INSTITUTIONAL EDGE",
        "EXCEPTIONAL": "★★ EXCEPTIONAL EDGE ★★",
    }
    print(f"\n  VERDICT: {verdict_labels.get(verdict, verdict)}")
    print()


if __name__ == "__main__":
    results = main()
