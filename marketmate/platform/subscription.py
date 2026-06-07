"""
marketmate.platform.subscription
─────────────────────────────────
Subscriber lifecycle, billing, and trial management.

Business logic extracted from db/users.py into the platform layer.
Uses SubscriberRepository from marketmate.db.repositories.subscribers.

This module orchestrates subscriber state transitions and enforces
business rules (trial limits, plan durations, etc.) on top of the
raw data access provided by the repository.

Migrated from db/users.py business logic.
Import paths updated to marketmate.* prefix.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.db.repositories.subscribers import SubscriberRepository
from marketmate.db.repositories.audit import AuditRepository

log = get_logger("platform.subscription")

# ─── Repository singletons ────────────────────────────────────────────────────
_subscriber_repo = SubscriberRepository()
_audit_repo = AuditRepository()


# ─── Public API ────────────────────────────────────────────────────────────────

async def create_trial_subscriber(
    chat_id:   str,
    username:  str,
    full_name: str,
) -> Optional[dict]:
    """
    Start a trial for a new subscriber.

    Business rules:
      - One trial per user (checked by repository)
      - Trial length from config (cfg.subscription.trial_days)
      - ToS acceptance must be recorded BEFORE calling this
    """
    if await _subscriber_repo.has_used_trial(chat_id):
        log.warning("trial_already_used", chat_id=chat_id)
        return None

    sub = await _subscriber_repo.create_trial(chat_id, username, full_name)

    if sub:
        await _audit_repo.log_event(
            chat_id=chat_id, username=username, full_name=full_name,
            event_type="TRIAL_STARTED",
            data={"expires_at": sub.get("expires_at")},
        )
        log.info("trial_created", chat_id=chat_id)

    return sub


async def approve_subscriber(
    chat_id:  str,
    admin_id: str,
    days:     int = 30,
) -> Optional[dict]:
    """
    Approve a pending subscriber.

    Business rules:
      - Sets status to ACTIVE
      - Default 30-day expiry
      - Records admin action in audit trail
    """
    sub = await _subscriber_repo.approve(chat_id, admin_id, days=days)

    if sub:
        await _audit_repo.log_admin_action(
            admin_id=admin_id, action="APPROVE",
            target_id=chat_id,
            details={"expires_at": sub.get("expires_at"), "days": days},
        )
        log.info("subscriber_approved", chat_id=chat_id, admin=admin_id)

    return sub


async def reject_subscriber(
    chat_id:  str,
    admin_id: str,
    reason:   str = "Payment not confirmed",
) -> None:
    """
    Reject a pending subscriber's payment.

    Business rules:
      - Reverts subscriber to expired status
      - Records admin action in audit trail
    """
    await _subscriber_repo.reject(chat_id)
    await _audit_repo.log_admin_action(
        admin_id=admin_id, action="REJECT",
        target_id=chat_id, details={"reason": reason},
    )
    await _audit_repo.log_payment_outcome(
        chat_id=chat_id, outcome="REJECTED",
        admin_id=admin_id, reason=reason,
    )
    log.info("subscriber_rejected", chat_id=chat_id, admin=admin_id)


async def extend_subscription(
    chat_id:  str,
    admin_id: str,
    days:     int,
) -> Optional[dict]:
    """
    Extend a subscriber's expiry date.

    Business rules:
      - Adds days to current expiry (or from now if already expired)
      - Records admin action in audit trail
    """
    sub = await _subscriber_repo.extend(chat_id, days)

    if sub:
        await _audit_repo.log_admin_action(
            admin_id=admin_id, action="EXTEND",
            target_id=chat_id, details={"days": days},
        )
        log.info("subscription_extended", chat_id=chat_id, days=days)

    return sub


async def ban_subscriber(chat_id: str, admin_id: str) -> None:
    """
    Permanently ban a subscriber.

    Business rules:
      - Sets status to BANNED
      - Records admin action in audit trail
    """
    await _subscriber_repo.ban(chat_id)
    await _audit_repo.log_admin_action(
        admin_id=admin_id, action="BAN",
        target_id=chat_id,
    )
    log.info("subscriber_banned", chat_id=chat_id, admin=admin_id)


async def unban_subscriber(chat_id: str, admin_id: str) -> None:
    """
    Unban a subscriber (reverts to expired so they can re-subscribe).

    Business rules:
      - Sets status to EXPIRED (allows re-subscription)
      - Records admin action in audit trail
    """
    await _subscriber_repo.upsert(
        chat_id=chat_id, status="EXPIRED", plan="none"
    )
    await _audit_repo.log_admin_action(
        admin_id=admin_id, action="UNBAN",
        target_id=chat_id,
    )
    log.info("subscriber_unbanned", chat_id=chat_id, admin=admin_id)


async def expire_subscriber(chat_id: str) -> None:
    """
    Mark a subscriber as expired (automatic lifecycle).

    Called by the reminder loop when a subscription or trial
    has passed its expiry date.
    """
    await _subscriber_repo.expire(chat_id)
    log.info("subscriber_expired_auto", chat_id=chat_id)


async def is_subscriber_active(chat_id: str) -> bool:
    """Check if a subscriber has active access (trial or active)."""
    return await _subscriber_repo.is_active(chat_id)


async def get_subscriber(chat_id: str) -> Optional[dict]:
    """Get a subscriber's record by chat_id."""
    return await _subscriber_repo.get_by_chat_id(chat_id)


async def get_active_chat_ids() -> list[str]:
    """Get all chat IDs with active access (for signal dispatch)."""
    return await _subscriber_repo.get_active_chat_ids()


async def get_all_active_subscribers() -> list[dict]:
    """Get all active subscriber records."""
    return await _subscriber_repo.get_all_active()


async def set_pending_subscriber(
    chat_id:     str,
    username:    str,
    full_name:   str,
    payment_ref: str,
) -> None:
    """Mark a user as pending after payment proof submission."""
    await _subscriber_repo.set_pending(chat_id, username, full_name, payment_ref)
    log.info("subscriber_pending", chat_id=chat_id)


async def has_used_trial(chat_id: str) -> bool:
    """Check if a user has already used their free trial."""
    return await _subscriber_repo.has_used_trial(chat_id)


async def mark_reminder_sent(chat_id: str, reminder_key: str) -> None:
    """Mark a reminder as sent so it doesn't fire again."""
    await _subscriber_repo.mark_reminder_sent(chat_id, reminder_key)


def get_subscription_config() -> dict:
    """Return subscription configuration for use in templates/APIs."""
    return {
        "monthly_price_ngn":   cfg.subscription.monthly_price_ngn,
        "quarterly_price_ngn": cfg.subscription.quarterly_price_ngn,
        "trial_days":          cfg.subscription.trial_days,
        "bank_name":           cfg.subscription.bank_name,
        "account_number":      cfg.subscription.account_number,
        "account_name":        cfg.subscription.account_name,
        "tos_version":         cfg.subscription.tos_version,
    }
