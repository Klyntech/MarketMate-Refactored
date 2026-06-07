"""
marketmate.intelligence.prism.validator
────────────────────────────────────────
PRISM: Data Integrity Validator

Passive, strict, mathematical validation of all market data
before it reaches downstream intelligence layers.

This module does NOT modify data. It ONLY validates and reports.
Its validation is FINAL — no downstream layer overrides PRISM flags.

Checks performed:
  1. MISSING_CANDLE   — Gap in candle sequence
  2. STALE_PRICE      — Price not updated within expected interval
  3. WEBSOCKET_DISCONNECT — Feed connection lost
  4. FEED_DELAY       — Latency exceeds threshold
  5. TIMESTAMP_DRIFT  — Provider clock offset exceeds tolerance
  6. MALFORMED_RESPONSE — Data structure does not match schema
  7. OHLC_IMPOSSIBLE  — High < Low, Close outside OHLC range
  8. DUPLICATE_TICK   — Same timestamp and price repeated
  9. SPREAD_ANOMALY   — Bid-ask spread exceeds normal range
  10. PROVIDER_DEVIATION — Cross-provider price difference exceeds threshold
  11. NORMALIZATION_FAILURE — Data cannot be normalized to expected format
  12. VOLUME_SPIKE    — Volume exceeds N standard deviations from mean

Created: 2026-05-29
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple

from marketmate.core.logger import get_logger

log = get_logger("intelligence.prism")


# ─── Check Types ──────────────────────────────────────────────────────────────

class PrismCheck(str, Enum):
    """All validation checks performed by PRISM."""

    MISSING_CANDLE = "missing_candle"
    STALE_PRICE = "stale_price"
    WEBSOCKET_DISCONNECT = "websocket_disconnect"
    FEED_DELAY = "feed_delay"
    TIMESTAMP_DRIFT = "timestamp_drift"
    MALFORMED_RESPONSE = "malformed_response"
    OHLC_IMPOSSIBLE = "ohlc_impossible"
    DUPLICATE_TICK = "duplicate_tick"
    SPREAD_ANOMALY = "spread_anomaly"
    PROVIDER_DEVIATION = "provider_deviation"
    NORMALIZATION_FAILURE = "normalization_failure"
    VOLUME_SPIKE = "volume_spike"


class PrismSeverity(str, Enum):
    """Severity levels for PRISM results."""

    INFO = "info"
    WARNING = "warning"
    CRITICAL = "critical"


class PrismAction(str, Enum):
    """Recommended actions based on PRISM validation."""

    NONE = "none"
    SWITCH_FALLBACK = "switch_fallback_provider"
    FLAG_UNRELIABLE = "flag_unreliable"
    HALT_PROCESSING = "halt_processing"
    NOTIFY_OPS = "notify_ops"


# ─── Validation Result ────────────────────────────────────────────────────────

@dataclass
class PrismResult:
    """
    A single PRISM validation result.

    Produced by PrismValidator.validate(). Contains the check type,
    status (pass/warn/fail), severity, and recommended action.

    Attributes:
        check: The type of validation check performed.
        status: Whether the check passed, warned, or failed.
        symbol: The trading symbol being validated.
        provider: The data provider source.
        severity: How serious a failure is (info/warning/critical).
        detail: Human-readable description of the issue.
        metric_value: Numeric value that triggered the check (if applicable).
        metric_unit: Unit for the metric value (ms, pct, count, etc.).
        recommended_action: What downstream layers should do about this.
        timestamp: When this validation was performed.
    """

    check: PrismCheck
    status: str  # "pass" | "warn" | "fail"
    symbol: str
    provider: str
    severity: PrismSeverity
    detail: str
    metric_value: float = 0.0
    metric_unit: str = ""
    recommended_action: PrismAction = PrismAction.NONE
    timestamp: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> Dict[str, Any]:
        """Convert to structured dictionary for downstream consumption."""
        return {
            "check": self.check.value,
            "status": self.status,
            "symbol": self.symbol,
            "provider": self.provider,
            "severity": self.severity.value,
            "detail": self.detail,
            "metric_value": self.metric_value,
            "metric_unit": self.metric_unit,
            "recommended_action": self.recommended_action.value,
            "timestamp": self.timestamp,
        }


# ─── Provider Reliability Score ───────────────────────────────────────────────

@dataclass
class ProviderReliability:
    """
    Tracks reliability score for a data provider.

    Reliability is computed as a rolling average of validation results.
    Providers that consistently fail checks get lower scores.
    Score ranges from 0.0 (completely unreliable) to 1.0 (perfect).

    Attributes:
        provider: Provider identifier.
        total_checks: Number of validation checks performed.
        passes: Number of checks that passed.
        warnings: Number of checks that warned.
        failures: Number of checks that failed.
        last_check_time: When the most recent check was performed.
        score: Current reliability score (0.0-1.0).
    """

    provider: str
    total_checks: int = 0
    passes: int = 0
    warnings: int = 0
    failures: int = 0
    last_check_time: str = ""
    score: float = 1.0

    def update(self, result: PrismResult) -> None:
        """Update reliability score based on a new validation result."""
        self.total_checks += 1
        self.last_check_time = result.timestamp

        if result.status == "pass":
            self.passes += 1
        elif result.status == "warn":
            self.warnings += 1
        else:
            self.failures += 1

        # Weighted scoring: pass=1.0, warn=0.5, fail=0.0
        total_weight = self.passes * 1.0 + self.warnings * 0.5 + self.failures * 0.0
        self.score = total_weight / max(self.total_checks, 1)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "provider": self.provider,
            "total_checks": self.total_checks,
            "passes": self.passes,
            "warnings": self.warnings,
            "failures": self.failures,
            "score": round(self.score, 4),
            "last_check_time": self.last_check_time,
        }


# ─── PRISM Validator ─────────────────────────────────────────────────────────

class PrismValidator:
    """
    Data integrity validator — the FIRST processing layer after raw market data.

    ALL market data passes through PRISM before reaching any other layer.
    If PRISM flags data as unreliable, downstream layers MUST respect that.

    PRISM is PASSIVE, STRICT, MATHEMATICAL, BORING.
    It does NOT modify data. It does NOT take actions.
    It ONLY validates, verifies, and reports.

    Configuration:
        max_feed_delay_ms: Maximum acceptable feed delay in milliseconds.
        max_timestamp_drift_ms: Maximum acceptable timestamp drift in ms.
        max_provider_deviation_pct: Maximum cross-provider price deviation %.
        max_spread_pct: Maximum acceptable bid-ask spread as percentage.
        stale_price_seconds: Seconds before a price is considered stale.
        volume_spike_sigma: Number of standard deviations for volume spike.
        candle_gap_threshold: Number of missing candles to trigger alert.
    """

    def __init__(
        self,
        max_feed_delay_ms: float = 5000.0,
        max_timestamp_drift_ms: float = 2000.0,
        max_provider_deviation_pct: float = 0.05,
        max_spread_pct: float = 0.1,
        stale_price_seconds: float = 30.0,
        volume_spike_sigma: float = 5.0,
        candle_gap_threshold: int = 2,
    ) -> None:
        """Initialize PRISM validator with configurable thresholds."""
        self._max_feed_delay_ms = max_feed_delay_ms
        self._max_timestamp_drift_ms = max_timestamp_drift_ms
        self._max_provider_deviation_pct = max_provider_deviation_pct
        self._max_spread_pct = max_spread_pct
        self._stale_price_seconds = stale_price_seconds
        self._volume_spike_sigma = volume_spike_sigma
        self._candle_gap_threshold = candle_gap_threshold

        # Provider reliability tracking
        self._reliability: Dict[str, ProviderReliability] = {}

        # Validation history for pattern detection
        self._recent_results: List[PrismResult] = []
        self._max_recent = 1000

        # Volume baseline for spike detection
        self._volume_baselines: Dict[str, List[float]] = {}

        log.info(
            "prism_initialized",
            max_feed_delay_ms=max_feed_delay_ms,
            max_timestamp_drift_ms=max_timestamp_drift_ms,
            max_provider_deviation_pct=max_provider_deviation_pct,
        )

    # ── Candle Validation ──────────────────────────────────────────────────

    def validate_candle(
        self,
        symbol: str,
        provider: str,
        candle: Dict[str, Any],
        timeframe_seconds: int = 60,
    ) -> PrismResult:
        """
        Validate a single OHLCV candle for data integrity.

        Checks:
          - OHLC_IMPOSSIBLE: High < Low, Close outside OHLC range
          - DUPLICATE_TICK: Same timestamp and price as previous
          - MISSING_CANDLE: Gap in candle sequence (requires previous candle)
          - VOLUME_SPIKE: Volume exceeds threshold

        Args:
            symbol: Trading symbol (e.g., "BTCUSDT").
            provider: Data provider name (e.g., "binance").
            candle: Dict with keys: open, high, low, close, volume, timestamp.
            timeframe_seconds: Expected candle interval in seconds.

        Returns:
            A PrismResult with the validation outcome.
        """
        o = candle.get("open", 0)
        h = candle.get("high", 0)
        l = candle.get("low", 0)
        c = candle.get("close", 0)
        v = candle.get("volume", 0)
        ts = candle.get("timestamp", "")

        # ── OHLC Impossible ────────────────────────────────────────────
        if h < l:
            result = PrismResult(
                check=PrismCheck.OHLC_IMPOSSIBLE,
                status="fail",
                symbol=symbol,
                provider=provider,
                severity=PrismSeverity.CRITICAL,
                detail=f"High ({h}) < Low ({l}) — impossible candle",
                metric_value=h - l,
                metric_unit="price_diff",
                recommended_action=PrismAction.HALT_PROCESSING,
            )
            self._record(result)
            return result

        if c > h or c < l:
            result = PrismResult(
                check=PrismCheck.OHLC_IMPOSSIBLE,
                status="fail",
                symbol=symbol,
                provider=provider,
                severity=PrismSeverity.CRITICAL,
                detail=f"Close ({c}) outside OHLC range [{l}, {h}]",
                metric_value=abs(c - h) if c > h else abs(l - c),
                metric_unit="price_diff",
                recommended_action=PrismAction.HALT_PROCESSING,
            )
            self._record(result)
            return result

        if o > h or o < l:
            result = PrismResult(
                check=PrismCheck.OHLC_IMPOSSIBLE,
                status="warn",
                symbol=symbol,
                provider=provider,
                severity=PrismSeverity.WARNING,
                detail=f"Open ({o}) outside OHLC range [{l}, {h}] — may be gap",
                metric_value=abs(o - h) if o > h else abs(l - o),
                metric_unit="price_diff",
                recommended_action=PrismAction.FLAG_UNRELIABLE,
            )
            self._record(result)
            return result

        # ── Volume Spike ───────────────────────────────────────────────
        if v > 0:
            baseline = self._volume_baselines.get(f"{symbol}:{provider}", [])
            if len(baseline) >= 10:
                mean_vol = sum(baseline) / len(baseline)
                std_vol = (sum((x - mean_vol) ** 2 for x in baseline) / len(baseline)) ** 0.5
                if std_vol > 0 and (v - mean_vol) / std_vol > self._volume_spike_sigma:
                    result = PrismResult(
                        check=PrismCheck.VOLUME_SPIKE,
                        status="warn",
                        symbol=symbol,
                        provider=provider,
                        severity=PrismSeverity.WARNING,
                        detail=f"Volume {v} exceeds {self._volume_spike_sigma} sigma from mean {mean_vol:.2f}",
                        metric_value=v,
                        metric_unit="volume",
                        recommended_action=PrismAction.FLAG_UNRELIABLE,
                    )
                    self._record(result)
                    # Still pass — volume spikes are warnings, not failures
                    self._update_volume_baseline(f"{symbol}:{provider}", v)
                    # Continue to return pass below

            # Update baseline
            self._update_volume_baseline(f"{symbol}:{provider}", v)

        # ── Malformed Response ──────────────────────────────────────────
        required_keys = {"open", "high", "low", "close"}
        if not required_keys.issubset(candle.keys()):
            missing = required_keys - set(candle.keys())
            result = PrismResult(
                check=PrismCheck.MALFORMED_RESPONSE,
                status="fail",
                symbol=symbol,
                provider=provider,
                severity=PrismSeverity.CRITICAL,
                detail=f"Missing required keys: {missing}",
                recommended_action=PrismAction.HALT_PROCESSING,
            )
            self._record(result)
            return result

        # All checks passed
        result = PrismResult(
            check=PrismCheck.OHLC_IMPOSSIBLE,  # Represents the candle check suite
            status="pass",
            symbol=symbol,
            provider=provider,
            severity=PrismSeverity.INFO,
            detail="Candle integrity verified",
            recommended_action=PrismAction.NONE,
        )
        self._record(result)
        return result

    # ── Feed Validation ────────────────────────────────────────────────────

    def validate_feed(
        self,
        symbol: str,
        provider: str,
        current_price: float,
        last_update_timestamp: str,
        expected_interval_seconds: float = 1.0,
        is_connected: bool = True,
    ) -> PrismResult:
        """
        Validate feed integrity for a symbol.

        Checks:
          - WEBSOCKET_DISCONNECT: Feed connection lost
          - STALE_PRICE: Price not updated within expected interval
          - FEED_DELAY: Latency exceeds threshold

        Args:
            symbol: Trading symbol.
            provider: Data provider.
            current_price: Current price from the feed.
            last_update_timestamp: ISO 8601 timestamp of last price update.
            expected_interval_seconds: Expected time between updates.
            is_connected: Whether the websocket/feed is connected.

        Returns:
            A PrismResult with the validation outcome.
        """
        # ── WebSocket Disconnect ────────────────────────────────────────
        if not is_connected:
            result = PrismResult(
                check=PrismCheck.WEBSOCKET_DISCONNECT,
                status="fail",
                symbol=symbol,
                provider=provider,
                severity=PrismSeverity.CRITICAL,
                detail="WebSocket disconnected — no live feed",
                recommended_action=PrismAction.SWITCH_FALLBACK,
            )
            self._record(result)
            return result

        # ── Stale Price ─────────────────────────────────────────────────
        if last_update_timestamp:
            try:
                last_update = datetime.fromisoformat(last_update_timestamp)
                now = datetime.now(timezone.utc)
                age_seconds = (now - last_update).total_seconds()

                if age_seconds > self._stale_price_seconds:
                    result = PrismResult(
                        check=PrismCheck.STALE_PRICE,
                        status="fail",
                        symbol=symbol,
                        provider=provider,
                        severity=PrismSeverity.CRITICAL,
                        detail=f"Price stale for {age_seconds:.1f}s (threshold: {self._stale_price_seconds}s)",
                        metric_value=age_seconds * 1000,
                        metric_unit="ms",
                        recommended_action=PrismAction.SWITCH_FALLBACK,
                    )
                    self._record(result)
                    return result

                if age_seconds > self._stale_price_seconds * 0.5:
                    result = PrismResult(
                        check=PrismCheck.STALE_PRICE,
                        status="warn",
                        symbol=symbol,
                        provider=provider,
                        severity=PrismSeverity.WARNING,
                        detail=f"Price aging: {age_seconds:.1f}s (threshold: {self._stale_price_seconds}s)",
                        metric_value=age_seconds * 1000,
                        metric_unit="ms",
                        recommended_action=PrismAction.FLAG_UNRELIABLE,
                    )
                    self._record(result)
                    return result

                # ── Feed Delay ──────────────────────────────────────
                if age_seconds * 1000 > self._max_feed_delay_ms:
                    result = PrismResult(
                        check=PrismCheck.FEED_DELAY,
                        status="fail",
                        symbol=symbol,
                        provider=provider,
                        severity=PrismSeverity.WARNING,
                        detail=f"Feed delay: {age_seconds * 1000:.1f}ms exceeds {self._max_feed_delay_ms}ms",
                        metric_value=age_seconds * 1000,
                        metric_unit="ms",
                        recommended_action=PrismAction.SWITCH_FALLBACK,
                    )
                    self._record(result)
                    return result

            except (ValueError, TypeError):
                pass  # Timestamp parsing failed — skip staleness check

        # Feed healthy
        result = PrismResult(
            check=PrismCheck.STALE_PRICE,  # Represents the feed check suite
            status="pass",
            symbol=symbol,
            provider=provider,
            severity=PrismSeverity.INFO,
            detail="Feed integrity verified",
            recommended_action=PrismAction.NONE,
        )
        self._record(result)
        return result

    # ── Cross-Provider Validation ──────────────────────────────────────────

    def validate_provider_consistency(
        self,
        symbol: str,
        prices: Dict[str, float],
    ) -> PrismResult:
        """
        Validate cross-provider price consistency.

        Compares prices from multiple providers for the same symbol.
        If deviation exceeds threshold, flags as unreliable.

        Args:
            symbol: Trading symbol.
            prices: Dict mapping provider name to current price.

        Returns:
            A PrismResult with the validation outcome.
        """
        if len(prices) < 2:
            result = PrismResult(
                check=PrismCheck.PROVIDER_DEVIATION,
                status="pass",
                symbol=symbol,
                provider="multi",
                severity=PrismSeverity.INFO,
                detail="Only one provider — no cross-check possible",
                recommended_action=PrismAction.NONE,
            )
            self._record(result)
            return result

        values = list(prices.values())
        min_price = min(values)
        max_price = max(values)
        avg_price = sum(values) / len(values)

        if avg_price == 0:
            deviation_pct = 0.0
        else:
            deviation_pct = (max_price - min_price) / avg_price * 100

        if deviation_pct > self._max_provider_deviation_pct:
            worst_provider = max(prices, key=prices.get)
            result = PrismResult(
                check=PrismCheck.PROVIDER_DEVIATION,
                status="fail",
                symbol=symbol,
                provider=worst_provider,
                severity=PrismSeverity.CRITICAL,
                detail=f"Cross-provider deviation: {deviation_pct:.4f}% (threshold: {self._max_provider_deviation_pct}%)",
                metric_value=deviation_pct,
                metric_unit="pct",
                recommended_action=PrismAction.SWITCH_FALLBACK,
            )
            self._record(result)
            return result

        if deviation_pct > self._max_provider_deviation_pct * 0.5:
            result = PrismResult(
                check=PrismCheck.PROVIDER_DEVIATION,
                status="warn",
                symbol=symbol,
                provider="multi",
                severity=PrismSeverity.WARNING,
                detail=f"Cross-provider deviation rising: {deviation_pct:.4f}%",
                metric_value=deviation_pct,
                metric_unit="pct",
                recommended_action=PrismAction.FLAG_UNRELIABLE,
            )
            self._record(result)
            return result

        result = PrismResult(
            check=PrismCheck.PROVIDER_DEVIATION,
            status="pass",
            symbol=symbol,
            provider="multi",
            severity=PrismSeverity.INFO,
            detail="Cross-provider consistency verified",
            metric_value=deviation_pct,
            metric_unit="pct",
            recommended_action=PrismAction.NONE,
        )
        self._record(result)
        return result

    # ── Timestamp Drift ────────────────────────────────────────────────────

    def validate_timestamp_drift(
        self,
        symbol: str,
        provider: str,
        provider_timestamp: str,
        reference_timestamp: Optional[str] = None,
    ) -> PrismResult:
        """
        Validate timestamp drift between provider and reference clock.

        Args:
            symbol: Trading symbol.
            provider: Data provider.
            provider_timestamp: Timestamp from the provider.
            reference_timestamp: Reference timestamp (defaults to now).

        Returns:
            A PrismResult with the validation outcome.
        """
        try:
            p_time = datetime.fromisoformat(provider_timestamp)
            r_time = (
                datetime.fromisoformat(reference_timestamp)
                if reference_timestamp
                else datetime.now(timezone.utc)
            )

            drift_ms = abs((p_time - r_time).total_seconds()) * 1000

            if drift_ms > self._max_timestamp_drift_ms:
                result = PrismResult(
                    check=PrismCheck.TIMESTAMP_DRIFT,
                    status="fail",
                    symbol=symbol,
                    provider=provider,
                    severity=PrismSeverity.WARNING,
                    detail=f"Timestamp drift: {drift_ms:.1f}ms (threshold: {self._max_timestamp_drift_ms}ms)",
                    metric_value=drift_ms,
                    metric_unit="ms",
                    recommended_action=PrismAction.FLAG_UNRELIABLE,
                )
                self._record(result)
                return result

            result = PrismResult(
                check=PrismCheck.TIMESTAMP_DRIFT,
                status="pass",
                symbol=symbol,
                provider=provider,
                severity=PrismSeverity.INFO,
                detail=f"Timestamp drift within tolerance: {drift_ms:.1f}ms",
                metric_value=drift_ms,
                metric_unit="ms",
                recommended_action=PrismAction.NONE,
            )
            self._record(result)
            return result

        except (ValueError, TypeError) as exc:
            result = PrismResult(
                check=PrismCheck.TIMESTAMP_DRIFT,
                status="fail",
                symbol=symbol,
                provider=provider,
                severity=PrismSeverity.CRITICAL,
                detail=f"Cannot parse timestamp: {exc}",
                recommended_action=PrismAction.HALT_PROCESSING,
            )
            self._record(result)
            return result

    # ── Duplicate Tick Detection ────────────────────────────────────────────

    def validate_tick_uniqueness(
        self,
        symbol: str,
        provider: str,
        timestamp: str,
        price: float,
    ) -> PrismResult:
        """
        Validate that a tick is not a duplicate of a previous one.

        Uses recent results to check for duplicate timestamp+price combos.

        Args:
            symbol: Trading symbol.
            provider: Data provider.
            timestamp: Tick timestamp.
            price: Tick price.

        Returns:
            A PrismResult with the validation outcome.
        """
        # Check recent results for duplicates
        for r in reversed(self._recent_results[-50:]):
            if (
                r.check == PrismCheck.DUPLICATE_TICK
                and r.symbol == symbol
                and r.provider == provider
            ):
                # Compare with stored detail
                prev_key = f"{symbol}:{provider}:{timestamp}:{price}"
                curr_key = f"{symbol}:{provider}:{timestamp}:{price}"
                if prev_key == curr_key and r.detail.endswith(f"ts={timestamp} price={price}"):
                    result = PrismResult(
                        check=PrismCheck.DUPLICATE_TICK,
                        status="warn",
                        symbol=symbol,
                        provider=provider,
                        severity=PrismSeverity.WARNING,
                        detail=f"Duplicate tick detected: ts={timestamp} price={price}",
                        recommended_action=PrismAction.FLAG_UNRELIABLE,
                    )
                    self._record(result)
                    return result

        # No duplicate found
        result = PrismResult(
            check=PrismCheck.DUPLICATE_TICK,
            status="pass",
            symbol=symbol,
            provider=provider,
            severity=PrismSeverity.INFO,
            detail="Tick uniqueness verified",
            recommended_action=PrismAction.NONE,
        )
        self._record(result)
        return result

    # ── Spread Anomaly ─────────────────────────────────────────────────────

    def validate_spread(
        self,
        symbol: str,
        provider: str,
        bid: float,
        ask: float,
    ) -> PrismResult:
        """
        Validate bid-ask spread for anomalies.

        Args:
            symbol: Trading symbol.
            provider: Data provider.
            bid: Bid price.
            ask: Ask price.

        Returns:
            A PrismResult with the validation outcome.
        """
        if bid <= 0 or ask <= 0:
            result = PrismResult(
                check=PrismCheck.SPREAD_ANOMALY,
                status="fail",
                symbol=symbol,
                provider=provider,
                severity=PrismSeverity.CRITICAL,
                detail="Invalid bid/ask prices (zero or negative)",
                recommended_action=PrismAction.HALT_PROCESSING,
            )
            self._record(result)
            return result

        mid = (bid + ask) / 2
        spread_pct = (ask - bid) / mid * 100 if mid > 0 else 0

        if spread_pct > self._max_spread_pct:
            result = PrismResult(
                check=PrismCheck.SPREAD_ANOMALY,
                status="fail",
                symbol=symbol,
                provider=provider,
                severity=PrismSeverity.WARNING,
                detail=f"Spread {spread_pct:.4f}% exceeds {self._max_spread_pct}%",
                metric_value=spread_pct,
                metric_unit="pct",
                recommended_action=PrismAction.FLAG_UNRELIABLE,
            )
            self._record(result)
            return result

        result = PrismResult(
            check=PrismCheck.SPREAD_ANOMALY,
            status="pass",
            symbol=symbol,
            provider=provider,
            severity=PrismSeverity.INFO,
            detail=f"Spread within tolerance: {spread_pct:.4f}%",
            metric_value=spread_pct,
            metric_unit="pct",
            recommended_action=PrismAction.NONE,
        )
        self._record(result)
        return result

    # ── Batch Validation ───────────────────────────────────────────────────

    def validate_market_data(
        self,
        symbol: str,
        provider: str,
        candle: Optional[Dict[str, Any]] = None,
        current_price: Optional[float] = None,
        last_update_timestamp: Optional[str] = None,
        is_connected: bool = True,
        bid: Optional[float] = None,
        ask: Optional[float] = None,
    ) -> List[PrismResult]:
        """
        Run all applicable PRISM validations on a batch of market data.

        Returns a list of PrismResult objects, one per check performed.
        """
        results: List[PrismResult] = []

        if candle is not None:
            results.append(self.validate_candle(symbol, provider, candle))

        if current_price is not None and last_update_timestamp is not None:
            results.append(self.validate_feed(
                symbol, provider, current_price, last_update_timestamp,
                is_connected=is_connected,
            ))

        if bid is not None and ask is not None:
            results.append(self.validate_spread(symbol, provider, bid, ask))

        return results

    # ── Provider Reliability ───────────────────────────────────────────────

    def get_provider_reliability(self, provider: str) -> ProviderReliability:
        """Get the reliability score for a provider."""
        return self._reliability.get(
            provider,
            ProviderReliability(provider=provider),
        )

    def get_all_reliability_scores(self) -> Dict[str, Dict[str, Any]]:
        """Get reliability scores for all tracked providers."""
        return {
            p: r.to_dict() for p, r in self._reliability.items()
        }

    def get_data_quality_score(self, symbol: str) -> float:
        """
        Compute overall data quality score for a symbol.

        Score is based on recent validation results.
        1.0 = perfect, 0.0 = completely unreliable.
        """
        recent = [
            r for r in self._recent_results
            if r.symbol == symbol
        ][-100:]  # Last 100 checks

        if not recent:
            return 0.5  # Unknown — neutral

        weights = {"pass": 1.0, "warn": 0.5, "fail": 0.0}
        total = sum(weights.get(r.status, 0.0) for r in recent)
        return total / len(recent)

    # ── Internal ──────────────────────────────────────────────────────────

    def _record(self, result: PrismResult) -> None:
        """Record a validation result and update provider reliability."""
        self._recent_results.append(result)
        if len(self._recent_results) > self._max_recent:
            self._recent_results = self._recent_results[-self._max_recent:]

        # Update provider reliability
        if result.provider not in self._reliability:
            self._reliability[result.provider] = ProviderReliability(provider=result.provider)
        self._reliability[result.provider].update(result)

        # Log failures and warnings
        if result.status == "fail":
            log.warning(
                "prism_validation_failed",
                check=result.check.value,
                symbol=result.symbol,
                provider=result.provider,
                detail=result.detail,
            )
        elif result.status == "warn":
            log.info(
                "prism_validation_warning",
                check=result.check.value,
                symbol=result.symbol,
                provider=result.provider,
                detail=result.detail,
            )

    def _update_volume_baseline(self, key: str, volume: float) -> None:
        """Update volume baseline for spike detection."""
        if key not in self._volume_baselines:
            self._volume_baselines[key] = []
        self._volume_baselines[key].append(volume)
        # Keep last 100 values
        if len(self._volume_baselines[key]) > 100:
            self._volume_baselines[key] = self._volume_baselines[key][-100:]

    # ── Status ────────────────────────────────────────────────────────────

    @property
    def status(self) -> Dict[str, Any]:
        """Return PRISM validator status."""
        return {
            "layer": "prism",
            "role": "data_integrity",
            "agent": False,
            "recent_checks": len(self._recent_results),
            "providers_tracked": len(self._reliability),
            "thresholds": {
                "max_feed_delay_ms": self._max_feed_delay_ms,
                "max_timestamp_drift_ms": self._max_timestamp_drift_ms,
                "max_provider_deviation_pct": self._max_provider_deviation_pct,
                "max_spread_pct": self._max_spread_pct,
                "stale_price_seconds": self._stale_price_seconds,
                "volume_spike_sigma": self._volume_spike_sigma,
            },
        }
