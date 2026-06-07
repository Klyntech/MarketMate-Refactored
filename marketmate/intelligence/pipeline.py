"""
marketmate.intelligence.pipeline
────────────────────────────────
6-Layer Intelligence Pipeline Orchestrator

Orchestrates the complete data flow through all intelligence layers:

  RAW MARKET DATA → PRISM (data integrity) → VINNI (data monitoring)
  → ATLAS (market reasoning) → VANTA (validation + agent)
  → NOVA (user delivery) → Users/API/Telegram

  OPS runs parallel — infrastructure operations, keeping system alive.

Critical Rule: Each layer NEVER overlaps responsibilities.
If PRISM flags data as unreliable, downstream layers MUST respect that.
If VANTA halts trading, NOVA MUST communicate the halt.

Created: 2026-05-29
Phase: 3 (High Agency)
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from marketmate.core.logger import get_logger
from marketmate.intelligence.prism import PrismValidator, PrismResult
from marketmate.intelligence.vinni import VinniMonitor, VinniDiagnostic
from marketmate.intelligence.atlas import AtlasEngine, AtlasAnalysis
from marketmate.intelligence.nova import NovaLayer, NovaSummary
from marketmate.intelligence.vanta import VantaAgent, VantaValidation, VantaBuildPlan
from marketmate.intelligence.ops import OpsController, OpsAction, OpsResult

log = get_logger("intelligence.pipeline")


# ─── Pipeline Result ──────────────────────────────────────────────────────────

@dataclass
class PipelineResult:
    """
    Complete result from one pass through the intelligence pipeline.

    Contains outputs from every layer plus overall health assessment.
    """

    pipeline_id: str = ""
    started_at: str = ""
    completed_at: str = ""
    total_latency_ms: float = 0.0

    # Layer outputs
    prism_results: List[PrismResult] = field(default_factory=list)
    vinni_diagnostics: List[VinniDiagnostic] = field(default_factory=list)
    atlas_analysis: Optional[AtlasAnalysis] = None
    vanta_validations: List[VantaValidation] = field(default_factory=list)
    nova_summary: Optional[NovaSummary] = None

    # Overall assessment
    data_quality_score: float = 0.0
    trading_halted: bool = False
    risk_environment: str = "safe"  # "safe" | "caution" | "unsafe"
    overall_health: str = "ok"  # "ok" | "degraded" | "critical"

    # Layer latencies
    prism_latency_ms: float = 0.0
    vinni_latency_ms: float = 0.0
    atlas_latency_ms: float = 0.0
    vanta_latency_ms: float = 0.0
    nova_latency_ms: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for API/audit consumption."""
        return {
            "pipeline_id": self.pipeline_id,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "total_latency_ms": self.total_latency_ms,
            "data_quality_score": round(self.data_quality_score, 4),
            "trading_halted": self.trading_halted,
            "risk_environment": self.risk_environment,
            "overall_health": self.overall_health,
            "prism_checks": len(self.prism_results),
            "prism_failures": sum(1 for r in self.prism_results if r.status == "fail"),
            "vinni_diagnostics": len(self.vinni_diagnostics),
            "vinni_criticals": sum(
                1 for d in self.vinni_diagnostics if d.severity in ("error", "critical")
            ),
            "atlas_available": self.atlas_analysis is not None,
            "atlas_regime": self.atlas_analysis.regime if self.atlas_analysis else "unknown",
            "atlas_conviction": self.atlas_analysis.conviction if self.atlas_analysis else 0,
            "vanta_validations": len(self.vanta_validations),
            "vanta_criticals": sum(
                1 for v in self.vanta_validations if v.severity == "critical"
            ),
            "nova_available": self.nova_summary is not None,
            "layer_latencies": {
                "prism_ms": self.prism_latency_ms,
                "vinni_ms": self.vinni_latency_ms,
                "atlas_ms": self.atlas_latency_ms,
                "vanta_ms": self.vanta_latency_ms,
                "nova_ms": self.nova_latency_ms,
            },
        }


# ─── Intelligence Pipeline ────────────────────────────────────────────────────

