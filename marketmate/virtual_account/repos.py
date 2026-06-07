"""
marketmate.virtual_account.repos
─────────────────────────────────
MongoDB repositories for the virtual accounting engine.

Four collections:
  virtual_account_config    — account parameters (initial balance, risk%)
  virtual_account_events    — append-only event log (immutable)
  virtual_account_snapshots — periodic balance checkpoints (optimization)
  virtual_account_metrics   — precomputed performance metrics (7d/30d)
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from marketmate.core.logger import get_logger
from marketmate.db.core import mongo_manager
from marketmate.virtual_account.models import (
    AccountEvent,
    AccountEventType,
    AccountSnapshot,
    AccountMetrics,
    AccountConfig,
)

log = get_logger("virtual_account.repos")


# ═══════════════════════════════════════════════════════════════════════════════
# Event Repository — append-only, immutable
# ═══════════════════════════════════════════════════════════════════════════════

class EventRepository:
    """
    Append-only repository for virtual account events.

    Events are NEVER updated or deleted — only inserted.
    Balance is derived by replaying events from the latest snapshot.
    """

    def __init__(self) -> None:
        self._manager = mongo_manager

    async def _col(self):
        try:
            db = await self._manager.get_db()
            return db["virtual_account_events"] if db is not None else None
        except Exception as exc:
            log.warning("va_events_col_unavailable", error=str(exc))
            return None

    async def append(self, event: AccountEvent) -> None:
        """Append a new event. Never raises — failures are logged."""
        col = await self._col()
        if col is None:
            return
        try:
            await col.insert_one(event.to_dict())
            log.debug("va_event_appended",
                      event_id=event.event_id,
                      event_type=event.event_type.value,
                      balance_after=round(event.balance_after, 2))
        except Exception as exc:
            log.error("va_event_append_failed",
                      event_id=event.event_id, error=str(exc))

    async def get_events_since(
        self,
        account_id: str = "default",
        since: Optional[datetime] = None,
        limit: int = 500,
    ) -> list[AccountEvent]:
        """Get events for an account, optionally since a timestamp."""
        col = await self._col()
        if col is None:
            return []
        try:
            query: dict = {"account_id": account_id}
            if since:
                query["timestamp"] = {"$gte": since}
            cursor = col.find(query, {"_id": 0}).sort("timestamp", 1).limit(limit)
            docs = await cursor.to_list(length=limit)
            return [AccountEvent.from_dict(d) for d in docs]
        except Exception as exc:
            log.error("va_events_read_failed", error=str(exc))
            return []

    async def get_event_count(self, account_id: str = "default") -> int:
        """Return total event count for an account."""
        col = await self._col()
        if col is None:
            return 0
        try:
            return await col.count_documents({"account_id": account_id})
        except Exception:
            return 0

    async def get_last_event(self, account_id: str = "default") -> Optional[AccountEvent]:
        """Return the most recent event for an account."""
        col = await self._col()
        if col is None:
            return None
        try:
            doc = await col.find_one(
                {"account_id": account_id},
                sort=[("timestamp", -1)],
            )
            return AccountEvent.from_dict(doc) if doc else None
        except Exception:
            return None

    async def ensure_indexes(self) -> None:
        col = await self._col()
        if col is None:
            return
        try:
            from pymongo import ASCENDING, DESCENDING
            await col.create_index(
                [("account_id", ASCENDING), ("timestamp", ASCENDING)],
                name="account_timestamp",
            )
            await col.create_index(
                [("event_id", ASCENDING)],
                unique=True,
                name="event_id_unique",
            )
            await col.create_index(
                [("event_type", ASCENDING)],
                name="event_type",
            )
        except Exception as exc:
            log.warning("va_events_index_warning", error=str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# Snapshot Repository — periodic checkpoints
# ═══════════════════════════════════════════════════════════════════════════════

class SnapshotRepository:
    """
    Repository for virtual account snapshots.

    Snapshots are an optimization that allows balance computation to
    start from the latest snapshot rather than replaying all events.
    """

    def __init__(self) -> None:
        self._manager = mongo_manager

    async def _col(self):
        try:
            db = await self._manager.get_db()
            return db["virtual_account_snapshots"] if db is not None else None
        except Exception as exc:
            log.warning("va_snapshots_col_unavailable", error=str(exc))
            return None

    async def save(self, snapshot: AccountSnapshot) -> None:
        col = await self._col()
        if col is None:
            return
        try:
            await col.insert_one(snapshot.to_dict())
            log.debug("va_snapshot_saved",
                      account_id=snapshot.account_id,
                      balance=round(snapshot.balance, 2),
                      event_seq=snapshot.event_seq)
        except Exception as exc:
            log.error("va_snapshot_save_failed", error=str(exc))

    async def get_latest(self, account_id: str = "default") -> Optional[AccountSnapshot]:
        col = await self._col()
        if col is None:
            return None
        try:
            doc = await col.find_one(
                {"account_id": account_id},
                sort=[("timestamp", -1)],
            )
            if doc is None:
                return None
            return AccountSnapshot(
                snapshot_id  = doc.get("snapshot_id", ""),
                account_id   = doc.get("account_id", "default"),
                event_seq    = doc.get("event_seq", 0),
                balance      = doc.get("balance", 0.0),
                equity       = doc.get("equity", 0.0),
                open_trades  = doc.get("open_trades", 0),
                total_trades = doc.get("total_trades", 0),
                wins         = doc.get("wins", 0),
                losses       = doc.get("losses", 0),
                timestamp    = doc.get("timestamp", datetime.now(timezone.utc)),
            )
        except Exception:
            return None

    async def ensure_indexes(self) -> None:
        col = await self._col()
        if col is None:
            return
        try:
            from pymongo import ASCENDING, DESCENDING
            await col.create_index(
                [("account_id", ASCENDING), ("timestamp", DESCENDING)],
                name="account_timestamp_desc",
            )
        except Exception as exc:
            log.warning("va_snapshots_index_warning", error=str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# Metrics Repository — precomputed performance
# ═══════════════════════════════════════════════════════════════════════════════

class MetricsRepository:
    """
    Repository for precomputed virtual account performance metrics.

    Two documents per account: "7d" and "30d" windows.
    Updated on every TRADE_CLOSED event.
    """

    def __init__(self) -> None:
        self._manager = mongo_manager

    async def _col(self):
        try:
            db = await self._manager.get_db()
            return db["virtual_account_metrics"] if db is not None else None
        except Exception as exc:
            log.warning("va_metrics_col_unavailable", error=str(exc))
            return None

    async def upsert(self, metrics: AccountMetrics) -> None:
        col = await self._col()
        if col is None:
            return
        try:
            await col.update_one(
                {"account_id": metrics.account_id, "window": metrics.window},
                {"$set": metrics.to_dict()},
                upsert=True,
            )
        except Exception as exc:
            log.error("va_metrics_upsert_failed", error=str(exc))

    async def get(
        self, account_id: str = "default", window: str = "30d"
    ) -> Optional[AccountMetrics]:
        col = await self._col()
        if col is None:
            return None
        try:
            doc = await col.find_one(
                {"account_id": account_id, "window": window}
            )
            if doc is None:
                return None
            return AccountMetrics(
                account_id         = doc.get("account_id", "default"),
                window             = doc.get("window", "30d"),
                balance            = doc.get("balance", 0.0),
                start_balance      = doc.get("start_balance", 0.0),
                return_pct         = doc.get("return_pct", 0.0),
                total_trades       = doc.get("total_trades", 0),
                wins               = doc.get("wins", 0),
                losses             = doc.get("losses", 0),
                win_rate           = doc.get("win_rate", 0.0),
                avg_rr             = doc.get("avg_rr", 0.0),
                profit_factor      = doc.get("profit_factor", 0.0),
                max_drawdown_pct   = doc.get("max_drawdown_pct", 0.0),
                sharpe_ratio       = doc.get("sharpe_ratio", 0.0),
                consecutive_wins   = doc.get("consecutive_wins", 0),
                consecutive_losses = doc.get("consecutive_losses", 0),
                computed_at        = doc.get("computed_at", datetime.now(timezone.utc)),
            )
        except Exception:
            return None

    async def ensure_indexes(self) -> None:
        col = await self._col()
        if col is None:
            return
        try:
            from pymongo import ASCENDING
            await col.create_index(
                [("account_id", ASCENDING), ("window", ASCENDING)],
                unique=True,
                name="account_window_unique",
            )
        except Exception as exc:
            log.warning("va_metrics_index_warning", error=str(exc))


# ═══════════════════════════════════════════════════════════════════════════════
# Config Repository — account settings
# ═══════════════════════════════════════════════════════════════════════════════

class ConfigRepository:
    """
    Repository for virtual account configuration.

    One document per account (typically just "default").
    """

    def __init__(self) -> None:
        self._manager = mongo_manager

    async def _col(self):
        try:
            db = await self._manager.get_db()
            return db["virtual_account_config"] if db is not None else None
        except Exception as exc:
            log.warning("va_config_col_unavailable", error=str(exc))
            return None

    async def get(self, account_id: str = "default") -> AccountConfig:
        """Get config, creating a default if it doesn't exist."""
        col = await self._col()
        if col is None:
            return AccountConfig()
        try:
            doc = await col.find_one({"account_id": account_id})
            if doc is None:
                config = AccountConfig(account_id=account_id)
                await col.insert_one(config.to_dict())
                return config
            return AccountConfig(
                account_id        = doc.get("account_id", "default"),
                initial_balance   = doc.get("initial_balance", 10000.0),
                risk_per_trade_pct = doc.get("risk_per_trade_pct", 1.0),
                currency          = doc.get("currency", "USD"),
                created_at        = doc.get("created_at", datetime.now(timezone.utc)),
                is_active         = doc.get("is_active", True),
            )
        except Exception:
            return AccountConfig()

    async def update(self, config: AccountConfig) -> None:
        col = await self._col()
        if col is None:
            return
        try:
            await col.update_one(
                {"account_id": config.account_id},
                {"$set": config.to_dict()},
                upsert=True,
            )
        except Exception as exc:
            log.error("va_config_update_failed", error=str(exc))

    async def ensure_indexes(self) -> None:
        col = await self._col()
        if col is None:
            return
        try:
            from pymongo import ASCENDING
            await col.create_index(
                [("account_id", ASCENDING)],
                unique=True,
                name="account_id_unique",
            )
        except Exception as exc:
            log.warning("va_config_index_warning", error=str(exc))
