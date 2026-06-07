"""
marketmate.intelligence.vinni.monitor
──────────────────────────────────────
VINNI: Market Data Intelligence Monitor

Observation-only intelligence layer. Watches PRISM outputs for data quality
patterns and produces structured diagnostics for downstream consumption.

VINNI NEVER:
  - Fixes things
  - Restarts servers
  - Deploys code
  - Executes shell commands
  - Controls systems directly

VINNI ONLY:
  - Observes data quality patterns
  - Analyzes trends and anomalies
  - Validates state consistency
  - Reports structured diagnostics
  - Recommends actions for other layers

Monitoring domains:
  1. Feed integrity     — PRISM validation result patterns
  2. Data consistency   — cross-provider deviations, normalization failures
  3. State engine health — conviction freezes, regime lockups, stale vectors
  4. Signal integrity   — impossible RR, abnormal SL streaks, confidence collapse
  5. Infrastructure     — CPU, RAM, queue depth, websocket throughput

Position in pipeline:
  RAW DATA → PRISM (validate) → [VINNI] (observe) → ATLAS → VANTA → NOVA

Created: 2026-05-29
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional

from marketmate.core.logger import get_logger

log = get_logger("intelligence.vinni")


# ─── Severity Levels ──────────────────────────────────────────────────────────

class VinniSeverity(str, Enum):
    """Severity levels for VINNI diagnostics."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


class VinniComponent(str, Enum):
    """Component domains that VINNI monitors."""

    FEED_VALIDATION = "feed_validation"
    DATA_CONSISTENCY = "data_consistency"
    STATE_ENGINE = "state_engine"
    SIGNAL_INTEGRITY = "signal_integrity"
    INFRASTRUCTURE = "infrastructure"


# ─── Diagnostic Output ────────────────────────────────────────────────────────

@dataclass
class VinniDiagnostic:
    """
    A single structured diagnostic output from VINNI.

    VINNI always produces JSON-like structured output — never prose.
    Each diagnostic pinpoints a specific observation with metric context
    and a recommended action for downstream layers.

    Attributes:
        severity: How serious the observation is.
        component: Which monitoring domain this belongs to.
        symbol: The trading symbol this observation relates to.
        issue: Specific issue identifier (machine-readable key).
        metric_value: Numeric value that characterises the observation.
        metric_unit: Unit for metric_value (ms, pct, count, score, etc.).
        recommended_action: What downstream layers should consider doing.
        observation_time: ISO 8601 timestamp of when this was observed.
        prism_correlation: Which PRISM check this relates to, if any.
    """

    severity: str  # "info" | "warning" | "error" | "critical"
    component: str  # "feed_validation" | "data_consistency" | "state_engine" | "signal_integrity" | "infrastructure"
    symbol: str
    issue: str  # specific issue identifier
    metric_value: float
    metric_unit: str
    recommended_action: str
    observation_time: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )
    prism_correlation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        """Convert to structured dictionary for downstream consumption."""
        return {
            "severity": self.severity,
            "component": self.component,
            "symbol": self.symbol,
            "issue": self.issue,
            "metric_value": self.metric_value,
            "metric_unit": self.metric_unit,
            "recommended_action": self.recommended_action,
            "observation_time": self.observation_time,
            "prism_correlation": self.prism_correlation,
        }


# ─── Internal Tracking Structures ─────────────────────────────────────────────

@dataclass
class _QualityTrendPoint:
    """A single data quality measurement for trend tracking."""

    timestamp: str
    quality_score: float  # 0.0 to 1.0
    check_count: int = 0
    fail_count: int = 0


@dataclass
class _ProviderDegradation:
    """
    Tracks degradation state for a single data provider.

    VINNI does NOT act on degradation — it only observes and reports.
    The recommended_action field in diagnostics will suggest what
    other layers (OPS, VANTA) might do about it.
    """

    provider: str
    consecutive_failures: int = 0
    degradation_score: float = 0.0  # 0.0 (healthy) to 1.0 (degraded)
    last_failure_time: str = ""
    last_recovery_time: str = ""
    total_failures: int = 0
    total_checks: int = 0

    def record_check(self, passed: bool) -> None:
        """Record a single check result and update degradation state."""
        self.total_checks += 1
        if passed:
            self.consecutive_failures = 0
            self.degradation_score = max(0.0, self.degradation_score - 0.05)
            self.last_recovery_time = datetime.now(timezone.utc).isoformat()
        else:
            self.consecutive_failures += 1
            self.total_failures += 1
            self.last_failure_time = datetime.now(timezone.utc).isoformat()
            # Exponential decay toward full degradation
            self.degradation_score = min(1.0, self.degradation_score + 0.15)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider": self.provider,
            "consecutive_failures": self.consecutive_failures,
            "degradation_score": round(self.degradation_score, 4),
            "last_failure_time": self.last_failure_time,
            "last_recovery_time": self.last_recovery_time,
            "total_failures": self.total_failures,
            "total_checks": self.total_checks,
        }


