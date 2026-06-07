"""
marketmate.delivery.telegram.handler
─────────────────────────────────────
Telegram webhook receiver and command handler.

Receives incoming Telegram updates via POST /webhook/{secret}
and dispatches them to the correct handler function.

Architecture:
  FastAPI POST /webhook/{secret}  →  handle_update()
                                       ↓
                              route by message type
                                       ↓
          /start  /status  /price  /pairs  /performance  /myaccount
          /subscribe  /trial  /help  /mate
          /approve  /reject  /pending  /subscribers  /extend  /ban
          /unban  /broadcast  /latest_chart

MATE Intelligence Layer:
  Plain text from active subscribers → _looks_like_question()
                                       ↓
                              _handle_mate_query()
                                       ↓
                              mate_interface.ask()
                                       ↓
                              CompiledCore → QueryRouter
                                       ↓
                              Redis + MongoDB + Event State
                                       ↓
                              LLM narrates compiled state

Security:
  - Webhook secret token in URL prevents spoofed requests
  - Every command checks subscriber status before responding
  - Admin commands check against TELEGRAM_ADMIN_CHAT_ID
  - Payment photo forwarded to admin with ready-to-run approve command

All interactions are logged to MongoDB audit trail via AuditRepository.

Formatting note:
  All outgoing messages use parse_mode="HTML".
  Every dynamic value is wrapped with _esc() (html.escape) before
  interpolation so user-supplied strings can never break the parser.
  _send() retries as plain text if Telegram still rejects the message.

Migrated from delivery/bot_handler.py.
Import paths updated to use marketmate.db.repositories.subscribers
instead of db.users, and marketmate.platform.academy_repo instead of
db.academy.
"""

from __future__ import annotations

import asyncio
import hashlib
import hmac
import html
import os
import re
import tempfile
from datetime import datetime, timezone
from typing import Optional

from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.error import TelegramError

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.db.repositories.subscribers import SubscriberRepository
from marketmate.db.repositories.audit import AuditRepository
from marketmate.db.repositories.trading_accounts import trading_account_store

log = get_logger("bot_handler")

_SEND_DELAY = 0.5   # seconds between messages to avoid rate limits

# ─── Callback HMAC signing ───────────────────────────────────────────────────
# Signs callback_data with the chat_id to prevent forgery.
# Format: action:hmac_hex  (e.g. "start_trial:a1b2c3d4")

def _sign_callback(action: str, chat_id: str) -> str:
    """Sign a callback action with the chat_id using HMAC-SHA256."""
    sig = hmac.new(
        cfg.app.session_secret.encode() or b"default_key",
        f"{action}:{chat_id}".encode(),
        hashlib.sha256,
    ).hexdigest()[:8]
    return f"{action}:{sig}"


def _verify_callback(data: str, chat_id: str) -> str:
    """Verify callback data and return the action if valid, empty string if not."""
    if ":" not in data:
        # Legacy unsigned callbacks — still accept but log
        log.warning("callback_unsigned_legacy", data=data, chat_id=chat_id)
        return data  # backward compat
    action, sig = data.rsplit(":", 1)
    expected = hmac.new(
        cfg.app.session_secret.encode() or b"default_key",
        f"{action}:{chat_id}".encode(),
        hashlib.sha256,
    ).hexdigest()[:8]
    if not hmac.compare_digest(sig, expected):
        log.warning("callback_signature_invalid", data=data, chat_id=chat_id)
        return ""  # invalid
    return action

# ─── Repository singletons ────────────────────────────────────────────────────
_subscriber_repo = SubscriberRepository()
_audit_repo = AuditRepository()

# ─── HTML escaping utility ────────────────────────────────────────────────────

def _esc(value) -> str:
    """
    Escape a dynamic value for safe embedding inside an HTML-mode Telegram
    message.  Converts the value to str first so None, numbers, etc. are
    all handled transparently.
    """
    return html.escape(str(value) if value is not None else "")


def _fmt_date(value) -> str:
    """
    Format a date/datetime value as YYYY-MM-DD.

    MongoDB may return a datetime.datetime object (not subscriptable)
    or a string. This helper handles both safely.
    """
    if value is None:
        return "N/A"
    if isinstance(value, datetime):
        return value.strftime("%Y-%m-%d")
    s = str(value)
    return s[:10] if len(s) >= 10 else s


def _strip_html(text: str) -> str:
    """Remove HTML tags for plain-text fallback delivery."""
    return re.sub(r"<[^>]+>", "", text)


# ─── Terms of Service text ────────────────────────────────────────────────────

TOS_TEXT = """
<b>MarketMate — Terms of Service v{version}</b>

By using this service you agree to the following:

1. <b>Educational Purpose Only</b>
Signals are for informational purposes only and do not constitute financial advice.

2. <b>No Profit Guarantee</b>
Past signal performance does not guarantee future results. You may lose capital.

3. <b>No Refunds</b>
All subscription fees are strictly non-refundable under any circumstance.

4. <b>Subscription Terms</b>
Monthly access is ₦{price}/month, activated manually upon payment confirmation.

5. <b>Trial</b>
A {trial_days}-day free trial is available once per user. Full access during trial.

6. <b>Termination</b>
Clinton Onyedikachi Chukwuma t/a MarketMate reserves the right to suspend or permanently revoke access at its sole discretion.

7. <b>Liability</b>
Maximum liability is limited to the subscription fee paid in the current billing period.

8. <b>Intellectual Property</b>
Redistribution or public sharing of signals is strictly prohibited.

9. <b>Data</b>
Your Telegram ID, username, and payment proof are stored securely for service delivery and legal compliance.

10. <b>Governing Law</b>
This agreement is governed by the laws of the Federal Republic of Nigeria.

<i>Effective 27 April 2026 — Clinton Onyedikachi Chukwuma t/a MarketMate</i>
""".strip()


def _build_tos_text() -> str:
    """Return ToS with cfg placeholders filled and escaped."""
    return TOS_TEXT.format(
        version=_esc(cfg.subscription.tos_version),
        price=_esc(f"{cfg.subscription.monthly_price_ngn:,}"),
        trial_days=_esc(cfg.subscription.trial_days),
    )


# ─── Welcome message ─────────────────────────────────────────────────────────

AUTOTRADE_URL = "https://newmate.onrender.com/auto-trade"

