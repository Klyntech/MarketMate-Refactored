"""
marketmate/mate_ops/permission_gate.py
───────────────────────────────────────
Safety layer for MATE-Ops execution.

Every action is validated against:
  1. Authority level (0=read-only, 1=safe ops, 2=destructive)
  2. Action-specific policy (whitelist of allowed actions)
  3. Human approval (for Level 2 actions)

The gate logs every decision including denied actions.

Kill switch:
  When KILL_SWITCH is enabled, ALL Level 1+ actions are denied.
  This is the emergency brake — use it when something is wrong and
  you need to freeze all automated operations immediately.
"""

from __future__ import annotations

import asyncio
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from enum import IntEnum
from typing import Any, Callable, Coroutine, List, Optional

from marketmate.core.logger import get_logger

log = get_logger("mate_ops.permission_gate")


# ─── Authority Levels ─────────────────────────────────────────────────────────

class AuthorityLevel(IntEnum):
    """
    Authority levels for MATE-Ops actions.

    0 = Read-only — observe, analyze, report
    1 = Safe ops  — restart workers, clear caches, rotate logs, notify team
    2 = Destructive — requires explicit human approval (DB migrations, deploys)
    """

    READ_ONLY = 0
    SAFE_OPS = 1
    DESTRUCTIVE = 2


# ─── Escalation Token (Phase 2) ────────────────────────────────────────────────

@dataclass
class EscalationToken:
    """Time-limited token granting temporary authority escalation."""

    token_id: str = field(default_factory=lambda: str(uuid.uuid4())[:8])
    level: AuthorityLevel = AuthorityLevel.READ_ONLY
    reason: str = ""
    issued_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    expires_at: str = ""
    issued_by: str = "system"
    is_valid: bool = True

    def is_expired(self) -> bool:
        """Check if the token has expired."""
        if not self.expires_at:
            return False
        try:
            expiry = datetime.fromisoformat(self.expires_at)
            return datetime.now(timezone.utc) > expiry
        except (ValueError, TypeError):
            return False

    def remaining_seconds(self) -> float:
        """Return seconds until expiration, or float('inf') if no expiry."""
        if not self.expires_at:
            return float("inf")
        try:
            expiry = datetime.fromisoformat(self.expires_at)
            remaining = (expiry - datetime.now(timezone.utc)).total_seconds()
            return max(remaining, 0.0)
        except (ValueError, TypeError):
            return 0.0


# ─── Action Authority Map ─────────────────────────────────────────────────────
# Maps every known action name to the minimum authority level required.

ACTION_AUTHORITY_MAP: dict[str, AuthorityLevel] = {
    # Level 0 — Read-only
    "check_health":      AuthorityLevel.READ_ONLY,
    "read_logs":         AuthorityLevel.READ_ONLY,
    "check_metrics":     AuthorityLevel.READ_ONLY,
    "check_website":     AuthorityLevel.READ_ONLY,
    "check_ollama":      AuthorityLevel.READ_ONLY,
    "check_redis":       AuthorityLevel.READ_ONLY,
    "check_mongodb":     AuthorityLevel.READ_ONLY,
    "check_telegram":    AuthorityLevel.READ_ONLY,
    # Level 1 — Safe operations
    "restart_service":   AuthorityLevel.SAFE_OPS,
    "clear_cache":       AuthorityLevel.SAFE_OPS,
    "rotate_logs":       AuthorityLevel.SAFE_OPS,
    "notify_team":       AuthorityLevel.SAFE_OPS,
    "reconnect_feed":    AuthorityLevel.SAFE_OPS,
    "switch_provider":   AuthorityLevel.SAFE_OPS,
    # Level 0 — OPS read-only (Tier 1)
    "monitor":           AuthorityLevel.READ_ONLY,
    "observe":           AuthorityLevel.READ_ONLY,
    "report":            AuthorityLevel.READ_ONLY,
    "inspect":           AuthorityLevel.READ_ONLY,
    # Level 2 — Destructive (requires human approval)
    "db_migration":      AuthorityLevel.DESTRUCTIVE,
    "config_change":     AuthorityLevel.DESTRUCTIVE,
    "deploy":            AuthorityLevel.DESTRUCTIVE,
    "scale":             AuthorityLevel.DESTRUCTIVE,
    "delete_data":       AuthorityLevel.DESTRUCTIVE,
}


# ─── Permission Gate ──────────────────────────────────────────────────────────

