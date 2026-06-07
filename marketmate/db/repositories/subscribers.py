"""
marketmate/db/repositories/subscribers.py
──────────────────────────────────────────
SubscriberRepository — MongoDB-only subscriber management.

Migrated from db/users.py + db/subscribers.py + db/mongo_subscribers.py.
Combines the operational SQLite store and the durable MongoDB store into
a single MongoDB-only implementation.

No SQLite. No reconciliation needed. MongoDB is the sole source of truth.

Subscriber states:
  trial    → 7-day free access, auto-expires
  pending  → payment submitted, awaiting admin approval
  active   → paid and approved, 30-day clock running
  expired  → subscription lapsed, locked out
  banned   → permanently blocked
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.db.core import mongo_manager

log = get_logger("db.repositories.subscribers")


class SubscriberRepository:
    """
    MongoDB-only repository for subscriber CRUD and state management.

    All operations go directly to MongoDB — no SQLite, no reconciliation.
    Every method is safe to call when MongoDB is unavailable and returns
    a graceful sentinel (None, [], False).
    """

    def __init__(self) -> None:
        self._manager = mongo_manager

    async def _col(self):
        """Return subscribers collection or None. Always safe."""
        try:
            db = await self._manager.get_db()
            return db["subscribers"] if db is not None else None
        except Exception as exc:
            log.warning("subscribers_col_unavailable", error=str(exc))
            return None

    # ═════════════════════════════════════════════════════════════════════════
    # Writes
    # ═════════════════════════════════════════════════════════════════════════

    async def upsert(
        self,
        chat_id:    str,
        status:     str,
        plan:       str,
        username:   str                = "",
        full_name:  str                = "",
        expires_at: Optional[datetime] = None,
        started_at: Optional[datetime] = None,
    ) -> None:
        """
        Insert or update a subscriber record.
        Called on every state change. Failure is logged but never crashes caller.
        """
        col = await self._col()
        if col is None:
            return
        try:
            now = datetime.now(timezone.utc)
            set_fields: dict = {
                "chat_id":    chat_id,
                "status":     status.upper(),
                "plan":       plan,
                "username":   username,
                "full_name":  full_name,
                "expires_at": expires_at,
                "updated_at": now,
            }
            # Only write started_at when explicitly provided so that calls
            # that don't carry this value (expire, ban) never erase it.
            if started_at is not None:
                set_fields["started_at"] = started_at

            await col.update_one(
                {"chat_id": chat_id},
                {
                    "$set":         set_fields,
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
            log.debug("subscriber_upserted", chat_id=chat_id, status=status)
        except Exception as exc:
            log.error("subscriber_upsert_failed", chat_id=chat_id, error=str(exc))

    async def create_trial(
        self,
        chat_id:   str,
        username:  str,
        full_name: str,
    ) -> Optional[dict]:
        """
        Create a new trial subscriber.
        Returns the subscriber dict on success.
        """
        now        = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=cfg.subscription.trial_days)

        col = await self._col()
        if col is None:
            return None
        try:
            await col.update_one(
                {"chat_id": chat_id},
                {
                    "$set": {
                        "chat_id":    chat_id,
                        "status":     "TRIAL",
                        "plan":       "trial",
                        "username":   username,
                        "full_name":  full_name,
                        "started_at": now,
                        "expires_at": expires_at,
                        "trial_used": True,
                        "updated_at": now,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
            log.info("trial_created", chat_id=chat_id, expires=expires_at.isoformat())
            return await self.get_by_chat_id(chat_id)
        except Exception as exc:
            log.error("create_trial_failed", chat_id=chat_id, error=str(exc))
            return None

    async def set_pending(
        self,
        chat_id:     str,
        username:    str,
        full_name:   str,
        payment_ref: str,
    ) -> None:
        """Mark a user as pending after they submit payment proof."""
        now = datetime.now(timezone.utc)
        col = await self._col()
        if col is None:
            return
        try:
            await col.update_one(
                {"chat_id": chat_id},
                {
                    "$set": {
                        "chat_id":     chat_id,
                        "status":      "PENDING",
                        "plan":        "monthly",
                        "username":    username,
                        "full_name":   full_name,
                        "payment_ref": payment_ref,
                        "updated_at":  now,
                    },
                    "$setOnInsert": {"created_at": now},
                },
                upsert=True,
            )
            log.info("subscriber_pending", chat_id=chat_id)
        except Exception as exc:
            log.error("set_pending_failed", chat_id=chat_id, error=str(exc))

    async def approve(
        self,
        chat_id:  str,
        admin_id: str,
        days:     int = 30,
    ) -> Optional[dict]:
        """
        Approve a subscriber. Sets status to ACTIVE, N-day expiry.
        Returns updated subscriber dict.
        """
        now        = datetime.now(timezone.utc)
        expires_at = now + timedelta(days=days)

        col = await self._col()
        if col is None:
            return None
        try:
            await col.update_one(
                {"chat_id": chat_id},
                {
                    "$set": {
                        "status":       "ACTIVE",
                        "plan":         "monthly",
                        "started_at":   now,
                        "expires_at":   expires_at,
                        "approved_by":  admin_id,
                        "approved_at":  now,
                        "reminder_d27": False,
                        "reminder_d29": False,
                        "updated_at":   now,
                    },
                },
            )
            log.info("subscriber_approved", chat_id=chat_id,
                     admin=admin_id, expires=expires_at.isoformat())
            return await self.get_by_chat_id(chat_id)
        except Exception as exc:
            log.error("approve_failed", chat_id=chat_id, error=str(exc))
            return None

    async def ban(self, chat_id: str) -> None:
        """Permanently ban a subscriber."""
        col = await self._col()
        if col is None:
            return
        try:
            await col.update_one(
                {"chat_id": chat_id},
                {"$set": {"status": "BANNED", "updated_at": datetime.now(timezone.utc)}},
            )
            log.info("subscriber_banned", chat_id=chat_id)
        except Exception as exc:
            log.error("ban_failed", chat_id=chat_id, error=str(exc))

    async def expire(self, chat_id: str) -> None:
        """Mark a subscriber as expired."""
        col = await self._col()
        if col is None:
            return
        try:
            await col.update_one(
                {"chat_id": chat_id},
                {"$set": {"status": "EXPIRED", "updated_at": datetime.now(timezone.utc)}},
            )
            log.info("subscriber_expired", chat_id=chat_id)
        except Exception as exc:
            log.error("expire_failed", chat_id=chat_id, error=str(exc))

    async def extend(self, chat_id: str, days: int) -> Optional[dict]:
        """Add `days` to a subscriber's current expiry date."""
        sub = await self.get_by_chat_id(chat_id)
        if not sub:
            return None

        current_expiry = sub.get("expires_at")
        if current_expiry:
            if isinstance(current_expiry, str):
                base = datetime.fromisoformat(current_expiry)
            else:
                base = current_expiry
            if base.tzinfo is None:
                base = base.replace(tzinfo=timezone.utc)
        else:
            base = datetime.now(timezone.utc)

        new_expiry = base + timedelta(days=days)

        col = await self._col()
        if col is None:
            return None
        try:
            await col.update_one(
                {"chat_id": chat_id},
                {"$set": {"expires_at": new_expiry, "updated_at": datetime.now(timezone.utc)}},
            )
            log.info("subscription_extended", chat_id=chat_id, days=days,
                     new_expiry=new_expiry.isoformat())
            return await self.get_by_chat_id(chat_id)
        except Exception as exc:
            log.error("extend_failed", chat_id=chat_id, error=str(exc))
            return None

    async def reject(self, chat_id: str) -> None:
        """Reject a pending subscriber (sets back to expired)."""
        sub = await self.get_by_chat_id(chat_id)
        if not sub:
            return
        await self.expire(chat_id)
        log.info("subscriber_rejected", chat_id=chat_id)

    # ═════════════════════════════════════════════════════════════════════════
    # Reads
    # ═════════════════════════════════════════════════════════════════════════

    async def get_by_chat_id(self, chat_id: str) -> Optional[dict]:
        """Return one subscriber document by chat_id, or None."""
        col = await self._col()
        if col is None:
            return None
        try:
            doc = await col.find_one({"chat_id": chat_id}, {"_id": 0})
            if doc:
                # Normalize status to lowercase for compatibility
                doc["status_lower"] = (doc.get("status") or "").lower()
            return doc
        except Exception as exc:
            log.error("subscriber_get_failed", chat_id=chat_id, error=str(exc))
            return None

    async def get_active_chat_ids(self) -> list[str]:
        """
        Return chat_ids of all ACTIVE/TRIAL subscribers with valid expiry.
        This is the primary method for signal dispatch targeting.
        """
        col = await self._col()
        if col is None:
            return []
        try:
            now = datetime.now(timezone.utc)
            cursor = col.find(
                {
                    "status": {"$in": ["ACTIVE", "TRIAL"]},
                    "$or": [
                        {"expires_at": None},
                        {"expires_at": {"$gt": now}},
                    ],
                },
                {"chat_id": 1, "_id": 0},
            )
            docs = await cursor.to_list(length=10_000)
            ids = [d["chat_id"] for d in docs]
            log.debug("active_chat_ids_fetched", count=len(ids))
            return ids
        except Exception as exc:
            log.error("active_chat_ids_failed", error=str(exc))
            return []

    async def get_all_active(self) -> list[dict]:
        """Return all ACTIVE/TRIAL docs with valid expiry."""
        col = await self._col()
        if col is None:
            return []
        try:
            now = datetime.now(timezone.utc)
            cursor = col.find(
                {
                    "status": {"$in": ["ACTIVE", "TRIAL"]},
                    "$or": [
                        {"expires_at": None},
                        {"expires_at": {"$gt": now}},
                    ],
                },
                {"_id": 0},
            ).sort("created_at", -1)
            docs = await cursor.to_list(length=10_000)
            return docs
        except Exception as exc:
            log.error("get_all_active_failed", error=str(exc))
            return []

    async def is_active(self, chat_id: str) -> bool:
        """
        Return True if the subscriber has a valid active or trial subscription.
        Also handles expiry: if trial/active but expired_at has passed, returns False.
        """
        sub = await self.get_by_chat_id(chat_id)
        if not sub:
            return False
        status = (sub.get("status") or "").upper()
        if status in ("BANNED", "EXPIRED", "PENDING"):
            return False
        if status in ("TRIAL", "ACTIVE"):
            expires_at = sub.get("expires_at")
            if expires_at:
                if isinstance(expires_at, str):
                    expiry = datetime.fromisoformat(expires_at)
                else:
                    expiry = expires_at
                if expiry.tzinfo is None:
                    expiry = expiry.replace(tzinfo=timezone.utc)
                if datetime.now(timezone.utc) > expiry:
                    return False
            return True
        return False

    async def has_used_trial(self, chat_id: str) -> bool:
        """Return True if this chat_id has already started a trial."""
        sub = await self.get_by_chat_id(chat_id)
        return bool(sub and sub.get("trial_used"))

    async def get_expiring_soon(self, days_ahead: int) -> list[dict]:
        """
        Return subscribers whose subscription expires within `days_ahead` days.
        Used by the daily reminder loop.
        """
        col = await self._col()
        if col is None:
            return []
        try:
            now    = datetime.now(timezone.utc)
            cutoff = now + timedelta(days=days_ahead)
            cursor = col.find(
                {
                    "status": {"$in": ["ACTIVE", "TRIAL"]},
                    "expires_at": {"$gt": now, "$lte": cutoff},
                },
                {"_id": 0},
            )
            return await cursor.to_list(length=1_000)
        except Exception as exc:
            log.error("get_expiring_soon_failed", days_ahead=days_ahead, error=str(exc))
            return []

    # ═════════════════════════════════════════════════════════════════════════
    # Reminders
    # ═════════════════════════════════════════════════════════════════════════

    async def mark_reminder_sent(self, chat_id: str, reminder_key: str) -> None:
        """
        Mark a reminder as sent so it doesn't fire again.
        reminder_key: 'reminder_d5' | 'reminder_d7' | 'reminder_d27' | 'reminder_d29'
        """
        allowed = {"reminder_d5", "reminder_d7", "reminder_d27", "reminder_d29"}
        if reminder_key not in allowed:
            raise ValueError(f"Unknown reminder key: {reminder_key}")

        col = await self._col()
        if col is None:
            return
        try:
            await col.update_one(
                {"chat_id": chat_id},
                {"$set": {reminder_key: True, "updated_at": datetime.now(timezone.utc)}},
            )
        except Exception as exc:
            log.error("mark_reminder_sent_failed", chat_id=chat_id,
                      reminder=reminder_key, error=str(exc))

    # ═════════════════════════════════════════════════════════════════════════
    # Indexes
    # ═════════════════════════════════════════════════════════════════════════

    async def ensure_indexes(self) -> None:
        """Create indexes on subscribers collection. Safe to call repeatedly."""
        col = await self._col()
        if col is None:
            return
        from pymongo import ASCENDING
        specs = [
            ({"chat_id":    ASCENDING}, {"unique": True, "name": "chat_id_unique"}),
            ({"status":     ASCENDING}, {}),
            ({"expires_at": ASCENDING}, {}),
        ]
        for keys, opts in specs:
            try:
                await col.create_index(list(keys.items()), **opts)
            except Exception as exc:
                log.warning("subscriber_index_warning", error=str(exc))
        log.debug("subscriber_indexes_ensured")