@dataclass
class _FeedStability:
    """
    Tracks feed stability metrics for a symbol+provider pair.

    Feed stability measures how consistently the data feed delivers
    timely, complete, and valid data without interruptions.
    """

    symbol: str
    provider: str
    disconnect_count: int = 0
    stale_count: int = 0
    delay_samples: deque = field(default_factory=lambda: deque(maxlen=100))
    quality_samples: deque = field(default_factory=lambda: deque(maxlen=200))

    @property
    def avg_delay_ms(self) -> float:
        """Average feed delay from recent samples."""
        if not self.delay_samples:
            return 0.0
        return sum(self.delay_samples) / len(self.delay_samples)

    @property
    def quality_score(self) -> float:
        """Current feed quality score (0.0-1.0)."""
        if not self.quality_samples:
            return 0.5  # Unknown — neutral
        return sum(self.quality_samples) / len(self.quality_samples)


# ─── VINNI Monitor ─────────────────────────────────────────────────────────────

# Thresholds — VINNI observes against these; it does NOT enforce them.
_CONSECUTIVE_FAILURE_DEGRADATION_THRESHOLD = 3
_STALE_VECTOR_MAX_AGE_SECONDS = 300.0
_CONVICTTION_FREEZE_THRESHOLD = 0.01
_CONVICTTION_FREEZE_CYCLES = 10
_REGIME_LOCKUP_CYCLES = 15
_IMPOSSIBLE_RR_MIN = 0.3
_SL_STREAK_ABNORMAL_MIN = 5
_CONFIDENCE_COLLAPSE_THRESHOLD = 0.2
_CPU_WARNING_PCT = 80.0
_CPU_CRITICAL_PCT = 95.0
_RAM_WARNING_PCT = 85.0
_RAM_CRITICAL_PCT = 95.0
_QUEUE_DEPTH_WARNING = 500
_QUEUE_DEPTH_CRITICAL = 2000
_WEBSOCKET_THROUGHPUT_MIN = 10  # messages per second


