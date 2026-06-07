"""
marketmate/mate_ops/observation_history.py
──────────────────────────────────────────
Persistent observation history with pattern matching — MATE-Ops Phase 2.

Phase 1 (read-only, Level 0 authority) identified "Memory Depth" as the single
biggest gap in the Max/Mini assessment, scoring **2/10** against a target of 8.
Without historical memory, every observation cycle started from scratch — the
system could not recognise recurring failures, detect correlated outages, or
spot degradation trends across cycles.

This module closes that gap by providing:

  1. **Persistent in-memory storage** — a bounded ``deque`` (default 10 000
     records) that retains observation history across cycles, giving the
     Analyse and Plan stages longitudinal context they never had before.

  2. **Pattern detection** — four pattern types are identified from the
     accumulated history:
       a. **Recurring failures**  — same source+status="error" appearing >3 times
       b. **Correlated failures**  — services that fail together (within 5 min)
       c. **Degradation trends**   — status progression ok → warn → error
       d. **Recovery patterns**    — status progression error → warn → ok

  3. **Semantic search** — when a ``MemoryStore`` (ChromaDB-backed) is
     provided, ``find_similar()`` uses vector similarity for high-quality
     semantic matching.  Without it, keyword-based matching is used as a
     zero-dependency fallback.

  4. **Lifecycle management** — ``prune()`` and ``clear()`` keep the store
     from growing unbounded; ``get_service_timeline()`` provides per-service
     chronological views for the Verify stage.

Pipeline position: this module sits between the **Observe** and **Analyze**
stages, providing the memory layer that the Analyze stage queries for
historical context and pattern insights.

Phase 2 authority level is 1 (safe ops: restart, cache clear, notify), so
pattern matches produced here can inform automated remediation through the
PermissionGate — but only for approved safe actions.
"""

from __future__ import annotations

import uuid
from collections import Counter, defaultdict, deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional, Set

from marketmate.core.logger import get_logger
from marketmate.mate_ops.observer import Observation

log = get_logger("mate_ops.observation_history")

# Optional vector store — graceful fallback when ChromaDB is not installed
try:
    from marketmate.memory.vector_store import MemoryStore
    _VECTOR_STORE_AVAILABLE = True
except ImportError:
    _VECTOR_STORE_AVAILABLE = False


# ─── Data Models ──────────────────────────────────────────────────────────────

@dataclass
class ObservationRecord:
    """
    A single persisted observation with optional analysis context.

    Enriches the raw ``Observation`` from the Observe stage with a unique
    identifier, cycle linkage, and an optional analysis summary from the
    Analyse stage.

    Attributes:
        id:               Unique record identifier (UUID4).
        source:           The service or component observed (e.g. "api", "redis").
        status:           Health status — "ok", "warn", or "error".
        message:          Human-readable description of the observation.
        timestamp:        ISO 8601 timestamp of when the observation was taken.
        details:          Additional structured data (latency, error codes, etc.).
        cycle_id:         Identifier linking records from the same Observe cycle.
        analysis_summary: Optional summary from the Analyse stage for this record.
    """

    id: str
    source: str
    status: str  # "ok", "warn", "error"
    message: str
    timestamp: str
    details: Dict[str, Any] = field(default_factory=dict)
    cycle_id: str = ""
    analysis_summary: str = ""


@dataclass
class PatternMatch:
    """
    A detected pattern in the observation history.

    Represents a recurring behaviour identified by ``detect_patterns()``,
    including the pattern type, a human-readable description, confidence
    score, and links to the records that contributed to the match.

    Attributes:
        pattern_type:        One of "recurring_failure", "correlated_failure",
                             "degradation_trend", or "recovery_pattern".
        pattern_description: Human-readable explanation of the pattern.
        confidence:          0.0–1.0 confidence score for the match.
        similar_events:      Number of historical events matching this pattern.
        first_seen:          ISO 8601 timestamp of the earliest matching event.
        last_seen:           ISO 8601 timestamp of the most recent matching event.
        related_records:     IDs of the ``ObservationRecord`` entries that
                             contribute to this pattern.
    """

    pattern_type: str
    pattern_description: str
    confidence: float
    similar_events: int
    first_seen: str
    last_seen: str
    related_records: List[str] = field(default_factory=list)


