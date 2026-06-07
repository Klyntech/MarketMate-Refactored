"""
marketmate.virtual_account.engine
──────────────────────────────────
VirtualAccountEngine — the core event-sourced accounting engine.

This is the brain of the virtual account system. It:
  1. Maintains the current balance by replaying events from the latest snapshot
  2. Appends new events (DEPOSIT, TRADE_OPENED, TRADE_CLOSED, etc.)
  3. Computes risk amounts using 1% risk per trade with compounding
  4. Takes periodic snapshots (every 50 events or 24 hours)
  5. Recomputes metrics (7d/30d) on every TRADE_CLOSED

The engine is event-sourced: the event log IS the truth. Any balance
can be reconstructed by replaying events. Snapshots are just a cache.

Usage:
    engine = VirtualAccountEngine()
    await engine.initialize()          # Load config + latest snapshot
    balance = await engine.get_balance()
    risk_amount = await engine.compute_risk_amount()
    await engine.on_trade_opened(signal_id, symbol, direction, entry, sl)
    await engine.on_trade_closed(signal_id, pnl, rr_realized)
"""

from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone
from typing import Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.core.events import event_bus, EventType
from marketmate.virtual_account.models import (
    AccountEvent,
    AccountEventType,
    AccountSnapshot,
    AccountMetrics,
    AccountConfig,
)
from marketmate.virtual_account.repos import (
    EventRepository,
    SnapshotRepository,
    MetricsRepository,
    ConfigRepository,
)

log = get_logger("virtual_account.engine")

# Snapshot every N events
SNAPSHOT_EVENT_INTERVAL = 50

# Snapshot every N hours
SNAPSHOT_TIME_INTERVAL_HOURS = 24


