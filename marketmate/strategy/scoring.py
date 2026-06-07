"""
marketmate/strategy/scoring.py
────────────────────────────────
Multi-Factor Confidence Scoring & Weighted Setup Scoring Engine.

Migrated from strategy/confidence.py with updated imports to use
marketmate.strategy.models. Expanded with weighted setup scoring.

Two scoring systems:

1. Confidence Scoring (compute_confidence):
   Replaces the binary HIGH/MEDIUM confidence system with a continuous 0.0-1.0
   score derived from multiple signal quality factors. The score is then mapped
   to human-readable tiers (HIGH / MEDIUM / LOW) for display.

   Quality factors:
     1. Sweep Strength     — How deep the wick penetrated beyond the swept level
     2. Zone Freshness     — How recently the OB/FVG was formed
     3. Volume at Sweep    — High-volume sweeps are more reliable
     4. Time-of-Day Bonus  — London-NY overlap produces more reliable setups
     5. Pattern Quality    — OB+CHoCH is historically stronger than FVG+BOS
     6. Confirmation TF    — M15 confirmation is stronger than M5

2. Weighted Setup Scoring (compute_weighted_score):
   A broader scoring system that incorporates RR ratio and session quality
   alongside the confidence factors, producing a SetupScore with a minimum
   threshold check.

   Weighted factors:
     - session:       0.05  (trading session quality)
     - htf_bias:      0.20  (HTF directional alignment)
     - sweep_quality: 0.25  (sweep depth and recency)
     - zone_quality:  0.20  (entry zone institutional weight)
     - confirmation:  0.15  (LTF confirmation strength)
     - rr_ratio:      0.15  (reward-to-risk ratio)

Backward Compatibility:
  The continuous score is stored internally and also mapped to the original
  HIGH/MEDIUM labels so that existing consumers continue to work.
"""

from __future__ import annotations
from datetime import datetime, timezone, time
from typing import Optional

import numpy as np
import pandas as pd

from marketmate.core.config import cfg
from marketmate.strategy.models import (
    ConfirmResult,
    EntryZone,
    SweepResult,
)

# Type aliases for the return types of the scoring functions.
# ConfidenceScore and SetupScore were originally Pydantic/dataclass types
# removed during the v1 strategy revert. Now re-introduced as TypedDict
# equivalents for type checking while maintaining backward compatibility
# with the plain-dict return values.
from typing import Dict, Any, TypedDict


class ConfidenceScore(TypedDict):
    score: float
    tier: str
    breakdown: Dict[str, float]


class SetupScore(TypedDict):
    total: float
    threshold: float
    passed: bool
    breakdown: Dict[str, float]
    weighted: Dict[str, float]
    legacy_tier: str
from marketmate.core.logger import get_logger

log = get_logger("confidence")


# ─── Confidence Scoring Weights (must sum to 1.0) ───────────────────────────

WEIGHTS = {
    "sweep_strength":   0.25,   # Most important: sweep quality drives signal quality
    "zone_freshness":   0.15,   # Fresh zones are more likely to hold
    "volume_quality":   0.10,   # Volume confirmation (lower weight — data may be missing)
    "time_of_day":      0.15,   # London-NY overlap produces more reliable signals
    "pattern_quality":  0.20,   # OB+CHoCH > FVG+BOS historically
    "confirmation_tf":  0.15,   # M15 > M5 for confirmation strength
}

# ─── Tier thresholds ────────────────────────────────────────────────────────
TIER_HIGH   = 0.70   # >= 0.70 → HIGH
TIER_MEDIUM = 0.45   # >= 0.45 → MEDIUM
# < 0.45 → LOW (rare, but possible for weak setups that pass all gates)

# ─── Weighted Setup Scoring Weights ─────────────────────────────────────────

