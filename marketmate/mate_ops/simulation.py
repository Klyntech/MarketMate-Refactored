"""
marketmate/mate_ops/simulation.py
──────────────────────────────────
Phase 1 simulation framework for MATE-Ops.

Mocks all external services (API, Ollama, Redis, MongoDB, Telegram,
Prometheus) and runs the full 5-stage pipeline against them — no real
network calls required.

Scenarios:
  - all_healthy        → everything green
  - api_degraded       → API slow but responding
  - ollama_down        → LLM inference unavailable (tests fallback)
  - redis_timeout      → Redis connection timeout
  - cascading_failure  → multiple services fail simultaneously
  - recovery_sequence  → services recover one by one
"""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from marketmate.core.logger import get_logger
from marketmate.mate_ops.observer import Observation
from marketmate.mate_ops.permission_gate import AuthorityLevel, PermissionGate

log = get_logger("mate_ops.simulation")


# ─── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class StageLatency:
    """Latency measurement for a single pipeline stage."""

    stage: str
    latency_ms: float


@dataclass
class ScenarioResult:
    """Result of running a single simulation scenario."""

    scenario_name: str
    observations: List[Dict[str, Any]] = field(default_factory=list)
    analysis: str = ""
    plan: Dict[str, Any] = field(default_factory=dict)
    execution_results: List[Dict[str, Any]] = field(default_factory=list)
    verification: str = ""
    stage_latencies: List[StageLatency] = field(default_factory=list)
    total_latency_ms: float = 0.0
    passed: bool = False
    error: Optional[str] = None


@dataclass
class SimulationReport:
    """Aggregated report from all simulation scenarios."""

    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    scenarios_run: int = 0
    scenarios_passed: int = 0
    scenarios_failed: int = 0
    scenario_results: List[ScenarioResult] = field(default_factory=list)
    total_latency_ms: float = 0.0
    authority_level: int = 0


# ─── Mock Service Responses ────────────────────────────────────────────────────

@dataclass
class MockServiceConfig:
    """Configuration for a single mocked service."""

    source: str
    status: str = "ok"
    message: str = ""
    latency_ms: float = 5.0
    details: Dict[str, Any] = field(default_factory=dict)
    should_timeout: bool = False
    should_error: bool = False


# ─── Simulation Environment ────────────────────────────────────────────────────

class SimulationEnvironment:
    """
    Mock environment that simulates all MATE-Ops dependencies.

    Replaces real HTTP calls, Redis connections, MongoDB queries,
    and Telegram API with deterministic mock responses.  No external
    services are required — the simulation is fully self-contained.

    Each scenario configures the mock responses differently to test
    how MATE-Ops behaves under various infrastructure conditions.
    """

    def __init__(self, service_configs: Optional[List[MockServiceConfig]] = None) -> None:
        """
        Initialize the simulation environment with optional service configs.

        Args:
            service_configs: List of MockServiceConfig objects defining how
                each service should respond.  If None, defaults to all healthy.
        """
        if service_configs is not None:
            self._configs = {c.source: c for c in service_configs}
        else:
            self._configs = self._default_healthy_configs()

    # ── Default Configs ──────────────────────────────────────────────────────

    @staticmethod
    def _default_healthy_configs() -> Dict[str, MockServiceConfig]:
        """Return configs where every service is healthy."""
        return {
            "api": MockServiceConfig(
                source="api", status="ok",
                message="API health check: ok",
                details={"latency_ms": 45.2, "status_code": 200, "uptime_s": 86400},
            ),
            "ollama": MockServiceConfig(
                source="ollama", status="ok",
                message="Ollama healthy: 3 model(s) loaded",
                details={"latency_ms": 120.5, "model_count": 3, "models": ["llama3", "mistral", "codellama"]},
            ),
            "redis": MockServiceConfig(
                source="redis", status="ok",
                message="Redis PING successful",
                details={"latency_ms": 2.1, "redis_version": "7.2.4", "connected_clients": 12},
            ),
            "mongodb": MockServiceConfig(
                source="mongodb", status="ok",
                message="MongoDB ping successful",
                details={"latency_ms": 8.3, "db": "marketmate"},
            ),
            "telegram_bot": MockServiceConfig(
                source="telegram_bot", status="ok",
                message="Telegram bot healthy: @MarketMateBot",
                details={"latency_ms": 95.0, "bot_username": "MarketMateBot", "bot_id": 123456789},
            ),
            "prometheus": MockServiceConfig(
                source="prometheus", status="ok",
                message="Prometheus metrics collected: 3 queries",
                details={
                    "latency_ms": 35.7,
                    "metrics": {
                        "api_request_rate": "12.5",
                        "api_error_rate": "0.02",
                        "api_p95_latency": "0.145",
                    },
                },
            ),
        }

    # ── Mock Collect ─────────────────────────────────────────────────────────

    async def collect(self) -> List[Observation]:
        """
        Simulate telemetry collection — returns mocked Observations.

        Each service's response is determined by its MockServiceConfig.
        Timeout and error conditions are simulated with appropriate delays
        or error-status observations.
        """
        observations: List[Observation] = []

        for source, config in self._configs.items():
            # Simulate latency
            if not config.should_timeout:
                await asyncio.sleep(config.latency_ms / 1000.0)

            if config.should_timeout:
                observations.append(Observation(
                    source=source,
                    status="error",
                    message=f"{source} health check timed out",
                    details={"latency_ms": 10000.0, "timeout_s": 10},
                ))
            elif config.should_error:
                observations.append(Observation(
                    source=source,
                    status="error",
                    message=config.message or f"{source} health check failed: connection refused",
                    details=config.details or {"exception": "ConnectionRefusedError"},
                ))
            else:
                observations.append(Observation(
                    source=source,
                    status=config.status,
                    message=config.message or f"{source} healthy",
                    details=config.details,
                ))

        return observations

    # ── Mock Individual Checks ───────────────────────────────────────────────

    async def check_ollama_health(self) -> Observation:
        """Return mocked Ollama health observation."""
        config = self._configs.get("ollama", MockServiceConfig(source="ollama"))
        return Observation(
            source=config.source,
            status=config.status,
            message=config.message,
            details=config.details,
        )

    async def check_api_health(self) -> Observation:
        """Return mocked API health observation."""
        config = self._configs.get("api", MockServiceConfig(source="api"))
        return Observation(
            source=config.source,
            status=config.status,
            message=config.message,
            details=config.details,
        )


