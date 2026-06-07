"""
marketmate.mate.observer
────────────────────────
State Observer — subscribes to state transition events and maintains
a hot in-memory cache for MATE brains.

The observer bridges the Event layer and the MATE Interpretation layer:
  State → Events → Observer → MATE brains (instant access to transitions)

Without this, MATE has no way to know about state transitions (bias_changed,
zone_formed, sweep_detected, regime_changed) because the EventStatePipeline
only subscribes to legacy events (signal_created, trade_opened, etc.).

The observer provides:
  1. Recent transition history per symbol (last N diffs)
  2. Global transition timeline (across all symbols)
  3. Transition counters for observability dashboards
  4. Real-time notification of material state changes

This is the "Observability as Non-Negotiable" piece — state inspectors,
event replay, and transition diffs are always visible through this module.

New in Phase 3 (v9.0.0 MATE State Integration).
"""

from __future__ import annotations

from collections import deque
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from marketmate.core.config import cfg
from marketmate.core.events import event_bus, EventType
from marketmate.core.logger import get_logger

log = get_logger("mate.observer")


class StateObserver:
    """
    Observes state transition events and maintains hot caches.

    Subscribes to: bias_changed, zone_formed, zone_expired,
    sweep_detected, regime_changed.

    Maintains:
      - Per-symbol transition deque (last 50 transitions)
      - Global transition deque (last 200 transitions)
      - Transition counters per type
      - Last transition timestamp per symbol

    All data is in-memory for sub-millisecond access by MATE brains.
    """

    MAX_PER_SYMBOL = 50
    MAX_GLOBAL = 200

    def __init__(self) -> None:
        self._per_symbol: Dict[str, deque] = {}
        self._global_timeline: deque = deque(maxlen=self.MAX_GLOBAL)
        self._counters: Dict[str, int] = {
            "bias_changed": 0,
            "zone_formed": 0,
            "zone_expired": 0,
            "sweep_detected": 0,
            "regime_changed": 0,
        }
        self._last_transition_at: Dict[str, datetime] = {}
        self._subscribed = False

    def subscribe(self) -> None:
        """Subscribe to all state transition events from the EventBus."""
        if self._subscribed:
            return

        event_bus.subscribe(EventType.BIAS_CHANGED, self._on_bias_changed)
        event_bus.subscribe(EventType.ZONE_FORMED, self._on_zone_formed)
        event_bus.subscribe(EventType.ZONE_EXPIRED, self._on_zone_expired)
        event_bus.subscribe(EventType.SWEEP_DETECTED, self._on_sweep_detected)
        event_bus.subscribe(EventType.REGIME_CHANGED, self._on_regime_changed)

        self._subscribed = True
        log.info("state_observer_subscribed")

    # ═════════════════════════════════════════════════════════════════════════
    # Event Handlers
    # ═════════════════════════════════════════════════════════════════════════

    async def _on_bias_changed(self, **kwargs) -> None:
        """Handle bias_changed event."""
        symbol = kwargs.get("symbol", "")
        if not symbol:
            return

        transition = {
            "event_type": "bias_changed",
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "old_bias": kwargs.get("old_bias", ""),
            "new_bias": kwargs.get("new_bias", ""),
            "conviction_score": kwargs.get("conviction_score", 0),
            "resolution_path": kwargs.get("resolution_path", ""),
        }

        self._record_transition(symbol, transition)
        log.info(
            "observer_bias_changed",
            symbol=symbol,
            old_bias=transition["old_bias"],
            new_bias=transition["new_bias"],
            conviction=transition["conviction_score"],
        )

    async def _on_zone_formed(self, **kwargs) -> None:
        """Handle zone_formed event."""
        symbol = kwargs.get("symbol", "")
        if not symbol:
            return

        transition = {
            "event_type": "zone_formed",
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "zone_type": kwargs.get("zone_type", ""),
            "direction": kwargs.get("direction", ""),
            "zone_high": kwargs.get("zone_high", 0),
            "zone_low": kwargs.get("zone_low", 0),
            "freshness_score": kwargs.get("freshness_score", 0),
        }

        self._record_transition(symbol, transition)
        log.info(
            "observer_zone_formed",
            symbol=symbol,
            zone_type=transition["zone_type"],
            direction=transition["direction"],
        )

    async def _on_zone_expired(self, **kwargs) -> None:
        """Handle zone_expired event."""
        symbol = kwargs.get("symbol", "")
        if not symbol:
            return

        transition = {
            "event_type": "zone_expired",
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "zone_type": kwargs.get("zone_type", ""),
            "direction": kwargs.get("direction", ""),
        }

        self._record_transition(symbol, transition)
        log.info(
            "observer_zone_expired",
            symbol=symbol,
            zone_type=transition["zone_type"],
        )

    async def _on_sweep_detected(self, **kwargs) -> None:
        """Handle sweep_detected event."""
        symbol = kwargs.get("symbol", "")
        if not symbol:
            return

        transition = {
            "event_type": "sweep_detected",
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "swept_level": kwargs.get("swept_level", 0),
            "sweep_type": kwargs.get("sweep_type", ""),
            "direction": kwargs.get("direction", ""),
            "available_levels": kwargs.get("available_levels", 0),
        }

        self._record_transition(symbol, transition)
        log.info(
            "observer_sweep_detected",
            symbol=symbol,
            sweep_type=transition["sweep_type"],
            direction=transition["direction"],
        )

    async def _on_regime_changed(self, **kwargs) -> None:
        """Handle regime_changed event."""
        symbol = kwargs.get("symbol", "")
        if not symbol:
            return

        transition = {
            "event_type": "regime_changed",
            "symbol": symbol,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "old_regime": kwargs.get("old_regime", ""),
            "new_regime": kwargs.get("new_regime", ""),
            "conviction_score": kwargs.get("conviction_score", 0),
        }

        self._record_transition(symbol, transition)
        log.info(
            "observer_regime_changed",
            symbol=symbol,
            old_regime=transition["old_regime"],
            new_regime=transition["new_regime"],
        )

    # ═════════════════════════════════════════════════════════════════════════
    # Internal Recording
    # ═════════════════════════════════════════════════════════════════════════

    def _record_transition(self, symbol: str, transition: Dict[str, Any]) -> None:
        """Record a transition in per-symbol and global deques."""
        now = datetime.now(timezone.utc)

        # Per-symbol deque
        if symbol not in self._per_symbol:
            self._per_symbol[symbol] = deque(maxlen=self.MAX_PER_SYMBOL)
        self._per_symbol[symbol].append(transition)

        # Global timeline
        self._global_timeline.append(transition)

        # Counters
        event_type = transition.get("event_type", "")
        if event_type in self._counters:
            self._counters[event_type] += 1

        # Last transition timestamp
        self._last_transition_at[symbol] = now

    # ═════════════════════════════════════════════════════════════════════════
    # Public Query API — used by StateIntelBrain and API routes
    # ═════════════════════════════════════════════════════════════════════════

    def get_recent_transitions(
        self, symbol: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        """Get recent transitions for a specific symbol."""
        transitions = self._per_symbol.get(symbol, deque())
        return list(transitions)[-limit:]

    def get_all_recent_transitions(self, limit: int = 50) -> List[Dict[str, Any]]:
        """Get recent transitions across all symbols."""
        return list(self._global_timeline)[-limit:]

    def get_transition_counters(self) -> Dict[str, int]:
        """Get transition counters per event type."""
        return dict(self._counters)

    def get_last_transition_time(self, symbol: str) -> Optional[str]:
        """Get the ISO timestamp of the last transition for a symbol."""
        ts = self._last_transition_at.get(symbol)
        return ts.isoformat() if ts else None

    def get_symbols_with_transitions(self) -> List[str]:
        """Get all symbols that have recorded transitions."""
        return list(self._per_symbol.keys())

    @property
    def status(self) -> Dict[str, Any]:
        """Return observer status for diagnostics."""
        return {
            "subscribed": self._subscribed,
            "total_transitions_recorded": sum(self._counters.values()),
            "counters": dict(self._counters),
            "symbols_tracked": len(self._per_symbol),
            "global_timeline_size": len(self._global_timeline),
            "symbols": list(self._per_symbol.keys()),
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

state_observer = StateObserver()
