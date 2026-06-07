"""
marketmate.api.intelligence_routes
───────────────────────────────────
FastAPI routes for the 6-layer Intelligence Stack (Phase 3).

Endpoints:
  GET  /api/intelligence/status         — Pipeline + all layer statuses
  POST /api/intelligence/process         — Run full pipeline for a symbol
  GET  /api/intelligence/prism/status    — PRISM validator status
  POST /api/intelligence/prism/validate  — Run PRISM validation
  GET  /api/intelligence/vinni/status    — VINNI monitor status
  POST /api/intelligence/vinni/check     — Run VINNI checks
  GET  /api/intelligence/atlas/status    — ATLAS engine status
  POST /api/intelligence/atlas/analyze   — Run ATLAS analysis
  GET  /api/intelligence/vanta/status    — VANTA agent status
  POST /api/intelligence/vanta/validate  — Run VANTA validation
  POST /api/intelligence/vanta/build     — Create VANTA build plan
  GET  /api/intelligence/nova/status     — NOVA layer status
  POST /api/intelligence/nova/summarize  — Generate NOVA summary
  GET  /api/intelligence/ops/status      — OPS controller status
  POST /api/intelligence/ops/execute     — Execute OPS action

All endpoints require X-Admin-Secret header for authentication.

Created: 2026-05-29
Phase: 3 (High Agency)
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger

log = get_logger("api.intelligence_routes")

router = APIRouter(prefix="/api/intelligence", tags=["intelligence"])

INTELLIGENCE_ENABLED = os.environ.get("INTELLIGENCE_ENABLED", "true").lower() == "true"


# ─── Pydantic Models ──────────────────────────────────────────────────────────

class ProcessRequest(BaseModel):
    """Request body for running the full intelligence pipeline."""
    symbol: str = Field(..., description="Trading symbol (e.g., BTCUSDT)")
    provider: str = Field(default="default", description="Data provider name")
    market_data: Dict[str, Any] = Field(
        default_factory=dict,
        description="Market data (candle, prices, bids, asks, etc.)",
    )
    state_data: Optional[Dict[str, Any]] = Field(
        default=None, description="State engine data",
    )
    signal_data: Optional[Dict[str, Any]] = Field(
        default=None, description="Signal data for integrity check",
    )
    infrastructure_data: Optional[Dict[str, Any]] = Field(
        default=None, description="Infrastructure metrics",
    )


class PrismValidateRequest(BaseModel):
    """Request body for PRISM validation."""
    symbol: str
    provider: str = "default"
    candle: Optional[Dict[str, Any]] = None
    current_price: Optional[float] = None
    last_update_timestamp: Optional[str] = None
    is_connected: bool = True
    bid: Optional[float] = None
    ask: Optional[float] = None


class AtlasAnalyzeRequest(BaseModel):
    """Request body for ATLAS analysis."""
    symbol: str
    candles: List[Dict[str, Any]] = Field(default_factory=list)
    prism_flags: List[str] = Field(default_factory=list)


class VantaValidateRequest(BaseModel):
    """Request body for VANTA validation."""
    atlas_analysis: Optional[Dict[str, Any]] = None
    nova_summary: Optional[Dict[str, Any]] = None
    prism_flags: List[str] = Field(default_factory=list)


class VantaBuildRequest(BaseModel):
    """Request body for VANTA build plan creation."""
    requirement: str = Field(..., description="What to build")
    tier: int = Field(default=2, ge=1, le=3, description="Authority tier (1-3)")


class NovaSummarizeRequest(BaseModel):
    """Request body for NOVA summary."""
    symbol: str
    market_data: Dict[str, Any] = Field(default_factory=dict)
    atlas_analysis: Optional[Dict[str, Any]] = None
    prism_flags: List[str] = Field(default_factory=list)


class OpsExecuteRequest(BaseModel):
    """Request body for OPS action execution."""
    operation: str = Field(
        ..., description="Operation: restart_service, clear_cache, rotate_logs, "
        "reconnect_feed, switch_provider, scale_service, deploy",
    )
    target: str = Field(..., description="Target service/provider")
    params: Dict[str, Any] = Field(default_factory=dict)


# ─── Auth Helper ───────────────────────────────────────────────────────────────

def _require_admin(request: Request) -> bool:
    """Verify admin secret in request header."""
    secret = request.headers.get("x-admin-secret", "")
    if not cfg.app.admin_secret:
        return False
    return secret == cfg.app.admin_secret


def _disabled_response() -> JSONResponse:
    """Standard 503 when intelligence stack is not enabled."""
    return JSONResponse(
        {"error": "Intelligence stack not enabled", "hint": "Set INTELLIGENCE_ENABLED=true"},
        status_code=503,
    )


# ─── Pipeline Endpoints ────────────────────────────────────────────────────────

@router.get("/status")
async def get_status(request: Request):
    """Get the full intelligence pipeline status with all 6 layers."""
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if not INTELLIGENCE_ENABLED:
        return _disabled_response()

    try:
        from marketmate.intelligence.pipeline import IntelligencePipeline
        pipeline = IntelligencePipeline()
        return JSONResponse(pipeline.status)
    except Exception as exc:
        log.error("intelligence_status_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.post("/process")
async def process_pipeline(body: ProcessRequest, request: Request):
    """Run the full 6-layer intelligence pipeline for a symbol."""
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if not INTELLIGENCE_ENABLED:
        return _disabled_response()

    try:
        from marketmate.intelligence.pipeline import IntelligencePipeline
        pipeline = IntelligencePipeline()
        result = await pipeline.process(
            symbol=body.symbol,
            market_data=body.market_data,
            state_data=body.state_data,
            signal_data=body.signal_data,
            infrastructure_data=body.infrastructure_data,
            provider=body.provider,
        )
        return JSONResponse(result.to_dict())
    except Exception as exc:
        log.error("intelligence_process_error", symbol=body.symbol, error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


# ── PRISM Endpoints ────────────────────────────────────────────────────────────

@router.get("/prism/status")
async def get_prism_status(request: Request):
    """Get PRISM validator status and thresholds."""
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if not INTELLIGENCE_ENABLED:
        return _disabled_response()

    try:
        from marketmate.intelligence.prism import PrismValidator
        validator = PrismValidator()
        return JSONResponse(validator.status)
    except Exception as exc:
        log.error("prism_status_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.post("/prism/validate")
async def validate_prism(body: PrismValidateRequest, request: Request):
    """Run PRISM data validation checks."""
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if not INTELLIGENCE_ENABLED:
        return _disabled_response()

    try:
        from marketmate.intelligence.prism import PrismValidator
        validator = PrismValidator()
        results = validator.validate_market_data(
            symbol=body.symbol,
            provider=body.provider,
            candle=body.candle,
            current_price=body.current_price,
            last_update_timestamp=body.last_update_timestamp,
            is_connected=body.is_connected,
            bid=body.bid,
            ask=body.ask,
        )
        return JSONResponse({
            "results": [r.to_dict() for r in results],
            "data_quality_score": validator.get_data_quality_score(body.symbol),
            "provider_reliability": validator.get_all_reliability_scores(),
        })
    except Exception as exc:
        log.error("prism_validate_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


# ── ATLAS Endpoints ────────────────────────────────────────────────────────────

@router.post("/atlas/analyze")
async def analyze_atlas(body: AtlasAnalyzeRequest, request: Request):
    """Run ATLAS market analysis."""
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if not INTELLIGENCE_ENABLED:
        return _disabled_response()

    try:
        from marketmate.intelligence.atlas import AtlasEngine
        engine = AtlasEngine()
        analysis = engine.analyze_market_data(
            symbol=body.symbol,
            candles=body.candles,
            prism_flags=body.prism_flags,
        )
        return JSONResponse(analysis.to_dict())
    except Exception as exc:
        log.error("atlas_analyze_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


# ── VANTA Endpoints ────────────────────────────────────────────────────────────

@router.post("/vanta/validate")
async def validate_vanta(body: VantaValidateRequest, request: Request):
    """Run VANTA intelligence validation."""
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if not INTELLIGENCE_ENABLED:
        return _disabled_response()

    try:
        from marketmate.intelligence.vanta import VantaAgent
        agent = VantaAgent()
        validations = agent.validate_intelligence(
            atlas_analysis=body.atlas_analysis,
            nova_summary=body.nova_summary,
            prism_flags=body.prism_flags,
        )
        risk_env = agent.classify_risk_environment(
            market_data={},
            atlas_analysis=body.atlas_analysis or {},
        )
        should_halt = agent.should_halt_trading(validations, risk_env)

        return JSONResponse({
            "validations": [v.to_dict() for v in validations],
            "risk_environment": risk_env,
            "trading_halted": should_halt,
            "critical_count": sum(1 for v in validations if v.severity == "critical"),
        })
    except Exception as exc:
        log.error("vanta_validate_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.post("/vanta/build")
async def create_build_plan(body: VantaBuildRequest, request: Request):
    """Create a VANTA build plan (bounded creation with approval gates)."""
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if not INTELLIGENCE_ENABLED:
        return _disabled_response()

    try:
        from marketmate.intelligence.vanta import VantaAgent
        agent = VantaAgent()
        plan = agent.create_build_plan(
            requirement=body.requirement,
            tier=body.tier,
        )
        validation = agent.validate_build_plan(plan)

        return JSONResponse({
            "plan": plan.to_dict() if hasattr(plan, "to_dict") else plan.__dict__,
            "validation": validation.to_dict() if hasattr(validation, "to_dict") else validation.__dict__,
            "requires_human_approval": plan.requires_approval,
        })
    except Exception as exc:
        log.error("vanta_build_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


# ── NOVA Endpoints ─────────────────────────────────────────────────────────────

@router.post("/nova/summarize")
async def summarize_nova(body: NovaSummarizeRequest, request: Request):
    """Generate a NOVA market summary."""
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if not INTELLIGENCE_ENABLED:
        return _disabled_response()

    try:
        from marketmate.intelligence.nova import NovaLayer
        layer = NovaLayer()
        summary = layer.generate_summary(
            symbol=body.symbol,
            market_data=body.market_data,
            atlas_analysis=body.atlas_analysis,
            prism_flags=body.prism_flags,
        )
        return JSONResponse({
            "summary": summary.to_dict() if hasattr(summary, "to_dict") else summary.__dict__,
            "telegram": layer.format_for_telegram(summary),
            "should_escalate": layer.should_escalate_to_atlas(summary),
        })
    except Exception as exc:
        log.error("nova_summarize_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


# ── OPS Endpoints ──────────────────────────────────────────────────────────────

@router.post("/ops/execute")
async def execute_ops(body: OpsExecuteRequest, request: Request):
    """Execute an OPS infrastructure action."""
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)
    if not INTELLIGENCE_ENABLED:
        return _disabled_response()

    try:
        from marketmate.intelligence.ops import OpsController, OpsAction

        controller = OpsController()
        action = OpsAction(
            operation=body.operation,
            target=body.target,
            params=body.params,
        )
        result = await controller.execute_action(action)
        return JSONResponse(result.to_dict() if hasattr(result, "to_dict") else result.__dict__)
    except Exception as exc:
        log.error("ops_execute_error", operation=body.operation, error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)