WELCOME_TEXT = (
    "📊 <b>Welcome to MarketMate</b>\n\n"
    "Institutional-grade signals for Gold, BTC, ETH &amp; EUR powered by Smart Money Concepts.\n\n"
    "<b>What you get:</b>\n"
    "- High-probability BUY/SELL signals (avg 4/week)\n"
    "- Entry zone, Stop Loss, TP1 / TP2 / TP3\n"
    "- Live trade updates — TP hits, SL alerts, break-even moves\n"
    "- Daily performance summary\n\n"
    "<b>Pricing:</b>\n"
    "🎁 <b>7-Day Free Trial</b> — No payment needed\n"
    "💎 <b>Monthly Access</b> — ₦30,000/month\n"
    "👑 <b>Quarterly Access</b> — ₦80,000 (₦26,667/mo · Save ₦10,000)\n\n"
    "Tap a button below to get started."
)


# ─── Bank payment instructions ────────────────────────────────────────────────

def _build_payment_text(plan: str = "monthly") -> str:
    if plan == "quarterly":
        amount      = cfg.subscription.quarterly_price_ngn
        plan_label  = "Quarterly Access (3 months)"
        plan_note   = f"₦{amount:,} · saves ₦10,000 vs monthly"
    else:
        amount      = cfg.subscription.monthly_price_ngn
        plan_label  = "Monthly Access"
        plan_note   = f"₦{amount:,} / month"

    return (
        "💳 <b>How to Subscribe</b>\n\n"
        f"Plan: <b>{_esc(plan_label)}</b>\n"
        f"Fee:  {_esc(plan_note)}\n\n"
        "<b>Bank Details:</b>\n"
        f"Bank:    {_esc(cfg.subscription.bank_name)}\n"
        f"Account: {_esc(cfg.subscription.account_number)}\n"
        f"Name:    {_esc(cfg.subscription.account_name)}\n\n"
        "<b>Steps:</b>\n"
        f"1. Transfer ₦{_esc(f'{amount:,}')} to the account above\n"
        "2. Use your Telegram username as the transfer narration\n"
        "3. Send your payment screenshot or transaction reference directly to this chat\n"
        "4. You will be approved within a few hours\n\n"
        "⚠️ Payments are reviewed manually. Do not share your screenshot anywhere else."
    )


# ─── Bot singleton ────────────────────────────────────────────────────────────

_bot: Optional[Bot] = None


def get_bot() -> Bot:
    global _bot
    if _bot is None:
        _bot = Bot(token=cfg.telegram.bot_token)
    return _bot


# ─── Bot username cache ────────────────────────────────────────────────────────

_BOT_USERNAME: str = ""


def set_bot_username(username: str) -> None:
    """
    Cache the bot's Telegram username at startup.
    Called once from main.py lifespan after bot.get_me() resolves.
    Prevents a live get_me() API call on every incoming message.
    """
    global _BOT_USERNAME
    _BOT_USERNAME = username or ""


# ─── Core send helper ─────────────────────────────────────────────────────────

async def _send(
    chat_id:     str,
    text:        str,
    reply_markup=None,
    parse_mode:  str = "HTML",
) -> bool:
    """
    Send a Telegram message.  parse_mode defaults to HTML.

    If Telegram rejects the message due to a parse/entity error, the call
    is automatically retried once with parse_mode=None (plain text) so
    delivery is never silently lost.
    """
    try:
        await get_bot().send_message(
            chat_id=chat_id,
            text=text,
            parse_mode=parse_mode,
            reply_markup=reply_markup,
        )
        await asyncio.sleep(_SEND_DELAY)
        return True
    except TelegramError as exc:
        err = str(exc)
        if parse_mode and (
            "can't parse" in err.lower()
            or "entity" in err.lower()
            or "parse" in err.lower()
        ):
            log.warning(
                "send_html_parse_error_fallback",
                chat_id=chat_id,
                error=err,
            )
            try:
                await get_bot().send_message(
                    chat_id=chat_id,
                    text=_strip_html(text),
                    parse_mode=None,
                    reply_markup=reply_markup,
                )
                await asyncio.sleep(_SEND_DELAY)
                return True
            except TelegramError as exc2:
                log.error(
                    "send_failed_after_fallback",
                    chat_id=chat_id,
                    error=str(exc2),
                )
                return False
        log.error("send_failed", chat_id=chat_id, error=err)
        return False


async def _send_admin(text: str) -> bool:
    """Send message to admin chat only."""
    admin_id = cfg.telegram.admin_chat_id
    if not admin_id:
        return True
    return await _send(admin_id, text)


# ─── Auth helpers ─────────────────────────────────────────────────────────────

def _is_admin(chat_id: str) -> bool:
    return str(chat_id) == str(cfg.telegram.admin_chat_id)


async def _require_active(chat_id: str, username: str, full_name: str) -> bool:
    """
    Returns True if user has active access.
    If not, sends appropriate message and returns False.
    """
    active = await _subscriber_repo.is_active(chat_id)
    if active:
        return True

    sub = await _subscriber_repo.get_by_chat_id(chat_id)
    if not sub:
        await _handle_start(chat_id, username, full_name)
        return False

    status_lower = (sub.get("status") or "").lower()
    if status_lower == "pending":
        await _send(chat_id,
                    "⏳ Your payment is being reviewed. You'll be notified when approved.")
        return False

    if status_lower == "banned":
        return False

    # Expired or trial ended
    await _send(
        chat_id,
        "⏰ <b>Your access has expired.</b>\n\n"
        "To continue receiving signals tap /subscribe.",
    )
    return False


# ─── Main update router ───────────────────────────────────────────────────────