# ─── Helpers ──────────────────────────────────────────────────────────────────

def _now_iso() -> str:
    """Current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _parse_timestamp(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp string into a ``datetime`` object.

    Falls back to the current time if parsing fails, so that comparison
    logic never crashes on malformed timestamps.

    Args:
        ts: ISO 8601 timestamp string.

    Returns:
        A timezone-aware ``datetime`` in UTC.
    """
    try:
        dt = datetime.fromisoformat(ts)
        # Ensure timezone-aware
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        return datetime.now(timezone.utc)


def _keyword_similarity(query: str, text: str) -> float:
    """Compute a simple keyword-overlap similarity score.

    Tokenises both strings on whitespace and computes the Jaccard-like
    ratio of shared tokens to total unique tokens.  Used as the fallback
    similarity measure when no vector store is available.

    Args:
        query: The search query string.
        text:  The text to compare against.

    Returns:
        A float between 0.0 and 1.0.
    """
    query_tokens = set(query.lower().split())
    text_tokens = set(text.lower().split())
    if not query_tokens or not text_tokens:
        return 0.0
    overlap = query_tokens & text_tokens
    union = query_tokens | text_tokens
    return len(overlap) / len(union)


# ─── Status severity ordering ─────────────────────────────────────────────────

_STATUS_ORDER: Dict[str, int] = {"ok": 0, "warn": 1, "error": 2}


# ─── Observation History ─────────────────────────────────────────────────────

