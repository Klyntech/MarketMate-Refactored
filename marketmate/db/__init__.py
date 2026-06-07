"""
marketmate/db
─────────────
MongoDB-only database layer for MarketMate.

This package provides:
  - connect_all()  → initializes all MongoDB collections and indexes
  - close_all()    → gracefully shuts down all connections
  - Repository singletons for each domain

No SQLite. No reconciliation. MongoDB is the sole source of truth.
"""

from __future__ import annotations

from marketmate.core.logger import get_logger
from marketmate.db.core import mongo_manager, db_cache

log = get_logger("db")

# ─── Repository singletons ────────────────────────────────────────────────────
# Lazy-initialized to avoid import-time side effects.

_signals_repo = None
_subscribers_repo = None
_trading_accounts_repo = None
_training_repo = None
_audit_repo = None
_signal_state_repo = None


def get_signals_repo():
    """Return the SignalRepository singleton."""
    global _signals_repo
    if _signals_repo is None:
        from marketmate.db.repositories.signals import SignalRepository
        _signals_repo = SignalRepository()
    return _signals_repo


def get_subscribers_repo():
    """Return the SubscriberRepository singleton."""
    global _subscribers_repo
    if _subscribers_repo is None:
        from marketmate.db.repositories.subscribers import SubscriberRepository
        _subscribers_repo = SubscriberRepository()
    return _subscribers_repo


def get_trading_accounts_repo():
    """Return the TradingAccountRepository singleton."""
    global _trading_accounts_repo
    if _trading_accounts_repo is None:
        from marketmate.db.repositories.trading_accounts import TradingAccountRepository
        _trading_accounts_repo = TradingAccountRepository()
    return _trading_accounts_repo


def get_training_repo():
    """Return the TrainingRepository singleton."""
    global _training_repo
    if _training_repo is None:
        from marketmate.db.repositories.training import TrainingRepository
        _training_repo = TrainingRepository()
    return _training_repo


def get_audit_repo():
    """Return the AuditRepository singleton."""
    global _audit_repo
    if _audit_repo is None:
        from marketmate.db.repositories.audit import AuditRepository
        _audit_repo = AuditRepository()
    return _audit_repo


def get_signal_state_repo():
    """Return the SignalStateRepository singleton."""
    global _signal_state_repo
    if _signal_state_repo is None:
        from marketmate.db.repositories.signal_state import SignalStateRepository
        _signal_state_repo = SignalStateRepository()
    return _signal_state_repo


# ─── Platform / Analytics repos (also lazy) ───────────────────────────────────

_academy_repo = None
_social_repo = None
_recap_repo = None
_proximity_repo = None


def get_academy_repo():
    """Return the AcademyRepo singleton."""
    global _academy_repo
    if _academy_repo is None:
        from marketmate.platform.academy_repo import AcademyRepo
        _academy_repo = AcademyRepo()
    return _academy_repo


def get_social_repo():
    """Return the SocialRepo singleton."""
    global _social_repo
    if _social_repo is None:
        from marketmate.platform.social_repo import SocialRepo
        _social_repo = SocialRepo()
    return _social_repo


def get_recap_repo():
    """Return the RecapRepo singleton."""
    global _recap_repo
    if _recap_repo is None:
        from marketmate.analytics.recap_repo import RecapRepo
        _recap_repo = RecapRepo()
    return _recap_repo


def get_proximity_repo():
    """Return the ProximityRepo singleton."""
    global _proximity_repo
    if _proximity_repo is None:
        from marketmate.analytics.proximity import ProximityRepo
        _proximity_repo = ProximityRepo()
    return _proximity_repo


# ═══════════════════════════════════════════════════════════════════════════════
# Startup / Shutdown
# ═══════════════════════════════════════════════════════════════════════════════

async def connect_all() -> bool:
    """
    Initialize all MongoDB collections and indexes.

    Call once at application startup (from lifespan handler).
    Returns True if the core MongoDB connection succeeded.
    """
    # 1. Connect the shared MongoDB client
    connected = await mongo_manager.connect()
    if not connected:
        log.warning("connect_all_mongodb_unavailable",
                    hint="All repositories will degrade gracefully")
        return False

    # 2. Create indexes on all collections
    #    Each ensure_indexes() is safe to call repeatedly and catches its own errors.
    index_tasks = [
        ("signal_archive",    get_signals_repo().ensure_indexes),
        ("subscribers",       get_subscribers_repo().ensure_indexes),
        ("trading_accounts",  get_trading_accounts_repo().ensure_indexes),
        ("training_data",     get_training_repo().ensure_indexes),
        ("audit",             get_audit_repo().ensure_indexes),
        ("signal_state",      get_signal_state_repo().ensure_indexes),
        ("academy",           get_academy_repo().ensure_indexes),
        ("social",            get_social_repo().ensure_indexes),
        ("recaps",            get_recap_repo().ensure_indexes),
        ("proximity",         get_proximity_repo().ensure_indexes),
    ]

    for name, fn in index_tasks:
        try:
            await fn()
            log.debug("connect_all_index_ok", collection=name)
        except Exception as exc:
            log.warning("connect_all_index_failed", collection=name, error=str(exc))

    log.info("connect_all_complete",
             collections=len(index_tasks),
             hint="MongoDB-only mode — no SQLite, no reconciliation")
    return True


async def close_all() -> None:
    """
    Gracefully shut down all database connections.

    Call once at application shutdown (from lifespan finally block).
    """
    # Clear the in-memory cache
    await db_cache.clear()

    # Close the shared MongoDB client
    await mongo_manager.close()

    log.info("close_all_complete")
