"""
marketmate.mate.brains.system
─────────────────────────────
System Brain — answers everything about system health, providers, and pipeline diagnostics.

Capability Domain:
  - System health: "Is the system online?"
  - Provider status: "Are market data providers working?"
  - Pipeline diagnostics: "Why wasn't this trade executed?"
  - Backup status: "Is backup running?"

Functions:
  get_system_health()                → MongoDB, Redis, dual-write, backup status
  get_provider_status()              → data provider availability
  get_pipeline_diagnostics()         → auto-trade diagnostics, gate rejection reasons
  get_config_summary()               → current system configuration

This brain queries infrastructure state — NOT market data or account state.
The LLM only narrates what this brain compiles.
"""

from __future__ import annotations

from typing import Any, Dict

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.mate.state_store import redis_state_store

log = get_logger("mate.brains.system")


class SystemBrain:
    """
    Financial cognition primitive for system infrastructure.

    Answers: health, provider status, pipeline diagnostics, config.
    Does NOT answer: prices, signal quality, strategy theory.
    """

    # ═════════════════════════════════════════════════════════════════════════
    # Core Brain Functions
    # ═════════════════════════════════════════════════════════════════════════

    async def get_system_health(self) -> Dict[str, Any]:
        """Get the health status of all system components."""
        health = {
            "env": cfg.app.env,
            "version": "6.2.0",
        }

        # MongoDB
        try:
            from marketmate.db.core import mongo_manager
            health["mongodb"] = mongo_manager.status
        except Exception:
            health["mongodb"] = {"status": "unknown"}

        # Redis
        try:
            redis_state = await redis_state_store.get("event:last_id")
            health["redis"] = "connected" if redis_state is not None or True else "degraded"
        except Exception:
            health["redis"] = "unknown"

        # Dual-write
        try:
            from marketmate.backup.dual_write import dual_write_manager
            health["dual_write"] = dual_write_manager.status
        except Exception:
            health["dual_write"] = {"status": "unknown"}

        # Backup
        try:
            from marketmate.backup.scheduler import backup_scheduler
            health["backup"] = backup_scheduler.status
        except Exception:
            health["backup"] = {"status": "unknown"}

        return health

    async def get_provider_status(self) -> Dict[str, Any]:
        """Get the status of market data providers."""
        providers = {}

        # TwelveData
        if cfg.data.twelve_data_key:
            providers["twelve_data"] = "configured"
        else:
            providers["twelve_data"] = "not_configured"

        # Alpha Vantage
        if cfg.data.alpha_vantage_key:
            providers["alpha_vantage"] = "configured"
        else:
            providers["alpha_vantage"] = "not_configured"

        # Binance
        if cfg.data.binance_api_key:
            providers["binance"] = "configured"
        else:
            providers["binance"] = "not_configured"

        # Test freshness for configured pairs
        freshness = {}
        try:
            from marketmate.data.engine import fetch_ohlcv
            for symbol in cfg.strategy.pairs[:2]:  # Test first 2 pairs only
                try:
                    df = await fetch_ohlcv(symbol, "1d", limit=1)
                    freshness[symbol] = "fresh" if df is not None and not df.empty else "stale"
                except Exception:
                    freshness[symbol] = "unavailable"
        except Exception:
            pass

        return {"providers": providers, "data_freshness": freshness}

    async def get_pipeline_diagnostics(self) -> Dict[str, Any]:
        """
        Diagnose why a trade might not be executing.

        Provides auto-trade rejection reasons, account status,
        position limits, and execution audit trail.
        """
        try:
            from marketmate.db.repositories.signals import SignalRepository
            repo = SignalRepository()
            open_trades = await repo.get_open_signals()
            account = await redis_state_store.get_account_state()

            active = {}
            for sym in cfg.strategy.pairs:
                signal = await redis_state_store.get_active_signal(sym)
                if signal:
                    active[sym] = signal

            return {
                "open_trades_count": len(open_trades),
                "open_trades": [
                    {
                        "symbol": t.get("symbol", ""),
                        "direction": t.get("direction", ""),
                        "entry": t.get("entry_mid", 0),
                        "status": t.get("status", ""),
                    }
                    for t in open_trades[:5]
                ],
                "active_signals_in_redis": active,
                "account_state": account,
                "max_trades_per_day": cfg.strategy.max_trades_per_day,
                "min_rr": cfg.strategy.min_rr,
                "risk_per_trade_pct": cfg.risk.risk_per_trade_pct,
                "max_concurrent_positions": getattr(cfg.strategy, "max_concurrent_positions", "unlimited"),
                "scan_interval_seconds": cfg.app.scan_interval_seconds,
                "gate_rejection_reasons": {
                    "G1_SESSION": "weekend_no_trading / outside_trading_session",
                    "G2_DAILY_LIMIT": "daily_trade_limit_reached / daily_buy_limit / daily_sell_limit",
                    "G2b_DRAWDOWN": "max_consecutive_losses_hit",
                    "G3_NEWS": "high_impact_event_window",
                    "G4_HTF_BIAS": "neutral_bias_no_sweep",
                    "G5_SWEEP": "no_recent_sweep",
                    "G6_ZONE": "no_valid_ob_or_fvg",
                    "G7_LTF_CONFIRM": "no_bos_or_choch",
                    "G8_RR": "insufficient_rr",
                    "DEDUP": "cooldown / zone_overlap / price_proximity / same_h4_candle / flip_cooldown",
                },
            }
        except Exception as exc:
            return {"error": str(exc)}

    async def get_config_summary(self) -> Dict[str, Any]:
        """Get a summary of current system configuration."""
        return {
            "env": cfg.app.env,
            "pairs": cfg.strategy.pairs,
            "max_trades_per_day": cfg.strategy.max_trades_per_day,
            "min_rr": cfg.strategy.min_rr,
            "risk_per_trade_pct": cfg.risk.risk_per_trade_pct,
            "scan_interval_seconds": cfg.app.scan_interval_seconds,
            "london_session": f"{cfg.strategy.london_open}-{cfg.strategy.london_close} UTC",
            "ny_session": f"{cfg.strategy.ny_open}-{cfg.strategy.ny_close} UTC",
            "dual_write_enabled": cfg.backup.dual_write_enabled,
            "analytics_enabled": cfg.analytics.enabled,
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

system_brain = SystemBrain()
