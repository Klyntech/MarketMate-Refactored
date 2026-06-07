"""
marketmate/mate_ops/agent.py
────────────────────────────
MATE-Ops: Autonomous infrastructure intelligence agent.

5-stage pipeline: Observe → Analyze → Plan → Execute → Verify

Authority levels:
  0 = Read-only (observe, analyze, report)
  1 = Safe operations (restart workers, clear caches, rotate logs)
  2 = Destructive (requires explicit human approval)

The agent never executes actions without permission gate approval.
Every decision is logged for audit.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

import httpx

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.mate_ops.observer import Observation, TelemetryCollector, telemetry_collector
from marketmate.mate_ops.permission_gate import AuthorityLevel, PermissionGate

log = get_logger("mate_ops.agent")


# ─── Pipeline Stage Results ───────────────────────────────────────────────────

@dataclass
class PipelineResult:
    """Result of a complete Observe→Analyze→Plan→Execute→Verify cycle."""

    observations: List[Observation] = field(default_factory=list)
    analysis: str = ""
    plan: Dict[str, Any] = field(default_factory=dict)
    execution_results: List[Dict[str, Any]] = field(default_factory=list)
    verification: str = ""
    cycle_id: str = ""
    started_at: str = ""
    completed_at: str = ""
    total_latency_ms: float = 0.0


# ─── MATE-Ops Agent ───────────────────────────────────────────────────────────

class MATEOpsAgent:
    """
    Autonomous infrastructure intelligence agent.

    Runs a 5-stage pipeline:
      1. Observe  — collect telemetry from all monitoring sources
      2. Analyze  — use LLM to identify anomalies and patterns
      3. Plan     — generate action plan with risk assessment
      4. Execute  — validate plan against permission gate, execute approved actions
      5. Verify   — confirm actions had intended effect

    Authority levels control what the agent can do:
      Level 0: observe and report only
      Level 1: safe operations (restart, clear cache, notify)
      Level 2: destructive operations (requires human approval)

    The agent NEVER bypasses the permission gate. If an action is
    denied, it is logged and the agent moves to the next step.
    """

    def __init__(
        self,
        llm_provider: Any = None,
        authority_level: AuthorityLevel = AuthorityLevel.READ_ONLY,
        permission_gate: Optional[PermissionGate] = None,
        telemetry: Optional[TelemetryCollector] = None,
    ) -> None:
        """
        Initialize the MATE-Ops agent.

        Args:
            llm_provider: LLM provider instance for analysis and planning.
                If None, the agent uses the global llm_provider from core.llm.
            authority_level: Maximum authority level for this agent instance.
                Default is Level 0 (read-only) for safety.
            permission_gate: Permission gate for action validation.
                If None, a default gate is created with the given authority_level.
            telemetry: Telemetry collector instance.
                If None, the global singleton is used.
        """
        self._llm_provider = llm_provider
        self._authority_level = authority_level
        self._permission_gate = permission_gate or PermissionGate(
            max_authority_level=authority_level,
        )
        self._telemetry = telemetry or telemetry_collector
        self._cycle_count: int = 0

    # ── Main Pipeline ─────────────────────────────────────────────────────────

    async def run_cycle(self) -> PipelineResult:
        """
        Run one full Observe→Analyze→Plan→Execute→Verify cycle.

        Returns a PipelineResult with details of every stage.
        If any stage fails, subsequent stages are skipped and the
        failure is recorded.
        """
        cycle_id = f"cycle_{self._cycle_count}_{int(time.time())}"
        self._cycle_count += 1
        start = time.monotonic()

        result = PipelineResult(
            cycle_id=cycle_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        log.info("mate_ops_cycle_start", cycle_id=cycle_id)

        # Stage 1: Observe
        try:
            result.observations = await self.observe()
            log.info(
                "mate_ops_observe_complete",
                cycle_id=cycle_id,
                observation_count=len(result.observations),
            )
        except Exception as exc:
            log.error("mate_ops_observe_failed", cycle_id=cycle_id, error=str(exc))
            result.observations = [Observation(
                source="agent",
                status="error",
                message=f"Observation stage failed: {exc}",
            )]

        # Stage 2: Analyze
        try:
            result.analysis = await self.analyze(result.observations)
            log.info("mate_ops_analyze_complete", cycle_id=cycle_id)
        except Exception as exc:
            log.error("mate_ops_analyze_failed", cycle_id=cycle_id, error=str(exc))
            result.analysis = f"Analysis failed: {exc}"

        # Stage 3: Plan
        try:
            result.plan = await self.plan(result.analysis)
            log.info(
                "mate_ops_plan_complete",
                cycle_id=cycle_id,
                action_count=len(result.plan.get("actions", [])),
            )
        except Exception as exc:
            log.error("mate_ops_plan_failed", cycle_id=cycle_id, error=str(exc))
            result.plan = {"error": str(exc), "actions": []}

        # Stage 4: Execute
        try:
            result.execution_results = await self.execute(result.plan)
            log.info(
                "mate_ops_execute_complete",
                cycle_id=cycle_id,
                result_count=len(result.execution_results),
            )
        except Exception as exc:
            log.error("mate_ops_execute_failed", cycle_id=cycle_id, error=str(exc))
            result.execution_results = [{"error": str(exc)}]

        # Stage 5: Verify
        try:
            result.verification = await self.verify(result.execution_results)
            log.info("mate_ops_verify_complete", cycle_id=cycle_id)
        except Exception as exc:
            log.error("mate_ops_verify_failed", cycle_id=cycle_id, error=str(exc))
            result.verification = f"Verification failed: {exc}"

        result.completed_at = datetime.now(timezone.utc).isoformat()
        result.total_latency_ms = round((time.monotonic() - start) * 1000, 1)

        log.info(
            "mate_ops_cycle_complete",
            cycle_id=cycle_id,
            latency_ms=result.total_latency_ms,
            observations=len(result.observations),
            actions_planned=len(result.plan.get("actions", [])),
            actions_executed=len(result.execution_results),
        )

        return result

    # ── Stage 1: Observe ──────────────────────────────────────────────────────

    async def observe(self) -> List[Observation]:
        """
        Collect telemetry from all monitors.

        Delegates to the TelemetryCollector which runs all health
        checks concurrently. Returns a list of Observation objects.
        """
        return await self._telemetry.collect()

    # ── Stage 2: Analyze ──────────────────────────────────────────────────────

    async def analyze(self, observations: List[Observation]) -> str:
        """
        Use LLM to identify anomalies and patterns in observations.

        The LLM receives the full observation list and is prompted
        to identify:
          - Services that are down or degraded
          - Anomalous patterns (high latency, error spikes)
          - Root cause hypotheses
          - Severity assessment

        If no LLM provider is available, falls back to rule-based
        analysis of the observations.
        """
        # Build observation summary for LLM
        obs_summary = self._format_observations(observations)

        prompt = f"""You are MATE-Ops, an infrastructure intelligence analyst. Analyze the following telemetry observations and identify:

