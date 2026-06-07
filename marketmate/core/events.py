"""
marketmate/core/events.py
──────────────────────────
Simple async event bus for system-wide events.

Provides a decoupled publish/subscribe mechanism so that modules can
react to domain events (signal created, trade opened, TP hit, etc.)
without importing each other directly.

Thread-safe via asyncio.Lock. All handlers are async callables.
emit() catches exceptions per-handler so a failing subscriber never
blocks the rest of the pipeline.

Singleton ``event_bus`` instance — import from this module:
    from marketmate.core.events import event_bus
"""

from __future__ import annotations

import asyncio
from collections import defaultdict
from typing import Callable, Coroutine, Dict, List

from marketmate.core.logger import get_logger

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
      - per-handler exception isolation — one bad handler never kills the chain
      - asyncio.Lock protects the subscriber registry
      - all events and handler results are logged
    """

    def __init__(self) -> None:
        self._handlers: Dict[str, List[EventHandler]] = defaultdict(list)
        self._lock = asyncio.Lock()

    # ── Subscribe ─────────────────────────────────────────────────────────────

    def subscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        Register *handler* for *event_type*.

        Handlers are async callables that accept keyword arguments
        matching the event payload dict keys.  Duplicate registrations
        are allowed — the handler will be called once per subscription.
        """
        self._handlers[event_type].append(handler)
        log.debug(
            "event_subscribed",
            event_type=event_type,
            handler=getattr(handler, "__qualname__", str(handler)),
        )

    # ── Unsubscribe ───────────────────────────────────────────────────────────

    def unsubscribe(self, event_type: str, handler: EventHandler) -> None:
        """
        Remove *handler* from *event_type* subscribers.

        No-op if the handler was not subscribed.
        """
        handlers = self._handlers.get(event_type)
        if handlers is None:
            return
        # Remove all occurrences (defensive — shouldn't have dups but safe)
        while handler in handlers:
            handlers.remove(handler)
        log.debug(
            "event_unsubscribed",
            event_type=event_type,
            handler=getattr(handler, "__qualname__", str(handler)),
        )

    # ── Emit ──────────────────────────────────────────────────────────────────

    async def emit(self, event_type: str, payload: dict | None = None) -> None:
        """
        Fire *event_type* with *payload* to all subscribers.

        Each handler is called as an independent asyncio.Task so that
        a slow or failing handler does not block the others.  Exceptions
        are caught per-handler and logged — they never propagate to the
        caller.

        v8.0.0: Optionally validates payload against registered schema
        if core.schemas is importable.
        """
        if payload is None:
            payload = {}

        # ── Schema validation (best-effort) ────────────────────────────────
        validated_event = None
        try:
            from marketmate.core.schemas import validate_event
            validated_event = validate_event(event_type, payload)
        except ImportError:
            pass  # schemas module not available — skip validation
        except Exception as exc:
            log.warning(
                "event_schema_validation_error",
                event_type=event_type,
                error=str(exc),
            )

        log.debug(
            "event_emitted",
            event_type=event_type,
            payload_keys=list(payload.keys()),
            schema_validated=validated_event is not None,
        )

        # Snapshot the handler list under the lock so we don't hold it
        # while awaiting handlers.
        async with self._lock:
            handlers = list(self._handlers.get(event_type, []))

        if not handlers:
            return

        # Run all handlers concurrently, catching exceptions individually.
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

    # ── Introspection ─────────────────────────────────────────────────────────

    def subscriber_count(self, event_type: str) -> int:
        """Return the number of handlers subscribed to *event_type*."""
        return len(self._handlers.get(event_type, []))

    @property
    def event_types(self) -> list[str]:
        """Return all event types that have at least one subscriber."""
        return [k for k, v in self._handlers.items() if v]


# ─── Singleton ─────────────────────────────────────────────────────────────────
# Import this wherever you need the event bus:
#     from marketmate.core.events import event_bus

event_bus = EventBus()
