"""
marketmate.api.routes
──────────────────────
Core application routes extracted from main.py.

Routes:
  GET  /health            — JSON status + uptime
  GET  /trades            — Open virtual trades (requires session)
  GET  /performance       — Win rate, RR, P&L stats (requires session)
  POST /webhook/{secret}  — Telegram webhook receiver
  POST /api/mate          — MATE intelligence (requires session)

Website is now served by Next.js — all page routes removed.
"""

from __future__ import annotations

import time as _time
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, List

from fastapi import APIRouter, Cookie, Request
from fastapi.responses import FileResponse, JSONResponse

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger

log = get_logger("api.routes")

router = APIRouter(tags=["core"])

_START_TS = _time.time()


# ─── Per-User MATE Rate Limiter ───────────────────────────────────────────────
# Prevents LLM cost amplification: limits how many MATE queries each user
# can make per time window. Uses in-memory sliding window counter.

class _UserRateLimiter:
    """Simple in-memory per-user rate limiter using sliding window."""

    def __init__(self, max_requests: int, window_seconds: int) -> None:
        self._max = max_requests
        self._window = window_seconds
        self._timestamps: Dict[str, List[float]] = defaultdict(list)

    def is_limited(self, user_id: str) -> bool:
        """Return True if user has exceeded their rate limit."""
        now = _time.time()
        cutoff = now - self._window
        # Prune old entries
        self._timestamps[user_id] = [
            ts for ts in self._timestamps[user_id] if ts > cutoff
        ]
        if len(self._timestamps[user_id]) >= self._max:
            return True
        self._timestamps[user_id].append(now)
        return False


# MATE query rate limiter: 10 queries per minute per user by default.
# Configurable via MATE_RATE_LIMIT_RPM env var.
# Reduced from 20 to 10: each MATE query spawns 1-8 LLM API calls,
# so 10 RPM/user × 3 avg iterations = 30 Gemini calls/min, staying
# within the free tier budget of ~15 RPM (with client-side throttling).
_mate_rpm = int(getattr(cfg.mate, 'rate_limit_rpm', 10))
_mate_limiter = _UserRateLimiter(max_requests=_mate_rpm, window_seconds=60)


def _require_session(mm_session: str = "") -> dict:
    """Verify session cookie and return user dict, or raise 401."""
    from marketmate.api.auth import _session_verify
    if not mm_session:
        return None
    return _session_verify(mm_session)


# Website pages are now served by Next.js (port 3000).
# All static HTML page routes have been removed.
# FastAPI only serves API endpoints.


@router.get("/health")
async def health():
    """Health check endpoint — minimal info, no internal details."""
    return JSONResponse({"status": "ok"})


@router.get("/trades")
async def trades(mm_session: str = Cookie(default=None)):
    """Return open virtual trades — requires authentication."""
    user = _require_session(mm_session or "")
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        from marketmate.db.repositories.signals import SignalRepository
        signal_repo = SignalRepository()
        open_signals = await signal_repo.get_open_signals()
        return JSONResponse({"trades": open_signals, "count": len(open_signals)})
    except Exception as exc:
        log.error("trades_api_error", error=str(exc))
        return JSONResponse({"error": "Failed to retrieve trades"}, status_code=500)


@router.get("/performance")
async def performance(mm_session: str = Cookie(default=None)):
    """Win rate, RR, P&L stats — requires authentication."""
    user = _require_session(mm_session or "")
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        from marketmate.db.repositories.signals import SignalRepository
        signal_repo = SignalRepository()
        stats_7  = await signal_repo.get_performance_stats(days=7)
        stats_30 = await signal_repo.get_performance_stats(days=30)
        return JSONResponse({
            "7_day":  stats_7,
            "30_day": stats_30,
        })
    except Exception as exc:
        log.error("performance_api_error", error=str(exc))
        return JSONResponse({"error": "Failed to retrieve performance"}, status_code=500)


# REMOVED: /api/config endpoint that leaked the Twelve Data API key.
# Frontend should proxy data requests through backend, not use the key directly.