class ObservationHistory:
    """
    Persistent observation history with pattern matching for MATE-Ops Phase 2.

    Stores ``ObservationRecord`` entries in a bounded ``deque`` and provides
    query, search, and pattern-detection capabilities.  Optionally backed by
    a ``MemoryStore`` (ChromaDB) for semantic similarity search.

    Typical usage::

        history = ObservationHistory(max_records=10000)

        # In the Observe stage — persist observations
        history.store(observations, cycle_id="cycle-42")

        # In the Analyse stage — query for context
        timeline = history.get_service_timeline("redis", hours=6)

        # Detect recurring patterns
        patterns = history.detect_patterns()

        # Find similar past incidents
        similar = history.find_similar("redis connection timeout", n=5)

    Args:
        max_records:   Maximum number of records to retain in the deque.
                       Oldest records are evicted when the limit is exceeded.
        vector_store:  Optional ``MemoryStore`` for semantic search.  When
                       provided, records are also indexed in the vector store
                       for high-quality ``find_similar()`` results.
    """

    def __init__(
        self,
        max_records: int = 10000,
        vector_store: Optional[MemoryStore] = None,
    ) -> None:
        self._max_records = max_records
        self._vector_store = vector_store
        self._records: deque[ObservationRecord] = deque(maxlen=max_records)
        # Index for fast lookup by record ID (stores IDs currently in the deque)
        self._id_set: Set[str] = set()

        log.info(
            "observation_history_init",
            max_records=max_records,
            vector_store_enabled=vector_store is not None,
        )

    # ── Store ──────────────────────────────────────────────────────────────

    def store(
        self,
        observations: List[Observation],
        cycle_id: str = "",
        analysis: str = "",
    ) -> int:
        """Store a batch of observations and return the count stored.

        Each ``Observation`` is converted to an ``ObservationRecord`` with a
        unique ID, the provided cycle ID, and an optional analysis summary.
        Records are appended to the in-memory deque (evicting the oldest if
        at capacity) and, if a vector store is available, indexed for
        semantic search.

        Args:
            observations: List of ``Observation`` objects from the Observe stage.
            cycle_id:     Identifier linking records from the same cycle.
            analysis:     Optional analysis summary applied to all records
                          in this batch.

        Returns:
            The number of observations stored.
        """
        if not observations:
            return 0

        stored = 0
        for obs in observations:
            record_id = str(uuid.uuid4())
            record = ObservationRecord(
                id=record_id,
                source=obs.source,
                status=obs.status,
                message=obs.message,
                timestamp=obs.timestamp,
                details=dict(obs.details) if obs.details else {},
                cycle_id=cycle_id,
                analysis_summary=analysis,
            )

            # If the deque is at capacity, the oldest record will be evicted.
            # Remove its ID from the index set *before* appending.
            if len(self._records) >= self._max_records:
                evicted = self._records[0]
                self._id_set.discard(evicted.id)

            self._records.append(record)
            self._id_set.add(record_id)
            stored += 1

            # Index in vector store for semantic search (best-effort)
            if self._vector_store is not None:
                try:
                    import asyncio

                    obs_dict = {
                        "source": record.source,
                        "status": record.status,
                        "message": record.message,
                        "details": record.details,
                        "timestamp": record.timestamp,
                    }
                    # If there's a running event loop, schedule the add;
                    # otherwise run it synchronously (e.g. in tests).
                    try:
                        loop = asyncio.get_running_loop()
                        loop.create_task(
                            self._vector_store.add_observation(obs_dict)
                        )
                    except RuntimeError:
                        # No running loop — run synchronously
                        asyncio.run(
                            self._vector_store.add_observation(obs_dict)
                        )
                except Exception as exc:
                    log.warning(
                        "observation_history_vector_store_add_failed",
                        record_id=record_id,
                        error=str(exc),
                    )

        log.info(
            "observation_history_store",
            stored=stored,
            cycle_id=cycle_id,
            total_records=len(self._records),
        )
        return stored

    # ── Query ──────────────────────────────────────────────────────────────

    def query(
        self,
        service: str = "",
        status: str = "",
        since: str = "",
        limit: int = 100,
    ) -> List[ObservationRecord]:
        """Query observation history by service, status, and/or time.

        All filters are optional — omitting a filter means "match everything"
        for that dimension.  Results are returned in reverse chronological
        order (most recent first).

        Args:
            service: Filter by source/service name (e.g. "redis").
            status:  Filter by status ("ok", "warn", "error").
            since:   ISO 8601 timestamp — only return records at or after
                     this time.
            limit:   Maximum number of records to return.

        Returns:
            List of matching ``ObservationRecord`` entries, newest first.
        """
        since_dt = _parse_timestamp(since) if since else None
        results: List[ObservationRecord] = []

        # Iterate in reverse (newest first) for natural ordering
        for record in reversed(self._records):
            if service and record.source != service:
                continue
            if status and record.status != status:
                continue
            if since_dt:
                record_dt = _parse_timestamp(record.timestamp)
                if record_dt < since_dt:
                    continue
            results.append(record)
            if len(results) >= limit:
                break

        return results

    # ── Find Similar ───────────────────────────────────────────────────────

    def find_similar(
        self,
        description: str,
        n: int = 5,
    ) -> List[ObservationRecord]:
        """Find past observations similar to the given description.

        When a ``MemoryStore`` (ChromaDB) is available, uses semantic vector
        search for high-quality similarity matching.  Otherwise falls back
        to keyword-overlap scoring against each record's source, message,
        and status fields.

        Args:
            description: The text to match against historical observations.
            n:           Maximum number of results to return.

        Returns:
            List of the *n* most similar ``ObservationRecord`` entries,
            ordered by descending similarity.
        """
        if not description or not self._records:
            return []

        # ── Vector store path ───────────────────────────────────────────
        if self._vector_store is not None:
            try:
                import asyncio

                try:
                    loop = asyncio.get_running_loop()
                    # We're inside an async context — schedule and wait
                    import concurrent.futures
                    with concurrent.futures.ThreadPoolExecutor() as pool:
                        future = pool.submit(
                            asyncio.run,
                            self._vector_store.search_observations(
                                query=description, n_results=n
                            ),
                        )
                        vs_results = future.result(timeout=10)
                except RuntimeError:
                    vs_results = asyncio.run(
                        self._vector_store.search_observations(
                            query=description, n_results=n
                        )
                    )

                # Map vector-store results back to our records
                matched: List[ObservationRecord] = []
                for vs_doc in vs_results:
                    meta = vs_doc.get("metadata", {})
                    source = meta.get("source", "")
                    created_at = meta.get("created_at", "")
                    # Find the corresponding record by matching metadata
                    for rec in reversed(self._records):
                        if (
                            rec.source == source
                            and rec.timestamp == created_at
                            and rec.id not in {r.id for r in matched}
                        ):
                            matched.append(rec)
                            break
                    if len(matched) >= n:
                        break

                if matched:
                    return matched[:n]
            except Exception as exc:
                log.warning(
                    "observation_history_find_similar_vector_fallback",
                    error=str(exc),
                    hint="Falling back to keyword matching",
                )

        # ── Keyword fallback ────────────────────────────────────────────
        scored: List[tuple[float, ObservationRecord]] = []
        for record in self._records:
            text = f"{record.source} {record.status} {record.message}"
            score = _keyword_similarity(description, text)
            scored.append((score, record))

        scored.sort(key=lambda pair: pair[0], reverse=True)
        return [record for _score, record in scored[:n]]

    # ── Detect Patterns ───────────────────────────────────────────────────

    def detect_patterns(self) -> List[PatternMatch]:
        """Analyse observation history for recurring patterns.

        Scans all records currently in the deque and identifies four pattern
        types:

          a. **Recurring failures** — same source+status="error" appearing
             more than 3 times.  Confidence scales with occurrence count.
          b. **Correlated failures** — distinct services that both report
             "error" within a 5-minute window.  Confidence scales with
             co-occurrence count.
          c. **Degradation trends** — a service whose status progresses
             from "ok" through "warn" to "error" over time.
          d. **Recovery patterns** — a service whose status progresses
             from "error" through "warn" to "ok" over time.

        Returns:
            A list of ``PatternMatch`` objects, one per detected pattern.
        """
        patterns: List[PatternMatch] = []

        if len(self._records) < 2:
            return patterns

        patterns.extend(self._detect_recurring_failures())
        patterns.extend(self._detect_correlated_failures())
        patterns.extend(self._detect_degradation_trends())
        patterns.extend(self._detect_recovery_patterns())

        if patterns:
            log.info(
                "observation_history_patterns_detected",
                total_patterns=len(patterns),
                recurring_failures=sum(
                    1 for p in patterns if p.pattern_type == "recurring_failure"
                ),
                correlated_failures=sum(
                    1 for p in patterns if p.pattern_type == "correlated_failure"
                ),
                degradation_trends=sum(
                    1 for p in patterns if p.pattern_type == "degradation_trend"
                ),
                recovery_patterns=sum(
                    1 for p in patterns if p.pattern_type == "recovery_pattern"
                ),
            )

        return patterns

    # ── Pattern: Recurring Failures ────────────────────────────────────────

    def _detect_recurring_failures(self) -> List[PatternMatch]:
        """Detect services with the same error appearing more than 3 times.

        Groups error records by (source, status) and flags any group with
        more than 3 occurrences.  Confidence is calculated as
        ``min(count / 10, 0.95)`` — the more occurrences, the higher the
        confidence, capped at 0.95 to reflect that pattern detection is
        heuristic rather than certain.

        Returns:
            List of ``PatternMatch`` for recurring failures.
        """
        MIN_OCCURRENCES = 3
        patterns: List[PatternMatch] = []

        # Group error records by source
        error_by_source: Dict[str, List[ObservationRecord]] = defaultdict(list)
        for record in self._records:
            if record.status == "error":
                error_by_source[record.source].append(record)

        for source, records in error_by_source.items():
            if len(records) <= MIN_OCCURRENCES:
                continue

            records_sorted = sorted(records, key=lambda r: r.timestamp)
            confidence = min(len(records) / 10.0, 0.95)

            patterns.append(
                PatternMatch(
                    pattern_type="recurring_failure",
                    pattern_description=(
                        f"Service '{source}' has reported error status "
                        f"{len(records)} times — potential systemic issue"
                    ),
                    confidence=round(confidence, 3),
                    similar_events=len(records),
                    first_seen=records_sorted[0].timestamp,
                    last_seen=records_sorted[-1].timestamp,
                    related_records=[r.id for r in records_sorted],
                )
            )

        return patterns

    # ── Pattern: Correlated Failures ───────────────────────────────────────

    def _detect_correlated_failures(self) -> List[PatternMatch]:
        """Detect services that fail together within a 5-minute window.

        For each pair of distinct services that both have error records
        within 5 minutes of each other, count the co-occurrences.  Pairs
        with more than 2 co-occurrences are flagged.  Confidence scales
        with co-occurrence count.

        Returns:
            List of ``PatternMatch`` for correlated failures.
        """
        CORRELATION_WINDOW = timedelta(minutes=5)
        MIN_CO_OCCURRENCES = 2
        patterns: List[PatternMatch] = []

        # Collect error records with parsed timestamps
        errors: List[tuple[datetime, ObservationRecord]] = []
        for record in self._records:
            if record.status == "error":
                errors.append((_parse_timestamp(record.timestamp), record))

        if len(errors) < 2:
            return patterns

        # Sort by timestamp for efficient window scanning
        errors.sort(key=lambda pair: pair[0])

        # Count co-occurrences per service pair
        pair_counts: Dict[frozenset[str], List[tuple[ObservationRecord, ...]]] = (
            defaultdict(list)
        )

        for i, (ts_i, rec_i) in enumerate(errors):
            for j in range(i + 1, len(errors)):
                ts_j, rec_j = errors[j]
                if ts_j - ts_i > CORRELATION_WINDOW:
                    break  # Sorted, so no further matches in this window
                if rec_i.source == rec_j.source:
                    continue  # Same service, not a correlation
                pair_key = frozenset({rec_i.source, rec_j.source})
                pair_counts[pair_key].append((rec_i, rec_j))

        for pair_key, co_occurrences in pair_counts.items():
            if len(co_occurrences) < MIN_CO_OCCURRENCES:
                continue

            services = sorted(pair_key)
            all_records = [r for pair in co_occurrences for r in pair]
            timestamps = [_parse_timestamp(r.timestamp) for r in all_records]
            confidence = min(len(co_occurrences) / 5.0, 0.90)

            patterns.append(
                PatternMatch(
                    pattern_type="correlated_failure",
                    pattern_description=(
                        f"Services '{services[0]}' and '{services[1]}' fail "
                        f"together within 5 minutes ({len(co_occurrences)} "
                        f"co-occurrences) — possible shared dependency"
                    ),
                    confidence=round(confidence, 3),
                    similar_events=len(co_occurrences),
                    first_seen=min(timestamps).isoformat(),
                    last_seen=max(timestamps).isoformat(),
                    related_records=list({r.id for r in all_records}),
                )
            )

        return patterns

    # ── Pattern: Degradation Trends ────────────────────────────────────────

    def _detect_degradation_trends(self) -> List[PatternMatch]:
        """Detect services whose status degrades from ok → warn → error.

        For each service, examines the chronological sequence of statuses.
        A degradation trend is detected when a service transitions from
        "ok" to "warn" and then to "error" within the stored history.

        Confidence is based on how cleanly the progression follows the
        ok→warn→error path without regressions.

        Returns:
            List of ``PatternMatch`` for degradation trends.
        """
        patterns: List[PatternMatch] = []

        # Group records by source, sorted chronologically
        by_source: Dict[str, List[ObservationRecord]] = defaultdict(list)
        for record in self._records:
            by_source[record.source].append(record)

        for source, records in by_source.items():
            if len(records) < 3:
                continue

            records_sorted = sorted(records, key=lambda r: r.timestamp)

            # Extract status sequence
            statuses = [r.status for r in records_sorted]

            # Look for ok → warn → error progression
            ok_idx = warn_idx = error_idx = None
            for i, status in enumerate(statuses):
                if status == "ok" and ok_idx is None:
                    ok_idx = i
                elif status == "warn" and ok_idx is not None and warn_idx is None:
                    if i > ok_idx:
                        warn_idx = i
                elif status == "error" and warn_idx is not None and error_idx is None:
                    if i > warn_idx:
                        error_idx = i

            if ok_idx is not None and warn_idx is not None and error_idx is not None:
                # Count how many records in the progression path
                progression_records = records_sorted[ok_idx : error_idx + 1]
                # Confidence: higher if the transition is clean (few flips)
                progression_statuses = statuses[ok_idx : error_idx + 1]
                flips = 0
                for k in range(1, len(progression_statuses)):
                    if progression_statuses[k] != progression_statuses[k - 1]:
                        flips += 1
                # Ideal ok→warn→error has exactly 2 flips
                confidence = max(0.4, min(0.95, 0.7 - (flips - 2) * 0.1))

                patterns.append(
                    PatternMatch(
                        pattern_type="degradation_trend",
                        pattern_description=(
                            f"Service '{source}' shows degradation from "
                            f"ok → warn → error over "
                            f"{len(progression_records)} observations"
                        ),
                        confidence=round(confidence, 3),
                        similar_events=len(progression_records),
                        first_seen=records_sorted[ok_idx].timestamp,
                        last_seen=records_sorted[error_idx].timestamp,
                        related_records=[r.id for r in progression_records],
                    )
                )

        return patterns

    # ── Pattern: Recovery Patterns ─────────────────────────────────────────

    def _detect_recovery_patterns(self) -> List[PatternMatch]:
        """Detect services that recover from error → warn → ok.

        The inverse of degradation: a service that transitions from "error"
        through "warn" back to "ok" indicates a successful remediation
        (automated or manual).

        Confidence is based on the cleanliness of the recovery progression.

        Returns:
            List of ``PatternMatch`` for recovery patterns.
        """
        patterns: List[PatternMatch] = []

        # Group records by source, sorted chronologically
        by_source: Dict[str, List[ObservationRecord]] = defaultdict(list)
        for record in self._records:
            by_source[record.source].append(record)

        for source, records in by_source.items():
            if len(records) < 3:
                continue

            records_sorted = sorted(records, key=lambda r: r.timestamp)
            statuses = [r.status for r in records_sorted]

            # Look for error → warn → ok progression
            error_idx = warn_idx = ok_idx = None
            for i, status in enumerate(statuses):
                if status == "error" and error_idx is None:
                    error_idx = i
                elif status == "warn" and error_idx is not None and warn_idx is None:
                    if i > error_idx:
                        warn_idx = i
                elif status == "ok" and warn_idx is not None and ok_idx is None:
                    if i > warn_idx:
                        ok_idx = i

            if error_idx is not None and warn_idx is not None and ok_idx is not None:
                recovery_records = records_sorted[error_idx : ok_idx + 1]
                # Confidence based on how clean the recovery is
                recovery_statuses = statuses[error_idx : ok_idx + 1]
                flips = 0
                for k in range(1, len(recovery_statuses)):
                    if recovery_statuses[k] != recovery_statuses[k - 1]:
                        flips += 1
                confidence = max(0.4, min(0.95, 0.7 - (flips - 2) * 0.1))

                patterns.append(
                    PatternMatch(
                        pattern_type="recovery_pattern",
                        pattern_description=(
                            f"Service '{source}' recovered from "
                            f"error → warn → ok over "
                            f"{len(recovery_records)} observations"
                        ),
                        confidence=round(confidence, 3),
                        similar_events=len(recovery_records),
                        first_seen=records_sorted[error_idx].timestamp,
                        last_seen=records_sorted[ok_idx].timestamp,
                        related_records=[r.id for r in recovery_records],
                    )
                )

        return patterns

    # ── Service Timeline ───────────────────────────────────────────────────

    def get_service_timeline(
        self,
        service: str,
        hours: int = 24,
    ) -> List[ObservationRecord]:
        """Return chronological observations for a specific service.

        Filters records by source and by the *hours* lookback window,
        then sorts them chronologically (oldest first).  Useful for the
        Verify stage to check a service's recent trajectory.

        Args:
            service: The service name to filter on (e.g. "redis").
            hours:   Lookback window in hours (default 24).

        Returns:
            Chronologically ordered list of ``ObservationRecord`` entries
            for the specified service.
        """
        if not service:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        results: List[ObservationRecord] = []

        for record in self._records:
            if record.source != service:
                continue
            record_dt = _parse_timestamp(record.timestamp)
            if record_dt >= cutoff:
                results.append(record)

        results.sort(key=lambda r: r.timestamp)
        return results

    # ── Statistics ─────────────────────────────────────────────────────────

    def get_stats(self) -> Dict[str, Any]:
        """Return summary statistics about the observation history.

        Provides counts and distributions useful for dashboard rendering
        and operational monitoring.

        Returns:
            Dict with keys:
              - ``total_records``: Total number of records currently stored.
              - ``records_by_service``: Dict mapping source → count.
              - ``records_by_status``: Dict mapping status → count.
              - ``time_range``: Dict with ``earliest`` and ``latest`` ISO
                timestamps, or ``None`` if no records exist.
        """
        if not self._records:
            return {
                "total_records": 0,
                "records_by_service": {},
                "records_by_status": {},
                "time_range": None,
            }

        by_service: Counter[str] = Counter()
        by_status: Counter[str] = Counter()
        timestamps: List[str] = []

        for record in self._records:
            by_service[record.source] += 1
            by_status[record.status] += 1
            timestamps.append(record.timestamp)

        timestamps.sort()

        return {
            "total_records": len(self._records),
            "records_by_service": dict(by_service),
            "records_by_status": dict(by_status),
            "time_range": {
                "earliest": timestamps[0],
                "latest": timestamps[-1],
            },
        }

    # ── Clear ──────────────────────────────────────────────────────────────

    def clear(self) -> int:
        """Clear all observation records and return the count cleared.

        Removes all records from the in-memory deque and the ID index.
        Does NOT clear the vector store — that must be done separately
        via ``MemoryStore.clear()`` if needed.

        Returns:
            The number of records that were cleared.
        """
        count = len(self._records)
        self._records.clear()
        self._id_set.clear()

        log.info(
            "observation_history_cleared",
            records_cleared=count,
        )
        return count

    # ── Prune ──────────────────────────────────────────────────────────────

    def prune(self, max_age_hours: int = 168) -> int:
        """Remove records older than *max_age_hours* (default 7 days).

        Rebuilds the deque with only records that fall within the age
        window, and updates the ID index accordingly.

        Args:
            max_age_hours: Maximum age in hours for retained records.
                           Default is 168 (7 days).

        Returns:
            The number of records that were pruned.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
        original_count = len(self._records)

        surviving: List[ObservationRecord] = []
        for record in self._records:
            record_dt = _parse_timestamp(record.timestamp)
            if record_dt >= cutoff:
                surviving.append(record)

        pruned = original_count - len(surviving)

        # Rebuild the deque with surviving records
        self._records = deque(surviving, maxlen=self._max_records)
        self._id_set = {r.id for r in self._records}

        log.info(
            "observation_history_pruned",
            pruned=pruned,
            remaining=len(self._records),
            max_age_hours=max_age_hours,
        )
        return pruned