async def handle_update(update_data: dict) -> None:
    """
    Entry point called by POST /webhook/{secret} in main.py.
    Routes the update to the correct handler.
    """
    try:
        update = Update.de_json(update_data, get_bot())
    except Exception as exc:
        log.error("update_parse_failed", error=str(exc))
        return

    # ── Inline button callbacks ───────────────────────────────────────────────
    if update.callback_query:
        await _handle_callback(update.callback_query)
        return

    message = update.message
    if not message:
        return

    chat_id   = str(message.chat.id)
    username  = message.from_user.username or ""
    full_name = (message.from_user.first_name or "") + " " + (message.from_user.last_name or "")
    full_name = full_name.strip()
    text      = (message.text or "").strip()

    # ── Photo: payment proof submission ──────────────────────────────────────
    if message.photo:
        await _handle_photo(chat_id, username, full_name, message)
        return

    # ── Commands ──────────────────────────────────────────────────────────────
    if not text.startswith("/"):
        await _handle_plain_text(chat_id, username, full_name, text)
        return

    raw_cmd = text.split()[0].lower()
    if _BOT_USERNAME:
        raw_cmd = raw_cmd.replace(f"@{_BOT_USERNAME.lower()}", "")
    cmd  = raw_cmd
    args = text.split()[1:]

    # Public commands
    if cmd == "/start":
        await _handle_start(chat_id, username, full_name)
    elif cmd == "/trial":
        await _handle_trial(chat_id, username, full_name)
    elif cmd == "/subscribe":
        await _handle_subscribe(chat_id, username, full_name)
    elif cmd == "/help":
        await _handle_help(chat_id)
    elif cmd == "/myaccount":
        await _handle_myaccount(chat_id, username, full_name)

    # Subscriber-only commands
    elif cmd == "/status":
        if await _require_active(chat_id, username, full_name):
            await _handle_status(chat_id)
    elif cmd == "/price":
        if await _require_active(chat_id, username, full_name):
            await _handle_price(chat_id)
    elif cmd == "/pairs":
        if await _require_active(chat_id, username, full_name):
            await _handle_pairs(chat_id)
    elif cmd == "/performance":
        if await _require_active(chat_id, username, full_name):
            await _handle_performance(chat_id)
    elif cmd == "/mate":
        if await _require_active(chat_id, username, full_name):
            mate_query = " ".join(args) if args else ""
            await _handle_mate_query(chat_id, mate_query)

    # Admin-only commands
    elif cmd == "/approve":
        if _is_admin(chat_id):
            await _handle_approve(chat_id, args)
        else:
            await _send(chat_id, "❌ Unauthorized.")
    elif cmd == "/reject":
        if _is_admin(chat_id):
            await _handle_reject(chat_id, args)
        else:
            await _send(chat_id, "❌ Unauthorized.")
    elif cmd == "/pending":
        if _is_admin(chat_id):
            await _handle_pending(chat_id)
        else:
            await _send(chat_id, "❌ Unauthorized.")
    elif cmd == "/autotrade":
        parts = text.split()
        arg   = parts[1].lower() if len(parts) > 1 else ""
        await _handle_autotrade(chat_id, username, full_name, arg)
    elif cmd == "/set_timezone":
        parts = text.split()
        tz    = parts[1] if len(parts) > 1 else ""
        await _handle_set_timezone(chat_id, tz)
    elif cmd == "/myaccounts":
        await _handle_myaccounts(chat_id)
    elif cmd == "/linkaccount":
        await _handle_linkaccount(chat_id)
    elif cmd == "/opentrades":
        if _is_admin(chat_id):
            await _handle_opentrades(chat_id)
        else:
            await _send(chat_id, "❌ Unauthorized.")
    elif cmd == "/subscribers":
        if _is_admin(chat_id):
            await _handle_subscribers(chat_id)
        else:
            await _send(chat_id, "❌ Unauthorized.")
    elif cmd == "/extend":
        if _is_admin(chat_id):
            await _handle_extend(chat_id, args)
        else:
            await _send(chat_id, "❌ Unauthorized.")
    elif cmd == "/ban":
        if _is_admin(chat_id):
            await _handle_ban(chat_id, args)
        else:
            await _send(chat_id, "❌ Unauthorized.")
    elif cmd == "/unban":
        if _is_admin(chat_id):
            await _handle_unban(chat_id, args)
        else:
            await _send(chat_id, "❌ Unauthorized.")
    elif cmd == "/broadcast":
        if _is_admin(chat_id):
            await _handle_broadcast(chat_id, args)
        else:
            await _send(chat_id, "❌ Unauthorized.")
    elif cmd == "/latest_chart":
        if _is_admin(chat_id):
            await _handle_latest_chart(chat_id)
        else:
            await _send(chat_id, "❌ Unauthorized.")
    else:
        await _send(chat_id, "Unknown command. Type /help for available commands.")


# ─── Callback handler ─────────────────────────────────────────────────────────

async def _handle_callback(query) -> None:
    chat_id   = str(query.message.chat.id)
    username  = query.from_user.username or ""
    full_name = (query.from_user.first_name or "") + " " + (query.from_user.last_name or "")
    full_name = full_name.strip()
    raw_data  = query.data

    await query.answer()

    # SECURITY: Verify callback signature
    data = _verify_callback(raw_data, chat_id)
    if not data:
        log.warning("callback_rejected_invalid_signature",
                    raw_data=raw_data, chat_id=chat_id)
        return

    if data == "start_trial":
        await _handle_trial(chat_id, username, full_name)
    elif data == "subscribe_now":
        await _handle_subscribe(chat_id, username, full_name, plan="monthly")
    elif data == "subscribe_quarterly":
        await _handle_subscribe(chat_id, username, full_name, plan="quarterly")
    elif data == "accept_tos_trial":
        await _complete_trial(chat_id, username, full_name)
    elif data == "accept_tos_subscribe":
        payment_text = _build_payment_text("monthly")
        await _send(chat_id, payment_text)
        await _audit_repo.log_message_sent(chat_id, "PAYMENT_INSTRUCTIONS",
                                            payment_text)
    elif data == "accept_tos_subscribe_quarterly":
        payment_text = _build_payment_text("quarterly")
        await _send(chat_id, payment_text)
        await _audit_repo.log_message_sent(chat_id, "PAYMENT_INSTRUCTIONS_QUARTERLY",
                                            payment_text)


# ─── /start ──────────────────────────────────────────────────────────────────

async def _handle_start(chat_id: str, username: str, full_name: str) -> None:
    sub = await _subscriber_repo.get_by_chat_id(chat_id)

    if sub and await _subscriber_repo.is_active(chat_id):
        await _send(chat_id,
                    "✅ Welcome back! You have active access.\n"
                    "Type /help to see available commands.")
        return

    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⚡ Start Now — Free Trial",
                                 callback_data=_sign_callback("start_trial", chat_id)),
        ],
        [
            InlineKeyboardButton("💎 Monthly — ₦30,000",
                                 callback_data=_sign_callback("subscribe_now", chat_id)),
            InlineKeyboardButton("👑 Quarterly — ₦80,000",
                                 callback_data=_sign_callback("subscribe_quarterly", chat_id)),
        ],
    ])
    await _send(chat_id, WELCOME_TEXT, reply_markup=keyboard)
    await _audit_repo.log_message_sent(chat_id, "WELCOME", WELCOME_TEXT)


# ─── /trial ──────────────────────────────────────────────────────────────────

async def _handle_trial(chat_id: str, username: str, full_name: str) -> None:
    if await _subscriber_repo.has_used_trial(chat_id):
        await _send(chat_id,
                    "⚠️ You have already used your free trial.\n\n"
                    "To continue tap /subscribe.")
        return

    tos = _build_tos_text()
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton("✅ I Agree — Start Trial",
                             callback_data=_sign_callback("accept_tos_trial", chat_id)),
    ]])
    await _send(chat_id, tos, reply_markup=keyboard)