@router.post("/webhook/{secret}")
async def telegram_webhook(secret: str, request: Request):
    """Telegram webhook receiver — verifies secret and dispatches update.

    Security checks (both must pass):
      1. URL path secret must match cfg.telegram.webhook_secret
      2. X-Telegram-Bot-Api-Secret-Token header must match
         (Telegram sets this when webhook is registered with secret_token)
    """
    if not cfg.telegram.webhook_secret:
        log.error("webhook_secret_not_set")
        return JSONResponse({"error": "server misconfiguration"}, status_code=500)

    # Check 1: URL path parameter — validate against path_token (or webhook_secret for backward compat)
    expected_path_token = cfg.telegram.webhook_path_token or cfg.telegram.webhook_secret
    if secret != expected_path_token:
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    # Check 2: Telegram's secret_token header
    # When the webhook is registered with secret_token=X, Telegram sends
    # X-Telegram-Bot-Api-Secret-Token: X on every request.
    telegram_header = request.headers.get("x-telegram-bot-api-secret-token", "")
    if telegram_header != cfg.telegram.webhook_secret:
        log.warning("webhook_missing_or_wrong_secret_token_header",
                    has_header=bool(telegram_header))
        return JSONResponse({"error": "unauthorized"}, status_code=403)

    try:
        update_data = await request.json()
    except Exception as exc:
        log.error("webhook_parse_failed", error=str(exc))
        return JSONResponse({"error": "invalid payload"}, status_code=400)

    # SECURITY: Limit update size to prevent memory exhaustion
    raw_body = await request.body()
    if len(raw_body) > 1_000_000:  # 1MB limit
        log.warning("webhook_oversized_payload", size=len(raw_body))
        return JSONResponse({"error": "payload too large"}, status_code=413)

    from marketmate.delivery.telegram.handler import handle_update
    # Dispatch in background — don't block the webhook response
    import asyncio
    asyncio.create_task(handle_update(update_data))

    return JSONResponse({"ok": True})


