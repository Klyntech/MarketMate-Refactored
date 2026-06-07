"""
signal_engine.db
────────────────
MongoDB-only database layer for MarketMate Refactored.

This package provides:
  - connect_all()  → initializes MongoDB collections and indexes
  - close_all()    → gracefully shuts down all connections
  - Repository singletons for signals and signal_state

MongoDB is optional — the engine runs without persistence if not configured.
"""

from __future__ import annotations

from signal_engine.core.logger import get_logger
from signal_engine.db.core import mongo_manager, db_cache

log = get_logger("db")

# ─── Repository singletons ────────────────────────────────────────────────────

_signals_repo = None
_signal_state_repo = None


def get_signals_repo():
    """Return the SignalRepository singleton."""
    global _signals_repo
    if _signals_repo is None:
        from signal_engine.db.repositories.signals import SignalRepository
        _signals_repo = SignalRepository()
    return _signals_repo


def get_signal_state_repo():
    """Return the SignalStateRepository singleton."""
    global _signal_state_repo
    if _signal_state_repo is None:
        from signal_engine.db.repositories.signal_state import SignalStateRepository
        _signal_state_repo = SignalStateRepository()
    return _signal_state_repo


# ═══════════════════════════════════════════════════════════════════════════════
# Startup / Shutdown
# ═══════════════════════════════════════════════════════════════════════════════

async def connect_all() -> bool:
    """
    Initialize all MongoDB collections and indexes.

    Call once at application startup.
    Returns True if the core MongoDB connection succeeded.
    Returns False if MongoDB is unavailable (engine continues without persistence).
    """
    connected = await mongo_manager.connect()
    if not connected:
        log.warning("connect_all_mongodb_unavailable",
                    hint="Engine will run without persistence")
        return False

    # Create indexes on signal collections
    index_tasks = [
        ("signal_archive",    get_signals_repo().ensure_indexes),
        ("signal_state",      get_signal_state_repo().ensure_indexes),
    ]

    for name, fn in index_tasks:
        try:
            await fn()
            log.debug("connect_all_index_ok", collection=name)
        except Exception as exc:
            log.warning("connect_all_index_failed", collection=name, error=str(exc))

    # Also initialize the candle cache indexes
    try:
        from signal_engine.data.cache import connect as cache_connect
        await cache_connect(mongo_manager)
    except Exception as exc:
        log.warning("connect_all_cache_indexes_failed", error=str(exc))

    log.info("connect_all_complete", collections=len(index_tasks))
    return True


async def close_all() -> None:
    """
    Gracefully shut down all database connections.
    Call once at application shutdown.
    """
    await db_cache.clear()
    await mongo_manager.close()
    log.info("close_all_complete")
