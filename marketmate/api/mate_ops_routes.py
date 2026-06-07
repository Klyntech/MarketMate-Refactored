"""
marketmate.api.mate_ops_routes
───────────────────────────────
FastAPI routes for MATE-Ops monitoring and management.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger

log = get_logger("api.mate_ops_routes")

router = APIRouter(prefix="/api/mate-ops", tags=["mate-ops"])

# ─── MATE-Ops enabled flag ─────────────────────────────────────────────────────
MATE_OPS_ENABLED = os.environ.get("MATE_OPS_ENABLED", "true").lower() == "true"


# ─── Pydantic models ───────────────────────────────────────────────────────────

class ActionRequest(BaseModel):
    """Request body for executing a specific MATE-Ops action."""

    action: str = Field(
        ...,
        description="Action name (must match PermissionGate ACTION_AUTHORITY_MAP)",
        example="check_health",
    )
    params: Dict[str, Any] = Field(
        default_factory=dict,
        description="Parameters for the action",
    )

    @validator("action")
    def validate_action_name(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("action must not be empty")
        # Allow only known action names to prevent injection
        allowed = {
            "check_health", "check_ollama_status", "read_logs",
            "check_metrics", "check_website", "restart_service",
            "clear_cache", "notify_team",
        }
        if v not in allowed:
            raise ValueError(
                f"Unknown action '{v}'. Allowed: {', '.join(sorted(allowed))}"
            )
        return v


class ActionResponse(BaseModel):
    """Response body for action execution."""

    status: str
    action: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    denied: bool = False
    reason: Optional[str] = None


class KillSwitchRequest(BaseModel):
    """Request body for toggling the kill switch."""

    active: bool = Field(
        ...,
        description="True to activate kill switch (deny all Level 1+), False to deactivate",
    )


class KillSwitchResponse(BaseModel):
    """Response body for kill switch toggle."""

    kill_switch_active: bool
    message: str


class AuthorityUpdateRequest(BaseModel):
    """Request body for authority level update (used via query param)."""

    level: int = Field(
        ...,
        ge=0,
        le=2,
        description="Authority level: 0=read-only, 1=safe ops, 2=destructive",
    )


class StatusResponse(BaseModel):
    """Response body for agent status."""

    module: str
    architecture: str
    authority_level: int
    kill_switch_active: bool
    cycles_completed: int


class HealthResponse(BaseModel):
    """Response body for health check results."""

    services: List[Dict[str, Any]]
    healthy_count: int
    total_count: int


class CycleResponse(BaseModel):
    """Response body for a full cycle result."""

    cycle_id: str
    observations: int
    analysis_preview: str
    actions_planned: int
    execution_results: List[Dict[str, Any]]
    verification: str
    latency_ms: float


class ObservationResponse(BaseModel):
    """Response body for latest observations."""

    observations: List[Dict[str, Any]]
    total: int
    collected_at: str


class PermissionResponse(BaseModel):
    """Response body for permission configuration."""

    max_authority_level: int
    kill_switch_active: bool
    action_authority_map: Dict[str, int]


# ─── Admin auth helper ─────────────────────────────────────────────────────────

def _require_admin(request: Request) -> bool:
    """Verify admin secret in request header. Returns True if authorized."""
    secret = request.headers.get("x-admin-secret", "")
    if not cfg.app.admin_secret:
        return False
    return secret == cfg.app.admin_secret


def _mate_ops_disabled_response() -> JSONResponse:
    """Standard 503 response when MATE-Ops is not enabled."""
    return JSONResponse(
        {
            "error": "MATE-Ops is not enabled",
            "hint": "Set MATE_OPS_ENABLED=true in environment variables",
        },
        status_code=503,
    )


# ─── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("/status", response_model=StatusResponse)
async def get_status(request: Request):
    """Get MATE-Ops agent status.

    Returns authority level, kill switch state, and cycles completed.
    Requires X-Admin-Secret header.
    """
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    if not MATE_OPS_ENABLED:
        return _mate_ops_disabled_response()

    try:
        from marketmate.mate_ops.agent import MATEOpsAgent
        from marketmate.mate_ops.permission_gate import AuthorityLevel, PermissionGate

        # Create a lightweight agent instance just for status introspection
        gate = PermissionGate(max_authority_level=AuthorityLevel.READ_ONLY)
        agent = MATEOpsAgent(authority_level=AuthorityLevel.READ_ONLY, permission_gate=gate)

        status = agent.status
        return JSONResponse(status)
    except Exception as exc:
        log.error("mate_ops_status_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.get("/health", response_model=HealthResponse)
async def get_health(request: Request):
    """Run a quick health check across all monitored services.

    Calls agent.check_health() which runs all service health checks
    concurrently. Requires X-Admin-Secret header.
    """
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    if not MATE_OPS_ENABLED:
        return _mate_ops_disabled_response()

    try:
        from marketmate.mate_ops.agent import MATEOpsAgent
        from marketmate.mate_ops.permission_gate import AuthorityLevel, PermissionGate

        gate = PermissionGate(max_authority_level=AuthorityLevel.READ_ONLY)
        agent = MATEOpsAgent(authority_level=AuthorityLevel.READ_ONLY, permission_gate=gate)
        result = await agent.check_health()
        return JSONResponse(result)
    except Exception as exc:
        log.error("mate_ops_health_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.post("/cycle", response_model=CycleResponse)
async def trigger_cycle(request: Request):
    """Trigger a full Observe->Analyze->Plan->Execute->Verify cycle.

    The cycle runs the complete 5-stage MATE-Ops pipeline.
    Requires X-Admin-Secret header.
    """
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    if not MATE_OPS_ENABLED:
        return _mate_ops_disabled_response()

    try:
        from marketmate.mate_ops.agent import MATEOpsAgent
        from marketmate.mate_ops.permission_gate import AuthorityLevel, PermissionGate
        from marketmate.core.llm import llm_provider

        # Use SAFE_OPS authority for manually triggered cycles
        gate = PermissionGate(max_authority_level=AuthorityLevel.SAFE_OPS)
        agent = MATEOpsAgent(
            llm_provider=llm_provider,
            authority_level=AuthorityLevel.SAFE_OPS,
            permission_gate=gate,
        )
        result = await agent.run_cycle()

        return JSONResponse({
            "cycle_id": result.cycle_id,
            "observations": len(result.observations),
            "analysis_preview": result.analysis[:500] if result.analysis else "",
            "actions_planned": len(result.plan.get("actions", [])),
            "execution_results": result.execution_results,
            "verification": result.verification,
            "latency_ms": result.total_latency_ms,
            "started_at": result.started_at,
            "completed_at": result.completed_at,
        })
    except Exception as exc:
        log.error("mate_ops_cycle_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.get("/observations", response_model=ObservationResponse)
async def get_observations(request: Request):
    """Get latest telemetry observations.

    Returns the current state of all monitored services.
    Requires X-Admin-Secret header.
    """
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    if not MATE_OPS_ENABLED:
        return _mate_ops_disabled_response()

    try:
        from marketmate.mate_ops.observer import telemetry_collector

        observations = await telemetry_collector.collect()

        return JSONResponse({
            "observations": [
                {
                    "source": o.source,
                    "status": o.status,
                    "message": o.message,
                    "timestamp": o.timestamp,
                    "details": o.details,
                }
                for o in observations
            ],
            "total": len(observations),
            "collected_at": datetime.now(timezone.utc).isoformat(),
        })
    except Exception as exc:
        log.error("mate_ops_observations_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.post("/execute", response_model=ActionResponse)
async def execute_action(body: ActionRequest, request: Request):
    """Execute a specific MATE-Ops action.

    Validates the action against the permission gate before execution.
    Actions requiring higher authority than the current level are denied.
    Requires X-Admin-Secret header.
    """
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    if not MATE_OPS_ENABLED:
        return _mate_ops_disabled_response()

    try:
        from marketmate.mate_ops.agent import MATEOpsAgent
        from marketmate.mate_ops.permission_gate import AuthorityLevel, PermissionGate
        from marketmate.core.llm import llm_provider

        # Use SAFE_OPS authority for manual execution requests
        gate = PermissionGate(max_authority_level=AuthorityLevel.SAFE_OPS)
        agent = MATEOpsAgent(
            llm_provider=llm_provider,
            authority_level=AuthorityLevel.SAFE_OPS,
            permission_gate=gate,
        )

        # Validate against permission gate
        if not gate.validate(body.action):
            required_level = gate.get_required_level(body.action)
            return JSONResponse({
                "status": "denied",
                "action": body.action,
                "denied": True,
                "reason": (
                    f"Action '{body.action}' requires authority level "
                    f"{required_level.value if required_level else 'unknown'}, "
                    f"but current max is {gate.max_authority_level.value}. "
                    f"Kill switch active: {gate.kill_switch_active}"
                ),
            }, status_code=403)

        # Execute the action
        try:
            result = await agent._execute_action(body.action, body.params)
            return JSONResponse({
                "status": "success",
                "action": body.action,
                "result": result,
            })
        except Exception as exc:
            return JSONResponse({
                "status": "error",
                "action": body.action,
                "error": str(exc),
            }, status_code=500)

    except Exception as exc:
        log.error("mate_ops_execute_error", action=body.action, error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.get("/permissions", response_model=PermissionResponse)
async def get_permissions(request: Request):
    """Get current permission configuration.

    Returns the authority level, kill switch status, and the full
    action-authority mapping. Requires X-Admin-Secret header.
    """
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    if not MATE_OPS_ENABLED:
        return _mate_ops_disabled_response()

    try:
        from marketmate.mate_ops.permission_gate import (
            ACTION_AUTHORITY_MAP,
            AuthorityLevel,
            PermissionGate,
        )

        return JSONResponse({
            "max_authority_level": PermissionGate._max_authority_level
            if hasattr(PermissionGate, "_max_authority_level")
            else AuthorityLevel.READ_ONLY.value,
            "kill_switch_active": PermissionGate.KILL_SWITCH,
            "action_authority_map": {
                action: level.value for action, level in ACTION_AUTHORITY_MAP.items()
            },
        })
    except Exception as exc:
        log.error("mate_ops_permissions_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.put("/authority")
async def update_authority(level: int, request: Request):
    """Update the MATE-Ops authority level.

    Requires ``level`` query parameter (0, 1, or 2).
    Level 0 = read-only, Level 1 = safe ops, Level 2 = destructive.
    Requires X-Admin-Secret header.
    """
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    if not MATE_OPS_ENABLED:
        return _mate_ops_disabled_response()

    # Validate level
    if level not in (0, 1, 2):
        return JSONResponse(
            {"error": "level must be 0 (read-only), 1 (safe ops), or 2 (destructive)"},
            status_code=422,
        )

    try:
        from marketmate.mate_ops.permission_gate import AuthorityLevel, PermissionGate

        new_level = AuthorityLevel(level)
        PermissionGate.set_authority_level(new_level)

        log.info(
            "mate_ops_authority_updated_via_api",
            new_level=new_level.value,
        )

        return JSONResponse({
            "authority_level": new_level.value,
            "level_name": new_level.name,
            "message": f"Authority level updated to {new_level.name} ({new_level.value})",
        })
    except Exception as exc:
        log.error("mate_ops_authority_update_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.post("/kill-switch", response_model=KillSwitchResponse)
async def toggle_kill_switch(body: KillSwitchRequest, request: Request):
    """Activate or deactivate the MATE-Ops kill switch.

    When active, ALL Level 1+ actions are denied. This is the
    emergency brake for automated operations.
    Requires X-Admin-Secret header.
    """
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    if not MATE_OPS_ENABLED:
        return _mate_ops_disabled_response()

    try:
        from marketmate.mate_ops.permission_gate import PermissionGate

        if body.active:
            PermissionGate.enable_kill_switch()
            message = (
                "Kill switch ACTIVATED. All Level 1+ actions are now DENIED. "
                "Use deactivate to resume normal operations."
            )
        else:
            PermissionGate.disable_kill_switch()
            message = "Kill switch DEACTIVATED. Normal permission validation resumed."

        log.info(
            "mate_ops_kill_switch_toggled_via_api",
            active=body.active,
        )

        return JSONResponse({
            "kill_switch_active": body.active,
            "message": message,
        })
    except Exception as exc:
        log.error("mate_ops_kill_switch_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)