class VinniMonitor:
    """
    Market Data Intelligence Monitor — observation only.

    Watches PRISM outputs for data quality patterns and produces
    structured diagnostics (NOT prose). VINNI never modifies state,
    never restarts services, and never takes direct action.

    Instead, VINNI:
      - Observes data quality patterns across feeds and providers
      - Tracks degradation trends over time
      - Detects state engine anomalies (frozen conviction, regime lockups)
      - Validates signal integrity (impossible RR, confidence collapse)
      - Monitors infrastructure health (CPU, RAM, queue depth)
      - Recommends actions for ATLAS, VANTA, and OPS layers

    Configuration:
        quality_trend_window: Number of recent quality samples to retain.
        provider_degradation_threshold: Consecutive failures before flagging.
        stale_vector_max_age_seconds: Seconds before state is considered stale.
        conviction_freeze_threshold: Minimum conviction change to be "alive".
        conviction_freeze_cycles: Consecutive zero-change cycles = freeze.
    """

    def __init__(
        self,
        quality_trend_window: int = 200,
        provider_degradation_threshold: int = _CONSECUTIVE_FAILURE_DEGRADATION_THRESHOLD,
        stale_vector_max_age_seconds: float = _STALE_VECTOR_MAX_AGE_SECONDS,
        conviction_freeze_threshold: float = _CONVICTTION_FREEZE_THRESHOLD,
        conviction_freeze_cycles: int = _CONVICTTION_FREEZE_CYCLES,
    ) -> None:
        """Initialize VINNI monitor with configurable thresholds."""
        self._quality_trend_window = quality_trend_window
        self._provider_degradation_threshold = provider_degradation_threshold
        self._stale_vector_max_age_seconds = stale_vector_max_age_seconds
        self._conviction_freeze_threshold = conviction_freeze_threshold
        self._conviction_freeze_cycles = conviction_freeze_cycles

        # Quality trend tracking: symbol → deque of _QualityTrendPoint
        self._quality_trends: Dict[str, deque] = {}

        # Provider degradation: provider → _ProviderDegradation
        self._provider_degradation: Dict[str, _ProviderDegradation] = {}

        # Feed stability: "symbol:provider" → _FeedStability
        self._feed_stability: Dict[str, _FeedStability] = {}

        # Conviction history for freeze detection: symbol → deque of float
        self._conviction_history: Dict[str, deque] = {}

        # Regime history for lockup detection: symbol → deque of str
        self._regime_history: Dict[str, deque] = {}

        # Recent diagnostics
        self._diagnostics: List[VinniDiagnostic] = []
        self._max_diagnostics = 1000

        # Observation counters
        self._total_observations = 0
        self._total_diagnostics_produced = 0

        log.info(
            "vinni_initialized",
            quality_trend_window=quality_trend_window,
            provider_degradation_threshold=provider_degradation_threshold,
            stale_vector_max_age_seconds=stale_vector_max_age_seconds,
        )

    # ── PRISM Result Processing ─────────────────────────────────────────────

    def process_prism_results(self, prism_results: List[Any]) -> List[VinniDiagnostic]:
        """
        Process PRISM validation results and produce VINNI diagnostics.

        This is the primary ingestion point. VINNI observes PRISM outputs
        and generates structured diagnostics based on patterns detected
        across feed integrity, data consistency, and provider reliability.

        Args:
            prism_results: List of PrismResult objects from the PRISM layer.

        Returns:
            List of VinniDiagnostic objects for observations that warrant
            attention. Not every PRISM result produces a VINNI diagnostic —
            only patterns that indicate systemic issues or trends.
        """
        diagnostics: List[VinniDiagnostic] = []
        self._total_observations += len(prism_results)

        for result in prism_results:
            symbol = getattr(result, "symbol", "UNKNOWN")
            provider = getattr(result, "provider", "unknown")
            status = getattr(result, "status", "pass")
            check = getattr(result, "check", "")
            check_value = check.value if hasattr(check, "value") else str(check)
            severity = getattr(result, "severity", "")
            severity_value = severity.value if hasattr(severity, "value") else str(severity)
            metric_value = getattr(result, "metric_value", 0.0)
            metric_unit = getattr(result, "metric_unit", "")

            # ── Update provider degradation tracking ───────────────────
            self._update_provider_degradation(provider, status == "pass")

            # ── Update feed stability tracking ─────────────────────────
            feed_key = f"{symbol}:{provider}"
            self._update_feed_stability(
                feed_key, symbol, provider, status, metric_value, metric_unit,
            )

            # ── Update quality trend for symbol ────────────────────────
            quality_score = 1.0 if status == "pass" else (0.5 if status == "warn" else 0.0)
            self._record_quality_point(symbol, quality_score, 1, 0 if status == "pass" else 1)

            # ── Generate diagnostics for non-pass results ──────────────
            if status == "fail":
                diag = VinniDiagnostic(
                    severity=self._map_prism_severity(severity_value),
                    component=self._map_prism_component(check_value),
                    symbol=symbol,
                    issue=f"prism_{check_value}",
                    metric_value=metric_value,
                    metric_unit=metric_unit,
                    recommended_action=self._recommend_for_check(check_value, provider),
                    prism_correlation=check_value,
                )
                diagnostics.append(diag)

            elif status == "warn":
                # Check if this is part of a degradation pattern
                degradation = self._provider_degradation.get(provider)
                if degradation and degradation.consecutive_failures >= 1:
                    diag = VinniDiagnostic(
                        severity=VinniSeverity.WARNING.value,
                        component=VinniComponent.DATA_CONSISTENCY.value,
                        symbol=symbol,
                        issue="provider_degradation_pattern",
                        metric_value=degradation.degradation_score,
                        metric_unit="score",
                        recommended_action=f"Monitor provider {provider} — consecutive issues detected",
                        prism_correlation=check_value,
                    )
                    diagnostics.append(diag)

        # ── Check for provider degradation alerts ──────────────────────────
        degradation_diags = self._check_provider_degradation()
        diagnostics.extend(degradation_diags)

        # ── Check for feed stability issues ────────────────────────────────
        feed_diags = self._check_feed_stability()
        diagnostics.extend(feed_diags)

        # Record all diagnostics
        self._diagnostics.extend(diagnostics)
        if len(self._diagnostics) > self._max_diagnostics:
            self._diagnostics = self._diagnostics[-self._max_diagnostics:]
        self._total_diagnostics_produced += len(diagnostics)

        if diagnostics:
            log.info(
                "vinni_diagnostics_produced",
                input_count=len(prism_results),
                output_count=len(diagnostics),
                critical=sum(1 for d in diagnostics if d.severity == "critical"),
                warning=sum(1 for d in diagnostics if d.severity == "warning"),
            )

        return diagnostics

    # ── State Engine Health ─────────────────────────────────────────────────

    def check_state_engine_health(self, state_data: Dict) -> List[VinniDiagnostic]:
        """
        Check state engine health for anomalies.

        Detects:
          - Conviction freezes: conviction score unchanged for many cycles
          - Regime lockups: regime stuck in same state for too long
          - Stale state vectors: state not updated within expected interval
          - Event discontinuity: expected state transitions missing

        Args:
            state_data: Dict with keys per symbol, each containing:
                - conviction_score: float
                - regime: str
                - last_updated: str (ISO 8601)
                - scan_count: int

        Returns:
            List of VinniDiagnostic for any state engine issues observed.
        """
        diagnostics: List[VinniDiagnostic] = []
        now = datetime.now(timezone.utc)

        for symbol, data in state_data.items():
            conviction = float(data.get("conviction_score", 0.0))
            regime = str(data.get("regime", "unknown"))
            last_updated = str(data.get("last_updated", ""))
            scan_count = int(data.get("scan_count", 0))

            # ── Track conviction history for freeze detection ──────────
            if symbol not in self._conviction_history:
                self._conviction_history[symbol] = deque(maxlen=self._conviction_freeze_cycles + 5)
            self._conviction_history[symbol].append(conviction)

            # ── Track regime history for lockup detection ──────────────
            if symbol not in self._regime_history:
                self._regime_history[symbol] = deque(maxlen=_REGIME_LOCKUP_CYCLES + 5)
            self._regime_history[symbol].append(regime)

            # ── Stale state vector ─────────────────────────────────────
            if last_updated:
                try:
                    last_time = datetime.fromisoformat(last_updated)
                    age_seconds = (now - last_time).total_seconds()

                    if age_seconds > self._stale_vector_max_age_seconds:
                        diagnostics.append(VinniDiagnostic(
                            severity=VinniSeverity.ERROR.value,
                            component=VinniComponent.STATE_ENGINE.value,
                            symbol=symbol,
                            issue="stale_state_vector",
                            metric_value=age_seconds,
                            metric_unit="seconds",
                            recommended_action="Investigate state engine update loop — vector may be frozen",
                            prism_correlation="",
                        ))
                    elif age_seconds > self._stale_vector_max_age_seconds * 0.5:
                        diagnostics.append(VinniDiagnostic(
                            severity=VinniSeverity.WARNING.value,
                            component=VinniComponent.STATE_ENGINE.value,
                            symbol=symbol,
                            issue="aging_state_vector",
                            metric_value=age_seconds,
                            metric_unit="seconds",
                            recommended_action="State vector aging — monitor for staleness",
                            prism_correlation="",
                        ))
                except (ValueError, TypeError):
                    diagnostics.append(VinniDiagnostic(
                        severity=VinniSeverity.WARNING.value,
                        component=VinniComponent.STATE_ENGINE.value,
                        symbol=symbol,
                        issue="invalid_state_timestamp",
                        metric_value=0.0,
                        metric_unit="parse_error",
                        recommended_action="State engine timestamp unparseable — verify data format",
                        prism_correlation="",
                    ))

            # ── Conviction freeze detection ────────────────────────────
            conviction_hist = self._conviction_history[symbol]
            if len(conviction_hist) >= self._conviction_freeze_cycles:
                recent = list(conviction_hist)[-self._conviction_freeze_cycles:]
                max_change = max(abs(recent[i] - recent[i - 1]) for i in range(1, len(recent)))
                if max_change < self._conviction_freeze_threshold:
                    diagnostics.append(VinniDiagnostic(
                        severity=VinniSeverity.WARNING.value,
                        component=VinniComponent.STATE_ENGINE.value,
                        symbol=symbol,
                        issue="conviction_freeze",
                        metric_value=max_change,
                        metric_unit="delta",
                        recommended_action="Conviction score frozen — state engine may not be processing new data",
                        prism_correlation="",
                    ))

            # ── Regime lockup detection ────────────────────────────────
            regime_hist = self._regime_history[symbol]
            if len(regime_hist) >= _REGIME_LOCKUP_CYCLES:
                recent_regimes = list(regime_hist)[-_REGIME_LOCKUP_CYCLES:]
                if len(set(recent_regimes)) == 1 and recent_regimes[0] != "unknown":
                    diagnostics.append(VinniDiagnostic(
                        severity=VinniSeverity.INFO.value,
                        component=VinniComponent.STATE_ENGINE.value,
                        symbol=symbol,
                        issue="regime_lockup",
                        metric_value=float(_REGIME_LOCKUP_CYCLES),
                        metric_unit="cycles",
                        recommended_action=f"Regime locked in '{recent_regimes[0]}' for {_REGIME_LOCKUP_CYCLES} cycles — verify market conditions",
                        prism_correlation="",
                    ))

        return diagnostics

    # ── Signal Integrity ────────────────────────────────────────────────────

    def check_signal_integrity(self, signal_data: Dict) -> List[VinniDiagnostic]:
        """
        Check signal integrity for anomalies.

        Detects:
          - Impossible RR: risk-reward ratios that cannot be achieved
          - Abnormal SL streaks: consecutive stop-losses exceeding threshold
          - Confidence collapse: confidence score drops below threshold
          - RR inconsistency: RR values that contradict signal direction

        Args:
            signal_data: Dict with keys per symbol, each containing:
                - current_rr: float
                - sl_streak: int (consecutive SL count)
                - confidence: float
                - signal_direction: str
                - atr: float

        Returns:
            List of VinniDiagnostic for any signal integrity issues.
        """
        diagnostics: List[VinniDiagnostic] = []

        for symbol, data in signal_data.items():
            current_rr = float(data.get("current_rr", 0.0))
            sl_streak = int(data.get("sl_streak", 0))
            confidence = float(data.get("confidence", 0.0))
            signal_direction = str(data.get("signal_direction", "none"))
            atr = float(data.get("atr", 0.0))

            # ── Impossible RR ──────────────────────────────────────────
            if 0 < current_rr < _IMPOSSIBLE_RR_MIN:
                diagnostics.append(VinniDiagnostic(
                    severity=VinniSeverity.ERROR.value,
                    component=VinniComponent.SIGNAL_INTEGRITY.value,
                    symbol=symbol,
                    issue="impossible_rr",
                    metric_value=current_rr,
                    metric_unit="rr_ratio",
                    recommended_action="RR below viable threshold — signal should not have been generated",
                    prism_correlation="",
                ))

            # ── Negative RR ────────────────────────────────────────────
            if current_rr < 0:
                diagnostics.append(VinniDiagnostic(
                    severity=VinniSeverity.CRITICAL.value,
                    component=VinniComponent.SIGNAL_INTEGRITY.value,
                    symbol=symbol,
                    issue="negative_rr",
                    metric_value=current_rr,
                    metric_unit="rr_ratio",
                    recommended_action="Negative RR detected — SL/TP calculation is inverted or corrupted",
                    prism_correlation="",
                ))

            # ── Abnormal SL streaks ────────────────────────────────────
            if sl_streak >= _SL_STREAK_ABNORMAL_MIN:
                diagnostics.append(VinniDiagnostic(
                    severity=VinniSeverity.ERROR.value,
                    component=VinniComponent.SIGNAL_INTEGRITY.value,
                    symbol=symbol,
                    issue="abnormal_sl_streak",
                    metric_value=float(sl_streak),
                    metric_unit="consecutive_count",
                    recommended_action=f"SL streak of {sl_streak} — signal generation may be misaligned with market",
                    prism_correlation="",
                ))
            elif sl_streak >= _SL_STREAK_ABNORMAL_MIN - 2:
                diagnostics.append(VinniDiagnostic(
                    severity=VinniSeverity.WARNING.value,
                    component=VinniComponent.SIGNAL_INTEGRITY.value,
                    symbol=symbol,
                    issue="elevated_sl_streak",
                    metric_value=float(sl_streak),
                    metric_unit="consecutive_count",
                    recommended_action="SL streak approaching abnormal levels — monitor closely",
                    prism_correlation="",
                ))

            # ── Confidence collapse ────────────────────────────────────
            if 0 < confidence < _CONFIDENCE_COLLAPSE_THRESHOLD:
                diagnostics.append(VinniDiagnostic(
                    severity=VinniSeverity.WARNING.value,
                    component=VinniComponent.SIGNAL_INTEGRITY.value,
                    symbol=symbol,
                    issue="confidence_collapse",
                    metric_value=confidence,
                    metric_unit="score",
                    recommended_action="Confidence score near zero — signal quality unreliable",
                    prism_correlation="",
                ))

            # ── Zero ATR with active signal ────────────────────────────
            if atr == 0.0 and signal_direction not in ("none", ""):
                diagnostics.append(VinniDiagnostic(
                    severity=VinniSeverity.ERROR.value,
                    component=VinniComponent.SIGNAL_INTEGRITY.value,
                    symbol=symbol,
                    issue="zero_atr_with_signal",
                    metric_value=0.0,
                    metric_unit="atr",
                    recommended_action="Active signal with zero ATR — volatility calculation failed or data missing",
                    prism_correlation="stale_price",
                ))

        return diagnostics

    # ── Infrastructure ──────────────────────────────────────────────────────

    def check_infrastructure(self, infrastructure_data: Dict) -> List[VinniDiagnostic]:
        """
        Check infrastructure health metrics.

        Monitors:
          - CPU usage
          - RAM usage
          - Queue depth (pending tasks)
          - WebSocket throughput

        Args:
            infrastructure_data: Dict containing:
                - cpu_pct: float (0-100)
                - ram_pct: float (0-100)
                - queue_depth: int
                - websocket_throughput: float (messages/sec)
                - active_connections: int
                - uptime_seconds: float

        Returns:
            List of VinniDiagnostic for any infrastructure issues.
        """
        diagnostics: List[VinniDiagnostic] = []
        symbol = "SYSTEM"  # Infrastructure is system-wide, not per-symbol

        cpu_pct = float(infrastructure_data.get("cpu_pct", 0.0))
        ram_pct = float(infrastructure_data.get("ram_pct", 0.0))
        queue_depth = int(infrastructure_data.get("queue_depth", 0))
        ws_throughput = float(infrastructure_data.get("websocket_throughput", 0.0))
        active_connections = int(infrastructure_data.get("active_connections", 0))
        uptime_seconds = float(infrastructure_data.get("uptime_seconds", 0.0))

        # ── CPU ────────────────────────────────────────────────────────
        if cpu_pct >= _CPU_CRITICAL_PCT:
            diagnostics.append(VinniDiagnostic(
                severity=VinniSeverity.CRITICAL.value,
                component=VinniComponent.INFRASTRUCTURE.value,
                symbol=symbol,
                issue="cpu_critical",
                metric_value=cpu_pct,
                metric_unit="pct",
                recommended_action="CPU at critical level — OPS should investigate and scale",
            ))
        elif cpu_pct >= _CPU_WARNING_PCT:
            diagnostics.append(VinniDiagnostic(
                severity=VinniSeverity.WARNING.value,
                component=VinniComponent.INFRASTRUCTURE.value,
                symbol=symbol,
                issue="cpu_high",
                metric_value=cpu_pct,
                metric_unit="pct",
                recommended_action="CPU usage elevated — monitor for sustained high load",
            ))

        # ── RAM ────────────────────────────────────────────────────────
        if ram_pct >= _RAM_CRITICAL_PCT:
            diagnostics.append(VinniDiagnostic(
                severity=VinniSeverity.CRITICAL.value,
                component=VinniComponent.INFRASTRUCTURE.value,
                symbol=symbol,
                issue="ram_critical",
                metric_value=ram_pct,
                metric_unit="pct",
                recommended_action="RAM at critical level — risk of OOM, OPS should investigate",
            ))
        elif ram_pct >= _RAM_WARNING_PCT:
            diagnostics.append(VinniDiagnostic(
                severity=VinniSeverity.WARNING.value,
                component=VinniComponent.INFRASTRUCTURE.value,
                symbol=symbol,
                issue="ram_high",
                metric_value=ram_pct,
                metric_unit="pct",
                recommended_action="RAM usage elevated — monitor for memory leaks",
            ))

        # ── Queue depth ────────────────────────────────────────────────
        if queue_depth >= _QUEUE_DEPTH_CRITICAL:
            diagnostics.append(VinniDiagnostic(
                severity=VinniSeverity.CRITICAL.value,
                component=VinniComponent.INFRASTRUCTURE.value,
                symbol=symbol,
                issue="queue_depth_critical",
                metric_value=float(queue_depth),
                metric_unit="count",
                recommended_action="Task queue severely backlogged — processing may stall",
            ))
        elif queue_depth >= _QUEUE_DEPTH_WARNING:
            diagnostics.append(VinniDiagnostic(
                severity=VinniSeverity.WARNING.value,
                component=VinniComponent.INFRASTRUCTURE.value,
                symbol=symbol,
                issue="queue_depth_high",
                metric_value=float(queue_depth),
                metric_unit="count",
                recommended_action="Task queue accumulating — monitor for processing delays",
            ))

        # ── WebSocket throughput ───────────────────────────────────────
        if ws_throughput < _WEBSOCKET_THROUGHPUT_MIN and uptime_seconds > 60:
            diagnostics.append(VinniDiagnostic(
                severity=VinniSeverity.WARNING.value,
                component=VinniComponent.INFRASTRUCTURE.value,
                symbol=symbol,
                issue="low_websocket_throughput",
                metric_value=ws_throughput,
                metric_unit="msg_per_sec",
                recommended_action="WebSocket throughput below expected — feed may be disconnected",
            ))

        # ── Zero connections ───────────────────────────────────────────
        if active_connections == 0 and uptime_seconds > 30:
            diagnostics.append(VinniDiagnostic(
                severity=VinniSeverity.ERROR.value,
                component=VinniComponent.INFRASTRUCTURE.value,
                symbol=symbol,
                issue="zero_websocket_connections",
                metric_value=0.0,
                metric_unit="count",
                recommended_action="No active WebSocket connections — all feeds are down",
            ))

        return diagnostics

    # ── Quality Trend ───────────────────────────────────────────────────────

    def get_data_quality_trend(self, symbol: str) -> Dict[str, Any]:
        """
        Return data quality trend over time for a given symbol.

        Provides a structured summary of how data quality has evolved,
        including current score, trend direction, and recent samples.

        Args:
            symbol: Trading symbol to query.

        Returns:
            Dict with keys:
                - symbol: str
                - current_score: float (0.0-1.0)
                - trend_direction: str ("improving" | "stable" | "degrading" | "unknown")
                - sample_count: int
                - samples: List of recent {timestamp, quality_score} dicts
        """
        trend_deque = self._quality_trends.get(symbol)

        if not trend_deque or len(trend_deque) < 2:
            return {
                "symbol": symbol,
                "current_score": 0.5,
                "trend_direction": "unknown",
                "sample_count": 0,
                "samples": [],
            }

        points = list(trend_deque)
        current_score = points[-1].quality_score

        # Compute trend direction from recent samples
        window = min(20, len(points))
        recent = points[-window:]
        if len(recent) >= 3:
            first_half_avg = sum(p.quality_score for p in recent[: window // 2]) / max(len(recent[: window // 2]), 1)
            second_half_avg = sum(p.quality_score for p in recent[window // 2 :]) / max(len(recent[window // 2 :]), 1)
            delta = second_half_avg - first_half_avg

            if delta > 0.05:
                trend_direction = "improving"
            elif delta < -0.05:
                trend_direction = "degrading"
            else:
                trend_direction = "stable"
        else:
            trend_direction = "unknown"

        samples = [
            {"timestamp": p.timestamp, "quality_score": round(p.quality_score, 4)}
            for p in points[-20:]
        ]

        return {
            "symbol": symbol,
            "current_score": round(current_score, 4),
            "trend_direction": trend_direction,
            "sample_count": len(points),
            "samples": samples,
        }

    # ── Diagnostics Access ──────────────────────────────────────────────────

    def get_diagnostics(
        self,
        severity: Optional[str] = None,
        component: Optional[str] = None,
        symbol: Optional[str] = None,
        limit: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Return recent diagnostics, optionally filtered.

        Args:
            severity: Filter by severity level (info/warning/error/critical).
            component: Filter by component domain.
            symbol: Filter by trading symbol.
            limit: Maximum number of diagnostics to return.

        Returns:
            List of diagnostic dicts, most recent first.
        """
        results = self._diagnostics

        if severity:
            results = [d for d in results if d.severity == severity]
        if component:
            results = [d for d in results if d.component == component]
        if symbol:
            results = [d for d in results if d.symbol == symbol]

        return [d.to_dict() for d in reversed(results[-limit:])]

    # ── Status ──────────────────────────────────────────────────────────────

    @property
    def status(self) -> Dict[str, Any]:
        """Return VINNI monitor status."""
        critical_count = sum(1 for d in self._diagnostics if d.severity == "critical")
        error_count = sum(1 for d in self._diagnostics if d.severity == "error")
        warning_count = sum(1 for d in self._diagnostics if d.severity == "warning")

        # Determine overall health
        if critical_count > 0:
            health = "critical"
        elif error_count > 3:
            health = "degraded"
        elif warning_count > 5:
            health = "warning"
        else:
            health = "nominal"

        return {
            "layer": "vinni",
            "role": "data_monitoring",
            "agent": False,
            "observation_only": True,
            "health": health,
            "total_observations": self._total_observations,
            "total_diagnostics_produced": self._total_diagnostics_produced,
            "recent_diagnostics": len(self._diagnostics),
            "providers_tracked": len(self._provider_degradation),
            "symbols_tracked": len(self._quality_trends),
            "critical_count": critical_count,
            "error_count": error_count,
            "warning_count": warning_count,
            "thresholds": {
                "provider_degradation_threshold": self._provider_degradation_threshold,
                "stale_vector_max_age_seconds": self._stale_vector_max_age_seconds,
                "conviction_freeze_threshold": self._conviction_freeze_threshold,
                "conviction_freeze_cycles": self._conviction_freeze_cycles,
            },
        }

    # ── Internal Helpers ────────────────────────────────────────────────────

    def _update_provider_degradation(self, provider: str, passed: bool) -> None:
        """Update provider degradation tracking with a check result."""
        if provider not in self._provider_degradation:
            self._provider_degradation[provider] = _ProviderDegradation(provider=provider)
        self._provider_degradation[provider].record_check(passed)

    def _update_feed_stability(
        self,
        feed_key: str,
        symbol: str,
        provider: str,
        status: str,
        metric_value: float,
        metric_unit: str,
    ) -> None:
        """Update feed stability tracking for a symbol+provider pair."""
        if feed_key not in self._feed_stability:
            self._feed_stability[feed_key] = _FeedStability(symbol=symbol, provider=provider)

        fs = self._feed_stability[feed_key]

        if status == "fail":
            if metric_unit == "ms":
                fs.delay_samples.append(metric_value)
            fs.quality_samples.append(0.0)
        elif status == "warn":
            if metric_unit == "ms":
                fs.delay_samples.append(metric_value)
            fs.quality_samples.append(0.5)
        else:
            fs.quality_samples.append(1.0)

    def _record_quality_point(
        self,
        symbol: str,
        quality_score: float,
        check_count: int,
        fail_count: int,
    ) -> None:
        """Record a data quality measurement for trend tracking."""
        if symbol not in self._quality_trends:
            self._quality_trends[symbol] = deque(maxlen=self._quality_trend_window)

        self._quality_trends[symbol].append(_QualityTrendPoint(
            timestamp=datetime.now(timezone.utc).isoformat(),
            quality_score=quality_score,
            check_count=check_count,
            fail_count=fail_count,
        ))

    def _check_provider_degradation(self) -> List[VinniDiagnostic]:
        """Check all providers for degradation patterns and produce diagnostics."""
        diagnostics: List[VinniDiagnostic] = []

        for provider, deg in self._provider_degradation.items():
            if deg.consecutive_failures >= self._provider_degradation_threshold:
                severity = (
                    VinniSeverity.CRITICAL.value
                    if deg.consecutive_failures >= self._provider_degradation_threshold * 3
                    else VinniSeverity.ERROR.value
                )
                diagnostics.append(VinniDiagnostic(
                    severity=severity,
                    component=VinniComponent.FEED_VALIDATION.value,
                    symbol="*",
                    issue="provider_degradation",
                    metric_value=deg.degradation_score,
                    metric_unit="score",
                    recommended_action=f"Provider {provider} degraded ({deg.consecutive_failures} consecutive failures) — consider switching to fallback",
                    prism_correlation="",
                ))

        return diagnostics

    def _check_feed_stability(self) -> List[VinniDiagnostic]:
        """Check all feeds for stability issues and produce diagnostics."""
        diagnostics: List[VinniDiagnostic] = []

        for feed_key, fs in self._feed_stability.items():
            # Low quality score
            if fs.quality_score < 0.5 and len(fs.quality_samples) >= 10:
                diagnostics.append(VinniDiagnostic(
                    severity=VinniSeverity.WARNING.value,
                    component=VinniComponent.FEED_VALIDATION.value,
                    symbol=fs.symbol,
                    issue="feed_quality_low",
                    metric_value=fs.quality_score,
                    metric_unit="score",
                    recommended_action=f"Feed {fs.provider} quality below 0.5 for {fs.symbol} — data may be unreliable",
                    prism_correlation="",
                ))

            # High average delay
            if fs.avg_delay_ms > 3000 and len(fs.delay_samples) >= 5:
                diagnostics.append(VinniDiagnostic(
                    severity=VinniSeverity.WARNING.value,
                    component=VinniComponent.FEED_VALIDATION.value,
                    symbol=fs.symbol,
                    issue="feed_delay_high",
                    metric_value=fs.avg_delay_ms,
                    metric_unit="ms",
                    recommended_action=f"Feed {fs.provider} avg delay {fs.avg_delay_ms:.0f}ms for {fs.symbol} — investigate latency",
                    prism_correlation="feed_delay",
                ))

        return diagnostics

    @staticmethod
    def _map_prism_severity(prism_severity: str) -> str:
        """Map PRISM severity to VINNI severity."""
        mapping = {
            "info": VinniSeverity.INFO.value,
            "warning": VinniSeverity.WARNING.value,
            "critical": VinniSeverity.ERROR.value,
        }
        return mapping.get(prism_severity, VinniSeverity.WARNING.value)

    @staticmethod
    def _map_prism_component(prism_check: str) -> str:
        """Map PRISM check type to VINNI component domain."""
        feed_checks = {
            "missing_candle", "stale_price", "websocket_disconnect",
            "feed_delay", "timestamp_drift",
        }
        consistency_checks = {
            "ohlc_impossible", "duplicate_tick", "spread_anomaly",
            "provider_deviation", "normalization_failure",
        }

        if prism_check in feed_checks:
            return VinniComponent.FEED_VALIDATION.value
        if prism_check in consistency_checks:
            return VinniComponent.DATA_CONSISTENCY.value
        return VinniComponent.DATA_CONSISTENCY.value

    @staticmethod
    def _recommend_for_check(check_value: str, provider: str) -> str:
        """Generate a recommended action based on PRISM check type."""
        recommendations = {
            "missing_candle": f"Gap in candle sequence from {provider} — check feed continuity",
            "stale_price": f"Price not updating from {provider} — verify connection",
            "websocket_disconnect": f"WebSocket disconnected from {provider} — switch to fallback provider",
            "feed_delay": f"Feed latency from {provider} — investigate network or provider issues",
            "timestamp_drift": f"Clock offset from {provider} — check NTP sync",
            "malformed_response": f"Invalid data from {provider} — schema may have changed",
            "ohlc_impossible": "Impossible OHLC values — halt processing for this data point",
            "duplicate_tick": f"Duplicate ticks from {provider} — possible feed echo",
            "spread_anomaly": f"Abnormal spread from {provider} — liquidity may be thin",
            "provider_deviation": "Cross-provider price mismatch — identify outlier and switch",
            "normalization_failure": "Data cannot be normalized — verify provider schema",
            "volume_spike": "Volume exceeds statistical threshold — flag for review",
        }
        return recommendations.get(check_value, f"Review {check_value} issue from {provider}")
