"""
marketmate/db/repositories/trading_accounts.py
───────────────────────────────────────────────
TradingAccountRepository — MongoDB-only MT5 account management.

Migrated from db/trading_accounts.py. Each document represents one MT5
account a subscriber has connected for auto-trade execution.

No SQLite. MongoDB is the sole source of truth.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from marketmate.core.logger import get_logger
from marketmate.db.core import mongo_manager

log = get_logger("db.repositories.trading_accounts")


class TradingAccountRepository:
    """
    MongoDB-only repository for user-linked MT5 trading accounts.

    All methods return None / [] / False gracefully when MongoDB is unavailable.
    """

    def __init__(self) -> None:
        self._manager = mongo_manager

    async def _col(self):
        """Return trading_accounts collection or None. Always safe."""
        try:
            db = await self._manager.get_db()
            return db["trading_accounts"] if db is not None else None
        except Exception as exc:
            log.warning("trading_accounts_col_unavailable", error=str(exc))
            return None

    # ═════════════════════════════════════════════════════════════════════════
    # Reads
    # ═════════════════════════════════════════════════════════════════════════

    async def get_by_chat_id(self, chat_id: str) -> list[dict]:
        """Return all accounts for a user (active and inactive)."""
        col = await self._col()
        if col is None:
            return []
        try:
            cursor = col.find({"chat_id": chat_id}, {"_id": 0})
            return await cursor.to_list(length=20)
        except Exception as exc:
            log.error("trading_accounts_get_failed", chat_id=chat_id, error=str(exc))
            return []

    async def get_active_accounts_for_signal(self) -> list[dict]:
        """
        Return ALL active accounts across ALL users.
        Called from _process_pair to find who gets a "Place Trade?" button.
        """
        col = await self._col()
        if col is None:
            return []
        try:
            cursor = col.find({"active": True}, {"_id": 0})
            return await cursor.to_list(length=10_000)
        except Exception as exc:
            log.error("trading_accounts_active_query_failed", error=str(exc))
            return []

    async def get_by_account_id(self, account_id: str) -> Optional[dict]:
        """Fetch one account by its account_id field."""
        col = await self._col()
        if col is None:
            return None
        try:
            return await col.find_one({"account_id": account_id}, {"_id": 0})
        except Exception as exc:
            log.error("trading_accounts_fetch_failed", account_id=account_id, error=str(exc))
            return None

    # ═════════════════════════════════════════════════════════════════════════
    # Writes
    # ═════════════════════════════════════════════════════════════════════════

    async def upsert(
        self,
        chat_id:             str,
        account_id:          str,
        nickname:            str,
        broker:              str,
        account_number:      str,
        server:              str,
        risk_mode:           str   = "fixed_pct",
        risk_value:          float = 1.0,
        max_positions:       int   = 1,
        slippage:            float = 0.5,
        active:              bool  = False,
        meta_api_account_id: str   = "",
    ) -> bool:
        col = await self._col()
        if col is None:
            return False
        try:
            now = datetime.now(timezone.utc)
            await col.update_one(
                {"account_id": account_id},
                {"$set": {
                    "chat_id":             chat_id,
                    "account_id":          account_id,
                    "nickname":            nickname,
                    "broker":              broker,
                    "account_number":      account_number,
                    "server":              server,
                    "risk_mode":           risk_mode,
                    "risk_value":          risk_value,
                    "max_positions":       max_positions,
                    "slippage":            slippage,
                    "active":              active,
                    "meta_api_account_id": meta_api_account_id,
                    "updated_at":          now,
                },
                 "$setOnInsert": {"created_at": now}},
                upsert=True,
            )
            log.info("trading_account_upserted",
                     chat_id=chat_id, account_id=account_id, active=active)
            return True
        except Exception as exc:
            log.error("trading_account_upsert_failed", error=str(exc))
            return False

    async def set_active(self, account_id: str, active: bool) -> bool:
        """Toggle auto-trade on or off for one account."""
        col = await self._col()
        if col is None:
            return False
        try:
            result = await col.update_one(
                {"account_id": account_id},
                {"$set": {"active": active,
                          "updated_at": datetime.now(timezone.utc)}}
            )
            return result.modified_count > 0
        except Exception as exc:
            log.error("trading_account_toggle_failed", error=str(exc))
            return False

    async def delete(self, account_id: str, chat_id: str) -> bool:
        """Delete an account. Requires chat_id match for ownership verification."""
        col = await self._col()
        if col is None:
            return False
        try:
            result = await col.delete_one(
                {"account_id": account_id, "chat_id": chat_id}
            )
            return result.deleted_count > 0
        except Exception as exc:
            log.error("trading_account_delete_failed", error=str(exc))
            return False

    # ═════════════════════════════════════════════════════════════════════════
    # Indexes
    # ═════════════════════════════════════════════════════════════════════════

    async def ensure_indexes(self) -> None:
        """Create indexes on trading_accounts collection."""
        col = await self._col()
        if col is None:
            return
        from pymongo import ASCENDING
        specs = [
            ([("chat_id",    ASCENDING)], {}),
            ([("account_id", ASCENDING)], {"unique": True}),
            ([("active",     ASCENDING)], {}),
        ]
        for keys, opts in specs:
            try:
                await col.create_index(keys, **opts)
            except Exception as exc:
                log.warning("trading_accounts_index_warning", error=str(exc))
        log.debug("trading_accounts_indexes_ensured")


# ─── Module-level singleton ────────────────────────────────────────────────────
# Backward-compatible alias used by:
#   from marketmate.db.repositories.trading_accounts import trading_account_store

trading_account_store = TradingAccountRepository()