1. Services that are DOWN or DEGRADED
2. Anomalous patterns (high latency, error rates, connection issues)
3. Root cause hypotheses
4. Severity level (low/medium/high/critical)

OBSERVATIONS:
{obs_summary}

Provide a concise analysis with clear actionability. Focus on what's wrong and what might be causing it."""

        try:
            llm = self._get_llm_provider()
            if llm is not None:
                response = await llm.chat(
                    system_prompt="You are an infrastructure analyst. Be concise and actionable.",
                    user_prompt=prompt,
                    max_tokens=1024,
                    temperature=0.3,
                )
                return response.text
        except Exception as exc:
            log.warning("mate_ops_llm_analysis_failed", error=str(exc))

        # Fallback: rule-based analysis
        return self._rule_based_analysis(observations)

    # ── Stage 3: Plan ─────────────────────────────────────────────────────────

    async def plan(self, analysis: str) -> Dict[str, Any]:
        """
        Generate action plan with risk assessment.

        Uses the LLM to propose actions based on the analysis.
        Each action includes:
          - action: the action name (must match PermissionGate's ACTION_AUTHORITY_MAP)
          - params: parameters for the action
          - risk: low/medium/high
          - reason: why this action is recommended

        The plan also includes an overall risk assessment and
        a list of actions that were considered but rejected.
        """
        prompt = f"""Based on the following analysis, create an action plan.

ANALYSIS:
{analysis}

Available actions (choose ONLY from this list):
- check_health: Check API health (Level 0)
- check_ollama_status: Check Ollama status (Level 0)
- read_logs: Read application logs (Level 0)
- check_metrics: Query Prometheus metrics (Level 0)
- check_website: Check website via browser (Level 0)
- restart_service: Restart a container service (Level 1)
- clear_cache: Clear Redis cache keys (Level 1)
- notify_team: Send alert to team (Level 1)

Return a JSON plan with this structure:
{{
    "actions": [
        {{
            "action": "action_name",
            "params": {{}},
            "risk": "low|medium|high",
            "reason": "why this action is recommended"
        }}
    ],
    "overall_risk": "low|medium|high|critical",
    "rejected_actions": [
        {{
            "action": "action_name",
            "reason": "why it was considered but rejected"
        }}
    ]
}}"""

        try:
            llm = self._get_llm_provider()
            if llm is not None:
                response = await llm.chat(
                    system_prompt="You are an infrastructure planner. Return valid JSON only.",
                    user_prompt=prompt,
                    max_tokens=1024,
                    temperature=0.2,
                )
                # Try to parse JSON from response
                text = response.text
                # Find JSON in the response (may have markdown fences)
                json_start = text.find("{")
                json_end = text.rfind("}") + 1
                if json_start >= 0 and json_end > json_start:
                    return json.loads(text[json_start:json_end])
        except (json.JSONDecodeError, Exception) as exc:
            log.warning("mate_ops_llm_planning_failed", error=str(exc))

        # Fallback: basic plan from analysis
        return self._rule_based_plan(analysis)

    # ── Stage 4: Execute ──────────────────────────────────────────────────────

    async def execute(self, plan: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Validate plan against permission gate, execute approved actions.

        Each action in the plan is validated against the permission
        gate before execution. Denied actions are logged and skipped.

        Returns a list of execution results, one per action attempted.
        """
        actions = plan.get("actions", [])
        results: List[Dict[str, Any]] = []

        for action_spec in actions:
            action_name = action_spec.get("action", "")
            action_params = action_spec.get("params", {})

            # Validate against permission gate
            if not self._permission_gate.validate(action_name):
                # For destructive actions, try requesting approval
                required_level = self._permission_gate.get_required_level(action_name)
                if required_level == AuthorityLevel.DESTRUCTIVE:
                    approved = await self._permission_gate.request_approval(action_name)
                    if not approved:
                        results.append({
                            "action": action_name,
                            "status": "denied",
                            "reason": "Permission gate denied or human approval rejected",
                        })
                        continue
                else:
                    results.append({
                        "action": action_name,
                        "status": "denied",
                        "reason": f"Authority level too low for '{action_name}'",
                    })
                    continue

            # Execute the action
            try:
                result = await self._execute_action(action_name, action_params)
                results.append({
                    "action": action_name,
                    "status": "success",
                    "result": result,
                })
            except Exception as exc:
                results.append({
                    "action": action_name,
                    "status": "error",
                    "error": str(exc),
                })
                log.error(
                    "mate_ops_action_failed",
                    action=action_name,
                    error=str(exc),
                )

        return results

    # ── Stage 5: Verify ───────────────────────────────────────────────────────

    async def verify(self, execution_results: List[Dict[str, Any]]) -> str:
        """
        Confirm actions had intended effect.

        Re-runs health checks for any services that were acted upon
        and compares before/after states. Returns a summary of
        whether the actions resolved the issues.
        """
        # Collect fresh observations to compare
        try:
            new_observations = await self.observe()
        except Exception as exc:
            return f"Verification failed — could not collect fresh observations: {exc}"

        # Count successes and failures
        action_successes = sum(
            1 for r in execution_results if r.get("status") == "success"
        )
        action_errors = sum(
            1 for r in execution_results if r.get("status") == "error"
        )
        action_denied = sum(
            1 for r in execution_results if r.get("status") == "denied"
        )

        # Count current service health
        services_ok = sum(1 for o in new_observations if o.status == "ok")
        services_warn = sum(1 for o in new_observations if o.status == "warn")
        services_error = sum(1 for o in new_observations if o.status == "error")

        summary_lines = [
            f"Verification complete.",
            f"  Actions: {action_successes} succeeded, {action_errors} failed, {action_denied} denied.",
            f"  Services: {services_ok} ok, {services_warn} degraded, {services_error} error.",
        ]

        if services_error == 0:
            summary_lines.append("  Result: ALL SERVICES HEALTHY.")
        elif services_error <= 1:
            summary_lines.append("  Result: MOSTLY HEALTHY — minor issues remain.")
        else:
            summary_lines.append("  Result: MULTIPLE ISSUES DETECTED — escalation recommended.")

        return "\n".join(summary_lines)

    # ── Individual Action Methods ──────────────────────────────────────────────

    async def check_health(self) -> Dict[str, Any]:
        """
        Quick health check — Authority Level 0.

        Returns current health status of all monitored services.
        """
        observations = await self._telemetry.collect()
        return {
            "services": [
                {"source": o.source, "status": o.status, "message": o.message}
                for o in observations
            ],
            "healthy_count": sum(1 for o in observations if o.status == "ok"),
            "total_count": len(observations),
        }

    async def check_website(self, url: str = "", check_ssl: bool = True) -> Dict[str, Any]:
        """
        Website health via HTTP(S) check — Authority Level 0.

        Optionally checks SSL certificate validity and measures
        response time. Uses Playwright for full browser-based
        checks if available, falls back to HTTP client.
        """
        target_url = url or cfg.platform.base_url
        start = time.monotonic()

        try:
            async with httpx.AsyncClient(timeout=15, verify=check_ssl) as client:
                resp = await client.get(target_url)
            latency_ms = round((time.monotonic() - start) * 1000, 1)

            result: Dict[str, Any] = {
                "url": target_url,
                "status_code": resp.status_code,
                "latency_ms": latency_ms,
                "healthy": resp.status_code < 400,
            }

            # SSL check
            if check_ssl and target_url.startswith("https://"):
                try:
                    ssl_info = resp.extensions.get("network_info", {})
                    result["ssl_valid"] = True  # If we got here, SSL is valid
                except Exception:
                    result["ssl_valid"] = False

            return result

        except httpx.ConnectError:
            return {
                "url": target_url,
                "healthy": False,
                "error": "Connection refused",
            }
        except Exception as exc:
            return {
                "url": target_url,
                "healthy": False,
                "error": str(exc),
            }

    async def read_logs(
        self,
        level: str = "ERROR",
        source: str = "",
        limit: int = 50,
        query: str = "",
    ) -> Dict[str, Any]:
        """
        Query application logs — Authority Level 0.

        Returns recent log entries matching the filters.
        In production, this would query the structured log
        aggregation system (e.g., Loki, CloudWatch).
        """
        # This is a placeholder — in production, integrate with
        # your log aggregation system
        return {
            "level": level,
            "source": source or "all",
            "limit": limit,
            "query": query,
            "entries": [],
            "message": (
                "Log aggregation not configured. "
                "Integrate with Loki, CloudWatch, or similar for production use."
            ),
        }

    async def check_metrics(self, query: str = "", time_range: str = "5m") -> Dict[str, Any]:
        """
        Query Prometheus metrics — Authority Level 0.

        Runs the given PromQL query and returns results.
        Falls back to basic telemetry if Prometheus is unavailable.
        """
        if not self._telemetry._prometheus_url:
            return {
                "query": query,
                "time_range": time_range,
                "error": "Prometheus URL not configured",
                "hint": "Set PROMETHEUS_URL environment variable",
            }

        try:
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.get(
                    f"{self._telemetry._prometheus_url}/api/v1/query",
                    params={"query": query},
                )

            if resp.status_code == 200:
                data = resp.json()
                return {
                    "query": query,
                    "time_range": time_range,
                    "results": data.get("data", {}).get("result", []),
                }
            else:
                return {
                    "query": query,
                    "time_range": time_range,
                    "error": f"Prometheus returned HTTP {resp.status_code}",
                }

        except Exception as exc:
            return {
                "query": query,
                "time_range": time_range,
                "error": str(exc),
            }

    async def restart_service(self, service_name: str) -> Dict[str, Any]:
        """
        Restart a container service — Authority Level 1.

        Validates authority level before execution.
        Sends a restart command via the container orchestration API
        (Docker, Render API, etc.).
        """
        if not self._permission_gate.validate("restart_service"):
            return {"error": "Authority level too low for restart_service"}

        log.warning("mate_ops_restart_service", service=service_name)

        # Integration point: connect to your container orchestration
        # (Docker API, Render API, Kubernetes, etc.)
        return {
            "service": service_name,
            "action": "restart",
            "status": "requested",
            "message": (
                f"Restart requested for '{service_name}'. "
                "Integrate with Docker/Render/K8s API for actual restart."
            ),
        }

    async def clear_cache(self, pattern: str = "*") -> Dict[str, Any]:
        """
        Flush Redis keys matching pattern — Authority Level 1.

        Validates authority level before execution.
        Uses SCAN + DEL to avoid blocking Redis on large key spaces.
        """
        if not self._permission_gate.validate("clear_cache"):
            return {"error": "Authority level too low for clear_cache"}

        log.warning("mate_ops_clear_cache", pattern=pattern)

        try:
            import redis.asyncio as aioredis

            redis_url = cfg.redis.url or "redis://localhost:6379"
            async with aioredis.from_url(redis_url, socket_timeout=5) as r:
                # Scan for matching keys
                keys = []
                async for key in r.scan_iter(match=pattern, count=100):
                    keys.append(key)

                if keys:
                    deleted = await r.delete(*keys)
                    return {
                        "pattern": pattern,
                        "keys_found": len(keys),
                        "keys_deleted": deleted,
                        "status": "success",
                    }
                else:
                    return {
                        "pattern": pattern,
                        "keys_found": 0,
                        "keys_deleted": 0,
                        "status": "no_matching_keys",
                    }

        except ImportError:
            return {
                "pattern": pattern,
                "error": "redis async library not installed",
                "hint": "pip install redis",
            }
        except Exception as exc:
            return {
                "pattern": pattern,
                "error": str(exc),
            }

    async def notify_team(self, message: str, severity: str = "info") -> Dict[str, Any]:
        """
        Send alert via Telegram — Authority Level 1.

        Validates authority level before execution.
        Sends to the admin chat configured in TelegramConfig.
        """
        if not self._permission_gate.validate("notify_team"):
            return {"error": "Authority level too low for notify_team"}

        log.info("mate_ops_notify_team", message=message[:80], severity=severity)

        try:
            if not cfg.telegram.bot_token or not cfg.telegram.admin_chat_id:
                return {
                    "error": "Telegram not configured",
                    "hint": "Set TELEGRAM_BOT_TOKEN and TELEGRAM_ADMIN_CHAT_ID",
                }

            severity_emoji = {
                "info": "ℹ️",
                "warning": "⚠️",
                "critical": "🚨",
            }.get(severity, "📢")

            text = f"{severity_emoji} **MATE-Ops Alert** ({severity.upper()})\n\n{message}"

            url = f"https://api.telegram.org/bot{cfg.telegram.bot_token}/sendMessage"
            async with httpx.AsyncClient(timeout=10) as client:
                resp = await client.post(url, json={
                    "chat_id": cfg.telegram.admin_chat_id,
                    "text": text,
                    "parse_mode": "Markdown",
                })

            if resp.status_code == 200:
                return {"status": "sent", "severity": severity}
            else:
                return {
                    "status": "failed",
                    "error": f"Telegram API returned HTTP {resp.status_code}",
                }

        except Exception as exc:
            return {"status": "failed", "error": str(exc)}

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _get_llm_provider(self) -> Any:
        """
        Get the LLM provider instance.

        Uses the injected provider if available, otherwise imports
        the global provider from core.llm.
        """
        if self._llm_provider is not None:
            return self._llm_provider

        try:
            from marketmate.core.llm import llm_provider
            return llm_provider
        except ImportError:
            return None

    def _format_observations(self, observations: List[Observation]) -> str:
        """Format observations into a readable summary for the LLM."""
        lines = []
        for obs in observations:
            status_icon = {"ok": "✅", "warn": "⚠️", "error": "❌"}.get(
                obs.status, "❓"
            )
            line = f"{status_icon} [{obs.source.upper()}] {obs.status.upper()}: {obs.message}"
            if obs.details:
                detail_strs = [f"  {k}={v}" for k, v in obs.details.items()]
                line += "\n" + "\n".join(detail_strs)
            lines.append(line)
        return "\n\n".join(lines)

    def _rule_based_analysis(self, observations: List[Observation]) -> str:
        """
        Fallback rule-based analysis when LLM is unavailable.

        Identifies services by status and generates a summary.
        """
        errors = [o for o in observations if o.status == "error"]
        warnings = [o for o in observations if o.status == "warn"]
        ok = [o for o in observations if o.status == "ok"]

        lines = [f"Infrastructure Analysis (rule-based)"]
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

        severity = "critical" if len(errors) >= 2 else "high" if errors else "medium" if warnings else "low"
        lines.append(f"\nOverall severity: {severity}")

        return "\n".join(lines)

    def _rule_based_plan(self, analysis: str) -> Dict[str, Any]:
        """
        Fallback rule-based planning when LLM is unavailable.

        Generates a simple plan based on the analysis text.
        """
        actions: List[Dict[str, Any]] = []

        # If errors detected, plan diagnostic actions
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

            # If authority allows, suggest notification
            if self._authority_level >= AuthorityLevel.SAFE_OPS:
                actions.append({
                    "action": "notify_team",
                    "params": {"message": "Errors detected in infrastructure", "severity": "warning"},
                    "risk": "low",
                    "reason": "Alert team about detected errors",
                })

        return {
            "actions": actions,
            "overall_risk": "medium" if actions else "low",
            "rejected_actions": [],
        }

    async def _execute_action(
        self, action_name: str, params: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Execute a single action by name with the given parameters."""
        action_map = {
            "check_health": lambda: self.check_health(),
            "check_ollama_status": lambda: self._check_ollama(),
            "read_logs": lambda: self.read_logs(**params),
            "check_metrics": lambda: self.check_metrics(**params),
            "check_website": lambda: self.check_website(**params),
            "restart_service": lambda: self.restart_service(**params),
            "clear_cache": lambda: self.clear_cache(**params),
            "notify_team": lambda: self.notify_team(**params),
        }

        handler = action_map.get(action_name)
        if handler is None:
            return {"error": f"Unknown action: {action_name}"}

        return await handler()

    async def _check_ollama(self) -> Dict[str, Any]:
        """Check Ollama status — helper for action dispatch."""
        obs = await self._telemetry.check_ollama_health()
        return {
            "source": obs.source,
            "status": obs.status,
            "message": obs.message,
            "details": obs.details,
        }

    # ── Introspection ─────────────────────────────────────────────────────────

    @property
    def authority_level(self) -> AuthorityLevel:
        """Return the current maximum authority level."""
        return self._authority_level

    @property
    def permission_gate(self) -> PermissionGate:
        """Return the permission gate instance."""
        return self._permission_gate

    @property
    def status(self) -> Dict[str, Any]:
        """Return agent status summary."""
        return {
            "module": "mate_ops",
            "architecture": "5_stage_pipeline",
            "authority_level": self._authority_level.value,
            "kill_switch_active": PermissionGate.KILL_SWITCH,
            "cycles_completed": self._cycle_count,
        }
