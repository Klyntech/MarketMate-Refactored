"""
marketmate.delivery.telegram.reminders
───────────────────────────────────────
Automated subscription lifecycle manager.

Runs daily at 09:00 UTC as a background task in main.py.

Responsibilities:
  - Send Day 5 trial reminder (2 days left)
  - Send Day 7 trial reminder (1 day left)
  - Send Day 27 paid reminder (3 days left)
  - Send Day 29 paid reminder (1 day left)
  - Revoke expired trial/paid subscriptions automatically
  - Send renewal prompt after expiry

All actions are logged to MongoDB audit trail.

Migrated from delivery/reminders.py.
Import paths updated to marketmate.* prefix.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

from marketmate.core.config import cfg
from marketmate.db.repositories.subscribers import SubscriberRepository
from marketmate.db.repositories.audit import AuditRepository
from marketmate.core.logger import get_logger

log = get_logger("reminders")

_SEND_DELAY = 0.5

# ─── Repository singletons ────────────────────────────────────────────────────
_subscriber_repo = SubscriberRepository()
_audit_repo = AuditRepository()


async def run_reminder_loop(telegram) -> None:
    """
    Background loop. Fires daily at 09:00 UTC.
    Called from main.py as asyncio.create_task().
    `telegram` is the TelegramDelivery instance from main.py.
    """
    while True:
        now = datetime.now(timezone.utc)
        if now.hour == 9 and now.minute < 5:
            try:
                await _run_daily_checks(telegram)
            except Exception as exc:
                log.error("reminder_loop_error", error=str(exc), exc_info=True)

        # ── Weekly recap: Saturday 02:00 UTC ──────────────────────────────────
        if now.weekday() == 5 and now.hour == 2 and now.minute < 5:
            try:
                from marketmate.analytics.weekly_recap import generate_weekly_recap
                log.info("weekly_recap_trigger_saturday")
                await generate_weekly_recap()
            except Exception as exc:
                log.error("weekly_recap_trigger_failed",
                          error=str(exc), exc_info=True)

        await asyncio.sleep(60)


async def _run_daily_checks(telegram) -> None:
    """Run all expiry and reminder checks."""
    log.info("reminder_checks_start")

    subs = await _subscriber_repo.get_all_active()
    now  = datetime.now(timezone.utc)

    for sub in subs:
        chat_id   = sub["chat_id"]
        username  = sub.get("username", "")
        full_name = sub.get("full_name", "")
        status    = (sub.get("status") or "").lower()
        expires_s = sub.get("expires_at")

        if not expires_s:
            continue

        expires = datetime.fromisoformat(str(expires_s)) if isinstance(expires_s, str) else expires_s
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)

        days_left = (expires - now).days

        # ── Already expired ───────────────────────────────────────────────────
        if now > expires:
            await _subscriber_repo.expire(chat_id)
            await _audit_repo.log_event(
                chat_id=chat_id, username=username, full_name=full_name,
                event_type="EXPIRED",
                data={"expired_at": now.isoformat()},
            )
            msg = _renewal_message(status)
            await _notify(telegram, chat_id, msg)
            await _audit_repo.log_message_sent(
                chat_id, "EXPIRED_NOTIFICATION", msg
            )
            log.info("subscriber_expired_auto", chat_id=chat_id)
            continue

        # ── Trial reminders ───────────────────────────────────────────────────
        if status == "trial":
            if days_left <= 2 and not sub.get("reminder_d5"):
                msg = (
                    f"⚠️ *Trial Ending Soon*\n\n"
                    f"Your free trial ends in {days_left} day(s).\n\n"
                    f"To keep access subscribe now:\n"
                    f"Monthly: ₦{cfg.subscription.monthly_price_ngn:,}\n\n"
                    f"Tap /subscribe for payment details."
                )
                await _notify(telegram, chat_id, msg)
                await _subscriber_repo.mark_reminder_sent(chat_id, "reminder_d5")
                await _audit_repo.log_event(
                    chat_id=chat_id, username=username, full_name=full_name,
                    event_type="REMINDER_SENT",
                    data={"type": "TRIAL_D5", "days_left": days_left},
                )
                await _audit_repo.log_message_sent(chat_id, "REMINDER_D5", msg)

            elif days_left <= 1 and not sub.get("reminder_d7"):
                msg = (
                    f"🚨 *Trial Ends Tomorrow*\n\n"
                    f"Your free trial expires tomorrow.\n\n"
                    f"Subscribe now to avoid losing access:\n"
                    f"₦{cfg.subscription.monthly_price_ngn:,}/month\n\n"
                    f"Tap /subscribe for bank details."
                )
                await _notify(telegram, chat_id, msg)
                await _subscriber_repo.mark_reminder_sent(chat_id, "reminder_d7")
                await _audit_repo.log_event(
                    chat_id=chat_id, username=username, full_name=full_name,
                    event_type="REMINDER_SENT",
                    data={"type": "TRIAL_D7", "days_left": days_left},
                )
                await _audit_repo.log_message_sent(chat_id, "REMINDER_D7", msg)

        # ── Paid subscription reminders ───────────────────────────────────────
        elif status == "active":
            if days_left <= 3 and not sub.get("reminder_d27"):
                msg = (
                    f"🔔 *Subscription Expiring Soon*\n\n"
                    f"Your subscription expires in {days_left} day(s).\n\n"
                    f"Renew now to avoid interruption:\n"
                    f"₦{cfg.subscription.monthly_price_ngn:,}/month\n\n"
                    f"Tap /subscribe for payment details."
                )
                await _notify(telegram, chat_id, msg)
                await _subscriber_repo.mark_reminder_sent(chat_id, "reminder_d27")
                await _audit_repo.log_event(
                    chat_id=chat_id, username=username, full_name=full_name,
                    event_type="REMINDER_SENT",
                    data={"type": "PAID_D27", "days_left": days_left},
                )
                await _audit_repo.log_message_sent(chat_id, "REMINDER_D27", msg)

            elif days_left <= 1 and not sub.get("reminder_d29"):
                msg = (
                    f"🚨 *Subscription Expires Tomorrow*\n\n"
                    f"Your access expires tomorrow.\n\n"
                    f"Renew now:\n"
                    f"₦{cfg.subscription.monthly_price_ngn:,}/month\n\n"
                    f"Tap /subscribe for payment details."
                )
                await _notify(telegram, chat_id, msg)
                await _subscriber_repo.mark_reminder_sent(chat_id, "reminder_d29")
                await _audit_repo.log_event(
                    chat_id=chat_id, username=username, full_name=full_name,
                    event_type="REMINDER_SENT",
                    data={"type": "PAID_D29", "days_left": days_left},
                )
                await _audit_repo.log_message_sent(chat_id, "REMINDER_D29", msg)

    log.info("reminder_checks_complete", checked=len(subs))


def _renewal_message(previous_status: str) -> str:
    if previous_status == "trial":
        return (
            f"⏰ *Your Free Trial Has Ended*\n\n"
            f"We hope you found value during your trial.\n\n"
            f"Subscribe to continue receiving signals:\n"
            f"₦{cfg.subscription.monthly_price_ngn:,}/month\n\n"
            f"Tap /subscribe for payment details."
        )
    return (
        f"⏰ *Your Subscription Has Expired*\n\n"
        f"Renew to continue receiving MarketMate signals:\n"
        f"₦{cfg.subscription.monthly_price_ngn:,}/month\n\n"
        f"Tap /subscribe for payment details."
    )


async def _notify(telegram, chat_id: str, message: str) -> None:
    """Send a message using the TelegramDelivery._send method."""
    try:
        await telegram._send(message, chat_id_override=chat_id)
        await asyncio.sleep(_SEND_DELAY)
    except Exception as exc:
        log.error("reminder_send_failed", chat_id=chat_id, error=str(exc))
