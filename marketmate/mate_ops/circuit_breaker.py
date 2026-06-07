"""
marketmate/mate_ops/circuit_breaker.py
──────────────────────────────────────
Circuit Breaker pattern for MATE-Ops — Phase 2 semi-autonomous infrastructure
intelligence.

Phase 1 (read-only, Level 0 authority) identified critical gaps in the Max/Mini
assessment:

  * **Self-Healing Capability** scored 3/10 (target 8) — the system kept
    hammering failing services instead of backing off and recovering.
  * **Blast Radius** scored 4/10 (target 2) — cascading failures spread from
    one degraded service to the rest of the stack because nothing stopped
    the propagation.

The Circuit Breaker pattern directly addresses both gaps:

  1. **Self-Healing**: when a service exceeds its failure threshold the circuit
     *opens*, immediately rejecting (fast-failing) further requests.  After a
     configurable recovery timeout the circuit transitions to *half-open*,
     allowing a limited number of probe requests to test whether the service
     has recovered.  Successful probes close the circuit; failures re-open it.

  2. **Blast Radius containment**: by fast-failing at the circuit boundary,
     failing services are isolated.  Downstream callers receive immediate
     feedback instead of hanging on timeouts, and the failing service is
     shielded from additional load it cannot handle.

Circuit states
──────────────
  * **CLOSED**  — normal operation; all requests flow through.
  * **OPEN**    — circuit broken; requests are rejected / fast-failed.
  * **HALF_OPEN** — probing; a limited number of requests are allowed to
    test whether the downstream service has recovered.

Phase 2 authority level is 1 (safe ops: restart, cache clear, notify), so
circuit state transitions are logged and exposed to the MATE-Ops pipeline
but do not autonomously restart services — that requires PermissionGate
approval.

Pipeline position: this module sits in the **Execute** stage, protecting
outbound operations against known-failing downstream services.  The
``CircuitBreakerManager`` singleton is consumed by the health-check scheduler
and the anomaly-driven remediation loop.

Thread safety: ``CircuitBreakerManager`` uses ``asyncio.Lock`` for
coordinating access to the breaker registry.  Individual ``CircuitBreaker``
state transitions are synchronous and fast (dict / int updates) so they do
not require their own lock — callers should hold the manager lock when
looking up a breaker, then release it before mutating the breaker itself.
"""

from __future__ import annotations

import asyncio
import time
from enum import Enum
from typing import Any, Dict, Optional

from marketmate.core.logger import get_logger

log = get_logger("mate_ops.circuit_breaker")


# ─── Circuit State Enum ───────────────────────────────────────────────────────

class CircuitState(str, Enum):
    """
    Possible states of a circuit breaker.

    Inherits from ``str`` so that serialisation (JSON, logging) produces
    human-readable values rather than integer codes.

    Attributes:
        CLOSED:    Normal operation — requests flow through.
        OPEN:      Circuit broken — requests are rejected / fast-failed.
        HALF_OPEN: Probing — allow limited requests to test recovery.
    """

    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


# ─── Circuit Breaker ──────────────────────────────────────────────────────────

