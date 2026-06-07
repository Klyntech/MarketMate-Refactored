"""
marketmate.mate.pipeline
─────────────────────────
Event-to-State Pipeline — converts domain events into compiled Redis state.

Subscribes to EventBus events and updates the Redis state store
with precomputed, structured outputs. This is the bridge between
the raw event stream and the MATE intelligence layer.

Event Handlers:
  signal_created  → update symbol state (bias, last signal time, zone)
  trade_opened    → set active signal, update account state
  trade_closed    → remove active signal, update account state, update metrics
  tp_hit          → update symbol state (TP level hit)
  loss_hit        → update symbol state (SL hit)

The pipeline is incremental: it only updates the parts of state that
changed, not the entire document. This keeps Redis writes fast.

Bootstrap:
  On startup, bootstrap() pre-populates Redis from MongoDB so MATE
  has data immediately — even before any new events fire.
  Without bootstrap, Redis is empty after every restart, causing
  MATE to say "No data available".
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.core.events import event_bus, EventType
from marketmate.mate.state_store import redis_state_store

log = get_logger("mate.pipeline")


class EventStatePipeline:
    """
    Converts domain events into compiled Redis state.

    Subscribes to the EventBus and updates the Redis state store
    with structured, precomputed data that the MATE layer can
    read without touching the database.

    Phase 3 upgrade: Now also subscribes to state transition events
    (bias_changed, zone_formed, sweep_detected, regime_changed) so
    the MATE layer's Redis cache is updated from the v8.0.0 StateEngine
    output, not just from legacy signal/trade events.

    On startup, the ``bootstrap()`` method pre-populates Redis
    from MongoDB so MATE has data immediately — even before any
    new events fire.  Without bootstrap, Redis is empty after
    every restart, causing MATE to say "No data available".
    """

    def __init__(self) -> None:
        self._subscribed = False
        self._bootstrapped = False

    def subscribe(self) -> None:
        """Subscribe to all relevant EventBus events."""
        if self._subscribed:
            return

        # Legacy events (signal/trade lifecycle)
        event_bus.subscribe(EventType.SIGNAL_CREATED, self._on_signal_created)
        event_bus.subscribe(EventType.TRADE_OPENED, self._on_trade_opened)
        event_bus.subscribe(EventType.TRADE_CLOSED, self._on_trade_closed)
        event_bus.subscribe(EventType.TP_HIT, self._on_tp_hit)
        event_bus.subscribe(EventType.LOSS_HIT, self._on_loss_hit)

        # State transition events (Phase 3: MATE consumes compiled state)
        event_bus.subscribe(EventType.BIAS_CHANGED, self._on_bias_changed)
        event_bus.subscribe(EventType.ZONE_FORMED, self._on_zone_formed)
        event_bus.subscribe(EventType.ZONE_EXPIRED, self._on_zone_expired)
        event_bus.subscribe(EventType.SWEEP_DETECTED, self._on_sweep_detected)
        event_bus.subscribe(EventType.REGIME_CHANGED, self._on_regime_changed)

        self._subscribed = True
        log.info("event_state_pipeline_subscribed", events="legacy+state_transitions")

    # ═════════════════════════════════════════════════════════════════════════
    # Event Handlers
    # ═════════════════════════════════════════════════════════════════════════

    async def _on_signal_created(self, **kwargs) -> None:
        """Update symbol state when a new signal is created."""
        signal_data = kwargs.get("signal", {})
        if not signal_data:
            return

        symbol = signal_data.get("symbol", "")
        if not symbol:
            return

        state = await redis_state_store.get_symbol_state(symbol) or {}
        state.update({
            "last_signal_id": signal_data.get("id", ""),
            "last_signal_direction": signal_data.get("direction", ""),
            "last_signal_time": datetime.now(timezone.utc).isoformat(),
            "last_signal_confidence": signal_data.get("confidence", ""),
            "last_signal_rr": signal_data.get("rr", 0),
            "last_zone_type": signal_data.get("zone_type", ""),
            "bias": signal_data.get("direction", "").lower(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })

        await redis_state_store.set_symbol_state(symbol, state)
        log.debug("pipeline_signal_created", symbol=symbol)

    async def _on_trade_opened(self, **kwargs) -> None:
        """Set active signal and update account state on trade open."""
        symbol = kwargs.get("symbol", "")
        signal_id = kwargs.get("signal_id", "")

        # Set active signal
        if symbol:
            signal_state = {
                "signal_id": signal_id,
                "direction": kwargs.get("direction", ""),
                "entry": kwargs.get("entry_price", 0),
                "stop_loss": kwargs.get("stop_loss", 0),
                "tp1": kwargs.get("tp1", 0),
                "tp2": kwargs.get("tp2", 0),
                "opened_at": datetime.now(timezone.utc).isoformat(),
            }
            await redis_state_store.set_active_signal(symbol, signal_state)

        # Update account state (open trade count)
        await self._refresh_account_state()

        log.debug("pipeline_trade_opened", symbol=symbol, signal_id=signal_id)

    async def _on_trade_closed(self, **kwargs) -> None:
        """Remove active signal, update metrics on trade close."""
        symbol = kwargs.get("symbol", "")
        signal_id = kwargs.get("signal_id", "")
        outcome = kwargs.get("outcome", "")

        # Remove active signal
        if symbol:
            await redis_state_store.remove_active_signal(symbol)

        # Update symbol state
        if symbol:
            state = await redis_state_store.get_symbol_state(symbol) or {}
            state["last_outcome"] = outcome
            state["last_close_time"] = datetime.now(timezone.utc).isoformat()
            state["rr_realized"] = kwargs.get("rr_realized", 0)
            state["pnl_pct"] = kwargs.get("pnl_pct", 0)
            await redis_state_store.set_symbol_state(symbol, state)

        # Refresh account state and performance metrics
        await self._refresh_account_state()
        await self._refresh_performance_metrics()

        log.debug("pipeline_trade_closed", symbol=symbol, signal_id=signal_id)

    async def _on_tp_hit(self, **kwargs) -> None:
        """Update symbol state on TP hit."""
        symbol = kwargs.get("symbol", "")
        if symbol:
            state = await redis_state_store.get_symbol_state(symbol) or {}
            state["last_tp_level"] = kwargs.get("level", "")
            state["last_tp_price"] = kwargs.get("price", 0)
            await redis_state_store.set_symbol_state(symbol, state)

    async def _on_loss_hit(self, **kwargs) -> None:
        """Update symbol state on SL hit."""
        symbol = kwargs.get("symbol", "")
        if symbol:
            state = await redis_state_store.get_symbol_state(symbol) or {}
            state["last_loss_time"] = datetime.now(timezone.utc).isoformat()
            state["last_loss_price"] = kwargs.get("exit_price", 0)
            await redis_state_store.set_symbol_state(symbol, state)

    # ═════════════════════════════════════════════════════════════════════════
    # State Transition Handlers (Phase 3)
    # ═════════════════════════════════════════════════════════════════════════

    async def _on_bias_changed(self, **kwargs) -> None:
        """Update symbol state when bias changes (from StateEngine)."""
        symbol = kwargs.get("symbol", "")
        if not symbol:
            return

        state = await redis_state_store.get_symbol_state(symbol) or {}
        state.update({
            "bias": kwargs.get("new_bias", ""),
            "conviction_score": kwargs.get("conviction_score", 0),
            "resolution_path": kwargs.get("resolution_path", ""),
            "daily_ema200": kwargs.get("daily_ema200", 0),
            "h4_ema200": kwargs.get("h4_ema200", 0),
            "bias_changed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        await redis_state_store.set_symbol_state(symbol, state)
        log.debug("pipeline_bias_changed", symbol=symbol, new_bias=kwargs.get("new_bias"))

    async def _on_zone_formed(self, **kwargs) -> None:
        """Update symbol state when a new zone forms (from StateEngine)."""
        symbol = kwargs.get("symbol", "")
        if not symbol:
            return

        state = await redis_state_store.get_symbol_state(symbol) or {}
        state.update({
            "latest_zone_type": kwargs.get("zone_type", ""),
            "latest_zone_direction": kwargs.get("direction", ""),
            "latest_zone_high": kwargs.get("zone_high", 0),
            "latest_zone_low": kwargs.get("zone_low", 0),
            "zone_freshness": kwargs.get("freshness_score", 0),
            "zone_formed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        await redis_state_store.set_symbol_state(symbol, state)
        log.debug("pipeline_zone_formed", symbol=symbol, zone_type=kwargs.get("zone_type"))

    async def _on_zone_expired(self, **kwargs) -> None:
        """Update symbol state when a zone expires."""
        symbol = kwargs.get("symbol", "")
        if not symbol:
            return

        state = await redis_state_store.get_symbol_state(symbol) or {}
        state["zone_expired_at"] = datetime.now(timezone.utc).isoformat()
        state["updated_at"] = datetime.now(timezone.utc).isoformat()
        await redis_state_store.set_symbol_state(symbol, state)
        log.debug("pipeline_zone_expired", symbol=symbol)

    async def _on_sweep_detected(self, **kwargs) -> None:
        """Update symbol state when a liquidity sweep is detected."""
        symbol = kwargs.get("symbol", "")
        if not symbol:
            return

        state = await redis_state_store.get_symbol_state(symbol) or {}
        state.update({
            "sweep_detected": True,
            "sweep_level": kwargs.get("swept_level", 0),
            "sweep_type": kwargs.get("sweep_type", ""),
            "sweep_direction": kwargs.get("direction", ""),
            "available_liquidity_levels": kwargs.get("available_levels", 0),
            "sweep_detected_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        await redis_state_store.set_symbol_state(symbol, state)
        log.debug("pipeline_sweep_detected", symbol=symbol, sweep_type=kwargs.get("sweep_type"))

    async def _on_regime_changed(self, **kwargs) -> None:
        """Update symbol state when market regime changes."""
        symbol = kwargs.get("symbol", "")
        if not symbol:
            return

        state = await redis_state_store.get_symbol_state(symbol) or {}
        state.update({
            "regime": kwargs.get("new_regime", ""),
            "regime_confidence": kwargs.get("confidence", 0),
            "conviction_score": kwargs.get("conviction_score", 0),
            "regime_changed_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        })
        await redis_state_store.set_symbol_state(symbol, state)
        log.debug("pipeline_regime_changed", symbol=symbol, new_regime=kwargs.get("new_regime"))

    # ═════════════════════════════════════════════════════════════════════════
    # Bootstrap — load historical data on startup
    # ═════════════════════════════════════════════════════════════════════════

    async def bootstrap(self) -> None:
        """
        Pre-populate Redis state from MongoDB and VirtualAccountEngine.

        Without this, Redis is empty after every restart and MATE
        says "No data available" until new events fire.  Bootstrap
        loads: account state, performance metrics, open signals,
        and per-symbol state from recent signal history.
        """
        if self._bootstrapped:
            return

        log.info("pipeline_bootstrap_start")
        errors = []

        # 1. Account state from VirtualAccountEngine
        try:
            await self._refresh_account_state()
        except Exception as exc:
            errors.append(f"account_state: {exc}")

        # 2. Performance metrics from VirtualAccountEngine
        try:
            await self._refresh_performance_metrics()
        except Exception as exc:
            errors.append(f"perf_metrics: {exc}")

        # 3. Open signals from MongoDB
        try:
            from marketmate.db import get_signals_repo
            signal_repo = get_signals_repo()
            open_signals = await signal_repo.get_open_signals()

            for signal in open_signals:
                symbol = signal.get("symbol", "")
                if not symbol:
                    continue

                # Set active signal in Redis
                signal_state = {
                    "signal_id": signal.get("signal_id", ""),
                    "direction": signal.get("direction", ""),
                    "entry": signal.get("entry_mid", 0),
                    "stop_loss": signal.get("stop_loss", 0),
                    "tp1": signal.get("tp1", 0),
                    "tp2": signal.get("tp2", 0),
                    "opened_at": str(signal.get("generated_at", "")),
                }
                await redis_state_store.set_active_signal(symbol, signal_state)

                # Set symbol state from signal data
                sym_state = await redis_state_store.get_symbol_state(symbol) or {}
                sym_state.update({
                    "last_signal_id": signal.get("signal_id", ""),
                    "last_signal_direction": signal.get("direction", ""),
                    "last_signal_time": str(signal.get("generated_at", "")),
                    "last_signal_confidence": signal.get("confidence", ""),
                    "last_signal_rr": signal.get("rr", 0),
                    "last_zone_type": signal.get("zone_type", ""),
                    "bias": signal.get("direction", "").lower(),
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                await redis_state_store.set_symbol_state(symbol, sym_state)

            log.info("pipeline_bootstrap_open_signals", count=len(open_signals))
        except Exception as exc:
            errors.append(f"open_signals: {exc}")

        # 4. Recent signal history per symbol (last 20 closed signals)
        try:
            from marketmate.db import get_signals_repo
            signal_repo = get_signals_repo()
            recent = await signal_repo.get_virtual_trade_history(limit=20)

            # Build per-symbol summaries from recent closed trades
            symbol_stats: dict[str, dict] = {}
            for trade in recent:
                symbol = trade.get("symbol", "")
                if not symbol:
                    continue
                if symbol not in symbol_stats:
                    symbol_stats[symbol] = {"wins": 0, "losses": 0, "total_rr": 0.0, "count": 0}
                symbol_stats[symbol]["count"] += 1
                outcome = (trade.get("outcome") or "").upper()
                if outcome == "WIN":
                    symbol_stats[symbol]["wins"] += 1
                elif outcome == "LOSS":
                    symbol_stats[symbol]["losses"] += 1
                symbol_stats[symbol]["total_rr"] += trade.get("pnl_r", 0) or 0

            for symbol, stats in symbol_stats.items():
                state = await redis_state_store.get_symbol_state(symbol) or {}
                state.update({
                    "recent_wins": stats["wins"],
                    "recent_losses": stats["losses"],
                    "recent_total": stats["count"],
                    "recent_avg_rr": round(stats["total_rr"] / max(stats["count"], 1), 2),
                    "last_outcome": (recent[0].get("outcome") or "").upper() if recent else "",
                    "updated_at": datetime.now(timezone.utc).isoformat(),
                })
                await redis_state_store.set_symbol_state(symbol, state)

            log.info("pipeline_bootstrap_signal_history", symbols=list(symbol_stats.keys()))
        except Exception as exc:
            errors.append(f"signal_history: {exc}")

        self._bootstrapped = True

        if errors:
            log.warning("pipeline_bootstrap_partial", errors=errors)
        else:
            log.info("pipeline_bootstrap_complete")

    # ═════════════════════════════════════════════════════════════════════════
    # State Refresh
    # ═════════════════════════════════════════════════════════════════════════

    async def _refresh_account_state(self) -> None:
        """Refresh the compiled account state from the virtual account engine."""
        try:
            from marketmate.virtual_account.engine import get_virtual_account_engine
            engine = get_virtual_account_engine()
            state = await engine.get_state()
            await redis_state_store.set_account_state(state)
        except Exception as exc:
            log.warning("pipeline_account_refresh_failed", error=str(exc))

    async def _refresh_performance_metrics(self) -> None:
        """Refresh performance metrics from the virtual account engine."""
        try:
            from marketmate.virtual_account.engine import get_virtual_account_engine
            engine = get_virtual_account_engine()

            for window in ["7d", "30d"]:
                metrics = await engine.get_metrics(window)
                if metrics:
                    await redis_state_store.set_perf("winrate", window, metrics.win_rate)
                    await redis_state_store.set_perf("avg_rr", window, metrics.avg_rr)
                    await redis_state_store.set_perf("total_trades", window, metrics.total_trades)
                    await redis_state_store.set_perf("profit_factor", window, metrics.profit_factor)
        except Exception as exc:
            log.warning("pipeline_metrics_refresh_failed", error=str(exc))


# ─── Singleton ────────────────────────────────────────────────────────────────

event_state_pipeline = EventStatePipeline()
