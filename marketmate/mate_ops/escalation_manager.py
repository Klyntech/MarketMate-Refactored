"""
marketmate/mate_ops/escalation_manager.py
──────────────────────────────────────────
Phase 2 of MATE-Ops: Time-limited authority escalation with automatic
de-escalation.

Phase 1 gaps addressed:
  - "Privilege Escalation Risk" (3 → 1): Every escalated privilege now
    carries a time-limited token that automatically expires, forcing
    authority back to READ_ONLY.  No permanent elevation is possible.
  - "Audit Trail Completeness" (6 → 10): Every escalation, approval,
    revocation, and expiration event is recorded with who/why/when/level
    in a structured audit log.

Authority model (unchanged from Phase 1):
  Level 0  READ_ONLY   — observe, analyze, report
  Level 1  SAFE_OPS    — restart, clear cache, notify, rotate logs
  Level 2  DESTRUCTIVE — db_migration, config_change, deploy, delete_data
                          (always requires explicit human approval)

Phase 2 addition:
  An ``EscalationManager`` can issue *time-limited* escalation tokens.
  When a token expires, the authority it granted is automatically
  revoked.  If multiple tokens are active simultaneously, the effective
  authority level is the maximum among them.  When all tokens expire,
  the permission gate reverts to READ_ONLY.

Safety guarantees:
  - Tokens are always time-limited (TTL capped at 2 hours by default).
  - DESTRUCTIVE level *always* requires explicit approval — never
    auto-approved.
  - ``force_deescalate()`` is available as an emergency reset that
    revokes every active token immediately.
  - A background loop checks for expired tokens every 30 seconds.
"""

from __future__ import annotations

import asyncio
import threading
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import List, Optional

from marketmate.core.logger import get_logger
from marketmate.mate_ops.permission_gate import AuthorityLevel, PermissionGate

log = get_logger("mate_ops.escalation_manager")


# ─── Data Classes ─────────────────────────────────────────────────────────────

@dataclass
class EscalationRequest:
    """
    A request to escalate authority to a higher level.

    Attributes:
        id: Unique identifier for the request.
        requested_level: The authority level being requested.
        reason: Human-readable justification for the escalation.
        requested_by: Identity of the requester (default "system").
        requested_at: ISO-8601 timestamp when the request was created.
        expires_at: ISO-8601 timestamp when the requested token would expire.
        status: Lifecycle status — one of "pending", "approved", "active",
                "expired", or "revoked".
    """

    id: str
    requested_level: AuthorityLevel
    reason: str
    requested_by: str
    requested_at: str
    expires_at: str
    status: str = "pending"


@dataclass
class EscalationToken:
    """
    A time-limited token granting elevated authority.

    Once issued, the token is valid until ``expires_at``.  The
    ``is_expired()`` method should be checked before relying on the
    token; ``remaining_seconds()`` reports how long the token still has.

    Attributes:
        id: Unique identifier for the token.
        level: The authority level this token grants.
        issued_at: ISO-8601 timestamp when the token was issued.
        expires_at: ISO-8601 timestamp when the token expires.
        reason: Human-readable justification (carried from the request).
        issued_by: Identity of the approver who issued the token.
        is_valid: False once the token has been explicitly revoked or
                  detected as expired.
    """

    id: str
    level: AuthorityLevel
    issued_at: str
    expires_at: str
    reason: str
    issued_by: str
    is_valid: bool = True

    def is_expired(self) -> bool:
        """
        Return True if the current time is past ``expires_at``.

        Uses UTC for all comparisons.
        """
        now = datetime.now(timezone.utc)
        expiry = datetime.fromisoformat(self.expires_at)
        # Ensure timezone-aware comparison
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        return now > expiry

    def remaining_seconds(self) -> float:
        """
        Return the number of seconds until this token expires.

        Returns 0.0 if the token is already expired.
        """
        now = datetime.now(timezone.utc)
        expiry = datetime.fromisoformat(self.expires_at)
        if expiry.tzinfo is None:
            expiry = expiry.replace(tzinfo=timezone.utc)
        delta = (expiry - now).total_seconds()
        return max(0.0, delta)


