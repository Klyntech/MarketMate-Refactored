"""
marketmate.virtual_account.models
──────────────────────────────────
Typed domain models for the virtual accounting engine.

All models are immutable dataclasses with to_dict() for MongoDB serialization.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any, Dict, List, Optional


class AccountEventType(str, Enum):
    """Canonical event types in the virtual account event log."""
    DEPOSIT         = "DEPOSIT"
    TRADE_OPENED    = "TRADE_OPENED"
    TRADE_CLOSED    = "TRADE_CLOSED"
    DRAWDOWN_PAUSE  = "DRAWDOWN_PAUSE"
    DRAWDOWN_RESUME = "DRAWDOWN_RESUME"
    WITHDRAWAL      = "WITHDRAWAL"
    ADJUSTMENT      = "ADJUSTMENT"


@dataclass
class AccountEvent:
    """
    A single immutable event in the virtual account ledger.

    Every state change is recorded as an event. Balances are always
    derived by replaying events from the beginning (or from the latest
    snapshot). Events are NEVER mutated after insertion.

    Fields:
      event_id:     Unique identifier (UUID4)
      event_type:   One of AccountEventType
      timestamp:    When the event occurred (UTC)
      account_id:   Which virtual account this belongs to
      amount:       The monetary amount involved (positive = credit, negative = debit)
      balance_after: The computed balance AFTER this event was applied
      trade_id:     For TRADE_OPENED/TRADE_CLOSED: the signal_id
      risk_amount:  For TRADE_OPENED: the dollar amount risked (1% of balance)
      pnl:          For TRADE_CLOSED: the realized profit/loss in dollars
      rr_realized:  For TRADE_CLOSED: the R-multiple realized
      direction:    For trade events: BUY or SELL
      symbol:       For trade events: the trading pair
      metadata:     Additional key-value data (gate_trace, proximity, etc.)
    """
    event_id:      str = field(default_factory=lambda: str(uuid.uuid4()))
    event_type:    AccountEventType = AccountEventType.DEPOSIT
    timestamp:     datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    account_id:    str = "default"
    amount:        float = 0.0
    balance_after: float = 0.0
    trade_id:      Optional[str] = None
    risk_amount:   Optional[float] = None
    pnl:           Optional[float] = None
    rr_realized:   Optional[float] = None
    direction:     Optional[str] = None
    symbol:        Optional[str] = None
    metadata:      Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        d: Dict[str, Any] = {
            "event_id":      self.event_id,
            "event_type":    self.event_type.value,
            "timestamp":     self.timestamp,
            "account_id":    self.account_id,
            "amount":        round(self.amount, 6),
            "balance_after": round(self.balance_after, 6),
        }
        if self.trade_id is not None:
            d["trade_id"] = self.trade_id
        if self.risk_amount is not None:
            d["risk_amount"] = round(self.risk_amount, 6)
        if self.pnl is not None:
            d["pnl"] = round(self.pnl, 6)
        if self.rr_realized is not None:
            d["rr_realized"] = round(self.rr_realized, 4)
        if self.direction is not None:
            d["direction"] = self.direction
        if self.symbol is not None:
            d["symbol"] = self.symbol
        if self.metadata:
            d["metadata"] = self.metadata
        return d

    @classmethod
    def from_dict(cls, d: Dict[str, Any]) -> "AccountEvent":
        """Reconstruct an AccountEvent from a MongoDB document."""
        return cls(
            event_id      = d.get("event_id", ""),
            event_type    = AccountEventType(d.get("event_type", "DEPOSIT")),
            timestamp     = d.get("timestamp", datetime.now(timezone.utc)),
            account_id    = d.get("account_id", "default"),
            amount        = d.get("amount", 0.0),
            balance_after = d.get("balance_after", 0.0),
            trade_id      = d.get("trade_id"),
            risk_amount   = d.get("risk_amount"),
            pnl           = d.get("pnl"),
            rr_realized   = d.get("rr_realized"),
            direction     = d.get("direction"),
            symbol        = d.get("symbol"),
            metadata      = d.get("metadata", {}),
        )


@dataclass
class AccountSnapshot:
    """
    A periodic checkpoint of the virtual account balance.

    Snapshots are an optimization — they allow balance computation to
    start from the snapshot rather than replaying all events from the
    beginning. The snapshot is always consistent because it is derived
    from the event log.

    Snapshots are taken:
      - Every 50 events
      - Every 24 hours (whichever comes first)
      - On application shutdown (graceful)

    Fields:
      snapshot_id:  Unique identifier
      account_id:   Which virtual account
      event_seq:    The sequence number of the last event included
      balance:      The computed balance at this point
      equity:       Balance + unrealized P&L (same as balance for cash account)
      open_trades:  Number of currently open trades
      total_trades: Total trades since account inception
      wins:         Total winning trades
      losses:       Total losing trades
      timestamp:    When the snapshot was taken
    """
    snapshot_id:   str = field(default_factory=lambda: str(uuid.uuid4()))
    account_id:    str = "default"
    event_seq:     int = 0
    balance:       float = 0.0
    equity:        float = 0.0
    open_trades:   int = 0
    total_trades:  int = 0
    wins:          int = 0
    losses:        int = 0
    timestamp:     datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "snapshot_id":  self.snapshot_id,
            "account_id":   self.account_id,
            "event_seq":    self.event_seq,
            "balance":      round(self.balance, 2),
            "equity":       round(self.equity, 2),
            "open_trades":  self.open_trades,
            "total_trades": self.total_trades,
            "wins":         self.wins,
            "losses":       self.losses,
            "timestamp":    self.timestamp,
        }


@dataclass
class AccountMetrics:
    """
    Precomputed performance metrics for the virtual account.

    These are recalculated on every TRADE_CLOSED event and stored in
    the virtual_account_metrics collection. Two time windows are
    maintained: 7 days and 30 days.

    Fields:
      account_id:   Which virtual account
      window:       "7d" or "30d"
      balance:      Current account balance
      start_balance: Balance at the start of the window
      return_pct:   Percentage return over the window
      total_trades: Trades in the window
      wins:         Winning trades in the window
      losses:       Losing trades in the window
      win_rate:     Win rate as a decimal (0.0 - 1.0)
      avg_rr:       Average R-multiple in the window
      profit_factor: Gross profit / Gross loss
      max_drawdown_pct: Maximum drawdown percentage in the window
      sharpe_ratio:  Annualized Sharpe ratio (simplified)
      consecutive_wins:  Current streak of consecutive wins
      consecutive_losses: Current streak of consecutive losses
      computed_at:  When these metrics were last computed
    """
    account_id:          str = "default"
    window:              str = "30d"
    balance:             float = 0.0
    start_balance:       float = 0.0
    return_pct:          float = 0.0
    total_trades:        int = 0
    wins:                int = 0
    losses:              int = 0
    win_rate:            float = 0.0
    avg_rr:              float = 0.0
    profit_factor:       float = 0.0
    max_drawdown_pct:    float = 0.0
    sharpe_ratio:        float = 0.0
    consecutive_wins:    int = 0
    consecutive_losses:  int = 0
    computed_at:         datetime = field(default_factory=lambda: datetime.now(timezone.utc))

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id":         self.account_id,
            "window":             self.window,
            "balance":            round(self.balance, 2),
            "start_balance":      round(self.start_balance, 2),
            "return_pct":         round(self.return_pct, 4),
            "total_trades":       self.total_trades,
            "wins":               self.wins,
            "losses":             self.losses,
            "win_rate":           round(self.win_rate, 4),
            "avg_rr":             round(self.avg_rr, 4),
            "profit_factor":      round(self.profit_factor, 4),
            "max_drawdown_pct":   round(self.max_drawdown_pct, 4),
            "sharpe_ratio":       round(self.sharpe_ratio, 4),
            "consecutive_wins":   self.consecutive_wins,
            "consecutive_losses": self.consecutive_losses,
            "computed_at":        self.computed_at,
        }


@dataclass
class AccountConfig:
    """
    Configuration for a virtual account.

    Stored in virtual_account_config collection. One document per account.
    """
    account_id:       str = "default"
    initial_balance:  float = 10000.0
    risk_per_trade_pct: float = 1.0   # 1% risk per trade
    currency:         str = "USD"
    created_at:       datetime = field(default_factory=lambda: datetime.now(timezone.utc))
    is_active:        bool = True

    def to_dict(self) -> Dict[str, Any]:
        return {
            "account_id":        self.account_id,
            "initial_balance":   self.initial_balance,
            "risk_per_trade_pct": self.risk_per_trade_pct,
            "currency":          self.currency,
            "created_at":        self.created_at,
            "is_active":         self.is_active,
        }
