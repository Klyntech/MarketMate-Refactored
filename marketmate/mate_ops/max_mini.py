"""
marketmate/mate_ops/max_mini.py
───────────────────────────────
Max & Mini optimization analysis for MATE-Ops.

Documents what to MAXIMIZE and what to MINIMIZE in the
MATE-Ops autonomous infrastructure intelligence system.

MAXIMIZE:
  - Observation Coverage
  - Anomaly Detection Sensitivity
  - Self-Healing Capability
  - Audit Trail Completeness
  - Fallback Resilience
  - Memory Depth
  - Alert Richness
  - Schedule Coverage

MINIMIZE:
  - Attack Surface
  - Latency Overhead
  - Resource Consumption
  - False Positive Rate
  - Privilege Escalation Risk
  - Data Exposure
  - Blast Radius
  - Complexity
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List

from marketmate.core.logger import get_logger

log = get_logger("mate_ops.max_mini")


# ─── Data Classes ──────────────────────────────────────────────────────────────

@dataclass
class OptimizationItem:
    """A single optimization target (maximize or minimize)."""

    name: str
    description: str
    current_score: int  # 1-10
    target_score: int   # 1-10
    strategy: str
    priority: str  # "critical", "high", "medium", "low"


@dataclass
class MaxMiniSection:
    """A section of the Max/Mini analysis (either MAXIMIZE or MINIMIZE)."""

    direction: str  # "MAXIMIZE" or "MINIMIZE"
    items: List[OptimizationItem] = field(default_factory=list)


@dataclass
class MaxMiniReport:
    """Complete Max/Mini optimization analysis report."""

    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    maximize_section: MaxMiniSection = field(
        default_factory=lambda: MaxMiniSection(direction="MAXIMIZE")
    )
    minimize_section: MaxMiniSection = field(
        default_factory=lambda: MaxMiniSection(direction="MINIMIZE")
    )
    overall_health_score: float = 0.0
    critical_gaps: int = 0
    recommendations: List[str] = field(default_factory=list)


# ─── Max & Mini Analysis ──────────────────────────────────────────────────────

class MaxMiniAnalysis:
    """
    Analyzes and documents what to MAXIMIZE and MINIMIZE in MATE-Ops.

    For each optimization target, provides:
      - Current score (1-10)
      - Target score (1-10)
      - Implementation strategy
      - Priority level

    Generates a MaxMiniReport with all findings and an overall
    health score for the MATE-Ops system.
    """

    def __init__(self) -> None:
        """Initialize the Max/Mini analysis."""
        self._report = MaxMiniReport()

    # ── Main Runner ──────────────────────────────────────────────────────────

    def analyze(self) -> MaxMiniReport:
        """
        Run the full Max/Mini analysis and return the report.

        Evaluates all MAXIMIZE and MINIMIZE items, computes the
        overall health score, identifies critical gaps, and
        generates actionable recommendations.
        """
        log.info("mate_ops_max_mini_analysis_start")

        self._report.maximize_section = self._build_maximize_section()
        self._report.minimize_section = self._build_minimize_section()
        self._report.overall_health_score = self._compute_health_score()
        self._report.critical_gaps = self._count_critical_gaps()
        self._report.recommendations = self._generate_recommendations()

        self._print_report()

        log.info(
            "mate_ops_max_mini_analysis_complete",
            health_score=round(self._report.overall_health_score, 1),
            critical_gaps=self._report.critical_gaps,
        )

        return self._report

    # ── MAXIMIZE Section ─────────────────────────────────────────────────────

    @staticmethod
    def _build_maximize_section() -> MaxMiniSection:
        """
        Build the MAXIMIZE section with 8 optimization items.

        These are the capabilities we want to increase in MATE-Ops.
        Higher scores are better for MAXIMIZE items.
        """
        items: List[OptimizationItem] = [
            OptimizationItem(
                name="Observation Coverage",
                description=(
                    "All 6 service checks running: API, Ollama, Redis, "
                    "MongoDB, Telegram, Prometheus.  Full coverage ensures "
                    "no blind spots in infrastructure monitoring."
                ),
                current_score=7,
                target_score=10,
                strategy=(
                    "Add database replication lag check, CDN health check, "
                    "SSL certificate expiry check, and DNS resolution time.  "
                    "Implement custom health check plugins for domain-specific "
                    "monitoring (e.g., signal freshness, portfolio accuracy)."
                ),
                priority="high",
            ),
            OptimizationItem(
                name="Anomaly Detection Sensitivity",
                description=(
                    "How early can we detect issues?  Current rule-based "
                    "analysis catches obvious failures but misses subtle "
                    "degradation patterns (gradual latency increase, "
                    "memory leaks, connection pool exhaustion)."
                ),
                current_score=4,
                target_score=9,
                strategy=(
                    "Implement statistical anomaly detection: rolling "
                    "averages, standard deviation thresholds, and trend "
                    "analysis.  When LLM is available, use it for pattern "
                    "recognition in time-series metrics.  Add baseline "
                    "learning during healthy periods."
                ),
                priority="critical",
            ),
            OptimizationItem(
                name="Self-Healing Capability",
                description=(
                    "What can Phase 1 safely auto-remediate?  Currently "
                    "limited to Level 1 actions (restart, clear cache, "
                    "notify).  Need to expand the set of safe automated "
                    "responses."
                ),
                current_score=3,
                target_score=8,
                strategy=(
                    "Phase 1: Implement auto-restart for crashed workers, "
                    "auto-cache-clear for stale state, auto-log-rotation.  "
                    "Phase 2: Add circuit breaker pattern, graceful "
                    "degradation, and load shedding.  Phase 3: Add "
                    "predictive remediation based on trend analysis."
                ),
                priority="high",
            ),
            OptimizationItem(
                name="Audit Trail Completeness",
                description=(
                    "Every decision logged with reason.  Currently logs "
                    "permission decisions and pipeline stages, but missing "
                    "some granular data (why an action was chosen, what "
                    "alternatives were considered)."
                ),
                current_score=6,
                target_score=10,
                strategy=(
                    "Add structured logging for every pipeline stage with: "
                    "input state, reasoning, output state, alternatives.  "
                    "Implement log aggregation with searchable index.  "
                    "Add correlation IDs linking observations to actions "
                    "to outcomes."
                ),
                priority="high",
            ),
            OptimizationItem(
                name="Fallback Resilience",
                description=(
                    "Rule-based fallback when LLM is unavailable.  "
                    "Currently implemented for analyze and plan stages, "
                    "but could be more comprehensive."
                ),
                current_score=6,
                target_score=9,
                strategy=(
                    "Expand rule-based fallback to cover more scenarios: "
                    "cascading failures, partial degradation, slow recovery.  "
                    "Implement graduated response: Level 1 fallback → "
                    "Level 2 fallback → minimal safe response.  Add "
                    "caching of LLM responses for similar patterns."
                ),
                priority="high",
            ),
            OptimizationItem(
                name="Memory Depth",
                description=(
                    "How much historical context MATE-Ops can leverage.  "
                    "Currently no persistent memory — each cycle starts "
                    "fresh.  Need to store and query historical observations."
                ),
                current_score=2,
                target_score=8,
                strategy=(
                    "Implement observation history store (MongoDB-backed).  "
                    "Add time-series database for metrics history.  "
                    "Implement pattern matching against past incidents.  "
                    "Build knowledge base of known failure modes and "
                    "successful remediations."
                ),
                priority="critical",
            ),
            OptimizationItem(
                name="Alert Richness",
                description=(
                    "Quality and detail of alert notifications.  Currently "
                    "sends basic text alerts via Telegram.  Need richer "
                    "context, actionable suggestions, and escalation paths."
                ),
                current_score=4,
                target_score=9,
                strategy=(
                    "Enhance alert format: include relevant metrics, "
                    "affected services, recommended actions, and severity "
                    "assessment.  Add interactive buttons for approval/"
                    "denial of proposed actions.  Implement escalation "
                    "tiers: info → warning → critical → phone call."
                ),
                priority="medium",
            ),
            OptimizationItem(
                name="Schedule Coverage",
                description=(
                    "4 monitoring loops (5m/15m/30m/60m).  Currently "
                    "implemented but all loops are running the same "
                    "general pipeline with different intervals."
                ),
                current_score=5,
                target_score=9,
                strategy=(
                    "Specialize each loop: 5m for critical health checks, "
                    "15m for log pattern analysis, 30m for metric trend "
                    "detection, 60m for full diagnostic with LLM analysis.  "
                    "Add on-demand cycles triggered by alerts.  Implement "
                    "adaptive intervals (more frequent during incidents)."
                ),
                priority="medium",
            ),
        ]

        return MaxMiniSection(direction="MAXIMIZE", items=items)

    # ── MINIMIZE Section ─────────────────────────────────────────────────────

    @staticmethod
    def _build_minimize_section() -> MaxMiniSection:
        """
        Build the MINIMIZE section with 8 optimization items.

        These are the risks and costs we want to reduce.
        Lower scores are better for MINIMIZE items (score = how much
        of the thing exists, so lower = better).
        """
        items: List[OptimizationItem] = [
            OptimizationItem(
                name="Attack Surface",
                description=(
                    "Minimize exposed endpoints and permissions.  Currently "
                    "the permission gate restricts actions, but the system "
                    "exposes HTTP clients, Redis connections, and MongoDB "
                    "queries that could be exploited."
                ),
                current_score=5,
                target_score=2,
                strategy=(
                    "Implement network-level isolation for monitoring.  "
                    "Use read-only database connections for observations.  "
                    "Add IP whitelisting for Ollama and Prometheus.  "
                    "Implement mTLS for internal service communication."
                ),
                priority="critical",
            ),
            OptimizationItem(
                name="Latency Overhead",
                description=(
                    "Minimize impact on API performance.  Monitoring "
                    "activities should not degrade user-facing services."
                ),
                current_score=4,
                target_score=2,
                strategy=(
                    "Run all health checks with short timeouts (5-15s).  "
                    "Use connection pooling for repeated checks.  "
                    "Schedule heavy operations (full diagnostics) during "
                    "low-traffic periods.  Implement circuit breakers to "
                    "skip checks when service is known-down."
                ),
                priority="high",
            ),
            OptimizationItem(
                name="Resource Consumption",
                description=(
                    "Minimize CPU/memory usage of monitoring.  The "
                    "MATE-Ops agent should be lightweight and not "
                    "compete with production services for resources."
                ),
                current_score=3,
                target_score=1,
                strategy=(
                    "Limit concurrent health checks to 6.  Cap LLM token "
                    "usage per cycle (1024 tokens).  Use streaming for "
                    "large log reads.  Implement memory limits on "
                    "observation history.  Profile and optimize hot paths."
                ),
                priority="high",
            ),
            OptimizationItem(
                name="False Positive Rate",
                description=(
                    "Minimize unnecessary alerts.  Too many false alarms "
                    "lead to alert fatigue and ignored notifications."
                ),
                current_score=5,
                target_score=2,
                strategy=(
                    "Implement confirmation checks before alerting.  "
                    "Add hysteresis: require N consecutive failures before "
                    "alerting.  Use statistical thresholds instead of "
                    "binary checks.  Add 'known issue' suppression for "
                    "planned maintenance windows."
                ),
                priority="high",
            ),
            OptimizationItem(
                name="Privilege Escalation Risk",
                description=(
                    "Minimize authority levels in normal operation.  "
                    "The default should be READ_ONLY, with escalation "
                    "only when needed and logged."
                ),
                current_score=3,
                target_score=1,
                strategy=(
                    "Default all agents to READ_ONLY authority.  Require "
                    "explicit escalation with time-limited tokens.  "
                    "Auto-deescalate after incident resolution.  Log all "
                    "authority changes with reason and approver."
                ),
                priority="critical",
            ),
            OptimizationItem(
                name="Data Exposure",
                description=(
                    "Minimize sensitive data in logs and responses.  "
                    "Connection strings, API tokens, and internal URLs "
                    "should never appear in external-facing output."
                ),
                current_score=4,
                target_score=1,
                strategy=(
                    "Implement log sanitization: redact tokens, passwords, "
                    "and connection strings.  Use structured logging with "
                    "typed fields (not string interpolation).  Add output "
                    "filtering for Telegram messages.  Audit all log "
                    "statements for sensitive data leakage."
                ),
                priority="critical",
            ),
            OptimizationItem(
                name="Blast Radius",
                description=(
                    "Minimize impact of any single action.  If a remediation "
                    "goes wrong, it should affect the smallest possible "
                    "scope."
                ),
                current_score=4,
                target_score=2,
                strategy=(
                    "Implement canary deployments for restart operations.  "
                    "Use targeted cache clearing (not flushall).  Add "
                    "pre-action validation: check service state before "
                    "acting.  Implement rollback capability for all "
                    "state-changing actions."
                ),
                priority="high",
            ),
            OptimizationItem(
                name="Complexity",
                description=(
                    "Minimize code complexity for auditability.  Simpler "
                    "code is easier to verify, test, and trust."
                ),
                current_score=5,
                target_score=3,
                strategy=(
                    "Maintain single-responsibility per module.  Use "
                    "dataclasses for structured data.  Avoid clever "
                    "abstractions — prefer explicit code.  Keep the "
                    "5-stage pipeline linear and predictable.  Document "
                    "every design decision."
                ),
                priority="medium",
            ),
        ]

        return MaxMiniSection(direction="MINIMIZE", items=items)

    # ── Health Score ─────────────────────────────────────────────────────────

    def _compute_health_score(self) -> float:
        """
        Compute overall MATE-Ops health score (0-100).

        For MAXIMIZE items: higher current_score = better
        For MINIMIZE items: lower current_score = better

        The health score reflects how close the system is to
        its target optimization state.
        """
        maximize = self._report.maximize_section.items
        minimize = self._report.minimize_section.items

        # MAXIMIZE: ratio of current to target (capped at 1.0)
        max_scores = []
        for item in maximize:
            if item.target_score > 0:
                ratio = min(item.current_score / item.target_score, 1.0)
                max_scores.append(ratio)

        # MINIMIZE: ratio of how close to target (lower = better)
        # A current of 5 with target of 2 means we want to reduce by 3
        # Score = 1 - (current - target) / current when current > target
        min_scores = []
        for item in minimize:
            if item.current_score <= item.target_score:
                min_scores.append(1.0)  # Already at or below target
            elif item.current_score > 0:
                # How far from target as a fraction
                excess = item.current_score - item.target_score
                ratio = 1.0 - (excess / 10.0)  # Normalize to 0-1
                min_scores.append(max(ratio, 0.0))

        all_scores = max_scores + min_scores
        if not all_scores:
            return 0.0

        return round(sum(all_scores) / len(all_scores) * 100, 1)

    # ── Critical Gaps ────────────────────────────────────────────────────────

    def _count_critical_gaps(self) -> int:
        """Count items with 'critical' priority where current != target."""
        all_items = (
            self._report.maximize_section.items
            + self._report.minimize_section.items
        )
        return sum(
            1 for item in all_items
            if item.priority == "critical" and item.current_score != item.target_score
        )

    # ── Recommendations ──────────────────────────────────────────────────────

    def _generate_recommendations(self) -> List[str]:
        """Generate prioritized recommendations from the analysis."""
        all_items = (
            self._report.maximize_section.items
            + self._report.minimize_section.items
        )

        # Sort by priority then gap size
        priority_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
        sorted_items = sorted(
            all_items,
            key=lambda x: (priority_order.get(x.priority, 99), abs(x.target_score - x.current_score)),
            reverse=False,  # critical first, then by gap within each priority
        )

        # Actually we want critical first, then largest gap
        sorted_items = sorted(
            all_items,
            key=lambda x: (priority_order.get(x.priority, 99), -abs(x.target_score - x.current_score)),
        )

        recommendations: List[str] = []
        for item in sorted_items[:10]:  # Top 10
            gap = abs(item.target_score - item.current_score)
            direction = "↑" if item in self._report.maximize_section.items else "↓"
            recommendations.append(
                f"[{item.priority.upper()}] {direction} {item.name}: "
                f"score {item.current_score}→{item.target_score} (gap: {gap}). "
                f"{item.strategy.split('.')[0]}."
            )

        return recommendations

    # ── Report Printing ──────────────────────────────────────────────────────

    def _print_report(self) -> None:
        """Print a formatted Max/Mini report to the console."""
        report = self._report
        divider = "═" * 70

        print(f"\n{divider}")
        print("  MATE-Ops Phase 1 — Max & Mini Optimization Analysis")
        print(f"{divider}")
        print(f"  Timestamp        : {report.timestamp}")
        print(f"  Overall Health   : {report.overall_health_score}/100")
        print(f"  Critical Gaps    : {report.critical_gaps}")
        print(f"{divider}")

        # MAXIMIZE section
        print(f"\n  {'─' * 66}")
        print("  MAXIMIZE — Increase These Capabilities")
        print(f"  {'─' * 66}")
        for item in report.maximize_section.items:
            bar_filled = item.current_score
            bar_empty = 10 - item.current_score
            bar = "█" * bar_filled + "░" * bar_empty
            priority_badge = {
                "critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢",
            }.get(item.priority, "⚪")
            print(f"\n  {priority_badge} {item.name} [{item.priority.upper()}]")
            print(f"     Score  : [{bar}] {item.current_score}/10 → target {item.target_score}/10")
            print(f"     Strategy: {item.strategy[:90]}...")

        # MINIMIZE section
        print(f"\n  {'─' * 66}")
        print("  MINIMIZE — Reduce These Risks")
        print(f"  {'─' * 66}")
        for item in report.minimize_section.items:
            bar_filled = item.current_score
            bar_empty = 10 - item.current_score
            bar = "█" * bar_filled + "░" * bar_empty
            priority_badge = {
                "critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🟢",
            }.get(item.priority, "⚪")
            print(f"\n  {priority_badge} {item.name} [{item.priority.upper()}]")
            print(f"     Score  : [{bar}] {item.current_score}/10 → target {item.target_score}/10")
            print(f"     Strategy: {item.strategy[:90]}...")

        # Recommendations
        print(f"\n  {'─' * 66}")
        print("  Top Recommendations")
        print(f"  {'─' * 66}")
        for i, rec in enumerate(report.recommendations, 1):
            print(f"  {i}. {rec[:95]}...")

        print(f"\n{divider}")
        print(f"  Overall Health Score: {report.overall_health_score}/100")
        print(f"{divider}\n")
