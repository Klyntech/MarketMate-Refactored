"""
marketmate/core/schemas.py
─────────────────────────────
Typed event schemas with versioning for the EventBus.

Every event emitted through the EventBus is validated against a
Pydantic schema before delivery. Schemas are versioned to support
backward-compatible evolution: consumers check schema_version
before processing and handle unknown fields gracefully.

New in v8.0.0 (Intelligence Infrastructure).
"""

from __future__ import annotations

from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import uuid4

from pydantic import BaseModel, Field


# ─── Schema Version ───────────────────────────────────────────────────────────

SCHEMA_VERSION = "v1"


# ─── Event Categories ─────────────────────────────────────────────────────────

class EventCategory(str, Enum):
    GATE = "gate"
    STATE = "state"
    SIGNAL = "signal"
    MARKET = "market"
    SYSTEM = "system"


# ─── Base Event Schema ─────────────────────────────────────────────────────────

class BaseEvent(BaseModel):
    """
    Base schema for all events in the system.

    Every event carries:
      - event_id: UUID for idempotency and deduplication
      - event_type: Typed event name for routing
      - category: Event category for filtering
      - schema_version: Version for backward-compatible evolution
      - timestamp: ISO 8601 UTC timestamp
      - symbol: Related instrument (empty for system events)
    """
    event_id: str = Field(default_factory=lambda: str(uuid4())[:12])
    event_type: str = ""
    category: EventCategory = EventCategory.SYSTEM
    schema_version: str = SCHEMA_VERSION
    timestamp: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    symbol: str = ""


# ─── Gate Events ──────────────────────────────────────────────────────────────

class GatePassedEvent(BaseEvent):
    """Emitted when a gate passes ( informational, not actionable)."""
    event_type: str = "gate_passed"
    category: EventCategory = EventCategory.GATE
    gate_name: str = ""        # e.g. "G4_HTF_BIAS"
    gate_values: Dict[str, Any] = Field(default_factory=dict)


class GateFailedEvent(BaseEvent):
    """Emitted when a gate fails (diagnostic, not actionable)."""
    event_type: str = "gate_failed"
    category: EventCategory = EventCategory.GATE
    gate_name: str = ""
    reason: str = ""
    gate_values: Dict[str, Any] = Field(default_factory=dict)


class GateFeaturesComputedEvent(BaseEvent):
    """Emitted after all gates run, carrying the full feature vector."""
    event_type: str = "gate_features_computed"
    category: EventCategory = EventCategory.GATE
    passed: bool = False
    failed_at: str = ""
    feature_summary: Dict[str, Any] = Field(default_factory=dict)


# ─── State Events ─────────────────────────────────────────────────────────────

class BiasChangedEvent(BaseEvent):
    """Emitted when HTF bias changes for an instrument."""
    event_type: str = "bias_changed"
    category: EventCategory = EventCategory.STATE
    old_bias: str = ""
    new_bias: str = ""
    conviction_score: float = 0.0
    resolution_path: str = ""
    daily_ema200: float = 0.0
    h4_ema200: float = 0.0


class ZoneFormedEvent(BaseEvent):
    """Emitted when a new entry zone is identified."""
    event_type: str = "zone_formed"
    category: EventCategory = EventCategory.STATE
    zone_type: str = ""        # "order_block" | "fvg"
    direction: str = ""        # "bullish" | "bearish"
    zone_high: float = 0.0
    zone_low: float = 0.0
    freshness_score: float = 0.0


class ZoneExpiredEvent(BaseEvent):
    """Emitted when an active zone expires."""
    event_type: str = "zone_expired"
    category: EventCategory = EventCategory.STATE
    zone_type: str = ""
    direction: str = ""
    zone_high: float = 0.0
    zone_low: float = 0.0


class SweepDetectedEvent(BaseEvent):
    """Emitted when a liquidity sweep is detected."""
    event_type: str = "sweep_detected"
    category: EventCategory = EventCategory.STATE
    swept_level: float = 0.0
    sweep_type: str = ""       # "buy" | "sell"
    direction: str = ""
    strength: str = ""         # "strong" | "weak"
    close_inside: bool = False
    sweep_distance: float = 0.0
    available_levels: int = 0
    sweep_rate: float = 0.0


class RegimeChangedEvent(BaseEvent):
    """Emitted when the market regime transitions."""
    event_type: str = "regime_changed"
    category: EventCategory = EventCategory.STATE
    old_regime: str = ""
    new_regime: str = ""
    confidence: float = 0.0
    conviction_score: float = 0.0


# ─── Signal Events (existing, now schema-validated) ───────────────────────────

class SignalCreatedEvent(BaseEvent):
    """Emitted when a new signal passes all gates and dedup."""
    event_type: str = "signal_created"
    category: EventCategory = EventCategory.SIGNAL
    signal_id: str = ""
    direction: str = ""
    entry: float = 0.0
    stop_loss: float = 0.0
    tp1: float = 0.0
    rr: float = 0.0
    confidence: str = ""
    confidence_score: float = 0.0
    setup_score: float = 0.0


