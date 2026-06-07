"""
marketmate.mate.brains.account
──────────────────────────────
Account Brain — answers everything about balance, drawdown, and account health.

Capability Domain:
  - Balance queries: "What's my balance?"
  - Drawdown state: "What's current DD?"
  - Monthly return: "How much return this month?"
  - Equity curve: "How has the account performed?"
  - Risk state: "What's the risk per trade?"

Functions:
  get_balance()          → current balance
  get_state()            → full account state
  get_metrics(window)    → 7d/30d metrics (win_rate, profit_factor, sharpe, DD)
  get_drawdown()         → current drawdown state
  get_risk_state()       → risk per trade, consecutive losses, risk limits

This brain NEVER fabricates balances.
It reads from VirtualAccountEngine (event-sourced replay).
The LLM only narrates what this brain compiles.
"""

from __future__ import annotations

from typing import Any, Dict

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.mate.state_store import redis_state_store

log = get_logger("mate.brains.account")


class AccountBrain:
    """
    Financial cognition primitive for account state.

    Answers: balance, drawdown, equity, risk state, metrics.
    Does NOT answer: prices, signal logic, strategy theory.
    """

    # ═════════════════════════════════════════════════════════════════════════
    # Core Brain Functions
    # ═════════════════════════════════════════════════════════════════════════

    async def get_balance(self) -> Dict[str, Any]:
        """Get the current virtual account balance."""
        # 1. Redis cache
        state = await redis_state_store.get_account_state()
        if state and state.get("balance") is not None:
            return {
                "balance": state["balance"],
                "source": "redis",
            }

        # 2. VirtualAccountEngine
        try:
            from marketmate.virtual_account.engine import get_virtual_account_engine
            engine = get_virtual_account_engine()
            balance = await engine.get_balance()
            return {"balance": balance, "source": "engine"}
        except Exception as exc:
            log.warning("balance_fetch_failed", error=str(exc))
            return {"status": "unavailable"}

    async def get_state(self) -> Dict[str, Any]:
        """
        Get full compiled account state.

        Returns balance, open trades, total trades, win rate, risk pct.
        """
        # 1. Redis cache
        state = await redis_state_store.get_account_state()
        if state and state.get("balance") is not None:
            return {**state, "source": "redis"}

        # 2. VirtualAccountEngine
        try:
            from marketmate.virtual_account.engine import get_virtual_account_engine
            engine = get_virtual_account_engine()
            state = await engine.get_state()
            if state:
                state["source"] = "engine_fallback"
                return state
        except Exception as exc:
            log.warning("account_state_fetch_failed", error=str(exc))

        return {"status": "no_data", "hint": "Account state not yet compiled"}

    async def get_metrics(self, window: str = "30d") -> Dict[str, Any]:
        """
        Get precomputed account metrics for a time window.

        Returns AccountMetrics: win_rate, avg_rr, profit_factor, max_dd, sharpe.
        """
        # 1. Redis cache
        perf_metrics = {}
        for metric in ["winrate", "avg_rr", "total_trades", "profit_factor"]:
            value = await redis_state_store.get_perf(metric, window)
            if value:
                perf_metrics[metric] = value.get("value") if isinstance(value, dict) else value

        if perf_metrics and perf_metrics.get("total_trades"):
            return {"window": window, "metrics": perf_metrics, "source": "redis"}

        # 2. VirtualAccountEngine
        try:
            from marketmate.virtual_account.engine import get_virtual_account_engine
            engine = get_virtual_account_engine()
            m = await engine.get_metrics(window)
            if m:
                return {
                    "window": window,
                    "metrics": {
                        "balance": m.balance,
                        "start_balance": m.start_balance,
                        "return_pct": round(m.return_pct, 2),
                        "total_trades": m.total_trades,
                        "wins": m.wins,
                        "losses": m.losses,
                        "win_rate": round(m.win_rate, 4),
                        "avg_rr": round(m.avg_rr, 2),
                        "profit_factor": round(m.profit_factor, 2) if m.profit_factor else None,
                        "max_drawdown_pct": round(m.max_drawdown_pct, 2),
                        "consecutive_wins": m.consecutive_wins,
                        "consecutive_losses": m.consecutive_losses,
                    },
                    "source": "engine",
                }
        except Exception as exc:
            log.warning("account_metrics_fetch_failed", window=window, error=str(exc))

        return {"window": window, "status": "no_data"}

    async def get_drawdown(self) -> Dict[str, Any]:
        """
        Get current drawdown state.

        Combines account state with consecutive loss tracking.
        """
        state = await self.get_state()

        try:
            from marketmate.db.repositories.signals import SignalRepository
            repo = SignalRepository()
            consecutive_losses = await repo.get_consecutive_losses()
            state["consecutive_losses"] = consecutive_losses
            state["max_consecutive_losses"] = cfg.risk.max_consecutive_losses
            state["drawdown_pause_active"] = consecutive_losses >= cfg.risk.max_consecutive_losses
        except Exception:
            pass

        return state

    async def get_risk_state(self) -> Dict[str, Any]:
        """
        Get current risk configuration and state.

        Returns risk per trade, account size, risk amount in dollars.
        """
        try:
            from marketmate.virtual_account.engine import get_virtual_account_engine
            engine = get_virtual_account_engine()
            risk_amount = await engine.compute_risk_amount()
            balance = await engine.get_balance()
            return {
                "balance": balance,
                "risk_per_trade_pct": cfg.risk.risk_per_trade_pct,
                "risk_amount_usd": round(risk_amount, 2),
                "max_consecutive_losses": cfg.risk.max_consecutive_losses,
                "atr_sl_multiplier": cfg.risk.atr_sl_multiplier,
            }
        except Exception as exc:
            log.warning("risk_state_failed", error=str(exc))
            return {
                "risk_per_trade_pct": cfg.risk.risk_per_trade_pct,
                "account_size": cfg.risk.account_size,
                "max_consecutive_losses": cfg.risk.max_consecutive_losses,
            }


# ─── Singleton ────────────────────────────────────────────────────────────────

account_brain = AccountBrain()
