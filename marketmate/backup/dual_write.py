"""
marketmate.backup.dual_write
─────────────────────────────
Dual-write MongoDB replication manager.

Every write operation is sent to both the primary MongoDB instance
(MONGODB_URI) and the replica instance (MONGODB_REPLICA_URI)
simultaneously. Reads always come from the primary.

If the replica write fails, the primary write still succeeds —
replication is asynchronous and best-effort. A background health
check monitors replica connectivity and logs discrepancies.

The DualWriteManager wraps the Motor client and provides:
  - dual_insert_one(collection, doc)
  - dual_update_one(collection, filter, update, **kwargs)
  - dual_delete_one(collection, filter)
  - get_replica_status() → health info
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger

log = get_logger("backup.dual_write")

try:
    from motor.motor_asyncio import AsyncIOMotorClient
    _MOTOR_AVAILABLE = True
except ImportError:
    _MOTOR_AVAILABLE = False


class DualWriteManager:
    """
    Manages dual-write replication to a secondary MongoDB instance.

    All writes go to both primary and replica. Reads always use primary.
    Replica failures are logged but never block the primary operation.
    """

    def __init__(self) -> None:
        self._replica_client: Optional[Any] = None
        self._replica_db: Optional[Any] = None
        self._replica_uri: str = ""
        self._connected: bool = False
        self._write_count: int = 0
        self._replica_fail_count: int = 0
        self._replica_success_count: int = 0

    async def connect(self) -> bool:
        """
        Connect to the replica MongoDB instance.

        Reads MONGODB_REPLICA_URI from environment. If not set,
        dual-write is silently disabled.
        """
        import os
        self._replica_uri = os.getenv("MONGODB_REPLICA_URI", "")

        if not self._replica_uri:
            log.info("dual_write_disabled", reason="MONGODB_REPLICA_URI not set")
            return False

        if not _MOTOR_AVAILABLE:
            log.warning("dual_write_disabled", reason="motor not installed")
            return False

        try:
            self._replica_client = AsyncIOMotorClient(
                self._replica_uri,
                maxPoolSize=3,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=3000,
            )
            self._replica_db = self._replica_client[cfg.mongo.db_name]

            # Verify connectivity
            await self._replica_client.admin.command("ping", serverSelectionTimeoutMS=3000)
            self._connected = True

            log.info(
                "dual_write_connected",
                replica_uri_prefix=self._replica_uri[:30] + "...",
                db=cfg.mongo.db_name,
            )
            return True

        except Exception as exc:
            self._connected = False
            log.warning(
                "dual_write_connect_failed",
                error=str(exc),
                hint="Primary continues — replica writes will be skipped",
            )
            return False

    async def close(self) -> None:
        """Close the replica MongoDB client."""
        if self._replica_client:
            self._replica_client.close()
        self._connected = False
        self._replica_client = None
        self._replica_db = None
        log.info("dual_write_closed")

    # ═════════════════════════════════════════════════════════════════════════
    # Dual-Write Operations
    # ═════════════════════════════════════════════════════════════════════════

    async def dual_insert_one(self, collection: str, doc: dict) -> None:
        """
        Insert a document into both primary and replica.

        Primary insert is handled by the caller (the repository).
        This method only handles the replica side. Call this AFTER
        the primary insert succeeds.
        """
        self._write_count += 1
        if not self._connected or self._replica_db is None:
            return

        try:
            await self._replica_db[collection].insert_one(doc)
            self._replica_success_count += 1
        except Exception as exc:
            self._replica_fail_count += 1
            log.warning(
                "dual_write_replica_insert_failed",
                collection=collection,
                error=str(exc),
            )

    async def dual_update_one(
        self,
        collection: str,
        filter_dict: dict,
        update: dict,
        upsert: bool = False,
    ) -> None:
        """
        Update a document in both primary and replica.

        Primary update is handled by the caller. This handles the replica.
        """
        self._write_count += 1
        if not self._connected or self._replica_db is None:
            return

        try:
            await self._replica_db[collection].update_one(
                filter_dict, update, upsert=upsert
            )
            self._replica_success_count += 1
        except Exception as exc:
            self._replica_fail_count += 1
            log.warning(
                "dual_write_replica_update_failed",
                collection=collection,
                error=str(exc),
            )

    async def dual_delete_one(self, collection: str, filter_dict: dict) -> None:
        """
        Delete a document from both primary and replica.
        """
        self._write_count += 1
        if not self._connected or self._replica_db is None:
            return

        try:
            await self._replica_db[collection].delete_one(filter_dict)
            self._replica_success_count += 1
        except Exception as exc:
            self._replica_fail_count += 1
            log.warning(
                "dual_write_replica_delete_failed",
                collection=collection,
                error=str(exc),
            )

    async def full_sync(self, primary_db) -> Dict[str, int]:
        """
        Perform a full collection-by-collection sync from primary to replica.

        Used for initial setup or after a replica recovery.
        Returns a dict of {collection: docs_synced}.
        """
        if not self._connected or self._replica_db is None:
            return {}

        results = {}
        collections_to_sync = [
            "signal_archive", "trade_events", "subscribers",
            "trading_accounts", "training_data", "signal_state",
            "virtual_account_events", "virtual_account_snapshots",
            "virtual_account_metrics", "virtual_account_config",
            "candles", "trade_proximity",
            "subscriber_events", "payments", "signal_deliveries",
            "terms_acceptance", "admin_actions", "messages_sent",
        ]

        for col_name in collections_to_sync:
            try:
                # Drop replica collection and re-populate from primary
                await self._replica_db[col_name].drop()

                docs = await primary_db[col_name].find({}).to_list(length=None)
                if docs:
                    await self._replica_db[col_name].insert_many(docs)

                results[col_name] = len(docs) if docs else 0
                log.info(
                    "dual_write_sync_collection",
                    collection=col_name,
                    docs_synced=len(docs) if docs else 0,
                )
            except Exception as exc:
                log.warning(
                    "dual_write_sync_collection_failed",
                    collection=col_name,
                    error=str(exc),
                )
                results[col_name] = -1

        log.info("dual_write_full_sync_complete", results=results)
        return results

    # ═════════════════════════════════════════════════════════════════════════
    # Status
    # ═════════════════════════════════════════════════════════════════════════

    @property
    def status(self) -> dict:
        """Return replication status for health checks."""
        return {
            "connected": self._connected,
            "replica_uri_set": bool(self._replica_uri),
            "total_writes": self._write_count,
            "replica_successes": self._replica_success_count,
            "replica_failures": self._replica_fail_count,
            "replication_rate": (
                round(self._replica_success_count / max(self._write_count, 1) * 100, 1)
                if self._write_count > 0 else 0.0
            ),
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

dual_write_manager = DualWriteManager()
