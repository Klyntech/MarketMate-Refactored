"""
marketmate/mate_ops/phase1_runner.py
─────────────────────────────────────
Phase 1 orchestrator for MATE-Ops.

Runs simulation, penetration tests, and Max/Mini analysis
concurrently where possible, collects all results into a
comprehensive Phase1Report, writes JSON output, and prints
a formatted summary to console.

Usage:
    python -m marketmate.mate_ops.phase1_runner
"""

from __future__ import annotations

import asyncio
import json
import os
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

from marketmate.core.logger import get_logger
from marketmate.mate_ops.max_mini import MaxMiniAnalysis, MaxMiniReport
from marketmate.mate_ops.pentest import MateOpsPenTest, PentestSummary
from marketmate.mate_ops.simulation import Phase1Simulation, SimulationReport

log = get_logger("mate_ops.phase1_runner")


# ─── Output Path ───────────────────────────────────────────────────────────────

RESULTS_DIR = Path("/home/z/my-project/download")
RESULTS_FILE = RESULTS_DIR / "mate_ops_phase1_results.json"


# ─── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class Phase1Report:
    """Comprehensive report from the full Phase 1 suite."""

    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    phase: str = "1"
    module: str = "mate_ops"
    simulation_report: Dict[str, Any] = field(default_factory=dict)
    pentest_summary: Dict[str, Any] = field(default_factory=dict)
    max_mini_report: Dict[str, Any] = field(default_factory=dict)
    overall_status: str = "pending"
    total_duration_ms: float = 0.0
    errors: List[str] = field(default_factory=list)


# ─── Phase 1 Runner ────────────────────────────────────────────────────────────

