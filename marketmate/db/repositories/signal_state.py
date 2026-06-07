"""
marketmate/db/repositories/signal_state.py
──────────────────────────────────────────
SignalStateRepository — MongoDB-only signal deduplication persistence.

Migrated from db/signal_state.py + db/signals.py (signal_state collection).
One document per (symbol, direction) pair storing the last signal timestamp.
Prevents duplicate signals being sent after a restart.

No SQLite. MongoDB is the sole source of truth.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from marketmate.core.logger import get_logger
from marketmate.db.core import mongo_manager

log = get_logger("db.repositories.signal_state")


class SignalStateRepository:
    """
    MongoDB-only repository for signal deduplication state.

    One document per (symbol, direction) pair storing the last signal
    timestamp. Prevents duplicate signals after a restart.
    """

    def __init__(self) -> None:
        self._manager = mongo_manager

    async def _col(self):
        """Return signal_state collection or None. Always safe."""
        try:
            db = await self._manager.get_db()
            return db["signal_state"] if db is not None else None
        except Exception as exc:
            log.warning("signal_state_col_unavailable", error=str(exc))
            return None

    # ═════════════════════════════════════════════════════════════════════════
    # Reads
    # ═════════════════════════════════════════════════════════════════════════

    async def get_last_signal_time(self, symbol: str, direction: str) -> Optional[datetime]:
        """Return the UTC datetime of the last signal for a pair, or None."""
        col = await self._col()
        if col is None:
            return None
        try:
            doc = await col.find_one({"symbol": symbol, "direction": direction})
            if doc and "last_signal_at" in doc:
                ts = doc["last_signal_at"]
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
                return ts
        except Exception as exc:
            log.warning("signal_state_read_failed", symbol=symbol,
                        direction=direction, error=str(exc))
        return None

    # ═════════════════════════════════════════════════════════════════════════
    # Writes
    # ═════════════════════════════════════════════════════════════════════════

    async def set_last_signal_time(
        self, symbol: str, direction: str, timestamp: datetime
    ) -> None:
        """Upsert the last signal timestamp for a symbol/direction pair."""
        col = await self._col()
        if col is None:
            return
        try:
            if timestamp.tzinfo is None:
                timestamp = timestamp.replace(tzinfo=timezone.utc)

            await col.update_one(
                {"symbol": symbol, "direction": direction},
                {"$set": {"last_signal_at": timestamp}},
                upsert=True,
            )
            log.debug("signal_state_persisted", symbol=symbol, direction=direction)
        except Exception as exc:
            log.warning("signal_state_write_failed", symbol=symbol,
                        direction=direction, error=str(exc))

    # ═════════════════════════════════════════════════════════════════════════
    # Indexes
    # ═════════════════════════════════════════════════════════════════════════

    async def ensure_indexes(self) -> None:
        """Create indexes on signal_state collection. Safe to call repeatedly."""
        col = await self._col()
        if col is None:
            return
        from pymongo import ASCENDING
        try:
            await col.create_index(
                [("symbol", ASCENDING), ("direction", ASCENDING)],
                unique=True,
                name="symbol_direction_unique",
            )
        except Exception as exc:
            log.warning("signal_state_index_warning", error=str(exc))
        log.debug("signal_state_indexes_ensured")
