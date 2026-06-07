"""
marketmate/state/models.py
─────────────────────────────
Pydantic models for the Market Intelligence State Engine.

Defines the canonical data structures for instrument state,
market state vectors, and state transitions (diffs).

These models are the source of truth for the state engine's
data format and are used for:
  - Redis hot-layer storage (via model_dump_json / model_validate_json)
  - MongoDB warm-layer storage (via model_dump)
  - API response serialization
  - Event payload validation

New in v8.0.0 (Intelligence Infrastructure).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Dict, List, Optional

from pydantic import BaseModel, Field, field_validator


# ─── Enums ────────────────────────────────────────────────────────────────────

class BiasDirection(str, Enum):
    BULLISH = "bullish"
    BEARISH = "bearish"
    NEUTRAL = "neutral"


class MarketRegime(str, Enum):
    TRENDING = "trending"
    RANGING = "ranging"
    TRANSITIONAL = "transitional"


class VolatilityRegime(str, Enum):
    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    EXTREME = "extreme"


class ZoneStatus(str, Enum):
    ACTIVE = "active"
    APPROACHING = "approaching"
    EXPIRED = "expired"


# ─── Sub-State Models ─────────────────────────────────────────────────────────

class BiasState(BaseModel):
    """Directional conviction state for a single instrument."""
    daily_ema200: float = 0.0
    h4_ema200: float = 0.0
    daily_bias: BiasDirection = BiasDirection.NEUTRAL
    h4_bias: BiasDirection = BiasDirection.NEUTRAL
    daily_structure: str = "neutral"
    h4_structure: str = "neutral"
    daily_above_ema: bool = False
    h4_above_ema: bool = False
    conviction_score: float = Field(default=0.0, ge=-1.0, le=1.0,
                                     description="Directional conviction: -1.0 (bearish) to +1.0 (bullish)")
    regime: MarketRegime = MarketRegime.RANGING
    resolution_path: str = ""
    current_price: float = 0.0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    @field_validator("conviction_score")
    @classmethod
    def clamp_conviction(cls, v: float) -> float:
        return max(-1.0, min(1.0, v))


class LiquidityLevel(BaseModel):
    """A single tracked liquidity level."""
    price: float
    level_type: str = Field(description="swing_high | swing_low")
    is_swept: bool = False
    swept_at: Optional[datetime] = None


class LiquidityState(BaseModel):
    """Liquidity sweep state for a single instrument."""
    active_levels: List[LiquidityLevel] = Field(default_factory=list)
    recent_sweeps: List[LiquidityLevel] = Field(default_factory=list)
    sweep_rate: float = Field(default=0.0, ge=0.0, description="Sweeps per hour (rolling 24h)")
    available_liquidity_score: float = Field(default=0.0, ge=0.0, le=1.0,
                                              description="How much unrealized liquidity remains")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class TrackedZone(BaseModel):
    """A single tracked entry zone."""
    zone_type: str = Field(description="order_block | fvg")
    direction: str = Field(description="bullish | bearish")
    zone_high: float
    zone_low: float
    zone_mid: float = 0.0
    status: ZoneStatus = ZoneStatus.ACTIVE
    freshness_score: float = Field(default=1.0, ge=0.0, le=1.0)
    formed_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    candle_idx: int = 0


class ZoneState(BaseModel):
    """Entry zone state for a single instrument."""
    active_zones: List[TrackedZone] = Field(default_factory=list)
    approaching_zones: List[TrackedZone] = Field(default_factory=list)
    expired_zones: List[TrackedZone] = Field(default_factory=list, max_length=20)
    zone_freshness: float = Field(default=0.0, ge=0.0, le=1.0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConfirmationPattern(BaseModel):
    """A recent BOS or CHoCH pattern."""
    signal_type: str = Field(description="BOS | CHoCH")
    direction: str = Field(description="bullish | bearish")
    break_level: float
    timeframe: str = Field(description="M15 | M5")
    detected_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ConfirmState(BaseModel):
    """LTF confirmation state for a single instrument."""
    recent_bos: List[ConfirmationPattern] = Field(default_factory=list, max_length=10)
    recent_choch: List[ConfirmationPattern] = Field(default_factory=list, max_length=10)
    pattern_rate: float = Field(default=0.0, ge=0.0, description="Patterns per hour (rolling 24h)")
    alignment_score: float = Field(default=0.0, ge=0.0, le=1.0,
                                    description="How well confirmations align with bias")
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class RiskState(BaseModel):
    """Risk and volatility state for a single instrument."""
    atr: float = Field(default=0.0, ge=0.0)
    sl_distance_pips: float = Field(default=0.0, ge=0.0)
    volatility_regime: VolatilityRegime = VolatilityRegime.NORMAL
    current_rr: float = Field(default=0.0, ge=0.0)
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# ─── Composite Models ─────────────────────────────────────────────────────────

class InstrumentState(BaseModel):
    """
    Complete market state for a single instrument.

    Aggregates all sub-states into a unified view that can be
    queried, persisted, and compared across scan cycles.
    """
    symbol: str
    bias_state: BiasState = Field(default_factory=BiasState)
    liquidity_state: LiquidityState = Field(default_factory=LiquidityState)
    zone_state: ZoneState = Field(default_factory=ZoneState)
    confirm_state: ConfirmState = Field(default_factory=ConfirmState)
    risk_state: RiskState = Field(default_factory=RiskState)

    # Composite metrics
    overall_signal_quality: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_score: float = Field(default=0.0, ge=0.0, le=1.0)
    confidence_tier: str = ""
    setup_score: float = Field(default=0.0, ge=0.0, le=1.0)

    # Scan metadata
    scan_count: int = 0
    last_scan_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    last_signal_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class InstrumentStateSummary(BaseModel):
    """Compact summary of an instrument state for list/overview API responses."""
    symbol: str
    bias: BiasDirection = BiasDirection.NEUTRAL
    conviction_score: float = 0.0
    regime: MarketRegime = MarketRegime.RANGING
    active_zones_count: int = 0
    available_liquidity_score: float = 0.0
    confidence_tier: str = ""
    volatility_regime: VolatilityRegime = VolatilityRegime.NORMAL
    last_scan_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class MarketStateVector(BaseModel):
    """
    Complete market state across all monitored instruments.

    Provides both per-instrument detail and cross-instrument
    correlation/regime analysis.
    """
    instruments: Dict[str, InstrumentState] = Field(default_factory=dict)
    correlations: Dict[str, float] = Field(default_factory=dict,
                                            description="Cross-instrument correlation scores")
    market_regime: MarketRegime = MarketRegime.RANGING
    scan_cycle: int = 0
    updated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))

    def get_summary(self) -> Dict[str, InstrumentStateSummary]:
        """Return compact summaries for all instruments."""
        return {
            sym: InstrumentStateSummary(
                symbol=sym,
                bias=state.bias_state.daily_bias if state.bias_state else BiasDirection.NEUTRAL,
                conviction_score=state.bias_state.conviction_score if state.bias_state else 0.0,
                regime=state.bias_state.regime if state.bias_state else MarketRegime.RANGING,
                active_zones_count=len(state.zone_state.active_zones) if state.zone_state else 0,
                available_liquidity_score=state.liquidity_state.available_liquidity_score if state.liquidity_state else 0.0,
                confidence_tier=state.confidence_tier,
                volatility_regime=state.risk_state.volatility_regime if state.risk_state else VolatilityRegime.NORMAL,
                last_scan_at=state.last_scan_at,
            )
            for sym, state in self.instruments.items()
        }


# ─── State Diff ───────────────────────────────────────────────────────────────

class StateDiffField(BaseModel):
    """A single field change within a state transition."""
    field_path: str = Field(description="Dot-notation path, e.g. 'bias_state.conviction_score'")
    old_value: Optional[float] = None
    new_value: Optional[float] = None
    change_type: str = Field(description="created | updated | removed")


class StateDiff(BaseModel):
    """
    Delta between two consecutive InstrumentState snapshots.

    Rather than storing complete state on every scan, the engine
    computes and persists only the meaningful changes. These diffs
    are compact, queryable, and ideal for event generation and
    historical analysis.
    """
    symbol: str
    diff_id: str = ""
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    changes: List[StateDiffField] = Field(default_factory=list)

    # Quick-access flags for common transitions
    bias_changed: bool = False
    zone_formed: bool = False
    zone_expired: bool = False
    sweep_detected: bool = False
    regime_changed: bool = False

    @property
    def has_material_change(self) -> bool:
        """Whether this diff contains any material state transition."""
        return (
            self.bias_changed
            or self.zone_formed
            or self.zone_expired
            or self.sweep_detected
            or self.regime_changed
        )