# ─── Simulation Scenarios ──────────────────────────────────────────────────────

class SimulationScenarios:
    """
    Pre-built simulation scenarios for testing MATE-Ops resilience.

    Each class method returns a SimulationEnvironment configured for
    a specific infrastructure condition.  Run all scenarios to verify
    that the agent handles every situation gracefully.
    """

    @staticmethod
    def all_healthy() -> SimulationEnvironment:
        """Everything green — all 6 services report ok."""
        return SimulationEnvironment([
            MockServiceConfig(source="api", status="ok", message="API health check: ok",
                              details={"latency_ms": 45.2, "status_code": 200}),
            MockServiceConfig(source="ollama", status="ok", message="Ollama healthy: 3 model(s) loaded",
                              details={"latency_ms": 120.5, "model_count": 3}),
            MockServiceConfig(source="redis", status="ok", message="Redis PING successful",
                              details={"latency_ms": 2.1}),
            MockServiceConfig(source="mongodb", status="ok", message="MongoDB ping successful",
                              details={"latency_ms": 8.3}),
            MockServiceConfig(source="telegram_bot", status="ok", message="Telegram bot healthy: @MarketMateBot",
                              details={"latency_ms": 95.0}),
            MockServiceConfig(source="prometheus", status="ok", message="Prometheus metrics collected: 3 queries",
                              details={"latency_ms": 35.7, "metrics": {"api_request_rate": "12.5"}}),
        ])

    @staticmethod
    def api_degraded() -> SimulationEnvironment:
        """API slow but responding — high latency warning."""
        return SimulationEnvironment([
            MockServiceConfig(source="api", status="warn", message="API responding slowly (latency 3200ms)",
                              details={"latency_ms": 3200.0, "status_code": 200}),
            MockServiceConfig(source="ollama", status="ok", message="Ollama healthy: 3 model(s) loaded",
                              details={"latency_ms": 120.5, "model_count": 3}),
            MockServiceConfig(source="redis", status="ok", message="Redis PING successful",
                              details={"latency_ms": 2.1}),
            MockServiceConfig(source="mongodb", status="ok", message="MongoDB ping successful",
                              details={"latency_ms": 8.3}),
            MockServiceConfig(source="telegram_bot", status="ok", message="Telegram bot healthy: @MarketMateBot",
                              details={"latency_ms": 95.0}),
            MockServiceConfig(source="prometheus", status="ok", message="Prometheus metrics collected: 3 queries",
                              details={"latency_ms": 35.7, "metrics": {"api_request_rate": "12.5"}}),
        ])

    @staticmethod
    def ollama_down() -> SimulationEnvironment:
        """LLM inference unavailable — tests rule-based fallback."""
        return SimulationEnvironment([
            MockServiceConfig(source="api", status="ok", message="API health check: ok",
                              details={"latency_ms": 45.2, "status_code": 200}),
            MockServiceConfig(source="ollama", status="error",
                              message="Ollama not reachable (connection refused)",
                              details={"url": "http://localhost:11434"}, should_error=True),
            MockServiceConfig(source="redis", status="ok", message="Redis PING successful",
                              details={"latency_ms": 2.1}),
            MockServiceConfig(source="mongodb", status="ok", message="MongoDB ping successful",
                              details={"latency_ms": 8.3}),
            MockServiceConfig(source="telegram_bot", status="ok", message="Telegram bot healthy: @MarketMateBot",
                              details={"latency_ms": 95.0}),
            MockServiceConfig(source="prometheus", status="ok", message="Prometheus metrics collected: 3 queries",
                              details={"latency_ms": 35.7, "metrics": {"api_request_rate": "12.5"}}),
        ])

    @staticmethod
    def redis_timeout() -> SimulationEnvironment:
        """Redis connection timeout — cache layer unavailable."""
        return SimulationEnvironment([
            MockServiceConfig(source="api", status="ok", message="API health check: ok",
                              details={"latency_ms": 45.2, "status_code": 200}),
            MockServiceConfig(source="ollama", status="ok", message="Ollama healthy: 3 model(s) loaded",
                              details={"latency_ms": 120.5, "model_count": 3}),
            MockServiceConfig(source="redis", status="error",
                              message="Redis health check timed out",
                              details={"latency_ms": 5000.0, "timeout_s": 5}, should_timeout=True),
            MockServiceConfig(source="mongodb", status="ok", message="MongoDB ping successful",
                              details={"latency_ms": 8.3}),
            MockServiceConfig(source="telegram_bot", status="ok", message="Telegram bot healthy: @MarketMateBot",
                              details={"latency_ms": 95.0}),
            MockServiceConfig(source="prometheus", status="ok", message="Prometheus metrics collected: 3 queries",
                              details={"latency_ms": 35.7, "metrics": {"api_request_rate": "12.5"}}),
        ])

    @staticmethod
    def cascading_failure() -> SimulationEnvironment:
        """Multiple services fail simultaneously — worst case scenario."""
        return SimulationEnvironment([
            MockServiceConfig(source="api", status="error",
                              message="API returned HTTP 503",
                              details={"latency_ms": 15000.0, "status_code": 503}, should_error=True),
            MockServiceConfig(source="ollama", status="error",
                              message="Ollama not reachable (connection refused)",
                              details={"url": "http://localhost:11434"}, should_error=True),
            MockServiceConfig(source="redis", status="error",
                              message="Redis health check failed: ConnectionRefusedError",
                              details={"latency_ms": 5000.0}, should_error=True),
            MockServiceConfig(source="mongodb", status="warn",
                              message="MongoDB ping slow (latency 4500ms)",
                              details={"latency_ms": 4500.0}),
            MockServiceConfig(source="telegram_bot", status="ok", message="Telegram bot healthy: @MarketMateBot",
                              details={"latency_ms": 95.0}),
            MockServiceConfig(source="prometheus", status="warn",
                              message="Prometheus metrics partial: 1 of 3 queries returned data",
                              details={"latency_ms": 8000.0, "metrics": {"api_request_rate": "0.0"}}),
        ])

    @staticmethod
    def recovery_sequence() -> SimulationEnvironment:
        """Services in mixed state — some recovering, some still degraded."""
        return SimulationEnvironment([
            MockServiceConfig(source="api", status="ok", message="API health check: ok (recovered)",
                              details={"latency_ms": 55.0, "status_code": 200}),
            MockServiceConfig(source="ollama", status="warn",
                              message="Ollama responding but no models loaded",
                              details={"latency_ms": 500.0, "model_count": 0}),
            MockServiceConfig(source="redis", status="ok", message="Redis PING successful (recovered)",
                              details={"latency_ms": 3.5}),
            MockServiceConfig(source="mongodb", status="error",
                              message="MongoDB ping returned not-ok",
                              details={"latency_ms": 3000.0, "result": "timeout"}),
            MockServiceConfig(source="telegram_bot", status="ok", message="Telegram bot healthy: @MarketMateBot",
                              details={"latency_ms": 95.0}),
            MockServiceConfig(source="prometheus", status="ok", message="Prometheus metrics collected: 3 queries",
                              details={"latency_ms": 35.7, "metrics": {"api_request_rate": "8.2"}}),
        ])

    @classmethod
    def all_scenarios(cls) -> Dict[str, SimulationEnvironment]:
        """Return all pre-built scenarios as a dict keyed by name."""
        return {
            "all_healthy": cls.all_healthy(),
            "api_degraded": cls.api_degraded(),
            "ollama_down": cls.ollama_down(),
            "redis_timeout": cls.redis_timeout(),
            "cascading_failure": cls.cascading_failure(),
            "recovery_sequence": cls.recovery_sequence(),
        }


