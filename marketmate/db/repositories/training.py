"""
marketmate/db/repositories/training.py
───────────────────────────────────────
TrainingRepository — MongoDB-only ML training data with gate dedup.

Migrated from db/training.py. Every gate run is recorded as an ML-ready
document, with outcome written back when the trade closes.

No SQLite. MongoDB is the sole source of truth.

Rejection deduplication:
  G6/G7/G8 rejections for the same (pair, gate, feature-hash) within 30 min
  are silently dropped.  G1–G5 rejections are always stored (varied features).
  G1_SESSION is never stored (no training value — happens ~14 h/day).
"""

from __future__ import annotations

import hashlib
import json
import uuid as _uuid
from datetime import datetime, time, timezone
from typing import Any, Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.db.core import mongo_manager

log = get_logger("db.repositories.training")

try:
    from bson import ObjectId as _ObjectId
    _BSON_AVAILABLE = True
except ImportError:
    _BSON_AVAILABLE = False
    _ObjectId = None  # type: ignore[assignment,misc]

# Gates whose rejections are deduplicated to prevent DB flooding
_DEDUP_GATES = {"G6_ZONE", "G7_LTF_CONFIRM", "G8_RR"}
# In-memory cache: { pair: { gate: (feature_hash, timestamp) } }
_recent_rejects: dict[str, dict[str, tuple[str, datetime]]] = {}
_DEDUP_WINDOW_SECONDS = 1800  # 30 minutes