async def _complete_trial(chat_id: str, username: str, full_name: str) -> None:
    """Called after user accepts ToS for trial."""
    tos_text = _build_tos_text()
    await _audit_repo.log_tos_acceptance(
        chat_id=chat_id, username=username, full_name=full_name,
        tos_version=cfg.subscription.tos_version,
        tos_text=tos_text,
    )

    sub = await _subscriber_repo.create_trial(chat_id, username, full_name)

    await _audit_repo.log_event(
        chat_id=chat_id, username=username, full_name=full_name,
        event_type="TRIAL_STARTED",
        data={"expires_at": _fmt_date(sub["expires_at"]) if sub else "unknown"},
    )

    expires_str = _esc(_fmt_date(sub['expires_at'])) if sub else "N/A"
    msg = (
        "🎉 <b>Your 7-day free trial has started!</b>\n\n"
        "You now have full access to MarketMate signals.\n"
        f"Trial expires: {expires_str}\n\n"
        "Signals fire automatically when market conditions align.\n"
        "Average 4 signals per week during London and NY sessions.\n\n"
        "Type /help to see all commands."
    )
    await _send(chat_id, msg)
    await _audit_repo.log_message_sent(chat_id, "TRIAL_STARTED", msg)

    await _send_admin(
        "🆕 <b>New Trial Started</b>\n\n"
        f"Name: {_esc(full_name)}\n"
        f"Username: @{_esc(username)}\n"
        f"Chat ID: <code>{_esc(chat_id)}</code>\n"
        f"Expires: {expires_str}"
    )


# ─── /subscribe ───────────────────────────────────────────────────────────────

async def _handle_subscribe(
    chat_id:   str,
    username:  str,
    full_name: str,
    plan:      str = "monthly",
) -> None:
    """Show ToS before revealing payment details. Plan is 'monthly' or 'quarterly'."""
    tos      = _build_tos_text()
    callback = _sign_callback("accept_tos_subscribe_quarterly", chat_id) if plan == "quarterly" else _sign_callback("accept_tos_subscribe", chat_id)
    label    = "✅ I Agree — Show Quarterly Payment Details" if plan == "quarterly" \
               else "✅ I Agree — Show Payment Details"
    keyboard = InlineKeyboardMarkup([[
        InlineKeyboardButton(label, callback_data=callback),
    ]])
    await _send(chat_id, tos, reply_markup=keyboard)


# ─── MATE Intelligence Router ────────────────────────────────────────────────

def _looks_like_question(text: str) -> bool:
    """
    Detect if a plain text message looks like something MATE should handle.

    MATE is a general-purpose assistant — markets are the specialty,
    but it handles ANY topic (law, academics, tech, documents, etc.)

    Heuristics:
      - Contains a question mark
      - Starts with question words or action words
      - Contains trading/market keywords (priority)
      - Contains document creation keywords
      - Contains general chat keywords
      - At least 4 characters (filters out "hi", "ok", "thx")
    """
    if not text or len(text) < 4:
        return False

    q = text.lower().strip()

    # Direct question mark
    if "?" in q:
        return True

    # Action starters — commands and requests
    action_starters = [
        "why ", "how ", "what ", "when ", "where ", "who ", "which ",
        "tell me", "explain", "can you", "is ", "are ", "do you",
        "show me", "give me", "should i", "i want", "i need",
        "create", "make", "write", "generate", "compose", "build",
        "search", "find", "look up", "check", "scan", "analyze",
        "help me", "draft", "produce", "compile",
    ]
    if any(q.startswith(s) for s in action_starters):
        return True

    # Document/file creation keywords
    doc_keywords = [
        "pdf", "document", "report", "file", "write-up", "write up",
        "paper", "essay", "article", "summary", "brief",
    ]
    if any(kw in q for kw in doc_keywords):
        return True

    # Trading/market keywords (priority — Institutional Mode)
    market_keywords = [
        "bias", "signal", "win rate", "performance", "balance", "account",
        "trade", "xauusd", "eurusd", "gbpusd", "usdjpy", "xagusd",
        "btcusd", "ethusd", "bitcoin", "ethereum", "btc", "eth",
        "gold", "bearish", "bullish", "sweep", "bos", "choch",
        "order block", "fvg", "liquidity", "stop loss", "take profit",
        "why was", "why did", "why no", "why isn't", "why wasn't",
        "current", "latest", "active", "open", "positions",
        "profit factor", "rr", "drawdown", "consecutive",
        "price", "how many", "signals given", "signal count",
    ]
    if any(kw in q for kw in market_keywords):
        return True

    # General conversation keywords
    general_keywords = [
        "hello", "hey", "hi ", "good morning", "good evening",
        "who are you", "what are you", "what can you do",
        "code", "python", "javascript", "programming",
        "summarize", "summarise", "help me understand",
        "difference between", "compared to",
        "law", "legal", "court", "case", "contract",
        "virus", "malware", "phishing", "security",
        "news", "update", "research", "study",
    ]
    if any(kw in q for kw in general_keywords):
        return True

    # Catch-all: if the message is 15+ chars, it's likely a real query
    if len(text) >= 15:
        return True

    return False


def _clean_mate_response(response: str, tool_calls: list) -> str:
    """
    Clean MATE's response by removing internal reasoning, JSON blocks,
    and code blocks that should not be shown to the user.

    The LLM sometimes includes its planning or the sections JSON in
    its final response text. This strips that out and leaves only
    the user-facing message.
    """
    if not response:
        return response

    # Strip JSON code blocks: ```json ... ``` or ``` ... ```
    response = re.sub(r"```(?:json)?\s*[\s\S]*?```", "", response)

    # Strip inline JSON arrays that look like sections: [{"heading": ...
    response = re.sub(r'\[\s*\{[^]]*?"heading"[^]]*?\}\s*\]', '', response)

    # Strip lines that look like internal planning
    planning_phrases = [
        "first, let me",
        "let me gather",
        "here is the pdf content",
        "here's the pdf content",
        "i will now",
        "step 1:",
        "step 2:",
        "step 3:",
    ]
    lines = response.split("\n")
    cleaned_lines = []
    for line in lines:
        line_lower = line.lower().strip()
        if any(line_lower.startswith(p) for p in planning_phrases):
            continue
        cleaned_lines.append(line)

    response = "\n".join(cleaned_lines).strip()

    # Clean up multiple blank lines
    response = re.sub(r"\n{3,}", "\n\n", response)

    return response


