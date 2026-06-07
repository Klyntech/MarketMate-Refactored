"""
marketmate.mate.brains.user
───────────────────────────
User Brain — answers everything about user subscriptions, trade history, and activity.

Capability Domain:
  - Subscription status: "Am I still active?"
  - Trade history: "Show me my recent trades"
  - Account timeline: "What happened with my account?"

Functions:
  get_user_status(chat_id)          → subscription state, expiry
  get_trade_history(limit)          → recent closed trades
  get_user_timeline(chat_id)        → full audit timeline

This brain queries user-specific data from SubscriberRepository and AuditRepository.
The LLM only narrates what this brain compiles.
"""

from __future__ import annotations

from typing import Any, Dict

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger

log = get_logger("mate.brains.user")


class UserBrain:
    """
    Financial cognition primitive for user-specific data.

    Answers: subscription status, trade history, user timeline.
    Does NOT answer: prices, strategy theory, system health.
    """

    # ═════════════════════════════════════════════════════════════════════════
    # Core Brain Functions
    # ═════════════════════════════════════════════════════════════════════════

    async def get_user_status(self, chat_id: str) -> Dict[str, Any]:
        """
        Get the subscription status for a user.

        Returns plan, status, expiry date.
        """
        try:
            from marketmate.db.repositories.subscribers import SubscriberRepository
            repo = SubscriberRepository()
            sub = await repo.get_by_chat_id(chat_id)
            if not sub:
                return {"chat_id": chat_id, "status": "not_registered"}

            from marketmate.delivery.telegram.handler import _fmt_date
            return {
                "chat_id": chat_id,
                "status": (sub.get("status") or "").upper(),
                "plan": sub.get("plan", "N/A"),
                "started_at": _fmt_date(sub.get("started_at")),
                "expires_at": _fmt_date(sub.get("expires_at")),
                "username": sub.get("username", ""),
            }
        except Exception as exc:
            log.warning("user_status_failed", chat_id=chat_id, error=str(exc))
            return {"chat_id": chat_id, "status": "lookup_failed"}

    async def get_trade_history(self, limit: int = 10) -> Dict[str, Any]:
        """
        Get recent closed trade history.

        Returns paginated list of closed trades with outcomes.
        """
        limit = min(limit, 50)  # Cap at 50
        try:
            from marketmate.db.repositories.signals import SignalRepository
            repo = SignalRepository()
            trades = await repo.get_virtual_trade_history(limit=limit)
            return {
                "trades": trades,
                "count": len(trades),
                "limit": limit,
            }
        except Exception as exc:
            return {"error": str(exc), "trades": [], "count": 0}

    async def get_user_timeline(self, chat_id: str) -> Dict[str, Any]:
        """
        Get the full audit timeline for a user.

        Returns events, payments, signals received, admin actions.
        """
        try:
            from marketmate.db.repositories.audit import AuditRepository
            repo = AuditRepository()
            timeline = await repo.get_user_timeline(chat_id)
            return {"chat_id": chat_id, **timeline}
        except Exception as exc:
            return {"chat_id": chat_id, "status": "timeline_unavailable", "error": str(exc)}


# ─── Singleton ────────────────────────────────────────────────────────────────

user_brain = UserBrain()