SCORE_WEIGHTS = {
    "session":       0.05,   # Trading session quality
    "htf_bias":      0.20,   # HTF directional alignment
    "sweep_quality": 0.25,   # Sweep depth and recency
    "zone_quality":  0.20,   # Entry zone institutional weight
    "confirmation":  0.15,   # LTF confirmation strength
    "rr_ratio":      0.15,   # Reward-to-risk ratio
}

MIN_SCORE_THRESHOLD = 0.45

# ─── Time-of-day session boundaries (UTC) ───────────────────────────────────
_LONDON_OPEN  = time(7, 0)
_LONDON_CLOSE = time(12, 0)
_NY_OPEN      = time(12, 0)
_NY_CLOSE     = time(17, 0)


# ─── Confidence Scoring ─────────────────────────────────────────────────────

def compute_confidence(
    sweep: SweepResult,
    zone: EntryZone,
    confirm: ConfirmResult,
    h4_df: Optional[pd.DataFrame] = None,
    volume_df: Optional[pd.DataFrame] = None,
    confidence_cap: Optional[str] = None,
) -> Dict[str, Any]:
    """
    Compute a multi-factor confidence score for a signal that passed all gates.

    Args:
        sweep:          Gate 5 sweep result
        zone:           Gate 6 entry zone result
        confirm:        Gate 7 LTF confirmation result
        h4_df:          H4 DataFrame for ATR computation (optional, for sweep strength)
        volume_df:      OHLCV DataFrame with volume data (optional, for volume quality)
        confidence_cap: If "MEDIUM", cap the final score at the MEDIUM threshold

    Returns:
        ConfidenceScore with continuous score, tier, and factor breakdown.
    """
    breakdown = {}

    # ── Factor 1: Sweep Strength ──────────────────────────────────────────
    breakdown["sweep_strength"] = _score_sweep_strength(sweep, h4_df)

    # ── Factor 2: Zone Freshness ──────────────────────────────────────────
    breakdown["zone_freshness"] = _score_zone_freshness(zone)

    # ── Factor 3: Volume Quality ──────────────────────────────────────────
    breakdown["volume_quality"] = _score_volume_quality(volume_df)

    # ── Factor 4: Time of Day ─────────────────────────────────────────────
    breakdown["time_of_day"] = _score_time_of_day()

    # ── Factor 5: Pattern Quality ─────────────────────────────────────────
    breakdown["pattern_quality"] = _score_pattern_quality(zone, confirm)

    # ── Factor 6: Confirmation Timeframe ──────────────────────────────────
    breakdown["confirmation_tf"] = _score_confirmation_tf(confirm)

    # ── Weighted Sum ───────────────────────────────────────────────────────
    score = sum(
        WEIGHTS[factor] * breakdown[factor]
        for factor in WEIGHTS
    )

    # ── Apply cap for neutral-bias setups ──────────────────────────────────
    if confidence_cap == "MEDIUM" and score >= TIER_HIGH:
        score = TIER_HIGH - 0.01  # Just below HIGH threshold → MEDIUM tier

    # ── Clamp to [0.0, 1.0] ───────────────────────────────────────────────
    score = max(0.0, min(1.0, score))

    # ── Map to tier ────────────────────────────────────────────────────────
    if score >= TIER_HIGH:
        tier = "HIGH"
    elif score >= TIER_MEDIUM:
        tier = "MEDIUM"
    else:
        tier = "LOW"

    log.info(
        "confidence_scored",
        score=round(score, 3),
        tier=tier,
        breakdown={k: round(v, 3) for k, v in breakdown.items()},
    )

    return {"score": score, "tier": tier, "breakdown": breakdown}


# ─── Weighted Setup Scoring ──────────────────────────────────────────────────