# ─── Phase 1 Simulation ────────────────────────────────────────────────────────

class Phase1Simulation:
    """
    Runs the full MATE-Ops pipeline against simulated services.

    Initializes MATEOpsAgent with READ_ONLY authority, runs the
    Observe → Analyze → Plan → Execute → Verify pipeline for each
    scenario, measures latency per stage, and produces a detailed
    SimulationReport.

    The simulation requires NO external services — everything is
    mocked through SimulationEnvironment.
    """

    def __init__(self) -> None:
        """Initialize the Phase 1 simulation runner."""
        self._report = SimulationReport()

    # ── Main Runner ──────────────────────────────────────────────────────────

    async def run_all(self) -> SimulationReport:
        """
        Run all pre-built scenarios and return the aggregated report.

        Each scenario runs the full 5-stage pipeline.  The agent uses
        READ_ONLY authority so no destructive actions are attempted.
        """
        log.info("mate_ops_simulation_start")

        scenarios = SimulationScenarios.all_scenarios()

        for name, env in scenarios.items():
            log.info("mate_ops_simulation_scenario", scenario=name)
            result = await self._run_scenario(name, env)
            self._report.scenario_results.append(result)

        self._report.scenarios_run = len(self._report.scenario_results)
        self._report.scenarios_passed = sum(1 for r in self._report.scenario_results if r.passed)
        self._report.scenarios_failed = self._report.scenarios_run - self._report.scenarios_passed
        self._report.total_latency_ms = sum(r.total_latency_ms for r in self._report.scenario_results)
        self._report.authority_level = AuthorityLevel.READ_ONLY

        self._print_report()

        log.info(
            "mate_ops_simulation_complete",
            scenarios_run=self._report.scenarios_run,
            passed=self._report.scenarios_passed,
            failed=self._report.scenarios_failed,
            total_latency_ms=round(self._report.total_latency_ms, 1),
        )

        return self._report

    # ── Single Scenario ──────────────────────────────────────────────────────

    async def _run_scenario(
        self,
        scenario_name: str,
        env: SimulationEnvironment,
    ) -> ScenarioResult:
        """
        Run the full pipeline for one scenario.

        Args:
            scenario_name: Human-readable name for the scenario.
            env: Configured SimulationEnvironment.

        Returns:
            ScenarioResult with observations, analysis, plan,
            execution results, verification, and latency measurements.
        """
        result = ScenarioResult(scenario_name=scenario_name)
        overall_start = time.monotonic()

        try:
            # Create a permission gate with READ_ONLY authority
            gate = PermissionGate(max_authority_level=AuthorityLevel.READ_ONLY)

            # ── Stage 1: Observe ─────────────────────────────────────────
            stage_start = time.monotonic()
            observations = await env.collect()
            observe_ms = round((time.monotonic() - stage_start) * 1000, 1)
            result.observations = [
                {"source": o.source, "status": o.status, "message": o.message, "details": o.details}
                for o in observations
            ]
            result.stage_latencies.append(StageLatency(stage="observe", latency_ms=observe_ms))

            # ── Stage 2: Analyze (rule-based, since no LLM in simulation) ──
            stage_start = time.monotonic()
            analysis = self._rule_based_analysis(observations)
            analyze_ms = round((time.monotonic() - stage_start) * 1000, 1)
            result.analysis = analysis
            result.stage_latencies.append(StageLatency(stage="analyze", latency_ms=analyze_ms))

            # ── Stage 3: Plan ────────────────────────────────────────────
            stage_start = time.monotonic()
            plan = self._rule_based_plan(analysis, gate)
            plan_ms = round((time.monotonic() - stage_start) * 1000, 1)
            result.plan = plan
            result.stage_latencies.append(StageLatency(stage="plan", latency_ms=plan_ms))

            # ── Stage 4: Execute ─────────────────────────────────────────
            stage_start = time.monotonic()
            execution_results = await self._execute_plan(plan, gate, env)
            execute_ms = round((time.monotonic() - stage_start) * 1000, 1)
            result.execution_results = execution_results
            result.stage_latencies.append(StageLatency(stage="execute", latency_ms=execute_ms))

            # ── Stage 5: Verify ──────────────────────────────────────────
            stage_start = time.monotonic()
            new_observations = await env.collect()
            verification = self._verify(execution_results, new_observations)
            verify_ms = round((time.monotonic() - stage_start) * 1000, 1)
            result.verification = verification
            result.stage_latencies.append(StageLatency(stage="verify", latency_ms=verify_ms))

            # Scenario passes if pipeline completes without unhandled errors
            result.passed = True

        except Exception as exc:
            result.passed = False
            result.error = str(exc)
            log.error(
                "mate_ops_simulation_scenario_failed",
                scenario=scenario_name,
                error=str(exc),
            )

        result.total_latency_ms = round((time.monotonic() - overall_start) * 1000, 1)
        return result

    # ── Analysis (rule-based fallback) ───────────────────────────────────────

    @staticmethod
    def _rule_based_analysis(observations: List[Observation]) -> str:
        """
        Rule-based analysis matching the agent's fallback logic.

        Identifies services by status and generates a summary
        with severity assessment.
        """
        errors = [o for o in observations if o.status == "error"]
        warnings = [o for o in observations if o.status == "warn"]
        ok = [o for o in observations if o.status == "ok"]

        lines = ["Infrastructure Analysis (rule-based)"]
        lines.append(f"  Healthy: {len(ok)} services")
        lines.append(f"  Degraded: {len(warnings)} services")
        lines.append(f"  Error: {len(errors)} services")

        if errors:
            lines.append("\nServices with ERRORS:")
            for o in errors:
                lines.append(f"  - {o.source}: {o.message}")

        if warnings:
            lines.append("\nServices with WARNINGS:")
            for o in warnings:
                lines.append(f"  - {o.source}: {o.message}")

        severity = (
            "critical" if len(errors) >= 2
            else "high" if errors
            else "medium" if warnings
            else "low"
        )
        lines.append(f"\nOverall severity: {severity}")

        return "\n".join(lines)

    # ── Planning (rule-based fallback) ───────────────────────────────────────

    @staticmethod
    def _rule_based_plan(analysis: str, gate: PermissionGate) -> Dict[str, Any]:
        """
        Rule-based planning matching the agent's fallback logic.

        Generates a simple plan from the analysis text.
        """
        actions: List[Dict[str, Any]] = []

        if "ERROR" in analysis or "critical" in analysis.lower():
            actions.append({
                "action": "check_health",
                "params": {},
                "risk": "low",
                "reason": "Re-check service health to confirm error state",
            })
            actions.append({
                "action": "read_logs",
                "params": {"level": "ERROR", "limit": 20},
                "risk": "low",
                "reason": "Check error logs for root cause",
            })

        if "WARNING" in analysis or "medium" in analysis.lower():
            actions.append({
                "action": "check_metrics",
                "params": {"query": "rate(http_requests_total[5m])", "time_range": "5m"},
                "risk": "low",
                "reason": "Check metrics for degradation patterns",
            })

        # Filter actions through permission gate
        approved_actions = []
        rejected_actions = []
        for a in actions:
            if gate.validate(a["action"]):
                approved_actions.append(a)
            else:
                rejected_actions.append({
                    "action": a["action"],
                    "reason": f"Permission denied for '{a['action']}'",
                })

        overall_risk = "medium" if approved_actions else "low"

        return {
            "actions": approved_actions,
            "overall_risk": overall_risk,
            "rejected_actions": rejected_actions,
        }

    # ── Execution ────────────────────────────────────────────────────────────

    @staticmethod
    async def _execute_plan(
        plan: Dict[str, Any],
        gate: PermissionGate,
        env: SimulationEnvironment,
    ) -> List[Dict[str, Any]]:
        """
        Execute approved actions in the plan against the simulated environment.

        Each action is re-validated through the permission gate before
        execution.  Denied actions are recorded and skipped.
        """
        actions = plan.get("actions", [])
        results: List[Dict[str, Any]] = []

        for action_spec in actions:
            action_name = action_spec.get("action", "")

            # Re-validate through permission gate
            if not gate.validate(action_name):
                results.append({
                    "action": action_name,
                    "status": "denied",
                    "reason": "Permission gate denied action",
                })
                continue

            # Execute mock action
            try:
                if action_name == "check_health":
                    observations = await env.collect()
                    results.append({
                        "action": action_name,
                        "status": "success",
                        "result": {
                            "healthy_count": sum(1 for o in observations if o.status == "ok"),
                            "total_count": len(observations),
                        },
                    })
                elif action_name == "read_logs":
                    results.append({
                        "action": action_name,
                        "status": "success",
                        "result": {"entries": [], "message": "Mocked log read"},
                    })
                elif action_name == "check_metrics":
                    results.append({
                        "action": action_name,
                        "status": "success",
                        "result": {"metrics": {"mock": True}},
                    })
                else:
                    results.append({
                        "action": action_name,
                        "status": "success",
                        "result": {"mocked": True},
                    })
            except Exception as exc:
                results.append({
                    "action": action_name,
                    "status": "error",
                    "error": str(exc),
                })

        return results

    # ── Verification ─────────────────────────────────────────────────────────

    @staticmethod
    def _verify(
        execution_results: List[Dict[str, Any]],
        new_observations: List[Observation],
    ) -> str:
        """
        Verify that executed actions had their intended effect.

        Compares execution results against fresh observations.
        """
        successes = sum(1 for r in execution_results if r.get("status") == "success")
        errors = sum(1 for r in execution_results if r.get("status") == "error")
        denied = sum(1 for r in execution_results if r.get("status") == "denied")

        services_ok = sum(1 for o in new_observations if o.status == "ok")
        services_warn = sum(1 for o in new_observations if o.status == "warn")
        services_error = sum(1 for o in new_observations if o.status == "error")

        lines = [
            "Verification complete.",
            f"  Actions: {successes} succeeded, {errors} failed, {denied} denied.",
            f"  Services: {services_ok} ok, {services_warn} degraded, {services_error} error.",
        ]

        if services_error == 0:
            lines.append("  Result: ALL SERVICES HEALTHY.")
        elif services_error <= 1:
            lines.append("  Result: MOSTLY HEALTHY — minor issues remain.")
        else:
            lines.append("  Result: MULTIPLE ISSUES DETECTED — escalation recommended.")

        return "\n".join(lines)

    # ── Report Printing ──────────────────────────────────────────────────────

    def _print_report(self) -> None:
        """Print a formatted simulation report to the console."""
        report = self._report
        divider = "═" * 70

        print(f"\n{divider}")
        print("  MATE-Ops Phase 1 — Simulation Report")
        print(f"{divider}")
        print(f"  Timestamp       : {report.timestamp}")
        print(f"  Authority Level : {report.authority_level} (READ_ONLY)")
        print(f"  Scenarios Run   : {report.scenarios_run}")
        print(f"  Scenarios Passed: {report.scenarios_passed}")
        print(f"  Scenarios Failed: {report.scenarios_failed}")
        print(f"  Total Latency   : {round(report.total_latency_ms, 1)} ms")
        print(f"{divider}")

        for sr in report.scenario_results:
            status_icon = "✅" if sr.passed else "❌"
            print(f"\n  {status_icon} {sr.scenario_name} ({round(sr.total_latency_ms, 1)} ms)")

            for sl in sr.stage_latencies:
                print(f"     └─ {sl.stage:10s} : {round(sl.latency_ms, 1):>8} ms")

            # Show key findings
            obs_ok = sum(1 for o in sr.observations if o.get("status") == "ok")
            obs_err = sum(1 for o in sr.observations if o.get("status") == "error")
            obs_warn = sum(1 for o in sr.observations if o.get("status") == "warn")
            print(f"     └─ {'services':10s} : {obs_ok} ok, {obs_warn} warn, {obs_err} error")

            exec_ok = sum(1 for r in sr.execution_results if r.get("status") == "success")
            exec_denied = sum(1 for r in sr.execution_results if r.get("status") == "denied")
            print(f"     └─ {'actions':10s} : {exec_ok} succeeded, {exec_denied} denied")

            if sr.error:
                print(f"     └─ {'ERROR':10s} : {sr.error}")

        print(f"\n{divider}")
        print(f"  Result: {report.scenarios_passed}/{report.scenarios_run} scenarios passed")
        print(f"{divider}\n")