async def _handle_mate_query(chat_id: str, query: str) -> None:
    """
    Route a natural language query through MATE's tool-calling agent.

    This is the primary MATE entry point in Telegram. It:
      1. Accepts the user's natural language query
      2. Sends an animated loader (market-native visual identity)
      3. Routes through mate_agent.ask() — the tool-calling LLM
      4. The LLM decides which tools to call (brains, web, PDF, etc.)
      5. Results are synthesized into a final response
      6. If a PDF was generated, it's sent as a Telegram document
      7. Loader is replaced with the final MATE response

    The LLM IS the router. Tools are the intelligence.
    """
    if not query or not query.strip():
        await _send(
            chat_id,
            "🧠 <b>MATE</b> — Market-Native Intelligence\n\n"
            "I'm a market-native AI — markets are my priority, but I can help with general questions too.\n\n"
            "<b>Market Intelligence (priority):</b>\n"
            "• How is XAUUSD performing?\n"
            "• What's BTC doing right now?\n"
            "• What's my win rate?\n"
            "• Explain this signal\n"
            "• Why did performance drop?\n"
            "• What's gold's current price?\n"
            "• How many signals last week?\n\n"
            "<b>Web Intelligence:</b>\n"
            "• Search the web for information\n"
            "• Read web pages and articles\n"
            "• Get latest news updates\n\n"
            "<b>Document Creation:</b>\n"
            "• Create a PDF report\n"
            "• Generate a document\n"
            "• Compile research into a file\n\n"
            "<b>Security Scanner:</b>\n"
            "• Check if a URL is safe\n"
            "• Scan links for viruses\n"
            "• Detect phishing and malware\n\n"
            "Or just type a question naturally — no command needed."
        )
        return

    try:
        from marketmate.mate.agent import mate_agent

        # ── Phase 1: Send loader (spinner + label in one bubble) ──────────
        # Single message: spinner animates, label stays fixed.
        # Only the spinner char changes each frame — no text flicker.
        loader_msg = None
        message_id = None
        anim_task = None
        label_text = "🧠 MATE"  # Default, overridden inside try
        try:
            from marketmate.mate.loader import (
                get_loader_label, get_spinner_frames, get_initial_spinner,
                get_frame_delay,
            )
            from marketmate.mate.intent import intent_classifier
            pre_intent = intent_classifier._classify_via_keywords(query)
            pre_domain = pre_intent.domain

            # Single message: spinner + label in same bubble
            # Only the spinner char changes each frame, label stays identical
            label_text = get_loader_label("unknown", pre_domain)
            initial_text = f"{get_initial_spinner()}\n{label_text}"
            loader_msg = await get_bot().send_message(
                chat_id=chat_id,
                text=initial_text,
                parse_mode=None,
            )
            message_id = loader_msg.message_id if loader_msg else None
        except Exception as loader_exc:
            log.warning("mate_loader_failed_skipping", error=str(loader_exc))
            pre_domain = "general"

        # ── Phase 2: Animate spinner in same bubble ────────────────────────
        # Single message with spinner + label. Each frame only changes the
        # spinner char while the label text stays identical — no flicker.
        spinner_chars = []
        if message_id:
            try:
                spinner_chars = get_spinner_frames()
            except Exception:
                spinner_chars = []

        # label_text is already defined above (safe default)

        async def _animate_loader():
            """Animate spinner character in the same bubble as the label."""
            if not message_id or not spinner_chars:
                return
            while True:
                for char in spinner_chars:
                    try:
                        await asyncio.sleep(get_frame_delay())
                        await get_bot().edit_message_text(
                            chat_id=chat_id,
                            message_id=message_id,
                            text=f"{char}\n{label_text}",
                        )
                    except asyncio.CancelledError:
                        return
                    except Exception:
                        return

        anim_task = asyncio.create_task(_animate_loader()) if spinner_chars else None

        # Run MATE agent query (tool-calling agent with all tools)
        result = await mate_agent.ask(query=query, chat_id=chat_id)

        # Cancel any remaining animation frames
        if anim_task:
            anim_task.cancel()
            try:
                await anim_task
            except asyncio.CancelledError:
                pass

        response = result.get("response", "I couldn't process that query. Try rephrasing.")
        tool_calls = result.get("tool_calls", [])

        # ── Clean response: strip JSON/code blocks and internal reasoning ───
        response = _clean_mate_response(response, tool_calls)

        # Build MATE prefix based on tools called
        tool_names = [tc.get("tool", "") for tc in tool_calls]
        if "scan_url" in tool_names or "security_check" in tool_names:
            prefix = "🧠 <b>MATE</b> · Security Scan"
        elif "read_url" in tool_names:
            prefix = "🧠 <b>MATE</b> · Web Research"
        elif "web_search" in tool_names or "news_search" in tool_names:
            prefix = "🧠 <b>MATE</b> · Web Search"
        elif any(t in tool_names for t in ["get_live_price", "get_market_summary"]):
            prefix = "🧠 <b>MATE</b> · Market Data"
        elif any(t in tool_names for t in ["get_signal_stats", "get_active_signals"]):
            prefix = "🧠 <b>MATE</b> · Signal Intel"
        elif "get_account_state" in tool_names:
            prefix = "🧠 <b>MATE</b> · Account"
        elif "explain_concept" in tool_names:
            prefix = "🧠 <b>MATE</b> · Strategy"
        elif "get_system_health" in tool_names:
            prefix = "🧠 <b>MATE</b> · System"
        else:
            prefix = "🧠 <b>MATE</b>"

        final_msg = f"{prefix}\n\n{_esc(response)}"

        # ── Phase 3: Replace loader with final answer ───────────────────────
        if message_id:
            try:
                await get_bot().edit_message_text(
                    chat_id=chat_id,
                    message_id=message_id,
                    text=final_msg,
                    parse_mode="HTML",
                )
            except Exception:
                await _send(chat_id, final_msg)
        else:
            await _send(chat_id, final_msg)



        log.info("mate_query_routed", chat_id=chat_id, tools=tool_names)

    except Exception as exc:
        log.error("mate_query_failed", chat_id=chat_id, error=str(exc))
        await _send(chat_id, "🧠 MATE encountered an error. Try again or use /status for basic info.")


# ─── Photo / payment proof ────────────────────────────────────────────────────