def compute_weighted_score(
    sweep: SweepResult,
    zone: EntryZone,
    confirm: ConfirmResult,
    bias: str,
    rr: float,
    h4_df: Optional[pd.DataFrame] = None,
    volume_df: Optional[pd.DataFrame] = None,
) -> Dict[str, Any]:
    """
    Compute a weighted setup quality score incorporating RR ratio and
    session quality alongside the confidence factors.

    Args:
        sweep:      Gate 5 sweep result
        zone:       Gate 6 entry zone result
        confirm:    Gate 7 LTF confirmation result
        bias:       HTF bias direction ("bullish" | "bearish")
        rr:         Reward-to-risk ratio from Gate 8
        h4_df:      H4 DataFrame for ATR computation
        volume_df:  OHLCV DataFrame with volume data

    Returns:
        SetupScore with total, threshold, passed flag, and breakdown.
    """
    breakdown = {}
    weighted = {}

    # ── Session Quality ────────────────────────────────────────────────────
    breakdown["session"] = _score_time_of_day()
    weighted["session"] = breakdown["session"] * SCORE_WEIGHTS["session"]

    # ── HTF Bias Quality ───────────────────────────────────────────────────
    # Full directional bias (bullish/bearish) scores higher than neutral-resolved
    breakdown["htf_bias"] = 1.0  # Full score — if we're here, bias is confirmed
    weighted["htf_bias"] = breakdown["htf_bias"] * SCORE_WEIGHTS["htf_bias"]

    # ── Sweep Quality ──────────────────────────────────────────────────────
    breakdown["sweep_quality"] = _score_sweep_strength(sweep, h4_df)
    weighted["sweep_quality"] = breakdown["sweep_quality"] * SCORE_WEIGHTS["sweep_quality"]

    # ── Zone Quality ───────────────────────────────────────────────────────
    breakdown["zone_quality"] = _score_zone_quality(zone)
    weighted["zone_quality"] = breakdown["zone_quality"] * SCORE_WEIGHTS["zone_quality"]

    # ── Confirmation Quality ───────────────────────────────────────────────
    breakdown["confirmation"] = _score_confirmation_quality(zone, confirm)
    weighted["confirmation"] = breakdown["confirmation"] * SCORE_WEIGHTS["confirmation"]

    # ── RR Ratio ───────────────────────────────────────────────────────────
    breakdown["rr_ratio"] = _score_rr_ratio(rr)
    weighted["rr_ratio"] = breakdown["rr_ratio"] * SCORE_WEIGHTS["rr_ratio"]

    # ── Total ──────────────────────────────────────────────────────────────
    total = sum(weighted.values())
    total = max(0.0, min(1.0, total))

    passed = total >= MIN_SCORE_THRESHOLD

    # Legacy tier mapping
    if total >= TIER_HIGH:
        legacy_tier = "HIGH"
    else:
        legacy_tier = "MEDIUM"

    log.info(
        "setup_score_computed",
        total=round(total, 3),
        threshold=MIN_SCORE_THRESHOLD,
        passed=passed,
        legacy_tier=legacy_tier,
        breakdown={k: round(v, 3) for k, v in breakdown.items()},
        weighted={k: round(v, 3) for k, v in weighted.items()},
    )

    return {
        "total": total,
        "threshold": MIN_SCORE_THRESHOLD,
        "passed": passed,
        "breakdown": breakdown,
        "weighted": weighted,
        "legacy_tier": legacy_tier,
    }


# ─── Individual Factor Scorers (Confidence) ─────────────────────────────────

