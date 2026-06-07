"""
marketmate/db/repositories
──────────────────────────
MongoDB-only repository layer. Each repository encapsulates all database
operations for a single domain collection.

No SQLite. No reconciliation. MongoDB is the sole source of truth.

Repositories:
  SignalRepository         — signal_archive + operational signal queries
  SubscriberRepository     — subscriber CRUD + state management
  TradingAccountRepository — MT5 account linkage
  TrainingRepository       — ML training data with gate dedup
  AuditRepository          — append-only audit trail
  SignalStateRepository    — signal deduplication state
"""

from marketmate.db.repositories.signals import SignalRepository
from marketmate.db.repositories.subscribers import SubscriberRepository
from marketmate.db.repositories.trading_accounts import TradingAccountRepository, trading_account_store
from marketmate.db.repositories.training import TrainingRepository, training_logger
from marketmate.db.repositories.audit import AuditRepository
from marketmate.db.repositories.signal_state import SignalStateRepository

# ── Backward-compatible aliases (v4→v6 migration) ──────────────────────────
# Some older code uses get_signal_repo / get_subscriber_repo (singular).
# These redirect to the canonical lazy singletons in marketmate.db.

def get_signal_repo():
    """Alias for get_signals_repo() — backward compatibility."""
    from marketmate.db import get_signals_repo
    return get_signals_repo()

def get_subscriber_repo():
    """Alias for get_subscribers_repo() — backward compatibility."""
    from marketmate.db import get_subscribers_repo
    return get_subscribers_repo()


__all__ = [
    "SignalRepository",
    "SubscriberRepository",
    "TradingAccountRepository",
    "TrainingRepository",
    "AuditRepository",
    "SignalStateRepository",
    "training_logger",
    "trading_account_store",
    "get_signal_repo",
    "get_subscriber_repo",
]
