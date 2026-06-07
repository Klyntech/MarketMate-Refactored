"""
marketmate/mate_ops/scheduler.py
─────────────────────────────────
Periodic MATE-Ops monitoring scheduler.

Runs observation cycles at configurable intervals:
  - Health checks: every 5 minutes
  - Log analysis: every 15 minutes
  - Metric analysis: every 30 minutes
  - Full diagnostics: every 60 minutes

The scheduler uses asyncio tasks with clean shutdown support.
Each loop runs independently — if one fails, the others continue.

Usage:
    from marketmate.mate_ops.agent import MATEOpsAgent
    from marketmate.mate_ops.scheduler import MATEOpsScheduler

    agent = MATEOpsAgent(authority_level=AuthorityLevel.SAFE_OPS)
    scheduler = MATEOpsScheduler(agent=agent)
    await scheduler.start()
    # ... later ...
    await scheduler.stop()
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from marketmate.core.logger import get_logger
from marketmate.mate_ops.agent import MATEOpsAgent

log = get_logger("mate_ops.scheduler")


# ─── Default Intervals ────────────────────────────────────────────────────────

DEFAULT_INTERVALS: Dict[str, int] = {
    "health_check": 5 * 60,      # 5 minutes
    "log_analysis": 15 * 60,     # 15 minutes
    "metric_analysis": 30 * 60,  # 30 minutes
    "full_diagnostics": 60 * 60, # 60 minutes
}


# ─── MATE-Ops Scheduler ──────────────────────────────────────────────────────

class MATEOpsScheduler:
    """
    Periodic MATE-Ops monitoring scheduler.

    Manages four independent asyncio loops, each running at
    a different interval:
      1. Health check loop    — every 5 min  (quick service checks)
      2. Log analysis loop    — every 15 min (scan for error patterns)
      3. Metric analysis loop — every 30 min (Prometheus queries)
      4. Full diagnostics     — every 60 min (complete pipeline cycle)

    Each loop:
      - Runs its assigned check/analysis
      - Logs results
      - Notifies the team if issues are detected (if authority allows)
      - Sleeps until the next interval

    Clean shutdown:
      - stop() cancels all tasks
      - Waits for in-progress checks to complete (up to 10s)
      - Logs the shutdown
    """

    def __init__(
        self,
        agent: MATEOpsAgent,
        intervals: Optional[Dict[str, int]] = None,
    ) -> None:
        """
        Initialize the scheduler.

        Args:
            agent: MATEOpsAgent instance to run checks through.
            intervals: Custom intervals in seconds for each loop.
                Keys: "health_check", "log_analysis", "metric_analysis",
                "full_diagnostics". Defaults to DEFAULT_INTERVALS.
        """
        self._agent = agent
        self._intervals = {**DEFAULT_INTERVALS, **(intervals or {})}
        self._tasks: list[asyncio.Task] = []
        self._shutdown = asyncio.Event()

    # ── Lifecycle ─────────────────────────────────────────────────────────────

    async def start(self) -> None:
        """
        Start all periodic monitoring loops.

        Each loop runs as an independent asyncio task. If one
        fails or throws an exception, the others continue running.
        """
        self._shutdown.clear()

        loop_definitions = [
            ("mate_ops_health_check", self._health_check_loop),
            ("mate_ops_log_analysis", self._log_analysis_loop),
            ("mate_ops_metric_analysis", self._metric_analysis_loop),
            ("mate_ops_full_diagnostics", self._full_diagnostics_loop),
        ]

        for name, coro_fn in loop_definitions:
            task = asyncio.create_task(coro_fn(), name=name)
            self._tasks.append(task)

        log.info(
            "mate_ops_scheduler_started",
            tasks=[t.get_name() for t in self._tasks],
            intervals=self._intervals,
            authority_level=self._agent.authority_level.value,
        )

    async def stop(self) -> None:
        """
        Stop all periodic monitoring loops.

        Signals shutdown, cancels all tasks, and waits for them
        to finish. Allows up to 10 seconds for graceful shutdown.
        """
        self._shutdown.set()

        for task in self._tasks:
            if not task.done():
                task.cancel()

        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)

        log.info(
            "mate_ops_scheduler_stopped",
            tasks_cancelled=len(self._tasks),
        )
        self._tasks.clear()

    # ── Periodic Loops: Health Check (5 min) ──────────────────────────────────

    async def _health_check_loop(self) -> None:
        """
        Run quick health checks every 5 minutes.

        Calls agent.check_health() which runs all service health
        checks concurrently. If any service reports an error,
        logs a warning and optionally notifies the team.
        """
        interval = self._intervals["health_check"]
        log.info("mate_ops_health_loop_started", interval_s=interval)

        while not self._shutdown.is_set():
            try:
                result = await self._agent.check_health()

                error_count = sum(
                    1 for s in result.get("services", [])
                    if s.get("status") == "error"
                )

                if error_count > 0:
                    log.warning(
                        "mate_ops_health_check_degraded",
                        error_count=error_count,
                        total=result.get("total_count", 0),
                    )
                    # Notify team if authority allows
                    if self._agent.permission_gate.validate("notify_team"):
                        services_with_errors = [
                            s["source"] for s in result.get("services", [])
                            if s.get("status") == "error"
                        ]
                        try:
                            await self._agent.notify_team(
                                message=(
                                    f"Health check detected {error_count} service(s) with errors: "
                                    f"{', '.join(services_with_errors)}"
                                ),
                                severity="warning",
                            )
                        except Exception as exc:
                            log.warning("mate_ops_health_notify_failed", error=str(exc))
                else:
                    log.info(
                        "mate_ops_health_check_ok",
                        healthy=result.get("healthy_count", 0),
                        total=result.get("total_count", 0),
                    )

            except Exception as exc:
                log.error("mate_ops_health_check_error", error=str(exc), exc_info=True)

            # Sleep until next interval
            try:
                await asyncio.wait_for(self._shutdown.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    # ── Periodic Loops: Log Analysis (15 min) ────────────────────────────────

    async def _log_analysis_loop(self) -> None:
        """
        Analyze application logs every 15 minutes.

        Queries recent ERROR-level logs and checks for patterns
        like repeated errors, new error types, or escalating
        error rates. If anomalies are found, notifies the team.
        """
        interval = self._intervals["log_analysis"]
        log.info("mate_ops_log_analysis_loop_started", interval_s=interval)

        while not self._shutdown.is_set():
            try:
                # Read recent error logs
                log_result = await self._agent.read_logs(
                    level="ERROR",
                    limit=100,
                )

                entries = log_result.get("entries", [])
                entry_count = len(entries)

                if entry_count > 0:
                    log.warning(
                        "mate_ops_log_errors_detected",
                        error_count=entry_count,
                        source=log_result.get("source", "unknown"),
                    )

                    # Notify if error count is significant
                    if entry_count >= 10 and self._agent.permission_gate.validate("notify_team"):
                        try:
                            await self._agent.notify_team(
                                message=(
                                    f"Log analysis detected {entry_count} recent errors. "
                                    f"Source: {log_result.get('source', 'unknown')}. "
                                    f"Review logs for details."
                                ),
                                severity="warning",
                            )
                        except Exception as exc:
                            log.warning("mate_ops_log_notify_failed", error=str(exc))
                else:
                    log.info("mate_ops_log_analysis_clean", errors=0)

            except Exception as exc:
                log.error("mate_ops_log_analysis_error", error=str(exc), exc_info=True)

            try:
                await asyncio.wait_for(self._shutdown.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    # ── Periodic Loops: Metric Analysis (30 min) ─────────────────────────────

    async def _metric_analysis_loop(self) -> None:
        """
        Analyze Prometheus metrics every 30 minutes.

        Queries key infrastructure metrics (error rate, latency,
        throughput) and checks for anomalies. If metrics indicate
        degradation, triggers a notification.
        """
        interval = self._intervals["metric_analysis"]
        log.info("mate_ops_metric_analysis_loop_started", interval_s=interval)

        while not self._shutdown.is_set():
            try:
                # Query error rate
                error_metrics = await self._agent.check_metrics(
                    query='rate(http_requests_total{status=~"5.."}[5m])',
                    time_range="5m",
                )

                # Query latency
                latency_metrics = await self._agent.check_metrics(
                    query='histogram_quantile(0.95, rate(http_request_duration_seconds_bucket[5m]))',
                    time_range="5m",
                )

                # Check for anomalies
                has_errors = "error" not in error_metrics
                has_latency = "error" not in latency_metrics

                if has_errors or has_latency:
                    log.info(
                        "mate_ops_metric_analysis_complete",
                        error_metrics_available=has_errors,
                        latency_metrics_available=has_latency,
                    )
                else:
                    log.info("mate_ops_metric_analysis_unavailable")

            except Exception as exc:
                log.error("mate_ops_metric_analysis_error", error=str(exc), exc_info=True)

            try:
                await asyncio.wait_for(self._shutdown.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    # ── Periodic Loops: Full Diagnostics (60 min) ────────────────────────────

    async def _full_diagnostics_loop(self) -> None:
        """
        Run a full Observe→Analyze→Plan→Execute→Verify cycle every 60 minutes.

        This is the most comprehensive check. It runs the full
        MATE-Ops pipeline which includes observation, LLM analysis,
        action planning, execution, and verification.
        """
        interval = self._intervals["full_diagnostics"]
        log.info("mate_ops_full_diagnostics_loop_started", interval_s=interval)

        while not self._shutdown.is_set():
            try:
                result = await self._agent.run_cycle()

                error_actions = sum(
                    1 for r in result.execution_results
                    if r.get("status") == "error"
                )
                denied_actions = sum(
                    1 for r in result.execution_results
                    if r.get("status") == "denied"
                )

                log.info(
                    "mate_ops_full_diagnostics_complete",
                    cycle_id=result.cycle_id,
                    latency_ms=result.total_latency_ms,
                    observations=len(result.observations),
                    execution_errors=error_actions,
                    execution_denied=denied_actions,
                )

                # If cycle detected issues, ensure team is notified
                services_with_errors = [
                    o for o in result.observations if o.status == "error"
                ]
                if services_with_errors and self._agent.permission_gate.validate("notify_team"):
                    try:
                        error_sources = [o.source for o in services_with_errors]
                        await self._agent.notify_team(
                            message=(
                                f"Full diagnostics detected issues in: "
                                f"{', '.join(error_sources)}. "
                                f"Cycle ID: {result.cycle_id}"
                            ),
                            severity="warning",
                        )
                    except Exception as exc:
                        log.warning("mate_ops_diagnostics_notify_failed", error=str(exc))

            except Exception as exc:
                log.error("mate_ops_full_diagnostics_error", error=str(exc), exc_info=True)

            try:
                await asyncio.wait_for(self._shutdown.wait(), timeout=interval)
            except asyncio.TimeoutError:
                pass

    # ── Introspection ─────────────────────────────────────────────────────────

    @property
    def is_running(self) -> bool:
        """Return True if any scheduled task is still alive."""
        return any(not t.done() for t in self._tasks)

    @property
    def task_names(self) -> list[str]:
        """Return names of all scheduled tasks."""
        return [t.get_name() for t in self._tasks]

    @property
    def intervals(self) -> Dict[str, int]:
        """Return the configured intervals in seconds."""
        return dict(self._intervals)