def _score_sweep_strength(sweep: SweepResult, h4_df: Optional[pd.DataFrame]) -> float:
    """
    Score sweep quality on a 0.0-1.0 scale.

    Factors:
    - close_inside: Strong signal (sweep + rejection) → base 0.7
    - Sweep distance relative to ATR: Deeper sweeps score higher
    - Candles ago: More recent sweeps score slightly higher

    Without h4_df for ATR computation, falls back to the simpler binary model.
    """
    score = 0.3  # Base score for any sweep

    # Close inside is the primary quality indicator
    if sweep.close_inside:
        score += 0.3  # 0.6 base for close_inside

    # Sweep recency — more recent sweeps are more relevant
    # candles_ago = 0 → most recent candle, score 1.0; candles_ago = 20 → 0.0
    recency = max(0.0, 1.0 - (sweep.candles_ago / 20.0))
    score += recency * 0.2  # Up to 0.2 bonus for recency

    # Sweep depth relative to ATR (when available)
    if h4_df is not None and len(h4_df) >= 14:
        try:
            atr = _compute_atr(h4_df, period=14)
            if atr > 0:
                # Normalize sweep distance by ATR
                # A sweep of 0.5 ATR is decent; 1.0+ ATR is very strong
                atr_ratio = sweep.sweep_distance / atr
                depth_score = min(1.0, atr_ratio / 1.0)  # Normalize to 0-1
                score += depth_score * 0.2  # Up to 0.2 bonus for deep sweeps
            else:
                score += 0.1  # Default bonus when ATR can't be computed
        except Exception:
            score += 0.1
    else:
        # No ATR data — give small default bonus
        if sweep.close_inside:
            score += 0.1

    return max(0.0, min(1.0, score))


def _score_zone_freshness(zone: EntryZone) -> float:
    """
    Score zone freshness on a 0.0-1.0 scale.

    Fresher zones (formed more recently) score higher because they haven't
    been retested and depleted of institutional order flow.

    Uses zone type as a proxy for freshness.
    """
    if zone.zone_type == "order_block":
        # Order blocks are inherently fresh — they're the most recent displacement
        return 0.8
    elif zone.zone_type == "fvg":
        # FVGs can be fresh or stale — give moderate score
        return 0.6
    else:
        # Unknown zone type
        return 0.5


def _score_volume_quality(volume_df: Optional[pd.DataFrame]) -> float:
    """
    Score volume quality on a 0.0-1.0 scale.

    High-volume at the sweep point confirms institutional participation.
    Low-volume sweeps are more likely to be false outs.

    Without volume data, returns a neutral score (0.5).
    """
    if volume_df is None or volume_df.empty:
        return 0.5  # Neutral — no data to evaluate

    try:
        volumes = volume_df["volume"].values
        if len(volumes) < 20:
            return 0.5

        avg_volume = np.mean(volumes[-20:])
        recent_volume = float(volumes[-1])

        if avg_volume <= 0:
            return 0.5

        # Relative volume ratio
        rel_vol = recent_volume / avg_volume

        # Score: 1x average → 0.5, 2x+ → 0.8+, <0.5x → 0.2
        if rel_vol >= 2.0:
            return 0.85  # High volume confirmation
        elif rel_vol >= 1.5:
            return 0.7
        elif rel_vol >= 1.0:
            return 0.5
        elif rel_vol >= 0.5:
            return 0.35
        else:
            return 0.2  # Low volume — suspicious
    except Exception:
        return 0.5


def _score_time_of_day() -> float:
    """
    Score time-of-day reliability on a 0.0-1.0 scale.

    SMC patterns work best during high-volume sessions:
    - London-NY overlap (12:00-17:00 UTC): 1.0
    - London only (07:00-12:00 UTC): 0.8
    - NY only (12:00-17:00 UTC): 0.7
    - Asian session / off-hours: 0.4
    """
    now_utc = datetime.now(timezone.utc).time()

    in_london = _LONDON_OPEN <= now_utc <= _LONDON_CLOSE
    in_ny = _NY_OPEN <= now_utc <= _NY_CLOSE

    if in_london and in_ny:
        return 1.0   # London-NY overlap — best liquidity
    elif in_london:
        return 0.8   # London session
    elif in_ny:
        return 0.7   # NY session
    else:
        return 0.4   # Off-hours


