"""MATE-Ops Phase 2 — Message Sanitization & Rate Limiting.

This module provides outbound-message sanitization and rate limiting for the
MATE-Ops semi-autonomous infrastructure intelligence system.  It directly
addresses two Phase 1 pentest warnings:

1. **Telegram sanitization gap** — Alert messages were found to leak internal
   URLs (redis://, mongodb://), file paths (/etc/, /var/), internal IPs, and
   credentials in plaintext.
2. **API rate limiting gap** — No explicit rate limiter existed for outbound
   alert dispatch, allowing potential alert storms that could trigger upstream
   throttling or bans.

Additionally, the module closes the Phase 1 Max/Mini "Data Exposure" gap
(severity 4 → 1) by ensuring that every piece of sensitive infrastructure
metadata is redacted before it leaves the system.

Classes
-------
Sanitizer
    Regex-driven text sanitization with pluggable custom patterns.
RateLimiter
    Sliding-window rate limiter backed by a ``collections.deque`` of
    timestamps.
AlertManager
    Combines ``Sanitizer`` and ``RateLimiter`` into a single façade for
    safe, formatted alert dispatch.

Module Singletons
-----------------
default_sanitizer, default_rate_limiter, default_alert_manager
    Pre-wired instances using sensible defaults.
"""

from __future__ import annotations

import re
import time
from collections import deque
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Sanitizer
# ---------------------------------------------------------------------------

class Sanitizer:
    """Redacts sensitive infrastructure data from outbound text.

    Built-in patterns cover the most common leak categories identified during
    the Phase 1 pentest (internal URLs, credentials, file paths, IPs, and
    Telegram bot tokens).  Additional patterns can be supplied at construction
    time or added later via :meth:`add_pattern`.

    Parameters
    ----------
    custom_patterns : list[tuple[str, str]] | None
        Optional list of ``(regex, replacement)`` pairs that are applied
        **after** the built-in patterns.  Each replacement may contain
        back-references (e.g. ``\\1``) to groups captured in the regex.
    """

    # Built-in sanitization rules — ordered from most specific to least.
    _BUILTIN_PATTERNS: List[Tuple[str, str]] = [
        # ── Database / broker URLs ──────────────────────────────────────
        (
            r"redis://[^\s\"'>]+",
            "[REDIS_URL_REDACTED]",
        ),
        (
            r"mongodb://[^\s\"'>]+",
            "[MONGODB_URL_REDACTED]",
        ),
        (
            r"postgresql://[^\s\"'>]+",
            "[POSTGRES_URL_REDACTED]",
        ),
        # ── Telegram bot tokens ────────────────────────────────────────
        (
            r"bot\d+:[A-Za-z0-9_-]+",
            "[BOT_TOKEN_REDACTED]",
        ),
        # ── API keys / tokens / Bearer headers ─────────────────────────
        (
            r"(?i)bearer\s+\S+",
            "[CREDENTIAL_REDACTED]",
        ),
        (
            r"(?i)(api[_-]?key|secret|password|passwd)\s*[=:]\s*\S+",
            "[CREDENTIAL_REDACTED]",
        ),
        # ── 0.0.0.0 with port ─────────────────────────────────────────
        (
            r"0\.0\.0\.0:(\d+)",
            r"[ALL_INTERFACES:\1]",
        ),
        # ── localhost with port (preserve port) ────────────────────────
        (
            r"localhost:(\d+)",
            r"[LOCALHOST:\1]",
        ),
        # ── RFC 1918 internal IPs ──────────────────────────────────────
        (
            r"\b(?:10\.\d{1,3}\.\d{1,3}\.\d{1,3}"
            r"|192\.168\.\d{1,3}\.\d{1,3}"
            r"|172\.(?:1[6-9]|2\d|3[01])\.\d{1,3}\.\d{1,3})\b",
            "[INTERNAL_IP]",
        ),
        # ── Sensitive file paths ───────────────────────────────────────
        (
            r"(?:(?:/etc/|/var/|/home/|/root/)[^\s\"'>]*)",
            "[PATH_REDACTED]",
        ),
    ]

    def __init__(self, custom_patterns: Optional[List[Tuple[str, str]]] = None) -> None:
        self._patterns: List[Tuple[re.Pattern[str], str]] = [
            (re.compile(pat), repl) for pat, repl in self._BUILTIN_PATTERNS
        ]
        if custom_patterns:
            for pat, repl in custom_patterns:
                self._patterns.append((re.compile(pat), repl))

    # ── Public API ─────────────────────────────────────────────────────

    def sanitize(self, text: str) -> str:
        """Redact sensitive data from *text* using all registered patterns.

        Patterns are applied in order; later patterns operate on the output
        of earlier ones, which means custom patterns can further transform
        built-in redaction markers if desired.

        Parameters
        ----------
        text : str
            Raw text that may contain sensitive infrastructure data.

        Returns
        -------
        str
            Sanitized text with sensitive values replaced by redaction
            markers.
        """
        result = text
        for pattern, replacement in self._patterns:
            result = pattern.sub(replacement, result)
        return result

    def sanitize_observation(self, observation_dict: dict) -> dict:
        """Return a shallow copy of *observation_dict* with sanitized strings.

        The function sanitizes the values of any keys named ``"message"`` or
        ``"details"`` (case-insensitive match).  All other keys are passed
        through unchanged.

        Parameters
        ----------
        observation_dict : dict
            An observation mapping, typically produced by
            :mod:`marketmate.mate_ops.observer`.

        Returns
        -------
        dict
            A new dictionary with sensitive values redacted.
        """
        sanitized: dict = {}
        for key, value in observation_dict.items():
            if isinstance(key, str) and key.lower() in ("message", "details") and isinstance(value, str):
                sanitized[key] = self.sanitize(value)
            else:
                sanitized[key] = value
        return sanitized

    def add_pattern(self, pattern: str, replacement: str) -> None:
        """Register an additional sanitization rule at runtime.

        The new rule is appended to the end of the pattern list, meaning it
        runs **after** all existing rules (both built-in and previously-added
        custom rules).

        Parameters
        ----------
        pattern : str
            A regular expression string.
        replacement : str
            The replacement string (may include back-references like
            ``\\1``).
        """
        self._patterns.append((re.compile(pattern), replacement))


