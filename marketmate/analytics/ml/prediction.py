"""
marketmate.analytics.ml.prediction
───────────────────────────────────
Price prediction stub.

Neural network / transformer-based price prediction model that
forecasts short-term price movement direction and magnitude.
Falls back gracefully when no model is available.

IMPORTANT: This module must NEVER be in the import path of production code.
It subscribes to EventBus events independently. If the model cannot load,
the signal pipeline proceeds without prediction input — no production
code path depends on this module's output.
"""

from __future__ import annotations

from typing import Optional

from marketmate.core.logger import get_logger
from marketmate.core.events import event_bus, EventType

log = get_logger("ml.prediction")


class PricePredictor:
    """
    Experimental price prediction model.

    In production, this would:
      - Load a trained time-series model (LSTM, Transformer, etc.)
      - Accept OHLCV candle data and technical features as input
      - Output predicted price direction and confidence for the
        next N candles
      - Feed predictions into the signal ranking model as an
        additional confluence factor

    For now, this is a stub that always returns None to indicate
    "no prediction available" — callers should proceed without
    ML price input.
    """

    def __init__(self) -> None:
        self._model = None
        self._loaded = False
        self._subscribe()

    def _subscribe(self) -> None:
        """Subscribe to signal events for prediction validation."""
        event_bus.subscribe(EventType.SIGNAL_CREATED, self._on_signal_created)
        log.info("ml_prediction_subscribed", event_type=EventType.SIGNAL_CREATED)

    async def _on_signal_created(self, **payload) -> None:
        """
        EventBus handler: validate prediction against actual signal.

        In the future, this would:
          1. Compare the model's prior prediction with the signal's
             actual entry direction
          2. Record accuracy metrics
          3. Use the signal as a new training sample

        For now, it simply logs the event.
        """
        signal_id = payload.get("signal_id", "unknown")
        direction = payload.get("direction", "unknown")
        log.debug("ml_prediction_signal_created",
                  signal_id=signal_id, direction=direction)

    async def load(self, model_path: Optional[str] = None) -> bool:
        """
        Load a trained prediction model from disk.

        Stub: always returns False (no model available).
        """
        log.info("ml_prediction_load_attempt", path=model_path)
        self._loaded = False
        return False

    async def predict(
        self,
        candle_data: list[dict],
        symbol: str = "XAUUSD",
        horizon_bars: int = 4,
    ) -> Optional[dict]:
        """
        Predict price direction and magnitude.

        Args:
            candle_data: Recent OHLCV candles as list of dicts.
            symbol: Trading symbol.
            horizon_bars: Number of bars ahead to predict.

        Returns:
            Dict with keys:
              - direction: "BUY" | "SELL" | "NEUTRAL"
              - confidence: float (0.0–1.0)
              - predicted_move_pct: float (expected % move)
              - horizon_bars: int
            Or None if the model is not available.

        Stub: always returns None.
        """
        if not self._loaded or self._model is None:
            return None

        # In production:
        #   features = self._extract_features(candle_data)
        #   raw = self._model.predict(features)
        #   return {
        #       "direction": self._decode_direction(raw),
        #       "confidence": float(raw["confidence"]),
        #       "predicted_move_pct": float(raw["move_pct"]),
        #       "horizon_bars": horizon_bars,
        #   }

        return None

    async def predict_direction(
        self,
        candle_data: list[dict],
        symbol: str = "XAUUSD",
    ) -> Optional[str]:
        """
        Convenience method: predict only the direction.

        Returns:
            "BUY", "SELL", or "NEUTRAL", or None if no model.
        """
        result = await self.predict(candle_data, symbol)
        if result is None:
            return None
        return result.get("direction", "NEUTRAL")

    @property
    def is_loaded(self) -> bool:
        """Return True if a prediction model is loaded and ready."""
        return self._loaded


# ─── Module-level singleton ───────────────────────────────────────────────────
price_predictor = PricePredictor()
