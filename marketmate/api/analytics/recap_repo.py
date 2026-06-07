"""
marketmate/analytics/recap_repo.py
─────────────────────────────────
RecapRepo — MongoDB-only weekly recaps data access.

Migrated from db/recaps.py. AI-summarised weekly market recaps with
admin approval workflow.

Collection : weekly_recaps
No SQLite. MongoDB is the sole source of truth.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from marketmate.core.logger import get_logger
from marketmate.db.core import mongo_manager

log = get_logger("analytics.recap_repo")


class RecapRepo:
    """
    MongoDB-only repository for weekly recaps.

    Covers save, publish, discard, and retrieval operations.
    """

    def __init__(self) -> None:
        self._manager = mongo_manager

    async def _col(self):
        """Return weekly_recaps collection or None. Always safe."""
        try:
            db = await self._manager.get_db()
            return db["weekly_recaps"] if db is not None else None
        except Exception as exc:
            log.warning("recaps_col_unavailable", error=str(exc))
            return None

    # ═════════════════════════════════════════════════════════════════════════
    # Writes
    # ═════════════════════════════════════════════════════════════════════════

    async def save_recap(self, recap_data: dict) -> str:
        """
        Upsert a recap document by week_id.
        Returns the week_id on success, empty string on failure.
        """
        col = await self._col()
        if col is None:
            return ""
        try:
            week_id = recap_data["week_id"]
            recap_data.setdefault("created_at", datetime.now(timezone.utc))
            await col.find_one_and_update(
                {"week_id": week_id},
                {"$set": recap_data},
                upsert=True,
            )
            log.info("recap_saved", week_id=week_id, status=recap_data.get("status"))
            return week_id
        except Exception as exc:
            log.error("recap_save_failed", error=str(exc))
            return ""

    async def mark_published(self, week_id: str, ai_summary: str) -> bool:
        """Set status=published and store the AI summary. Returns True on success."""
        col = await self._col()
        if col is None:
            return False
        try:
            await col.update_one(
                {"week_id": week_id},
                {"$set": {
                    "status":       "published",
                    "ai_summary":   ai_summary,
                    "published_at": datetime.now(timezone.utc),
                }},
            )
            log.info("recap_published", week_id=week_id)
            return True
        except Exception as exc:
            log.error("recap_publish_failed", week_id=week_id, error=str(exc))
            return False

    async def mark_discarded(self, week_id: str) -> bool:
        """Set status=discarded. Returns True on success."""
        col = await self._col()
        if col is None:
            return False
        try:
            await col.update_one(
                {"week_id": week_id},
                {"$set": {"status": "discarded"}},
            )
            log.info("recap_discarded", week_id=week_id)
            return True
        except Exception as exc:
            log.error("recap_discard_failed", week_id=week_id, error=str(exc))
            return False

    # ═════════════════════════════════════════════════════════════════════════
    # Reads
    # ═════════════════════════════════════════════════════════════════════════

    async def get_latest_recap(self) -> Optional[dict]:
        """Return the most recent published recap, or None."""
        col = await self._col()
        if col is None:
            return None
        try:
            doc = await col.find_one(
                {"status": "published"},
                {"_id": 0},
                sort=[("created_at", -1)],
            )
            return doc
        except Exception as exc:
            log.error("get_latest_recap_failed", error=str(exc))
            return None

    async def get_recap_history(self, limit: int = 10) -> list[dict]:
        """Return the last N published recaps, newest first."""
        col = await self._col()
        if col is None:
            return []
        try:
            cursor = (
                col.find({"status": "published"}, {"_id": 0})
                .sort("created_at", -1)
                .limit(limit)
            )
            return await cursor.to_list(length=limit)
        except Exception as exc:
            log.error("get_recap_history_failed", error=str(exc))
            return []

    async def get_recap_by_week_id(self, week_id: str) -> Optional[dict]:
        """Return a specific published recap by week_id."""
        col = await self._col()
        if col is None:
            return None
        try:
            return await col.find_one(
                {"week_id": week_id, "status": "published"}, {"_id": 0}
            )
        except Exception as exc:
            log.error("get_recap_by_week_id_failed", week_id=week_id, error=str(exc))
            return None

    async def get_held_recap(self, week_id: str) -> Optional[dict]:
        """Return a held (pending admin approval) recap."""
        col = await self._col()
        if col is None:
            return None
        try:
            return await col.find_one(
                {"week_id": week_id, "status": "held"}, {"_id": 0}
            )
        except Exception as exc:
            log.error("get_held_recap_failed", week_id=week_id, error=str(exc))
            return None

    # ═════════════════════════════════════════════════════════════════════════
    # Indexes
    # ═════════════════════════════════════════════════════════════════════════

    async def ensure_indexes(self) -> None:
        """Create indexes on weekly_recaps. Safe to call repeatedly."""
        col = await self._col()
        if col is None:
            return
        from pymongo import ASCENDING, DESCENDING
        try:
            await col.create_index(
                [("week_id", ASCENDING)], unique=True, name="week_id_unique"
            )
            await col.create_index([("created_at", DESCENDING)])
            log.info("recaps_indexes_ensured")
        except Exception as exc:
            log.error("recaps_ensure_indexes_failed", error=str(exc))
