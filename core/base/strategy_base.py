"""
Base class fix: All strategies MUST set entry_time on signals.
This is critical for trade execution.
"""

from __future__ import annotations
from dataclasses import dataclass, field
from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime
import numpy as np
import pandas as pd


@dataclass
class TradeSignal:
    """A single trade signal produced by a strategy."""
    symbol: str
    direction: str
    entry_price: float
    stop_loss: float
    take_profit: float
    tp2: float = 0.0
    tp3: float = 0.0
    entry_time: Optional[datetime] = None
    entry_bar: int = -1              # Bar index for fast lookup
    strategy_id: str = ""
    confidence: float = 0.0
    rr_ratio: float = 0.0
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def risk_distance(self) -> float:
        return abs(self.entry_price - self.stop_loss)

    @property
    def reward_distance(self) -> float:
        if self.direction == "BUY":
            return self.take_profit - self.entry_price
        return self.entry_price - self.take_profit


@dataclass
class TradeResult:
    signal: TradeSignal
    exit_price: float
    exit_time: Optional[datetime]
    exit_reason: str
    pnl_r: float
    pnl_pct: float
    duration_bars: int
    spread_cost: float = 0.0
    commission: float = 0.0

    @property
    def is_winner(self) -> bool:
        return self.pnl_r > 0


@dataclass
class StrategyResult:
    strategy_id: str
    symbol: str
    trades: List[TradeResult]
    parameters: Dict[str, Any]

    @property
    def total_trades(self) -> int:
        return len(self.trades)

    @property
    def win_rate(self) -> float:
        if not self.trades:
            return 0.0
        return sum(1 for t in self.trades if t.is_winner) / len(self.trades)

    @property
    def profit_factor(self) -> float:
        wins = sum(t.pnl_r for t in self.trades if t.is_winner)
        losses = abs(sum(t.pnl_r for t in self.trades if not t.is_winner))
        return wins / losses if losses > 0 else 0.0

    @property
    def sharpe_ratio(self) -> float:
        if len(self.trades) < 2:
            return 0.0
        rv = [t.pnl_r for t in self.trades]
        std = np.std(rv)
        return np.mean(rv) / std * np.sqrt(252) if std > 0 else 0.0

    @property
    def max_drawdown(self) -> float:
        if not self.trades:
            return 0.0
        rv = [t.pnl_r for t in self.trades]
        cum = np.cumsum(rv)
        peak = np.maximum.accumulate(cum)
        dd = peak - cum
        return float(np.max(dd))

    @property
    def avg_r(self) -> float:
        if not self.trades:
            return 0.0
        return np.mean([t.pnl_r for t in self.trades])

    def to_dict(self) -> Dict:
        return {
            "strategy_id": self.strategy_id,
            "symbol": self.symbol,
            "total_trades": self.total_trades,
            "win_rate": round(self.win_rate, 4),
            "profit_factor": round(self.profit_factor, 4),
            "sharpe_ratio": round(self.sharpe_ratio, 4),
            "max_drawdown": round(self.max_drawdown, 4),
            "avg_r": round(self.avg_r, 4),
            "parameters": self.parameters,
        }