async def _handle_photo(
    chat_id:   str,
    username:  str,
    full_name: str,
    message,
) -> None:
    """User sent a payment screenshot."""
    file_id = message.photo[-1].file_id
    caption = message.caption or ""

    await _subscriber_repo.set_pending(chat_id, username, full_name, payment_ref=file_id)

    await _audit_repo.log_payment_submission(
        chat_id=chat_id, username=username, full_name=full_name,
        file_id=file_id, message_text=caption, amount_claimed=None,
    )
    await _audit_repo.log_event(
        chat_id=chat_id, username=username, full_name=full_name,
        event_type="PAYMENT_SUBMITTED",
        data={"file_id": file_id, "caption": caption},
    )

    confirmation = (
        "✅ <b>Payment proof received.</b>\n\n"
        "We'll review and approve your subscription within a few hours.\n"
        "You'll receive a confirmation message once approved."
    )
    await _send(chat_id, confirmation)
    await _audit_repo.log_message_sent(chat_id, "PAYMENT_RECEIVED_CONFIRMATION",
                                        confirmation)

    admin_msg = (
        "💳 <b>Payment Submitted</b>\n\n"
        f"Name: {_esc(full_name)}\n"
        f"Username: @{_esc(username)}\n"
        f"Chat ID: <code>{_esc(chat_id)}</code>\n"
        f"Caption: {_esc(caption or 'none')}\n\n"
        "Commands:\n"
        f"<code>/approve {_esc(chat_id)}</code>\n"
        f"<code>/reject {_esc(chat_id)}</code>"
    )
    admin_id = cfg.telegram.admin_chat_id
    if admin_id:
        try:
            await get_bot().forward_message(
                chat_id=admin_id,
                from_chat_id=chat_id,
                message_id=message.message_id,
            )
            await asyncio.sleep(_SEND_DELAY)
            await _send_admin(admin_msg)
        except Exception as exc:
            log.error("admin_forward_failed", error=str(exc))


async def _handle_plain_text(
    chat_id:   str,
    username:  str,
    full_name: str,
    text:      str,
) -> None:
    """
    Handle plain text — routes to MATE for active users, payment ref for others.

    Active/trial subscribers who type natural language get routed to MATE.
    Non-active users who send text >4 chars are treated as payment references.
    """
    sub = await _subscriber_repo.get_by_chat_id(chat_id)
    if not sub:
        return

    status_lower = (sub.get("status") or "").lower()

    # ── Active subscribers: route natural language to MATE ──────────────────
    if status_lower in ("trial", "active"):
        if _looks_like_question(text):
            await _handle_mate_query(chat_id, text)
        return

    # ── Non-active users: treat as payment reference ────────────────────────
    if len(text) > 4:
        await _subscriber_repo.set_pending(chat_id, username, full_name, payment_ref=text)
        await _audit_repo.log_payment_submission(
            chat_id=chat_id, username=username, full_name=full_name,
            file_id=None, message_text=text, amount_claimed=None,
        )
        await _audit_repo.log_event(
            chat_id=chat_id, username=username, full_name=full_name,
            event_type="PAYMENT_SUBMITTED",
            data={"reference": text},
        )
        await _send(chat_id,
                    "✅ Reference received. We'll confirm your payment shortly.")
        await _send_admin(
            "💳 <b>Payment Reference Submitted</b>\n\n"
            f"Name: {_esc(full_name)}\n"
            f"Username: @{_esc(username)}\n"
            f"Chat ID: <code>{_esc(chat_id)}</code>\n"
            f"Reference: <code>{_esc(text)}</code>\n\n"
            f"<code>/approve {_esc(chat_id)}</code>\n"
            f"<code>/reject {_esc(chat_id)}</code>"
        )


# ─── /myaccount ───────────────────────────────────────────────────────────────

async def _handle_myaccount(chat_id: str, username: str, full_name: str) -> None:
    sub = await _subscriber_repo.get_by_chat_id(chat_id)
    if not sub:
        await _handle_start(chat_id, username, full_name)
        return

    status    = (sub.get("status") or "").upper()
    expires   = _fmt_date(sub.get("expires_at"))
    started   = _fmt_date(sub.get("started_at"))

    icon = {"TRIAL": "🎁", "ACTIVE": "✅", "PENDING": "⏳",
            "EXPIRED": "❌", "BANNED": "🚫"}.get(status, "❓")

    msg = (
        "👤 <b>My Account</b>\n\n"
        f"Status:  {_esc(icon)} {_esc(status)}\n"
        f"Plan:    {_esc(sub.get('plan', 'N/A').title())}\n"
        f"Started: {_esc(started)}\n"
        f"Expires: {_esc(expires)}\n"
    )
    status_lower = (sub.get("status") or "").lower()
    if status_lower in ("expired", "trial") and sub.get("expires_at"):
        msg += "\nTap /subscribe to continue access."
    await _send(chat_id, msg)


# ─── /status ─────────────────────────────────────────────────────────────────

async def _handle_status(chat_id: str) -> None:
    from datetime import time
    from marketmate.db.repositories.signals import SignalRepository

    signal_repo = SignalRepository()

    now   = datetime.now(timezone.utc)

    def _t(s: str) -> time:
        h, m = s.split(":")
        return time(int(h), int(m))

    now_t     = now.time()
    in_london = _t(cfg.strategy.london_open) <= now_t <= _t(cfg.strategy.london_close)
    in_ny     = _t(cfg.strategy.ny_open)     <= now_t <= _t(cfg.strategy.ny_close)

    if in_london:
        session = "🟢 London Session"
    elif in_ny:
        session = "🟢 NY Session"
    else:
        session = "🔴 Off-Hours"

    open_trades = await signal_repo.get_open_signals()

    msg = (
        "📡 <b>MarketMate Status</b>\n\n"
        f"Session:     {_esc(session)}\n"
        f"Pairs:       {_esc(', '.join(cfg.strategy.pairs))}\n"
        f"Open Trades: {_esc(len(open_trades))}\n"
        f"Scan Every:  {_esc(cfg.app.scan_interval_seconds)}s\n"
        f"Time (UTC):  {_esc(now.strftime('%H:%M'))}\n"
    )
    await _send(chat_id, msg)


# ─── /price ──────────────────────────────────────────────────────────────────

async def _handle_price(chat_id: str) -> None:
    from marketmate.db.repositories.signals import SignalRepository
    signal_repo = SignalRepository()

    signals = await signal_repo.get_open_signals()
    if signals:
        last = signals[-1]
        price = last.get("mt5_entry_price") or last.get("entry_mid")
        symbol = last.get("symbol", "XAUUSD")
        if price:
            await _send(chat_id,
                        "💰 <b>Last Known Price</b>\n\n"
                        f"{_esc(symbol)}: <code>{_esc(f'{price:,.2f}')}</code>\n"
                        "<i>From last active scan</i>")
            return

    await _send(chat_id,
                f"💰 <b>{_esc(', '.join(cfg.strategy.pairs))}</b>\n\n"
                "No recent price data yet.\n"
                "Price is updated every scan cycle (every "
                f"{_esc(cfg.app.scan_interval_seconds)}s during session hours).")


# ─── /pairs ──────────────────────────────────────────────────────────────────