class Phase1Runner:
    """
    Phase 1 orchestrator that runs the full MATE-Ops evaluation suite.

    Executes three components:
      1. Simulation — runs 6 scenarios against mocked services
      2. Penetration tests — runs 33 security tests
      3. Max/Mini analysis — documents optimization targets

    Simulation and pentest run concurrently via asyncio.
    Max/Mini analysis runs after both complete (it's synchronous).

    Results are written to JSON and printed to console.
    """

    def __init__(self) -> None:
        """Initialize the Phase 1 runner."""
        self._report = Phase1Report()
        self._simulation: Phase1Simulation = Phase1Simulation()
        self._pentest: MateOpsPenTest = MateOpsPenTest()
        self._max_mini: MaxMiniAnalysis = MaxMiniAnalysis()

    # ── Main Runner ──────────────────────────────────────────────────────────

    async def run(self) -> Phase1Report:
        """
        Run the full Phase 1 suite.

        Simulation and pentest run concurrently.  Max/Mini analysis
        runs synchronously after both complete.  Results are written
        to JSON and printed to console.
        """
        import time as _time

        overall_start = _time.monotonic()

        log.info("mate_ops_phase1_runner_start")
        self._print_banner()

        # ── Run simulation and pentest concurrently ────────────────────────
        try:
            simulation_result, pentest_result = await asyncio.gather(
                self._run_simulation(),
                self._run_pentest(),
                return_exceptions=True,
            )

            if isinstance(simulation_result, Exception):
                self._report.errors.append(f"Simulation failed: {simulation_result}")
                simulation_result = SimulationReport()

            if isinstance(pentest_result, Exception):
                self._report.errors.append(f"Pentest failed: {pentest_result}")
                pentest_result = PentestSummary()

            self._report.simulation_report = self._serialize_simulation(simulation_result)
            self._report.pentest_summary = self._serialize_pentest(pentest_result)

        except Exception as exc:
            self._report.errors.append(f"Concurrent execution failed: {exc}")
            log.error("mate_ops_phase1_concurrent_error", error=str(exc))

        # ── Run Max/Mini analysis (synchronous) ───────────────────────────
        try:
            max_mini_result = self._max_mini.analyze()
            self._report.max_mini_report = self._serialize_max_mini(max_mini_result)
        except Exception as exc:
            self._report.errors.append(f"Max/Mini analysis failed: {exc}")
            log.error("mate_ops_phase1_max_mini_error", error=str(exc))

        # ── Compute overall status ─────────────────────────────────────────
        self._report.total_duration_ms = round(
            (_time.monotonic() - overall_start) * 1000, 1
        )
        self._report.overall_status = self._compute_status()

        # ── Write results ──────────────────────────────────────────────────
        self._write_results()
        self._print_summary()

        log.info(
            "mate_ops_phase1_runner_complete",
            status=self._report.overall_status,
            duration_ms=self._report.total_duration_ms,
            errors=len(self._report.errors),
        )

        return self._report

    # ── Component Runners ────────────────────────────────────────────────────

    async def _run_simulation(self) -> SimulationReport:
        """Run the simulation suite."""
        log.info("mate_ops_phase1_simulation_start")
        print("  ▶ Running simulation scenarios...")
        result = await self._simulation.run_all()
        print(f"  ✓ Simulation complete: {result.scenarios_passed}/{result.scenarios_run} passed\n")
        return result

    async def _run_pentest(self) -> PentestSummary:
        """Run the penetration test suite."""
        log.info("mate_ops_phase1_pentest_start")
        print("  ▶ Running penetration tests...\n")
        result = await self._pentest.run_all()
        MateOpsPenTest.print_summary(result)
        return result

    # ── Serialization ────────────────────────────────────────────────────────

    @staticmethod
    def _serialize_simulation(report: SimulationReport) -> Dict[str, Any]:
        """Serialize SimulationReport to a JSON-safe dict."""
        return {
            "timestamp": report.timestamp,
            "scenarios_run": report.scenarios_run,
            "scenarios_passed": report.scenarios_passed,
            "scenarios_failed": report.scenarios_failed,
            "total_latency_ms": report.total_latency_ms,
            "authority_level": report.authority_level,
            "scenarios": [
                {
                    "name": sr.scenario_name,
                    "passed": sr.passed,
                    "total_latency_ms": sr.total_latency_ms,
                    "error": sr.error,
                    "stage_latencies": [
                        {"stage": sl.stage, "latency_ms": sl.latency_ms}
                        for sl in sr.stage_latencies
                    ],
                    "observations": sr.observations,
                    "execution_results": sr.execution_results,
                }
                for sr in report.scenario_results
            ],
        }

    @staticmethod
    def _serialize_pentest(summary: PentestSummary) -> Dict[str, Any]:
        """Serialize PentestSummary to a JSON-safe dict."""
        return {
            "timestamp": summary.timestamp,
            "total_tests": summary.total_tests,
            "passed": summary.passed,
            "failed": summary.failed,
            "warnings": summary.warnings,
            "critical_failures": summary.critical_failures,
            "high_failures": summary.high_failures,
            "categories": summary.categories,
            "results": [
                {
                    "test_name": r.test_name,
                    "category": r.category,
                    "status": r.status,
                    "details": r.details,
                    "severity": r.severity,
                    "timestamp": r.timestamp,
                }
                for r in summary.results
            ],
        }

    @staticmethod
    def _serialize_max_mini(report: MaxMiniReport) -> Dict[str, Any]:
        """Serialize MaxMiniReport to a JSON-safe dict."""
        return {
            "timestamp": report.timestamp,
            "overall_health_score": report.overall_health_score,
            "critical_gaps": report.critical_gaps,
            "maximize": [
                {
                    "name": item.name,
                    "description": item.description,
                    "current_score": item.current_score,
                    "target_score": item.target_score,
                    "strategy": item.strategy,
                    "priority": item.priority,
                }
                for item in report.maximize_section.items
            ],
            "minimize": [
                {
                    "name": item.name,
                    "description": item.description,
                    "current_score": item.current_score,
                    "target_score": item.target_score,
                    "strategy": item.strategy,
                    "priority": item.priority,
                }
                for item in report.minimize_section.items
            ],
            "recommendations": report.recommendations,
        }

    # ── Status Computation ───────────────────────────────────────────────────

    def _compute_status(self) -> str:
        """
        Compute overall Phase 1 status from all results.

        Returns one of:
          - "PASS" — all tests pass, simulation clean
          - "PASS_WITH_WARNINGS" — no failures but warnings exist
          - "FAIL" — critical failures detected
        """
        has_errors = len(self._report.errors) > 0
        pentest = self._report.pentest_summary
        simulation = self._report.simulation_report

        # Check for critical pentest failures
        critical_failures = pentest.get("critical_failures", 0)
        high_failures = pentest.get("high_failures", 0)
        pentest_failed = pentest.get("failed", 0)

        # Check simulation failures
        sim_failed = simulation.get("scenarios_failed", 0)

        if has_errors or critical_failures > 0:
            return "FAIL"
        elif pentest_failed > 0 or sim_failed > 0:
            return "FAIL"
        elif pentest.get("warnings", 0) > 0:
            return "PASS_WITH_WARNINGS"
        else:
            return "PASS"

    # ── File Output ──────────────────────────────────────────────────────────

    def _write_results(self) -> None:
        """Write the Phase1Report to a JSON file."""
        try:
            RESULTS_DIR.mkdir(parents=True, exist_ok=True)

            report_dict = asdict(self._report)
            with open(RESULTS_FILE, "w", encoding="utf-8") as f:
                json.dump(report_dict, f, indent=2, default=str)

            log.info("mate_ops_phase1_results_written", path=str(RESULTS_FILE))
        except Exception as exc:
            log.error("mate_ops_phase1_results_write_failed", error=str(exc))
            self._report.errors.append(f"Failed to write results: {exc}")

    # ── Console Output ───────────────────────────────────────────────────────

    @staticmethod
    def _print_banner() -> None:
        """Print the Phase 1 banner."""
        divider = "═" * 70
        print(f"\n{divider}")
        print("  MATE-Ops Phase 1 — Simulation + Pentest Suite")
        print(f"  {datetime.now(timezone.utc).isoformat()}")
        print(f"{divider}\n")

    def _print_summary(self) -> None:
        """Print the final Phase 1 summary."""
        report = self._report
        divider = "═" * 70

        status_icon = {
            "PASS": "✅",
            "PASS_WITH_WARNINGS": "⚠️",
            "FAIL": "❌",
        }.get(report.overall_status, "❓")

        print(f"\n{divider}")
        print(f"  MATE-Ops Phase 1 — Final Summary")
        print(f"{divider}")
        print(f"  Status         : {status_icon} {report.overall_status}")
        print(f"  Duration       : {round(report.total_duration_ms / 1000, 1)}s")

        # Simulation summary
        sim = report.simulation_report
        if sim:
            print(f"  Simulation     : {sim.get('scenarios_passed', '?')}/{sim.get('scenarios_run', '?')} scenarios passed")

        # Pentest summary
        pen = report.pentest_summary
        if pen:
            print(f"  Pentest        : {pen.get('passed', '?')}/{pen.get('total_tests', '?')} tests passed, "
                  f"{pen.get('failed', 0)} failed, {pen.get('warnings', 0)} warnings")

        # Max/Mini summary
        mm = report.max_mini_report
        if mm:
            print(f"  Max/Mini       : Health score {mm.get('overall_health_score', '?')}/100, "
                  f"{mm.get('critical_gaps', '?')} critical gaps")

        # Errors
        if report.errors:
            print(f"\n  Errors:")
            for err in report.errors:
                print(f"    └─ {err}")

        # Output file
        print(f"\n  Results file   : {RESULTS_FILE}")
        print(f"{divider}\n")


# ─── Main Entry Point ─────────────────────────────────────────────────────────

async def _main() -> None:
    """Run the full Phase 1 suite."""
    runner = Phase1Runner()
    report = await runner.run()

    # Exit with non-zero code on failure
    if report.overall_status == "FAIL":
        raise SystemExit(1)


if __name__ == "__main__":
    asyncio.run(_main())
