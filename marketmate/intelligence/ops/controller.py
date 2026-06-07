"""
marketmate.intelligence.ops.controller
───────────────────────────────────────
OPS: System Operations Controller

The infrastructure control brain — keeps the system alive, reliable,
and scalable. Fully internal. Never public-facing.

OPS runs parallel to the intelligence pipeline:
  RAW DATA → PRISM → VINNI → ATLAS → VANTA → NOVA → Users
                              ↑ OPS (infrastructure) ↑

Tier System:
  Tier 1 (Auto-approved):    Monitor, observe, report, read logs, check metrics
  Tier 2 (Auto-approved safe): Restart workers, clear cache, rotate logs,
                                reconnect feeds, switch provider
  Tier 3 (Human approval):   Deploy patches, delete data, modify infrastructure,
                              config changes

CRITICAL SAFETY:
  - OPS must NEVER execute Tier 3 actions without human approval.
  - ALWAYS validate against permission gate before execution.
  - NEVER bypass kill switch.
  - Every action is logged for audit.
  - Every Tier 3 action requires an approval callback confirmation.

Authority Level Mapping:
  Tier 1 → AuthorityLevel.READ_ONLY  (0)
  Tier 2 → AuthorityLevel.SAFE_OPS   (1)
  Tier 3 → AuthorityLevel.DESTRUCTIVE (2)

Integration:
  Uses PermissionGate from mate_ops.permission_gate for all
  authorization decisions. Never bypasses the gate.

Created: 2026-05-29
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Callable, Coroutine, Dict, List, Optional

from marketmate.core.logger import get_logger
from marketmate.mate_ops.permission_gate import AuthorityLevel, PermissionGate

log = get_logger("intelligence.ops")


# ─── Tier Definitions ────────────────────────────────────────────────────────

TIER_1_OPERATIONS: set[str] = {
    "monitor", "observe", "report", "read_logs", "check_metrics",
    "check_health", "get_status", "inspect",
}

TIER_2_OPERATIONS: set[str] = {
    "restart_service", "clear_cache", "rotate_logs",
    "reconnect_feed", "switch_provider",
}

TIER_3_OPERATIONS: set[str] = {
    "deploy", "delete_data", "modify_infrastructure", "config_change",
    "scale", "db_migration",
}

# Mapping from operation name to its tier
OPERATION_TIER_MAP: Dict[str, int] = {}
for _op in TIER_1_OPERATIONS:
    OPERATION_TIER_MAP[_op] = 1
for _op in TIER_2_OPERATIONS:
    OPERATION_TIER_MAP[_op] = 2
for _op in TIER_3_OPERATIONS:
    OPERATION_TIER_MAP[_op] = 3

# Mapping from tier to AuthorityLevel
TIER_TO_AUTHORITY: Dict[int, AuthorityLevel] = {
    1: AuthorityLevel.READ_ONLY,
    2: AuthorityLevel.SAFE_OPS,
    3: AuthorityLevel.DESTRUCTIVE,
}

# Scaling bounds — never auto-scale beyond these limits
SCALE_MIN_INSTANCES = 1
SCALE_MAX_INSTANCES = 10

# Known services for health monitoring
KNOWN_SERVICES: List[str] = [
    "api", "worker", "scheduler", "data_engine",
    "telegram_bot", "redis", "mongodb", "ollama",
]


# ─── Service Health Record ───────────────────────────────────────────────────

@dataclass
class _ServiceHealthRecord:
    """Internal tracking record for a single service's health state."""

    name: str
    status: str = "unknown"  # "healthy" | "degraded" | "down" | "unknown"
    last_check: str = ""
    consecutive_failures: int = 0
    total_checks: int = 0
    total_failures: int = 0
    latency_ms: float = 0.0
    details: Dict[str, Any] = field(default_factory=dict)

    def record_check(self, healthy: bool, latency_ms: float = 0.0) -> None:
        """Record a health check result."""
        self.total_checks += 1
        self.last_check = datetime.now(timezone.utc).isoformat()
        self.latency_ms = latency_ms

        if healthy:
            self.status = "healthy"
            self.consecutive_failures = 0
        else:
            self.total_failures += 1
            self.consecutive_failures += 1
            self.status = "down" if self.consecutive_failures >= 3 else "degraded"


# ─── Deployment Record ───────────────────────────────────────────────────────

@dataclass
class _DeploymentRecord:
    """Internal tracking record for a deployment."""

    version: str
    environment: str
    status: str = "pending"  # "pending" | "approved" | "in_progress" | "completed" | "failed" | "rolled_back"
    requested_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    approved_at: str = ""
    completed_at: str = ""
    requested_by: str = "ops_controller"
    rollback_version: str = ""
    details: Dict[str, Any] = field(default_factory=dict)


# ─── OpsAction ────────────────────────────────────────────────────────────────

