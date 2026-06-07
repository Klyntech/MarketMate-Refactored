"""
marketmate.virtual_account
───────────────────────────
Immutable Event-Sourced Virtual Accounting Engine.

All balances are DERIVED from event replay — never stored directly.
Periodic snapshots cache the computed balance for fast reads, but the
events are the single source of truth.

Collections:
  virtual_account_config    — account parameters (initial balance, risk%)
  virtual_account_events    — append-only event log (immutable)
  virtual_account_snapshots — periodic balance checkpoints (optimization)
  virtual_account_metrics   — precomputed performance metrics (7d/30d)

Rules:
  - 1% risk per trade, compounding
  - Event types: DEPOSIT, TRADE_OPENED, TRADE_CLOSED, DRAWDOWN_PAUSE, DRAWDOWN_RESUME
  - Snapshots taken every 50 events or every 24 hours (whichever first)
  - Metrics recomputed on every TRADE_CLOSED event
  - Never mutate events — append-only
"""

from marketmate.virtual_account.engine import VirtualAccountEngine
from marketmate.virtual_account.models import (
    AccountEvent,
    AccountEventType,
    AccountSnapshot,
    AccountMetrics,
    AccountConfig,
)
from marketmate.virtual_account.repos import (
    EventRepository,
    SnapshotRepository,
    MetricsRepository,
    ConfigRepository,
)

__all__ = [
    "VirtualAccountEngine",
    "AccountEvent",
    "AccountEventType",
    "AccountSnapshot",
    "AccountMetrics",
    "AccountConfig",
    "EventRepository",
    "SnapshotRepository",
    "MetricsRepository",
    "ConfigRepository",
]
