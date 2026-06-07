"""
marketmate.analytics.ml.scoring
────────────────────────────────
Adaptive scoring stub.

Learns from historical signal outcomes to adjust the weights of
confluence factors over time. Falls back to the static weighted
scorer defined in marketmate.core.config (SCORE_WEIGHTS) when
no adaptive model is available.

IMPORTANT: This module must NEVER be in the import path of production code.
It subscribes to EventBus events independently. If the model cannot load,
all scoring falls back to the static weighted scorer in config.
"""

from __future__ import annotations

from typing import Optional

from marketmate.core.config import cfg

# Local fallback weights (v1 strategy uses binary confidence, not weighted scoring)
SCORE_WEIGHTS: dict[str, float] = {
    "htf_bias":        0.25,
    "fvg":             0.15,
    "order_block":     0.20,
    "liquidity_sweep": 0.15,
    "ltf_confirmation": 0.15,
    "session_filter":  0.10,
}
from marketmate.core.logger import get_logger
from marketmate.core.events import event_bus, EventType

log = get_logger("ml.scoring")


class AdaptiveScorer:
    """
    Experimental adaptive scoring model.

    In production, this would:
      - Track signal outcomes (via trade_closed events)
      - Adjust confluence factor weights using a learning algorithm
      - Provide updated weights for the scoring pipeline

    For now, this is a stub that always falls back to the static
    SCORE_WEIGHTS defined in marketmate.core.config.
    """

    def __init__(self) -> None:
        self._weights: dict[str, float] = dict(SCORE_WEIGHTS)
        self._adapted = False
        self._subscribe()

    def _subscribe(self) -> None:
        """Subscribe to trade outcome events for weight adaptation."""
        event_bus.subscribe(EventType.TRADE_CLOSED, self._on_trade_closed)
        log.info("ml_scoring_subscribed", event_type=EventType.TRADE_CLOSED)

    async def _on_trade_closed(self, **payload) -> None:
        """
        EventBus handler: called when a trade is closed.

        In the future, this would:
          1. Record the outcome (win/loss, R-multiple)
          2. Update weight estimates based on which confluence
             factors were present in the original signal
          3. Periodically retrain the weight model

        For now, it simply logs the event.
        """
        signal_id = payload.get("signal_id", "unknown")
        outcome = payload.get("outcome", "unknown")
        log.debug("ml_scoring_trade_closed",
                  signal_id=signal_id, outcome=outcome)

    async def adapt(self, signal_outcomes: list[dict]) -> bool:
        """
        Adapt scoring weights based on historical signal outcomes.

        Args:
            signal_outcomes: List of dicts with keys:
                - signal_id, outcome, r_multiple, confluence_factors

        Returns:
            True if weights were updated, False if adaptation failed
            or is not available.

        Stub: always returns False (no adaptation available).
        """
        log.info("ml_scoring_adapt_attempt",
                 sample_count=len(signal_outcomes))
        # Stub: no adaptation logic implemented
        self._adapted = False
        return False

    def get_weights(self) -> dict[str, float]:
        """
        Return current scoring weights.

        If adaptive weights are available, returns those.
        Otherwise, falls back to the static SCORE_WEIGHTS from config.
        """
        if self._adapted and self._weights:
            return dict(self._weights)
        return dict(SCORE_WEIGHTS)

    async def score_signal(self, confluence_factors: dict[str, float]) -> Optional[float]:
        """
        Compute an adaptive composite score for a signal.

        Args:
            confluence_factors: Dict mapping factor names to their
                individual scores (0.0–1.0), e.g.:
                {"htf_bias": 0.9, "fvg": 0.5, "order_block": 0.8, ...}

        Returns:
            Weighted composite score (0.0–1.0), or None if adaptive
            scoring is not available. Callers should fall back to
            the static weighted scorer when None is returned.

        Stub: always returns None (use static scorer instead).
        """
        if not self._adapted:
            return None

        # In production:
        #   weights = self.get_weights()
        #   score = sum(weights.get(k, 0) * v for k, v in confluence_factors.items())
        #   return min(score, 1.0)

        return None

    @property
    def is_adapted(self) -> bool:
        """Return True if adaptive weights are available."""
        return self._adapted


# ─── Module-level singleton ───────────────────────────────────────────────────
adaptive_scorer = AdaptiveScorer()
