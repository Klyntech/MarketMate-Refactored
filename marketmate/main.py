"""
marketmate.main.py
──────────────────
MarketMate — Refactored Web Service Entry Point v7.0.0

This file is the slim app factory that was extracted from the original
1200-line main.py. All route logic lives in api/routes.py and api/auth.py.
All Academy logic lives in platform/academy_api.py. All background loop
orchestration lives in core/scheduler.py.

New in v7.0.0:
  - 7-Brain Architecture (6 Institutional + 1 General)
  - Dual-Mode Cognition (80% Institutional / 20% General)
  - Intent Classifier + Entity Extraction
  - BTCUSD + ETHUSD pair support
  - Animated Emoji Loader (brand identity)

Target: <200 lines
"""

from __future__ import annotations

import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.core.events import event_bus
from marketmate.core.scheduler import Scheduler
from marketmate.db.core import mongo_manager
from marketmate.db import connect_all, close_all
from marketmate.db import get_signals_repo, get_subscribers_repo
from marketmate.strategy.engine import SignalEngine
from marketmate.strategy.models import DailyState
from marketmate.execution.risk import RiskManager
from marketmate.execution.lifecycle import TradeLifecycleManager
from marketmate.execution.executor import SimExecutor
from marketmate.delivery.telegram.bot import TelegramDelivery
from marketmate.delivery.telegram.handler import set_bot_username
from marketmate.analytics.tracker import PerformanceTracker
from marketmate.analytics.training_logger import training_logger
from marketmate.analytics.audit_logger import audit_logger
from marketmate.state.engine import get_state_engine

# API routers
from marketmate.api.routes import router as routes_router
from marketmate.api.auth import router as auth_router
from marketmate.platform.academy_api import router as academy_router
from marketmate.platform.social_api import router as social_router