class VirtualAccountEngine:
    """
    Event-sourced virtual accounting engine.

    All balances are derived from event replay. The engine maintains
    an in-memory cache of the current state that is refreshed from
    MongoDB on demand or after each event append.
    """

    def __init__(self, account_id: str = "default") -> None:
        self.account_id = account_id
        self._event_repo = EventRepository()
        self._snapshot_repo = SnapshotRepository()
        self._metrics_repo = MetricsRepository()
        self._config_repo = ConfigRepository()

        # In-memory state (cached from latest snapshot + events)
        self._balance: float = 0.0
        self._open_trades: int = 0
        self._total_trades: int = 0
        self._wins: int = 0
        self._losses: int = 0
        self._event_count: int = 0
        self._config: Optional[AccountConfig] = None
        self._last_snapshot_event_seq: int = 0
        self._last_snapshot_time: Optional[datetime] = None
        self._initialized: bool = False

    # ═════════════════════════════════════════════════════════════════════════
    # Initialization
    # ═════════════════════════════════════════════════════════════════════════

    async def initialize(self) -> None:
        """
        Load config and latest snapshot, then replay events since snapshot.

        If no snapshot exists, creates an initial DEPOSIT event from config.
        """
        if self._initialized:
            return

        # Load config
        self._config = await self._config_repo.get(self.account_id)

        # Load latest snapshot
        snapshot = await self._snapshot_repo.get_latest(self.account_id)
        if snapshot is not None:
            self._balance = snapshot.balance
            self._open_trades = snapshot.open_trades
            self._total_trades = snapshot.total_trades
            self._wins = snapshot.wins
            self._losses = snapshot.losses
            self._last_snapshot_event_seq = snapshot.event_seq
            self._last_snapshot_time = snapshot.timestamp
            log.info(
                "va_snapshot_loaded",
                account_id=self.account_id,
                balance=round(self._balance, 2),
                event_seq=snapshot.event_seq,
            )
        else:
            # No snapshot — initialize from config
            self._balance = self._config.initial_balance
            self._last_snapshot_event_seq = 0
            # Create initial DEPOSIT event
            deposit = AccountEvent(
                event_type=AccountEventType.DEPOSIT,
                account_id=self.account_id,
                amount=self._config.initial_balance,
                balance_after=self._config.initial_balance,
            )
            await self._event_repo.append(deposit)
            self._event_count = 1
            log.info(
                "va_initialized_from_config",
                account_id=self.account_id,
                initial_balance=round(self._config.initial_balance, 2),
            )

        # Replay events since snapshot
        since = self._last_snapshot_time
        events = await self._event_repo.get_events_since(
            self.account_id, since=since, limit=5000
        )
        for event in events:
            self._apply_event(event)

        self._event_count = await self._event_repo.get_event_count(self.account_id)
        self._initialized = True

        log.info(
            "va_engine_initialized",
            account_id=self.account_id,
            balance=round(self._balance, 2),
            open_trades=self._open_trades,
            total_trades=self._total_trades,
            events_replayed=len(events),
        )

    # ═════════════════════════════════════════════════════════════════════════
    # Public API — Balance & Risk
    # ═════════════════════════════════════════════════════════════════════════

    async def get_balance(self) -> float:
        """Return the current account balance."""
        if not self._initialized:
            await self.initialize()
        return round(self._balance, 2)

    async def compute_risk_amount(self) -> float:
        """
        Compute the dollar risk for the next trade.

        Risk = balance × risk_per_trade_pct / 100
        With 1% risk and $10,000 balance: risk = $100
        This compounds naturally as balance changes.
        """
        if not self._initialized:
            await self.initialize()
        risk_pct = self._config.risk_per_trade_pct if self._config else 1.0
        return round(self._balance * risk_pct / 100.0, 2)

    async def get_state(self) -> dict:
        """Return the full current account state."""
        if not self._initialized:
            await self.initialize()
        return {
            "account_id": self.account_id,
            "balance": round(self._balance, 2),
            "open_trades": self._open_trades,
            "total_trades": self._total_trades,
            "wins": self._wins,
            "losses": self._losses,
            "win_rate": round(self._wins / max(self._total_trades, 1), 4),
            "risk_per_trade_pct": self._config.risk_per_trade_pct if self._config else 1.0,
        }

    # ═════════════════════════════════════════════════════════════════════════
    # Event Handlers — called by the system
    # ═════════════════════════════════════════════════════════════════════════

    async def on_trade_opened(
        self,
        signal_id: str,
        symbol: str,
        direction: str,
        entry: float,
        stop_loss: float,
    ) -> None:
        """
        Record a TRADE_OPENED event.

        Computes risk amount based on current balance (1% compounding).
        The risk amount is stored in the event for future reference.
        """
        if not self._initialized:
            await self.initialize()

        risk_amount = await self.compute_risk_amount()
        sl_distance = abs(entry - stop_loss)
        # Position size = risk_amount / sl_distance
        position_size = risk_amount / sl_distance if sl_distance > 0 else 0.0

        event = AccountEvent(
            event_type=AccountEventType.TRADE_OPENED,
            account_id=self.account_id,
            amount=0.0,  # No balance change on open
            balance_after=self._balance,
            trade_id=signal_id,
            risk_amount=risk_amount,
            direction=direction,
            symbol=symbol,
            metadata={
                "entry": round(entry, 4),
                "stop_loss": round(stop_loss, 4),
                "sl_distance": round(sl_distance, 6),
                "position_size": round(position_size, 6),
            },
        )

        await self._event_repo.append(event)
        self._apply_event(event)
        self._event_count += 1
        self._open_trades += 1

        log.info(
            "va_trade_opened",
            signal_id=signal_id,
            symbol=symbol,
            direction=direction,
            risk_amount=round(risk_amount, 2),
            balance=round(self._balance, 2),
        )

        await self._maybe_take_snapshot()

    async def on_trade_closed(
        self,
        signal_id: str,
        pnl: float,
        rr_realized: float,
        symbol: str = "",
        direction: str = "",
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Record a TRADE_CLOSED event.

        Updates the balance by the P&L amount, recomputes metrics,
        and takes a snapshot if needed.

        Args:
            signal_id:   The signal/trade identifier
            pnl:         Realized profit/loss in dollars (positive = profit)
            rr_realized:  R-multiple realized
            symbol:      Trading pair
            direction:   BUY or SELL
            metadata:    Additional data (proximity, etc.)
        """
        if not self._initialized:
            await self.initialize()

        self._balance += pnl
        self._open_trades = max(0, self._open_trades - 1)
        self._total_trades += 1

        if pnl > 0:
            self._wins += 1
        elif pnl < 0:
            self._losses += 1

        event = AccountEvent(
            event_type=AccountEventType.TRADE_CLOSED,
            account_id=self.account_id,
            amount=pnl,
            balance_after=self._balance,
            trade_id=signal_id,
            pnl=round(pnl, 2),
            rr_realized=rr_realized,
            direction=direction,
            symbol=symbol,
            metadata=metadata or {},
        )

        await self._event_repo.append(event)
        self._event_count += 1

        log.info(
            "va_trade_closed",
            signal_id=signal_id,
            symbol=symbol,
            direction=direction,
            pnl=round(pnl, 2),
            rr=round(rr_realized, 2),
            balance=round(self._balance, 2),
        )

        # Recompute metrics after every close
        await self._recompute_metrics()

        await self._maybe_take_snapshot()

    async def on_deposit(self, amount: float, note: str = "") -> None:
        """Record a DEPOSIT event."""
        if not self._initialized:
            await self.initialize()

        self._balance += amount
        event = AccountEvent(
            event_type=AccountEventType.DEPOSIT,
            account_id=self.account_id,
            amount=amount,
            balance_after=self._balance,
            metadata={"note": note},
        )
        await self._event_repo.append(event)
        self._event_count += 1
        await self._maybe_take_snapshot()

    async def on_drawdown_pause(self, reason: str = "") -> None:
        """Record a DRAWDOWN_PAUSE event."""
        if not self._initialized:
            await self.initialize()

        event = AccountEvent(
            event_type=AccountEventType.DRAWDOWN_PAUSE,
            account_id=self.account_id,
            amount=0.0,
            balance_after=self._balance,
            metadata={"reason": reason},
        )
        await self._event_repo.append(event)
        self._event_count += 1

    async def on_drawdown_resume(self) -> None:
        """Record a DRAWDOWN_RESUME event."""
        if not self._initialized:
            await self.initialize()

        event = AccountEvent(
            event_type=AccountEventType.DRAWDOWN_RESUME,
            account_id=self.account_id,
            amount=0.0,
            balance_after=self._balance,
        )
        await self._event_repo.append(event)
        self._event_count += 1

    # ═════════════════════════════════════════════════════════════════════════
    # Event Bus Integration
    # ═════════════════════════════════════════════════════════════════════════

    async def on_trade_opened_event(self, **kwargs) -> None:
        """EventBus handler for TRADE_OPENED events."""
        signal_id = kwargs.get("signal_id", "")
        symbol = kwargs.get("symbol", "")
        direction = kwargs.get("direction", "")
        entry = kwargs.get("entry_price", 0.0) or kwargs.get("entry", 0.0)
        stop_loss = kwargs.get("stop_loss", 0.0)
        if signal_id and entry and stop_loss:
            await self.on_trade_opened(signal_id, symbol, direction, entry, stop_loss)

    async def on_trade_closed_event(self, **kwargs) -> None:
        """EventBus handler for TRADE_CLOSED events."""
        signal_id = kwargs.get("signal_id", "")
        symbol = kwargs.get("symbol", "")
        direction = kwargs.get("direction", "")
        rr_realized = kwargs.get("rr_realized", 0.0)
        pnl_pct = kwargs.get("pnl_pct", 0.0)
        # Convert pnl_pct to dollar amount
        balance = await self.get_balance()
        pnl_dollars = balance * pnl_pct / 100.0 if balance > 0 else 0.0
        if signal_id:
            await self.on_trade_closed(
                signal_id, pnl_dollars, rr_realized, symbol, direction
            )

    def subscribe_to_events(self) -> None:
        """Subscribe to EventBus events for automatic event recording."""
        event_bus.subscribe(EventType.TRADE_OPENED, self.on_trade_opened_event)
        event_bus.subscribe(EventType.TRADE_CLOSED, self.on_trade_closed_event)
        log.info("va_engine_subscribed_to_events")

    # ═════════════════════════════════════════════════════════════════════════
    # Metrics
    # ═════════════════════════════════════════════════════════════════════════

    async def get_metrics(self, window: str = "30d") -> Optional[AccountMetrics]:
        """Get precomputed metrics for a time window."""
        return await self._metrics_repo.get(self.account_id, window)

    async def _recompute_metrics(self) -> None:
        """Recompute 7d and 30d metrics from events."""
        now = datetime.now(timezone.utc)
        for window_days, window_label in [(7, "7d"), (30, "30d")]:
            cutoff = now - timedelta(days=window_days)
            events = await self._event_repo.get_events_since(
                self.account_id, since=cutoff, limit=10000
            )

            # Filter to TRADE_CLOSED events only
            closed_events = [
                e for e in events
                if e.event_type == AccountEventType.TRADE_CLOSED
            ]

            if not closed_events:
                continue

            total_trades = len(closed_events)
            wins = sum(1 for e in closed_events if (e.pnl or 0) > 0)
            losses = sum(1 for e in closed_events if (e.pnl or 0) < 0)
            win_rate = wins / total_trades if total_trades > 0 else 0.0

            rr_values = [e.rr_realized for e in closed_events if e.rr_realized is not None]
            avg_rr = sum(rr_values) / len(rr_values) if rr_values else 0.0

            gross_profit = sum(e.pnl for e in closed_events if (e.pnl or 0) > 0)
            gross_loss = abs(sum(e.pnl for e in closed_events if (e.pnl or 0) < 0))
            profit_factor = gross_profit / gross_loss if gross_loss > 0 else 0.0

            # Max drawdown
            balance_series = []
            running = self._config.initial_balance if self._config else 10000.0
            peak = running
            max_dd = 0.0
            for e in closed_events:
                running += (e.pnl or 0)
                balance_series.append(running)
                if running > peak:
                    peak = running
                dd = (peak - running) / peak if peak > 0 else 0.0
                if dd > max_dd:
                    max_dd = dd

            # Simplified Sharpe ratio
            pnl_values = [e.pnl for e in closed_events if e.pnl is not None]
            sharpe = 0.0
            if len(pnl_values) > 1:
                mean_pnl = sum(pnl_values) / len(pnl_values)
                variance = sum((p - mean_pnl) ** 2 for p in pnl_values) / (len(pnl_values) - 1)
                std_pnl = math.sqrt(variance) if variance > 0 else 0.001
                sharpe = (mean_pnl / std_pnl) * math.sqrt(252)  # annualized

            # Consecutive streaks
            consec_wins = 0
            consec_losses = 0
            for e in reversed(closed_events):
                if (e.pnl or 0) > 0:
                    if consec_losses > 0:
                        break
                    consec_wins += 1
                elif (e.pnl or 0) < 0:
                    if consec_wins > 0:
                        break
                    consec_losses += 1
                else:
                    break

            # Start balance (balance at cutoff)
            start_balance = self._balance
            for e in reversed(closed_events):
                start_balance -= (e.pnl or 0)

            metrics = AccountMetrics(
                account_id=self.account_id,
                window=window_label,
                balance=round(self._balance, 2),
                start_balance=round(start_balance, 2),
                return_pct=round(
                    (self._balance - start_balance) / start_balance * 100, 4
                ) if start_balance > 0 else 0.0,
                total_trades=total_trades,
                wins=wins,
                losses=losses,
                win_rate=round(win_rate, 4),
                avg_rr=round(avg_rr, 4),
                profit_factor=round(profit_factor, 4),
                max_drawdown_pct=round(max_dd * 100, 4),
                sharpe_ratio=round(sharpe, 4),
                consecutive_wins=consec_wins,
                consecutive_losses=consec_losses,
                computed_at=now,
            )
            await self._metrics_repo.upsert(metrics)

    # ═════════════════════════════════════════════════════════════════════════
    # Internal
    # ═════════════════════════════════════════════════════════════════════════

    def _apply_event(self, event: AccountEvent) -> None:
        """Apply an event to the in-memory state."""
        if event.event_type == AccountEventType.DEPOSIT:
            self._balance += event.amount
        elif event.event_type == AccountEventType.WITHDRAWAL:
            self._balance -= abs(event.amount)
        elif event.event_type == AccountEventType.TRADE_CLOSED:
            self._balance += (event.pnl or 0.0)

    async def _maybe_take_snapshot(self) -> None:
        """Take a snapshot if conditions are met."""
        should_snapshot = False

        # Condition 1: Every N events
        events_since = self._event_count - self._last_snapshot_event_seq
        if events_since >= SNAPSHOT_EVENT_INTERVAL:
            should_snapshot = True

        # Condition 2: Every N hours
        if self._last_snapshot_time:
            hours_since = (
                datetime.now(timezone.utc) - self._last_snapshot_time
            ).total_seconds() / 3600
            if hours_since >= SNAPSHOT_TIME_INTERVAL_HOURS:
                should_snapshot = True

        if not should_snapshot:
            return

        snapshot = AccountSnapshot(
            account_id=self.account_id,
            event_seq=self._event_count,
            balance=self._balance,
            equity=self._balance,  # Cash account: equity = balance
            open_trades=self._open_trades,
            total_trades=self._total_trades,
            wins=self._wins,
            losses=self._losses,
        )
        await self._snapshot_repo.save(snapshot)
        self._last_snapshot_event_seq = self._event_count
        self._last_snapshot_time = datetime.now(timezone.utc)

    async def ensure_indexes(self) -> None:
        """Create indexes on all virtual account collections."""
        await self._event_repo.ensure_indexes()
        await self._snapshot_repo.ensure_indexes()
        await self._metrics_repo.ensure_indexes()
        await self._config_repo.ensure_indexes()


# ─── Singleton ────────────────────────────────────────────────────────────────

_va_engine: Optional[VirtualAccountEngine] = None


def get_virtual_account_engine() -> VirtualAccountEngine:
    """Return (and lazily create) the module-level engine singleton."""
    global _va_engine
    if _va_engine is None:
        _va_engine = VirtualAccountEngine()
    return _va_engine
