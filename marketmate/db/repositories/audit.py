"""
marketmate/db/repositories/audit.py
───────────────────────────────────
AuditRepository — MongoDB-only append-only audit trail.

Migrated from db/audit.py. Legal-defensibility grade logging.

RULES:
  - NEVER update or delete from audit collections
  - ONLY ever insert
  - Every document is timestamped and immutable
  - Full user history queryable with get_user_timeline()

Collections:
  subscriber_events   → every state change (trial, approved, banned …)
  payments            → every payment submission + admin decision
  signal_deliveries   → every signal sent to every subscriber
  terms_acceptance    → ToS consent record per user
  admin_actions       → every admin command (who, what, when, target)
  messages_sent       → every outbound bot message
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.db.core import mongo_manager

log = get_logger("db.repositories.audit")

_TTL_1_YEAR = 365 * 24 * 3600


class AuditRepository:
    """
    MongoDB-only append-only audit trail repository.

    All public methods log failures silently — audit never crashes the bot.
    """

    def __init__(self) -> None:
        self._manager = mongo_manager

    async def _db(self):
        """Return the Motor database or None. Always safe."""
        try:
            return await self._manager.get_db()
        except Exception as exc:
            log.warning("audit_db_unavailable", error=str(exc))
            return None

    async def _insert(self, collection: str, doc: dict) -> None:
        """Append-only insert. Exceptions are caught — audit never crashes the bot."""
        database = await self._db()
        if database is None:
            return
        try:
            doc["_audit_id"] = str(uuid.uuid4())
            await database[collection].insert_one(doc)
        except Exception as exc:
            log.error("audit_insert_failed", collection=collection, error=str(exc))

    # ═════════════════════════════════════════════════════════════════════════
    # Subscriber Events
    # ═════════════════════════════════════════════════════════════════════════

    async def log_event(
        self,
        chat_id:    str,
        username:   str,
        full_name:  str,
        event_type: str,
        data:       Optional[dict] = None,
    ) -> None:
        """Append one subscriber lifecycle event (trial started, approved, banned …)."""
        now_str = datetime.now(timezone.utc).isoformat()
        now_dt  = datetime.now(timezone.utc)
        await self._insert("subscriber_events", {
            "chat_id":    chat_id,
            "username":   username,
            "full_name":  full_name,
            "event_type": event_type,
            "data":       data or {},
            "timestamp":  now_str,
            "ts_dt":      now_dt,
        })

    # ═════════════════════════════════════════════════════════════════════════
    # ToS Acceptance  (retained forever)
    # ═════════════════════════════════════════════════════════════════════════

    async def log_tos_acceptance(
        self,
        chat_id:     str,
        username:    str,
        full_name:   str,
        tos_version: str,
        tos_text:    str,
    ) -> None:
        """Record explicit ToS consent with full text for legal defensibility."""
        now_str = datetime.now(timezone.utc).isoformat()
        now_dt  = datetime.now(timezone.utc)
        await self._insert("terms_acceptance", {
            "chat_id":     chat_id,
            "username":    username,
            "full_name":   full_name,
            "tos_version": tos_version,
            "tos_text":    tos_text,
            "agreed_at":   now_str,
            "agreed_dt":   now_dt,
            "method":      "telegram_button",
        })

    # ═════════════════════════════════════════════════════════════════════════
    # Payments
    # ═════════════════════════════════════════════════════════════════════════

    async def log_payment_submission(
        self,
        chat_id:        str,
        username:       str,
        full_name:      str,
        file_id:        Optional[str],
        message_text:   Optional[str],
        amount_claimed: Optional[str],
    ) -> None:
        now_str = datetime.now(timezone.utc).isoformat()
        now_dt  = datetime.now(timezone.utc)
        await self._insert("payments", {
            "chat_id":        chat_id,
            "username":       username,
            "full_name":      full_name,
            "file_id":        file_id,
            "message_text":   message_text,
            "amount_claimed": amount_claimed,
            "status":         "SUBMITTED",
            "submitted_at":   now_str,
            "submitted_dt":   now_dt,
        })

    async def log_payment_outcome(
        self,
        chat_id:  str,
        outcome:  str,
        admin_id: str,
        reason:   Optional[str] = None,
    ) -> None:
        now_str = datetime.now(timezone.utc).isoformat()
        now_dt  = datetime.now(timezone.utc)
        await self._insert("payments", {
            "chat_id":    chat_id,
            "outcome":    outcome,
            "admin_id":   admin_id,
            "reason":     reason,
            "decided_at": now_str,
            "decided_dt": now_dt,
        })

    # ═════════════════════════════════════════════════════════════════════════
    # Signal Deliveries
    # ═════════════════════════════════════════════════════════════════════════

    async def log_signal_delivery(
        self,
        signal_id:  str,
        symbol:     str,
        direction:  str,
        entry:      float,
        sl:         float,
        tp1:        float,
        tp2:        float,
        rr:         float,
        confidence: str,
        recipients: list[str],
    ) -> None:
        now_str = datetime.now(timezone.utc).isoformat()
        now_dt  = datetime.now(timezone.utc)
        await self._insert("signal_deliveries", {
            "signal_id":  signal_id,
            "symbol":     symbol,
            "direction":  direction,
            "entry":      entry,
            "sl":         sl,
            "tp1":        tp1,
            "tp2":        tp2,
            "rr":         rr,
            "confidence": confidence,
            "recipients": recipients,
            "sent_at":    now_str,
            "sent_dt":    now_dt,
        })

    # ═════════════════════════════════════════════════════════════════════════
    # Admin Actions
    # ═════════════════════════════════════════════════════════════════════════

    async def log_admin_action(
        self,
        admin_id:  str,
        action:    str,
        target_id: Optional[str],
        details:   Optional[dict] = None,
    ) -> None:
        now_str = datetime.now(timezone.utc).isoformat()
        now_dt  = datetime.now(timezone.utc)
        await self._insert("admin_actions", {
            "admin_id":    admin_id,
            "action":      action,
            "target_id":   target_id,
            "details":     details or {},
            "executed_at": now_str,
            "executed_dt": now_dt,
        })

    # ═════════════════════════════════════════════════════════════════════════
    # Messages Sent
    # ═════════════════════════════════════════════════════════════════════════

    async def log_message_sent(
        self,
        chat_id:      str,
        message_type: str,
        content:      str,
    ) -> None:
        now_str = datetime.now(timezone.utc).isoformat()
        now_dt  = datetime.now(timezone.utc)
        await self._insert("messages_sent", {
            "chat_id":      chat_id,
            "message_type": message_type,
            "content":      content,
            "sent_at":      now_str,
            "sent_dt":      now_dt,
        })

    # ═════════════════════════════════════════════════════════════════════════
    # Court Export
    # ═════════════════════════════════════════════════════════════════════════

    async def get_user_timeline(self, chat_id: str) -> dict:
        """Pull complete audit trail for one user across all collections."""
        database = await self._db()
        if database is None:
            return {"error": "MongoDB not connected"}

        async def _fetch(collection: str, query: dict) -> list:
            try:
                cursor = database[collection].find(query, {"_id": 0}).sort("sent_at", 1)
                return await cursor.to_list(length=10_000)
            except Exception as exc:
                log.warning("timeline_fetch_failed",
                            collection=collection, error=str(exc))
                return []

        q = {"chat_id": chat_id}
        return {
            "chat_id":      chat_id,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "events":              await _fetch("subscriber_events",  q),
            "tos_acceptance":      await _fetch("terms_acceptance",   q),
            "payments":            await _fetch("payments",           q),
            "messages_sent":       await _fetch("messages_sent",      q),
            "admin_actions":       await _fetch("admin_actions",      {"target_id": chat_id}),
            "signals_received":    await database["signal_deliveries"].find(
                {"recipients": chat_id}, {"_id": 0}
            ).sort("sent_at", 1).to_list(length=10_000),
        }

    # ═════════════════════════════════════════════════════════════════════════
    # Indexes
    # ═════════════════════════════════════════════════════════════════════════

    async def ensure_indexes(self) -> None:
        """Create indexes and TTL policies. Called from connect_all()."""
        database = await self._db()
        if database is None:
            return

        from pymongo import ASCENDING, DESCENDING

        # Compound indexes
        compound_indexes = {
            "subscriber_events":  [("chat_id",   ASCENDING), ("ts_dt",        DESCENDING)],
            "terms_acceptance":   [("chat_id",   ASCENDING), ("agreed_dt",    DESCENDING)],
            "payments":           [("chat_id",   ASCENDING), ("submitted_dt", DESCENDING)],
            "signal_deliveries":  [("signal_id", ASCENDING), ("sent_dt",      DESCENDING)],
            "admin_actions":      [("target_id", ASCENDING), ("executed_dt",  DESCENDING)],
            "messages_sent":      [("chat_id",   ASCENDING), ("sent_dt",      DESCENDING)],
        }
        for collection, field_pairs in compound_indexes.items():
            try:
                await database[collection].create_index(
                    field_pairs,
                    name=f"compound_{'_'.join(f[0] for f in field_pairs)}",
                )
            except Exception as exc:
                log.warning("audit_compound_index_warning",
                            collection=collection, error=str(exc))

        # TTL indexes — auto-expire after 1 year
        # terms_acceptance is intentionally excluded (retained forever)
        ttl_specs = {
            "subscriber_events": "ts_dt",
            "payments":          "submitted_dt",
            "signal_deliveries": "sent_dt",
            "admin_actions":     "executed_dt",
            "messages_sent":     "sent_dt",
        }
        for collection, date_field in ttl_specs.items():
            try:
                await database[collection].create_index(
                    [(date_field, ASCENDING)],
                    expireAfterSeconds=_TTL_1_YEAR,
                    name=f"ttl_1year_{date_field}",
                )
            except Exception as exc:
                log.warning("audit_ttl_index_warning",
                            collection=collection, error=str(exc))

        log.debug("audit_indexes_ensured")