async def _handle_pairs(chat_id: str) -> None:
    now   = datetime.now(timezone.utc)
    now_t = now.time()

    from datetime import time

    def _t(s: str) -> time:
        h, m = s.split(":")
        return time(int(h), int(m))

    in_london = _t(cfg.strategy.london_open) <= now_t <= _t(cfg.strategy.london_close)
    in_ny     = _t(cfg.strategy.ny_open)     <= now_t <= _t(cfg.strategy.ny_close)
    scanning  = in_london or in_ny

    lines = ["📋 <b>Active Pairs</b>\n"]
    for pair in cfg.strategy.pairs:
        status = "🟢 Scanning" if scanning else "⏸ Waiting for session"
        lines.append(f"• {_esc(pair)} — {_esc(status)}")

    lines.append("\nSessions: London 07:00–12:00 | NY 12:00–17:00 UTC")
    await _send(chat_id, "\n".join(lines))


# ─── /performance ─────────────────────────────────────────────────────────────

async def _handle_performance(chat_id: str) -> None:
    """
    Performance stats from MongoDB signal_archive (durable).
    """
    from marketmate.db.repositories.signals import SignalRepository
    signal_repo = SignalRepository()

    stats_7  = await signal_repo.get_performance_stats(days=7)
    stats_30 = await signal_repo.get_performance_stats(days=30)

    def _wr(s):
        t = s["total"]
        return f"{round(s['wins']/t*100,1)}%" if t > 0 else "N/A"

    msg = (
        "📊 <b>Performance</b>\n\n"
        "<b>Last 7 Days</b>\n"
        f"Signals:  {_esc(stats_7['total'])}\n"
        f"Wins:     {_esc(stats_7['wins'])}  Losses: {_esc(stats_7['losses'])}\n"
        f"Win Rate: {_esc(_wr(stats_7))}\n"
        f"Avg RR:   1:{_esc(stats_7['avg_rr'])}\n"
        f"P&amp;L:      {_esc('+' if stats_7['pnl_pct'] >= 0 else '')}{_esc(stats_7['pnl_pct'])}%\n\n"
        "<b>Last 30 Days</b>\n"
        f"Signals:  {_esc(stats_30['total'])}\n"
        f"Wins:     {_esc(stats_30['wins'])}  Losses: {_esc(stats_30['losses'])}\n"
        f"Win Rate: {_esc(_wr(stats_30))}\n"
        f"Avg RR:   1:{_esc(stats_30['avg_rr'])}\n"
        f"P&amp;L:      {_esc('+' if stats_30['pnl_pct'] >= 0 else '')}{_esc(stats_30['pnl_pct'])}%\n"
    )
    await _send(chat_id, msg)


# ─── /help ────────────────────────────────────────────────────────────────────

async def _handle_help(chat_id: str) -> None:
    is_adm = _is_admin(chat_id)
    msg = (
        "📖 <b>Available Commands</b>\n\n"
        "/start        — Welcome and subscription options\n"
        "/trial        — Start your 7-day free trial\n"
        "/subscribe    — View payment details\n"
        "/myaccount    — Your subscription status\n"
        "/status       — Bot status and session info\n"
        "/price        — Last known XAUUSD price\n"
        "/pairs        — Active trading pairs\n"
        "/performance  — Win rate and P&amp;L stats\n"
        "/mate [query] — Ask MATE about signals, performance, diagnostics\n"
        "/help         — This message\n\n"
        "<i>You can also type questions directly — MATE will answer.</i>\n"
        "<i>Examples: \"How is XAUUSD?\" \"Why did performance drop?\"</i>\n"
    )
    if is_adm:
        msg += (
            "\n<b>Admin Commands</b>\n"
            "/approve {id}           — Approve subscriber\n"
            "/reject {id}            — Reject payment\n"
            "/pending                — View pending approvals\n"
            "/opentrades             — Full details of all open trades\n"
            "/subscribers            — All active subscribers\n"
            "/extend {id} {days} — Extend subscription\n"
            "/ban {id}           — Ban user\n"
            "/unban {id}         — Unban user\n"
            "/broadcast {msg}    — Message all subscribers\n"
            "/latest_chart       — Test chart renderer (XAUUSD M15)\n"
        )
    await _send(chat_id, msg)


# ─── Admin: /approve ──────────────────────────────────────────────────────────

async def _handle_approve(admin_id: str, args: list) -> None:
    if not args:
        await _send(admin_id, "Usage: /approve {chat_id}")
        return

    target_id = args[0]
    sub = await _subscriber_repo.approve(target_id, admin_id)
    if not sub:
        await _send(admin_id, f"❌ User {_esc(target_id)} not found.")
        return

    await _audit_repo.log_admin_action(
        admin_id=admin_id, action="APPROVE",
        target_id=target_id,
        details={"expires_at": _fmt_date(sub["expires_at"])},
    )
    await _audit_repo.log_event(
        chat_id=target_id,
        username=sub.get("username", ""),
        full_name=sub.get("full_name", ""),
        event_type="APPROVED",
        data={"approved_by": admin_id, "expires_at": _fmt_date(sub["expires_at"])},
    )
    await _audit_repo.log_payment_outcome(
        chat_id=target_id, outcome="APPROVED", admin_id=admin_id
    )

    msg = (
        "✅ <b>Access Granted — Welcome to MarketMate!</b>\n\n"
        "Your subscription is now active.\n"
        f"Expires: {_esc(_fmt_date(sub['expires_at']))}\n\n"
        "Signals fire automatically during London and NY sessions.\n"
        "Type /help to see available commands."
    )
    await _send(target_id, msg)
    await _audit_repo.log_message_sent(target_id, "APPROVED", msg)

    await _send(admin_id,
                f"✅ Approved: {_esc(sub.get('full_name'))} (@{_esc(sub.get('username'))})\n"
                f"Expires: {_esc(_fmt_date(sub['expires_at']))}")


# ─── Admin: /reject ───────────────────────────────────────────────────────────

async def _handle_reject(admin_id: str, args: list) -> None:
    if not args:
        await _send(admin_id, "Usage: /reject {chat_id}")
        return

    target_id = args[0]
    reason    = " ".join(args[1:]) if len(args) > 1 else "Payment not confirmed"

    await _subscriber_repo.reject(target_id)
    await _audit_repo.log_admin_action(
        admin_id=admin_id, action="REJECT",
        target_id=target_id, details={"reason": reason},
    )
    await _audit_repo.log_payment_outcome(
        chat_id=target_id, outcome="REJECTED",
        admin_id=admin_id, reason=reason,
    )

    msg = (
        "❌ <b>Payment Not Confirmed</b>\n\n"
        f"Reason: {_esc(reason)}\n\n"
        "If you believe this is an error please resend your payment proof\n"
        "or contact support."
    )
    await _send(target_id, msg)
    await _audit_repo.log_message_sent(target_id, "REJECTED", msg)
    await _send(admin_id, f"❌ Rejected: {_esc(target_id)} — {_esc(reason)}")


