"""
marketmate/strategy/features.py
─────────────────────────────────
Enriched feature dataclasses for gate pipeline output.

Each gate currently returns only the minimum data needed for signal
generation (pass/fail + winning candidate).  These feature classes
capture ALL intermediate computations so that the state engine and
downstream consumers have access to the full analysis.

Feature extraction is STRICTLY ADDITIVE: it never alters gate logic,
only supplements the existing return values with richer context.

New in v8.0.0 (Intelligence Infrastructure):
  - BiasFeatures     — full G4 intermediate state (EMA values, swing structure)
  - SweepFeatures    — all swing levels + candidates from G5
  - ZoneFeatures     — all OB/FVG candidates + rejection reasons from G6
  - ConfirmFeatures  — both M5 and M15 results from G7
  - RRFeatures       — extended RR metrics from G8
  - ScanFeatures     — composite per-scan feature vector
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


# ─── BiasFeatures (Gate G4) ────────────────────────────────────────────────────

@dataclass
class BiasFeatures:
    """Full intermediate state from HTF bias computation (G4)."""
    # Per-timeframe EMA values
    daily_ema200: float = 0.0
    h4_ema200: float = 0.0

    # Per-timeframe bias results (before resolution)
    daily_bias: str = "neutral"   # "bullish" | "bearish" | "neutral"
    h4_bias: str = "neutral"

    # Per-timeframe structure
    daily_structure: str = "neutral"  # "bullish" | "bearish" | "neutral"
    h4_structure: str = "neutral"

    # EMA position flags
    daily_above_ema: bool = False
    h4_above_ema: bool = False

    # Current price for context
    current_price: float = 0.0

    # Resolution metadata
    resolution_path: str = ""  # e.g. "full_agreement", "daily_neutral_fallback_to_h4"

    # Final resolved bias (same as gate output)
    resolved_bias: str = "neutral"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "daily_ema200":    round(self.daily_ema200, 6),
            "h4_ema200":       round(self.h4_ema200, 6),
            "daily_bias":      self.daily_bias,
            "h4_bias":         self.h4_bias,
            "daily_structure": self.daily_structure,
            "h4_structure":    self.h4_structure,
            "daily_above_ema": self.daily_above_ema,
            "h4_above_ema":    self.h4_above_ema,
            "current_price":   round(self.current_price, 6),
            "resolution_path": self.resolution_path,
            "resolved_bias":   self.resolved_bias,
        }


# ─── SweepFeatures (Gate G5) ──────────────────────────────────────────────────

@dataclass
class SwingLevel:
    """A single swing level detected by the sweep algorithm."""
    price: float
    level_type: str   # "swing_high" | "swing_low"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "price": round(self.price, 6),
            "level_type": self.level_type,
        }


@dataclass
class SweepFeatures:
    """Full intermediate state from liquidity sweep detection (G5)."""
    # All swing levels detected (not just the swept one)
    all_swing_highs: List[float] = field(default_factory=list)
    all_swing_lows: List[float] = field(default_factory=list)

    # Counts
    available_swing_highs: int = 0
    available_swing_lows: int = 0

    # Best sweep (the one that passed the gate)
    best_sweep_type: str = ""         # "buy" | "sell"
    best_sweep_level: float = 0.0
    best_sweep_strength: str = ""     # "strong" | "weak"
    best_sweep_close_inside: bool = False
    best_sweep_candles_ago: int = 0
    best_sweep_distance: float = 0.0

    # Was a sweep found at all?
    sweep_found: bool = False

    # Freshness window metadata
    freshness_window: int = 0
    min_sweep_pct: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "all_swing_highs": [round(h, 6) for h in self.all_swing_highs],
            "all_swing_lows":  [round(l, 6) for l in self.all_swing_lows],
            "available_swing_highs": self.available_swing_highs,
            "available_swing_lows":  self.available_swing_lows,
            "best_sweep_type":        self.best_sweep_type,
            "best_sweep_level":       round(self.best_sweep_level, 6),
            "best_sweep_strength":    self.best_sweep_strength,
            "best_sweep_close_inside": self.best_sweep_close_inside,
            "best_sweep_candles_ago": self.best_sweep_candles_ago,
            "best_sweep_distance":    round(self.best_sweep_distance, 6),
            "sweep_found":       self.sweep_found,
            "freshness_window":  self.freshness_window,
            "min_sweep_pct":     self.min_sweep_pct,
        }


# ─── ZoneCandidate ─────────────────────────────────────────────────────────────

@dataclass
class ZoneCandidate:
    """A single entry zone candidate evaluated by G6."""
    zone_type: str        # "order_block" | "fvg"
    direction: str        # "bullish" | "bearish"
    zone_high: float
    zone_low: float
    zone_mid: float = 0.0
    candle_idx: int = 0
    is_winner: bool = False
    rejection_reason: str = ""  # Empty if winner

    def __post_init__(self) -> None:
        if self.zone_mid == 0.0:
            self.zone_mid = (self.zone_high + self.zone_low) / 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_type":       self.zone_type,
            "direction":       self.direction,
            "zone_high":       round(self.zone_high, 6),
            "zone_low":        round(self.zone_low, 6),
            "zone_mid":        round(self.zone_mid, 6),
            "candle_idx":      self.candle_idx,
            "is_winner":       self.is_winner,
            "rejection_reason": self.rejection_reason,
        }


# ─── ZoneFeatures (Gate G6) ───────────────────────────────────────────────────

@dataclass
class ZoneFeatures:
    """Full intermediate state from entry zone identification (G6)."""
    # All candidates evaluated (OBs + FVGs)
    all_candidates: List[ZoneCandidate] = field(default_factory=list)

    # Winner
    winner_zone_type: str = ""   # "order_block" | "fvg"
    winner_zone_high: float = 0.0
    winner_zone_low: float = 0.0

    # Counts
    ob_candidates_count: int = 0
    fvg_candidates_count: int = 0

    # Was a zone found?
    zone_found: bool = False

    # Search parameters
    ob_search_lookback: int = 0
    min_fvg_pct: float = 0.0
    fvg_freshness_candles: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "all_candidates": [c.to_dict() for c in self.all_candidates],
            "winner_zone_type": self.winner_zone_type,
            "winner_zone_high": round(self.winner_zone_high, 6),
            "winner_zone_low":  round(self.winner_zone_low, 6),
            "ob_candidates_count":  self.ob_candidates_count,
            "fvg_candidates_count": self.fvg_candidates_count,
            "zone_found":             self.zone_found,
            "ob_search_lookback":     self.ob_search_lookback,
            "min_fvg_pct":            self.min_fvg_pct,
            "fvg_freshness_candles":  self.fvg_freshness_candles,
        }


# ─── ConfirmFeatures (Gate G7) ────────────────────────────────────────────────

@dataclass
class ConfirmPattern:
    """A single confirmation pattern found on a specific timeframe."""
    signal_type: str    # "BOS" | "CHoCH"
    direction: str      # "bullish" | "bearish"
    break_level: float
    timeframe: str      # "M15" | "M5"
    is_winner: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_type": self.signal_type,
            "direction":   self.direction,
            "break_level": round(self.break_level, 6),
            "timeframe":   self.timeframe,
            "is_winner":   self.is_winner,
        }


@dataclass
class ConfirmFeatures:
    """Full intermediate state from LTF confirmation (G7)."""
    # Results from each timeframe independently
    m15_result: Optional[ConfirmPattern] = None
    m5_result: Optional[ConfirmPattern] = None

    # All patterns found (may include both BOS and CHoCH on same TF)
    all_patterns: List[ConfirmPattern] = field(default_factory=list)

    # Winner metadata
    winner_signal_type: str = ""   # "BOS" | "CHoCH"
    winner_timeframe: str = ""     # "M15" | "M5"

    # Was confirmation found?
    confirmation_found: bool = False

    # Data availability
    m15_candles_available: int = 0
    m5_candles_available: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "m15_result": self.m15_result.to_dict() if self.m15_result else None,
            "m5_result":  self.m5_result.to_dict() if self.m5_result else None,
            "all_patterns": [p.to_dict() for p in self.all_patterns],
            "winner_signal_type": self.winner_signal_type,
            "winner_timeframe":   self.winner_timeframe,
            "confirmation_found": self.confirmation_found,
            "m15_candles_available": self.m15_candles_available,
            "m5_candles_available":  self.m5_candles_available,
        }


# ─── RRFeatures (Gate G8) ─────────────────────────────────────────────────────

@dataclass
class RRFeatures:
    """Extended RR metrics from risk validation (G8)."""
    rr: float = 0.0
    entry: float = 0.0
    sl: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0

    # Extended metrics
    atr_value: float = 0.0
    sl_distance_pips: float = 0.0
    sl_distance_atr_ratio: float = 0.0  # SL distance / ATR

    # RR validation
    rr_passed: bool = False
    min_rr: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "rr":                round(self.rr, 2),
            "entry":             round(self.entry, 6),
            "sl":                round(self.sl, 6),
            "tp1":               round(self.tp1, 6),
            "tp2":               round(self.tp2, 6),
            "tp3":               round(self.tp3, 6),
            "atr_value":         round(self.atr_value, 6),
            "sl_distance_pips":  round(self.sl_distance_pips, 6),
            "sl_distance_atr_ratio": round(self.sl_distance_atr_ratio, 3),
            "rr_passed":         self.rr_passed,
            "min_rr":            self.min_rr,
        }


# ─── ScanFeatures (Composite) ─────────────────────────────────────────────────

@dataclass
class ScanFeatures:
    """
    Composite feature vector from a complete scan cycle.
    Aggregates all gate features plus scoring into a single object
    that can be persisted, queried, and fed to ML models.
    """
    symbol: str = ""
    timestamp: str = ""

    # Per-gate features
    bias_features: Optional[BiasFeatures] = None
    sweep_features: Optional[SweepFeatures] = None
    zone_features: Optional[ZoneFeatures] = None
    confirm_features: Optional[ConfirmFeatures] = None
    rr_features: Optional[RRFeatures] = None

    # Gate pipeline outcome
    passed: bool = False
    failed_at: str = ""

    # Scoring (populated when passed=True)
    confidence_score: float = 0.0
    confidence_tier: str = ""
    confidence_breakdown: Dict[str, float] = field(default_factory=dict)
    setup_score: float = 0.0
    setup_breakdown: Dict[str, float] = field(default_factory=dict)

    # Session context
    session_active: bool = False
    trades_today: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "symbol":            self.symbol,
            "timestamp":         self.timestamp,
            "bias_features":     self.bias_features.to_dict() if self.bias_features else None,
            "sweep_features":    self.sweep_features.to_dict() if self.sweep_features else None,
            "zone_features":     self.zone_features.to_dict() if self.zone_features else None,
            "confirm_features":  self.confirm_features.to_dict() if self.confirm_features else None,
            "rr_features":       self.rr_features.to_dict() if self.rr_features else None,
            "passed":            self.passed,
            "failed_at":         self.failed_at,
            "confidence_score":  round(self.confidence_score, 3),
            "confidence_tier":   self.confidence_tier,
            "confidence_breakdown": {k: round(v, 3) for k, v in self.confidence_breakdown.items()},
            "setup_score":       round(self.setup_score, 3),
            "setup_breakdown":   {k: round(v, 3) for k, v in self.setup_breakdown.items()},
            "session_active":    self.session_active,
            "trades_today":      self.trades_today,
        }