class CircuitBreaker:
    """
    A single circuit breaker protecting one downstream service.

    Typical lifecycle::

        breaker = CircuitBreaker("redis", failure_threshold=5, recovery_timeout=60)

        if breaker.allow_request():
            try:
                ...  # call the downstream service
                breaker.record_success()
            except Exception:
                breaker.record_failure()
        else:
            ...  # fast-fail / fallback

    State transitions:

      * CLOSED  → OPEN        when ``failure_count >= failure_threshold``
      * OPEN    → HALF_OPEN   when ``recovery_timeout`` seconds have elapsed
                                 since the last failure
      * HALF_OPEN → CLOSED    when ``success_count >= success_threshold``
      * HALF_OPEN → OPEN      on any single failure during the probe

    Args:
        name:              Human-readable identifier for the protected service.
        failure_threshold: Consecutive failures required to open the circuit.
        recovery_timeout:  Seconds to wait in OPEN state before transitioning
                           to HALF_OPEN for a recovery probe.
        success_threshold: Consecutive successes in HALF_OPEN required to
                           close the circuit.
    """

    def __init__(
        self,
        name: str,
        failure_threshold: int = 5,
        recovery_timeout: float = 60.0,
        success_threshold: int = 3,
    ) -> None:
        self._name = name
        self._failure_threshold = failure_threshold
        self._recovery_timeout = recovery_timeout
        self._success_threshold = success_threshold

        # State tracking
        self._state: CircuitState = CircuitState.CLOSED
        self._failure_count: int = 0
        self._success_count: int = 0
        self._last_failure_time: Optional[float] = None
        self._last_state_change_time: float = time.monotonic()

    # ── Recording ──────────────────────────────────────────────────────────

    def record_success(self) -> None:
        """Record a successful operation against the protected service.

        If the circuit is HALF_OPEN and the number of consecutive successes
        reaches *success_threshold*, the circuit transitions to CLOSED and
        counters are reset.

        In CLOSED state, a success resets the failure counter — we only
        trip the circuit on *consecutive* failures.
        """
        if self._state is CircuitState.HALF_OPEN:
            self._success_count += 1
            log.debug(
                "circuit_breaker_success_half_open",
                breaker=self._name,
                success_count=self._success_count,
                success_threshold=self._success_threshold,
            )
            if self._success_count >= self._success_threshold:
                self._transition_to(CircuitState.CLOSED)
        else:
            # CLOSED — reset consecutive failure counter on success
            self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed operation against the protected service.

        Behaviour depends on the current state:

          * **CLOSED**: increments the failure counter.  If it reaches
            *failure_threshold*, the circuit opens.
          * **HALF_OPEN**: a single failure immediately re-opens the circuit
            (the service is not yet healthy).
          * **OPEN**: no-op — the circuit is already open.
        """
        self._last_failure_time = time.monotonic()

        if self._state is CircuitState.HALF_OPEN:
            # One failure in half-open is enough to re-open
            log.info(
                "circuit_breaker_failure_half_open",
                breaker=self._name,
                action="reopening_circuit",
            )
            self._transition_to(CircuitState.OPEN)
            return

        if self._state is CircuitState.OPEN:
            # Already open — nothing to do
            return

        # CLOSED state — accumulate failures
        self._failure_count += 1
        log.debug(
            "circuit_breaker_failure",
            breaker=self._name,
            failure_count=self._failure_count,
            failure_threshold=self._failure_threshold,
        )
        if self._failure_count >= self._failure_threshold:
            self._transition_to(CircuitState.OPEN)

    # ── Request Admission ──────────────────────────────────────────────────

    def allow_request(self) -> bool:
        """Determine whether a request should be allowed through.

        Returns:
            ``True`` if the circuit is CLOSED or HALF_OPEN (requests flow).
            ``False`` if the circuit is OPEN (requests should be fast-failed),
            *unless* the recovery timeout has elapsed, in which case the
            circuit transitions to HALF_OPEN and ``True`` is returned.
        """
        if self._state is CircuitState.CLOSED:
            return True

        if self._state is CircuitState.HALF_OPEN:
            return True

        # OPEN — check whether recovery timeout has elapsed
        if self._last_failure_time is not None:
            elapsed = time.monotonic() - self._last_failure_time
            if elapsed >= self._recovery_timeout:
                log.info(
                    "circuit_breaker_recovery_probe",
                    breaker=self._name,
                    elapsed_seconds=round(elapsed, 2),
                    action="transitioning_to_half_open",
                )
                self._transition_to(CircuitState.HALF_OPEN)
                return True

        return False

    # ── State Access ───────────────────────────────────────────────────────

    def get_state(self) -> CircuitState:
        """Return the current circuit state."""
        return self._state

    def reset(self) -> None:
        """Force-reset the circuit breaker to CLOSED state.

        All counters are cleared and the last-failure timestamp is dropped.
        Use with caution — this should only be called by an operator or an
        authorised automated remediation action.
        """
        log.info(
            "circuit_breaker_reset",
            breaker=self._name,
            previous_state=self._state.value,
        )
        self._failure_count = 0
        self._success_count = 0
        self._last_failure_time = None
        self._state = CircuitState.CLOSED
        self._last_state_change_time = time.monotonic()

    def status(self) -> Dict[str, Any]:
        """Return a full snapshot of the circuit breaker's state.

        Useful for dashboard rendering, alerting, and the MATE-Ops
        **Verify** stage.

        Returns:
            Dict with keys: name, state, failure_count, success_count,
            failure_threshold, success_threshold, recovery_timeout,
            last_failure_time, last_state_change_time.
        """
        # Convert monotonic timestamps to human-readable elapsed seconds
        now = time.monotonic()
        last_failure_elapsed: Optional[float] = None
        if self._last_failure_time is not None:
            last_failure_elapsed = round(now - self._last_failure_time, 3)

        last_change_elapsed = round(now - self._last_state_change_time, 3)

        return {
            "name": self._name,
            "state": self._state.value,
            "failure_count": self._failure_count,
            "success_count": self._success_count,
            "failure_threshold": self._failure_threshold,
            "success_threshold": self._success_threshold,
            "recovery_timeout": self._recovery_timeout,
            "last_failure_time_elapsed_s": last_failure_elapsed,
            "last_state_change_elapsed_s": last_change_elapsed,
        }

    # ── Internal ───────────────────────────────────────────────────────────

    def _transition_to(self, new_state: CircuitState) -> None:
        """Transition to a new circuit state, resetting counters appropriately.

        Args:
            new_state: The target state.
        """
        old_state = self._state
        self._state = new_state
        self._last_state_change_time = time.monotonic()

        # Reset counters on state change
        if new_state is CircuitState.CLOSED:
            self._failure_count = 0
            self._success_count = 0
        elif new_state is CircuitState.OPEN:
            self._success_count = 0
        elif new_state is CircuitState.HALF_OPEN:
            self._failure_count = 0
            self._success_count = 0

        log.info(
            "circuit_breaker_state_change",
            breaker=self._name,
            old_state=old_state.value,
            new_state=new_state.value,
        )


# ─── Standard Service Names ───────────────────────────────────────────────────

DEFAULT_SERVICES: list[str] = [
    "api",
    "ollama",
    "redis",
    "mongodb",
    "telegram_bot",
    "prometheus",
]
"""Service names that receive circuit breakers by default when the
``CircuitBreakerManager`` is initialised."""


# ─── Circuit Breaker Manager ──────────────────────────────────────────────────

class CircuitBreakerManager:
    """
    Singleton registry of ``CircuitBreaker`` instances keyed by service name.

    Provides a unified API for the MATE-Ops pipeline to query and update
    circuit state without holding direct references to individual breakers.
    Thread safety for the breaker registry is provided by an ``asyncio.Lock``.

    Usage::

        manager = CircuitBreakerManager()

        if manager.should_check("redis"):
            try:
                ...  # health-check or operation
                manager.record_success("redis")
            except Exception:
                manager.record_failure("redis")

    The manager is a singleton: repeated construction returns the same
    instance.  This ensures all components in the MATE-Ops pipeline share
    a consistent view of circuit state.
    """

    _instance: Optional[CircuitBreakerManager] = None
    _initialised: bool = False

    def __new__(cls) -> CircuitBreakerManager:
        """Return the singleton instance, creating it on first call."""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self) -> None:
        """Initialise the manager and pre-create breakers for default services."""
        if self._initialised:
            return

        self._breakers: Dict[str, CircuitBreaker] = {}
        self._lock = asyncio.Lock()

        # Pre-create breakers for all standard services
        for service_name in DEFAULT_SERVICES:
            self._breakers[service_name] = CircuitBreaker(name=service_name)

        self.__class__._initialised = True
        log.info(
            "circuit_breaker_manager_init",
            default_services=DEFAULT_SERVICES,
        )

    # ── Registry ───────────────────────────────────────────────────────────

    async def get_breaker(self, service_name: str) -> CircuitBreaker:
        """Return the ``CircuitBreaker`` for *service_name*, creating one if needed.

        If a breaker does not yet exist for the given service, a new one
        is created with default parameters and registered.

        Args:
            service_name: The service to look up (e.g. "redis", "api").

        Returns:
            The ``CircuitBreaker`` instance for the requested service.
        """
        async with self._lock:
            if service_name not in self._breakers:
                self._breakers[service_name] = CircuitBreaker(name=service_name)
                log.debug(
                    "circuit_breaker_created",
                    service=service_name,
                    action="auto_created_on_get",
                )
            return self._breakers[service_name]

    # ── Convenience Methods ────────────────────────────────────────────────

    async def should_check(self, service_name: str) -> bool:
        """Return ``True`` if the circuit for *service_name* allows requests.

        This is the primary decision point for the health-check scheduler:
        before running a check, call ``should_check()`` to avoid wasting
        resources on services with open circuits.

        Args:
            service_name: The service to query.

        Returns:
            ``True`` if requests should be allowed; ``False`` if the circuit
            is open and the request should be fast-failed.
        """
        breaker = await self.get_breaker(service_name)
        return breaker.allow_request()

    async def record_success(self, service_name: str) -> None:
        """Record a successful operation for *service_name*.

        Args:
            service_name: The service that succeeded.
        """
        breaker = await self.get_breaker(service_name)
        breaker.record_success()

    async def record_failure(self, service_name: str) -> None:
        """Record a failed operation for *service_name*.

        Args:
            service_name: The service that failed.
        """
        breaker = await self.get_breaker(service_name)
        breaker.record_failure()

    # ── Bulk Operations ────────────────────────────────────────────────────

    async def get_all_status(self) -> Dict[str, Dict[str, Any]]:
        """Return the status of all registered circuit breakers.

        Returns:
            Dict mapping service names to their ``CircuitBreaker.status()``
            dictionaries.
        """
        async with self._lock:
            return {
                name: breaker.status()
                for name, breaker in self._breakers.items()
            }

    async def reset_all(self) -> None:
        """Reset all circuit breakers to CLOSED state.

        Use with caution — this should only be invoked by an operator
        or an authorised automated remediation action (e.g. after a
        confirmed infrastructure fix).
        """
        async with self._lock:
            for breaker in self._breakers.values():
                breaker.reset()
        log.info("circuit_breaker_manager_reset_all", count=len(self._breakers))

    async def remove_breaker(self, service_name: str) -> None:
        """Remove a circuit breaker from the registry.

        If no breaker exists for *service_name*, the call is a no-op.

        Args:
            service_name: The service whose breaker should be removed.
        """
        async with self._lock:
            if service_name in self._breakers:
                del self._breakers[service_name]
                log.info(
                    "circuit_breaker_removed",
                    service=service_name,
                )
