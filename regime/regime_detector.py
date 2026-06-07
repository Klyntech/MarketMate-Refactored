"""
Regime Detection Engine
═══════════════════════
Classifies market conditions into regimes that determine
which strategies should be active.

Regimes:
  TRENDING   — Strong directional move (gap fades DIE here)
  RANGING    — Mean-reverting (gap fades SURVIVE here)
  HIGH_VOL   — Elevated volatility (wider stops needed)
  LOW_VOL    — Compressed volatility (tighter stops possible)
  RISK_ON    — Equities/crypto rising, safe havens falling
  RISK_OFF   — Inverse: flight to safety

The key insight from validation:
  MM-002 works ONLY in RANGING/LOW_VOL regimes
  8-Gate SMC works across ALL regimes but best in TRENDING
  Regime detection is the HIGHEST ROI project because
  a mediocre strategy becomes excellent when deployed
  only in its favorable regime.

Usage:
  detector = RegimeDetector()
  regime = detector.classify(df, current_bar_index)
  if regime.is_favorable_for("MM-002"):
      # Allow signal generation
"""

import numpy as np
import pandas as pd
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


@dataclass
class MarketRegime:
    """Current market regime classification."""
    primary: str          # TRENDING, RANGING, MIXED
    volatility: str       # HIGH_VOL, LOW_VOL, NORMAL_VOL
    risk_appetite: str    # RISK_ON, RISK_OFF, RISK_NEUTRAL
    trend_strength: float # 0.0 to 3.0+
    volatility_rank: float # 0.0 to 1.0
    confidence: float     # 0.0 to 1.0

    @property
    def label(self) -> str:
        parts = [self.primary]
        if self.volatility != "NORMAL_VOL":
            parts.append(self.volatility)
        if self.risk_appetite != "RISK_NEUTRAL":
            parts.append(self.risk_appetite)
        return " + ".join(parts)

    def is_favorable_for(self, strategy_type: str) -> bool:
        """Determine if current regime is favorable for a strategy type."""
        favorable_map = {
            # Mean reversion strategies (gap fade, bounce)
            "mean_reversion": self.primary in ["RANGING", "MIXED"] and self.volatility in ["LOW_VOL", "NORMAL_VOL"],
            # Trend-following strategies
            "trend": self.primary == "TRENDING" and self.volatility in ["NORMAL_VOL", "HIGH_VOL"],
            # Breakout strategies
            "breakout": self.volatility == "LOW_VOL",  # Best after compression
            # Reversal strategies
            "reversal": self.primary in ["RANGING", "MIXED"],
            # SMC/structural strategies — work in all regimes
            "smc": True,
        }
        return favorable_map.get(strategy_type, False)

    def recommended_risk_mult(self) -> float:
        """Position sizing multiplier based on regime."""
        mult = 1.0
        if self.volatility == "HIGH_VOL":
            mult *= 0.5
        elif self.volatility == "LOW_VOL":
            mult *= 1.2
        if self.primary == "RANGING":
            mult *= 1.0  # Neutral for mean reversion
        elif self.primary == "TRENDING":
            mult *= 0.8  # Trending = more likely to violate S/R
        if self.confidence < 0.5:
            mult *= 0.7  # Low confidence = reduce size
        return round(max(0.2, min(mult, 1.5)), 2)