log = get_logger("main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    log.info("marketmate_starting", env=cfg.app.env, pairs=cfg.strategy.pairs)

    # ── Database startup ───────────────────────────────────────────────────
    await mongo_manager.connect()
    await connect_all()
    log.info("database_ready")

    # ── Virtual Account Engine ─────────────────────────────────────────────
    from marketmate.virtual_account.engine import get_virtual_account_engine
    va_engine = get_virtual_account_engine()
    await va_engine.initialize()
    await va_engine.ensure_indexes()
    va_engine.subscribe_to_events()
    log.info("virtual_account_ready", balance=await va_engine.get_balance())

    # ── MATE Intelligence Layer ────────────────────────────────────────────
    from marketmate.mate.state_store import redis_state_store
    from marketmate.mate.pipeline import event_state_pipeline
    from marketmate.mate.observer import state_observer
    await redis_state_store.connect()
    event_state_pipeline.subscribe()
    state_observer.subscribe()  # Phase 3: Observe state transitions for MATE
    # Bootstrap Redis state from MongoDB so MATE has data immediately
    await event_state_pipeline.bootstrap()
    log.info("mate_intelligence_ready", observer=state_observer.status)

    # ── State Engine (v8.0.0 Intelligence Infrastructure) ──────────────────
    state_engine = get_state_engine()
    await state_engine.initialize()
    # Subscribe the StateEngine to gate_features_computed events
    # so it processes ScanFeatures from every scan cycle
    async def _on_gate_features_computed(**kwargs):
        """Bridge: gate_features_computed → StateEngine.process_scan_features."""
        try:
            from marketmate.strategy.features import ScanFeatures
            sf = ScanFeatures(
                symbol=kwargs.get("symbol", ""),
                timestamp=kwargs.get("timestamp", ""),
                passed=kwargs.get("passed", False),
                failed_at=kwargs.get("failed_at", ""),
                confidence_score=kwargs.get("confidence_score", 0.0),
                confidence_tier=kwargs.get("confidence_tier", ""),
                setup_score=kwargs.get("setup_score", 0.0),
                session_active=kwargs.get("session_active", False),
                trades_today=kwargs.get("trades_today", 0),
            )
            # Attach sub-features if available
            bf = kwargs.get("bias_features")
            sf.bias_features = BiasFeatures(**bf) if isinstance(bf, dict) else None
            sfsw = kwargs.get("sweep_features")
            sf.sweep_features = SweepFeatures(**sfsw) if isinstance(sfsw, dict) else None
            sfz = kwargs.get("zone_features")
            sf.zone_features = ZoneFeatures(**sfz) if isinstance(sfz, dict) else None
            sfc = kwargs.get("confirm_features")
            sf.confirm_features = ConfirmFeatures(**sfc) if isinstance(sfc, dict) else None
            sfr = kwargs.get("rr_features")
            sf.rr_features = RRFeatures(**sfr) if isinstance(sfr, dict) else None
            await state_engine.process_scan_features(sf)
        except Exception as exc:
            log.warning("state_engine_process_error", error=str(exc))

    from marketmate.strategy.features import (
        BiasFeatures, SweepFeatures, ZoneFeatures,
        ConfirmFeatures, RRFeatures,
    )
    event_bus.subscribe("gate_features_computed", _on_gate_features_computed)
    log.info("state_engine_ready", instruments=len(state_engine._last_states))

    # ── Backup & Replication ───────────────────────────────────────────────
    from marketmate.backup.dual_write import dual_write_manager
    from marketmate.backup.scheduler import backup_scheduler
    await dual_write_manager.connect()
    log.info("backup_replication_ready", dual_write=dual_write_manager.status["connected"])

    # ── Initialize components ──────────────────────────────────────────────
    signal_repo = get_signals_repo()
    subscriber_repo = get_subscribers_repo()

    risk_manager = RiskManager()
    daily_state = DailyState()
    signal_engine = SignalEngine(
        risk_manager=risk_manager,
        daily_state=daily_state,
        event_bus=event_bus,
    )
    await signal_engine.load_dedup_state()

    telegram = TelegramDelivery()
    trade_lifecycle = TradeLifecycleManager(
        telegram=telegram,
        training_logger=training_logger,
        signal_repo=signal_repo,
    )
    sim_executor = SimExecutor(signal_repo=signal_repo)
    tracker = PerformanceTracker(telegram)

    # ── Subscribe event handlers ───────────────────────────────────────────
    from marketmate.analytics.ml.ranking import signal_ranking_model
    from marketmate.analytics.ml.scoring import adaptive_scorer
    from marketmate.analytics.ml.prediction import price_predictor
    # ML singletons auto-subscribe to EventBus on import; import triggers init

    # ── Telegram webhook setup ─────────────────────────────────────────────
    try:
        from telegram import Bot
        bot = Bot(token=cfg.telegram.bot_token)
        bot_info = await bot.get_me()
        set_bot_username(bot_info.username or "")
        render_host = os.getenv("RENDER_EXTERNAL_HOSTNAME", "")
        if render_host:
            # SECURITY: Use a separate path token for the URL (not the same as
            # the header secret). This prevents the webhook_secret from appearing
            # in server logs, CDN logs, etc.
            path_token = cfg.telegram.webhook_path_token or cfg.telegram.webhook_secret
            webhook_url = f"https://{render_host}/webhook/{path_token}"
            await bot.set_webhook(url=webhook_url, secret_token=cfg.telegram.webhook_secret)
            log.info("webhook_registered", url=webhook_url)
    except Exception as exc:
        log.warning("webhook_setup_failed", error=str(exc))

    # ── Startup alert ──────────────────────────────────────────────────────
    try:
        mongo_ok = "connected" if mongo_manager.status["connected"] else "offline"
        dual_ok = "active" if dual_write_manager.status["connected"] else "off"
        await telegram.send_alert(
            "MarketMate Online",
            f"Pairs: {', '.join(cfg.strategy.pairs)}\n"
            f"Max trades/day: {cfg.strategy.max_trades_per_day}\n"
            f"MongoDB: {mongo_ok}\n"
            f"Dual-write: {dual_ok}\n"
            f"MATE: active\n"
            f"Architecture: v9.0.0 · 8-Brain + State Engine + Observer",
        )
    except Exception:
        pass

    # ── Start background scheduler ─────────────────────────────────────────
    scheduler = Scheduler(
        signal_engine=signal_engine,
        trade_lifecycle_manager=trade_lifecycle,
        tracker=tracker,
        telegram=telegram,
    )

    # Add backup scheduler as a background task
    scheduler.add_task("backup_scheduler", backup_scheduler.run_loop)

    await scheduler.start()
    log.info("scheduler_started")

    # ── Social Marketing Engine ────────────────────────────────────────────
    from marketmate.platform.social_scheduler import social_scheduler
    from marketmate.platform.social_publishers import get_configured_platforms
    configured_platforms = get_configured_platforms()
    await social_scheduler.start()
    log.info("social_engine_ready",
             enabled=cfg.social.enabled,
             platforms=configured_platforms,
             auto_generate=cfg.social.auto_generate)

    # Update startup alert with social engine status
    try:
        platform_str = ", ".join(configured_platforms) if configured_platforms else "none configured"
        await telegram.send_alert(
            "Social Engine Online",
            f"Platforms: {platform_str}\n"
            f"AI Generation: {'on' if cfg.social.use_ai_generation else 'off'}\n"
            f"Auto-generate: {'on' if cfg.social.auto_generate else 'off'}\n"
            f"Require Approval: {'yes' if cfg.social.require_approval else 'no'}",
        )
    except Exception:
        pass

    # ── Warm cache on startup (optional) ───────────────────────────────────
    _warm_task = None
    if os.environ.get("WARM_CACHE_ON_STARTUP", "").lower() == "true":
        from marketmate.data.cache import warm_cache
        from marketmate.data.engine import fetch_ohlcv
        from marketmate.db.core import mongo_manager as _mm
        import asyncio
        _warm_task = asyncio.create_task(warm_cache("XAUUSD", ["1d", "4h", "15m", "5m"], _mm, fetch_ohlcv, limit=1500))

    try:
        yield
    finally:
        # Cancel background warm_cache task before closing DB
        if _warm_task and not _warm_task.done():
            _warm_task.cancel()
            try:
                await _warm_task
            except asyncio.CancelledError:
                pass

        await scheduler.stop()
        await social_scheduler.stop()
        await redis_state_store.close()
        await dual_write_manager.close()
        await close_all()
        log.info("state_engine_shutdown")
        try:
            await telegram.send_alert("MarketMate Offline", "Stopped gracefully.")
        except Exception:
            pass
        log.info("marketmate_stopped")


# ─── FastAPI app ───────────────────────────────────────────────────────────

app = FastAPI(
    title="MarketMate",
    description="Market Intelligence Operating System — 8-Brain + State Engine + Observer v9.0.0",
    version="9.0.0",
    lifespan=lifespan,
)

# ─── Rate Limiting (slowapi) ────────────────────────────────────────────────
# Enforces cfg.platform.api_rate_limit_rpm (default: 60 RPM per IP).
# Previously defined in config but never enforced — now active.

try:
    from slowapi import Limiter, _rate_limit_exceeded_handler
    from slowapi.util import get_remote_address
    from slowapi.errors import RateLimitExceeded
    from slowapi.middleware import SlowAPIMiddleware

    _limiter = Limiter(
        key_func=get_remote_address,
        default_limits=[f"{cfg.platform.api_rate_limit_rpm}/minute"],
        enabled=True,
    )
    app.state.limiter = _limiter
    app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
    app.add_middleware(SlowAPIMiddleware)
    log.info("rate_limiting_enabled", rpm=cfg.platform.api_rate_limit_rpm)
except ImportError:
    log.warning("slowapi_not_installed", hint="Rate limiting disabled — pip install slowapi")
except Exception as exc:
    log.warning("rate_limiting_setup_failed", error=str(exc))


# ─── Mount API routers ─────────────────────────────────────────────────────
# Website is now served by Next.js (port 3000). No static file mount needed.

app.include_router(routes_router)
app.include_router(auth_router)
app.include_router(academy_router)
app.include_router(social_router)