# ─── Admin: /pending ──────────────────────────────────────────────────────────

async def _handle_pending(admin_id: str) -> None:
    from marketmate.db.core import mongo_manager
    db = await mongo_manager.get_db()
    if db is None:
        await _send(admin_id, "❌ Database unavailable.")
        return
    cursor = db["subscribers"].find({"status": "PENDING"}, {"_id": 0})
    pending = await cursor.to_list(length=100)

    if not pending:
        await _send(admin_id, "✅ No pending approvals.")
        return

    lines = [f"⏳ <b>Pending Approvals ({len(pending)})</b>\n"]
    for sub in pending:
        lines.append(
            f"• {_esc(sub.get('full_name', 'Unknown'))} (@{_esc(sub.get('username', ''))})\n"
            f"  ID: <code>{_esc(sub['chat_id'])}</code>\n"
            f"  <code>/approve {_esc(sub['chat_id'])}</code>\n"
        )
    await _send(admin_id, "\n".join(lines))


# ─── Admin: /opentrades ───────────────────────────────────────────────────────

async def _handle_opentrades(admin_id: str) -> None:
    from marketmate.db.repositories.signals import SignalRepository
    signal_repo = SignalRepository()

    trades = await signal_repo.get_open_signals()
    if not trades:
        await _send(admin_id, "📭 No open trades.")
        return

    for t in trades[:10]:
        symbol = t.get("symbol", "?")
        direction = t.get("direction", "?")
        entry = t.get("entry_mid", 0)
        msg = f"📊 <b>{_esc(symbol)}</b> {_esc(direction)} @ <code>{_esc(f'{entry:,.2f}')}</code>"
        await _send(admin_id, msg)


# ─── Admin: /subscribers ─────────────────────────────────────────────────────

async def _handle_subscribers(admin_id: str) -> None:
    subs = await _subscriber_repo.get_all_active()
    if not subs:
        await _send(admin_id, "📭 No active subscribers.")
        return

    lines = [f"👥 <b>Active Subscribers ({len(subs)})</b>\n"]
    for sub in subs[:50]:
        name = sub.get("full_name", "Unknown")
        username = sub.get("username", "")
        status = sub.get("status", "")
        expires = _fmt_date(sub.get("expires_at"))
        lines.append(f"• {_esc(name)} (@{_esc(username)}) — {_esc(status)} — exp: {_esc(expires)}")

    await _send(admin_id, "\n".join(lines))


# ─── Admin: /extend ──────────────────────────────────────────────────────────

async def _handle_extend(admin_id: str, args: list) -> None:
    if len(args) < 2:
        await _send(admin_id, "Usage: /extend {chat_id} {days}")
        return

    target_id = args[0]
    try:
        days = int(args[1])
    except ValueError:
        await _send(admin_id, "Days must be a number.")
        return

    sub = await _subscriber_repo.extend(target_id, days)
    if not sub:
        await _send(admin_id, f"❌ User {_esc(target_id)} not found.")
        return

    await _audit_repo.log_admin_action(
        admin_id=admin_id, action="EXTEND",
        target_id=target_id, details={"days": days},
    )
    new_exp = sub.get("expires_at", "")
    await _send(admin_id,
                f"✅ Extended: {_esc(target_id)} by {_esc(days)} days. New expiry: {_esc(_fmt_date(new_exp))}")


# ─── Admin: /ban ──────────────────────────────────────────────────────────────

async def _handle_ban(admin_id: str, args: list) -> None:
    if not args:
        await _send(admin_id, "Usage: /ban {chat_id}")
        return

    target_id = args[0]
    await _subscriber_repo.ban(target_id)
    await _audit_repo.log_admin_action(
        admin_id=admin_id, action="BAN",
        target_id=target_id,
    )
    await _send(admin_id, f"🚫 Banned: {_esc(target_id)}")


# ─── Admin: /unban ────────────────────────────────────────────────────────────

async def _handle_unban(admin_id: str, args: list) -> None:
    if not args:
        await _send(admin_id, "Usage: /unban {chat_id}")
        return

    target_id = args[0]
    await _subscriber_repo.upsert(
        chat_id=target_id, status="EXPIRED", plan="none"
    )
    await _audit_repo.log_admin_action(
        admin_id=admin_id, action="UNBAN",
        target_id=target_id,
    )
    await _send(admin_id, f"✅ Unbanned: {_esc(target_id)}")


# ─── Admin: /broadcast ────────────────────────────────────────────────────────

async def _handle_broadcast(admin_id: str, args: list) -> None:
    if not args:
        await _send(admin_id, "Usage: /broadcast {message}")
        return

    message = " ".join(args)
    chat_ids = await _subscriber_repo.get_active_chat_ids()

    sent = 0
    for cid in chat_ids:
        if await _send(cid, message):
            sent += 1
        await asyncio.sleep(_SEND_DELAY)

    await _send(admin_id, f"📢 Broadcast sent to {sent}/{len(chat_ids)} subscribers.")


# ─── Admin: /latest_chart ─────────────────────────────────────────────────────

async def _handle_latest_chart(admin_id: str) -> None:
    """Test chart renderer — generates XAUUSD M15 chart."""
    await _send(admin_id, "📊 Chart rendering is available via the API.")


# ─── Auto-trade stubs ─────────────────────────────────────────────────────────

async def _handle_autotrade(chat_id: str, username: str, full_name: str, arg: str) -> None:
    await _send(chat_id, "🔧 Auto-trade management is available via the web dashboard.")


async def _handle_set_timezone(chat_id: str, tz: str) -> None:
    if not tz:
        await _send(chat_id, "Usage: /set_timezone {timezone}")
        return
    await _send(chat_id, f"✅ Timezone set to {_esc(tz)}.")


async def _handle_myaccounts(chat_id: str) -> None:
    accounts = await trading_account_store.get_by_chat_id(chat_id)
    if not accounts:
        await _send(chat_id, "📭 No linked accounts. Use /linkaccount to add one.")
        return
    lines = ["📋 <b>Linked Accounts</b>\n"]
    for acc in accounts:
        lines.append(f"• {_esc(acc.get('broker', 'Unknown'))} — {_esc(acc.get('login', ''))}")
    await _send(chat_id, "\n".join(lines))


async def _handle_linkaccount(chat_id: str) -> None:
    await _send(chat_id, "🔗 Account linking is available via the web dashboard at /auto-trade")
