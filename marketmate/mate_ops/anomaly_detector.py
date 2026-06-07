"""
marketmate/mate_ops/anomaly_detector.py
────────────────────────────────────────
Statistical anomaly detection with rolling baselines — MATE-Ops Phase 2.

Phase 1 (read-only, Level 0 authority) identified a critical gap: "Anomaly
Detection Sensitivity" scored 4/10 against a target of 9.  This module closes
that gap by maintaining per-service, per-metric rolling statistical baselines
and flagging observations that deviate significantly from established norms.

Statistical approach
────────────────────
Each metric is tracked in a bounded ``deque`` (default window = 100 samples).
From that window we compute:

  * **mean**  — central tendency of recent healthy behaviour
  * **std_dev** — dispersion; the yardstick for "how far is too far"
  * **min / max / p95** — boundary statistics for operational insight

An observation is flagged as anomalous when its value exceeds
*sigma_threshold* standard deviations from the mean (default 2.0σ).
The absolute sigma distance is then mapped to a severity level:

  * sigma < 1.5  → "low"       (unusual but within normal variance)
  * sigma 1.5–2.5 → "medium"    (potentially anomalous)
  * sigma 2.5–4.0 → "high"      (likely anomalous)
  * sigma > 4.0   → "critical"  (almost certainly anomalous)

Phase 2 authority level is 1 (safe ops: restart, cache clear, notify), so
anomaly alerts produced here can trigger automated remediation through the
PermissionGate — but only for approved safe actions.

Pipeline position: this module sits in the **Analyze** stage, consuming
``Observation`` objects produced by the **Observe** stage (``observer.py``).
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from marketmate.core.logger import get_logger
from marketmate.mate_ops.observer import Observation

log = get_logger("mate_ops.anomaly_detector")


# ─── Anomaly Alert ────────────────────────────────────────────────────────────

@dataclass
class AnomalyAlert:
    """
    A single detected anomaly — one metric of one service deviating
    from its established baseline.

    Attributes:
        service:       The originating service (e.g. "api", "redis").
        metric:        The specific metric name (e.g. "latency_ms").
        current_value: The observed value that triggered the anomaly.
        baseline_mean: Rolling mean of the metric at detection time.
        baseline_std:  Rolling standard deviation at detection time.
        sigma_distance: Absolute number of standard deviations from the mean.
        severity:      Mapped severity: "low", "medium", "high", or "critical".
        timestamp:     ISO 8601 timestamp of when the anomaly was detected.
    """

    service: str
    metric: str
    current_value: float
    baseline_mean: float
    baseline_std: float
    sigma_distance: float
    severity: str  # "low" | "medium" | "high" | "critical"
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )


# ─── Severity Helper ──────────────────────────────────────────────────────────

def _severity_for_sigma(sigma: float) -> str:
    """Map an absolute sigma distance to a severity label.

    Args:
        sigma: Absolute number of standard deviations from the mean.

    Returns:
        One of "low", "medium", "high", "critical".
    """
    if sigma < 1.5:
        return "low"
    if sigma < 2.5:
        return "medium"
    if sigma < 4.0:
        return "high"
    return "critical"


# ─── Rolling Baseline ─────────────────────────────────────────────────────────

class RollingBaseline:
    """
    A bounded statistical baseline for a single metric.

    Maintains a sliding window of recent numeric values in a ``deque`` and
    computes rolling statistics on demand.  Designed to be lightweight —
    no external dependencies, O(window) recomputation.

    The window size trades responsiveness for stability:
      * Small window (e.g. 20)  → fast adaptation, noisy baseline
      * Large window (e.g. 500) → stable baseline, slow to reflect trends
      * Default 100 is a practical middle ground for minute-level telemetry

    Args:
        window: Maximum number of recent values to retain.
    """

    def __init__(self, window: int = 100) -> None:
        self._window = window
        self._values: deque[float] = deque(maxlen=window)

    # ── Mutators ───────────────────────────────────────────────────────────

    def add(self, value: float) -> None:
        """Add a new observation value and trim to window size.

        The ``deque(maxlen=…)`` handles trimming automatically, but we
        keep the method name explicit for readability.

        Args:
            value: The numeric metric value to record.
        """
        self._values.append(value)

    # ── Statistics ─────────────────────────────────────────────────────────

    def stats(self) -> Dict[str, Any]:
        """Return current baseline statistics as a dictionary.

        If fewer than 2 data points have been recorded, ``std_dev`` and
        ``percentile_95`` will be ``0.0`` (degenerate case).

        Returns:
            Dict with keys: count, mean, std_dev, min, max, percentile_95.
        """
        n = len(self._values)
        if n == 0:
            return {
                "count": 0,
                "mean": 0.0,
                "std_dev": 0.0,
                "min": 0.0,
                "max": 0.0,
                "percentile_95": 0.0,
            }

        values = list(self._values)
        mean = sum(values) / n

        if n < 2:
            return {
                "count": n,
                "mean": mean,
                "std_dev": 0.0,
                "min": mean,
                "max": mean,
                "percentile_95": mean,
            }

        variance = sum((v - mean) ** 2 for v in values) / (n - 1)
        std_dev = math.sqrt(variance)
        sorted_vals = sorted(values)
        p95_idx = min(int(math.ceil(0.95 * n)) - 1, n - 1)

        return {
            "count": n,
            "mean": round(mean, 4),
            "std_dev": round(std_dev, 4),
            "min": round(sorted_vals[0], 4),
            "max": round(sorted_vals[-1], 4),
            "percentile_95": round(sorted_vals[p95_idx], 4),
        }

    # ── Anomaly Check ──────────────────────────────────────────────────────

    def is_anomaly(self, value: float, sigma_threshold: float = 2.0) -> bool:
        """Determine whether *value* is anomalous relative to the baseline.

        A value is flagged if its absolute deviation from the mean exceeds
        *sigma_threshold* standard deviations.  If the baseline has fewer
        than 2 data points (std_dev ≈ 0), no anomaly can be detected and
        the method returns ``False`` — we cannot judge without a baseline.

        Args:
            value:           The metric value to test.
            sigma_threshold: Number of standard deviations that constitute
                             an anomaly.  Default 2.0 (≈ 95th percentile
                             under normal distribution).

        Returns:
            ``True`` if the value exceeds the threshold; ``False`` otherwise.
        """
        n = len(self._values)
        if n < 2:
            return False

        s = self.stats()
        std_dev = s["std_dev"]
        if std_dev == 0.0:
            # All values are identical — any different value is an anomaly
            # only if it differs from the constant baseline.
            return value != s["mean"]

        sigma_distance = abs(value - s["mean"]) / std_dev
        return sigma_distance > sigma_threshold

    @property
    def count(self) -> int:
        """Number of data points currently in the window."""
        return len(self._values)


# ─── Service Baseline ─────────────────────────────────────────────────────────

# Mapping from service name to the metric keys we extract from Observation.details.
# Prometheus has nested metrics inside a "metrics" sub-dict.
_SERVICE_METRICS: Dict[str, List[str]] = {
    "api": ["latency_ms", "status_code"],
    "ollama": ["latency_ms", "model_count"],
    "redis": ["latency_ms", "connected_clients"],
    "mongodb": ["latency_ms"],
    "telegram_bot": ["latency_ms"],
    "prometheus": ["latency_ms", "api_request_rate", "api_error_rate", "api_p95_latency"],
}


class ServiceBaseline:
    """
    Manages per-metric rolling baselines for a single service.

    Each service emits multiple metrics (e.g. latency_ms, status_code).
    This class maintains one ``RollingBaseline`` per metric and provides
    methods to ingest observations and check for anomalies.

    For the *prometheus* service, nested metrics inside
    ``observation.details["metrics"]`` are also tracked.

    Args:
        service_name: Identifier for the service (e.g. "api", "redis").
        window:       Rolling window size passed to each ``RollingBaseline``.
        sigma_threshold: Default sigma threshold for anomaly checks.
    """

    def __init__(
        self,
        service_name: str,
        window: int = 100,
        sigma_threshold: float = 2.0,
    ) -> None:
        self._service_name = service_name
        self._window = window
        self._sigma_threshold = sigma_threshold
        self._baselines: Dict[str, RollingBaseline] = {}

    # ── Internal helpers ───────────────────────────────────────────────────

    def _get_baseline(self, metric: str) -> RollingBaseline:
        """Return (or create) the RollingBaseline for a given metric."""
        if metric not in self._baselines:
            self._baselines[metric] = RollingBaseline(window=self._window)
        return self._baselines[metric]

    def _extract_metrics(self, observation: Observation) -> Dict[str, float]:
        """Extract numeric metrics from an Observation's details dict.

        For services other than prometheus, metrics are looked up directly
        in ``observation.details``.  For prometheus, additional metrics are
        extracted from the nested ``details["metrics"]`` dict.

        Non-numeric or missing values are silently skipped.

        Args:
            observation: The observation to extract from.

        Returns:
            Dict mapping metric names to their float values.
        """
        extracted: Dict[str, float] = {}
        details = observation.details or {}
        metric_keys = _SERVICE_METRICS.get(self._service_name, [])

        for key in metric_keys:
            # Prometheus nests additional metrics under "metrics"
            if self._service_name == "prometheus" and key not in ("latency_ms",):
                nested = details.get("metrics", {})
                raw = nested.get(key)
            else:
                raw = details.get(key)

            if raw is not None:
                try:
                    extracted[key] = float(raw)
                except (TypeError, ValueError):
                    # Skip non-numeric values (e.g. "no_data", "N/A")
                    pass

        return extracted

    # ── Public API ─────────────────────────────────────────────────────────

    def record_observation(self, observation: Observation) -> None:
        """Extract metrics from an observation and add to appropriate baselines.

        This is used during both the warm-up (learning) phase and normal
        detection.  Only numeric values that match known metric keys are
        recorded.

        Args:
            observation: An Observation with a ``source`` matching this service
                         and a ``details`` dict containing metric values.
        """
        metrics = self._extract_metrics(observation)
        for metric_name, value in metrics.items():
            baseline = self._get_baseline(metric_name)
            baseline.add(value)

    def check_anomaly(self, observation: Observation) -> List[AnomalyAlert]:
        """Compare an observation against baselines and return anomaly alerts.

        Each metric extracted from the observation is compared to its
        rolling baseline.  If the value exceeds the sigma threshold, an
        ``AnomalyAlert`` is generated.

        Metrics that have insufficient baseline data (fewer than 2 points)
        are skipped — we cannot reliably detect anomalies without a baseline.

        Args:
            observation: The observation to evaluate.

        Returns:
            List of ``AnomalyAlert`` for every metric that is anomalous.
            Empty list if no anomalies are detected.
        """
        alerts: List[AnomalyAlert] = []
        metrics = self._extract_metrics(observation)
        timestamp = observation.timestamp or datetime.now(timezone.utc).isoformat()

        for metric_name, current_value in metrics.items():
            baseline = self._get_baseline(metric_name)

            if baseline.count < 2:
                # Not enough data to judge — skip
                continue

            s = baseline.stats()
            std_dev = s["std_dev"]

            if std_dev == 0.0:
                # Degenerate baseline: all values identical.
                # A different value is infinitely far in sigma terms.
                if current_value != s["mean"]:
                    sigma_distance = float("inf")
                else:
                    continue
            else:
                sigma_distance = abs(current_value - s["mean"]) / std_dev

            if sigma_distance > self._sigma_threshold:
                severity = _severity_for_sigma(sigma_distance)
                alerts.append(
                    AnomalyAlert(
                        service=self._service_name,
                        metric=metric_name,
                        current_value=current_value,
                        baseline_mean=s["mean"],
                        baseline_std=std_dev,
                        sigma_distance=round(sigma_distance, 4),
                        severity=severity,
                        timestamp=timestamp,
                    )
                )

        return alerts

    def baseline_count(self) -> int:
        """Return the minimum number of data points across all metrics.

        Used to determine warm-up readiness: if any metric has fewer
        than the required minimum, the service is not yet warmed up.
        """
        if not self._baselines:
            return 0
        return min(b.count for b in self._baselines.values())

    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """Return baseline statistics for every tracked metric.

        Returns:
            Dict mapping metric names to their ``RollingBaseline.stats()``
            dictionaries.
        """
        return {metric: bl.stats() for metric, bl in self._baselines.items()}


# ─── Anomaly Detector ─────────────────────────────────────────────────────────

# Minimum data points per service required before we consider the detector
# "warmed up" and ready for production anomaly detection.
_WARMUP_MINIMUM = 10


class AnomalyDetector:
    """
    Main entry point for statistical anomaly detection in MATE-Ops.

    Maintains a ``ServiceBaseline`` for every known service and provides
    a high-level API to:

      1. **Learn** — feed healthy observations during a warm-up phase to
         establish baselines.
      2. **Detect** — process new observations and flag anomalies.
      3. **Report** — retrieve baseline statistics for dashboards / alerting.

    Typical usage::

        detector = AnomalyDetector()

        # Warm-up: feed historical healthy observations
        detector.learn(healthy_observations)

        if detector.is_warmed_up:
            # Now detect anomalies in live observations
            alerts = detector.process_observations(live_observations)

    Args:
        window:           Rolling window size for each metric baseline.
        sigma_threshold:  Default sigma threshold for anomaly detection.
    """

    def __init__(
        self,
        window: int = 100,
        sigma_threshold: float = 2.0,
    ) -> None:
        self._window = window
        self._sigma_threshold = sigma_threshold
        self._service_baselines: Dict[str, ServiceBaseline] = {}
        self._known_services: List[str] = list(_SERVICE_METRICS.keys())

        # Pre-create baselines for all known services
        for service in self._known_services:
            self._service_baselines[service] = ServiceBaseline(
                service_name=service,
                window=window,
                sigma_threshold=sigma_threshold,
            )

    # ── Learning (Warm-Up) ─────────────────────────────────────────────────

    def learn(self, observations: List[Observation]) -> None:
        """Feed healthy observations to build baselines (warm-up phase).

        During warm-up, observations are recorded into rolling baselines
        but no anomaly detection is performed.  This allows the detector
        to establish what "normal" looks like before it starts flagging
        deviations.

        Call this method with historical or known-good observations before
        enabling live anomaly detection.  At least ``_WARMUP_MINIMUM``
        observations per service are recommended for meaningful baselines.

        Args:
            observations: A list of Observation objects, typically from
                          healthy operational periods.
        """
        for obs in observations:
            baseline = self._service_baselines.get(obs.source)
            if baseline is not None:
                baseline.record_observation(obs)
            else:
                # Unknown service — create a baseline on the fly
                new_baseline = ServiceBaseline(
                    service_name=obs.source,
                    window=self._window,
                    sigma_threshold=self._sigma_threshold,
                )
                new_baseline.record_observation(obs)
                self._service_baselines[obs.source] = new_baseline
                if obs.source not in self._known_services:
                    self._known_services.append(obs.source)
                log.debug(
                    "anomaly_detector_new_service",
                    service=obs.source,
                    action="baseline_created_on_learn",
                )

        log.info(
            "anomaly_detector_learn_complete",
            observations_processed=len(observations),
            services_tracked=len(self._service_baselines),
        )

    # ── Detection ──────────────────────────────────────────────────────────

    def process_observations(
        self, observations: List[Observation]
    ) -> List[AnomalyAlert]:
        """Process a batch of observations and return all detected anomalies.

        Each observation is:
          1. Recorded into its service's rolling baseline (baseline stays
             current even as we detect anomalies).
          2. Compared against the existing baseline for anomaly detection.

        This dual behaviour ensures the baseline continuously adapts to
        slow trends while still catching sudden spikes.

        Args:
            observations: A list of Observation objects to evaluate.

        Returns:
            A flat list of ``AnomalyAlert`` objects for every metric that
            triggered an anomaly across all observations.
        """
        all_alerts: List[AnomalyAlert] = []

        for obs in observations:
            baseline = self._service_baselines.get(obs.source)
            if baseline is None:
                # Auto-discover unknown services
                baseline = ServiceBaseline(
                    service_name=obs.source,
                    window=self._window,
                    sigma_threshold=self._sigma_threshold,
                )
                self._service_baselines[obs.source] = baseline
                if obs.source not in self._known_services:
                    self._known_services.append(obs.source)
                log.debug(
                    "anomaly_detector_new_service",
                    service=obs.source,
                    action="baseline_created_on_process",
                )

            # Always record the observation to keep the baseline current
            baseline.record_observation(obs)

            # Check for anomalies (requires >= 2 prior data points)
            alerts = baseline.check_anomaly(obs)
            all_alerts.extend(alerts)

        if all_alerts:
            log.info(
                "anomaly_detector_alerts",
                total_observations=len(observations),
                anomalies_detected=len(all_alerts),
                critical=sum(1 for a in all_alerts if a.severity == "critical"),
                high=sum(1 for a in all_alerts if a.severity == "high"),
                medium=sum(1 for a in all_alerts if a.severity == "medium"),
                low=sum(1 for a in all_alerts if a.severity == "low"),
            )

        return all_alerts

    # ── Reporting ──────────────────────────────────────────────────────────

    def get_baseline_stats(self) -> Dict[str, Dict[str, Any]]:
        """Return baseline statistics for all tracked services.

        Useful for dashboard rendering, debugging, and understanding
        what the detector considers "normal".

        Returns:
            Nested dict: ``{service_name: {metric_name: stats_dict}}``.
        """
        return {
            service: sb.get_stats()
            for service, sb in self._service_baselines.items()
        }

    # ── Warm-Up Check ──────────────────────────────────────────────────────

    @property
    def is_warmed_up(self) -> bool:
        """Whether all known services have enough data for meaningful baselines.

        Returns ``True`` only when *every* tracked service has at least
        ``_WARMUP_MINIMUM`` (default 10) data points across all of its
        metrics.  Until warmed up, anomaly detection may produce unreliable
        results due to insufficient baseline data.
        """
        if not self._service_baselines:
            return False

        return all(
            sb.baseline_count() >= _WARMUP_MINIMUM
            for sb in self._service_baselines.values()
        )