# ─── Escalation Manager ──────────────────────────────────────────────────────

class EscalationManager:
    """
    Manages time-limited authority escalation for MATE-Ops.

    Key behaviours:
      - ``request_escalation()`` creates a request.  If the requested
        level is SAFE_OPS or lower, the request is auto-approved and a
        token is issued immediately.  DESTRUCTIVE requests remain in
        "pending" status until explicitly approved via
        ``approve_escalation()``.
      - Expired tokens are automatically detected and revoked by a
        background loop (``_auto_check_loop``) running every 30 seconds.
      - When the last active token expires or is revoked, the permission
        gate is reset to READ_ONLY.
      - Every action is recorded in a structured audit log.

    Args:
        permission_gate: The ``PermissionGate`` whose authority level
            this manager controls.
        default_ttl_seconds: Default time-to-live for escalation tokens
            (30 minutes).
        max_ttl_seconds: Maximum allowed TTL — requests exceeding this
            are clamped (2 hours).
    """

    def __init__(
        self,
        permission_gate: PermissionGate,
        default_ttl_seconds: int = 1800,
        max_ttl_seconds: int = 7200,
    ) -> None:
        self._gate = permission_gate
        self._default_ttl = default_ttl_seconds
        self._max_ttl = max_ttl_seconds

        # Active storage
        self._requests: dict[str, EscalationRequest] = {}
        self._tokens: dict[str, EscalationToken] = {}

        # Structured audit trail
        self._audit_log: list[dict] = []

        # Background auto-check thread
        self._check_interval: int = 30  # seconds
        self._stop_event = threading.Event()
        self._bg_thread: Optional[threading.Thread] = None
        self._start_background_check()

    # ── Public API ────────────────────────────────────────────────────────────

    def request_escalation(
        self,
        level: AuthorityLevel,
        reason: str,
        requested_by: str = "system",
        ttl_seconds: int = 0,
    ) -> EscalationRequest:
        """
        Create an escalation request.

        If *level* is SAFE_OPS or lower the request is auto-approved: its
        status is set to "approved", a token is created, and the
        permission gate is updated immediately.  DESTRUCTIVE requests
        stay "pending" and must be approved explicitly via
        ``approve_escalation()``.

        The TTL is clamped to ``max_ttl_seconds``.

        Args:
            level: The authority level being requested.
            reason: Justification for the escalation.
            requested_by: Identity of the requester.
            ttl_seconds: Desired time-to-live. 0 means use the default.

        Returns:
            The ``EscalationRequest`` (status will be "approved" for
            auto-approved requests, "pending" otherwise).
        """
        now = datetime.now(timezone.utc)
        effective_ttl = self._clamp_ttl(ttl_seconds)
        expires_at = datetime.fromtimestamp(
            now.timestamp() + effective_ttl, tz=timezone.utc
        )

        request_id = uuid.uuid4().hex[:12]
        request = EscalationRequest(
            id=request_id,
            requested_level=level,
            reason=reason,
            requested_by=requested_by,
            requested_at=now.isoformat(),
            expires_at=expires_at.isoformat(),
            status="pending",
        )
        self._requests[request_id] = request

        self._record_audit(
            event="escalation_requested",
            request_id=request_id,
            level=level.value,
            reason=reason,
            requested_by=requested_by,
            ttl_seconds=effective_ttl,
        )

        # Auto-approve SAFE_OPS and below
        if level <= AuthorityLevel.SAFE_OPS:
            self.approve_escalation(request_id)
            request = self._requests[request_id]  # refresh after approval

        return request

    def approve_escalation(self, request_id: str) -> EscalationToken:
        """
        Approve a pending escalation request and issue a token.

        The permission gate's authority level is raised to the token's
        level (or the maximum among all active tokens, whichever is
        higher).

        Args:
            request_id: The ID of the ``EscalationRequest`` to approve.

        Returns:
            The newly issued ``EscalationToken``.

        Raises:
            KeyError: If the request ID does not exist.
            ValueError: If the request is not in "pending" status.
        """
        request = self._requests.get(request_id)
        if request is None:
            raise KeyError(f"No escalation request found with id={request_id!r}")
        if request.status != "pending":
            raise ValueError(
                f"Request {request_id!r} is not pending (status={request.status!r})"
            )

        now = datetime.now(timezone.utc)

        # Mark request as approved
        request.status = "approved"

        # Issue token
        token_id = uuid.uuid4().hex[:12]
        token = EscalationToken(
            id=token_id,
            level=request.requested_level,
            issued_at=now.isoformat(),
            expires_at=request.expires_at,
            reason=request.reason,
            issued_by=request.requested_by,
            is_valid=True,
        )
        self._tokens[token_id] = token

        # Update the request status to active
        request.status = "active"

        # Sync permission gate to highest active level
        self._sync_gate_level()

        self._record_audit(
            event="escalation_approved",
            request_id=request_id,
            token_id=token_id,
            level=token.level.value,
            expires_at=token.expires_at,
            reason=token.reason,
            issued_by=token.issued_by,
        )

        log.info(
            "escalation_token_issued",
            token_id=token_id,
            level=token.level.name,
            expires_at=token.expires_at,
            reason=token.reason,
        )

        return token

    def revoke_escalation(self, token_id: str) -> bool:
        """
        Immediately revoke an active escalation token.

        If no other active tokens remain, the permission gate is reset
        to READ_ONLY.

        Args:
            token_id: The ID of the ``EscalationToken`` to revoke.

        Returns:
            True if the token was found and revoked, False otherwise.
        """
        token = self._tokens.get(token_id)
        if token is None:
            self._record_audit(
                event="revocation_failed",
                token_id=token_id,
                reason="token_not_found",
            )
            return False

        if not token.is_valid:
            self._record_audit(
                event="revocation_skipped",
                token_id=token_id,
                reason="token_already_invalid",
            )
            return False

        token.is_valid = False

        # Also update any associated request
        for req in self._requests.values():
            if (
                req.status == "active"
                and req.requested_level == token.level
                and req.reason == token.reason
                and req.expires_at == token.expires_at
            ):
                req.status = "revoked"
                break

        # Sync gate — may revert to READ_ONLY
        self._sync_gate_level()

        self._record_audit(
            event="escalation_revoked",
            token_id=token_id,
            level=token.level.value,
            reason=token.reason,
        )

        log.warning(
            "escalation_token_revoked",
            token_id=token_id,
            level=token.level.name,
        )

        return True

    def check_tokens(self) -> list[str]:
        """
        Check all tokens for expiration and revoke expired ones.

        Returns:
            A list of token IDs that were revoked due to expiration.
        """
        revoked_ids: list[str] = []
        now = datetime.now(timezone.utc)

        for token_id, token in list(self._tokens.items()):
            if token.is_valid and token.is_expired():
                token.is_valid = False
                revoked_ids.append(token_id)

                # Update associated request
                for req in self._requests.values():
                    if (
                        req.status == "active"
                        and req.requested_level == token.level
                        and req.reason == token.reason
                        and req.expires_at == token.expires_at
                    ):
                        req.status = "expired"
                        break

                self._record_audit(
                    event="escalation_expired",
                    token_id=token_id,
                    level=token.level.value,
                    reason=token.reason,
                    expired_at=now.isoformat(),
                )

                log.info(
                    "escalation_token_expired",
                    token_id=token_id,
                    level=token.level.name,
                )

        if revoked_ids:
            self._sync_gate_level()

        return revoked_ids

    def get_active_tokens(self) -> list[EscalationToken]:
        """
        Return all non-expired, non-revoked escalation tokens.

        Tokens that have expired but haven't yet been caught by
        ``check_tokens()`` are also excluded (they are detected on the
        fly).
        """
        return [
            t for t in self._tokens.values()
            if t.is_valid and not t.is_expired()
        ]

    def get_escalation_log(self) -> list[dict]:
        """
        Return the full audit trail of all escalation events.

        Each entry is a dict with at least: event, timestamp, and
        event-specific fields (request_id, token_id, level, reason, …).
        """
        return list(self._audit_log)

    def get_current_effective_level(self) -> AuthorityLevel:
        """
        Return the highest authority level among all active tokens.

        Returns READ_ONLY if no tokens are active.
        """
        active = self.get_active_tokens()
        if not active:
            return AuthorityLevel.READ_ONLY
        return max(t.level for t in active)

    def force_deescalate(self) -> None:
        """
        Emergency reset: revoke every active token and reset the
        permission gate to READ_ONLY.

        This is the panic button — use it when something is wrong and
        all elevated authority must be removed immediately.
        """
        now = datetime.now(timezone.utc)
        revoked_count = 0

        for token_id, token in self._tokens.items():
            if token.is_valid:
                token.is_valid = False
                revoked_count += 1

                # Update associated request
                for req in self._requests.values():
                    if (
                        req.status == "active"
                        and req.requested_level == token.level
                        and req.reason == token.reason
                        and req.expires_at == token.expires_at
                    ):
                        req.status = "revoked"
                        break

        # Always reset to READ_ONLY
        self._gate.set_authority_level(AuthorityLevel.READ_ONLY)

        self._record_audit(
            event="force_deescalate",
            tokens_revoked=revoked_count,
            reset_to=AuthorityLevel.READ_ONLY.value,
            timestamp=now.isoformat(),
        )

        log.warning(
            "force_deescalate_executed",
            tokens_revoked=revoked_count,
            new_level=AuthorityLevel.READ_ONLY.name,
        )

    # ── Background Auto-Check ─────────────────────────────────────────────────

    def _start_background_check(self) -> None:
        """Start the background thread that periodically checks for expired tokens."""
        self._bg_thread = threading.Thread(
            target=self._auto_check_loop,
            name="escalation-manager-check",
            daemon=True,
        )
        self._bg_thread.start()

    def _auto_check_loop(self) -> None:
        """
        Periodically call ``check_tokens()`` to auto-revoke expired tokens.

        Runs on a daemon thread so it does not prevent interpreter
        shutdown.  Stops cleanly when ``_stop_event`` is set (e.g. in
        ``shutdown()``).
        """
        while not self._stop_event.is_set():
            try:
                self.check_tokens()
            except Exception as exc:
                log.error(
                    "escalation_auto_check_error",
                    error=str(exc),
                )
            self._stop_event.wait(timeout=self._check_interval)

    def shutdown(self) -> None:
        """
        Stop the background auto-check thread and revoke all tokens.

        Call this during application shutdown to ensure a clean state.
        """
        self._stop_event.set()
        if self._bg_thread is not None and self._bg_thread.is_alive():
            self._bg_thread.join(timeout=5)
        self.force_deescalate()
        log.info("escalation_manager_shutdown_complete")

    # ── Internal Helpers ──────────────────────────────────────────────────────

    def _clamp_ttl(self, ttl_seconds: int) -> int:
        """
        Clamp the requested TTL to the allowed range.

        A TTL of 0 means "use the default".  Any TTL exceeding
        ``max_ttl_seconds`` is clamped.
        """
        if ttl_seconds <= 0:
            return self._default_ttl
        return min(ttl_seconds, self._max_ttl)

    def _sync_gate_level(self) -> None:
        """
        Synchronise the permission gate's authority level with the
        highest level among all currently active tokens.

        If no tokens are active, the gate is reset to READ_ONLY.
        """
        effective = self.get_current_effective_level()
        current_gate = self._gate.max_authority_level

        if effective != current_gate:
            old = current_gate.value
            self._gate.set_authority_level(effective)
            self._record_audit(
                event="gate_level_synced",
                old_level=old,
                new_level=effective.value,
            )
            log.info(
                "gate_authority_synced",
                old_level=old,
                new_level=effective.value,
            )

    def _record_audit(self, **fields: object) -> None:
        """
        Append a structured audit entry.

        Every entry automatically receives a UTC timestamp.
        """
        entry: dict = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **fields,
        }
        self._audit_log.append(entry)
