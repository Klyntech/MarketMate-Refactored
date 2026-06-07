"""
marketmate/analytics/proximity.py
─────────────────────────────────
ProximityRepo — MongoDB-only per-trade price extremes.

Migrated from db/proximity.py. Fast atomic persistence for MFE/MAE
computation using MongoDB's $max/$min operators.

Collection: trade_proximity
One tiny document per open trade (~200 bytes). Never reads before writing —
MongoDB's $max/$min operators enforce the extremum atomically.

Lifecycle:
  init_proximity()  → called when a trade opens
  update_proximity() → called on every price tick (~1/sec)
  flush_proximity()  → called when a trade closes; returns final MFE%/MAE%
  get_all_open_proximity() → for monitor restart recovery
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.db.core import mongo_manager

log = get_logger("analytics.proximity")


class ProximityRepo:
    """
    MongoDB-only repository for per-trade price extremes.

    Uses MongoDB's $max/$min operators for atomic extremum updates.
    No read-before-write. ~20–50 ms round-trip to Atlas.
    """

    def __init__(self) -> None:
        self._manager = mongo_manager

    # ═════════════════════════════════════════════════════════════════════════
    # Writes
    # ═════════════════════════════════════════════════════════════════════════

    async def init_proximity(
        self,
        signal_id: str,
        symbol: str,
        direction: str,
        entry: float,
        sl: float,
        tp1: float,
        tp2: float,
        tp3: float = 0.0,
    ) -> None:
        """
        Create (or reset) the proximity document for an open trade.
        Safe to call multiple times — upserts.
        """
        try:
            db = await self._manager.get_db()
            if db is None:
                return

            await db["trade_proximity"].update_one(
                {"signal_id": signal_id},
                {
                    "$setOnInsert": {
                        "signal_id": signal_id,
                        "symbol":    symbol,
                        "direction": direction,
                        "entry":     entry,
                        "sl":        sl,
                        "tp1":       tp1,
                        "tp2":       tp2,
                        "tp3":       tp3 if tp3 else None,
                        "highest_price": entry,
                        "lowest_price":  entry,
                        "created_at":    datetime.now(timezone.utc),
                        "updated_at":    datetime.now(timezone.utc),
                    }
                },
                upsert=True,
            )
            log.debug("proximity_initialised", signal_id=signal_id, symbol=symbol,
                      direction=direction, entry=entry)
        except Exception as exc:
            log.warning("proximity_init_failed", signal_id=signal_id, error=str(exc))

    async def update_proximity(
        self,
        signal_id: str,
        price: float,
        direction: str,
    ) -> None:
        """
        Atomically update the extreme price for one open trade.

        For BUY  trades: $max on highest_price (track the best price reached).
        For SELL trades: $min on lowest_price  (track the best price reached).
        """
        try:
            db = await self._manager.get_db()
            if db is None:
                return

            if direction == "BUY":
                update_op = {
                    "$max": {"highest_price": price},
                    "$set": {"updated_at": datetime.now(timezone.utc)},
                }
            else:  # SELL
                update_op = {
                    "$min": {"lowest_price": price},
                    "$set": {"updated_at": datetime.now(timezone.utc)},
                }

            await db["trade_proximity"].update_one(
                {"signal_id": signal_id},
                update_op,
            )
        except Exception as exc:
            log.warning("proximity_update_failed", signal_id=signal_id,
                        price=price, error=str(exc))

    async def flush_proximity(self, signal_id: str) -> Optional[dict]:
        """
        Read the final proximity document, compute MFE%/MAE%, delete the
        document, and return a proximity block ready to write into signal_archive.

        Returns None if the document doesn't exist.
        """
        try:
            db = await self._manager.get_db()
            if db is None:
                return None

            doc = await db["trade_proximity"].find_one_and_delete(
                {"signal_id": signal_id}
            )
            if doc is None:
                log.warning("proximity_doc_not_found", signal_id=signal_id)
                return None

            entry    = doc["entry"]
            sl       = doc["sl"]
            tp2_val  = doc["tp2"]
            tp1_val  = doc.get("tp1", tp2_val)  # fallback to tp2 if tp1 missing
            highest  = doc["highest_price"]
            lowest   = doc["lowest_price"]
            direction = doc["direction"]

            # ── MFE% / MAE% ────────────────────────────────────────────────
            if direction == "BUY":
                tp_range = tp2_val - entry
                sl_range = entry - sl
                favorable_move  = highest - entry
                adverse_move    = entry - lowest
            else:  # SELL
                tp_range = entry - tp2_val
                sl_range = sl - entry
                favorable_move  = entry - lowest
                adverse_move    = highest - entry

            mfe_pct = round((favorable_move / tp_range * 100), 1) if tp_range > 0 else 0.0
            mae_pct = round((adverse_move   / sl_range * 100), 1) if sl_range > 0 else 0.0

            # Clamp to [0, 110]
            mfe_pct = max(0.0, min(110.0, mfe_pct))
            mae_pct = max(0.0, min(110.0, mae_pct))

            tp_threshold = getattr(cfg.strategy, "proximity_tp_threshold_pct", 80.0)
            sl_threshold = getattr(cfg.strategy, "proximity_sl_threshold_pct", 80.0)

            proximity = {
                "highest_price":  round(highest, 4),
                "lowest_price":   round(lowest, 4),
                "mfe_pct":        mfe_pct,
                "mae_pct":        mae_pct,
                "approached_tp":  mfe_pct >= tp_threshold,
                "approached_sl":  mae_pct >= sl_threshold,
            }

            log.info("proximity_flushed", signal_id=signal_id,
                     mfe_pct=mfe_pct, mae_pct=mae_pct,
                     approached_tp=proximity["approached_tp"],
                     approached_sl=proximity["approached_sl"])
            return proximity

        except Exception as exc:
            log.warning("proximity_flush_failed", signal_id=signal_id, error=str(exc))
            return None

    # ═════════════════════════════════════════════════════════════════════════
    # Reads
    # ═════════════════════════════════════════════════════════════════════════

    async def get_all_open_proximity(self) -> list[dict]:
        """
        Return all proximity documents (used on monitor startup to re-seed
        the in-memory dict from any trades that were open before a restart).
        """
        try:
            db = await self._manager.get_db()
            if db is None:
                return []
            cursor = db["trade_proximity"].find({})
            return await cursor.to_list(length=None)
        except Exception as exc:
            log.warning("proximity_list_failed", error=str(exc))
            return []

    # ═════════════════════════════════════════════════════════════════════════
    # Indexes
    # ═════════════════════════════════════════════════════════════════════════

    async def ensure_indexes(self) -> None:
        """
        Create indexes on trade_proximity.
        signal_id unique — enforces one-document-per-open-trade.
        No TTL: documents are explicitly deleted by flush_proximity().
        """
        try:
            db = await self._manager.get_db()
            if db is None:
                return
            from pymongo import ASCENDING
            await db["trade_proximity"].create_index(
                [("signal_id", ASCENDING)],
                unique=True,
                name="signal_id_unique",
            )
            log.info("proximity_indexes_ensured")
        except Exception as exc:
            log.error("proximity_ensure_indexes_failed", error=str(exc))