class PermissionGate:
    """
    Safety layer that validates every MATE-Ops action before execution.

    Three-layer validation:
      1. Kill switch check — if active, deny all Level 1+ actions
      2. Authority level check — action's required level vs max allowed
      3. Human approval — for Level 2 (destructive) actions, a callback
         must confirm the action is approved

    Every decision (approved or denied) is logged with the reason.
    """

    KILL_SWITCH: bool = False

    def __init__(
        self,
        max_authority_level: AuthorityLevel = AuthorityLevel.READ_ONLY,
        approval_callback: Optional[Callable[..., Coroutine[Any, Any, bool]]] = None,
    ) -> None:
        """
        Initialize the permission gate.

        Args:
            max_authority_level: Maximum authority level this gate allows.
                Actions requiring a higher level are automatically denied.
            approval_callback: Async callable invoked for Level 2 actions.
                Should return True if the action is approved, False otherwise.
                Typically sends a Telegram message and waits for confirmation.
        """
        self._base_authority_level: AuthorityLevel = max_authority_level
        self._active_tokens: List[EscalationToken] = []
        self._max_authority_level = max_authority_level
        self._approval_callback = approval_callback

    # ── Core Validation ───────────────────────────────────────────────────────

    def validate(self, action: str) -> bool:
        """
        Check if *action* is allowed at the current authority level.

        Validation order:
          1. Kill switch — if active, deny all Level 1+ actions
          2. Unknown actions are denied by default
          3. Action's required level vs gate's max authority level
          4. Level 2 actions require separate human approval via
             request_approval()

        Returns:
            True if the action is allowed, False otherwise.
        """
        # 1. Kill switch check
        if self.KILL_SWITCH:
            required_level = ACTION_AUTHORITY_MAP.get(action)
            if required_level is not None and required_level > AuthorityLevel.READ_ONLY:
                self.log_decision(
                    action=action,
                    approved=False,
                    reason="kill_switch_active",
                )
                return False

        # 2. Unknown actions are denied
        required_level = ACTION_AUTHORITY_MAP.get(action)
        if required_level is None:
            self.log_decision(
                action=action,
                approved=False,
                reason="unknown_action",
            )
            return False

        # 3. Authority level check
        if required_level > self._max_authority_level:
            self.log_decision(
                action=action,
                approved=False,
                reason=f"authority_level_too_low: required={required_level.value}, max={self._max_authority_level.value}",
            )
            return False

        # 4. Level 2 actions need human approval (checked separately)
        if required_level == AuthorityLevel.DESTRUCTIVE:
            self.log_decision(
                action=action,
                approved=False,
                reason="destructive_action_requires_approval",
            )
            return False

        # Action is allowed
        self.log_decision(
            action=action,
            approved=True,
            reason=f"authority_level_ok: required={required_level.value}, max={self._max_authority_level.value}",
        )
        return True

    async def request_approval(self, action: str) -> bool:
        """
        Request human approval for a Level 2 (destructive) action.

        Uses the approval_callback to send a notification (typically via
        Telegram) and wait for confirmation.

        If no callback is configured, Level 2 actions are ALWAYS denied.

        Args:
            action: The action name requesting approval.

        Returns:
            True if the action is approved, False otherwise.
        """
        required_level = ACTION_AUTHORITY_MAP.get(action)
        if required_level != AuthorityLevel.DESTRUCTIVE:
            # Not a destructive action — no approval needed
            return self.validate(action)

        # Kill switch overrides everything
        if self.KILL_SWITCH:
            self.log_decision(
                action=action,
                approved=False,
                reason="kill_switch_active_during_approval",
            )
            return False

        # Authority level must still allow Level 2
        if self._max_authority_level < AuthorityLevel.DESTRUCTIVE:
            self.log_decision(
                action=action,
                approved=False,
                reason=f"authority_level_too_low_for_approval: max={self._max_authority_level.value}",
            )
            return False

        # Request approval via callback
        if self._approval_callback is None:
            self.log_decision(
                action=action,
                approved=False,
                reason="no_approval_callback_configured",
            )
            return False

        try:
            approved = await self._approval_callback(action)
            self.log_decision(
                action=action,
                approved=approved,
                reason="human_approval_result",
            )
            return approved
        except Exception as exc:
            self.log_decision(
                action=action,
                approved=False,
                reason=f"approval_callback_error: {exc}",
            )
            return False

    # ── Logging ───────────────────────────────────────────────────────────────

    def log_decision(self, action: str, approved: bool, reason: str) -> None:
        """
        Log every permission decision — approved or denied.

        This creates an audit trail for all automated actions.
        Denied actions are logged at WARNING level so they show up
        in monitoring. Approved actions at INFO level.
        """
        level = "info" if approved else "warning"
        log_msg = {
            "action": action,
            "approved": approved,
            "reason": reason,
            "max_authority_level": self._max_authority_level.value,
            "kill_switch_active": self.KILL_SWITCH,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

        if approved:
            log.info("mate_ops_permission_decision", **log_msg)
        else:
            log.warning("mate_ops_permission_denied", **log_msg)

    # ── Configuration ─────────────────────────────────────────────────────────

    def set_authority_level(self, level: AuthorityLevel) -> None:
        """
        Update the maximum authority level this gate allows.

        This can be used to dynamically escalate or de-escalate
        permissions at runtime (e.g., during an incident).
        """
        old_level = self._max_authority_level
        self._max_authority_level = level
        log.info(
            "mate_ops_authority_level_changed",
            old_level=old_level.value,
            new_level=level.value,
        )

    @classmethod
    def enable_kill_switch(cls) -> None:
        """
        Activate the kill switch — deny ALL Level 1+ actions.

        This is the emergency brake. Use it when something is wrong
        and you need to freeze all automated operations immediately.
        """
        cls.KILL_SWITCH = True
        log.warning(
            "mate_ops_kill_switch_enabled",
            message="All Level 1+ actions are now DENIED. Use disable_kill_switch() to resume.",
        )

    @classmethod
    def disable_kill_switch(cls) -> None:
        """
        Deactivate the kill switch — resume normal permission validation.

        Only call this after the incident has been resolved.
        """
        cls.KILL_SWITCH = False
        log.info(
            "mate_ops_kill_switch_disabled",
            message="Normal permission validation resumed.",
        )

    # ── Introspection ─────────────────────────────────────────────────────────

    @property
    def max_authority_level(self) -> AuthorityLevel:
        """Return the current maximum authority level."""
        return self._max_authority_level

    @property
    def kill_switch_active(self) -> bool:
        """Return True if the kill switch is currently active."""
        return self.KILL_SWITCH

    def get_required_level(self, action: str) -> Optional[AuthorityLevel]:
        """Return the required authority level for an action, or None if unknown."""
        return ACTION_AUTHORITY_MAP.get(action)

    # ── Time-Limited Escalation (Phase 2) ────────────────────────────────────

    def escalate_to(
        self,
        level: AuthorityLevel,
        reason: str = "",
        ttl_seconds: int = 1800,
        issued_by: str = "system",
    ) -> EscalationToken:
        """
        Temporarily escalate authority with a time-limited token.

        Creates an EscalationToken, applies the escalated level, and
        tracks the token for auto-deescalation when it expires.

        Args:
            level: The authority level to escalate to.
            reason: Why the escalation is needed.
            ttl_seconds: Time-to-live in seconds (default 30 min, max 2h).
            issued_by: Who or what triggered the escalation.

        Returns:
            An EscalationToken that can be used to track or revoke the escalation.
        """
        ttl_seconds = min(ttl_seconds, 7200)  # Cap at 2 hours
        token = EscalationToken(
            level=level,
            reason=reason,
            expires_at=(datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)).isoformat(),
            issued_by=issued_by,
        )
        self._active_tokens.append(token)
        self._sync_effective_level()
        log.info(
            "mate_ops_escalation_granted",
            token_id=token.token_id,
            level=level.value,
            reason=reason,
            ttl_seconds=ttl_seconds,
            issued_by=issued_by,
        )
        return token

    def revoke_escalation(self, token_id: str) -> bool:
        """
        Revoke an escalation token by ID.

        Invalidates the token and re-syncs the effective authority level.
        If no other active tokens exist, reverts to the base level.

        Returns True if the token was found and revoked.
        """
        for token in self._active_tokens:
            if token.token_id == token_id:
                token.is_valid = False
                self._active_tokens = [
                    t for t in self._active_tokens if t.is_valid and not t.is_expired()
                ]
                self._sync_effective_level()
                log.info(
                    "mate_ops_escalation_revoked",
                    token_id=token_id,
                    new_effective_level=self._max_authority_level.value,
                )
                return True
        return False

    def cleanup_expired_tokens(self) -> int:
        """
        Remove expired tokens and re-sync effective level.

        Returns the number of tokens that were cleaned up.
        """
        before = len(self._active_tokens)
        self._active_tokens = [
            t for t in self._active_tokens if t.is_valid and not t.is_expired()
        ]
        cleaned = before - len(self._active_tokens)
        if cleaned > 0:
            self._sync_effective_level()
            log.info(
                "mate_ops_tokens_cleaned",
                tokens_removed=cleaned,
                remaining=len(self._active_tokens),
            )
        return cleaned

    def get_active_tokens(self) -> List[EscalationToken]:
        """Return all active (non-expired, valid) escalation tokens."""
        self._active_tokens = [
            t for t in self._active_tokens if t.is_valid and not t.is_expired()
        ]
        return list(self._active_tokens)

    def _sync_effective_level(self) -> None:
        """
        Sync the permission gate's max authority level with the highest active token.

        If there are active tokens, the effective level is the maximum of:
          - The highest active token level
          - The base level (set via constructor or set_authority_level)

        If no active tokens, reverts to the base level.
        """
        active = [t for t in self._active_tokens if t.is_valid and not t.is_expired()]
        if active:
            max_token_level = max(t.level for t in active)
            new_level = max(max_token_level, self._base_authority_level)
        else:
            new_level = self._base_authority_level

        old_level = self._max_authority_level
        self._max_authority_level = new_level

        if old_level != new_level:
            log.info(
                "mate_ops_effective_level_changed",
                old_level=old_level.value,
                new_level=new_level.value,
                reason="token_sync",
            )

    @property
    def base_authority_level(self) -> AuthorityLevel:
        """Return the base authority level (without any escalation tokens)."""
        return self._base_authority_level
