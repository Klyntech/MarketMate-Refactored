"""
signal_engine/strategy/models.py
──────────────────────────────
Typed domain models for the MarketMate strategy engine.

All dataclasses used across the strategy pipeline are centralised here so
every module imports from a single canonical location.  Each model exposes
a ``to_dict()`` method for serialisation (MongoDB persistence, API payloads,
logging, etc.).

Migrated from:
  - signals/builder.py       → Signal
  - strategy/liquidity.py    → SweepResult
  - strategy/entry_zones.py  → EntryZone
  - strategy/ltf_confirm.py  → ConfirmResult
  - strategy/gates.py        → GateResult, DailyState

New:
  - GateTraceEntry   — structured gate trace record
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional


# ─── SweepResult ─────────────────────────────────────────────────────────────

@dataclass
class SweepResult:
    """Result of a liquidity sweep detection (Gate 5)."""
    type: str              # "buy" | "sell"  (matches bias direction)
    direction: str         # "bullish" | "bearish"  (backward-compat alias)
    swept_level: float     # price of the swing level that was swept
    sweep_candle_idx: int  # DataFrame row index of the sweep candle
    close_inside: bool     # True if candle closed back inside the level
    strength: str          # "strong" | "weak"
    candles_ago: int       # distance from most-recent candle
    sweep_distance: float  # absolute distance the wick moved beyond level

    def to_dict(self) -> Dict[str, Any]:
        return {
            "type":             self.type,
            "direction":        self.direction,
            "swept_level":      round(self.swept_level, 6),
            "sweep_candle_idx": self.sweep_candle_idx,
            "close_inside":     self.close_inside,
            "strength":         self.strength,
            "candles_ago":      self.candles_ago,
            "sweep_distance":   round(self.sweep_distance, 6),
        }


# ─── EntryZone ───────────────────────────────────────────────────────────────

@dataclass
class EntryZone:
    """Result of entry zone identification (Gate 6)."""
    zone_type: str        # "order_block" | "fvg"
    direction: str        # "bullish" | "bearish"
    zone_high: float
    zone_low: float
    zone_mid: float = 0.0
    candle_idx: int = 0
    expiry_candle: int = 0   # OB only
    valid: bool = True

    def __post_init__(self) -> None:
        self.zone_mid = (self.zone_high + self.zone_low) / 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "zone_type":    self.zone_type,
            "direction":    self.direction,
            "zone_high":    round(self.zone_high, 6),
            "zone_low":     round(self.zone_low, 6),
            "zone_mid":     round(self.zone_mid, 6),
            "candle_idx":   self.candle_idx,
            "expiry_candle": self.expiry_candle,
            "valid":        self.valid,
        }


# ─── ConfirmResult ───────────────────────────────────────────────────────────

@dataclass
class ConfirmResult:
    """Result of lower-timeframe confirmation (Gate 7)."""
    signal_type: str     # "BOS" | "CHoCH"
    direction: str       # "bullish" | "bearish"
    break_level: float   # price that was broken
    confirm_candle: int  # candle index where break occurred
    timeframe: str       # "M15" | "M5"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "signal_type":   self.signal_type,
            "direction":     self.direction,
            "break_level":   round(self.break_level, 6),
            "confirm_candle": self.confirm_candle,
            "timeframe":     self.timeframe,
        }


# ─── GateTraceEntry ──────────────────────────────────────────────────────────

@dataclass
class GateTraceEntry:
    """Structured record for a single gate pass/fail event."""
    gate: str                       # e.g. "G1_SESSION", "G5_SWEEP"
    status: str                     # "pass" | "fail"
    reason: Optional[str] = None    # Human-readable reason (fail only)
    values: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "gate":      self.gate,
            "status":    self.status,
            "timestamp": self.timestamp,
            "values":    self.values,
        }
        if self.reason is not None:
            d["reason"] = self.reason
        return d


# ─── GateResult ──────────────────────────────────────────────────────────────

@dataclass
class GateResult:
    """Full result of the 8-gate pipeline."""
    passed: bool
    failed_at: Optional[str] = None
    reason: Optional[str] = None
    trace: List[Dict[str, Any]] = field(default_factory=list)

    # Populated only when passed=True
    symbol: str = ""
    direction: str = ""
    bias: str = ""
    sweep: Optional[SweepResult] = None
    zone: Optional[EntryZone] = None
    confirm: Optional[ConfirmResult] = None
    entry_low: float = 0.0
    entry_high: float = 0.0
    stop_loss: float = 0.0
    tp1: float = 0.0
    tp2: float = 0.0
    tp3: float = 0.0
    rr: float = 0.0
    confidence: str = ""
    position_size: float = 0.0
    # H4 candle timestamp for same-candle dedup
    h4_candle_ts: str = ""

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "passed":     self.passed,
            "failed_at":  self.failed_at,
            "reason":     self.reason,
            "symbol":     self.symbol,
            "direction":  self.direction,
            "bias":       self.bias,
            "entry_low":  self.entry_low,
            "entry_high": self.entry_high,
            "stop_loss":  self.stop_loss,
            "tp1":        self.tp1,
            "tp2":        self.tp2,
            "tp3":        self.tp3,
            "rr":         self.rr,
            "confidence": self.confidence,
            "position_size": self.position_size,
            "h4_candle_ts":  self.h4_candle_ts,
        }
        if self.sweep is not None:
            d["sweep"] = self.sweep.to_dict()
        if self.zone is not None:
            d["zone"] = self.zone.to_dict()
        if self.confirm is not None:
            d["confirm"] = self.confirm.to_dict()
        d["trace"] = self.trace
        return d


# ─── DailyState ──────────────────────────────────────────────────────────────

@dataclass
class DailyState:
    """Daily trading limits and drawdown state (Gate 2)."""
    trades_today: int = 0
    consecutive_losses: int = 0
    buy_trades_today: int = 0
    sell_trades_today: int = 0

    def to_dict(self) -> Dict[str, Any]:
        return {
            "trades_today":       self.trades_today,
            "consecutive_losses": self.consecutive_losses,
            "buy_trades_today":   self.buy_trades_today,
            "sell_trades_today":  self.sell_trades_today,
        }


# ─── Signal ──────────────────────────────────────────────────────────────────

@dataclass
class Signal:
    """Canonical trade record used throughout the system."""
    # ── Identity ───────────────────────────────────────────────────────────
    id: str = field(default_factory=lambda: str(uuid.uuid4())[:8].upper())
    created_at: datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    # ── Trade Parameters ───────────────────────────────────────────────────
    symbol: str = ""
    direction: str = ""          # "BUY" | "SELL"

    entry_low: float  = 0.0     # Entry zone lower bound
    entry_high: float = 0.0     # Entry zone upper bound
    entry_mid: float  = 0.0     # Suggested entry (midpoint)

    stop_loss: float = 0.0
    tp1: float = 0.0            # 1:1 RR
    tp2: float = 0.0            # 1:2 RR
    tp3: Optional[float] = None # Next liquidity

    rr: float = 0.0
    position_size: float = 0.0  # Base units

    # ── Context ────────────────────────────────────────────────────────────
    timeframe: str = "H4"
    confidence: str = ""         # "HIGH" | "MEDIUM" | "LOW"  (legacy tier)
    zone_type: str = ""          # "order_block" | "fvg"
    confirm_type: str = ""       # "BOS" | "CHoCH"
    confirm_tf: str = ""         # "M5" | "M15"
    swept_level: float = 0.0

    # ── Status ─────────────────────────────────────────────────────────────
    status: str = "PENDING"      # PENDING -> OPEN -> RUNNING -> CLOSED

    # ── Version ────────────────────────────────────────────────────────────
    strategy_version: str = ""   # e.g. "MarketMate v2.1"

    def to_dict(self) -> Dict[str, Any]:
        result: Dict[str, Any] = {
            "id":            self.id,
            "created_at":    self.created_at.isoformat(),
            "symbol":        self.symbol,
            "direction":     self.direction,
            "entry_low":     self.entry_low,
            "entry_high":    self.entry_high,
            "entry_mid":     self.entry_mid,
            "stop_loss":     self.stop_loss,
            "tp1":           self.tp1,
            "tp2":           self.tp2,
            "tp3":           self.tp3,
            "rr":            self.rr,
            "position_size": self.position_size,
            "timeframe":     self.timeframe,
            "confidence":    self.confidence,
            "zone_type":     self.zone_type,
            "confirm_type":  self.confirm_type,
            "confirm_tf":    self.confirm_tf,
            "swept_level":   self.swept_level,
            "status":        self.status,
            "strategy_version": self.strategy_version,
        }

        return result