def _score_pattern_quality(zone: EntryZone, confirm: ConfirmResult) -> float:
    """
    Score pattern quality on a 0.0-1.0 scale.

    Historical analysis shows significant win rate differences by pattern:
    - OB + CHoCH: 0.9 (strongest — institutional rejection + structure break)
    - OB + BOS: 0.7 (strong zone, continuation confirmation)
    - FVG + CHoCH: 0.65 (gap fill + reversal)
    - FVG + BOS: 0.5 (weakest — gap continuation)
    """
    is_ob = zone.zone_type == "order_block"
    is_choch = confirm.signal_type == "CHoCH"

    if is_ob and is_choch:
        return 0.9   # OB + CHoCH: strongest reversal pattern
    elif is_ob:
        return 0.7   # OB + BOS: strong continuation
    elif is_choch:
        return 0.65  # FVG + CHoCH: moderate reversal
    else:
        return 0.5   # FVG + BOS: weakest pattern


def _score_confirmation_tf(confirm: ConfirmResult) -> float:
    """
    Score confirmation timeframe on a 0.0-1.0 scale.

    M15 confirmation is stronger than M5 because it represents a more
    significant structural break (more market participants involved).
    """
    if confirm.timeframe == "M15":
        return 0.9   # M15 — significant structural break
    elif confirm.timeframe == "M5":
        return 0.6   # M5 — less significant but still valid
    else:
        return 0.5   # Unknown timeframe


# ─── Additional Factor Scorers (Weighted Setup) ─────────────────────────────

def _score_zone_quality(zone: EntryZone) -> float:
    """
    Score zone quality on a 0.0-1.0 scale for weighted setup scoring.

    Combines zone type weight with freshness assessment:
    - Order blocks score higher (institutional footprint)
    - FVGs score moderately (imbalance fill)
    """
    type_score = 0.85 if zone.zone_type == "order_block" else 0.60
    # Combine with freshness
    freshness = _score_zone_freshness(zone)
    return (type_score + freshness) / 2.0


def _score_confirmation_quality(zone: EntryZone, confirm: ConfirmResult) -> float:
    """
    Score confirmation quality combining pattern and timeframe strength.
    """
    pattern = _score_pattern_quality(zone, confirm)
    tf_score = _score_confirmation_tf(confirm)
    return (pattern + tf_score) / 2.0


def _score_rr_ratio(rr: float) -> float:
    """
    Score RR ratio on a 0.0-1.0 scale.

    - RR >= 3.0: 1.0  (excellent)
    - RR >= 2.0: 0.8  (good)
    - RR >= 1.5: 0.6  (acceptable)
    - RR >= 1.0: 0.4  (minimal)
    - RR < 1.0: 0.2   (poor — shouldn't happen after gate)
    """
    if rr >= 3.0:
        return 1.0
    elif rr >= 2.0:
        return 0.8
    elif rr >= 1.5:
        return 0.6
    elif rr >= 1.0:
        return 0.4
    else:
        return 0.2


# ─── Helpers ────────────────────────────────────────────────────────────────

def _compute_atr(df: pd.DataFrame, period: int = 14) -> float:
    """Compute the Average True Range from an OHLCV DataFrame."""
    highs = df["high"].values
    lows = df["low"].values
    closes = df["close"].values

    if len(highs) < period + 1:
        return 0.0

    # True Range = max(H-L, |H-prevC|, |L-prevC|)
    tr_values = []
    for i in range(1, len(highs)):
        tr = max(
            highs[i] - lows[i],
            abs(highs[i] - closes[i - 1]),
            abs(lows[i] - closes[i - 1]),
        )
        tr_values.append(tr)

    if len(tr_values) < period:
        return float(np.mean(tr_values)) if tr_values else 0.0

    # Simple moving average of TR for the last `period` values
    return float(np.mean(tr_values[-period:]))


def score_to_legacy_tier(score: float) -> str:
    """Convert a continuous confidence score to the original HIGH/MEDIUM tier."""
    if score >= TIER_HIGH:
        return "HIGH"
    else:
        return "MEDIUM"