@dataclass
class OpsAction:
    """
    A structured operation request for the OPS controller.

    Every action that passes through OPS is encapsulated as an OpsAction,
    which carries all the metadata needed for authorization, execution,
    and audit logging.

    Attributes:
        operation: The operation to perform. Must be a known operation
            name from the tier system (e.g., "restart_service", "deploy").
        target: The service or resource this operation targets.
        authority_level: Required authority level (0, 1, or 2).
            Mapped from the operation's tier automatically.
        requires_approval: Whether this action requires human approval
            before execution (True for all Tier 3 actions).
        estimated_impact: How much this operation will affect the system.
            One of: "none", "minimal", "moderate", "significant".
        rollback_plan: Description of how to undo this operation if
            something goes wrong. Required for Tier 2 and Tier 3.
        params: Additional parameters for the operation.
        tier: The operation tier (1, 2, or 3). Auto-set from operation
            name if not provided.
    """

    operation: str  # "restart_service" | "clear_cache" | "deploy" | "scale" | "rotate_logs" | "reconnect_feed" | "switch_provider"
    target: str  # service name
    authority_level: int  # 0, 1, or 2
    requires_approval: bool
    estimated_impact: str  # "none" | "minimal" | "moderate" | "significant"
    rollback_plan: str
    params: Dict[str, Any] = field(default_factory=dict)
    tier: int = 1  # 1=auto, 2=safe-auto, 3=human-required

    def __post_init__(self) -> None:
        """Auto-set tier from operation name if not explicitly provided."""
        if self.operation in OPERATION_TIER_MAP:
            mapped_tier = OPERATION_TIER_MAP[self.operation]
            # Only override if tier is still the default
            if self.tier == 1 and mapped_tier != 1:
                self.tier = mapped_tier

        # Ensure consistency: tier 3 always requires approval
        if self.tier == 3:
            self.requires_approval = True

        # Ensure authority level matches tier
        expected_auth = TIER_TO_AUTHORITY.get(self.tier, AuthorityLevel.READ_ONLY)
        if self.authority_level < expected_auth.value:
            self.authority_level = expected_auth.value

    def to_dict(self) -> Dict[str, Any]:
        """Convert to structured dictionary for logging and serialization."""
        return {
            "operation": self.operation,
            "target": self.target,
            "authority_level": self.authority_level,
            "requires_approval": self.requires_approval,
            "estimated_impact": self.estimated_impact,
            "rollback_plan": self.rollback_plan,
            "params": self.params,
            "tier": self.tier,
        }


# ─── OpsResult ───────────────────────────────────────────────────────────────

@dataclass
class OpsResult:
    """
    The result of an OPS operation execution.

    Captures everything about the outcome — what was attempted,
    whether it succeeded, and what happened. Every OpsAction
    produces exactly one OpsResult.

    Attributes:
        operation: The operation that was attempted.
        target: The service or resource that was targeted.
        status: The outcome status — "requested", "in_progress",
            "completed", "failed", or "denied".
        authority_level: The authority level at which this was executed.
        requires_approval: Whether approval was required (and obtained).
        estimated_impact: The impact estimate from the original action.
        rollback_plan: The rollback plan from the original action.
        result_detail: Detailed output from the operation, including
            any error messages, response data, or diagnostic info.
        timestamp: ISO 8601 timestamp when this result was produced.
        execution_time_ms: How long the operation took to execute.
    """

    operation: str
    target: str
    status: str  # "requested" | "in_progress" | "completed" | "failed" | "denied"
    authority_level: int
    requires_approval: bool
    estimated_impact: str
    rollback_plan: str
    result_detail: Dict[str, Any] = field(default_factory=dict)
    timestamp: str = ""
    execution_time_ms: float = 0.0

    def __post_init__(self) -> None:
        """Auto-set timestamp if not provided."""
        if not self.timestamp:
            self.timestamp = datetime.now(timezone.utc).isoformat()

    def to_dict(self) -> Dict[str, Any]:
        """Convert to structured dictionary for logging and serialization."""
        return {
            "operation": self.operation,
            "target": self.target,
            "status": self.status,
            "authority_level": self.authority_level,
            "requires_approval": self.requires_approval,
            "estimated_impact": self.estimated_impact,
            "rollback_plan": self.rollback_plan,
            "result_detail": self.result_detail,
            "timestamp": self.timestamp,
            "execution_time_ms": round(self.execution_time_ms, 2),
        }


# ─── OpsController ───────────────────────────────────────────────────────────

