"""
marketmate/platform/social_repo.py
──────────────────────────────────
SocialRepo — MongoDB-only pending social posts management.

Migrated from db/social.py. AI-generated social posts are drafted here
and held until an admin approves them.

Collection : pending_social_posts
No SQLite. MongoDB is the sole source of truth.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from marketmate.core.logger import get_logger
from marketmate.db.core import mongo_manager

log = get_logger("platform.social_repo")


class SocialRepo:
    """
    MongoDB-only repository for pending social posts.

    Covers post creation, approval, rejection, publishing, and retrieval.
    """

    def __init__(self) -> None:
        self._manager = mongo_manager

    async def _col(self):
        """Return pending_social_posts collection or None. Always safe."""
        try:
            db = await self._manager.get_db()
            return db["pending_social_posts"] if db is not None else None
        except Exception as exc:
            log.warning("social_col_unavailable", error=str(exc))
            return None

    # ═════════════════════════════════════════════════════════════════════════
    # Writes
    # ═════════════════════════════════════════════════════════════════════════

    async def create_post(
        self,
        post_type:     str,
        content:       str,
        platforms:     list[str],
        scheduled_for: Optional[datetime] = None,
    ) -> str:
        """
        Create a new draft post awaiting admin approval.
        Returns the post_id on success, empty string on failure.
        """
        col = await self._col()
        if col is None:
            return ""
        try:
            post_id = str(uuid.uuid4())
            await col.insert_one({
                "post_id":       post_id,
                "type":          post_type,
                "content":       content,
                "platforms":     platforms,
                "scheduled_for": scheduled_for,
                "status":        "pending",
                "created_at":    datetime.now(timezone.utc),
                "approved_at":   None,
                "published_at":  None,
                "rejected_at":   None,
                "rejection_note": None,
            })
            log.info("social_post_created", post_id=post_id, type=post_type)
            return post_id
        except Exception as exc:
            log.error("create_post_failed", error=str(exc))
            return ""

    async def approve_post(self, post_id: str) -> bool:
        """Admin approves a pending post. Returns True on success."""
        col = await self._col()
        if col is None:
            return False
        try:
            result = await col.update_one(
                {"post_id": post_id, "status": "pending"},
                {"$set": {
                    "status":      "approved",
                    "approved_at": datetime.now(timezone.utc),
                }},
            )
            success = result.modified_count > 0
            if success:
                log.info("post_approved", post_id=post_id)
            return success
        except Exception as exc:
            log.error("approve_post_failed", post_id=post_id, error=str(exc))
            return False

    async def reject_post(self, post_id: str, note: Optional[str] = None) -> bool:
        """Admin rejects a pending post. Returns True on success."""
        col = await self._col()
        if col is None:
            return False
        try:
            result = await col.update_one(
                {"post_id": post_id, "status": "pending"},
                {"$set": {
                    "status":         "rejected",
                    "rejected_at":    datetime.now(timezone.utc),
                    "rejection_note": note,
                }},
            )
            success = result.modified_count > 0
            if success:
                log.info("post_rejected", post_id=post_id)
            return success
        except Exception as exc:
            log.error("reject_post_failed", post_id=post_id, error=str(exc))
            return False

    async def mark_published(self, post_id: str) -> bool:
        """Mark an approved post as published. Returns True on success."""
        col = await self._col()
        if col is None:
            return False
        try:
            result = await col.update_one(
                {"post_id": post_id, "status": "approved"},
                {"$set": {
                    "status":       "published",
                    "published_at": datetime.now(timezone.utc),
                }},
            )
            success = result.modified_count > 0
            if success:
                log.info("post_published", post_id=post_id)
            return success
        except Exception as exc:
            log.error("mark_published_failed", post_id=post_id, error=str(exc))
            return False

    # ═════════════════════════════════════════════════════════════════════════
    # Reads
    # ═════════════════════════════════════════════════════════════════════════

    async def get_pending_posts(self) -> list[dict]:
        """Return all posts awaiting admin approval, oldest first."""
        col = await self._col()
        if col is None:
            return []
        try:
            cursor = col.find(
                {"status": "pending"}, {"_id": 0}
            ).sort("created_at", 1)
            return await cursor.to_list(length=200)
        except Exception as exc:
            log.error("get_pending_posts_failed", error=str(exc))
            return []

    async def get_due_posts(self) -> list[dict]:
        """Return approved posts whose scheduled_for is now or in the past."""
        col = await self._col()
        if col is None:
            return []
        try:
            now = datetime.now(timezone.utc)
            cursor = col.find(
                {
                    "status": "approved",
                    "$or": [
                        {"scheduled_for": None},
                        {"scheduled_for": {"$lte": now}},
                    ],
                },
                {"_id": 0},
            ).sort("scheduled_for", 1)
            return await cursor.to_list(length=100)
        except Exception as exc:
            log.error("get_due_posts_failed", error=str(exc))
            return []

    async def get_post(self, post_id: str) -> Optional[dict]:
        """Return a single post document by post_id."""
        col = await self._col()
        if col is None:
            return None
        try:
            return await col.find_one({"post_id": post_id}, {"_id": 0})
        except Exception as exc:
            log.error("get_post_failed", post_id=post_id, error=str(exc))
            return None

    # ═════════════════════════════════════════════════════════════════════════
    # Indexes
    # ═════════════════════════════════════════════════════════════════════════

    async def ensure_indexes(self) -> None:
        """Create indexes on pending_social_posts. Safe to call repeatedly."""
        col = await self._col()
        if col is None:
            return
        from pymongo import ASCENDING
        try:
            await col.create_index(
                [("post_id", ASCENDING)], unique=True, name="post_id_unique"
            )
            await col.create_index([("status", ASCENDING)])
            await col.create_index([("scheduled_for", ASCENDING)])
            log.info("social_indexes_ensured")
        except Exception as exc:
            log.error("social_ensure_indexes_failed", error=str(exc))