# ---------------------------------------------------------------------------
# RateLimiter
# ---------------------------------------------------------------------------

class RateLimiter:
    """Sliding-window rate limiter for outbound alert dispatch.

    Maintains a :class:`collections.deque` of timestamps representing recent
    calls.  Each call to :meth:`allow` records the current time and returns
    whether the call is within the configured rate limit.

    Parameters
    ----------
    max_calls : int
        Maximum number of calls permitted within *window_seconds*.
    window_seconds : float
        Duration of the sliding window in seconds.
    """

    def __init__(self, max_calls: int = 10, window_seconds: float = 60.0) -> None:
        if max_calls < 1:
            raise ValueError("max_calls must be >= 1")
        if window_seconds <= 0:
            raise ValueError("window_seconds must be > 0")
        self._max_calls: int = max_calls
        self._window_seconds: float = window_seconds
        self._timestamps: deque[float] = deque()

    # ── Internal helpers ───────────────────────────────────────────────

    def _prune(self) -> None:
        """Remove timestamps that have fallen outside the sliding window."""
        cutoff = time.monotonic() - self._window_seconds
        while self._timestamps and self._timestamps[0] <= cutoff:
            self._timestamps.popleft()

    # ── Public API ─────────────────────────────────────────────────────

    def allow(self) -> bool:
        """Check and record whether a call is permitted.

        If the number of calls within the current window is below
        ``max_calls``, the current timestamp is recorded and ``True`` is
        returned.  Otherwise the call is rejected and ``False`` is returned
        (the timestamp is **not** recorded for rejected calls).

        Returns
        -------
        bool
            ``True`` if the call is allowed, ``False`` if the rate limit
            has been exceeded.
        """
        self._prune()
        if len(self._timestamps) < self._max_calls:
            self._timestamps.append(time.monotonic())
            return True
        return False

    def remaining(self) -> int:
        """Return the number of calls still permitted in the current window.

        Returns
        -------
        int
            Remaining call budget (always >= 0).
        """
        self._prune()
        return max(0, self._max_calls - len(self._timestamps))

    def reset(self) -> None:
        """Clear all recorded timestamps, effectively resetting the window."""
        self._timestamps.clear()

    def status(self) -> Dict[str, int | float]:
        """Return a snapshot of the rate limiter's current state.

        Returns
        -------
        dict
            A mapping with the following keys:

            - ``max_calls`` (int): the configured maximum.
            - ``window`` (float): the configured window in seconds.
            - ``remaining`` (int): calls remaining in the current window.
            - ``calls_made`` (int): calls already made in the current window.
            - ``window_resets_at`` (float): approximate ``time.monotonic()``
              value when the oldest recorded call will expire.
        """
        self._prune()
        now = time.monotonic()
        window_resets_at: float = (
            self._timestamps[0] + self._window_seconds if self._timestamps else now
        )
        return {
            "max_calls": self._max_calls,
            "window": self._window_seconds,
            "remaining": max(0, self._max_calls - len(self._timestamps)),
            "calls_made": len(self._timestamps),
            "window_resets_at": window_resets_at,
        }


