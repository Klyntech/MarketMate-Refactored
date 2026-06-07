"""
marketmate.strategy
────────────────────
Unified strategy engine for MarketMate.

All strategy modules are available from this package:
  - models:       Domain dataclasses (Signal, GateResult, SweepResult, etc.)
  - engine:       SignalEngine — the unified gate pipeline + dedup + signal builder
  - bias:         HTF bias detection (Gate 4)
  - liquidity:    Liquidity sweep detection (Gate 5)
  - zones:        Entry zone identification (Gate 6)
  - confirmations: LTF confirmation detection (Gate 7)
  - gates:        News filter (Gate 3)
"""

from marketmate.strategy.models import (
    Signal,
    SweepResult,
    EntryZone,
    ConfirmResult,
    GateResult,
    DailyState,
    GateTraceEntry,
)
from marketmate.strategy.engine import SignalEngine

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
