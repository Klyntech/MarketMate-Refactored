"""
marketmate.analytics.ml.ranking
────────────────────────────────
Signal ranking model stub.

Uses EventBus to subscribe to signal_created events and ranks signals
by predicted quality. Falls back gracefully if the model is not loaded.

IMPORTANT: This module must NEVER be in the import path of production code.
It subscribes to EventBus events independently. If the model cannot load
or is not configured, all ranking falls back to the static weighted scorer
in the strategy module.
"""

from __future__ import annotations

from typing import Optional

from marketmate.core.logger import get_logger
from marketmate.core.events import event_bus, EventType

log = get_logger("ml.ranking")


class SignalRankingModel:
    """
    Experimental signal ranking model.

    In production, this would load a trained model (e.g. XGBoost, LightGBM)
    and predict a quality score for each signal. For now, this is a stub
    that returns None to indicate "no ML ranking available" — callers
    should fall back to the static weighted scorer.

    Lifecycle:
      1. On init, subscribe to signal_created events on the EventBus.
      2. When a signal_created event fires, optionally compute a ranking
         score asynchronously.
      3. If the model fails to load or predict, return None gracefully.
    """

    def __init__(self) -> None:
        self._model = None
        self._loaded = False
        self._subscribe()

    def _subscribe(self) -> None:
        """Subscribe to EventBus events for signal ranking."""
        event_bus.subscribe(EventType.SIGNAL_CREATED, self._on_signal_created)
        log.info("ml_ranking_subscribed", event_type=EventType.SIGNAL_CREATED)

    async def _on_signal_created(self, **payload) -> None:
        """
        EventBus handler: called when a new signal is created.

        In the future, this would:
          1. Extract features from the signal payload
          2. Run the model prediction
          3. Emit a ranking event or store the score

        For now, it simply logs that the event was received.
        """
        signal_id = payload.get("signal_id", "unknown")
        log.debug("ml_ranking_signal_received", signal_id=signal_id)

        score = await self.predict(payload)
        if score is not None:
            log.info("ml_ranking_score",
                     signal_id=signal_id, score=score)
        else:
            log.debug("ml_ranking_no_model", signal_id=signal_id)

    async def load(self, model_path: Optional[str] = None) -> bool:
        """
        Load a trained ranking model from disk.

        Stub: always returns False (model not available).
        In production, this would load a serialized model file.
        """
        log.info("ml_ranking_load_attempt", path=model_path)
        # Stub: no model file available
        self._loaded = False
        return False

    async def predict(self, signal_data: dict) -> Optional[float]:
        """
        Predict a ranking score for a signal.

        Returns:
            Float score (0.0–1.0) if the model is loaded, or None if
            the model is not available. Callers should fall back to the
            static weighted scorer when None is returned.

        Stub: always returns None (no model loaded).
        """
        if not self._loaded or self._model is None:
            return None

        # In production:
        #   features = self._extract_features(signal_data)
        #   score = self._model.predict(features)
        #   return float(score)

        return None

    @property
    def is_loaded(self) -> bool:
        """Return True if a ranking model is loaded and ready."""
        return self._loaded


# ─── Module-level singleton ───────────────────────────────────────────────────
# Lazily instantiated on first import. Safe to import — subscribing to
# events is side-effect-free (no model loaded, no prediction attempted).
signal_ranking_model = SignalRankingModel()