class Strategy:
    """Base class for all strategies."""

    STRATEGY_ID: str = "BASE"
    STRATEGY_NAME: str = "Base Strategy"
    STRATEGY_TYPE: str = "generic"

    def __init__(self, params: Optional[Dict] = None):
        self.params = params or self.default_params()

    @classmethod
    def default_params(cls) -> Dict[str, Any]:
        return {}

    @classmethod
    def param_ranges(cls) -> Dict[str, Tuple]:
        return {}

    def generate_signals(self, df: pd.DataFrame, symbol: str = "") -> List[TradeSignal]:
        raise NotImplementedError

    def _sig(self, symbol, direction, entry_price, sl, tp, df, bar_idx,
             tp2=0.0, tp3=0.0, rr=0.0, strategy_id="", confidence=0.0, metadata=None):
        """Helper to create a TradeSignal with entry_time and bar_idx always set."""
        entry_time = df.index[bar_idx] if bar_idx < len(df) else None
        return TradeSignal(
            symbol=symbol, direction=direction,
            entry_price=entry_price, stop_loss=sl, take_profit=tp,
            tp2=tp2, tp3=tp3,
            entry_time=entry_time, entry_bar=bar_idx,
            strategy_id=strategy_id or self.STRATEGY_ID,
            confidence=confidence, rr_ratio=rr,
            metadata=metadata or {}
        )

    # ─── Utility helpers ─────────────────────────────────────────────

    @staticmethod
    def ema(series, period):
        result = np.empty_like(series, dtype=float)
        mult = 2.0 / (period + 1)
        result[0] = series[0]
        for i in range(1, len(series)):
            result[i] = series[i] * mult + result[i-1] * (1 - mult)
        return result

    @staticmethod
    def sma(series, period):
        result = np.full_like(series, np.nan, dtype=float)
        for i in range(period - 1, len(series)):
            result[i] = np.mean(series[i - period + 1:i + 1])
        return result

    @staticmethod
    def rsi(closes, period=14):
        n = len(closes)
        result = np.full(n, 50.0)
        if n < period + 1:
            return result
        deltas = np.diff(closes)
        gains = np.where(deltas > 0, deltas, 0.0)
        losses = np.where(deltas < 0, -deltas, 0.0)
        avg_gain = np.mean(gains[:period])
        avg_loss = np.mean(losses[:period])
        for i in range(period, n - 1):
            avg_gain = (avg_gain * (period - 1) + gains[i]) / period
            avg_loss = (avg_loss * (period - 1) + losses[i]) / period
            if avg_loss > 0:
                rs = avg_gain / avg_loss
                result[i + 1] = 100.0 - (100.0 / (1.0 + rs))
            else:
                result[i + 1] = 100.0
        return result

    @staticmethod
    def atr(highs, lows, closes, period=14):
        n = len(highs)
        result = np.full(n, np.nan, dtype=float)
        tr = np.zeros(n)
        tr[0] = highs[0] - lows[0]
        for i in range(1, n):
            tr[i] = max(highs[i] - lows[i], abs(highs[i] - closes[i-1]), abs(lows[i] - closes[i-1]))
        if n > period:
            result[period] = np.mean(tr[1:period+1])
            for i in range(period + 1, n):
                result[i] = (result[i-1] * (period - 1) + tr[i]) / period
        return result

    @staticmethod
    def bollinger_bands(closes, period=20, std_mult=2.0):
        n = len(closes)
        upper = np.full(n, np.nan)
        middle = np.full(n, np.nan)
        lower = np.full(n, np.nan)
        for i in range(period - 1, n):
            window = closes[i - period + 1:i + 1]
            mean = np.mean(window)
            std = np.std(window)
            middle[i] = mean
            upper[i] = mean + std_mult * std
            lower[i] = mean - std_mult * std
        return upper, middle, lower

    @staticmethod
    def macd(closes, fast=12, slow=26, signal=9):
        ema_fast = Strategy.ema(closes, fast)
        ema_slow = Strategy.ema(closes, slow)
        macd_line = ema_fast - ema_slow
        signal_line = Strategy.ema(macd_line, signal)
        histogram = macd_line - signal_line
        return macd_line, signal_line, histogram

    @staticmethod
    def stochastic(highs, lows, closes, k_period=14, d_period=3):
        n = len(closes)
        k = np.full(n, 50.0)
        for i in range(k_period - 1, n):
            h = np.max(highs[i - k_period + 1:i + 1])
            l = np.min(lows[i - k_period + 1:i + 1])
            if h != l:
                k[i] = (closes[i] - l) / (h - l) * 100
        d = Strategy.sma(k, d_period)
        return k, d

    @staticmethod
    def heikin_ashi(df):
        ha = pd.DataFrame(index=df.index)
        closes = df['close'].values
        opens = df['open'].values
        highs = df['high'].values
        lows = df['low'].values
        ha_close = (opens + highs + lows + closes) / 4
        ha_open = np.zeros(len(df))
        ha_open[0] = (opens[0] + closes[0]) / 2
        for i in range(1, len(df)):
            ha_open[i] = (ha_open[i-1] + ha_close[i-1]) / 2
        ha_high = np.maximum(highs, np.maximum(ha_open, ha_close))
        ha_low = np.minimum(lows, np.minimum(ha_open, ha_close))
        ha['open'] = ha_open; ha['high'] = ha_high; ha['low'] = ha_low
        ha['close'] = ha_close
        ha['volume'] = df['volume'].values if 'volume' in df.columns else 0
        return ha

    @staticmethod
    def find_swing_points(highs, lows, lookback=5):
        n = len(highs)
        sh_i, sh_p, sl_i, sl_p = [], [], [], []
        for i in range(lookback, n - lookback):
            is_sh = all(highs[i] >= highs[j] for j in range(max(0,i-lookback), min(n,i+lookback+1)) if j != i)
            if is_sh:
                sh_i.append(i); sh_p.append(highs[i])
            is_sl = all(lows[i] <= lows[j] for j in range(max(0,i-lookback), min(n,i+lookback+1)) if j != i)
            if is_sl:
                sl_i.append(i); sl_p.append(lows[i])
        return np.array(sh_i), np.array(sh_p), np.array(sl_i), np.array(sl_p)