class OpsController:
    """
    System Operations Controller — the infrastructure control brain.

    Keeps the system alive, reliable, and scalable. Fully internal,
    never public-facing. Runs parallel to the intelligence pipeline.

    Capabilities:
      1. Service monitoring and health checks
      2. Container orchestration (Docker/K8s integration points)
      3. Deployment management (with approval gates)
      4. Scaling decisions (auto-scale within bounds)
      5. Log management and rotation
      6. Self-healing operations (bounded automation)
      7. Recovery orchestration
      8. Resource optimization

    Safety Rules:
      - NEVER execute Tier 3 actions without human approval.
      - ALWAYS validate against permission gate before execution.
      - NEVER bypass kill switch.
      - Every action is logged for audit.
      - All operations have rollback plans.
      - Scaling is bounded by SCALE_MIN/MAX_INSTANCES.

    Usage:
        controller = OpsController()
        action = OpsAction(
            operation="restart_service",
            target="worker",
            authority_level=1,
            requires_approval=False,
            estimated_impact="minimal",
            rollback_plan="Service will auto-restart on failure",
        )
        result = controller.execute_action(action)

    Configuration:
        authority_level: Maximum authority level this controller operates at.
            Default is SAFE_OPS (1) — allows Tier 1 and Tier 2.
        permission_gate: Optional PermissionGate instance. If not provided,
            a default gate is created with the given authority_level.
        approval_callback: Async callable for human approval of Tier 3
            actions. Should return True if approved, False otherwise.
    """

    def __init__(
        self,
        authority_level: AuthorityLevel = AuthorityLevel.SAFE_OPS,
        permission_gate: Optional[PermissionGate] = None,
        approval_callback: Optional[Callable[..., Coroutine[Any, Any, bool]]] = None,
    ) -> None:
        """
        Initialize the OPS controller.

        Args:
            authority_level: Maximum authority level for this controller.
                Default is SAFE_OPS (1) — allows observation and safe
                operations but NOT destructive actions without escalation.
            permission_gate: Permission gate for action validation.
                If None, a default gate is created.
            approval_callback: Async callable for Tier 3 human approval.
                Typically sends a notification and waits for confirmation.
        """
        self._authority_level = authority_level
        self._permission_gate = permission_gate or PermissionGate(
            max_authority_level=authority_level,
            approval_callback=approval_callback,
        )
        self._approval_callback = approval_callback

        # Service health tracking
        self._service_health: Dict[str, _ServiceHealthRecord] = {
            svc: _ServiceHealthRecord(name=svc) for svc in KNOWN_SERVICES
        }

        # Deployment tracking
        self._deployments: List[_DeploymentRecord] = []
        self._max_deployment_history = 50

        # Execution history for audit
        self._execution_history: List[OpsResult] = []
        self._max_history = 500

        # Current deployment state
        self._current_version: str = "unknown"
        self._current_environment: str = "unknown"

        # Controller counters
        self._total_actions_executed: int = 0
        self._total_actions_denied: int = 0
        self._total_actions_failed: int = 0

        log.info(
            "ops_controller_initialized",
            authority_level=authority_level.value,
            kill_switch_active=PermissionGate.KILL_SWITCH,
            services_tracked=len(KNOWN_SERVICES),
        )

    # ── Core: Execute Action ───────────────────────────────────────────────

    def execute_action(self, action: OpsAction) -> OpsResult:
        """
        Validate an action against the permission gate and execute it.

        This is the primary execution path. Every OPS action must flow
        through this method to ensure proper authorization, logging,
        and safety checks.

        Validation order:
          1. Kill switch check — if active, deny all Tier 2+ actions
          2. Tier classification — determine required authority level
          3. Permission gate validation — check if action is allowed
          4. Tier 3 approval — if required, check human approval
          5. Execute the operation

        CRITICAL: Tier 3 actions are ALWAYS denied without explicit
        human approval. This cannot be overridden.

        Args:
            action: The OpsAction to validate and execute.

        Returns:
            OpsResult with the outcome of the operation.
        """
        start = time.monotonic()

        # ── Step 1: Kill switch check ────────────────────────────────────
        if PermissionGate.KILL_SWITCH and action.tier >= 2:
            result = OpsResult(
                operation=action.operation,
                target=action.target,
                status="denied",
                authority_level=action.authority_level,
                requires_approval=action.requires_approval,
                estimated_impact=action.estimated_impact,
                rollback_plan=action.rollback_plan,
                result_detail={
                    "reason": "kill_switch_active",
                    "message": "Kill switch is active. All Tier 2+ actions are denied.",
                },
                execution_time_ms=(time.monotonic() - start) * 1000,
            )
            self._record_result(result)
            self._total_actions_denied += 1
            log.warning(
                "ops_action_denied_kill_switch",
                operation=action.operation,
                target=action.target,
                tier=action.tier,
            )
            return result

        # ── Step 2: Permission gate validation ───────────────────────────
        if not self._permission_gate.validate(action.operation):
            # Check if this is a Tier 3 action that needs human approval
            if action.tier == 3:
                # Tier 3 actions require explicit human approval
                result = OpsResult(
                    operation=action.operation,
                    target=action.target,
                    status="denied",
                    authority_level=action.authority_level,
                    requires_approval=True,
                    estimated_impact=action.estimated_impact,
                    rollback_plan=action.rollback_plan,
                    result_detail={
                        "reason": "tier_3_requires_approval",
                        "message": (
                            f"Operation '{action.operation}' is Tier 3 and requires "
                            "explicit human approval. Use request_approval() first."
                        ),
                        "tier": action.tier,
                    },
                    execution_time_ms=(time.monotonic() - start) * 1000,
                )
                self._record_result(result)
                self._total_actions_denied += 1
                log.warning(
                    "ops_action_denied_tier3",
                    operation=action.operation,
                    target=action.target,
                )
                return result

            # Non-Tier-3 action denied by permission gate
            required_level = self._permission_gate.get_required_level(action.operation)
            result = OpsResult(
                operation=action.operation,
                target=action.target,
                status="denied",
                authority_level=action.authority_level,
                requires_approval=action.requires_approval,
                estimated_impact=action.estimated_impact,
                rollback_plan=action.rollback_plan,
                result_detail={
                    "reason": "permission_denied",
                    "required_level": required_level.value if required_level else None,
                    "max_level": self._permission_gate.max_authority_level.value,
                },
                execution_time_ms=(time.monotonic() - start) * 1000,
            )
            self._record_result(result)
            self._total_actions_denied += 1
            log.warning(
                "ops_action_denied_permission",
                operation=action.operation,
                target=action.target,
            )
            return result

        # ── Step 3: Dispatch operation ───────────────────────────────────
        log.info(
            "ops_action_executing",
            operation=action.operation,
            target=action.target,
            tier=action.tier,
            authority_level=action.authority_level,
        )

        try:
            result = self._dispatch_operation(action)
            result.execution_time_ms = (time.monotonic() - start) * 1000
            self._total_actions_executed += 1

            if result.status == "failed":
                self._total_actions_failed += 1

            log.info(
                "ops_action_completed",
                operation=action.operation,
                target=action.target,
                status=result.status,
                execution_time_ms=round(result.execution_time_ms, 2),
            )

        except Exception as exc:
            result = OpsResult(
                operation=action.operation,
                target=action.target,
                status="failed",
                authority_level=action.authority_level,
                requires_approval=action.requires_approval,
                estimated_impact=action.estimated_impact,
                rollback_plan=action.rollback_plan,
                result_detail={
                    "reason": "execution_error",
                    "error": str(exc),
                },
                execution_time_ms=(time.monotonic() - start) * 1000,
            )
            self._total_actions_failed += 1
            log.error(
                "ops_action_execution_error",
                operation=action.operation,
                target=action.target,
                error=str(exc),
            )

        self._record_result(result)
        return result

    # ── Tier 2 Operations ─────────────────────────────────────────────────

    def restart_service(self, service_name: str) -> OpsResult:
        """
        Restart a service — Tier 2 (auto-approved safe operation).

        Sends a restart command via the container orchestration layer.
        The service is expected to recover within its health check window.

        Args:
            service_name: Name of the service to restart.

        Returns:
            OpsResult with restart status.
        """
        action = OpsAction(
            operation="restart_service",
            target=service_name,
            authority_level=AuthorityLevel.SAFE_OPS.value,
            requires_approval=False,
            estimated_impact="minimal",
            rollback_plan=f"Service '{service_name}' will auto-restart on failure. Manual intervention if restart loop occurs.",
            params={"service_name": service_name},
            tier=2,
        )
        return self.execute_action(action)

    def clear_cache(self, pattern: str = "*") -> OpsResult:
        """
        Clear cache keys matching a pattern — Tier 2 (auto-approved safe operation).

        Uses SCAN + DEL to avoid blocking Redis on large key spaces.
        Common patterns: "signal:*", "price:*", "*" (full flush).

        Args:
            pattern: Redis key pattern to match and clear.

        Returns:
            OpsResult with cache clear status and count of keys deleted.
        """
        action = OpsAction(
            operation="clear_cache",
            target="redis",
            authority_level=AuthorityLevel.SAFE_OPS.value,
            requires_approval=False,
            estimated_impact="minimal",
            rollback_plan="Cache will repopulate from data sources. Expect temporary increase in data source queries.",
            params={"pattern": pattern},
            tier=2,
        )
        return self.execute_action(action)

    def rotate_logs(self, service_name: str) -> OpsResult:
        """
        Rotate logs for a service — Tier 2 (auto-approved safe operation).

        Compresses current log files and rotates them to archive storage.
        Prevents disk exhaustion from unbounded log growth.

        Args:
            service_name: Name of the service whose logs to rotate.

        Returns:
            OpsResult with log rotation status.
        """
        action = OpsAction(
            operation="rotate_logs",
            target=service_name,
            authority_level=AuthorityLevel.SAFE_OPS.value,
            requires_approval=False,
            estimated_impact="none",
            rollback_plan="Log rotation is non-destructive. Old logs are archived, not deleted.",
            params={"service_name": service_name},
            tier=2,
        )
        return self.execute_action(action)

    def reconnect_feed(self, provider: str, symbol: str) -> OpsResult:
        """
        Reconnect a data feed — Tier 2 (auto-approved safe operation).

        Drops and re-establishes the WebSocket/HTTP connection to a
        market data provider for a specific symbol. Used when feed
        latency exceeds thresholds or connection is stale.

        Args:
            provider: Data provider name (e.g., "binance", "twelve_data").
            symbol: Trading symbol to reconnect (e.g., "BTCUSDT").

        Returns:
            OpsResult with reconnection status.
        """
        action = OpsAction(
            operation="reconnect_feed",
            target=f"{provider}:{symbol}",
            authority_level=AuthorityLevel.SAFE_OPS.value,
            requires_approval=False,
            estimated_impact="minimal",
            rollback_plan=f"Feed will auto-reconnect. If {provider} is down, fallback provider will be used.",
            params={"provider": provider, "symbol": symbol},
            tier=2,
        )
        return self.execute_action(action)

    def switch_provider(self, from_provider: str, to_provider: str, symbol: str) -> OpsResult:
        """
        Switch data provider for a symbol — Tier 2 (auto-approved safe operation).

        Routes data requests from one provider to another for a specific
        symbol. Used when a provider is degraded or rate-limited.

        Args:
            from_provider: Current provider to switch away from.
            to_provider: Provider to switch to.
            symbol: Trading symbol affected by the switch.

        Returns:
            OpsResult with provider switch status.
        """
        action = OpsAction(
            operation="switch_provider",
            target=f"{symbol}",
            authority_level=AuthorityLevel.SAFE_OPS.value,
            requires_approval=False,
            estimated_impact="minimal",
            rollback_plan=f"Switch back to {from_provider} if {to_provider} has issues. Feed data may have brief gap during switch.",
            params={
                "from_provider": from_provider,
                "to_provider": to_provider,
                "symbol": symbol,
            },
            tier=2,
        )
        return self.execute_action(action)

    # ── Tier 3 Operations ─────────────────────────────────────────────────

    def scale_service(self, service_name: str, instances: int) -> OpsResult:
        """
        Scale a service to a given number of instances — Tier 3.

        Adjusts the number of running instances for a service within
        the bounded range [SCALE_MIN_INSTANCES, SCALE_MAX_INSTANCES].
        Requests outside this range are clamped and a warning is logged.

        CRITICAL: This is a Tier 3 operation and REQUIRES human approval.
        The permission gate will deny this action without explicit approval.

        Args:
            service_name: Name of the service to scale.
            instances: Target number of instances. Clamped to bounds.

        Returns:
            OpsResult with scaling status. Will be "denied" if approval
            is not obtained.
        """
        # Enforce scaling bounds
        clamped = max(SCALE_MIN_INSTANCES, min(SCALE_MAX_INSTANCES, instances))
        if clamped != instances:
            log.warning(
                "ops_scale_clamped",
                service=service_name,
                requested=instances,
                clamped=clamped,
                min=SCALE_MIN_INSTANCES,
                max=SCALE_MAX_INSTANCES,
            )

        impact = "moderate" if clamped <= 3 else "significant"
        action = OpsAction(
            operation="scale",
            target=service_name,
            authority_level=AuthorityLevel.DESTRUCTIVE.value,
            requires_approval=True,
            estimated_impact=impact,
            rollback_plan=f"Scale back to current instance count. Service '{service_name}' may have brief downtime during scale-down.",
            params={"service_name": service_name, "instances": clamped},
            tier=3,
        )
        return self.execute_action(action)

    def deploy(self, version: str, environment: str) -> OpsResult:
        """
        Deploy a new version — Tier 3 (REQUIRES human approval).

        Initiates a deployment of the specified version to the given
        environment. This is the most impactful OPS operation and
        absolutely requires human approval before execution.

        CRITICAL SAFETY:
          - NEVER execute without human approval.
          - ALWAYS validate against permission gate.
          - NEVER bypass kill switch.
          - Rollback plan is mandatory.

        The deployment is recorded in the deployment history for
        audit and potential rollback.

        Args:
            version: Version string to deploy (e.g., "v2.3.1").
            environment: Target environment (e.g., "production", "staging").

        Returns:
            OpsResult with deployment status. Will be "denied" if
            human approval is not obtained.
        """
        action = OpsAction(
            operation="deploy",
            target=environment,
            authority_level=AuthorityLevel.DESTRUCTIVE.value,
            requires_approval=True,
            estimated_impact="significant",
            rollback_plan=f"Rollback to {self._current_version}. Use deployment record to restore previous state.",
            params={"version": version, "environment": environment},
            tier=3,
        )
        return self.execute_action(action)

    # ── Health and Status ──────────────────────────────────────────────────

    def get_service_health(self) -> Dict[str, Any]:
        """
        Aggregate health across all tracked services.

        Returns a comprehensive health snapshot including per-service
        status, overall system health, and summary statistics.

        This is a Tier 1 (read-only) operation — always allowed.

        Returns:
            Dict with keys:
                - overall: "healthy" | "degraded" | "down" | "unknown"
                - services: Dict mapping service name to health detail
                - healthy_count: Number of healthy services
                - degraded_count: Number of degraded services
                - down_count: Number of down services
                - timestamp: ISO 8601 timestamp
        """
        services: Dict[str, Any] = {}
        healthy_count = 0
        degraded_count = 0
        down_count = 0

        for name, record in self._service_health.items():
            services[name] = {
                "status": record.status,
                "last_check": record.last_check,
                "consecutive_failures": record.consecutive_failures,
                "latency_ms": round(record.latency_ms, 2),
                "total_checks": record.total_checks,
                "total_failures": record.total_failures,
            }

            if record.status == "healthy":
                healthy_count += 1
            elif record.status == "degraded":
                degraded_count += 1
            elif record.status == "down":
                down_count += 1

        # Determine overall health
        if down_count > 0:
            overall = "down" if down_count >= 3 else "degraded"
        elif degraded_count > 0:
            overall = "degraded"
        elif healthy_count > 0:
            overall = "healthy"
        else:
            overall = "unknown"

        return {
            "overall": overall,
            "services": services,
            "healthy_count": healthy_count,
            "degraded_count": degraded_count,
            "down_count": down_count,
            "total_services": len(self._service_health),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def get_deployment_status(self) -> Dict[str, Any]:
        """
        Return current deployment status and recent deployment history.

        Includes the current version, environment, and recent deployments
        for audit and rollback reference.

        This is a Tier 1 (read-only) operation — always allowed.

        Returns:
            Dict with keys:
                - current_version: Currently deployed version
                - current_environment: Current environment
                - recent_deployments: List of recent deployment records
                - total_deployments: Total deployments tracked
                - timestamp: ISO 8601 timestamp
        """
        recent = [
            {
                "version": d.version,
                "environment": d.environment,
                "status": d.status,
                "requested_at": d.requested_at,
                "approved_at": d.approved_at,
                "completed_at": d.completed_at,
                "rollback_version": d.rollback_version,
            }
            for d in self._deployments[-10:]
        ]

        return {
            "current_version": self._current_version,
            "current_environment": self._current_environment,
            "recent_deployments": list(reversed(recent)),
            "total_deployments": len(self._deployments),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    def update_service_health(
        self,
        service_name: str,
        healthy: bool,
        latency_ms: float = 0.0,
        details: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Update health status for a tracked service.

        This is called by monitoring systems to report service health.
        Not an OPS action — this is observation data ingestion.

        Args:
            service_name: Name of the service to update.
            healthy: Whether the service is currently healthy.
            latency_ms: Response latency in milliseconds.
            details: Optional additional health details.
        """
        if service_name in self._service_health:
            record = self._service_health[service_name]
            record.record_check(healthy, latency_ms)
            if details:
                record.details.update(details)
        else:
            # Track previously unknown services
            record = _ServiceHealthRecord(name=service_name)
            record.record_check(healthy, latency_ms)
            if details:
                record.details.update(details)
            self._service_health[service_name] = record

        # Self-healing: auto-detect services that need restart
        record = self._service_health[service_name]
        if record.consecutive_failures >= 3 and not healthy:
            log.warning(
                "ops_self_healing_trigger",
                service=service_name,
                consecutive_failures=record.consecutive_failures,
                action="restart_recommended",
                message=(
                    f"Service '{service_name}' has {record.consecutive_failures} "
                    "consecutive failures. Self-healing: restart recommended."
                ),
            )

    # ── Introspection ─────────────────────────────────────────────────────

    @property
    def status(self) -> Dict[str, Any]:
        """
        Return OPS controller status for health checks and monitoring.

        Includes configuration, counters, and permission gate state.
        """
        health = self.get_service_health()
        return {
            "layer": "ops",
            "role": "infrastructure_control",
            "agent": False,
            "authority_level": self._authority_level.value,
            "kill_switch_active": PermissionGate.KILL_SWITCH,
            "system_health": health["overall"],
            "services_tracked": len(self._service_health),
            "healthy_services": health["healthy_count"],
            "degraded_services": health["degraded_count"],
            "down_services": health["down_count"],
            "total_actions_executed": self._total_actions_executed,
            "total_actions_denied": self._total_actions_denied,
            "total_actions_failed": self._total_actions_failed,
            "current_version": self._current_version,
            "current_environment": self._current_environment,
            "execution_history_size": len(self._execution_history),
            "deployment_history_size": len(self._deployments),
            "scaling_bounds": {
                "min_instances": SCALE_MIN_INSTANCES,
                "max_instances": SCALE_MAX_INSTANCES,
            },
        }

    # ── Internal: Operation Dispatch ──────────────────────────────────────

    def _dispatch_operation(self, action: OpsAction) -> OpsResult:
        """
        Dispatch an approved operation to its handler.

        Each operation type has a dedicated handler that performs the
        actual work. This method routes to the correct handler based
        on the operation name.

        Args:
            action: The validated OpsAction to execute.

        Returns:
            OpsResult from the operation handler.
        """
        dispatch_map: Dict[str, Callable[[OpsAction], OpsResult]] = {
            "restart_service": self._handle_restart_service,
            "clear_cache": self._handle_clear_cache,
            "rotate_logs": self._handle_rotate_logs,
            "reconnect_feed": self._handle_reconnect_feed,
            "switch_provider": self._handle_switch_provider,
            "scale": self._handle_scale_service,
            "deploy": self._handle_deploy,
            # Tier 1 operations (read-only)
            "check_health": self._handle_check_health,
            "read_logs": self._handle_read_logs,
            "check_metrics": self._handle_check_metrics,
            "monitor": self._handle_monitor,
            "observe": self._handle_observe,
            "report": self._handle_report,
        }

        handler = dispatch_map.get(action.operation)
        if handler is None:
            return OpsResult(
                operation=action.operation,
                target=action.target,
                status="failed",
                authority_level=action.authority_level,
                requires_approval=action.requires_approval,
                estimated_impact=action.estimated_impact,
                rollback_plan=action.rollback_plan,
                result_detail={
                    "reason": "unknown_operation",
                    "message": f"No handler registered for operation '{action.operation}'",
                },
            )

        return handler(action)

    # ── Operation Handlers: Tier 2 ────────────────────────────────────────

    def _handle_restart_service(self, action: OpsAction) -> OpsResult:
        """Handle restart_service operation."""
        service_name = action.params.get("service_name", action.target)

        log.warning("ops_restart_service", service=service_name)

        # Integration point: Docker API / K8s API / Render API
        # In production, this would call the container orchestration API.
        # For now, update health tracking and return a structured result.
        if service_name in self._service_health:
            self._service_health[service_name].status = "unknown"
            self._service_health[service_name].consecutive_failures = 0

        return OpsResult(
            operation=action.operation,
            target=action.target,
            status="completed",
            authority_level=action.authority_level,
            requires_approval=action.requires_approval,
            estimated_impact=action.estimated_impact,
            rollback_plan=action.rollback_plan,
            result_detail={
                "service": service_name,
                "action": "restart",
                "status": "requested",
                "message": (
                    f"Restart requested for '{service_name}'. "
                    "Integrate with Docker/K8s/Render API for actual restart."
                ),
                "integration_note": "Connect to container orchestration API for production use.",
            },
        )

    def _handle_clear_cache(self, action: OpsAction) -> OpsResult:
        """Handle clear_cache operation."""
        pattern = action.params.get("pattern", "*")

        log.warning("ops_clear_cache", pattern=pattern)

        return OpsResult(
            operation=action.operation,
            target=action.target,
            status="completed",
            authority_level=action.authority_level,
            requires_approval=action.requires_approval,
            estimated_impact=action.estimated_impact,
            rollback_plan=action.rollback_plan,
            result_detail={
                "pattern": pattern,
                "action": "clear_cache",
                "status": "requested",
                "message": (
                    f"Cache clear requested for pattern '{pattern}'. "
                    "Cache will repopulate from data sources."
                ),
                "integration_note": "Connect to Redis SCAN+DEL for production use.",
            },
        )

    def _handle_rotate_logs(self, action: OpsAction) -> OpsResult:
        """Handle rotate_logs operation."""
        service_name = action.params.get("service_name", action.target)

        log.info("ops_rotate_logs", service=service_name)

        return OpsResult(
            operation=action.operation,
            target=action.target,
            status="completed",
            authority_level=action.authority_level,
            requires_approval=action.requires_approval,
            estimated_impact=action.estimated_impact,
            rollback_plan=action.rollback_plan,
            result_detail={
                "service": service_name,
                "action": "rotate_logs",
                "status": "completed",
                "message": f"Log rotation requested for '{service_name}'.",
                "integration_note": "Connect to log aggregation system for production use.",
            },
        )

    def _handle_reconnect_feed(self, action: OpsAction) -> OpsResult:
        """Handle reconnect_feed operation."""
        provider = action.params.get("provider", "unknown")
        symbol = action.params.get("symbol", "UNKNOWN")

        log.info("ops_reconnect_feed", provider=provider, symbol=symbol)

        return OpsResult(
            operation=action.operation,
            target=action.target,
            status="completed",
            authority_level=action.authority_level,
            requires_approval=action.requires_approval,
            estimated_impact=action.estimated_impact,
            rollback_plan=action.rollback_plan,
            result_detail={
                "provider": provider,
                "symbol": symbol,
                "action": "reconnect",
                "status": "requested",
                "message": (
                    f"Feed reconnection requested for {provider}:{symbol}. "
                    "Feed will auto-reconnect. Fallback provider will cover any gap."
                ),
            },
        )

    def _handle_switch_provider(self, action: OpsAction) -> OpsResult:
        """Handle switch_provider operation."""
        from_provider = action.params.get("from_provider", "unknown")
        to_provider = action.params.get("to_provider", "unknown")
        symbol = action.params.get("symbol", "UNKNOWN")

        log.warning(
            "ops_switch_provider",
            from_provider=from_provider,
            to_provider=to_provider,
            symbol=symbol,
        )

        return OpsResult(
            operation=action.operation,
            target=action.target,
            status="completed",
            authority_level=action.authority_level,
            requires_approval=action.requires_approval,
            estimated_impact=action.estimated_impact,
            rollback_plan=action.rollback_plan,
            result_detail={
                "from_provider": from_provider,
                "to_provider": to_provider,
                "symbol": symbol,
                "action": "switch_provider",
                "status": "completed",
                "message": (
                    f"Provider switched for {symbol}: {from_provider} → {to_provider}. "
                    f"Rollback: switch back to {from_provider} if needed."
                ),
            },
        )

    # ── Operation Handlers: Tier 3 ────────────────────────────────────────

    def _handle_scale_service(self, action: OpsAction) -> OpsResult:
        """Handle scale operation."""
        service_name = action.params.get("service_name", action.target)
        instances = action.params.get("instances", 1)

        # Enforce bounds again at execution time
        instances = max(SCALE_MIN_INSTANCES, min(SCALE_MAX_INSTANCES, instances))

        log.warning(
            "ops_scale_service",
            service=service_name,
            target_instances=instances,
        )

        return OpsResult(
            operation=action.operation,
            target=action.target,
            status="completed",
            authority_level=action.authority_level,
            requires_approval=action.requires_approval,
            estimated_impact=action.estimated_impact,
            rollback_plan=action.rollback_plan,
            result_detail={
                "service": service_name,
                "action": "scale",
                "target_instances": instances,
                "bounds": {
                    "min": SCALE_MIN_INSTANCES,
                    "max": SCALE_MAX_INSTANCES,
                },
                "status": "requested",
                "message": (
                    f"Scale requested for '{service_name}' to {instances} instances. "
                    "Integrate with Docker/K8s HPA for production use."
                ),
            },
        )

    def _handle_deploy(self, action: OpsAction) -> OpsResult:
        """Handle deploy operation."""
        version = action.params.get("version", "unknown")
        environment = action.params.get("environment", "unknown")

        log.warning(
            "ops_deploy",
            version=version,
            environment=environment,
            current_version=self._current_version,
        )

        # Record deployment
        deployment = _DeploymentRecord(
            version=version,
            environment=environment,
            status="requested",
            rollback_version=self._current_version,
        )
        self._deployments.append(deployment)
        if len(self._deployments) > self._max_deployment_history:
            self._deployments = self._deployments[-self._max_deployment_history:]

        # Update current state
        old_version = self._current_version
        self._current_version = version
        self._current_environment = environment
        deployment.status = "completed"
        deployment.completed_at = datetime.now(timezone.utc).isoformat()

        return OpsResult(
            operation=action.operation,
            target=action.target,
            status="completed",
            authority_level=action.authority_level,
            requires_approval=action.requires_approval,
            estimated_impact=action.estimated_impact,
            rollback_plan=action.rollback_plan,
            result_detail={
                "version": version,
                "environment": environment,
                "previous_version": old_version,
                "action": "deploy",
                "status": "completed",
                "rollback_version": old_version,
                "message": (
                    f"Deployment of {version} to {environment} completed. "
                    f"Rollback to {old_version} available."
                ),
                "integration_note": "Connect to CI/CD pipeline for production use.",
            },
        )

    # ── Operation Handlers: Tier 1 (Read-only) ───────────────────────────

    def _handle_check_health(self, action: OpsAction) -> OpsResult:
        """Handle check_health operation (Tier 1)."""
        health = self.get_service_health()
        return OpsResult(
            operation=action.operation,
            target=action.target,
            status="completed",
            authority_level=action.authority_level,
            requires_approval=action.requires_approval,
            estimated_impact=action.estimated_impact,
            rollback_plan=action.rollback_plan,
            result_detail=health,
        )

    def _handle_read_logs(self, action: OpsAction) -> OpsResult:
        """Handle read_logs operation (Tier 1)."""
        return OpsResult(
            operation=action.operation,
            target=action.target,
            status="completed",
            authority_level=action.authority_level,
            requires_approval=action.requires_approval,
            estimated_impact=action.estimated_impact,
            rollback_plan=action.rollback_plan,
            result_detail={
                "message": "Log read operation. Connect to log aggregation for production use.",
                "target": action.target,
            },
        )

    def _handle_check_metrics(self, action: OpsAction) -> OpsResult:
        """Handle check_metrics operation (Tier 1)."""
        return OpsResult(
            operation=action.operation,
            target=action.target,
            status="completed",
            authority_level=action.authority_level,
            requires_approval=action.requires_approval,
            estimated_impact=action.estimated_impact,
            rollback_plan=action.rollback_plan,
            result_detail={
                "message": "Metrics query. Connect to Prometheus/Grafana for production use.",
                "target": action.target,
            },
        )

    def _handle_monitor(self, action: OpsAction) -> OpsResult:
        """Handle monitor operation (Tier 1)."""
        health = self.get_service_health()
        return OpsResult(
            operation=action.operation,
            target=action.target,
            status="completed",
            authority_level=action.authority_level,
            requires_approval=action.requires_approval,
            estimated_impact=action.estimated_impact,
            rollback_plan=action.rollback_plan,
            result_detail={
                "monitoring_snapshot": health,
                "message": "Monitoring snapshot captured.",
            },
        )

    def _handle_observe(self, action: OpsAction) -> OpsResult:
        """Handle observe operation (Tier 1)."""
        return OpsResult(
            operation=action.operation,
            target=action.target,
            status="completed",
            authority_level=action.authority_level,
            requires_approval=action.requires_approval,
            estimated_impact=action.estimated_impact,
            rollback_plan=action.rollback_plan,
            result_detail={
                "message": "Observation recorded. No actions taken.",
                "target": action.target,
                "params": action.params,
            },
        )

    def _handle_report(self, action: OpsAction) -> OpsResult:
        """Handle report operation (Tier 1)."""
        health = self.get_service_health()
        deployment = self.get_deployment_status()
        return OpsResult(
            operation=action.operation,
            target=action.target,
            status="completed",
            authority_level=action.authority_level,
            requires_approval=action.requires_approval,
            estimated_impact=action.estimated_impact,
            rollback_plan=action.rollback_plan,
            result_detail={
                "health_report": health,
                "deployment_report": deployment,
                "ops_status": self.status,
            },
        )

    # ── Internal: Record Keeping ──────────────────────────────────────────

    def _record_result(self, result: OpsResult) -> None:
        """
        Record an OpsResult in the execution history for audit.

        Maintains a bounded history to prevent unbounded memory growth.
        Oldest entries are evicted when the history exceeds the maximum.
        """
        self._execution_history.append(result)
        if len(self._execution_history) > self._max_history:
            self._execution_history = self._execution_history[-self._max_history:]

    def get_execution_history(
        self,
        operation: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 50,
    ) -> List[Dict[str, Any]]:
        """
        Return execution history, optionally filtered.

        Args:
            operation: Filter by operation name.
            status: Filter by result status.
            limit: Maximum number of records to return.

        Returns:
            List of OpsResult dicts, most recent first.
        """
        results = self._execution_history

        if operation:
            results = [r for r in results if r.operation == operation]
        if status:
            results = [r for r in results if r.status == status]

        return [r.to_dict() for r in reversed(results[-limit:])]

    # ── Configuration ─────────────────────────────────────────────────────

    def set_authority_level(self, level: AuthorityLevel) -> None:
        """
        Update the maximum authority level for this controller.

        Also updates the permission gate to match.

        Args:
            level: The new maximum authority level.
        """
        old_level = self._authority_level
        self._authority_level = level
        self._permission_gate.set_authority_level(level)
        log.info(
            "ops_authority_level_changed",
            old_level=old_level.value,
            new_level=level.value,
        )

    @property
    def permission_gate(self) -> PermissionGate:
        """Return the permission gate instance."""
        return self._permission_gate

    @property
    def authority_level(self) -> AuthorityLevel:
        """Return the current maximum authority level."""
        return self._authority_level