class TrainingRepository:
    """
    MongoDB-only repository for ML training data.

    Provides gate rejection logging, signal logging, execution/outcome
    recording, and ML data fetching. Includes in-memory rejection
    deduplication for G6/G7/G8 gates.
    """

    def __init__(self) -> None:
        self._manager = mongo_manager

    async def _col(self):
        """Return training_data collection or None. Always safe."""
        try:
            db = await self._manager.get_db()
            return db["training_data"] if db is not None else None
        except Exception as exc:
            log.warning("training_col_unavailable", error=str(exc))
            return None

    # ═════════════════════════════════════════════════════════════════════════
    # Session label
    # ═════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _session_label() -> str:
        now = datetime.now(timezone.utc).time()

        def _t(s: str) -> time:
            h, m = s.split(":")
            return time(int(h), int(m))

        if _t(cfg.strategy.london_open) <= now < _t(cfg.strategy.london_close):
            return "london"
        if _t(cfg.strategy.ny_open) <= now < _t(cfg.strategy.ny_close):
            return "ny"
        if now < time(7, 0):
            return "asia"
        return "off"

    # ═════════════════════════════════════════════════════════════════════════
    # Feature encoder
    # ═════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _encode_features(gate_trace: list[dict], rr: float) -> dict:
        gate_status = {e["gate"]: e["status"] for e in gate_trace}
        gate_values = {e["gate"]: e.get("values", {}) for e in gate_trace}

        bias_raw     = gate_values.get("G4_HTF_BIAS", {}).get("bias", "")
        htf_bias     = 1 if bias_raw == "bullish" else (-1 if bias_raw == "bearish" else 0)

        sweep_vals   = gate_values.get("G5_SWEEP", {})
        sweep_pass   = 1 if gate_status.get("G5_SWEEP") == "pass" else 0
        sweep_strong = 1 if sweep_vals.get("strength") == "strong" else 0
        sweep_close  = 1 if sweep_vals.get("close_inside") else 0

        zone_vals    = gate_values.get("G6_ZONE", {})
        zone_pass    = 1 if gate_status.get("G6_ZONE") == "pass" else 0
        zone_type    = zone_vals.get("zone_type", "")
        ob_present   = 1 if zone_type == "order_block" else 0
        fvg_present  = 1 if zone_type == "fvg" else 0

        ltf_vals     = gate_values.get("G7_LTF_CONFIRM", {})
        ltf_pass     = 1 if gate_status.get("G7_LTF_CONFIRM") == "pass" else 0
        confirm_type = ltf_vals.get("signal_type", "")
        choch        = 1 if confirm_type == "CHoCH" else 0
        bos          = 1 if confirm_type == "BOS" else 0

        session = TrainingRepository._session_label()

        return {
            "htf_bias":           htf_bias,
            "sweep":              sweep_pass,
            "sweep_strong":       sweep_strong,
            "sweep_close_inside": sweep_close,
            "ob":                 ob_present,
            "fvg":                fvg_present,
            "zone_present":       zone_pass,
            "ltf_confirmed":      ltf_pass,
            "choch":              choch,
            "bos":                bos,
            "rr":                 round(rr, 4),
            "session_london":     1 if session == "london" else 0,
            "session_ny":         1 if session == "ny" else 0,
            "session_asia":       1 if session == "asia" else 0,
        }

    @staticmethod
    def _feature_hash(features: dict) -> str:
        """Stable hash of a feature dict for rejection deduplication."""
        serialised = json.dumps(features, sort_keys=True)
        return hashlib.md5(serialised.encode()).hexdigest()[:12]

    # ═════════════════════════════════════════════════════════════════════════
    # Document builder
    # ═════════════════════════════════════════════════════════════════════════

    def _build_document(
        self,
        pair:        str,
        gate_trace:  list[dict],
        passed:      bool,
        failed_gate: Optional[str],
        rr:          float,
        entry_zone:  Optional[dict] = None,
        signal_id:   Optional[str]  = None,
    ) -> dict:
        now      = datetime.now(timezone.utc)
        session  = self._session_label()
        features = self._encode_features(gate_trace, rr)

        gate_values: dict[str, Any] = {
            e["gate"]: e.get("values", {}) for e in gate_trace
        }
        bias_raw = gate_values.get("G4_HTF_BIAS", {}).get("bias", None)

        return {
            "signal_id":    signal_id or str(_uuid.uuid4()),
            "pair":         pair,
            "timestamp":    now.isoformat(),
            "timestamp_dt": now,
            "session":      session,
            "htf_bias": bias_raw,
            "liquidity_sweep": {
                "present":      features["sweep"] == 1,
                "direction":    gate_values.get("G5_SWEEP", {}).get("type"),
                "strength":     gate_values.get("G5_SWEEP", {}).get("strength"),
                "close_inside": bool(features["sweep_close_inside"]),
            },
            "fvg_present":  bool(features["fvg"]),
            "ob_present":   bool(features["ob"]),
            "entry_zone":   entry_zone,
            "rr_offered":   round(rr, 4),
            "decision":      "TRADE" if passed else "SKIP",
            "failed_gate":   failed_gate,
            "signal_status": "OPEN" if passed else "SKIP",
            "features":  features,
            "execution": None,
            "outcome":   None,
            "schema_version": 2,
        }

    # ═════════════════════════════════════════════════════════════════════════
    # Deduplication helpers
    # ═════════════════════════════════════════════════════════════════════════

    @staticmethod
    def _should_skip_rejection(pair: str, gate: str, feature_hash: str) -> bool:
        """Return True if this rejection is a duplicate within the dedup window."""
        if gate not in _DEDUP_GATES:
            return False

        now = datetime.now(timezone.utc)
        pair_cache = _recent_rejects.get(pair, {})

        # Prune stale entries
        stale = [
            g for g, (_, ts) in pair_cache.items()
            if (now - ts).total_seconds() > _DEDUP_WINDOW_SECONDS
        ]
        for g in stale:
            del pair_cache[g]

        if gate in pair_cache:
            prev_hash, _ = pair_cache[gate]
            if prev_hash == feature_hash:
                return True

        # Record this rejection
        pair_cache[gate] = (feature_hash, now)
        _recent_rejects[pair] = pair_cache
        return False

    # ═════════════════════════════════════════════════════════════════════════
    # Public write API
    # ═════════════════════════════════════════════════════════════════════════

    async def log_gate_rejection(
        self,
        pair:        str,
        gate_trace:  list[dict],
        failed_gate: Optional[str],
        rr:          float,
    ) -> Optional[str]:
        """
        Record a gate rejection in training_data.

        G1_SESSION is never stored. G6/G7/G8 identical rejections within
        30 min are deduplicated. G1–G5 are always stored.

        Returns MongoDB doc_id string, or None if not stored.
        """
        if failed_gate == "G1_SESSION":
            log.debug("rejection_skipped", pair=pair, gate=failed_gate,
                      reason="session_outside_hours")
            return None

        col = await self._col()
        if col is None:
            return None

        try:
            features = self._encode_features(gate_trace, rr)
            fhash    = self._feature_hash(features)

            if failed_gate and self._should_skip_rejection(pair, failed_gate, fhash):
                log.debug("rejection_deduped", pair=pair, gate=failed_gate)
                return None

            doc    = self._build_document(pair=pair, gate_trace=gate_trace,
                                          passed=False, failed_gate=failed_gate, rr=rr)
            result = await col.insert_one(doc)
            return str(result.inserted_id)

        except Exception as exc:
            log.error("log_gate_rejection_failed", pair=pair, error=str(exc))
            return None

    async def log_signal(
        self,
        signal,
        gate_trace:  list[dict],
        rr:          float,
        entry_zone:  Optional[dict] = None,
    ) -> Optional[str]:
        """
        Record a fully-passed signal in training_data.
        Returns MongoDB doc_id for linking outcomes back to this document.
        """
        col = await self._col()
        if col is None:
            return None
        try:
            doc    = self._build_document(
                pair=signal.symbol, gate_trace=gate_trace,
                passed=True, failed_gate=None, rr=rr,
                entry_zone=entry_zone, signal_id=signal.id,
            )
            result = await col.insert_one(doc)
            doc_id = str(result.inserted_id)
            log.debug("training_signal_logged", doc_id=doc_id, pair=signal.symbol)
            return doc_id
        except Exception as exc:
            log.error("log_signal_failed", pair=getattr(signal, "symbol", "?"),
                      error=str(exc))
            return None

    async def log_execution(
        self,
        doc_id:           str,
        mt5_ticket:       Optional[int],
        entry_price:      float,
        stop_loss:        float,
        take_profits:     list[float],
        execution_status: str,
    ) -> None:
        if not _BSON_AVAILABLE or not doc_id:
            return
        col = await self._col()
        if col is None:
            return
        try:
            await col.update_one(
                {"_id": _ObjectId(doc_id)},
                {"$set": {"execution": {
                    "mt5_ticket":       mt5_ticket,
                    "entry_price":      entry_price,
                    "stop_loss":        stop_loss,
                    "take_profits":     take_profits,
                    "execution_status": execution_status,
                    "executed_at":      datetime.now(timezone.utc).isoformat(),
                }}},
            )
        except Exception as exc:
            log.error("log_execution_failed", doc_id=doc_id, error=str(exc))

    async def log_status_update(self, doc_id: str, status: str) -> None:
        if not _BSON_AVAILABLE or not doc_id:
            return
        col = await self._col()
        if col is None:
            return
        try:
            await col.update_one(
                {"_id": _ObjectId(doc_id)},
                {"$set": {
                    "signal_status":     status,
                    "status_updated_at": datetime.now(timezone.utc).isoformat(),
                }},
            )
            log.debug("training_status_updated", doc_id=doc_id, status=status)
        except Exception as exc:
            log.error("log_status_update_failed", doc_id=doc_id, error=str(exc))

    async def log_outcome(
        self,
        doc_id:           str,
        outcome:          str,
        rr_realized:      float,
        hit_tp:           Optional[str] = None,
        duration_minutes: Optional[int] = None,
    ) -> None:
        if not _BSON_AVAILABLE or not doc_id:
            return
        col = await self._col()
        if col is None:
            return
        try:
            await col.update_one(
                {"_id": _ObjectId(doc_id)},
                {"$set": {
                    "signal_status": "CLOSED",
                    "outcome": {
                        "result":           outcome,
                        "rr_realized":      round(rr_realized, 4),
                        "hit_tp":           hit_tp,
                        "duration_minutes": duration_minutes,
                        "closed_at":        datetime.now(timezone.utc).isoformat(),
                    },
                }},
            )
            log.debug("training_outcome_recorded", doc_id=doc_id, outcome=outcome)
        except Exception as exc:
            log.error("log_outcome_failed", doc_id=doc_id, error=str(exc))

    # ═════════════════════════════════════════════════════════════════════════
    # ML data fetch
    # ═════════════════════════════════════════════════════════════════════════

    async def get_valid_training_data(self, limit: int = 1000) -> list[dict]:
        """Return ML-ready documents: TRADE decision, rr_offered > 0, outcome resolved."""
        col = await self._col()
        if col is None:
            return []
        try:
            cursor = col.find(
                {"decision": "TRADE", "rr_offered": {"$gt": 0}, "outcome": {"$ne": None}},
                {"_id": 0},
            ).sort("timestamp_dt", -1).limit(limit)
            results = await cursor.to_list(length=limit)
            log.info("valid_training_data_fetched", count=len(results))
            return results
        except Exception as exc:
            log.error("get_valid_training_data_failed", error=str(exc))
            return []

    # ═════════════════════════════════════════════════════════════════════════
    # Indexes
    # ═════════════════════════════════════════════════════════════════════════

    async def ensure_indexes(self) -> None:
        """Create indexes on training_data. Called from connect_all()."""
        col = await self._col()
        if col is None:
            return

        from pymongo import ASCENDING, DESCENDING

        # Drop legacy sparse index that caused IndexKeySpecsConflict
        try:
            await col.drop_index("signal_id_1")
            log.info("legacy_signal_id_index_dropped")
        except Exception:
            pass

        specs = [
            dict(keys=[("pair",          ASCENDING)]),
            dict(keys=[("timestamp_dt",  DESCENDING)]),
            dict(keys=[("decision",      ASCENDING)]),
            dict(keys=[("failed_gate",   ASCENDING)]),
            dict(keys=[("signal_status", ASCENDING)]),
            dict(keys=[("signal_id",     ASCENDING)], unique=True),
            dict(
                keys=[("timestamp_dt", ASCENDING)],
                expireAfterSeconds=365 * 24 * 3600,
                name="ttl_1year",
            ),
        ]
        for spec in specs:
            keys = spec.pop("keys")
            try:
                await col.create_index(keys, **spec)
            except Exception as exc:
                log.warning("training_index_warning", keys=str(keys), error=str(exc))

        log.debug("training_indexes_ensured")


# ─── Module-level singleton ────────────────────────────────────────────────────
# Backward-compatible alias used by:
#   from marketmate.db.repositories.training import training_logger
# Also re-exported via the analytics/training_logger.py shim.

training_logger = TrainingRepository()