class IntelligencePipeline:
    """
    Orchestrates the complete 6-layer intelligence pipeline.

    Data flows strictly:
      RAW DATA → PRISM → VINNI → ATLAS → VANTA → NOVA → Users

    OPS runs in parallel for infrastructure control.

    Usage:
        pipeline = IntelligencePipeline()
        result = await pipeline.process(
            symbol="BTCUSDT",
            market_data={...},
        )

    Each layer only receives the outputs of the previous layer,
    maintaining strict separation of responsibilities.
    """

    def __init__(
        self,
        prism: Optional[PrismValidator] = None,
        vinni: Optional[VinniMonitor] = None,
        atlas: Optional[AtlasEngine] = None,
        vanta: Optional[VantaAgent] = None,
        nova: Optional[NovaLayer] = None,
        ops: Optional[OpsController] = None,
    ) -> None:
        """Initialize with optional layer instances (defaults created if not provided)."""
        self._prism = prism or PrismValidator()
        self._vinni = vinni or VinniMonitor()
        self._atlas = atlas or AtlasEngine()
        self._vanta = vanta or VantaAgent()
        self._nova = nova or NovaLayer()
        self._ops = ops or OpsController()

        self._pipeline_count: int = 0

        log.info(
            "intelligence_pipeline_initialized",
            layers=["prism", "vinni", "atlas", "vanta", "nova", "ops"],
        )

    # ── Main Pipeline ──────────────────────────────────────────────────────

    async def process(
        self,
        symbol: str,
        market_data: Dict[str, Any],
        state_data: Optional[Dict[str, Any]] = None,
        signal_data: Optional[Dict[str, Any]] = None,
        infrastructure_data: Optional[Dict[str, Any]] = None,
        provider: str = "default",
    ) -> PipelineResult:
        """
        Run the complete 6-layer intelligence pipeline.

        Processes market data through all layers in strict order:
          1. PRISM  — Validate data integrity
          2. VINNI  — Monitor data quality and produce diagnostics
          3. ATLAS  — Analyze market structure and reasoning
          4. VANTA  — Validate intelligence and classify risk
          5. NOVA   — Generate user-facing summaries

        Returns a PipelineResult with outputs from every layer.
        """
        pipeline_id = f"pipe_{self._pipeline_count}_{int(time.time())}"
        self._pipeline_count += 1
        start = time.monotonic()

        result = PipelineResult(
            pipeline_id=pipeline_id,
            started_at=datetime.now(timezone.utc).isoformat(),
        )

        log.info("intelligence_pipeline_start", pipeline_id=pipeline_id, symbol=symbol)

        # ── Layer 1: PRISM (Data Integrity) ─────────────────────────────
        t0 = time.monotonic()
        try:
            candle = market_data.get("candle")
            current_price = market_data.get("current_price")
            last_update = market_data.get("last_update_timestamp")
            is_connected = market_data.get("is_connected", True)
            bid = market_data.get("bid")
            ask = market_data.get("ask")

            result.prism_results = self._prism.validate_market_data(
                symbol=symbol,
                provider=provider,
                candle=candle,
                current_price=current_price,
                last_update_timestamp=last_update,
                is_connected=is_connected,
                bid=bid,
                ask=ask,
            )

            # Cross-provider validation if multiple prices available
            if "provider_prices" in market_data:
                pp_result = self._prism.validate_provider_consistency(
                    symbol=symbol,
                    prices=market_data["provider_prices"],
                )
                result.prism_results.append(pp_result)

            # Timestamp drift check
            if last_update:
                drift_result = self._prism.validate_timestamp_drift(
                    symbol=symbol,
                    provider=provider,
                    provider_timestamp=last_update,
                )
                result.prism_results.append(drift_result)

            # Data quality score from PRISM
            result.data_quality_score = self._prism.get_data_quality_score(symbol)

        except Exception as exc:
            log.error("prism_layer_failed", pipeline_id=pipeline_id, error=str(exc))
            result.data_quality_score = 0.0

        result.prism_latency_ms = round((time.monotonic() - t0) * 1000, 1)

        # ── Layer 2: VINNI (Data Monitoring) ────────────────────────────
        t0 = time.monotonic()
        try:
            result.vinni_diagnostics = self._vinni.process_prism_results(
                result.prism_results,
            )

            if state_data:
                state_diags = self._vinni.check_state_engine_health(state_data)
                result.vinni_diagnostics.extend(state_diags)

            if signal_data:
                signal_diags = self._vinni.check_signal_integrity(signal_data)
                result.vinni_diagnostics.extend(signal_diags)

            if infrastructure_data:
                infra_diags = self._vinni.check_infrastructure(infrastructure_data)
                result.vinni_diagnostics.extend(infra_diags)

        except Exception as exc:
            log.error("vinni_layer_failed", pipeline_id=pipeline_id, error=str(exc))

        result.vinni_latency_ms = round((time.monotonic() - t0) * 1000, 1)

        # ── Layer 3: ATLAS (Market Reasoning) ───────────────────────────
        t0 = time.monotonic()
        try:
            candles = market_data.get("candles", [])
            if candles and result.data_quality_score > 0.3:
                # Only run ATLAS if data quality is above minimum threshold
                prism_flags = [
                    r.detail for r in result.prism_results if r.status != "pass"
                ]
                result.atlas_analysis = self._atlas.analyze_market_data(
                    symbol=symbol,
                    candles=candles,
                    prism_flags=prism_flags,
                )
            else:
                log.warning(
                    "atlas_skipped_low_quality",
                    pipeline_id=pipeline_id,
                    data_quality_score=result.data_quality_score,
                )

        except Exception as exc:
            log.error("atlas_layer_failed", pipeline_id=pipeline_id, error=str(exc))

        result.atlas_latency_ms = round((time.monotonic() - t0) * 1000, 1)

        # ── Layer 4: VANTA (Validation + Agent) ──────────────────────────
        t0 = time.monotonic()
        try:
            atlas_dict = result.atlas_analysis.to_dict() if result.atlas_analysis else None
            prism_flags = [
                r.detail for r in result.prism_results if r.status != "pass"
            ]

            result.vanta_validations = self._vanta.validate_intelligence(
                atlas_analysis=atlas_dict,
                nova_summary=None,  # NOVA hasn't run yet
                prism_flags=prism_flags,
            )

            # Classify risk environment
            result.risk_environment = self._vanta.classify_risk_environment(
                market_data=market_data,
                atlas_analysis=atlas_dict or {},
            )

            # Check if trading should be halted
            result.trading_halted = self._vanta.should_halt_trading(
                validations=result.vanta_validations,
                risk_env=result.risk_environment,
            )

        except Exception as exc:
            log.error("vanta_layer_failed", pipeline_id=pipeline_id, error=str(exc))

        result.vanta_latency_ms = round((time.monotonic() - t0) * 1000, 1)

        # ── Layer 5: NOVA (User Delivery) ────────────────────────────────
        t0 = time.monotonic()
        try:
            atlas_for_nova = result.atlas_analysis.to_dict() if result.atlas_analysis else None
            prism_flags_for_nova = [
                r.detail for r in result.prism_results if r.status != "pass"
            ]

            result.nova_summary = self._nova.generate_summary(
                symbol=symbol,
                market_data=market_data,
                atlas_analysis=atlas_for_nova,
                prism_flags=prism_flags_for_nova,
            )

            # If trading is halted, override the data quality
            if result.trading_halted:
                result.nova_summary.data_quality = "unreliable"
                result.nova_summary.context = (
                    f"TRADING HALTED: {result.nova_summary.context}"
                )

        except Exception as exc:
            log.error("nova_layer_failed", pipeline_id=pipeline_id, error=str(exc))

        result.nova_latency_ms = round((time.monotonic() - t0) * 1000, 1)

        # ── Overall Health Assessment ────────────────────────────────────
        prism_fails = sum(1 for r in result.prism_results if r.status == "fail")
        vinni_criticals = sum(
            1 for d in result.vinni_diagnostics
            if d.severity in ("error", "critical")
        )
        vanta_criticals = sum(
            1 for v in result.vanta_validations if v.severity == "critical"
        )

        if prism_fails >= 3 or vinni_criticals >= 2 or vanta_criticals >= 1:
            result.overall_health = "critical"
        elif prism_fails >= 1 or vinni_criticals >= 1 or result.data_quality_score < 0.5:
            result.overall_health = "degraded"
        else:
            result.overall_health = "ok"

        result.completed_at = datetime.now(timezone.utc).isoformat()
        result.total_latency_ms = round((time.monotonic() - start) * 1000, 1)

        log.info(
            "intelligence_pipeline_complete",
            pipeline_id=pipeline_id,
            symbol=symbol,
            health=result.overall_health,
            quality=round(result.data_quality_score, 2),
            trading_halted=result.trading_halted,
            risk=result.risk_environment,
            latency_ms=result.total_latency_ms,
        )

        return result

    # ── Layer-Specific Access ──────────────────────────────────────────────

    @property
    def prism(self) -> PrismValidator:
        """Direct access to PRISM validator."""
        return self._prism

    @property
    def vinni(self) -> VinniMonitor:
        """Direct access to VINNI monitor."""
        return self._vinni

    @property
    def atlas(self) -> AtlasEngine:
        """Direct access to ATLAS engine."""
        return self._atlas

    @property
    def vanta(self) -> VantaAgent:
        """Direct access to VANTA agent."""
        return self._vanta

    @property
    def nova(self) -> NovaLayer:
        """Direct access to NOVA layer."""
        return self._nova

    @property
    def ops(self) -> OpsController:
        """Direct access to OPS controller."""
        return self._ops

    # ── Status ────────────────────────────────────────────────────────────

    @property
    def status(self) -> Dict[str, Any]:
        """Return pipeline status with all layer statuses."""
        return {
            "module": "intelligence_pipeline",
            "architecture": "6_layer_stack",
            "phase": 3,
            "pipeline_count": self._pipeline_count,
            "layers": {
                "prism": self._prism.status,
                "vinni": self._vinni.status,
                "atlas": self._atlas.status,
                "vanta": self._vanta.status,
                "nova": self._nova.status,
                "ops": self._ops.status,
            },
            "data_flow": "RAW → PRISM → VINNI → ATLAS → VANTA → NOVA → Users",
            "ops_flow": "OPS (parallel — infrastructure control)",
        }