class RegimeDetector:
    """
    Multi-factor regime detection using:
    1. ADX-derived trend strength
    2. ATR percentile for volatility regime
    3. Cross-asset correlation for risk appetite
    """

    def __init__(self, config: Dict = None):
        self.config = config or self.default_config()

    @staticmethod
    def default_config() -> Dict:
        return {
            "trend_lookback": 20,       # Bars for trend strength
            "vol_lookback": 60,         # Bars for volatility percentile
            "adx_period": 14,           # ADX calculation period
            "ema_period": 50,           # Trend EMA period
            "trending_threshold": 1.5,  # Trend strength above this = TRENDING
            "ranging_threshold": 0.5,   # Trend strength below this = RANGING
            "high_vol_percentile": 0.75,
            "low_vol_percentile": 0.25,
        }

    def classify(self, df: pd.DataFrame, current_idx: int = None) -> MarketRegime:
        """
        Classify the current market regime.

        Args:
            df: OHLCV DataFrame with DatetimeIndex
            current_idx: Bar index to classify at. If None, uses last bar.

        Returns:
            MarketRegime with classification
        """
        if current_idx is None:
            current_idx = len(df) - 1

        cfg = self.config
        closes = df['close'].values
        highs = df['high'].values
        lows = df['low'].values

        min_bars = max(cfg['trend_lookback'], cfg['vol_lookback'], cfg['adx_period'] * 2) + 10
        if current_idx < min_bars:
            return MarketRegime("MIXED", "NORMAL_VOL", "RISK_NEUTRAL", 0, 0.5, 0.0)

        # ── 1. Trend Strength (ADX-like) ───────────────────────────
        trend_strength = self._compute_trend_strength(closes, highs, lows, current_idx)

        # ── 2. Volatility Regime ────────────────────────────────────
        volatility_rank = self._compute_volatility_rank(highs, lows, closes, current_idx)

        # ── 3. Primary Classification ──────────────────────────────
        if trend_strength > cfg['trending_threshold']:
            primary = "TRENDING"
        elif trend_strength < cfg['ranging_threshold']:
            primary = "RANGING"
        else:
            primary = "MIXED"

        # ── 4. Volatility Classification ────────────────────────────
        if volatility_rank > cfg['high_vol_percentile']:
            vol_label = "HIGH_VOL"
        elif volatility_rank < cfg['low_vol_percentile']:
            vol_label = "LOW_VOL"
        else:
            vol_label = "NORMAL_VOL"

        # ── 5. Risk Appetite (simplified: price vs EMA direction) ───
        ema = self._ema(closes, cfg['ema_period'])
        risk_appetite = "RISK_NEUTRAL"
        if current_idx >= cfg['ema_period']:
            price_vs_ema = (closes[current_idx] - ema[current_idx]) / ema[current_idx]
            roc = (closes[current_idx] - closes[current_idx - cfg['trend_lookback']]) / closes[current_idx - cfg['trend_lookback']]

            if price_vs_ema > 0.01 and roc > 0.02:
                risk_appetite = "RISK_ON"
            elif price_vs_ema < -0.01 and roc < -0.02:
                risk_appetite = "RISK_OFF"

        # ── 6. Confidence ──────────────────────────────────────────
        # Higher confidence when trend and vol agree, lower when they conflict
        confidence = 0.5
        if primary == "TRENDING" and vol_label in ["NORMAL_VOL", "HIGH_VOL"]:
            confidence = 0.8
        elif primary == "RANGING" and vol_label in ["LOW_VOL", "NORMAL_VOL"]:
            confidence = 0.8
        elif primary == "MIXED":
            confidence = 0.3
        elif primary == "TRENDING" and vol_label == "LOW_VOL":
            confidence = 0.4  # Unusual: trending but low vol?

        return MarketRegime(
            primary=primary,
            volatility=vol_label,
            risk_appetite=risk_appetite,
            trend_strength=round(trend_strength, 3),
            volatility_rank=round(volatility_rank, 3),
            confidence=round(confidence, 2),
        )

    def classify_series(self, df: pd.DataFrame) -> pd.Series:
        """Classify regime for every bar in the DataFrame."""
        regimes = []
        for i in range(len(df)):
            if i < 100:
                regimes.append("UNCLASSIFIED")
            else:
                r = self.classify(df, i)
                regimes.append(r.label)
        return pd.Series(regimes, index=df.index, name="regime")

    def regime_performance_table(self, df: pd.DataFrame, trades: List[Dict]) -> pd.DataFrame:
        """
        Build a performance table showing strategy performance by regime.
        Critical for determining when a strategy should be active.
        """
        regime_series = self.classify_series(df)

        # Map trades to regimes
        regime_trades = {}
        for t in trades:
            date = pd.Timestamp(t['entry_date'])
            mask = df.index <= date
            if not mask.any():
                continue
            closest_idx = df.index[mask][-1]
            regime = regime_series.get(closest_idx, "UNCLASSIFIED")

            if regime not in regime_trades:
                regime_trades[regime] = []
            regime_trades[regime].append(t['net_pnl_r'] if 'net_pnl_r' in t else t.get('pnl_r', 0))

        rows = []
        for regime, pnls in sorted(regime_trades.items()):
            if not pnls:
                continue
            wins = [p for p in pnls if p > 0]
            losses = [abs(p) for p in pnls if p < 0]
            pf = sum(wins) / sum(losses) if sum(losses) > 0 else 0
            wr = len(wins) / len(pnls)
            avg_r = np.mean(pnls)
            cum_r = sum(pnls)

            rows.append({
                "regime": regime,
                "trades": len(pnls),
                "pf": round(pf, 3),
                "wr": round(wr, 3),
                "avg_r": round(avg_r, 4),
                "cum_r": round(cum_r, 2),
            })

        return pd.DataFrame(rows)

    # ── Internal Helpers ────────────────────────────────────────────

    def _compute_trend_strength(self, closes, highs, lows, idx) -> float:
        """Compute ADX-like trend strength."""
        cfg = self.config
        lookback = cfg['trend_lookback']

        if idx < lookback * 3:
            return 0.5

        # True Range
        tr = np.zeros(idx + 1)
        tr[0] = highs[0] - lows[0]
        for i in range(max(1, idx - lookback * 3), idx + 1):
            tr[i] = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )

        # Directional Movement
        plus_dm = np.zeros(idx + 1)
        minus_dm = np.zeros(idx + 1)
        for i in range(max(1, idx - lookback * 3), idx + 1):
            up = highs[i] - highs[i-1]
            down = lows[i-1] - lows[i]
            if up > down and up > 0:
                plus_dm[i] = up
            if down > up and down > 0:
                minus_dm[i] = down

        # Smooth
        period = cfg['adx_period']
        start = max(period, idx - lookback * 3)

        atr_smooth = np.mean(tr[start:start+period])
        plus_di_smooth = np.mean(plus_dm[start:start+period])
        minus_di_smooth = np.mean(minus_dm[start:start+period])

        for i in range(start + period, idx + 1):
            atr_smooth = (atr_smooth * (period - 1) + tr[i]) / period
            plus_di_smooth = (plus_di_smooth * (period - 1) + plus_dm[i]) / period
            minus_di_smooth = (minus_di_smooth * (period - 1) + minus_dm[i]) / period

        # ADX
        if atr_smooth == 0:
            return 0.5

        plus_di = 100 * plus_di_smooth / atr_smooth
        minus_di = 100 * minus_di_smooth / atr_smooth
        di_diff = abs(plus_di - minus_di)
        di_sum = plus_di + minus_di

        if di_sum == 0:
            return 0.5

        adx = 100 * di_diff / di_sum

        # Normalize to our scale (0 to 3+)
        return adx / 33.0  # ADX 100 = strength 3.0

    def _compute_volatility_rank(self, highs, lows, closes, idx) -> float:
        """Compute ATR percentile rank (0.0 to 1.0)."""
        cfg = self.config
        vol_lookback = cfg['vol_lookback']

        if idx < vol_lookback * 2:
            return 0.5

        # Compute ATR for the lookback window
        atrs = []
        period = 14
        for i in range(max(period + 1, idx - vol_lookback * 2), idx + 1):
            tr = max(
                highs[i] - lows[i],
                abs(highs[i] - closes[i-1]),
                abs(lows[i] - closes[i-1])
            )
            atrs.append(tr)

        if len(atrs) < 10:
            return 0.5

        current_atr = np.mean(atrs[-period:])
        window = atrs[-vol_lookback:]

        if not window:
            return 0.5

        rank = sum(1 for a in window if a < current_atr) / len(window)
        return rank

    @staticmethod
    def _ema(series, period):
        result = np.empty_like(series, dtype=float)
        mult = 2.0 / (period + 1)
        result[0] = series[0]
        for i in range(1, len(series)):
            result[i] = series[i] * mult + result[i-1] * (1 - mult)
        return result
