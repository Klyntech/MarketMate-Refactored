"""
signal_engine.db.repositories
──────────────────────────────
MongoDB-only repository layer for signal persistence.

Repositories:
  SignalRepository         — signal_archive + operational signal queries
  SignalStateRepository    — signal deduplication state
"""

from signal_engine.db.repositories.signals import SignalRepository
from signal_engine.db.repositories.signal_state import SignalStateRepository

__all__ = [
    "SignalRepository",
    "SignalStateRepository",
]