# ---------------------------------------------------------------------------
# AlertManager
# ---------------------------------------------------------------------------

class AlertManager:
    """Combined sanitization and rate-limiting façade for alert dispatch.

    Parameters
    ----------
    sanitizer : Sanitizer
        The sanitizer instance used to redact sensitive data.
    rate_limiter : RateLimiter
        The rate limiter used to gate outbound messages.
    """

    # Severity emoji mapping for Telegram-friendly formatting.
    _SEVERITY_EMOJI: Dict[str, str] = {
        "critical": "🔴",
        "error": "🟠",
        "warning": "🟡",
        "info": "🟢",
        "debug": "⚪",
    }

    def __init__(self, sanitizer: Sanitizer, rate_limiter: RateLimiter) -> None:
        self._sanitizer: Sanitizer = sanitizer
        self._rate_limiter: RateLimiter = rate_limiter

    # ── Public API ─────────────────────────────────────────────────────

    def format_alert(
        self,
        title: str,
        message: str,
        severity: str = "info",
        observations: Optional[List[dict]] = None,
    ) -> str:
        """Build a Telegram-safe alert message with all content sanitized.

        The resulting message uses a simple plain-text layout that renders
        well in Telegram monospace blocks.

        Parameters
        ----------
        title : str
            Short alert title (will be sanitized).
        message : str
            Human-readable alert body (will be sanitized).
        severity : str
            One of ``critical``, ``error``, ``warning``, ``info``, ``debug``.
            Maps to a coloured circle emoji in the output.
        observations : list[dict] | None
            Optional list of observation dicts.  Each observation's
            ``message`` and ``details`` values are sanitized.

        Returns
        -------
        str
            The fully formatted, sanitized alert string.
        """
        emoji = self._SEVERITY_EMOJI.get(severity.lower(), "⚪")
        clean_title = self._sanitizer.sanitize(title)
        clean_message = self._sanitizer.sanitize(message)

        lines: List[str] = [
            f"{emoji} [{severity.upper()}] {clean_title}",
            f"{clean_message}",
        ]

        if observations:
            lines.append("")
            lines.append(f"Observations ({len(observations)}):")
            for idx, obs in enumerate(observations, start=1):
                sanitized_obs = self._sanitizer.sanitize_observation(obs)
                obs_msg = sanitized_obs.get("message", "—")
                obs_details = sanitized_obs.get("details", "")
                lines.append(f"  {idx}. {obs_msg}")
                if obs_details:
                    lines.append(f"     {obs_details}")

        return "\n".join(lines)

    def should_send(self) -> bool:
        """Check whether the rate limiter would permit a new call.

        This is a **read-only** check — it does **not** consume a rate-limit
        slot.  Use :meth:`format_and_check` to both format and consume.

        Returns
        -------
        bool
            ``True`` if a call is currently allowed.
        """
        return self._rate_limiter.remaining() > 0

    def format_and_check(
        self,
        title: str,
        message: str,
        severity: str = "info",
        observations: Optional[List[dict]] = None,
    ) -> Tuple[str, bool]:
        """Format an alert **and** consume a rate-limit slot if allowed.

        This is the primary entry point for the alert pipeline: it returns
        both the sanitized, formatted message and a boolean indicating
        whether the message may be dispatched.

        Parameters
        ----------
        title : str
            Short alert title (will be sanitized).
        message : str
            Human-readable alert body (will be sanitized).
        severity : str
            Severity level (default ``"info"``).
        observations : list[dict] | None
            Optional observation dicts to include.

        Returns
        -------
        tuple[str, bool]
            A 2-tuple of ``(formatted_message, is_allowed)``.  When
            ``is_allowed`` is ``False`` the caller should suppress the
            dispatch but may still log the formatted message internally.
        """
        formatted = self.format_alert(title, message, severity, observations)
        allowed = self._rate_limiter.allow()
        return formatted, allowed


# ---------------------------------------------------------------------------
# Module-level singletons
# ---------------------------------------------------------------------------

default_sanitizer: Sanitizer = Sanitizer()
"""Default sanitizer instance with built-in patterns only."""

default_rate_limiter: RateLimiter = RateLimiter()
"""Default rate limiter (10 calls per 60 seconds)."""

default_alert_manager: AlertManager = AlertManager(default_sanitizer, default_rate_limiter)
"""Pre-wired alert manager using the default sanitizer and rate limiter."""
