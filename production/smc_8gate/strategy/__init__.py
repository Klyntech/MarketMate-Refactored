"""
signal_engine.strategy
────────────────────
Unified strategy engine for MarketMate Refactored.

All strategy modules are available from this package:
  - models:       Domain dataclasses (Signal, GateResult, SweepResult, etc.)
  - engine:       SignalEngine — the unified gate pipeline + dedup + signal builder
  - bias:         HTF bias detection (Gate 4)
  - liquidity:    Liquidity sweep detection (Gate 5)
  - zones:        Entry zone identification (Gate 6)
  - confirmations: LTF confirmation detection (Gate 7)
  - gates:        News filter (Gate 3)
  - scoring:      Multi-factor confidence scoring
  - dedup:        ATR-relative deduplication
  - features:     Enriched feature dataclasses
"""

from signal_engine.strategy.models import (
    Signal,
    SweepResult,
    EntryZone,
    ConfirmResult,
    GateResult,
    DailyState,
    GateTraceEntry,
)
from signal_engine.strategy.engine import SignalEngine

__all__ = [
    "Signal",
    "SweepResult",
    "EntryZone",
    "ConfirmResult",
    "GateResult",
    "DailyState",
    "GateTraceEntry",
    "SignalEngine",
]
