"""
marketmate/mate_ops/auto_remediator.py
───────────────────────────────────────
MATE-Ops Phase 2: Semi-autonomous infrastructure intelligence.

This module provides **safe auto-remediation** for Level 1 actions within
the MATE-Ops 5-stage pipeline (Observe → Analyze → Plan → Execute → Verify).

Phase 2 upgrades MATE-Ops from purely reactive observation to semi-autonomous
remediation with strong safety guardrails.  It addresses the Phase 1 Max/Mini
gaps identified in the capability assessment:

  ┌──────────────────────┬──────────┬──────────┐
  │ Gap                  │ Phase 1  │ Phase 2  │
  ├──────────────────────┼──────────┼──────────┤
  │ Self-Healing         │    3     │    8     │
  │ Blast Radius         │    4     │    2     │
  │ False Positive Rate  │    5     │    2     │
  └──────────────────────┴──────────┴──────────┘

Safety mechanisms enforce three hard constraints before any remediation
action is executed:

  1. **Cooldown enforcement** — a policy cannot fire again within its
     ``cooldown_seconds`` window, preventing remediation storms.
  2. **Max-attempts ceiling** — a policy cannot exceed ``max_attempts``
     within any rolling 24-hour window, capping repeated failures.
  3. **Permission gate** — every action MUST pass through the agent's
     ``PermissionGate``; actions that require higher authority are denied.
  4. **Confirmation gate** — policies flagged ``requires_confirmation``
     are logged but NOT auto-executed; they enter a pending list for
     human review.
  5. **Blast-radius assessment** — before executing, the estimated impact
     of each action is logged so operators can trace side-effects.

Level 1 authority (safe ops): restart_service, clear_cache, rotate_logs,
notify_team.  No Level 2 (destructive) actions are ever auto-executed.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from marketmate.core.logger import get_logger
from marketmate.mate_ops.observer import Observation
from marketmate.mate_ops.permission_gate import AuthorityLevel, PermissionGate
from marketmate.mate_ops.agent import MATEOpsAgent

log = get_logger("mate_ops.auto_remediator")


# ─── Remediation Action ───────────────────────────────────────────────────────

@dataclass
class RemediationAction:
    """
    A single remediation action proposed for execution.

    Produced by :meth:`AutoRemediator.evaluate` and consumed by
    :meth:`AutoRemediator.execute_remediations`.

    Attributes:
        policy_name:      Name of the :class:`RemediationPolicy` that triggered
                          this action.
        action:           Action identifier — must match a key in
                          ``PermissionGate.ACTION_AUTHORITY_MAP``.
        params:           Parameters forwarded to the agent's action handler.
        reason:           Human-readable justification for this action.
        urgency:          Severity bucket — one of ``low``, ``medium``,
                          ``high``, ``critical``.
        estimated_impact: Expected blast radius — one of ``none``,
                          ``minimal``, ``moderate``.
    """

    policy_name: str
    action: str
    params: Dict[str, Any] = field(default_factory=dict)
    reason: str = ""
    urgency: str = "medium"  # "low" | "medium" | "high" | "critical"
    estimated_impact: str = "minimal"  # "none" | "minimal" | "moderate"


# ─── Remediation Policy ──────────────────────────────────────────────────────

@dataclass
class RemediationPolicy:
    """
    Declarative policy that maps an observation trigger to a remediation action.

    Policies are evaluated against the current observation set by
    :meth:`AutoRemediator.evaluate`.  When the trigger condition matches,
    a :class:`RemediationAction` is produced and — subject to safety
    constraints — eventually executed.

    Attributes:
        name:                  Unique policy identifier.
        trigger_condition:     Human-readable description of the condition
                               under which this policy fires.  Used for
                               logging and for the rule-engine matching
                               inside :meth:`AutoRemediator.evaluate`.
        action:                Action identifier — must match a key in
                               ``PermissionGate.ACTION_AUTHORITY_MAP``.
        action_params:         Keyword arguments forwarded to the agent's
                               action handler when this policy fires.
        cooldown_seconds:      Minimum seconds between consecutive executions
                               of this policy.  Prevents remediation storms.
        max_attempts:          Maximum number of executions allowed within a
                               rolling 24-hour window.
        requires_confirmation: If ``True``, the action is logged but NOT
                               auto-executed; it is added to the pending
                               confirmations list for human review.
    """

    name: str
    trigger_condition: str
    action: str
    action_params: Dict[str, Any] = field(default_factory=dict)
    cooldown_seconds: int = 300
    max_attempts: int = 3
    requires_confirmation: bool = False

    @classmethod
    def from_dict(cls, data: dict) -> RemediationPolicy:
        """
        Construct a :class:`RemediationPolicy` from a plain dictionary.

        Missing optional keys fall back to their dataclass defaults.

        Args:
            data: Dictionary with at least ``name``, ``trigger_condition``,
                  and ``action`` keys.  Optional keys ``action_params``,
                  ``cooldown_seconds``, ``max_attempts``, and
                  ``requires_confirmation`` are also accepted.

        Returns:
            A new :class:`RemediationPolicy` instance.

        Raises:
            KeyError: If a required key is missing.
        """
        return cls(
            name=data["name"],
            trigger_condition=data["trigger_condition"],
            action=data["action"],
            action_params=data.get("action_params", {}),
            cooldown_seconds=data.get("cooldown_seconds", 300),
            max_attempts=data.get("max_attempts", 3),
            requires_confirmation=data.get("requires_confirmation", False),
        )


# ─── Remediation Record ──────────────────────────────────────────────────────

@dataclass
class RemediationRecord:
    """
    Audit record for a completed (or skipped/denied) remediation attempt.

    Every call to :meth:`AutoRemediator.execute_remediations` produces one
    record per action, regardless of outcome.  Records are stored in the
    remediator's history and retrievable via :meth:`AutoRemediator.get_history`.

    Attributes:
        policy_name:         Name of the policy that produced this action.
        action:              Action identifier that was attempted.
        triggered_at:        ISO 8601 timestamp when the action was triggered.
        completed_at:        ISO 8601 timestamp when execution finished.
        status:              Outcome — one of ``success``, ``failed``,
                             ``denied``, ``skipped``.
        result:              Structured result payload from the action handler.
        observations_snapshot: Shallow copy of the observations that triggered
                             this remediation, for post-incident analysis.
    """

    policy_name: str
    action: str
    triggered_at: str
    completed_at: str
    status: str  # "success" | "failed" | "denied" | "skipped"
    result: Dict[str, Any] = field(default_factory=dict)
    observations_snapshot: List[Dict[str, Any]] = field(default_factory=list)


# ─── Default Policies ────────────────────────────────────────────────────────

DEFAULT_POLICIES: List[RemediationPolicy] = [
    RemediationPolicy(
        name="stale_cache_clear",
        trigger_condition="redis latency > 500ms",
        action="clear_cache",
        action_params={"pattern": "cache:*"},
        cooldown_seconds=600,
        max_attempts=2,
        requires_confirmation=False,
    ),
    RemediationPolicy(
        name="degraded_service_restart",
        trigger_condition="service status=error for > 15 minutes",
        action="restart_service",
        action_params={},
        cooldown_seconds=1800,
        max_attempts=1,
        requires_confirmation=True,
    ),
    RemediationPolicy(
        name="high_error_alert",
        trigger_condition="2+ services in error state",
        action="notify_team",
        action_params={"severity": "critical"},
        cooldown_seconds=300,
        max_attempts=3,
        requires_confirmation=False,
    ),
    RemediationPolicy(
        name="slow_api_cache_refresh",
        trigger_condition="api latency > 3000ms",
        action="clear_cache",
        action_params={"pattern": "state:*"},
        cooldown_seconds=900,
        max_attempts=2,
        requires_confirmation=False,
    ),
    RemediationPolicy(
        name="disk_space_log_rotation",
        trigger_condition="log entries > 10000",
        action="rotate_logs",
        action_params={},
        cooldown_seconds=3600,
        max_attempts=1,
        requires_confirmation=False,
    ),
]


# ─── Auto Remediator ─────────────────────────────────────────────────────────

class AutoRemediator:
    """
    Semi-autonomous remediation engine for MATE-Ops Phase 2.

    Evaluates observations against a set of :class:`RemediationPolicy`
    objects and executes approved actions through the agent's
    :class:`PermissionGate`, respecting cooldowns, max-attempt ceilings,
    and confirmation requirements.

    Usage::

        agent = MATEOpsAgent(authority_level=AuthorityLevel.SAFE_OPS)
        remediator = AutoRemediator(agent=agent)

        observations = await agent.observe()
        analysis = await agent.analyze(observations)

        actions = remediator.evaluate(observations, analysis)
        records = await remediator.execute_remediations(actions)
    """

    # Class-level constant so it can be referenced without an instance
    DEFAULT_POLICIES: List[RemediationPolicy] = DEFAULT_POLICIES

    def __init__(
        self,
        agent: MATEOpsAgent,
        policies: Optional[List[RemediationPolicy]] = None,
    ) -> None:
        """
        Initialise the auto-remediator.

        Args:
            agent:    A :class:`MATEOpsAgent` instance whose permission gate
                      and action handlers will be used for execution.
            policies: Optional list of policies.  If ``None``, the
                      :data:`DEFAULT_POLICIES` are loaded.
        """
        self._agent = agent
        self._policies: List[RemediationPolicy] = list(
            policies if policies is not None else DEFAULT_POLICIES
        )
        # Execution history — append-only, never mutated after insertion
        self._history: List[RemediationRecord] = []
        # Pending confirmations — actions awaiting human approval
        self._pending_confirmations: List[RemediationAction] = []
        # Per-policy tracking: {policy_name: {"last_executed": float|None, "attempts_24h": list[float]}}
        self._policy_state: Dict[str, Dict[str, Any]] = {
            p.name: {"last_executed": None, "attempts_24h": []}
            for p in self._policies
        }

    # ── Policy Management ─────────────────────────────────────────────────────

    def add_policy(self, policy: RemediationPolicy) -> None:
        """
        Register a new remediation policy.

        If a policy with the same name already exists, a warning is logged
        and the duplicate is ignored.

        Args:
            policy: The :class:`RemediationPolicy` to add.
        """
        if policy.name in self._policy_state:
            log.warning(
                "auto_remediator_duplicate_policy",
                policy_name=policy.name,
                message="Policy with this name already exists; ignoring duplicate.",
            )
            return

        self._policies.append(policy)
        self._policy_state[policy.name] = {
            "last_executed": None,
            "attempts_24h": [],
        }
        log.info(
            "auto_remediator_policy_added",
            policy_name=policy.name,
            action=policy.action,
            cooldown_seconds=policy.cooldown_seconds,
            max_attempts=policy.max_attempts,
            requires_confirmation=policy.requires_confirmation,
        )

    # ── Evaluation ────────────────────────────────────────────────────────────

    def evaluate(
        self,
        observations: List[Observation],
        analysis: str,
    ) -> List[RemediationAction]:
        """
        Evaluate observations against all policies and return proposed actions.

        For each policy, the trigger condition is checked against the
        observation data.  If the condition matches and all safety
        constraints (cooldown, max-attempts) are satisfied, a
        :class:`RemediationAction` is produced.

        The returned actions have **not** been executed yet — call
        :meth:`execute_remediations` to carry them out.

        Args:
            observations: Current telemetry observations from the observer.
            analysis:     Analysis text from the MATE-Ops agent (Stage 2).

        Returns:
            A list of :class:`RemediationAction` instances to potentially
            execute.  The list may be empty if no policies match or all
            are suppressed by safety constraints.
        """
        proposed: List[RemediationAction] = []

        for policy in self._policies:
            if not self._trigger_matches(policy, observations, analysis):
                continue

            # ── Cooldown check ────────────────────────────────────────────
            if not self._check_cooldown(policy):
                log.info(
                    "auto_remediator_cooldown_active",
                    policy_name=policy.name,
                    message="Policy skipped — cooldown window has not elapsed.",
                )
                continue

            # ── Max-attempts check ────────────────────────────────────────
            if not self._check_max_attempts(policy):
                log.warning(
                    "auto_remediator_max_attempts_exceeded",
                    policy_name=policy.name,
                    max_attempts=policy.max_attempts,
                    message="Policy skipped — max attempts within 24h exceeded.",
                )
                continue

            # Build the action
            urgency = self._assess_urgency(policy, observations)
            impact = self._assess_blast_radius(policy)
            reason = (
                f"Policy '{policy.name}' triggered: {policy.trigger_condition}"
            )

            action = RemediationAction(
                policy_name=policy.name,
                action=policy.action,
                params=dict(policy.action_params),
                reason=reason,
                urgency=urgency,
                estimated_impact=impact,
            )
            proposed.append(action)

            log.info(
                "auto_remediator_action_proposed",
                policy_name=policy.name,
                action=policy.action,
                urgency=urgency,
                estimated_impact=impact,
            )

        return proposed

    # ── Execution ─────────────────────────────────────────────────────────────

    async def execute_remediations(
        self,
        actions: List[RemediationAction],
    ) -> List[RemediationRecord]:
        """
        Execute each proposed remediation action with full safety enforcement.

        For every :class:`RemediationAction` the following checks are applied
        in order:

          1. **Permission gate** — the agent's :class:`PermissionGate` must
             approve the action.
          2. **Confirmation gate** — if the originating policy has
             ``requires_confirmation=True``, the action is queued for human
             review instead of being executed.
          3. **Blast-radius logging** — the estimated impact is logged
             before execution.
          4. **Execution** — the action is dispatched through the agent's
             action handler.

        Args:
            actions: List of :class:`RemediationAction` instances, typically
                     produced by :meth:`evaluate`.

        Returns:
            A list of :class:`RemediationRecord` instances — one per action,
            documenting the outcome.
        """
        records: List[RemediationRecord] = []

        for action in actions:
            triggered_at = datetime.now(timezone.utc).isoformat()

            # Snapshot observations for audit
            obs_snapshot = self._snapshot_observations(action)

            # ── 1. Permission gate ────────────────────────────────────────
            gate: PermissionGate = self._agent.permission_gate
            if not gate.validate(action.action):
                record = RemediationRecord(
                    policy_name=action.policy_name,
                    action=action.action,
                    triggered_at=triggered_at,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    status="denied",
                    result={"reason": "Permission gate denied the action"},
                    observations_snapshot=obs_snapshot,
                )
                self._history.append(record)
                log.warning(
                    "auto_remediator_action_denied",
                    policy_name=action.policy_name,
                    action=action.action,
                    reason="permission_gate_denied",
                )
                records.append(record)
                continue

            # ── 2. Confirmation gate ──────────────────────────────────────
            policy = self._find_policy(action.policy_name)
            if policy is not None and policy.requires_confirmation:
                self._pending_confirmations.append(action)
                record = RemediationRecord(
                    policy_name=action.policy_name,
                    action=action.action,
                    triggered_at=triggered_at,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    status="skipped",
                    result={
                        "reason": "Requires human confirmation",
                        "pending": True,
                    },
                    observations_snapshot=obs_snapshot,
                )
                self._history.append(record)
                log.info(
                    "auto_remediator_action_pending_confirmation",
                    policy_name=action.policy_name,
                    action=action.action,
                    message="Action queued for human review; not auto-executed.",
                )
                records.append(record)
                continue

            # ── 3. Blast-radius assessment ────────────────────────────────
            log.info(
                "auto_remediator_blast_radius_assessment",
                policy_name=action.policy_name,
                action=action.action,
                urgency=action.urgency,
                estimated_impact=action.estimated_impact,
                params=action.params,
            )

            # ── 4. Execute ────────────────────────────────────────────────
            try:
                result = await self._agent._execute_action(
                    action.action, action.params
                )

                # Update per-policy tracking
                now = time.monotonic()
                state = self._policy_state.get(action.policy_name)
                if state is not None:
                    state["last_executed"] = now
                    state["attempts_24h"].append(now)
                    self._prune_attempts_24h(state)

                record = RemediationRecord(
                    policy_name=action.policy_name,
                    action=action.action,
                    triggered_at=triggered_at,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    status="success",
                    result=result,
                    observations_snapshot=obs_snapshot,
                )
                log.info(
                    "auto_remediator_action_success",
                    policy_name=action.policy_name,
                    action=action.action,
                )

            except Exception as exc:
                # Record the failure but don't re-raise — other actions
                # in the batch should still be attempted.
                now = time.monotonic()
                state = self._policy_state.get(action.policy_name)
                if state is not None:
                    state["last_executed"] = now
                    state["attempts_24h"].append(now)
                    self._prune_attempts_24h(state)

                record = RemediationRecord(
                    policy_name=action.policy_name,
                    action=action.action,
                    triggered_at=triggered_at,
                    completed_at=datetime.now(timezone.utc).isoformat(),
                    status="failed",
                    result={"error": str(exc)},
                    observations_snapshot=obs_snapshot,
                )
                log.error(
                    "auto_remediator_action_failed",
                    policy_name=action.policy_name,
                    action=action.action,
                    error=str(exc),
                )

            self._history.append(record)
            records.append(record)

        return records

    # ── History & Status ──────────────────────────────────────────────────────

    def get_history(self) -> List[RemediationRecord]:
        """
        Return all past remediation records.

        The list is ordered chronologically (oldest first) and is a
        shallow copy — callers cannot mutate the internal history.

        Returns:
            A list of :class:`RemediationRecord` instances.
        """
        return list(self._history)

    def get_policy_status(self) -> List[dict]:
        """
        Return the operational status of every registered policy.

        Each entry includes:
          - ``name`` — policy name
          - ``action`` — the action the policy triggers
          - ``last_execution_time`` — ISO 8601 or ``None``
          - ``attempt_count_24h`` — number of attempts in the last 24 hours
          - ``cooldown_remaining_seconds`` — seconds until cooldown expires
          - ``requires_confirmation`` — whether human review is needed

        Returns:
            A list of status dictionaries, one per policy.
        """
        statuses: List[dict] = []
        now_mono = time.monotonic()

        for policy in self._policies:
            state = self._policy_state.get(policy.name, {})
            last_executed = state.get("last_executed")
            attempts_24h: List[float] = state.get("attempts_24h", [])
            self._prune_attempts_24h(state)  # ensure up-to-date

            cooldown_remaining = 0
            if last_executed is not None:
                elapsed = now_mono - last_executed
                cooldown_remaining = max(0, policy.cooldown_seconds - elapsed)

            last_execution_iso: Optional[str] = None
            if last_executed is not None:
                # Approximate: we don't store wall-clock time per policy
                # so derive it from monotonic delta
                try:
                    delta = now_mono - last_executed
                    dt = datetime.now(timezone.utc) - __import__("datetime").timedelta(
                        seconds=delta
                    )
                    last_execution_iso = dt.isoformat()
                except Exception:
                    last_execution_iso = None

            statuses.append({
                "name": policy.name,
                "action": policy.action,
                "last_execution_time": last_execution_iso,
                "attempt_count_24h": len(attempts_24h),
                "cooldown_remaining_seconds": round(cooldown_remaining, 1),
                "requires_confirmation": policy.requires_confirmation,
            })

        return statuses

    # ── Pending Confirmations ─────────────────────────────────────────────────

    @property
    def pending_confirmations(self) -> List[RemediationAction]:
        """
        Actions that require human confirmation before execution.

        These are actions produced by policies with
        ``requires_confirmation=True``.  They are logged but not
        auto-executed.  An operator or external system can review
        and approve them separately.
        """
        return list(self._pending_confirmations)

    def clear_pending_confirmation(self, policy_name: str) -> bool:
        """
        Remove a pending confirmation by policy name.

        Returns ``True`` if a matching pending action was found and
        removed, ``False`` otherwise.
        """
        for i, action in enumerate(self._pending_confirmations):
            if action.policy_name == policy_name:
                self._pending_confirmations.pop(i)
                log.info(
                    "auto_remediator_pending_cleared",
                    policy_name=policy_name,
                )
                return True
        return False

    # ── Private: Trigger Matching ─────────────────────────────────────────────

    @staticmethod
    def _trigger_matches(
        policy: RemediationPolicy,
        observations: List[Observation],
        analysis: str,
    ) -> bool:
        """
        Determine whether a policy's trigger condition matches the
        current observations and analysis.

        Uses rule-based heuristics keyed on the policy name to
        evaluate the trigger.  This is intentionally conservative —
        when in doubt, the trigger does NOT match, reducing false
        positives.

        Args:
            policy:       The policy whose trigger is being tested.
            observations: Current telemetry observations.
            analysis:     LLM or rule-based analysis text.

        Returns:
            ``True`` if the trigger condition is satisfied.
        """
        name = policy.name
        trigger = policy.trigger_condition.lower()

        # ── stale_cache_clear: redis latency > 500ms ─────────────────────
        if name == "stale_cache_clear" or "redis latency" in trigger:
            for obs in observations:
                if obs.source == "redis" and obs.status in ("warn", "error"):
                    latency = obs.details.get("latency_ms", 0)
                    try:
                        if float(latency) > 500:
                            return True
                    except (TypeError, ValueError):
                        pass
            return False

        # ── degraded_service_restart: service status=error for > 15m ─────
        if name == "degraded_service_restart" or (
            "status=error" in trigger and "15 minute" in trigger
        ):
            for obs in observations:
                if obs.status == "error":
                    # Heuristic: check if the error duration is mentioned
                    # in details or if the observation itself signals a
                    # sustained issue
                    duration_s = obs.details.get("duration_s", 0)
                    try:
                        if float(duration_s) > 900:  # 15 minutes
                            return True
                    except (TypeError, ValueError):
                        pass
                    # Also trigger if analysis mentions sustained error
                    if "sustained" in analysis.lower() or "15 min" in analysis.lower():
                        return True
            return False

        # ── high_error_alert: 2+ services in error ───────────────────────
        if name == "high_error_alert" or "2+ services" in trigger:
            error_count = sum(1 for o in observations if o.status == "error")
            return error_count >= 2

        # ── slow_api_cache_refresh: api latency > 3000ms ─────────────────
        if name == "slow_api_cache_refresh" or "api latency" in trigger:
            for obs in observations:
                if obs.source == "api" and obs.status in ("warn", "error"):
                    latency = obs.details.get("latency_ms", 0)
                    try:
                        if float(latency) > 3000:
                            return True
                    except (TypeError, ValueError):
                        pass
            return False

        # ── disk_space_log_rotation: log entries > 10000 ─────────────────
        if name == "disk_space_log_rotation" or "log entries" in trigger:
            for obs in observations:
                log_count = obs.details.get("log_entries", 0)
                try:
                    if int(log_count) > 10000:
                        return True
                except (TypeError, ValueError):
                        pass
            return False

        # ── Generic fallback ─────────────────────────────────────────────
        # For custom policies, perform a best-effort match by looking for
        # keywords from the trigger condition in observation data.
        # This is intentionally conservative.
        if "error" in trigger:
            return any(o.status == "error" for o in observations)
        if "warn" in trigger:
            return any(o.status in ("warn", "error") for o in observations)
        if "latency" in trigger:
            for obs in observations:
                latency = obs.details.get("latency_ms", 0)
                try:
                    if float(latency) > 1000:
                        return True
                except (TypeError, ValueError):
                    pass

        return False

    # ── Private: Safety Checks ────────────────────────────────────────────────

    def _check_cooldown(self, policy: RemediationPolicy) -> bool:
        """
        Return ``True`` if the policy's cooldown has elapsed.

        A policy whose ``last_executed`` timestamp is within
        ``cooldown_seconds`` of the current time is suppressed.
        """
        state = self._policy_state.get(policy.name)
        if state is None:
            return True

        last_executed = state.get("last_executed")
        if last_executed is None:
            return True

        elapsed = time.monotonic() - last_executed
        return elapsed >= policy.cooldown_seconds

    def _check_max_attempts(self, policy: RemediationPolicy) -> bool:
        """
        Return ``True`` if the policy has not exceeded its 24-hour max attempts.

        Attempts older than 24 hours are pruned before counting.
        """
        state = self._policy_state.get(policy.name)
        if state is None:
            return True

        self._prune_attempts_24h(state)
        attempts = state.get("attempts_24h", [])
        return len(attempts) < policy.max_attempts

    @staticmethod
    def _prune_attempts_24h(state: Dict[str, Any]) -> None:
        """
        Remove attempt timestamps older than 24 hours from the state.

        Operates in-place on the ``attempts_24h`` list.
        """
        cutoff = time.monotonic() - 86400  # 24 hours ago
        attempts: List[float] = state.get("attempts_24h", [])
        state["attempts_24h"] = [t for t in attempts if t > cutoff]

    # ── Private: Assessment Helpers ───────────────────────────────────────────

    @staticmethod
    def _assess_urgency(
        policy: RemediationPolicy,
        observations: List[Observation],
    ) -> str:
        """
        Heuristically assess the urgency of a triggered policy.

        Returns one of ``low``, ``medium``, ``high``, ``critical``.
        """
        error_count = sum(1 for o in observations if o.status == "error")

        if error_count >= 3:
            return "critical"
        if error_count >= 2:
            return "high"
        if error_count >= 1:
            return "medium"

        # Policy-specific urgency adjustments
        if policy.action == "notify_team":
            return "high"
        if policy.action == "restart_service":
            return "medium"

        return "low"

    @staticmethod
    def _assess_blast_radius(policy: RemediationPolicy) -> str:
        """
        Estimate the blast radius of executing a policy's action.

        Returns one of ``none``, ``minimal``, ``moderate``.

        - ``notify_team`` → ``none`` (no side effects on infrastructure)
        - ``clear_cache`` → ``minimal`` (transient cache miss storm)
        - ``restart_service`` → ``moderate`` (brief downtime)
        - ``rotate_logs`` → ``none`` (no impact on running services)
        """
        blast_map: Dict[str, str] = {
            "notify_team": "none",
            "clear_cache": "minimal",
            "restart_service": "moderate",
            "rotate_logs": "none",
        }
        return blast_map.get(policy.action, "minimal")

    # ── Private: Utility ──────────────────────────────────────────────────────

    def _find_policy(self, name: str) -> Optional[RemediationPolicy]:
        """Look up a policy by name.  Returns ``None`` if not found."""
        for p in self._policies:
            if p.name == name:
                return p
        return None

    @staticmethod
    def _snapshot_observations(action: RemediationAction) -> List[Dict[str, Any]]:
        """
        Create a lightweight snapshot of the observations that led to an action.

        Since :class:`RemediationAction` does not carry observations directly,
        we store minimal metadata from the action itself.  In a future phase,
        observations can be attached to the action for richer auditing.
        """
        return [
            {
                "policy_name": action.policy_name,
                "action": action.action,
                "reason": action.reason,
                "urgency": action.urgency,
                "estimated_impact": action.estimated_impact,
                "snapshot_time": datetime.now(timezone.utc).isoformat(),
            }
        ]