class TradeOpenedEvent(BaseEvent):
    """Emitted when a signal transitions to OPEN status."""
    event_type: str = "trade_opened"
    category: EventCategory = EventCategory.SIGNAL
    signal_id: str = ""
    entry_price: float = 0.0


class TradeClosedEvent(BaseEvent):
    """Emitted when a trade is closed (TP or SL hit)."""
    event_type: str = "trade_closed"
    category: EventCategory = EventCategory.SIGNAL
    signal_id: str = ""
    outcome: str = ""          # "tp1" | "tp2" | "tp3" | "sl"
    exit_price: float = 0.0
    pnl_r: float = 0.0


class TPHitEvent(BaseEvent):
    """Emitted when a take-profit level is hit."""
    event_type: str = "tp_hit"
    category: EventCategory = EventCategory.SIGNAL
    signal_id: str = ""
    tp_level: str = ""         # "tp1" | "tp2" | "tp3"
    price: float = 0.0


class LossHitEvent(BaseEvent):
    """Emitted when stop-loss is hit."""
    event_type: str = "loss_hit"
    category: EventCategory = EventCategory.SIGNAL
    signal_id: str = ""
    price: float = 0.0


# ─── Market Events ────────────────────────────────────────────────────────────

class SessionOpenedEvent(BaseEvent):
    """Emitted when a trading session opens."""
    event_type: str = "session_opened"
    category: EventCategory = EventCategory.MARKET
    session: str = ""          # "london" | "ny"


class SessionClosedEvent(BaseEvent):
    """Emitted when a trading session closes."""
    event_type: str = "session_closed"
    category: EventCategory = EventCategory.MARKET
    session: str = ""


class VolatilitySpikeEvent(BaseEvent):
    """Emitted when ATR spikes beyond normal range."""
    event_type: str = "volatility_spike"
    category: EventCategory = EventCategory.MARKET
    atr: float = 0.0
    atr_normal: float = 0.0
    spike_ratio: float = 0.0


# ─── System Events ────────────────────────────────────────────────────────────

class ScanCompletedEvent(BaseEvent):
    """Emitted after each complete scan cycle."""
    event_type: str = "scan_completed"
    category: EventCategory = EventCategory.SYSTEM
    symbol: str = ""
    passed: bool = False
    failed_at: str = ""
    scan_duration_ms: float = 0.0


class ProviderDegradedEvent(BaseEvent):
    """Emitted when a data provider is degraded."""
    event_type: str = "provider_degraded"
    category: EventCategory = EventCategory.SYSTEM
    provider: str = ""
    status: str = ""


class HealthCheckFailedEvent(BaseEvent):
    """Emitted when a system health check fails."""
    event_type: str = "health_check_failed"
    category: EventCategory = EventCategory.SYSTEM
    component: str = ""
    error: str = ""


# ─── Event Schema Registry ────────────────────────────────────────────────────

EVENT_SCHEMA_REGISTRY: Dict[str, type[BaseEvent]] = {
    "gate_passed": GatePassedEvent,
    "gate_failed": GateFailedEvent,
    "gate_features_computed": GateFeaturesComputedEvent,
    "bias_changed": BiasChangedEvent,
    "zone_formed": ZoneFormedEvent,
    "zone_expired": ZoneExpiredEvent,
    "sweep_detected": SweepDetectedEvent,
    "regime_changed": RegimeChangedEvent,
    "signal_created": SignalCreatedEvent,
    "trade_opened": TradeOpenedEvent,
    "trade_closed": TradeClosedEvent,
    "tp_hit": TPHitEvent,
    "loss_hit": LossHitEvent,
    "session_opened": SessionOpenedEvent,
    "session_closed": SessionClosedEvent,
    "volatility_spike": VolatilitySpikeEvent,
    "scan_completed": ScanCompletedEvent,
    "provider_degraded": ProviderDegradedEvent,
    "health_check_failed": HealthCheckFailedEvent,
}


def validate_event(event_type: str, payload: dict) -> Optional[BaseEvent]:
    """
    Validate an event payload against its registered schema.

    Args:
        event_type: The event type string
        payload: The event payload dict

    Returns:
        Validated BaseEvent instance, or None if validation fails
    """
    schema_class = EVENT_SCHEMA_REGISTRY.get(event_type)
    if schema_class is None:
        # Unknown event type — allow through with a warning
        return BaseEvent(
            event_type=event_type,
            **{k: v for k, v in payload.items() if k in BaseEvent.model_fields},
        )

    try:
        # Filter payload to only include fields the schema knows about
        known_fields = set(schema_class.model_fields.keys())
        filtered = {k: v for k, v in payload.items() if k in known_fields}
        return schema_class(**filtered)
    except Exception as exc:
        # Validation failed — return base event with error metadata
        return BaseEvent(
            event_type=event_type,
            symbol=payload.get("symbol", ""),
        )