@router.post("/api/mate")
async def mate_query(request: Request, mm_session: str = Cookie(default=None)):
    """
    MATE intelligence endpoint — requires authentication.

    Routes through mate_interface.ask() → CompiledCore → QueryRouter
    → Redis + MongoDB + Event State → LLM-narrated response.

    Body: {"query": "string", "query_type": "optional_string", "mode": "compiled|direct"}
    """
    user = _require_session(mm_session or "")
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    # SECURITY: Per-user rate limit to prevent LLM cost amplification
    user_id = user.get("telegram_id", "") or user.get("google_id", "") or "unknown"
    if _mate_limiter.is_limited(user_id):
        log.warning("mate_rate_limited", user_id=user_id)
        return JSONResponse(
            {"error": f"Rate limit exceeded — max {_mate_rpm} MATE queries per minute"},
            status_code=429,
        )

    try:
        body = await request.json()
        query = body.get("query", "")
        query_type = body.get("query_type")
        mode = body.get("mode", "compiled")

        if not query:
            return JSONResponse({"error": "query required"}, status_code=422)

        # Limit query length to prevent abuse
        if len(query) > 2000:
            return JSONResponse({"error": "query too long (max 2000 chars)"}, status_code=422)

        from marketmate.mate.interface import mate_interface
        chat_id = user.get("telegram_id", "") or user.get("google_id", "")
        result = await mate_interface.ask(
            query=query,
            query_type=query_type,
            mode=mode,
            chat_id=chat_id,
        )

        return JSONResponse(result)
    except Exception as exc:
        log.error("mate_api_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.post("/api/mate/signal/{signal_id}")
async def mate_signal_explanation(signal_id: str, mm_session: str = Cookie(default=None)):
    """
    Signal explanation endpoint — requires authentication.
    """
    # SECURITY: Validate signal_id format (alphanumeric only)
    import re
    if not re.match(r'^[A-Za-z0-9]{1,16}$', signal_id):
        return JSONResponse({"error": "invalid signal_id format"}, status_code=422)

    user = _require_session(mm_session or "")
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    # SECURITY: Per-user rate limit to prevent LLM cost amplification
    user_id = user.get("telegram_id", "") or user.get("google_id", "") or "unknown"
    if _mate_limiter.is_limited(user_id):
        log.warning("mate_signal_rate_limited", user_id=user_id)
        return JSONResponse(
            {"error": f"Rate limit exceeded — max {_mate_rpm} MATE queries per minute"},
            status_code=429,
        )

    try:
        from marketmate.mate.interface import mate_interface
        result = await mate_interface.ask(
            query=f"Explain signal {signal_id}",
            query_type="signal_explanation",
        )
        return JSONResponse(result)
    except Exception as exc:
        log.error("mate_signal_explain_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


# ─── Observability API (v8.0.0 Intelligence Infrastructure) ────────────────────
# These endpoints provide visibility into the State Engine, event streams,
# and market state vectors. They are the "internal tools" needed to not
# fly blind inside the intelligence layer.
#
# All endpoints require admin_secret for access — they expose internal
# system state that should not be publicly accessible.

def _require_admin(request: Request) -> bool:
    """Verify admin secret in request header. Returns True if authorized."""
    secret = request.headers.get("x-admin-secret", "")
    if not cfg.app.admin_secret:
        return False
    return secret == cfg.app.admin_secret


@router.get("/api/state/instruments")
async def state_instruments(request: Request):
    """
    State Debugger: List all tracked instruments and their current state.

    Returns compact summaries for all instruments in the StateEngine,
    including bias, conviction, regime, zone counts, and volatility.
    Requires X-Admin-Secret header.
    """
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        from marketmate.state.engine import get_state_engine
        state_engine = get_state_engine()
        market_state = await state_engine.get_market_state()
        summaries = market_state.get_summary()
        return JSONResponse({
            "instruments": {
                sym: s.model_dump() for sym, s in summaries.items()
            },
            "market_regime": market_state.market_regime.value,
            "scan_cycle": market_state.scan_cycle,
            "updated_at": market_state.updated_at.isoformat(),
            "count": len(summaries),
        })
    except Exception as exc:
        log.error("state_instruments_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.get("/api/state/instrument/{symbol}")
async def state_instrument_detail(symbol: str, request: Request):
    """
    Vector Inspector: Full InstrumentState for a specific symbol.

    Returns the complete state vector including all sub-states
    (bias, liquidity, zones, confirmation, risk) and composite metrics.
    Requires X-Admin-Secret header.
    """
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    # Validate symbol format
    import re
    if not re.match(r'^[A-Za-z0-9]{2,12}$', symbol):
        return JSONResponse({"error": "invalid symbol format"}, status_code=422)

    try:
        from marketmate.state.engine import get_state_engine
        state_engine = get_state_engine()
        state = await state_engine.get_instrument_state(symbol.upper())
        if state is None:
            return JSONResponse({"error": f"No state for {symbol}"}, status_code=404)
        return JSONResponse(state.model_dump())
    except Exception as exc:
        log.error("state_instrument_detail_error", symbol=symbol, error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.get("/api/state/events")
async def state_event_timeline(request: Request):
    """
    Event Timeline: Recent state transition events.

    Returns the EventBus subscriber status and current event types.
    This provides visibility into what events are flowing through
    the system and which consumers are active.
    Requires X-Admin-Secret header.
    """
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        from marketmate.core.events import event_bus
        from marketmate.core.schemas import EVENT_SCHEMA_REGISTRY

        subscribers = {}
        for et in event_bus.event_types:
            subscribers[et] = event_bus.subscriber_count(et)

        return JSONResponse({
            "active_subscriptions": subscribers,
            "total_event_types": len(subscribers),
            "registered_schemas": sorted(EVENT_SCHEMA_REGISTRY.keys()),
            "schema_count": len(EVENT_SCHEMA_REGISTRY),
        })
    except Exception as exc:
        log.error("state_event_timeline_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.get("/api/state/conviction")
async def state_conviction_chart(request: Request):
    """
    Conviction Chart: Current conviction scores across all instruments.

    Returns a compact view of conviction scores and regimes for
    all tracked instruments, suitable for building real-time
    conviction charts in monitoring dashboards.
    Requires X-Admin-Secret header.
    """
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        from marketmate.state.engine import get_state_engine
        state_engine = get_state_engine()
        market_state = await state_engine.get_market_state()

        conviction_data = {}
        for sym, state in market_state.instruments.items():
            conviction_data[sym] = {
                "conviction_score": round(state.bias_state.conviction_score, 3),
                "bias": state.bias_state.daily_bias.value,
                "regime": state.bias_state.regime.value,
                "volatility_regime": state.risk_state.volatility_regime.value,
                "active_zones": len(state.zone_state.active_zones),
                "scan_count": state.scan_count,
                "last_scan_at": state.last_scan_at.isoformat(),
            }

        return JSONResponse({
            "convictions": conviction_data,
            "market_regime": market_state.market_regime.value,
            "scan_cycle": market_state.scan_cycle,
        })
    except Exception as exc:
        log.error("state_conviction_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.get("/api/state/regime")
async def state_regime_tracker(request: Request):
    """
    Regime Tracker: Current market regime classification for all instruments.

    Shows the current regime (trending/ranging/transitional) and
    volatility regime (low/normal/high/extreme) for each instrument,
    plus the overall market regime.
    Requires X-Admin-Secret header.
    """
    if not _require_admin(request):
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        from marketmate.state.engine import get_state_engine
        state_engine = get_state_engine()
        market_state = await state_engine.get_market_state()

        regimes = {}
        for sym, state in market_state.instruments.items():
            regimes[sym] = {
                "directional_regime": state.bias_state.regime.value,
                "volatility_regime": state.risk_state.volatility_regime.value,
                "conviction": round(state.bias_state.conviction_score, 3),
                "bias_direction": state.bias_state.daily_bias.value,
                "available_liquidity": round(state.liquidity_state.available_liquidity_score, 3),
                "zone_freshness": round(state.zone_state.zone_freshness, 3),
            }

        return JSONResponse({
            "instruments": regimes,
            "market_regime": market_state.market_regime.value,
            "updated_at": market_state.updated_at.isoformat(),
        })
    except Exception as exc:
        log.error("state_regime_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


# ─── Public Market State API (Phase 3: API-First) ────────────────────────────
# These endpoints expose the compiled market state to authenticated users.
# This is the "API-First" principle: every capability becomes callable.

@router.get("/api/market/state")
async def market_state_overview(mm_session: str = Cookie(default=None)):
    """
    Public Market State API: Overview of all instruments.

    Returns compact summaries for all tracked instruments including
    bias, conviction, regime, zone counts, and volatility.
    Requires session authentication.
    """
    user = _require_session(mm_session or "")
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        from marketmate.state.engine import get_state_engine
        state_engine = get_state_engine()
        market_state = await state_engine.get_market_state()
        summaries = market_state.get_summary()

        return JSONResponse({
            "instruments": {
                sym: s.model_dump() for sym, s in summaries.items()
            },
            "market_regime": market_state.market_regime.value,
            "scan_cycle": market_state.scan_cycle,
            "updated_at": market_state.updated_at.isoformat(),
        })
    except Exception as exc:
        log.error("public_market_state_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.get("/api/market/state/{symbol}")
async def market_state_symbol(symbol: str, mm_session: str = Cookie(default=None)):
    """
    Public Market State API: Full state vector for a specific symbol.

    Returns the complete InstrumentState including all sub-states
    (bias, liquidity, zones, confirmation, risk) and composite metrics.
    Requires session authentication.
    """
    user = _require_session(mm_session or "")
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    import re
    if not re.match(r'^[A-Za-z0-9]{2,12}$', symbol):
        return JSONResponse({"error": "invalid symbol format"}, status_code=422)

    try:
        from marketmate.mate.brains.state_intel import state_intel_brain
        result = await state_intel_brain.get_instrument_state(symbol=symbol)
        return JSONResponse(result)
    except Exception as exc:
        log.error("public_symbol_state_error", symbol=symbol, error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.get("/api/market/regime")
async def market_regime_public(mm_session: str = Cookie(default=None)):
    """
    Public Market Regime API: Current regime across all instruments.

    Returns per-instrument regime classification and the overall
    market regime. Requires session authentication.
    """
    user = _require_session(mm_session or "")
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        from marketmate.mate.brains.state_intel import state_intel_brain
        result = await state_intel_brain.get_market_regime()
        return JSONResponse(result)
    except Exception as exc:
        log.error("public_regime_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.get("/api/market/conviction")
async def market_conviction_public(mm_session: str = Cookie(default=None)):
    """
    Public Conviction API: Conviction scores across all instruments.

    Returns conviction scores ranging from -1.0 (bearish) to +1.0 (bullish).
    Requires session authentication.
    """
    user = _require_session(mm_session or "")
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        from marketmate.mate.brains.state_intel import state_intel_brain
        result = await state_intel_brain.get_conviction_chart()
        return JSONResponse(result)
    except Exception as exc:
        log.error("public_conviction_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.get("/api/market/transitions")
async def market_transitions_public(
    symbol: str = "", mm_session: str = Cookie(default=None)
):
    """
    Public Transitions API: Recent state transition events.

    Returns bias flips, zone formations, liquidity sweeps, and regime changes.
    Optional query param: ?symbol=XAUUSD to filter by symbol.
    Requires session authentication.
    """
    user = _require_session(mm_session or "")
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        from marketmate.mate.brains.state_intel import state_intel_brain
        result = await state_intel_brain.get_state_transitions(symbol=symbol)
        return JSONResponse(result)
    except Exception as exc:
        log.error("public_transitions_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.get("/api/market/zones/{symbol}")
async def market_zones_public(
    symbol: str, mm_session: str = Cookie(default=None)
):
    """
    Public Zones API: Active order blocks and FVGs for a symbol.

    Returns zone type, direction, price range, and freshness.
    Requires session authentication.
    """
    user = _require_session(mm_session or "")
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    import re
    if not re.match(r'^[A-Za-z0-9]{2,12}$', symbol):
        return JSONResponse({"error": "invalid symbol format"}, status_code=422)

    try:
        from marketmate.mate.brains.state_intel import state_intel_brain
        result = await state_intel_brain.get_zone_state(symbol=symbol)
        return JSONResponse(result)
    except Exception as exc:
        log.error("public_zones_error", symbol=symbol, error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.get("/api/market/liquidity/{symbol}")
async def market_liquidity_public(
    symbol: str, mm_session: str = Cookie(default=None)
):
    """
    Public Liquidity API: Liquidity sweep status for a symbol.

    Returns active levels, recent sweeps, and available liquidity score.
    Requires session authentication.
    """
    user = _require_session(mm_session or "")
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    import re
    if not re.match(r'^[A-Za-z0-9]{2,12}$', symbol):
        return JSONResponse({"error": "invalid symbol format"}, status_code=422)

    try:
        from marketmate.mate.brains.state_intel import state_intel_brain
        result = await state_intel_brain.get_liquidity_state(symbol=symbol)
        return JSONResponse(result)
    except Exception as exc:
        log.error("public_liquidity_error", symbol=symbol, error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)


@router.get("/api/market/observer")
async def market_observer_status(mm_session: str = Cookie(default=None)):
    """
    Public Observer API: State observer diagnostics.

    Returns transition counters, tracked symbols, and timeline size.
    Requires session authentication.
    """
    user = _require_session(mm_session or "")
    if not user:
        return JSONResponse({"error": "unauthorized"}, status_code=401)

    try:
        from marketmate.mate.observer import state_observer
        return JSONResponse(state_observer.status)
    except Exception as exc:
        log.error("public_observer_error", error=str(exc))
        return JSONResponse({"error": "Internal error"}, status_code=500)
