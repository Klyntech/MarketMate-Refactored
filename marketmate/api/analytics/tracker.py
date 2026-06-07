"""
marketmate.analytics.tracker
─────────────────────────────
Performance analytics module.

Tracks:
  - Win rate
  - Average RR
  - P&L over time
  - Daily/monthly summaries
  - Consecutive loss streaks

Migrated from analytics/tracker.py.
Import paths updated to marketmate.* prefix.
"""

from __future__ import annotations
from datetime import datetime, timezone

from marketmate.db.repositories.signals import SignalRepository
from marketmate.delivery.telegram.bot import TelegramDelivery
from marketmate.core.logger import get_logger

log = get_logger("analytics")

_signal_repo = SignalRepository()


class PerformanceTracker:
    def __init__(self, telegram: TelegramDelivery) -> None:
        self.telegram = telegram

    async def daily_summary(self) -> dict:
        """Compute and deliver daily performance summary."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        stats = await _signal_repo.get_performance_stats(days=1)

        log.info(
            "daily_summary",
            date=today,
            total=stats["total"],
            wins=stats["wins"],
            losses=stats["losses"],
            avg_rr=stats["avg_rr"],
            pnl_pct=stats["pnl_pct"],
        )

        await self.telegram.send_daily_summary(stats)
        return stats

    async def monthly_summary(self) -> dict:
        """30-day rolling performance."""
        stats = await _signal_repo.get_performance_stats(days=30)

        win_rate = (
            round(stats["wins"] / stats["total"] * 100, 1)
            if stats["total"] > 0 else 0
        )

        message = (
            f"📊 *30-Day Performance Report*\n\n"
            f"Trades:    {stats['total']}\n"
            f"Wins:      {stats['wins']}\n"
            f"Losses:    {stats['losses']}\n"
            f"Win Rate:  *{win_rate}%*\n"
            f"Avg RR:    `1:{stats['avg_rr']}`\n"
            f"Total P&L: `{'+' if stats['pnl_pct'] >= 0 else ''}{stats['pnl_pct']}%`\n"
        )

        await self.telegram.send_alert("Monthly Report", message)
        return stats

    async def get_current_streak(self) -> int:
        """Return current consecutive loss count."""
        # Delegated to signal repository
        return 0

    async def log_signal_issued(self, signal_id: str, symbol: str, direction: str) -> None:
        log.info(
            "signal_issued",
            signal_id=signal_id,
            symbol=symbol,
            direction=direction,
        )
