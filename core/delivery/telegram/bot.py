"""
marketmate.delivery.telegram.bot
─────────────────────────────────
Outbound signal and lifecycle message delivery.

All public messages (signals, TP hits, SL hits, summaries) are sent to
active subscribers only — not a fixed channel.

_send() accepts an optional chat_id_override so reminders.py and
bot_handler.py can reuse the same send infrastructure.

Migrated from delivery/telegram_bot.py.
Import paths updated to marketmate.* prefix.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Optional

from telegram import Bot
from telegram.error import TelegramError, RetryAfter

from signal_engine.core.config import cfg
from signal_engine.core.logger import get_logger

log = get_logger("telegram")

_SEND_DELAY = 1.0


class TelegramDelivery:
    def __init__(self) -> None:
        self._bot     = None
        self._chat_id = cfg.telegram.chat_id
        # Lazy Bot creation — only instantiate when token is present
        if cfg.telegram.is_configured:
            try:
                self._bot = Bot(token=cfg.telegram.bot_token)
            except Exception as exc:
                log.warning("telegram_bot_init_failed", error=str(exc))

    # ── Signal ────────────────────────────────────────────────────────────────

    async def send_signal(self, signal, recipient_ids: list[str] = None) -> None:
        """
        Send signal to a list of chat_ids concurrently.
        Falls back to cfg.telegram.chat_id if no list provided.
        """
        message = _format_signal(signal)
        if recipient_ids:
            await asyncio.gather(
                *[self._send(message, chat_id_override=cid) for cid in recipient_ids],
                return_exceptions=True,
            )
        else:
            await self._send(message)

    # ── Trade lifecycle ───────────────────────────────────────────────────────

    async def send_tp_hit(
        self, signal, tp_level: str, price: float,
        recipient_ids: list[str] = None,
    ) -> bool:
        icon = "🟢"
        message = (
            f"{icon} *TP Hit — {signal.symbol}*\n"
            f"Signal: `{signal.id}`\n"
            f"Level: *{tp_level}* @ `{_fmt(price, signal.symbol)}`\n"
            f"Direction: {signal.direction}\n"
            f"Time: {_utc_now()}"
        )
        return await self._send_to(message, recipient_ids)

    async def send_sl_hit(
        self, signal, price: float,
        recipient_ids: list[str] = None,
    ) -> bool:
        message = (
            f"🔴 *Stop Loss Hit — {signal.symbol}*\n"
            f"Signal: `{signal.id}`\n"
            f"SL: `{_fmt(price, signal.symbol)}`\n"
            f"Direction: {signal.direction}\n"
            f"Time: {_utc_now()}"
        )
        return await self._send_to(message, recipient_ids)

    async def send_breakeven(
        self, signal, new_sl: float,
        recipient_ids: list[str] = None,
    ) -> bool:
        message = (
            f"🔵 *Break-Even Set — {signal.symbol}*\n"
            f"Signal: `{signal.id}`\n"
            f"New SL: `{_fmt(new_sl, signal.symbol)}` (entry)\n"
            f"Time: {_utc_now()}"
        )
        return await self._send_to(message, recipient_ids)

    async def send_partial_close(
        self, signal, tp_level: str, closed_pct: int,
        recipient_ids: list[str] = None,
    ) -> bool:
        message = (
            f"🟡 *Partial Close — {signal.symbol}*\n"
            f"Signal: `{signal.id}`\n"
            f"Closed {closed_pct}% at {tp_level}\n"
            f"Time: {_utc_now()}"
        )
        return await self._send_to(message, recipient_ids)

    # ── Alerts ────────────────────────────────────────────────────────────────

    async def send_alert(self, title: str, body: str) -> bool:
        message = f"⚠️ *{title}*\n{body}\n{_utc_now()}"
        return await self._send(message)

    async def send_daily_summary(self, summary: dict) -> bool:
        message = _format_summary(summary)
        return await self._send(message)

    async def send_admin_execution_log(self, body: str) -> bool:
        """Send admin-only message to TELEGRAM_ADMIN_CHAT_ID."""
        admin_id = cfg.telegram.admin_chat_id
        if not admin_id:
            return True
        return await self._send(f"🔒 *ADMIN*\n{body}",
                                chat_id_override=admin_id)

    async def send_chart_photo(
        self,
        chart_path: str,
        caption: str,
        recipient_ids: list,
    ) -> None:
        """Send a chart image to a list of recipients, reusing the bot instance."""
        if self._bot is None:
            log.warning("telegram_chart_not_configured")
            return
        for cid in recipient_ids:
            try:
                with open(chart_path, "rb") as img:
                    await self._bot.send_photo(
                        chat_id=cid,
                        photo=img,
                        caption=caption,
                    )
            except Exception as e:
                log.warning("chart_send_failed", chat_id=cid, error=str(e))

    # ── Core sender ───────────────────────────────────────────────────────────

    async def _send(
        self,
        text: str,
        chat_id_override: Optional[str] = None,
    ) -> bool:
        chat_id = chat_id_override or self._chat_id
        if self._bot is None:
            log.warning("telegram_not_configured",
                        hint="Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID to enable delivery")
            return False
        try:
            await self._bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode="Markdown",
            )
            log.debug("telegram_sent",
                      chat_id=chat_id, chars=len(text))
            return True
        except RetryAfter as e:
            wait = e.retry_after or 5
            log.warning("telegram_rate_limited",
                        chat_id=chat_id, retry_after=wait)
            await asyncio.sleep(wait)
            try:
                await self._bot.send_message(
                    chat_id=chat_id,
                    text=text,
                    parse_mode="Markdown",
                )
                return True
            except Exception as retry_exc:
                log.error("telegram_retry_failed",
                          chat_id=chat_id, error=str(retry_exc))
                return False
        except TelegramError as e:
            log.error("telegram_error",
                      chat_id=chat_id, error=str(e))
            return False
        except Exception as e:
            log.error("telegram_unexpected_error",
                      chat_id=chat_id, error=str(e))
            return False

    async def _send_to(
        self,
        message: str,
        recipient_ids: Optional[list[str]],
    ) -> bool:
        if recipient_ids:
            results = await asyncio.gather(
                *[self._send(message, chat_id_override=cid) for cid in recipient_ids],
                return_exceptions=True,
            )
            return all(r is True for r in results)
        return await self._send(message)


# ─── Formatters ───────────────────────────────────────────────────────────────

def _format_signal(s) -> str:
    """Format signal in the clean institutional signal format."""
    sym = s.symbol
    direction = s.direction

    # Direction icon and colour indicator
    if direction == "BUY":
        icon = "🟢"
    else:
        icon = "🔴"

    # Entry price — use zone midpoint
    entry_price = getattr(s, "entry_mid", (s.entry_low + s.entry_high) / 2)

    # TP3 line — only include if TP3 exists and is non-zero
    tp3_line = f"TP3: {_fmt(s.tp3, sym)}\n" if s.tp3 and s.tp3 != 0 else ""

    # Strategy version
    version = getattr(s, "strategy_version", "MarketMate v2.1")

    # RR formatting — ensure at least 1 decimal
    rr_val = s.rr if s.rr else 0

    # Timestamp
    ts = _utc_now()

    return f"""{icon} {direction} {sym}

Entry: {_fmt(entry_price, sym)}
SL: {_fmt(s.stop_loss, sym)}

TP1: {_fmt(s.tp1, sym)}
TP2: {_fmt(s.tp2, sym)}
{tp3_line}RR: 1:{rr_val:.1f}

Strategy: {version}
Time: {ts}""".rstrip()


def _format_summary(summary: dict) -> str:
    total  = summary.get("total", 0)
    wins   = summary.get("wins", 0)
    losses = summary.get("losses", 0)
    wr     = round(wins / total * 100, 1) if total > 0 else 0
    avg_rr = summary.get("avg_rr", 0)
    pnl    = summary.get("pnl_pct", 0)

    return f"""
📅 *Daily Summary*

Trades: {total}  |  W: {wins}  L: {losses}
Win Rate: *{wr}%*
Avg RR: `1:{avg_rr}`
P&L: `{'+' if pnl >= 0 else ''}{pnl}%`

{_utc_now()}
""".strip()


def _fmt(value: Optional[float], symbol: str = "") -> str:
    if value is None:
        return "N/A"
    if value >= 100:
        return f"{value:,.2f}"
    elif value >= 1:
        return f"{value:.5f}"
    else:
        return f"{value:.6f}"


def _utc_now() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
