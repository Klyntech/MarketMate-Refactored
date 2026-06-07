"""
MarketMate Refactored — Signal Engine + Telegram Delivery

Standalone signal engine that:
  - Runs the 8-Gate Signal Pipeline (G1→G8)
  - Delivers signals via Telegram
  - Responds to basic Telegram commands via polling
  - Uses MongoDB for persistence (optional)

No AI, no web server, no FastAPI — just signals + Telegram.
"""

from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

from signal_engine.core.config import cfg
from signal_engine.core.logger import get_logger
from signal_engine.core.events import event_bus, EventType
from signal_engine.strategy.engine import SignalEngine
from signal_engine.strategy.models import DailyState
from signal_engine.execution.risk import RiskManager
from signal_engine.delivery.telegram.bot import TelegramDelivery
from signal_engine.data.engine import MarketDataEngine

log = get_logger("main")


class SignalEngineApp:
    """Standalone signal engine with Telegram delivery."""

    def __init__(self) -> None:
        self.signal_engine: Optional[SignalEngine] = None
        self.telegram: Optional[TelegramDelivery] = None
        self.data_engine: Optional[MarketDataEngine] = None
        self._shutdown = asyncio.Event()
        self._daily_state = DailyState()

    async def initialize(self) -> None:
        """Initialize all components."""
        log.info("signal_engine_starting", pairs=cfg.strategy.pairs, env=cfg.app.env)

        # Optional MongoDB
        mongo_manager = None
        try:
            from signal_engine.db.core import mongo_manager as _mm
            await _mm.connect()
            mongo_manager = _mm
            log.info("mongodb_connected")
        except Exception as exc:
            log.warning("mongodb_unavailable", error=str(exc), hint="Running without persistence")

        # Data engine
        self.data_engine = MarketDataEngine(config=cfg, mongo_manager=mongo_manager)

        # Signal engine
        risk_manager = RiskManager()
        self.signal_engine = SignalEngine(
            risk_manager=risk_manager,
            daily_state=self._daily_state,
            event_bus=event_bus,
        )

        # Try to load dedup state from MongoDB
        try:
            await self.signal_engine.load_dedup_state()
        except Exception:
            log.info("dedup_state_load_skipped", hint="Starting with fresh state")

        # Telegram delivery
        self.telegram = TelegramDelivery()

        # Subscribe to signal events
        event_bus.subscribe(EventType.SIGNAL_CREATED, self._on_signal_created)

        log.info("signal_engine_initialized")

    async def _on_signal_created(self, **kwargs) -> None:
        """Handle signal_created event: validate then deliver via Telegram."""
        signal_data = kwargs.get("signal", kwargs)
        if not signal_data:
            return

        try:
            # Create a simple signal object for delivery
            from signal_engine.strategy.models import Signal
            if isinstance(signal_data, dict):
                signal = Signal()
                for k, v in signal_data.items():
                    if hasattr(signal, k):
                        setattr(signal, k, v)
            else:
                signal = signal_data

            # ── Signal Validation ────────────────────────────────────────
            from signal_engine.delivery.telegram.validator import validate_signal
            is_valid, reasons = validate_signal(signal)
            if not is_valid:
                log.error(
                    "signal_rejected_by_validator",
                    signal_id=signal.id,
                    symbol=signal.symbol,
                    direction=signal.direction,
                    reasons=reasons,
                )
                # Alert admin about rejected signal
                try:
                    await self.telegram.send_admin_execution_log(
                        f"Signal REJECTED: {signal.symbol} {signal.direction}\n"
                        f"Reasons: {'; '.join(reasons)}"
                    )
                except Exception:
                    pass
                return

            # Send signal message
            await self.telegram.send_signal(signal)

            # Try to render and send chart
            try:
                df = await self.data_engine.fetch_candles(signal.symbol, "4h", limit=100)
                if df is not None and not df.empty:
                    from signal_engine.delivery.telegram.charts import render_signal_chart
                    chart_path = await render_signal_chart(signal, df)
                    if chart_path:
                        await self.telegram.send_chart_photo(
                            chart_path,
                            f"{signal.direction} {signal.symbol} | 1:{signal.rr}R",
                            [cfg.telegram.chat_id],
                        )
                        # Cleanup temp file
                        try:
                            os.unlink(chart_path)
                        except Exception:
                            pass
            except Exception as chart_exc:
                log.warning("chart_delivery_failed", error=str(chart_exc))

            log.info(
                "signal_delivered",
                signal_id=signal.id,
                symbol=signal.symbol,
                direction=signal.direction,
            )

            # Store for /last command
            self._last_signal = signal
        except Exception as exc:
            log.error("signal_delivery_error", error=str(exc))

    async def run_scan_loop(self) -> None:
        """Main scan loop."""
        interval = cfg.app.scan_interval_seconds
        log.info("scan_loop_started", interval_s=interval)

        while not self._shutdown.is_set():
            start = datetime.now(timezone.utc)

            # Refresh daily state from DB (optional)
            try:
                from signal_engine.db import get_signals_repo
                repo = get_signals_repo()
                today = start.strftime("%Y-%m-%d")
                self._daily_state.trades_today = await repo.get_daily_count(today)
                self._daily_state.consecutive_losses = await repo.get_consecutive_losses()
            except Exception:
                pass  # Running without DB

            for symbol in cfg.strategy.pairs:
                if self._shutdown.is_set():
                    break
                try:
                    signal = await self.signal_engine.run(symbol)
                    if signal is not None:
                        log.info(
                            "signal_generated",
                            signal_id=signal.id,
                            symbol=symbol,
                            direction=signal.direction,
                            rr=signal.rr,
                        )
                except Exception as exc:
                    log.error("scan_error", symbol=symbol, error=str(exc))

            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            log.info("scan_cycle_complete", elapsed_s=round(elapsed, 2))

            try:
                await asyncio.wait_for(self._shutdown.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def run_telegram_polling(self) -> None:
        """Run Telegram bot with polling for basic commands."""
        if not cfg.telegram.is_configured:
            log.warning("telegram_not_configured", hint="Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID")
            return

        try:
            from telegram import Update
            from telegram.ext import Application, CommandHandler, ContextTypes

            app = Application.builder().token(cfg.telegram.bot_token).build()

            # Store last signal for /last command
            self._last_signal = None

            async def start_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
                await update.message.reply_text(
                    f"📊 *MarketMate Signal Engine*\n\n"
                    f"Strategy: {cfg.strategy.version}\n"
                    f"Institutional-grade signals powered by Smart Money Concepts.\n\n"
                    f"• 8-Gate Signal Pipeline\n"
                    f"• London & NY Session Focus\n"
                    f"• Entry Zone + SL + TP1/TP2/TP3\n"
                    f"• Pre-delivery Validation\n\n"
                    f"Commands:\n"
                    f"/status — Engine status\n"
                    f"/pairs — Traded pairs\n"
                    f"/last — Last signal sent\n"
                    f"/version — Strategy version\n"
                    f"/help — Available commands"
                )

            async def status_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
                now = datetime.now(timezone.utc)
                in_session = (
                    cfg.strategy.london_open <= now.strftime("%H:%M") <= cfg.strategy.ny_close
                    and now.weekday() < 5
                )
                await update.message.reply_text(
                    f"📊 *Engine Status*\n\n"
                    f"Strategy: {cfg.strategy.version}\n"
                    f"Status: ✅ Running\n"
                    f"Session: {'🟢 Active' if in_session else '🔴 Closed'}\n"
                    f"Pairs: {', '.join(cfg.strategy.pairs)}\n"
                    f"Trades today: {self._daily_state.trades_today}/{cfg.strategy.max_trades_per_day}\n"
                    f"Consecutive losses: {self._daily_state.consecutive_losses}\n"
                    f"Scan interval: {cfg.app.scan_interval_seconds}s\n"
                    f"Validation: ENABLED\n"
                    f"Time (UTC): {now.strftime('%Y-%m-%d %H:%M')}"
                )

            async def pairs_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
                pairs_list = "\n".join(f"• {p}" for p in cfg.strategy.pairs)
                await update.message.reply_text(f"📊 *Traded Pairs*\n\n{pairs_list}")

            async def last_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
                if self._last_signal is None:
                    await update.message.reply_text("No signals sent yet.")
                    return
                from signal_engine.delivery.telegram.bot import _format_signal
                msg = _format_signal(self._last_signal)
                await update.message.reply_text(msg, parse_mode="Markdown")

            async def version_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
                await update.message.reply_text(
                    f"📊 *Strategy Version*\n\n"
                    f"Version: {cfg.strategy.version}\n"
                    f"Pipeline: 8-Gate (G1-G8)\n"
                    f"Min RR: {cfg.strategy.min_rr}\n"
                    f"Max trades/day: {cfg.strategy.max_trades_per_day}\n"
                    f"Scan interval: {cfg.app.scan_interval_seconds}s"
                )

            async def help_cmd(update: Update, context: ContextTypes.DEFAULT_TYPE):
                await update.message.reply_text(
                    f"📊 *MarketMate Signal Engine*\n\n"
                    f"Strategy: {cfg.strategy.version}\n\n"
                    f"Commands:\n"
                    f"/start — Welcome message\n"
                    f"/status — Engine status & session info\n"
                    f"/pairs — Currently traded pairs\n"
                    f"/last — Most recent signal\n"
                    f"/version — Strategy version\n"
                    f"/help — This message\n\n"
                    f"Signals are delivered automatically when the 8-Gate pipeline finds a valid setup."
                )

            app.add_handler(CommandHandler("start", start_cmd))
            app.add_handler(CommandHandler("status", status_cmd))
            app.add_handler(CommandHandler("pairs", pairs_cmd))
            app.add_handler(CommandHandler("last", last_cmd))
            app.add_handler(CommandHandler("version", version_cmd))
            app.add_handler(CommandHandler("help", help_cmd))

            log.info("telegram_polling_started")
            await app.run_polling(drop_pending_updates=True)

        except Exception as exc:
            log.error("telegram_polling_error", error=str(exc))

    async def start(self) -> None:
        """Start the signal engine."""
        await self.initialize()

        # Startup alert
        try:
            await self.telegram.send_alert(
                "Signal Engine Online",
                f"Strategy: {cfg.strategy.version}\n"
                f"Pairs: {', '.join(cfg.strategy.pairs)}\n"
                f"Max trades/day: {cfg.strategy.max_trades_per_day}\n"
                f"Min RR: {cfg.strategy.min_rr}\n"
                f"Scan interval: {cfg.app.scan_interval_seconds}s\n"
                f"Validation: ENABLED",
            )
        except Exception:
            pass

        # Run both loops concurrently
        await asyncio.gather(
            self.run_scan_loop(),
            self.run_telegram_polling(),
        )

    async def stop(self) -> None:
        """Stop the signal engine."""
        self._shutdown.set()
        try:
            await self.telegram.send_alert("Signal Engine Offline", "Stopped gracefully.")
        except Exception:
            pass
        log.info("signal_engine_stopped")


async def main():
    app = SignalEngineApp()
    try:
        await app.start()
    except KeyboardInterrupt:
        await app.stop()


if __name__ == "__main__":
    asyncio.run(main())
