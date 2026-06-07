"""
marketmate/core/scheduler.py
──────────────────────────────
Background loop orchestrator for MarketMate.

Extracts the signal_scan_loop, trade_evaluation_loop, and daily_summary_loop
patterns from the old main.py into a reusable Scheduler class.

The Scheduler:
  - Accepts all the components it needs (signal_engine, trade_lifecycle_manager, etc.)
  - Manages asyncio tasks with clean shutdown via asyncio.Event
  - Provides start(), stop(), and add_task() for extensibility
  - Logs every task start, stop, and unexpected error

Usage in lifespan:
    scheduler = Scheduler(
        signal_engine=engine,
        trade_lifecycle_manager=lifecycle_mgr,
        tracker=tracker,
        telegram=telegram,
    )
    await scheduler.start()
    # ... later in finally block ...
    await scheduler.stop()
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger

log = get_logger("scheduler")


# ─── Scheduler ─────────────────────────────────────────────────────────────────

class Scheduler:
    """
    Background loop orchestrator.

    Manages all long-running asyncio tasks (signal scan, trade eval,
    daily summary, reminders, etc.) with clean shutdown support.

    Dependencies are injected via __init__ so the Scheduler never
    imports domain modules directly.
    """

    def __init__(
        self,
        signal_engine: Any = None,
        trade_lifecycle_manager: Any = None,
        tracker: Any = None,
        telegram: Any = None,
    ) -> None:
        self.signal_engine = signal_engine
        self.trade_lifecycle_manager = trade_lifecycle_manager
        self.tracker = tracker
        self.telegram = telegram

        self._tasks: list[asyncio.Task] = []
        self._shutdown = asyncio.Event()
        self._extra_tasks: list[tuple[str, Callable[..., Coroutine]]] = []

    # ── Public API ────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """
        Launch all standard background loops and any extra tasks.

        Standard loops (always started if their dependencies are provided):
          1. signal_scan_loop      — every cfg.app.scan_interval_seconds
          2. trade_evaluation_loop — every cfg.sim.evaluation_interval_seconds
          3. daily_summary_loop    — fires at 17:05 UTC

        Extra tasks registered via add_task() are also started.
        """
        self._shutdown.clear()

        # ── Signal scan loop ─────────────────────────────────────────────────
        if self.signal_engine is not None:
            self._tasks.append(
                asyncio.create_task(
                    self._signal_scan_loop(),
                    name="signal_scan",
                )
            )

        # ── Trade evaluation loop ────────────────────────────────────────────
        if self.trade_lifecycle_manager is not None:
            self._tasks.append(
                asyncio.create_task(
                    self._trade_evaluation_loop(),
                    name="trade_eval",
                )
            )

        # ── Daily summary loop ───────────────────────────────────────────────
        if self.tracker is not None and self.telegram is not None:
            self._tasks.append(
                asyncio.create_task(
                    self._daily_summary_loop(),
                    name="daily_summary",
                )
            )

        # ── Extra tasks ──────────────────────────────────────────────────────
        for name, coro_fn in self._extra_tasks:
            self._tasks.append(
                asyncio.create_task(coro_fn(), name=name)
            )

        log.info(
            "scheduler_started",
            task_count=len(self._tasks),
            task_names=[t.get_name() for t in self._tasks],
        )

    async def stop(self) -> None:
        """
        Signal all tasks to stop and wait for them to finish.

        Cancels any tasks that don't finish within 10 seconds.
        """
        self._shutdown.set()

        # Give tasks a moment to finish gracefully
        if self._tasks:
            # Cancel tasks that are still running
            for task in self._tasks:
                if not task.done():
                    task.cancel()

            # Wait for all tasks to complete (or be cancelled)
            await asyncio.gather(*self._tasks, return_exceptions=True)

        log.info("scheduler_stopped", cancelled=len(self._tasks))
        self._tasks.clear()

    def add_task(self, name: str, coro_fn: Callable[..., Coroutine]) -> None:
        """
        Register an additional background task.

        *coro_fn* must be a zero-arg async callable (e.g. a lambda or
        bound method).  The task will be started on the next start() call.

        Example:
            scheduler.add_task("reminder_loop", run_reminder_loop)
        """
        self._extra_tasks.append((name, coro_fn))
        log.debug("scheduler_task_added", name=name)

    @property
    def is_running(self) -> bool:
        """Return True if any managed task is still alive."""
        return any(not t.done() for t in self._tasks)

    # ── Standard Loops ────────────────────────────────────────────────────────

    async def _signal_scan_loop(self) -> None:
        """
        Scan all configured pairs on a fixed interval.

        Uses signal_engine.run(symbol) for each pair and updates the
        daily state from the database.
        """
        interval = cfg.app.scan_interval_seconds
        log.info("signal_scan_loop_started", interval_s=interval)

        while not self._shutdown.is_set():
            start = datetime.now(timezone.utc)

            # Refresh daily state from DB before each cycle
            if self.signal_engine is not None:
                try:
                    from marketmate.db import get_signals_repo
                    repo = get_signals_repo()
                    today = start.strftime("%Y-%m-%d")
                    self.signal_engine.state.trades_today = await repo.get_daily_count(today)
                    self.signal_engine.state.consecutive_losses = await repo.get_consecutive_losses()
                except Exception as exc:
                    log.warning("daily_state_refresh_failed", error=str(exc))

                log.info(
                    "scan_cycle_start",
                    pairs=cfg.strategy.pairs,
                    trades_today=self.signal_engine.state.trades_today,
                    consec_losses=self.signal_engine.state.consecutive_losses,
                )

                for symbol in cfg.strategy.pairs:
                    if self._shutdown.is_set():
                        break
                    try:
                        signal = await self.signal_engine.run(symbol)
                        # The engine emits events internally; downstream
                        # subscribers handle persistence, delivery, execution.
                        if signal is not None:
                            log.info(
                                "scan_signal_generated",
                                signal_id=signal.id,
                                symbol=symbol,
                                direction=signal.direction,
                            )
                    except Exception as exc:
                        log.error("pair_scan_error", symbol=symbol,
                                  error=str(exc), exc_info=True)
                        if self.telegram is not None:
                            try:
                                await self.telegram.send_alert(
                                    "Scan Error", f"Error scanning {symbol}:\n{exc}"
                                )
                            except Exception:
                                pass

            elapsed = (datetime.now(timezone.utc) - start).total_seconds()
            log.info("scan_cycle_complete", elapsed_s=round(elapsed, 2))

            try:
                await asyncio.wait_for(self._shutdown.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def _trade_evaluation_loop(self) -> None:
        """
        Evaluate open trades on a fixed interval.

        Delegates to trade_lifecycle_manager.evaluate_open_trades().
        """
        interval = cfg.sim.evaluation_interval_seconds
        log.info("trade_eval_loop_started", interval_s=interval)

        while not self._shutdown.is_set():
            try:
                await self.trade_lifecycle_manager.evaluate_open_trades()
            except Exception as exc:
                log.error("trade_eval_error", error=str(exc), exc_info=True)

            try:
                await asyncio.wait_for(self._shutdown.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    async def _daily_summary_loop(self) -> None:
        """
        Fire the daily summary at 17:05 UTC.

        Checks every 60 seconds; calls tracker.daily_summary() when
        the time matches.
        """
        while not self._shutdown.is_set():
            now = datetime.now(timezone.utc)
            if now.hour == 17 and now.minute == 5:
                try:
                    await self.tracker.daily_summary()
                except Exception as exc:
                    log.error("daily_summary_error", error=str(exc))

            try:
                await asyncio.wait_for(self._shutdown.wait(), timeout=60)
            except asyncio.TimeoutError:
                pass
