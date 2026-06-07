"""
MarketMate — Unified Risk Manager (Pre-Trade Filter & Position Governor)
════════════════════════════════════════════════════════════════════════════
Integrates six protection mechanisms that run BEFORE any signal is executed:

  MM-004  DCB-01  Drawdown Circuit Breaker      (daily / weekly / monthly)
  MM-006  PWP-01  Pre-Weekend Protocol           (Thursday close, Friday/Sunday blocks)
  MM-007  TMG-01  Thin Market Guard              (spread, ATR, blocked hours)
  MM-008  CLP-01  Consecutive Loss Protocol      (per-strategy + portfolio-wide)
  MM-010  CCE-01  Correlation Cap                (position count + pairwise correlation)
  MM-011  ECB-01  Equity Curve Brake             (SMA deviation + 20 % halt)

Usage
-----
    rm = RiskManager()
    allowed, reason, multiplier = rm.check_signal(signal, current_spread=1.2, ...)
    if not allowed:
        log.warning(f"Signal blocked: {reason}")
    else:
        execute_with_size(base_size * multiplier)

    rm.update_after_trade(trade_result)
    rm.reset_daily()   # at 00:00 GMT
    rm.reset_weekly()  # at Monday 00:00 GMT
    rm.reset_monthly() # at 1st of month 00:00 GMT
"""

from __future__ import annotations

import numpy as np
import pandas as pd
from dataclasses import dataclass, field
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta
from pathlib import Path
import json
import warnings

warnings.filterwarnings("ignore", category=RuntimeWarning)


# ═══════════════════════════════════════════════════════════════════════════
#  Risk State
# ═══════════════════════════════════════════════════════════════════════════

@dataclass
class RiskState:
    """Current risk state of the portfolio."""

    balance: float = 15.0
    daily_pnl: float = 0.0
    weekly_pnl: float = 0.0
    monthly_pnl: float = 0.0

    consecutive_losses_strategy: Dict[str, int] = field(default_factory=dict)
    consecutive_losses_portfolio: int = 0
    consecutive_wins_portfolio: int = 0
    strategy_cooldown: Dict[str, bool] = field(default_factory=dict)
    reduced_size_trades_remaining: int = 0

    open_positions: List[Dict] = field(default_factory=list)
    equity_history: List[float] = field(default_factory=list)

    is_halted: bool = False
    halt_reason: str = ""
    position_size_multiplier: float = 1.0
    daily_halt_triggered: bool = False
    weekly_halt_triggered: bool = False
    last_trade_time: Optional[datetime] = None
    trades_today: int = 0

    # Internal bookkeeping
    spread_history: List[float] = field(default_factory=list)
    ecb_above_ma_count: int = 0


# ═══════════════════════════════════════════════════════════════════════════
#  Risk Manager
# ═══════════════════════════════════════════════════════════════════════════

