"""
marketmate/db/repositories/signals.py
──────────────────────────────────────
SignalRepository — all signal CRUD operations, MongoDB-only.

Migrated from db/sqlite.py + db/signals.py. Combines the operational
signal store (formerly SQLite) with the durable signal_archive (MongoDB)
into a single MongoDB-only implementation.

No SQLite. No reconciliation. In-memory LRU cache for hot-path queries.

Collections:
  signal_archive — canonical, append-only record of every signal and outcome
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional

from signal_engine.core.logger import get_logger
from signal_engine.db.core import mongo_manager, db_cache

log = get_logger("db.repositories.signals")

# All valid terminal outcomes
VALID_OUTCOMES = {"WIN", "LOSS", "BREAKEVEN", "BE", "EXPIRED"}


class SignalRepository:
    """
    MongoDB-only repository for all signal operations.

    Provides both operational queries (daily count, consecutive losses,
    open signals) and archival operations (archive, update outcome).

    Hot-path queries are cached in-memory via db_cache with short TTLs.
    """

    def __init__(self) -> None:
        self._manager = mongo_manager

    async def _col(self):
        """Return signal_archive collection or None. Always safe."""
        try:
            db = await self._manager.get_db()
            return db["signal_archive"] if db is not None else None
        except Exception as exc:
            log.warning("signal_archive_col_unavailable", error=str(exc))
            return None

    # ═════════════════════════════════════════════════════════════════════════
    # Writes — Archive
    # ═════════════════════════════════════════════════════════════════════════

    async def archive(self, signal, gate_trace: list[dict]) -> None:
        """
        Insert a new signal_archive document at the moment a signal is generated.

        Call this right after a signal passes all gates, before Telegram delivery.
        The outcome fields are intentionally absent — they are added by
        update_outcome() when the trade closes.

        Also inserts into the operational signals collection for tracking.
        """
        try:
            db = await self._manager.get_db()
            if db is None:
                return

            d = signal.to_dict()
            doc = {
                "signal_id":    d["id"],
                "symbol":       d["symbol"],
                "direction":    d["direction"],
                "entry_low":    d["entry_low"],
                "entry_high":   d["entry_high"],
                "entry_mid":    d["entry_mid"],
                "stop_loss":    d["stop_loss"],
                "tp1":          d["tp1"],
                "tp2":          d["tp2"],
                "tp3":          d.get("tp3"),
                "rr":           d["rr"],
                "position_size": d["position_size"],
                "confidence":   d["confidence"],
                "zone_type":    d["zone_type"],
                "confirm_type": d["confirm_type"],
                "confirm_tf":   d["confirm_tf"],
                "gate_trace":   gate_trace,
                "generated_at": datetime.now(timezone.utc),
                "status":       "PENDING",
                # outcome fields populated later by update_outcome()
            }

            await db["signal_archive"].insert_one(doc)
            log.debug("signal_archived", signal_id=d["id"], symbol=d["symbol"])

            # Invalidate relevant caches
            await db_cache.invalidate_prefix("daily_count:")
            await db_cache.invalidate("open_signals")
            await db_cache.invalidate("consecutive_losses")

        except Exception as exc:
            # Never block signal delivery on archive failure
            log.error("signal_archive_failed", signal_id=getattr(signal, "id", "?"),
                      error=str(exc))

    async def update_outcome(
        self,
        signal_id:    str,
        outcome:      str,
        exit_price:   float,
        pnl_r:        float,
        candles_held: int,
        proximity:    Optional[dict] = None,
    ) -> None:
        """
        Add outcome fields to an existing signal_archive document.

        Called from lifecycle/trade_manager when a trade closes.
        Outcome must be one of: WIN | LOSS | BREAKEVEN | EXPIRED
        """
        try:
            db = await self._manager.get_db()
            if db is None:
                return

            outcome_upper = outcome.upper()
            if outcome_upper not in VALID_OUTCOMES:
                log.warning("unknown_outcome_value", signal_id=signal_id,
                            outcome=outcome, allowed=list(VALID_OUTCOMES))

            set_fields: dict = {
                "outcome":      outcome_upper,
                "exit_price":   exit_price,
                "pnl_r":        round(pnl_r, 4),
                "candles_held": candles_held,
                "closed_at":    datetime.now(timezone.utc),
                "status":       "CLOSED",
                "close_reason": outcome_upper,
                "pnl_pct":      round(pnl_r * 100, 2),
            }

            if proximity is not None:
                set_fields["proximity"] = proximity

            await db["signal_archive"].update_one(
                {"signal_id": signal_id},
                {"$set": set_fields},
            )
            log.debug("signal_outcome_recorded", signal_id=signal_id,
                      outcome=outcome_upper,
                      mfe_pct=proximity.get("mfe_pct") if proximity else None,
                      approached_tp=proximity.get("approached_tp") if proximity else None)

            # Invalidate caches that depend on closed trades
            await db_cache.invalidate_prefix("daily_count:")
            await db_cache.invalidate("open_signals")
            await db_cache.invalidate("consecutive_losses")
            await db_cache.invalidate_prefix("performance_stats:")
            await db_cache.invalidate("virtual_account_summary")
            await db_cache.invalidate_prefix("virtual_trade_history:")

        except Exception as exc:
            log.error("signal_outcome_update_failed", signal_id=signal_id, error=str(exc))

    # ═════════════════════════════════════════════════════════════════════════
    # Writes — Operational Status
    # ═════════════════════════════════════════════════════════════════════════

    async def insert(self, signal) -> None:
        """
        Insert a new signal into the operational store.
        In MongoDB-only mode, this is equivalent to archive() but with
        status='PENDING' and no gate_trace requirement.
        """
        try:
            db = await self._manager.get_db()
            if db is None:
                return

            d = signal.to_dict()
            # Check if already archived (archive() may have been called first)
            existing = await db["signal_archive"].find_one({"signal_id": d["id"]})
            if existing:
                # Already in archive — just update status if needed
                if existing.get("status") != d.get("status", "PENDING"):
                    await db["signal_archive"].update_one(
                        {"signal_id": d["id"]},
                        {"$set": {"status": d.get("status", "PENDING")}},
                    )
                return

            doc = {
                "signal_id":     d["id"],
                "symbol":        d["symbol"],
                "direction":     d["direction"],
                "entry_low":     d["entry_low"],
                "entry_high":    d["entry_high"],
                "entry_mid":     d["entry_mid"],
                "stop_loss":     d["stop_loss"],
                "tp1":           d["tp1"],
                "tp2":           d["tp2"],
                "tp3":           d.get("tp3"),
                "rr":            d["rr"],
                "position_size": d["position_size"],
                "confidence":    d["confidence"],
                "zone_type":     d["zone_type"],
                "confirm_type":  d["confirm_type"],
                "confirm_tf":    d["confirm_tf"],
                "status":        d.get("status", "PENDING"),
                "generated_at":  datetime.now(timezone.utc),
            }
            await db["signal_archive"].insert_one(doc)

            await db_cache.invalidate_prefix("daily_count:")
            await db_cache.invalidate("open_signals")
            log.debug("signal_inserted", signal_id=d["id"])

        except Exception as exc:
            log.error("signal_insert_failed", signal_id=getattr(signal, "id", "?"),
                      error=str(exc))

    async def update_status(
        self,
        signal_id:    str,
        status:       str,
        close_reason: Optional[str] = None,
        pnl_pct:      Optional[float] = None,
    ) -> None:
        """Update the status of a signal (PENDING → OPEN → RUNNING → CLOSED)."""
        try:
            db = await self._manager.get_db()
            if db is None:
                return

            set_fields: dict = {"status": status}
            if status == "CLOSED":
                set_fields["closed_at"] = datetime.now(timezone.utc).isoformat()
            if close_reason is not None:
                set_fields["close_reason"] = close_reason
            if pnl_pct is not None:
                set_fields["pnl_pct"] = pnl_pct

            await db["signal_archive"].update_one(
                {"signal_id": signal_id},
                {"$set": set_fields},
            )

            # Invalidate caches
            await db_cache.invalidate("open_signals")
            if status == "CLOSED":
                await db_cache.invalidate_prefix("daily_count:")
                await db_cache.invalidate("consecutive_losses")
                await db_cache.invalidate_prefix("performance_stats:")
                await db_cache.invalidate("virtual_account_summary")

            log.debug("signal_status_updated", signal_id=signal_id, status=status)

        except Exception as exc:
            log.error("signal_status_update_failed", signal_id=signal_id,
                      error=str(exc))

    # ═════════════════════════════════════════════════════════════════════════
    # Reads — Hot-path (cached)
    # ═════════════════════════════════════════════════════════════════════════

    async def get_daily_count(self, date_str: str) -> int:
        """
        Return the number of signals created on a given date.
        Cached for 30 seconds — changes at most once per signal generation.
        """
        cache_key = f"daily_count:{date_str}"
        cached = await db_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            db = await self._manager.get_db()
            if db is None:
                return 0

            # Parse date and query range
            date_start = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
            date_end = date_start + timedelta(days=1)

            count = await db["signal_archive"].count_documents({
                "generated_at": {"$gte": date_start, "$lt": date_end},
            })

            await db_cache.set(cache_key, count, ttl=30.0)
            return count

        except Exception as exc:
            log.error("get_daily_count_failed", date_str=date_str, error=str(exc))
            return 0

    async def get_consecutive_losses(self) -> int:
        """
        Count recent consecutive closed losses.
        Cached for 30 seconds — changes at most once per trade close.
        """
        cache_key = "consecutive_losses"
        cached = await db_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            db = await self._manager.get_db()
            if db is None:
                return 0

            cursor = db["signal_archive"].find(
                {"outcome": {"$exists": True}},
                {"pnl_r": 1, "closed_at": 1, "_id": 0},
            ).sort("closed_at", -1).limit(10)

            docs = await cursor.to_list(length=10)
            count = 0
            for doc in docs:
                pnl_r = doc.get("pnl_r")
                if pnl_r is not None and pnl_r < 0:
                    count += 1
                else:
                    break

            await db_cache.set(cache_key, count, ttl=30.0)
            return count

        except Exception as exc:
            log.error("get_consecutive_losses_failed", error=str(exc))
            return 0

    async def get_open(self) -> list[dict]:
        """
        Return all currently open/running/pending signals.
        Cached for 10 seconds — changes on signal open/close.
        """
        cache_key = "open_signals"
        cached = await db_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            db = await self._manager.get_db()
            if db is None:
                return []

            cursor = db["signal_archive"].find(
                {"status": {"$in": ["OPEN", "RUNNING", "PENDING"]}},
                {"_id": 0, "gate_trace": 0},
            )
            results = await cursor.to_list(length=100)

            await db_cache.set(cache_key, results, ttl=10.0)
            return results

        except Exception as exc:
            log.error("get_open_signals_failed", error=str(exc))
            return []

    # Alias for backward compatibility — many callers use get_open_signals()
    get_open_signals = get_open

    # ═════════════════════════════════════════════════════════════════════════
    # Reads — Analytics
    # ═════════════════════════════════════════════════════════════════════════

    async def get_stats(self, days: int = 30) -> dict:
        """
        Query MongoDB signal_archive for performance statistics over the last N days.

        This is the DURABLE source of truth for /performance.
        Returns: {total, wins, losses, avg_rr, pnl_pct}
        """
        cache_key = f"performance_stats:{days}"
        cached = await db_cache.get(cache_key)
        if cached is not None:
            return cached

        default: dict = {"total": 0, "wins": 0, "losses": 0, "avg_rr": 0, "pnl_pct": 0}

        try:
            db = await self._manager.get_db()
            if db is None:
                return default

            cutoff = datetime.now(timezone.utc) - timedelta(days=days)

            pipeline = [
                {
                    "$match": {
                        "outcome": {"$exists": True},
                        "closed_at": {"$gte": cutoff},
                    }
                },
                {
                    "$group": {
                        "_id": None,
                        "total":      {"$sum": 1},
                        "wins":       {"$sum": {"$cond": [{"$in": ["$outcome", ["WIN"]]}, 1, 0]}},
                        "losses":     {"$sum": {"$cond": [{"$in": ["$outcome", ["LOSS"]]}, 1, 0]}},
                        "avg_rr":     {"$avg": "$pnl_r"},
                        "total_pnl_r": {"$sum": "$pnl_r"},
                    }
                },
            ]

            result = await db["signal_archive"].aggregate(pipeline).to_list(length=1)

            if not result:
                await db_cache.set(cache_key, default, ttl=60.0)
                return default

            r = result[0]
            stats = {
                "total":   r.get("total", 0),
                "wins":    r.get("wins", 0),
                "losses":  r.get("losses", 0),
                "avg_rr":  round(r.get("avg_rr", 0) or 0, 2),
                "pnl_pct": round(r.get("total_pnl_r", 0) or 0, 2),
            }

            await db_cache.set(cache_key, stats, ttl=60.0)
            return stats

        except Exception as exc:
            log.error("mongo_performance_stats_failed", days=days, error=str(exc))
            return default

    async def get_performance_stats(self, days: int = 30) -> dict:
        """Alias for get_stats() — compatible with old API."""
        return await self.get_stats(days)

    # ═════════════════════════════════════════════════════════════════════════
    # Reads — Virtual Account
    # ═════════════════════════════════════════════════════════════════════════

    async def get_virtual_account_summary(self) -> dict:
        """
        Return aggregate summary of all signals for the virtual account display.
        Cached for 60 seconds.
        """
        cache_key = "virtual_account_summary"
        cached = await db_cache.get(cache_key)
        if cached is not None:
            return cached

        default: dict = {
            "total_signals": 0, "wins": 0, "losses": 0,
            "open_trades": 0, "avg_rr": 0.0,
        }

        try:
            db = await self._manager.get_db()
            if db is None:
                return default

            pipeline = [
                {
                    "$facet": {
                        "total":    [{"$count": "value"}],
                        "wins":     [{"$match": {"outcome": "WIN"}}, {"$count": "value"}],
                        "losses":   [{"$match": {"outcome": "LOSS"}}, {"$count": "value"}],
                        "open":     [{"$match": {"status": {"$in": ["OPEN", "RUNNING", "PENDING"]}}},
                                     {"$count": "value"}],
                        "avg_rr":   [{"$match": {"outcome": {"$exists": True}}},
                                     {"$group": {"_id": None, "avg": {"$avg": "$rr"}}}],
                    }
                },
            ]

            result = await db["signal_archive"].aggregate(pipeline).to_list(length=1)

            if not result:
                await db_cache.set(cache_key, default, ttl=60.0)
                return default

            facet = result[0]
            summary = {
                "total_signals": facet["total"][0]["value"] if facet["total"] else 0,
                "wins":          facet["wins"][0]["value"] if facet["wins"] else 0,
                "losses":        facet["losses"][0]["value"] if facet["losses"] else 0,
                "open_trades":   facet["open"][0]["value"] if facet["open"] else 0,
                "avg_rr":        round(facet["avg_rr"][0]["avg"], 2) if facet["avg_rr"] else 0.0,
            }

            await db_cache.set(cache_key, summary, ttl=60.0)
            return summary

        except Exception as exc:
            log.error("get_virtual_account_summary_failed", error=str(exc))
            return default

    async def get_virtual_trade_history(self, limit: int = 20) -> list[dict]:
        """
        Return the most recent closed trades for virtual account display.
        Cached for 60 seconds.
        """
        cache_key = f"virtual_trade_history:{limit}"
        cached = await db_cache.get(cache_key)
        if cached is not None:
            return cached

        try:
            db = await self._manager.get_db()
            if db is None:
                return []

            cursor = db["signal_archive"].find(
                {"outcome": {"$exists": True}},
                {
                    "_id": 0, "signal_id": 1, "symbol": 1, "direction": 1,
                    "entry_mid": 1, "stop_loss": 1, "tp1": 1, "rr": 1,
                    "confidence": 1, "status": 1, "closed_at": 1,
                    "close_reason": 1, "pnl_pct": 1, "outcome": 1, "pnl_r": 1,
                },
            ).sort("closed_at", -1).limit(limit)

            results = await cursor.to_list(length=limit)
            await db_cache.set(cache_key, results, ttl=60.0)
            return results

        except Exception as exc:
            log.error("get_virtual_trade_history_failed", error=str(exc))
            return []

    # ═════════════════════════════════════════════════════════════════════════
    # Reads — General
    # ═════════════════════════════════════════════════════════════════════════

    async def get_closed_signals(self, limit: int = 100) -> list[dict]:
        """Return the most recent closed signals (have outcome field)."""
        try:
            db = await self._manager.get_db()
            if db is None:
                return []
            cursor = (
                db["signal_archive"]
                .find({"outcome": {"$exists": True}}, {"_id": 0, "gate_trace": 0})
                .sort("closed_at", -1)
                .limit(limit)
            )
            return await cursor.to_list(length=limit)
        except Exception as exc:
            log.error("get_closed_signals_failed", error=str(exc))
            return []

    async def get_all_signals(self, limit: int = 200) -> list[dict]:
        """Return all archived signals (open and closed), newest first."""
        try:
            db = await self._manager.get_db()
            if db is None:
                return []
            cursor = (
                db["signal_archive"]
                .find({}, {"_id": 0, "gate_trace": 0})
                .sort("generated_at", -1)
                .limit(limit)
            )
            return await cursor.to_list(length=limit)
        except Exception as exc:
            log.error("get_all_signals_failed", error=str(exc))
            return []

    async def get_signals_with_mt5_ticket(self) -> list[dict]:
        """Return all open signals that have an MT5 ticket assigned."""
        try:
            db = await self._manager.get_db()
            if db is None:
                return []
            cursor = db["signal_archive"].find(
                {
                    "mt5_ticket": {"$exists": True, "$ne": None},
                    "status": {"$in": ["OPEN", "RUNNING", "PENDING"]},
                },
                {"_id": 0, "gate_trace": 0},
            )
            return await cursor.to_list(length=100)
        except Exception as exc:
            log.error("get_signals_with_mt5_ticket_failed", error=str(exc))
            return []

    # ═════════════════════════════════════════════════════════════════════════
    # Writes — MT5 / Virtual Execution
    # ═════════════════════════════════════════════════════════════════════════

    async def set_mt5_ticket(
        self,
        signal_id:   str,
        ticket:      int,
        entry_price: float,
    ) -> None:
        """Store MT5 ticket and actual fill price after successful execution."""
        try:
            db = await self._manager.get_db()
            if db is None:
                return
            await db["signal_archive"].update_one(
                {"signal_id": signal_id},
                {"$set": {
                    "mt5_ticket": ticket,
                    "mt5_entry_price": entry_price,
                    "status": "OPEN",
                }},
            )
            await db_cache.invalidate("open_signals")
        except Exception as exc:
            log.error("set_mt5_ticket_failed", signal_id=signal_id, error=str(exc))

    async def update_mongo_doc_id(self, signal_id: str, doc_id: str) -> None:
        """Persist the MongoDB training document ID so it survives restarts."""
        try:
            db = await self._manager.get_db()
            if db is None:
                return
            await db["signal_archive"].update_one(
                {"signal_id": signal_id},
                {"$set": {"mongo_doc_id": doc_id}},
            )
            log.debug("mongo_doc_id_persisted", signal_id=signal_id, doc_id=doc_id)
        except Exception as exc:
            log.error("update_mongo_doc_id_failed", signal_id=signal_id, error=str(exc))

    async def activate_virtual_trade(self, signal_id: str, entry_price: float) -> None:
        """Simulated execution: move PENDING → OPEN and record the virtual fill price."""
        try:
            db = await self._manager.get_db()
            if db is None:
                return
            await db["signal_archive"].update_one(
                {"signal_id": signal_id, "status": "PENDING"},
                {"$set": {"status": "OPEN", "mt5_entry_price": entry_price}},
            )
            await db_cache.invalidate("open_signals")
            log.debug("virtual_trade_activated", signal_id=signal_id,
                      entry_price=round(entry_price, 4))
        except Exception as exc:
            log.error("activate_virtual_trade_failed", signal_id=signal_id, error=str(exc))

    async def log_trade_event(
        self,
        signal_id:  str,
        event_type: str,
        price:      Optional[float] = None,
        note:       Optional[str]   = None,
    ) -> None:
        """Append a trade lifecycle event (TP1_HIT, SL_HIT, etc.)."""
        try:
            db = await self._manager.get_db()
            if db is None:
                return
            event = {
                "signal_id":  signal_id,
                "event_type": event_type,
                "price":      price,
                "note":       note,
                "created_at": datetime.now(timezone.utc),
            }
            await db["trade_events"].insert_one(event)
        except Exception as exc:
            log.error("log_trade_event_failed", signal_id=signal_id, error=str(exc))

    # ═════════════════════════════════════════════════════════════════════════
    # Indexes
    # ═════════════════════════════════════════════════════════════════════════

    async def ensure_indexes(self) -> None:
        """Create indexes on signal_archive and trade_events. Safe to call repeatedly."""
        try:
            db = await self._manager.get_db()
            if db is None:
                return

            from pymongo import ASCENDING, DESCENDING

            # signal_archive indexes
            archive_specs = [
                ({"signal_id":   ASCENDING},  {"unique": True, "name": "signal_id_unique"}),
                ({"generated_at": DESCENDING}, {}),
                ({"outcome":      ASCENDING},  {}),
                ({"symbol":       ASCENDING},  {}),
                ({"closed_at":    DESCENDING}, {}),
                ({"status":       ASCENDING},  {}),
            ]
            for keys, opts in archive_specs:
                try:
                    await db["signal_archive"].create_index(list(keys.items()), **opts)
                except Exception as exc:
                    log.warning("signal_archive_index_warning", error=str(exc))

            # trade_events indexes
            try:
                await db["trade_events"].create_index(
                    [("signal_id", ASCENDING), ("created_at", DESCENDING)],
                    name="signal_id_created_at",
                )
            except Exception as exc:
                log.warning("trade_events_index_warning", error=str(exc))

            log.debug("signal_indexes_ensured")

        except Exception as exc:
            log.error("signal_ensure_indexes_failed", error=str(exc))
