"""
marketmate.intelligence.vanta.agent
────────────────────────────────────
VANTA: Truth Validator + System Builder Agent

THE ONLY layer with creation/building capabilities.
Judgment brain — validates correctness of intelligence and builds systems when needed.

TIER SYSTEM (critical safety mechanism):
  Tier 1 (Auto):        Validation, analysis, diagnostics, reporting
  Tier 2 (Auto-safe):   System design, code scaffolds, template generation
  Tier 3 (Human gate):  Actual deployment, data modification, infra changes

CRITICAL: VANTA is a BOUNDED agent. It NEVER directly edits production code,
deploys automatically without Tier 3 approval, freely controls desktop,
or performs unrestricted actions.

Position in pipeline:
  RAW DATA → PRISM → VINNI → ATLAS → [VANTA] → NOVA → Users

Created: 2026-05-29
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from marketmate.core.logger import get_logger

log = get_logger("intelligence.vanta")


# ─── Constants ────────────────────────────────────────────────────────────────

VALID_SEVERITIES = {"ok", "warning", "critical"}
VALID_LAYERS = {"atlas", "nova", "both"}
VALID_ACTIONS = {"proceed", "caution", "halt"}
VALID_RISK_ENVS = {"safe", "caution", "unsafe"}
VALID_BUILD_TYPES = {"system_design", "code_scaffold", "architecture"}
VALID_FEASIBILITY = {"high", "medium", "low"}
VALID_IMPACTS = {"none", "minimal", "moderate", "significant"}

_CONFIDENCE_LOW = 0.3
_CONFIDENCE_CRITICAL = 0.15
_VOLATILITY_UNSAFE_PCT = 5.0
_VOLATILITY_CAUTION_PCT = 3.0
_CONTRADICTION_IMPACT = 0.3
_SIGNAL_DIVERGENCE_IMPACT = 0.2
_MAX_CONSECUTIVE_HALTS = 3
_MAX_BUILD_COMPONENTS = 20
_MAX_BUILD_RISKS = 10


# ─── VantaValidation ─────────────────────────────────────────────────────────

@dataclass
class VantaValidation:
    """
    A single validation result from VANTA.

    Attributes:
        severity: "ok" | "warning" | "critical"
        layer: "atlas" | "nova" | "both"
        issue: Human-readable description of the issue.
        confidence_impact: 0.0-1.0 reduction in confidence.
        recommended_action: "proceed" | "caution" | "halt"
        contradiction_details: Optional dict with specifics of a contradiction.
        timestamp: When this validation was produced.
    """

    severity: str
    layer: str
    issue: str
    confidence_impact: float
    recommended_action: str
    contradiction_details: Optional[Dict] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        self.confidence_impact = max(0.0, min(1.0, self.confidence_impact))
        if self.severity not in VALID_SEVERITIES:
            log.warning("vanta_invalid_severity", severity=self.severity)
            self.severity = "ok"
        if self.recommended_action not in VALID_ACTIONS:
            log.warning("vanta_invalid_action", action=self.recommended_action)
            self.recommended_action = "caution"

    def to_dict(self) -> Dict[str, Any]:
        return {
            "severity": self.severity,
            "layer": self.layer,
            "issue": self.issue,
            "confidence_impact": round(self.confidence_impact, 4),
            "recommended_action": self.recommended_action,
            "contradiction_details": self.contradiction_details,
            "timestamp": self.timestamp,
        }


# ─── VantaBuildPlan ──────────────────────────────────────────────────────────

@dataclass
class VantaBuildPlan:
    """
    A structured build plan created by VANTA.

    Attributes:
        plan_type: "system_design" | "code_scaffold" | "architecture"
        description: What this plan will create.
        feasibility: "high" | "medium" | "low"
        components: List of component dicts describing what will be built.
        risks: List of risk strings.
        requires_approval: Whether human approval is required (True for Tier 3).
        tier: 1, 2, or 3.
        estimated_impact: "none" | "minimal" | "moderate" | "significant"
        rollback_plan: How to undo this plan if something goes wrong.
        timestamp: When this plan was created.
    """

    plan_type: str
    description: str
    feasibility: str
    components: List[Dict]
    risks: List[str]
    requires_approval: bool
    tier: int
    estimated_impact: str
    rollback_plan: str
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def __post_init__(self) -> None:
        if self.tier not in {1, 2, 3}:
            log.warning("vanta_invalid_tier", tier=self.tier)
            self.tier = 2
        if self.tier >= 3:
            self.requires_approval = True
        if self.tier == 1 and self.estimated_impact == "significant":
            log.warning("vanta_tier1_significant_impact")
            self.tier = 2

    def to_dict(self) -> Dict[str, Any]:
        return {
            "plan_type": self.plan_type,
            "description": self.description,
            "feasibility": self.feasibility,
            "components": self.components,
            "risks": self.risks,
            "requires_approval": self.requires_approval,
            "tier": self.tier,
            "estimated_impact": self.estimated_impact,
            "rollback_plan": self.rollback_plan,
            "timestamp": self.timestamp,
        }


# ─── VantaAgent ──────────────────────────────────────────────────────────────

class VantaAgent:
    """
    VANTA: Truth Validator + System Builder Agent.

    THE ONLY layer with creation/building capabilities. Sits between
    ATLAS and NOVA, cross-checking outputs, scoring confidence, flagging
    unsafe conditions, and building systems within tier boundaries.

    TIER SYSTEM:
      Tier 1 (Auto):        Validation, analysis, diagnostics, reporting
      Tier 2 (Auto-safe):   System design, code scaffolds, templates
      Tier 3 (Human gate):  Deployment, data modification, infra changes

    VANTA is BOUNDED — never edits production code, never auto-deploys,
    never controls desktop, never overrides PRISM flags.
    """

    def __init__(
        self,
        confidence_low_threshold: float = _CONFIDENCE_LOW,
        confidence_critical_threshold: float = _CONFIDENCE_CRITICAL,
        volatility_unsafe_pct: float = _VOLATILITY_UNSAFE_PCT,
        volatility_caution_pct: float = _VOLATILITY_CAUTION_PCT,
        max_consecutive_halts: int = _MAX_CONSECUTIVE_HALTS,
    ) -> None:
        self._confidence_low = confidence_low_threshold
        self._confidence_critical = confidence_critical_threshold
        self._volatility_unsafe = volatility_unsafe_pct
        self._volatility_caution = volatility_caution_pct
        self._max_consecutive_halts = max_consecutive_halts

        self._total_validations = 0
        self._halt_count = 0
        self._consecutive_halts = 0
        self._last_halt_time = ""
        self._recent_validations: List[VantaValidation] = []
        self._build_plans: List[VantaBuildPlan] = []
        self._pending_approvals: Dict[str, VantaBuildPlan] = {}

        log.info(
            "vanta_initialized",
            confidence_low=confidence_low_threshold,
            confidence_critical=confidence_critical_threshold,
            volatility_unsafe=volatility_unsafe_pct,
            volatility_caution=volatility_caution_pct,
        )

    # ── Core: Validate Intelligence ─────────────────────────────────────────

    def validate_intelligence(
        self,
        atlas_analysis: Optional[Dict],
        nova_summary: Optional[Dict],
        prism_flags: Optional[List[Any]] = None,
    ) -> List[VantaValidation]:
        """
        Perform full validation across all intelligence layers.

        Cross-checks ATLAS vs NOVA for contradictions, validates confidence,
        assesses PRISM flag impact, and detects logic anomalies.

        Args:
            atlas_analysis: Dict from ATLAS engine (may be None).
            nova_summary: Dict from NOVA layer (may be None).
            prism_flags: PRISM validation results affecting confidence.

        Returns:
            List of VantaValidation objects covering all checks.
        """
        validations: List[VantaValidation] = []
        if prism_flags is None:
            prism_flags = []

        if atlas_analysis and nova_summary:
            validations.append(self.check_atlas_nova_consistency(atlas_analysis, nova_summary))

        if atlas_analysis:
            validations.append(self.validate_confidence(atlas_analysis))
            validations.extend(self._detect_logic_anomalies(atlas_analysis))

        if nova_summary:
            validations.append(self._validate_nova_output(nova_summary))

        prism_val = self._assess_prism_impact(prism_flags)
        if prism_val:
            validations.append(prism_val)

        for v in validations:
            self._record(v)

        log.info(
            "vanta_intelligence_validated",
            count=len(validations),
            critical=sum(1 for v in validations if v.severity == "critical"),
            warning=sum(1 for v in validations if v.severity == "warning"),
        )
        return validations

    # ── Cross-check: ATLAS vs NOVA Consistency ──────────────────────────────

    def check_atlas_nova_consistency(self, atlas: Dict, nova: Dict) -> VantaValidation:
        """
        Cross-check ATLAS analysis against NOVA summary for contradictions.

        Checks regime consistency, direction alignment, and confidence vs quality.

        Args:
            atlas: ATLAS analysis dict.
            nova: NOVA summary dict.

        Returns:
            VantaValidation describing any contradiction found.
        """
        contradictions: Dict[str, Any] = {}
        severity = "ok"
        impact = 0.0
        issue = "ATLAS and NOVA outputs are consistent"
        action = "proceed"

        # Regime consistency
        atlas_regime = atlas.get("regime", "")
        nova_regime = nova.get("regime", "")
        if atlas_regime and nova_regime and atlas_regime != nova_regime:
            critical_pairs = {("trend", "volatile"), ("volatile", "trend"),
                             ("range", "volatile"), ("volatile", "range")}
            if (atlas_regime, nova_regime) in critical_pairs:
                severity, impact, action = "critical", _CONTRADICTION_IMPACT, "halt"
            else:
                severity, impact, action = "warning", _CONTRADICTION_IMPACT * 0.5, "caution"
            issue = f"Regime contradiction: ATLAS={atlas_regime}, NOVA={nova_regime}"
            contradictions["regime"] = {"atlas": atlas_regime, "nova": nova_regime}

        # Direction alignment
        atlas_structure = atlas.get("structure", "")
        nova_movement = nova.get("movement", "")
        if atlas_structure and nova_movement and self._direction_conflict(atlas_structure, nova_movement):
            if severity == "ok":
                severity, impact, action = "warning", _CONTRADICTION_IMPACT * 0.3, "caution"
                issue = f"Direction conflict: structure={atlas_structure}, movement={nova_movement}"
            contradictions["direction"] = {"atlas_structure": atlas_structure, "nova_movement": nova_movement}

        # Confidence vs quality mismatch
        atlas_conf = float(atlas.get("confidence", 1.0))
        nova_quality = nova.get("data_quality", "verified")
        if atlas_conf > 0.7 and nova_quality in ("degraded", "unreliable"):
            if severity != "critical":
                severity = "warning"
            impact += 0.15
            contradictions["conf_vs_quality"] = {"atlas_confidence": atlas_conf, "nova_quality": nova_quality}
            if action == "proceed":
                action = "caution"

        return VantaValidation(
            severity=severity, layer="both", issue=issue,
            confidence_impact=min(1.0, impact), recommended_action=action,
            contradiction_details=contradictions if contradictions else None,
        )

    # ── Validate Confidence ─────────────────────────────────────────────────

    def validate_confidence(self, atlas_analysis: Dict) -> VantaValidation:
        """
        Validate ATLAS confidence score for reliability.

        Checks confidence threshold, conviction coherence, and data quality penalty.

        Args:
            atlas_analysis: ATLAS output with confidence and conviction fields.

        Returns:
            VantaValidation describing the confidence assessment.
        """
        confidence = float(atlas_analysis.get("confidence", 0.0))
        conviction = int(atlas_analysis.get("conviction", 0))
        quality_flags = atlas_analysis.get("data_quality_flags", [])

        if confidence < self._confidence_critical:
            severity, action, impact = "critical", "halt", 0.5
            issue = f"ATLAS confidence critically low: {confidence:.3f}"
        elif confidence < self._confidence_low:
            severity, action, impact = "warning", "caution", 0.2
            issue = f"ATLAS confidence below acceptable: {confidence:.3f}"
        else:
            severity, action, impact = "ok", "proceed", 0.0
            issue = f"ATLAS confidence acceptable: {confidence:.3f}"

        # Confidence-conviction coherence
        divergence = abs(confidence - conviction / 100.0)
        if divergence > 0.3 and severity != "critical":
            if severity == "ok":
                severity, action = "warning", "caution"
            impact += 0.1
            issue += f" | Confidence-conviction divergence: {divergence:.3f}"

        # Data quality penalty
        if quality_flags:
            impact += min(0.2, len(quality_flags) * 0.05)
            if severity == "ok" and len(quality_flags) > 1:
                severity, action = "warning", "caution"

        return VantaValidation(
            severity=severity, layer="atlas", issue=issue,
            confidence_impact=min(1.0, impact), recommended_action=action,
        )

    # ── Risk Environment Classification ─────────────────────────────────────

    def classify_risk_environment(self, market_data: Dict, atlas_analysis: Dict) -> str:
        """
        Classify current risk environment as safe/caution/unsafe.

        Combines market volatility with ATLAS confidence and regime.

        Args:
            market_data: Dict with price, change_24h, high_24h, low_24h.
            atlas_analysis: ATLAS output with regime, confidence, structure.

        Returns:
            One of: "safe", "caution", "unsafe"
        """
        risk_score = 0.0

        # Volatility
        change_pct = abs(float(market_data.get("change_24h", 0.0)))
        high = float(market_data.get("high_24h", 0.0))
        low = float(market_data.get("low_24h", 0.0))
        mid = (high + low) / 2
        range_pct = ((high - low) / mid * 100) if mid > 0 else 0.0

        if change_pct > self._volatility_unsafe or range_pct > self._volatility_unsafe * 2:
            risk_score += 0.4
        elif change_pct > self._volatility_caution or range_pct > self._volatility_caution * 2:
            risk_score += 0.2

        # Regime risk
        regime = atlas_analysis.get("regime", "unknown")
        risk_score += {"volatile": 0.3, "transition": 0.15, "range": 0.05, "trend": 0.05}.get(regime, 0.2)

        # Confidence risk
        confidence = float(atlas_analysis.get("confidence", 0.5))
        if confidence < self._confidence_critical:
            risk_score += 0.3
        elif confidence < self._confidence_low:
            risk_score += 0.15

        # Structure risk
        if atlas_analysis.get("structure") == "undefined":
            risk_score += 0.1

        # Timeframe alignment risk
        if atlas_analysis.get("timeframe_alignment") == "conflicting":
            risk_score += 0.15
        elif atlas_analysis.get("timeframe_alignment") == "mixed":
            risk_score += 0.05

        if risk_score >= 0.6:
            env = "unsafe"
        elif risk_score >= 0.3:
            env = "caution"
        else:
            env = "safe"

        log.info("vanta_risk_classified", risk_env=env, risk_score=round(risk_score, 4), regime=regime)
        return env

    # ── Should Halt Trading ─────────────────────────────────────────────────

    def should_halt_trading(self, validations: List[VantaValidation], risk_env: str) -> bool:
        """
        Determine whether trading should be halted.

        Halt conditions: unsafe environment, critical halt validations,
        3+ warnings, or consecutive halt limit exceeded.

        Args:
            validations: List of VantaValidation objects.
            risk_env: Current risk environment classification.

        Returns:
            True if trading should be halted.
        """
        if risk_env == "unsafe":
            log.warning("vanta_halt", reason="unsafe_risk_environment")
            return True

        if any(v.severity == "critical" and v.recommended_action == "halt" for v in validations):
            log.warning("vanta_halt", reason="critical_validation_halt")
            return True

        if sum(1 for v in validations if v.severity == "warning") >= 3:
            log.warning("vanta_halt", reason="multiple_warnings")
            return True

        if self._consecutive_halts >= self._max_consecutive_halts:
            log.warning("vanta_halt", reason="consecutive_halt_limit")
            return True

        return False

    # ── Create Build Plan ───────────────────────────────────────────────────

    def create_build_plan(self, requirement: str, tier: int = 2) -> VantaBuildPlan:
        """
        Create a structured build plan for a given requirement.

        VANTA is the ONLY layer with creation/building capabilities.
        Plans are bounded by the tier system:
          Tier 1: Auto — validation, analysis, diagnostics
          Tier 2: Auto-safe — system design, code scaffolds, templates
          Tier 3: Human approval REQUIRED — deployment, data mod, infra

        Args:
            requirement: Natural language description of what needs to be built.
            tier: Build tier (1, 2, or 3). Default is 2.

        Returns:
            VantaBuildPlan with components, risks, and approval gates.
        """
        if tier not in {1, 2, 3}:
            log.warning("vanta_invalid_build_tier", requested=tier)
            tier = 2

        plan_type = self._infer_plan_type(requirement)
        feasibility = self._assess_feasibility(requirement, tier)
        components = self._generate_components(requirement, plan_type, tier)
        risks = self._identify_risks(requirement, tier)
        impact = self._estimate_impact(tier, plan_type)
        rollback = self._build_rollback(plan_type, tier)

        plan = VantaBuildPlan(
            plan_type=plan_type, description=requirement,
            feasibility=feasibility, components=components[:_MAX_BUILD_COMPONENTS],
            risks=risks[:_MAX_BUILD_RISKS], requires_approval=tier >= 3,
            tier=tier, estimated_impact=impact, rollback_plan=rollback,
        )

        self._build_plans.append(plan)
        if len(self._build_plans) > 100:
            self._build_plans = self._build_plans[-100:]

        if plan.requires_approval:
            plan_id = f"plan_{len(self._build_plans)}_{plan.timestamp}"
            self._pending_approvals[plan_id] = plan

        log.info("vanta_build_plan_created", plan_type=plan_type, tier=tier,
                 feasibility=feasibility, requires_approval=plan.requires_approval)
        return plan

    # ── Validate Build Plan ─────────────────────────────────────────────────

    def validate_build_plan(self, plan: VantaBuildPlan) -> VantaValidation:
        """
        Validate a build plan before execution.

        Checks tier boundary compliance, component count, risk assessment,
        rollback adequacy, and approval gate enforcement.

        Args:
            plan: The VantaBuildPlan to validate.

        Returns:
            VantaValidation describing the build plan assessment.
        """
        issues: List[str] = []
        severity, impact = "ok", 0.0

        if plan.tier >= 3 and not plan.requires_approval:
            issues.append("Tier 3 plan missing approval gate — BOUNDARY VIOLATION")
            severity, impact = "critical", 0.5

        if len(plan.components) > _MAX_BUILD_COMPONENTS:
            issues.append(f"Too many components: {len(plan.components)}")
            if severity != "critical":
                severity = "warning"
            impact += 0.1

        if not plan.risks:
            issues.append("No risks identified — assessment incomplete")
            if severity == "ok":
                severity = "warning"
            impact += 0.1

        if not plan.rollback_plan or not plan.rollback_plan.strip():
            issues.append("No rollback plan — cannot safely undo")
            if severity != "critical":
                severity = "warning"
            impact += 0.15

        if plan.feasibility == "low" and plan.tier >= 3:
            issues.append("Low feasibility at Tier 3 — high failure risk")
            if severity != "critical":
                severity = "warning"
            impact += 0.1

        if plan.estimated_impact == "significant" and plan.tier < 3:
            issues.append("Significant impact below Tier 3 — escalate")
            if severity == "ok":
                severity = "warning"
            impact += 0.1

        action = "halt" if severity == "critical" else "caution" if severity == "warning" else "proceed"
        return VantaValidation(
            severity=severity, layer="both",
            issue="; ".join(issues) if issues else "Build plan validation passed",
            confidence_impact=min(1.0, impact), recommended_action=action,
        )

    # ── Signal Consistency ──────────────────────────────────────────────────

    def check_signal_consistency(self, signals: List[Dict]) -> List[VantaValidation]:
        """
        Validate consistency across multiple trading signals.

        Checks direction consistency, confidence alignment, RR viability,
        and timeframe agreement.

        Args:
            signals: List of signal dicts with symbol, direction, confidence, rr, regime.

        Returns:
            List of VantaValidation objects for any inconsistencies.
        """
        validations: List[VantaValidation] = []

        if not signals:
            return validations

        if len(signals) == 1:
            validations.append(self._validate_single_signal(signals[0]))
            return validations

        # Direction consistency per symbol
        by_symbol: Dict[str, List[str]] = {}
        for s in signals:
            sym = s.get("symbol", "UNKNOWN")
            by_symbol.setdefault(sym, []).append(s.get("direction", "none"))

        for sym, dirs in by_symbol.items():
            bull = dirs.count("bullish")
            bear = dirs.count("bearish")
            if bull > 0 and bear > 0:
                validations.append(VantaValidation(
                    severity="critical", layer="both",
                    issue=f"Contradictory signals for {sym}: {bull} bullish, {bear} bearish",
                    confidence_impact=_SIGNAL_DIVERGENCE_IMPACT, recommended_action="halt",
                    contradiction_details={"symbol": sym, "bullish": bull, "bearish": bear},
                ))

        # Confidence spread
        confs = [float(s.get("confidence", 0.0)) for s in signals if s.get("confidence") is not None]
        if confs and (max(confs) - min(confs)) > 0.5:
            validations.append(VantaValidation(
                severity="warning", layer="both",
                issue=f"Signal confidence spread too wide: {max(confs):.3f} - {min(confs):.3f}",
                confidence_impact=0.1, recommended_action="caution",
            ))

        # RR viability
        for s in signals:
            rr = float(s.get("rr", 0.0))
            if rr < 0:
                validations.append(VantaValidation(
                    severity="critical", layer="both",
                    issue=f"Negative RR for {s.get('symbol', 'UNKNOWN')}: {rr}",
                    confidence_impact=0.4, recommended_action="halt",
                ))
            elif 0 < rr < 0.3:
                validations.append(VantaValidation(
                    severity="warning", layer="both",
                    issue=f"Very low RR for {s.get('symbol', 'UNKNOWN')}: {rr:.2f}",
                    confidence_impact=0.15, recommended_action="caution",
                ))

        # Mixed regime check
        sig_by_sym: Dict[str, List[Dict]] = {}
        for s in signals:
            sig_by_sym.setdefault(s.get("symbol", "UNKNOWN"), []).append(s)
        for sym, syms in sig_by_sym.items():
            regimes = set(s.get("regime", "") for s in syms)
            if len(regimes) > 1 and "volatile" in regimes:
                validations.append(VantaValidation(
                    severity="warning", layer="atlas",
                    issue=f"Mixed regime signals for {sym}: {regimes}",
                    confidence_impact=0.1, recommended_action="caution",
                ))

        for v in validations:
            self._record(v)

        log.info("vanta_signal_consistency", signals=len(signals), validations=len(validations))
        return validations

    # ── Status ──────────────────────────────────────────────────────────────

    @property
    def status(self) -> Dict[str, Any]:
        """Return VANTA agent status."""
        return {
            "layer": "vanta",
            "role": "validation_and_creation",
            "agent": True,
            "bounded": True,
            "total_validations": self._total_validations,
            "halt_count": self._halt_count,
            "consecutive_halts": self._consecutive_halts,
            "build_plans_created": len(self._build_plans),
            "pending_approvals": len(self._pending_approvals),
            "configuration": {
                "confidence_low_threshold": self._confidence_low,
                "confidence_critical_threshold": self._confidence_critical,
                "volatility_unsafe_pct": self._volatility_unsafe,
                "volatility_caution_pct": self._volatility_caution,
                "max_consecutive_halts": self._max_consecutive_halts,
            },
            "tier_boundaries": {
                "tier_1": "Auto: validation, analysis, diagnostics, reporting",
                "tier_2": "Auto-safe: system design, code scaffolds, templates",
                "tier_3": "Human approval REQUIRED: deployment, data mod, infra",
            },
            "critical_boundaries": [
                "NEVER directly edits production code",
                "NEVER deploys automatically without Tier 3 approval",
                "NEVER freely controls desktop or unrestricted actions",
                "NEVER overrides PRISM data quality flags",
            ],
        }

    # ── Internal: PRISM Impact ──────────────────────────────────────────────

    def _assess_prism_impact(self, prism_flags: List[Any]) -> Optional[VantaValidation]:
        """Assess impact of PRISM flags on intelligence reliability."""
        if not prism_flags:
            return None

        critical_count = 0
        warning_count = 0
        for flag in prism_flags:
            status = getattr(flag, "status", "")
            if hasattr(status, "value"):
                status = status.value
            severity = getattr(flag, "severity", "")
            if hasattr(severity, "value"):
                severity = severity.value
            if status == "fail" or severity == "critical":
                critical_count += 1
            elif status == "warn" or severity == "warning":
                warning_count += 1

        if critical_count > 0:
            return VantaValidation(
                severity="critical", layer="both",
                issue=f"PRISM flagged {critical_count} critical data quality issue(s)",
                confidence_impact=min(0.5, critical_count * 0.15), recommended_action="halt",
            )
        if warning_count > 0:
            return VantaValidation(
                severity="warning", layer="both",
                issue=f"PRISM flagged {warning_count} data quality warning(s)",
                confidence_impact=min(0.2, warning_count * 0.05), recommended_action="caution",
            )
        return None

    # ── Internal: Logic Anomaly Detection ───────────────────────────────────

    def _detect_logic_anomalies(self, atlas: Dict) -> List[VantaValidation]:
        """Detect logic inconsistencies in ATLAS analysis."""
        anomalies: List[VantaValidation] = []
        conf = float(atlas.get("confidence", 0.0))
        conviction = int(atlas.get("conviction", 0))
        structure = atlas.get("structure", "")
        regime = atlas.get("regime", "")
        zones = atlas.get("liquidity_zones", [])

        if conf > 0.7 and structure == "undefined":
            anomalies.append(VantaValidation(
                severity="warning", layer="atlas",
                issue="High confidence with undefined structure — inconsistency",
                confidence_impact=0.15, recommended_action="caution",
            ))

        if structure == "bos" and regime == "range":
            anomalies.append(VantaValidation(
                severity="warning", layer="atlas",
                issue="BOS with range regime — contradictory signals",
                confidence_impact=0.1, recommended_action="caution",
            ))

        if regime == "trend" and not zones:
            anomalies.append(VantaValidation(
                severity="warning", layer="atlas",
                issue="Trend regime with no liquidity zones — may be weak trend",
                confidence_impact=0.1, recommended_action="caution",
            ))

        if conviction == 0 and conf > 0.5:
            anomalies.append(VantaValidation(
                severity="warning", layer="atlas",
                issue="Zero conviction with moderate confidence — scoring inconsistency",
                confidence_impact=0.15, recommended_action="caution",
            ))

        if structure == "choch" and conf > 0.8:
            anomalies.append(VantaValidation(
                severity="warning", layer="atlas",
                issue="CHoCH with very high confidence — reversal certainty is rare",
                confidence_impact=0.05, recommended_action="caution",
            ))

        return anomalies

    # ── Internal: NOVA Output Validation ────────────────────────────────────

    def _validate_nova_output(self, nova: Dict) -> VantaValidation:
        """Validate NOVA output for internal consistency."""
        issues: List[str] = []
        severity, impact = "ok", 0.0

        movement = nova.get("movement", "").lower()
        change = float(nova.get("change_pct", 0.0))

        if "rising" in movement and change < -0.5:
            issues.append("Movement says 'rising' but change_pct is negative")
            severity, impact = "warning", 0.15
        elif "falling" in movement and change > 0.5:
            issues.append("Movement says 'falling' but change_pct is positive")
            severity, impact = "warning", 0.15

        key_levels = nova.get("key_levels", {})
        if isinstance(key_levels, dict):
            support = float(key_levels.get("support", 0.0))
            resistance = float(key_levels.get("resistance", 0.0))
            current = float(key_levels.get("current", 0.0))
            if support > 0 and resistance > 0 and support >= resistance:
                issues.append(f"Support ({support}) >= Resistance ({resistance}) — inverted")
                severity, impact = "critical", 0.3
            if current > 0 and support > 0 and current < support * 0.9:
                issues.append("Current price far below support — stale levels")
                if severity != "critical":
                    severity = "warning"
                impact += 0.1

        regime = nova.get("regime", "")
        if regime and regime not in {"trend", "range", "volatile", "unknown"}:
            issues.append(f"Invalid regime label: {regime}")
            if severity != "critical":
                severity = "warning"
            impact += 0.05

        action = "halt" if severity == "critical" else "caution" if severity == "warning" else "proceed"
        return VantaValidation(
            severity=severity, layer="nova",
            issue="; ".join(issues) if issues else "NOVA output validation passed",
            confidence_impact=min(1.0, impact), recommended_action=action,
        )

    # ── Internal: Direction Conflict ────────────────────────────────────────

    @staticmethod
    def _direction_conflict(atlas_structure: str, nova_movement: str) -> bool:
        """Check if ATLAS structure and NOVA movement contradict."""
        m = nova_movement.lower()
        if atlas_structure == "bos" and "sideways" in m:
            return True
        if atlas_structure == "choch" and "sideways" in m:
            return True
        if atlas_structure == "consolidation" and ("strongly" in m or "sharply" in m):
            return True
        return False

    # ── Internal: Build Plan Helpers ────────────────────────────────────────

    @staticmethod
    def _infer_plan_type(requirement: str) -> str:
        req = requirement.lower()
        for kw in ("architecture", "system design", "infrastructure", "migration", "redesign"):
            if kw in req:
                return "architecture"
        for kw in ("scaffold", "generate code", "template", "boilerplate", "skeleton", "prototype"):
            if kw in req:
                return "code_scaffold"
        return "system_design"

    @staticmethod
    def _assess_feasibility(requirement: str, tier: int) -> str:
        req = requirement.lower()
        for indicator in ("rewrite", "migration", "replace entire", "from scratch", "multiple systems"):
            if indicator in req:
                return "low"
        return "high" if tier <= 2 else "medium"

    @staticmethod
    def _generate_components(requirement: str, plan_type: str, tier: int) -> List[Dict]:
        if plan_type == "system_design":
            return [
                {"name": "core_module", "description": f"Core module for: {requirement[:100]}", "tier_required": tier, "dependencies": []},
                {"name": "interface", "description": "Public interface / API surface", "tier_required": tier, "dependencies": ["core_module"]},
                {"name": "validation_layer", "description": "Input/output validation", "tier_required": max(1, tier - 1), "dependencies": ["interface"]},
            ]
        if plan_type == "code_scaffold":
            return [
                {"name": "skeleton", "description": f"Code skeleton for: {requirement[:100]}", "tier_required": tier, "dependencies": []},
                {"name": "tests_skeleton", "description": "Test file skeleton", "tier_required": max(1, tier - 1), "dependencies": ["skeleton"]},
                {"name": "config_template", "description": "Configuration template", "tier_required": max(1, tier - 1), "dependencies": []},
            ]
        # architecture
        return [
            {"name": "architecture_doc", "description": f"Architecture design for: {requirement[:100]}", "tier_required": tier, "dependencies": []},
            {"name": "data_flow", "description": "Data flow diagram and contracts", "tier_required": tier, "dependencies": ["architecture_doc"]},
            {"name": "integration_points", "description": "Integration point specifications", "tier_required": tier, "dependencies": ["architecture_doc", "data_flow"]},
            {"name": "failure_modes", "description": "Failure mode analysis and recovery paths", "tier_required": tier, "dependencies": ["architecture_doc"]},
        ]

    @staticmethod
    def _identify_risks(requirement: str, tier: int) -> List[str]:
        risks = ["Requirement may be incomplete or ambiguous"]
        if tier >= 3:
            risks += ["Tier 3: Changes affect production systems",
                       "Tier 3: Human approval required before execution",
                       "Tier 3: Rollback may be complex or partial"]
        if tier >= 2:
            risks += ["Generated code may not match existing patterns",
                       "Dependencies may introduce version conflicts"]
        req = requirement.lower()
        if "database" in req or "db" in req:
            risks.append("Database changes risk data loss or corruption")
        if "api" in req:
            risks.append("API changes risk breaking existing consumers")
        if "auth" in req or "security" in req:
            risks.append("Security-related changes require extra review")
        if "deploy" in req or "production" in req:
            risks.append("Deployment changes risk service interruption")
        return risks

    @staticmethod
    def _estimate_impact(tier: int, plan_type: str) -> str:
        if tier >= 3:
            return "moderate"
        if tier == 2:
            return "moderate" if plan_type == "architecture" else "minimal"
        return "none"

    @staticmethod
    def _build_rollback(plan_type: str, tier: int) -> str:
        if tier >= 3:
            return ("Tier 3 rollback: Revert deployment to previous version. "
                    "Restore database snapshot if data was modified. "
                    "Verify all services healthy before declaring rollback complete.")
        if plan_type == "code_scaffold":
            return "Delete generated files and remove from version control. No runtime impact."
        if plan_type == "architecture":
            return "Archive architecture documents. No runtime impact — design only."
        return "Revert generated artifacts. Verify no runtime dependencies introduced."

    # ── Internal: Single Signal Validation ──────────────────────────────────

    @staticmethod
    def _validate_single_signal(signal: Dict) -> VantaValidation:
        """Validate a single signal for internal consistency."""
        issues: List[str] = []
        impact, severity = 0.0, "ok"
        direction = signal.get("direction", "none")
        confidence = float(signal.get("confidence", 0.0))
        rr = float(signal.get("rr", 0.0))

        if direction == "none" and confidence > 0.5:
            issues.append("No direction with high confidence")
            severity, impact = "warning", 0.1
        if rr < 0:
            issues.append(f"Negative RR: {rr}")
            severity, impact = "critical", 0.3
        if confidence < 0.1 and direction not in ("none", ""):
            issues.append("Very low confidence with active direction")
            if severity != "critical":
                severity = "warning"
            impact += 0.1

        action = "halt" if severity == "critical" else "caution" if severity == "warning" else "proceed"
        return VantaValidation(
            severity=severity, layer="both",
            issue="; ".join(issues) if issues else "Single signal validation passed",
            confidence_impact=min(1.0, impact), recommended_action=action,
        )

    # ── Internal: Record Validation ─────────────────────────────────────────

    def _record(self, validation: VantaValidation) -> None:
        """Record a validation result for history and pattern detection."""
        self._total_validations += 1
        self._recent_validations.append(validation)
        if len(self._recent_validations) > 500:
            self._recent_validations = self._recent_validations[-500:]

        if validation.severity == "critical" and validation.recommended_action == "halt":
            self._halt_count += 1
            self._consecutive_halts += 1
            self._last_halt_time = validation.timestamp
        elif validation.severity != "critical":
            self._consecutive_halts = 0

        if validation.severity == "critical":
            log.warning("vanta_critical", layer=validation.layer,
                        issue=validation.issue, action=validation.recommended_action)