class RiskManager:
    """
    Unified risk manager integrating:
    - MM-004: Drawdown Circuit Breaker (DCB-01)
    - MM-006: Pre-Weekend Protocol (PWP-01)
    - MM-007: Thin Market Guard (TMG-01)
    - MM-008: Consecutive Loss Protocol (CLP-01)
    - MM-010: Correlation Cap (CCE-01)
    - MM-011: Equity Curve Brake (ECB-01)
    """

    def __init__(self, config: Dict = None):
        self.config = config or self.default_config()
        self.state = RiskState()

    # ── Default Configuration ────────────────────────────────────────────────

    @staticmethod
    def default_config() -> Dict[str, Any]:
        return {
            # MM-004: Drawdown Circuit Breaker
            "daily_loss_limit_pct": 3.0,        # Halt at -3 % daily
            "weekly_loss_limit_pct": 7.0,        # 50 % size reduction at -7 % weekly
            "monthly_loss_limit_pct": 15.0,      # Full pause at -15 % monthly

            # MM-006: Pre-Weekend Protocol
            "pre_weekend_close_hour": 20,        # Thursday 20:00 GMT
            "pre_weekend_close_day": 3,          # Thursday (0 = Mon)
            "no_entry_friday_after_hour": 18,    # Friday 18:00 GMT
            "no_entry_sunday_before_hour": 21,   # Sunday 21:00 GMT

            # MM-007: Thin Market Guard
            "spread_mult_threshold": 2.0,        # Suspend if spread > 2× median
            "atr_session_pct_threshold": 30,     # Suspend if ATR < 30 % of average
            "blocked_hours": [(0, 6), (12, 13), (20, 23)],  # GMT hours blocked
            "median_spread_window": 20,          # Sessions for median spread

            # MM-008: Consecutive Loss Protocol
            "strategy_cooldown_after_losses": 2,  # Skip next signal after 2 consecutive losses per strategy
            "portfolio_reduction_after_losses": 3, # Reduce 30 % size after 3 consecutive portfolio losses
            "portfolio_halt_after_losses": 5,     # Full halt after 5 consecutive portfolio losses
            "reduction_pct": 30,                  # Position size reduction %
            "restore_after_wins": 3,              # Restore full size after 3 consecutive wins

            # MM-010: Correlation Cap
            "max_correlation": 0.7,              # Block if correlation > 0.7
            "max_open_positions": 2,             # Hard cap on open positions
            "correlation_window": 20,            # Bars for correlation calculation

            # MM-011: Equity Curve Brake
            "ecb_window": 10,                    # Rolling equity window
            "ecb_drop_pct": 20,                  # Full halt if 20 % below MA

            # Portfolio sizing
            "risk_per_trade_pct": 5.0,           # % of balance risked per trade (for PnL conversion)
        }

    # ══════════════════════════════════════════════════════════════════════
    #  Main Pre-Trade Gate
    # ══════════════════════════════════════════════════════════════════════

    def check_signal(
        self,
        signal,
        current_spread: float = 0,
        current_atr: float = 0,
        avg_atr: float = 0,
        current_hour: int = 0,
        current_weekday: int = 0,
        correlation_data: Optional[Dict[str, List[float]]] = None,
    ) -> Tuple[bool, str, float]:
        """
        Pre-trade risk check.  Returns ``(allowed, reason, size_multiplier)``.

        Runs every protection layer in priority order.  The *most restrictive*
        result wins: if any layer blocks the signal the result is ``False``;
        otherwise the final ``size_multiplier`` is the minimum across all layers.
        """

        # ── 0. Global halt already active ────────────────────────────────
        if self.state.is_halted:
            return False, f"HALTED — {self.state.halt_reason}", 0.0

        # Collect per-layer results: (allowed, reason, size_multiplier)
        layer_results: List[Tuple[bool, str, float]] = []

        # ── 1. MM-004 — Drawdown Circuit Breaker ────────────────────────
        layer_results.append(self._check_drawdown())

        # ── 2. MM-008 — Consecutive Loss Protocol ───────────────────────
        strategy_id = getattr(signal, "strategy_id", "")
        layer_results.append(self._check_consecutive_losses(strategy_id))

        # ── 3. MM-011 — Equity Curve Brake ──────────────────────────────
        layer_results.append(self._check_equity_curve())

        # ── 4. MM-006 — Pre-Weekend Protocol ────────────────────────────
        layer_results.append(self._check_pre_weekend(current_hour, current_weekday))

        # ── 5. MM-007 — Thin Market Guard ───────────────────────────────
        layer_results.append(
            self._check_thin_market(current_spread, current_atr, avg_atr, current_hour)
        )

        # ── 6. MM-010 — Correlation Cap ─────────────────────────────────
        symbol = getattr(signal, "symbol", "")
        direction = getattr(signal, "direction", "")
        layer_results.append(self._check_correlation(symbol, direction, correlation_data))

        # ── Aggregate ────────────────────────────────────────────────────
        # If any layer blocks, return the first blocking reason
        for allowed, reason, _ in layer_results:
            if not allowed:
                return False, reason, 0.0

        # All layers allow — take the most conservative multiplier
        final_multiplier = min(m for _, _, m in layer_results)

        # Also factor in the state-level weekly reduction
        final_multiplier = min(final_multiplier, self.state.position_size_multiplier)

        # If reduced_size_trades_remaining is active, apply the reduction
        if self.state.reduced_size_trades_remaining > 0:
            reduction_factor = 1.0 - self.config["reduction_pct"] / 100.0
            final_multiplier = min(final_multiplier, reduction_factor)

        return True, "", round(final_multiplier, 4)

    # ══════════════════════════════════════════════════════════════════════
    #  Post-Trade State Update
    # ══════════════════════════════════════════════════════════════════════

    def update_after_trade(self, trade_result) -> None:
        """
        Update risk state after a trade completes.

        ``trade_result`` can be a ``TradeResult`` object **or** a dict with
        keys: ``pnl_r`` / ``pnl_pct``, ``symbol``, ``direction``,
        ``strategy_id``, ``is_closing``, ``entry_price``.
        """
        pnl_r = self._attr(trade_result, "pnl_r", 0.0)
        pnl_pct = self._attr(trade_result, "pnl_pct", None)

        # TradeResult objects nest symbol/direction inside .signal;
        # flat dicts keep them at the top level.
        nested_signal = self._attr(trade_result, "signal", None)
        if nested_signal is not None:
            symbol = self._attr(nested_signal, "symbol", "")
            direction = self._attr(nested_signal, "direction", "")
            strategy_id = self._attr(nested_signal, "strategy_id", "")
            entry_price = self._attr(nested_signal, "entry_price", 0.0)
            # TradeResult always represents a closed trade
            is_closing = True
        else:
            symbol = self._attr(trade_result, "symbol", "")
            direction = self._attr(trade_result, "direction", "")
            strategy_id = self._attr(trade_result, "strategy_id", "")
            entry_price = self._attr(trade_result, "entry_price", 0.0)
            is_closing = self._attr(trade_result, "is_closing", True)

        # ── PnL bookkeeping ──────────────────────────────────────────────
        # pnl_pct is the preferred metric: percentage of balance gained/lost.
        # If absent, derive from pnl_r × risk_per_trade_pct.
        if pnl_pct is not None and pnl_pct != 0.0:
            pnl_dollar = pnl_pct / 100.0 * self.state.balance
        else:
            risk_pct = self.config["risk_per_trade_pct"] / 100.0
            pnl_dollar = pnl_r * risk_pct * self.state.balance

        self.state.daily_pnl += pnl_dollar
        self.state.weekly_pnl += pnl_dollar
        self.state.monthly_pnl += pnl_dollar
        self.state.balance += pnl_dollar

        # For win/loss classification, use pnl_r (R-multiple)
        pnl = pnl_r

        # ── Consecutive loss / win tracking ──────────────────────────────
        is_loss = pnl < 0
        is_win = pnl > 0

        # Also treat pnl_pct-based wins/losses when pnl_r is zero
        if pnl_r == 0.0 and pnl_pct is not None:
            is_loss = pnl_pct < 0
            is_win = pnl_pct > 0

        if is_loss:
            # Per-strategy counter
            self.state.consecutive_losses_strategy[strategy_id] = (
                self.state.consecutive_losses_strategy.get(strategy_id, 0) + 1
            )
            # Portfolio-wide counter
            self.state.consecutive_losses_portfolio += 1
            self.state.consecutive_wins_portfolio = 0

            # Activate strategy cooldown after N consecutive losses
            if (
                self.state.consecutive_losses_strategy[strategy_id]
                >= self.config["strategy_cooldown_after_losses"]
            ):
                self.state.strategy_cooldown[strategy_id] = True

            # Portfolio-level reductions
            if (
                self.state.consecutive_losses_portfolio
                >= self.config["portfolio_halt_after_losses"]
            ):
                self.state.is_halted = True
                self.state.halt_reason = (
                    f"Portfolio halt: {self.state.consecutive_losses_portfolio} "
                    f"consecutive losses"
                )
            elif (
                self.state.consecutive_losses_portfolio
                >= self.config["portfolio_reduction_after_losses"]
                and self.state.reduced_size_trades_remaining == 0
            ):
                self.state.reduced_size_trades_remaining = 5

        elif is_win:
            # Reset per-strategy loss counter and cooldown
            self.state.consecutive_losses_strategy[strategy_id] = 0
            self.state.strategy_cooldown.pop(strategy_id, None)

            # Portfolio win streak
            self.state.consecutive_losses_portfolio = 0
            self.state.consecutive_wins_portfolio += 1

            # Restore full size after N consecutive wins
            if self.state.consecutive_wins_portfolio >= self.config["restore_after_wins"]:
                self.state.position_size_multiplier = 1.0
                self.state.reduced_size_trades_remaining = 0

        # ── Decrement reduced-size counter on every trade ────────────────
        if self.state.reduced_size_trades_remaining > 0:
            self.state.reduced_size_trades_remaining -= 1
            if self.state.reduced_size_trades_remaining == 0:
                # Reduction period expired — restore unless weekly DCB is active
                if not self.state.weekly_halt_triggered:
                    self.state.position_size_multiplier = 1.0

        # ── Equity history (for ECB) ─────────────────────────────────────
        self.state.equity_history.append(self.state.balance)
        max_history = self.config["ecb_window"] * 3  # keep a buffer
        if len(self.state.equity_history) > max_history:
            self.state.equity_history = self.state.equity_history[-max_history:]

        # ── Open positions bookkeeping ───────────────────────────────────
        if is_closing:
            # Remove matching position (most recent entry for this symbol + direction)
            for i in range(len(self.state.open_positions) - 1, -1, -1):
                pos = self.state.open_positions[i]
                if pos["symbol"] == symbol and pos["direction"] == direction:
                    self.state.open_positions.pop(i)
                    break
        else:
            self.state.open_positions.append(
                {
                    "symbol": symbol,
                    "direction": direction,
                    "entry_price": entry_price,
                    "strategy_id": strategy_id,
                }
            )

        # ── Housekeeping ─────────────────────────────────────────────────
        self.state.trades_today += 1
        self.state.last_trade_time = datetime.utcnow()

    # ══════════════════════════════════════════════════════════════════════
    #  Periodic Resets
    # ══════════════════════════════════════════════════════════════════════

    def reset_daily(self) -> None:
        """Reset daily counters.  Called at start of each trading day."""
        self.state.daily_pnl = 0.0
        self.state.daily_halt_triggered = False
        self.state.trades_today = 0

    def reset_weekly(self) -> None:
        """Reset weekly counters.  Called at start of each trading week (Monday 00:00 GMT)."""
        # Restore position_size_multiplier after a net-positive week
        # (the reduction was imposed by weekly DCB; a positive week signals recovery)
        if self.state.weekly_pnl > 0:
            self.state.position_size_multiplier = 1.0
        self.state.weekly_pnl = 0.0
        self.state.weekly_halt_triggered = False

    def reset_monthly(self) -> None:
        """Reset monthly counters.  Called at start of each calendar month."""
        self.state.monthly_pnl = 0.0
        # Lift a monthly-drawdown halt so the new month can begin trading
        if self.state.is_halted and "Monthly drawdown" in self.state.halt_reason:
            self.state.is_halted = False
            self.state.halt_reason = ""

    # ══════════════════════════════════════════════════════════════════════
    #  MM-004: Drawdown Circuit Breaker
    # ══════════════════════════════════════════════════════════════════════

    def _check_drawdown(self) -> Tuple[bool, str, float]:
        """Check daily / weekly / monthly drawdown limits."""
        cfg = self.config
        balance = self.state.balance
        if balance <= 0:
            return False, "DCB: Balance depleted", 0.0

        daily_pct = self.state.daily_pnl / balance * 100
        weekly_pct = self.state.weekly_pnl / balance * 100
        monthly_pct = self.state.monthly_pnl / balance * 100

        # Monthly — full halt
        if monthly_pct <= -cfg["monthly_loss_limit_pct"]:
            self.state.is_halted = True
            self.state.halt_reason = (
                f"DCB: Monthly drawdown limit reached ({monthly_pct:.1f}%)"
            )
            return False, self.state.halt_reason, 0.0

        # Daily — halt for rest of day
        if daily_pct <= -cfg["daily_loss_limit_pct"]:
            self.state.daily_halt_triggered = True
            return False, f"DCB: Daily drawdown limit reached ({daily_pct:.1f}%)", 0.0

        # Weekly — reduce to half size
        if weekly_pct <= -cfg["weekly_loss_limit_pct"]:
            if not self.state.weekly_halt_triggered:
                self.state.weekly_halt_triggered = True
                self.state.position_size_multiplier = 0.5
            return True, f"DCB: Weekly drawdown — size reduced ({weekly_pct:.1f}%)", 0.5

        return True, "", 1.0

    # ══════════════════════════════════════════════════════════════════════
    #  MM-006: Pre-Weekend Protocol
    # ══════════════════════════════════════════════════════════════════════

    def _check_pre_weekend(self, hour: int, weekday: int) -> Tuple[bool, str, float]:
        """Check if trading is blocked due to pre-weekend rules."""
        cfg = self.config

        # Thursday — flag to close profitable positions after close_hour
        if weekday == cfg["pre_weekend_close_day"] and hour >= cfg["pre_weekend_close_hour"]:
            return False, "PWP: Pre-weekend close — close profitable positions", 0.0

        # Friday — no new entries after cutoff
        if weekday == 4 and hour >= cfg["no_entry_friday_after_hour"]:
            return False, "PWP: No new entries Friday after cutoff", 0.0

        # Sunday — no new entries before cutoff
        if weekday == 6 and hour < cfg["no_entry_sunday_before_hour"]:
            return False, "PWP: No new entries Sunday before cutoff", 0.0

        return True, "", 1.0

    # ══════════════════════════════════════════════════════════════════════
    #  MM-007: Thin Market Guard
    # ══════════════════════════════════════════════════════════════════════

    def _check_thin_market(
        self, spread: float, atr: float, avg_atr: float, hour: int
    ) -> Tuple[bool, str, float]:
        """Check if market is too thin for trading."""
        cfg = self.config

        # ── Spread check ─────────────────────────────────────────────────
        if spread > 0:
            # Record spread for median calculation
            self.state.spread_history.append(spread)
            window = cfg["median_spread_window"]
            if len(self.state.spread_history) > window * 3:
                self.state.spread_history = self.state.spread_history[-(window * 3):]

            if len(self.state.spread_history) >= 3:
                recent = self.state.spread_history[-window:]
                median_spread = float(np.median(recent))
                if median_spread > 0 and spread > cfg["spread_mult_threshold"] * median_spread:
                    return (
                        False,
                        f"TMG: Spread too wide ({spread:.2f} > "
                        f"{cfg['spread_mult_threshold']}× median {median_spread:.2f})",
                        0.0,
                    )

        # ── ATR check ────────────────────────────────────────────────────
        if atr > 0 and avg_atr > 0:
            threshold = cfg["atr_session_pct_threshold"] / 100.0 * avg_atr
            if atr < threshold:
                return (
                    False,
                    f"TMG: ATR too low ({atr:.4f} < {threshold:.4f} = "
                    f"{cfg['atr_session_pct_threshold']}% of avg {avg_atr:.4f})",
                    0.0,
                )

        # ── Blocked hours ────────────────────────────────────────────────
        for start, end in cfg["blocked_hours"]:
            if start <= hour < end:
                return (
                    False,
                    f"TMG: Blocked trading hour ({hour}:00 GMT, blocked range {start}–{end})",
                    0.0,
                )

        return True, "", 1.0

    # ══════════════════════════════════════════════════════════════════════
    #  MM-008: Consecutive Loss Protocol
    # ══════════════════════════════════════════════════════════════════════

    def _check_consecutive_losses(self, strategy_id: str) -> Tuple[bool, str, float]:
        """Check consecutive loss limits.  Returns (allowed, reason, size_multiplier)."""
        cfg = self.config

        # ── Strategy-level cooldown ──────────────────────────────────────
        if self.state.strategy_cooldown.get(strategy_id, False):
            # Consuming the cooldown — the next signal is skipped
            self.state.strategy_cooldown[strategy_id] = False
            return (
                False,
                f"CLP: Strategy '{strategy_id}' in cooldown after "
                f"{cfg['strategy_cooldown_after_losses']} consecutive losses",
                0.0,
            )

        # ── Portfolio-level halt ─────────────────────────────────────────
        if self.state.consecutive_losses_portfolio >= cfg["portfolio_halt_after_losses"]:
            self.state.is_halted = True
            self.state.halt_reason = (
                f"CLP: Portfolio halt — {self.state.consecutive_losses_portfolio} "
                f"consecutive losses"
            )
            return False, self.state.halt_reason, 0.0

        # ── Portfolio-level size reduction ───────────────────────────────
        if self.state.reduced_size_trades_remaining > 0:
            reduction_factor = 1.0 - cfg["reduction_pct"] / 100.0
            return (
                True,
                f"CLP: Reduced size ({cfg['reduction_pct']}% reduction, "
                f"{self.state.reduced_size_trades_remaining} trades remaining)",
                reduction_factor,
            )

        return True, "", 1.0

    # ══════════════════════════════════════════════════════════════════════
    #  MM-010: Correlation Cap
    # ══════════════════════════════════════════════════════════════════════

    def _check_correlation(
        self,
        symbol: str,
        direction: str,
        correlation_data: Optional[Dict[str, List[float]]],
    ) -> Tuple[bool, str, float]:
        """Check if new trade would exceed correlation limits."""
        cfg = self.config

        # ── Hard cap on open positions ───────────────────────────────────
        if len(self.state.open_positions) >= cfg["max_open_positions"]:
            return (
                False,
                f"CCE: Max open positions reached "
                f"({len(self.state.open_positions)}/{cfg['max_open_positions']})",
                0.0,
            )

        # ── No existing positions → no correlation risk ──────────────────
        if not self.state.open_positions or correlation_data is None:
            return True, "", 1.0

        # ── Pairwise correlation check ───────────────────────────────────
        new_returns = correlation_data.get(symbol)
        if new_returns is None or len(new_returns) < 2:
            return True, "", 1.0

        for pos in self.state.open_positions:
            existing_symbol = pos["symbol"]
            existing_direction = pos["direction"]

            existing_returns = correlation_data.get(existing_symbol)
            if existing_returns is None or len(existing_returns) < 2:
                continue

            corr = self._pearson_correlation(new_returns, existing_returns, cfg["correlation_window"])

            if abs(corr) > cfg["max_correlation"]:
                same_direction = (
                    direction.upper() == existing_direction.upper()
                    or direction.lower() == existing_direction.lower()
                )
                if same_direction:
                    return (
                        False,
                        f"CCE: Correlation {corr:.2f} > {cfg['max_correlation']} "
                        f"with {existing_symbol} (same direction)",
                        0.0,
                    )
                else:
                    # Opposite direction — allow at half size
                    return (
                        True,
                        f"CCE: High correlation {corr:.2f} with {existing_symbol} "
                        f"(opposite direction — size reduced 50%)",
                        0.5,
                    )

        return True, "", 1.0

    # ══════════════════════════════════════════════════════════════════════
    #  MM-011: Equity Curve Brake
    # ══════════════════════════════════════════════════════════════════════

    def _check_equity_curve(self) -> Tuple[bool, str, float]:
        """Check if equity is below moving average.  Returns (allowed, reason, size_multiplier)."""
        cfg = self.config
        window = cfg["ecb_window"]
        history = self.state.equity_history

        # Not enough data yet — allow with full size
        if len(history) < window:
            return True, "", 1.0

        recent = history[-window:]
        sma = float(np.mean(recent))
        current_equity = history[-1]

        if sma <= 0:
            return True, "", 1.0

        # ── 20 % below SMA → full halt ──────────────────────────────────
        drop_pct = (sma - current_equity) / sma * 100
        if drop_pct >= cfg["ecb_drop_pct"]:
            self.state.is_halted = True
            self.state.halt_reason = (
                f"ECB: Equity {current_equity:.2f} is {drop_pct:.1f}% below SMA {sma:.2f}"
            )
            return False, self.state.halt_reason, 0.0

        # ── Below SMA → half size ────────────────────────────────────────
        if current_equity < sma:
            self.state.ecb_above_ma_count = 0
            return (
                True,
                f"ECB: Equity below SMA ({current_equity:.2f} < {sma:.2f}) — half size",
                0.5,
            )

        # ── Above SMA → track recovery ──────────────────────────────────
        self.state.ecb_above_ma_count += 1
        if self.state.ecb_above_ma_count >= 3:
            # Restored after 3 consecutive trades above SMA
            return True, "", 1.0

        return True, "", 1.0

    # ══════════════════════════════════════════════════════════════════════
    #  Status / Serialisation
    # ══════════════════════════════════════════════════════════════════════

    def get_status(self) -> Dict:
        """Return current risk state as a dict for logging / display."""
        balance = self.state.balance
        return {
            "balance": round(balance, 4),
            "daily_pnl": round(self.state.daily_pnl, 4),
            "weekly_pnl": round(self.state.weekly_pnl, 4),
            "monthly_pnl": round(self.state.monthly_pnl, 4),
            "daily_pnl_pct": round(self.state.daily_pnl / balance * 100, 2) if balance else 0.0,
            "weekly_pnl_pct": round(self.state.weekly_pnl / balance * 100, 2) if balance else 0.0,
            "monthly_pnl_pct": round(self.state.monthly_pnl / balance * 100, 2) if balance else 0.0,
            "consecutive_losses_strategy": dict(self.state.consecutive_losses_strategy),
            "consecutive_losses_portfolio": self.state.consecutive_losses_portfolio,
            "consecutive_wins_portfolio": self.state.consecutive_wins_portfolio,
            "open_positions": len(self.state.open_positions),
            "open_position_details": list(self.state.open_positions),
            "is_halted": self.state.is_halted,
            "halt_reason": self.state.halt_reason,
            "position_size_multiplier": self.state.position_size_multiplier,
            "daily_halt_triggered": self.state.daily_halt_triggered,
            "weekly_halt_triggered": self.state.weekly_halt_triggered,
            "trades_today": self.state.trades_today,
            "reduced_size_trades_remaining": self.state.reduced_size_trades_remaining,
            "ecb_above_ma_count": self.state.ecb_above_ma_count,
            "equity_history_len": len(self.state.equity_history),
            "spread_history_len": len(self.state.spread_history),
            "strategy_cooldowns": {
                k: v for k, v in self.state.strategy_cooldown.items() if v
            },
        }

    def save_state(self, path: str | Path) -> None:
        """Persist risk state to a JSON file."""
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        data = {
            "balance": self.state.balance,
            "daily_pnl": self.state.daily_pnl,
            "weekly_pnl": self.state.weekly_pnl,
            "monthly_pnl": self.state.monthly_pnl,
            "consecutive_losses_strategy": self.state.consecutive_losses_strategy,
            "consecutive_losses_portfolio": self.state.consecutive_losses_portfolio,
            "consecutive_wins_portfolio": self.state.consecutive_wins_portfolio,
            "strategy_cooldown": self.state.strategy_cooldown,
            "reduced_size_trades_remaining": self.state.reduced_size_trades_remaining,
            "open_positions": self.state.open_positions,
            "equity_history": self.state.equity_history[-60:],  # keep last 60
            "is_halted": self.state.is_halted,
            "halt_reason": self.state.halt_reason,
            "position_size_multiplier": self.state.position_size_multiplier,
            "daily_halt_triggered": self.state.daily_halt_triggered,
            "weekly_halt_triggered": self.state.weekly_halt_triggered,
            "trades_today": self.state.trades_today,
            "spread_history": self.state.spread_history[-60:],
            "ecb_above_ma_count": self.state.ecb_above_ma_count,
            "last_trade_time": (
                self.state.last_trade_time.isoformat() if self.state.last_trade_time else None
            ),
        }
        p.write_text(json.dumps(data, indent=2, default=str))

    def load_state(self, path: str | Path) -> None:
        """Restore risk state from a JSON file."""
        p = Path(path)
        if not p.exists():
            return
        data = json.loads(p.read_text())
        self.state.balance = data.get("balance", self.state.balance)
        self.state.daily_pnl = data.get("daily_pnl", 0.0)
        self.state.weekly_pnl = data.get("weekly_pnl", 0.0)
        self.state.monthly_pnl = data.get("monthly_pnl", 0.0)
        self.state.consecutive_losses_strategy = data.get(
            "consecutive_losses_strategy", {}
        )
        self.state.consecutive_losses_portfolio = data.get(
            "consecutive_losses_portfolio", 0
        )
        self.state.consecutive_wins_portfolio = data.get(
            "consecutive_wins_portfolio", 0
        )
        self.state.strategy_cooldown = data.get("strategy_cooldown", {})
        self.state.reduced_size_trades_remaining = data.get(
            "reduced_size_trades_remaining", 0
        )
        self.state.open_positions = data.get("open_positions", [])
        self.state.equity_history = data.get("equity_history", [])
        self.state.is_halted = data.get("is_halted", False)
        self.state.halt_reason = data.get("halt_reason", "")
        self.state.position_size_multiplier = data.get("position_size_multiplier", 1.0)
        self.state.daily_halt_triggered = data.get("daily_halt_triggered", False)
        self.state.weekly_halt_triggered = data.get("weekly_halt_triggered", False)
        self.state.trades_today = data.get("trades_today", 0)
        self.state.spread_history = data.get("spread_history", [])
        self.state.ecb_above_ma_count = data.get("ecb_above_ma_count", 0)
        ltt = data.get("last_trade_time")
        self.state.last_trade_time = datetime.fromisoformat(ltt) if ltt else None

    # ══════════════════════════════════════════════════════════════════════
    #  Internal Helpers
    # ══════════════════════════════════════════════════════════════════════

    @staticmethod
    def _attr(obj, key: str, default=None):
        """Retrieve an attribute from a dict or object, with fallback."""
        if isinstance(obj, dict):
            return obj.get(key, default)
        return getattr(obj, key, default)

    @staticmethod
    def _pearson_correlation(
        series_a: List[float],
        series_b: List[float],
        window: int = 20,
    ) -> float:
        """
        Compute Pearson correlation between two return series,
        using the most recent ``window`` observations.
        Returns 0.0 if insufficient data or correlation is NaN.
        """
        a = series_a[-window:]
        b = series_b[-window:]
        min_len = min(len(a), len(b))
        if min_len < 3:
            return 0.0
        a = a[-min_len:]
        b = b[-min_len:]
        corr = float(np.corrcoef(a, b)[0, 1])
        if np.isnan(corr):
            return 0.0
        return corr
