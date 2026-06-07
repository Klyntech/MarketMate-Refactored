"""
marketmate.analytics.ml.reinforcement
──────────────────────────────────────
RL risk management stub.

Reinforcement learning agent that learns optimal risk parameters
(position sizing, max drawdown limits, cooldown periods) from
historical trade outcomes. Falls back to the static risk
parameters in marketmate.core.config when no RL model is available.

IMPORTANT: This module must NEVER be in the import path of production code.
It subscribes to EventBus events independently. If the model cannot load,
all risk management falls back to the static config-based RiskManager.
"""

from __future__ import annotations

from typing import Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.core.events import event_bus, EventType

log = get_logger("ml.reinforcement")


class RLRiskManager:
    """
    Experimental RL-based risk management agent.

    In production, this would:
      - Learn optimal position sizing from reward signals
      - Adjust max_consecutive_losses thresholds dynamically
      - Adapt risk_per_trade_pct based on recent market regime
      - Suggest cooldown periods after drawdown events

    For now, this is a stub that always returns None to indicate
    "no RL recommendation available" — callers should fall back
    to the static RiskManager with config-based parameters.
    """

    def __init__(self) -> None:
        self._agent = None
        self._loaded = False
        self._subscribe()

    def _subscribe(self) -> None:
        """Subscribe to trade outcome events for RL reward computation."""
        event_bus.subscribe(EventType.TRADE_CLOSED, self._on_trade_closed)
        event_bus.subscribe(EventType.LOSS_HIT, self._on_loss_hit)
        log.info("ml_rl_subscribed",
                 events=[EventType.TRADE_CLOSED, EventType.LOSS_HIT])

    async def _on_trade_closed(self, **payload) -> None:
        """
        EventBus handler: record trade outcome as RL reward.

        In the future, this would:
          1. Compute the reward (R-multiple, win/loss)
          2. Update the RL agent's state-action value estimates
          3. Decay exploration rate

        For now, it simply logs the event.
        """
        signal_id = payload.get("signal_id", "unknown")
        outcome = payload.get("outcome", "unknown")
        log.debug("ml_rl_trade_closed",
                  signal_id=signal_id, outcome=outcome)

    async def _on_loss_hit(self, **payload) -> None:
        """
        EventBus handler: record loss event for drawdown tracking.

        In the future, this would trigger risk parameter adjustments
        (e.g. reduce position size, increase cooldown).
        """
        signal_id = payload.get("signal_id", "unknown")
        log.debug("ml_rl_loss_hit", signal_id=signal_id)

    async def load(self, model_path: Optional[str] = None) -> bool:
        """
        Load a trained RL agent from disk.

        Stub: always returns False (no RL agent available).
        """
        log.info("ml_rl_load_attempt", path=model_path)
        self._loaded = False
        return False

    async def recommend_position_size(
        self,
        account_size: float,
        current_drawdown_pct: float,
        consecutive_losses: int,
        market_regime: Optional[str] = None,
    ) -> Optional[float]:
        """
        Recommend a position size based on RL policy.

        Args:
            account_size: Current account balance.
            current_drawdown_pct: Current drawdown as percentage.
            consecutive_losses: Number of consecutive losses.
            market_regime: Optional market regime label.

        Returns:
            Recommended lot size, or None if RL is not available.
            Callers should fall back to static risk calculation.

        Stub: always returns None.
        """
        if not self._loaded or self._agent is None:
            return None

        # In production:
        #   state = self._encode_state(account_size, drawdown, losses, regime)
        #   action = self._agent.act(state)
        #   return self._decode_position_size(action)

        return None

    async def recommend_cooldown(
        self,
        consecutive_losses: int,
        recent_rr: float,
    ) -> Optional[int]:
        """
        Recommend a cooldown period (in minutes) after consecutive losses.

        Returns:
            Cooldown minutes, or None if RL is not available.
            Callers should fall back to static cooldown logic.

        Stub: always returns None.
        """
        if not self._loaded or self._agent is None:
            return None

        return None

    async def train_step(
        self,
        state: dict,
        action: dict,
        reward: float,
        next_state: dict,
        done: bool,
    ) -> None:
        """
        Perform a single RL training step.

        Stub: no-op.
        """
        pass

    @property
    def is_loaded(self) -> bool:
        """Return True if an RL agent is loaded and ready."""
        return self._loaded


# ─── Module-level singleton ───────────────────────────────────────────────────
rl_risk_manager = RLRiskManager()
