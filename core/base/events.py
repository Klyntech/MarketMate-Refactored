"""
signal_engine/core/events.py
──────────────────────────
Simple async event bus for system-wide events.

Provides a decoupled publish/subscribe mechanism so that modules can
react to domain events (signal created, trade opened, TP hit, etc.)
without importing each other directly.

Thread-safe via asyncio.Lock. All handlers are async callables.
emit() catches exceptions per-handler so a failing subscriber never
blocks the rest of the pipeline.

Singleton ``event_bus`` instance — import from this module:
    from signal_engine.core.events import event_bus
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Callable, Coroutine, Dict, List

from signal_engine.core.logger import get_logger

log = get_logger("events")


# ─── Event Type Constants ──────────────────────────────────────────────────────

class EventType:
    """Canonical event type strings used across the system."""

    # ── Legacy events (pre-v8) ──────────────────────────────────────────
    SIGNAL_CREATED  = "signal_created"
    TRADE_OPENED    = "trade_opened"
    TRADE_CLOSED    = "trade_closed"
    TP_HIT          = "tp_hit"
    LOSS_HIT        = "loss_hit"
    WEEKLY_RECAP    = "weekly_recap_generated"
    TRAINING_SAMPLE = "training_sample_logged"
    SUBSCRIBER_CHANGED = "subscriber_changed"

    # ── Gate events (v8.0.0) ─────────────────────────────────────────────
    GATE_PASSED           = "gate_passed"
    GATE_FAILED           = "gate_failed"
    GATE_FEATURES_COMPUTED = "gate_features_computed"
    GATE_TRACE            = "gate_trace"

    # ── State events (v8.0.0) ─────────────────────────────────────────────
    BIAS_CHANGED    = "bias_changed"
    ZONE_FORMED     = "zone_formed"
    ZONE_EXPIRED    = "zone_expired"
    SWEEP_DETECTED  = "sweep_detected"
    REGIME_CHANGED  = "regime_changed"

    # ── Market events (v8.0.0) ────────────────────────────────────────────
    SESSION_OPENED     = "session_opened"
    SESSION_CLOSED     = "session_closed"
    VOLATILITY_SPIKE   = "volatility_spike"

    # ── System events (v8.0.0) ────────────────────────────────────────────
    SCAN_COMPLETED       = "scan_completed"
    PROVIDER_DEGRADED    = "provider_degraded"
    HEALTH_CHECK_FAILED  = "health_check_failed"


# Type alias for async handler callables
EventHandler = Callable[..., Coroutine]


# ─── EventBus ──────────────────────────────────────────────────────────────────

class EventBus:
    """
    Simple async event bus for system-wide events.

    Features:
      - subscribe / unsubscribe by event type
      - emit calls all registered handlers concurrently
      - per-handler exception isolation
      - asyncio.Lock protects the subscriber registry
      - all events and handler results are logged
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._lock = asyncio.Lock()

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """Register *handler* for *event_type*."""
        self._handlers[event_type].append(handler)
        log.debug(
            "event_subscribed",
            event_type=event_type,
            handler=getattr(handler, "__qualname__", str(handler)),
        )

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """Remove *handler* from *event_type* subscribers."""
        handlers = self._handlers.get(event_type)
        if handlers is None:
            return
        while handler in handlers:
            handlers.remove(handler)
        log.debug(
            "event_unsubscribed",
            event_type=event_type,
            handler=getattr(handler, "__qualname__", str(handler)),
        )

    async def emit(self, event_type: str, payload: dict | None = None) -> None:
        """Fire *event_type* with *payload* to all subscribers."""
        if payload is None:
            payload = {}

        log.debug(
            "event_emitted",
            event_type=event_type,
            payload_keys=list(payload.keys()),
        )

        async with self._lock:
            handlers = list(self._handlers.get(event_type, []))

        if not handlers:
            return

        async def _safe_call(handler: EventHandler) -> None:
            try:
                await handler(**payload)
                log.debug(
                    "event_handler_ok",
                    event_type=event_type,
                    handler=getattr(handler, "__qualname__", str(handler)),
                )
            except Exception as exc:
                log.error(
                    "event_handler_error",
                    event_type=event_type,
                    handler=getattr(handler, "__qualname__", str(handler)),
                    error=str(exc),
                )

        await asyncio.gather(
            *[_safe_call(h) for h in handlers],
            return_exceptions=True,
        )

    def subscriber_count(self, event_type: str) -> int:
        """Return the number of handlers subscribed to *event_type*."""
        return len(self._handlers.get(event_type, []))

    @property
    def event_types(self) -> list[str]:
        """Return all event types that have at least one subscriber."""
        return [k for k, v in self._handlers.items() if v]


# ─── Singleton ─────────────────────────────────────────────────────────────────
event_bus = EventBus()
