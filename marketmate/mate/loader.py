"""
marketmate.mate.loader
──────────────────────
MATE Animated Telegram Loader — spinner and text separated.

Design Principles:
  - SPINNER and TEXT are SEPARATE — spinner animates independently
  - Static label message stays fixed (no flicker, no rewriting)
  - Spinner-only message gets rapidly edited (smooth animation)
  - Two messages: label (static) + spinner (animated)
  - Clean visual: text is always readable, spinner is always smooth
  - Fast transitions: 0.25-0.35s per spinner frame
  - 10 spinner characters for a full braille arc: ⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏

Telegram rate limit: ~0.3s per edit is safe and snappy.
When done, spinner message is deleted, label is replaced with the answer.
"""

from __future__ import annotations

import random
from typing import Tuple

from marketmate.core.logger import get_logger

log = get_logger("mate.loader")

# Spinner characters — the heartbeat of the loader
_SPIN = ["⠋", "⠙", "⠹", "⠸", "⠼", "⠴", "⠦", "⠧", "⠇", "⠏"]


# ═══════════════════════════════════════════════════════════════════════════════
# Static Labels — one per domain, never changes during animation
# ═══════════════════════════════════════════════════════════════════════════════
# These are the words the user sees. They stay fixed the entire time.
# Only the spinner message (a separate Telegram message) animates.

_DOMAIN_LABELS = {
    "market":   "🧠 MATE · Market",
    "signal":   "🧠 MATE · Signals",
    "account":  "🧠 MATE · Account",
    "strategy": "🧠 MATE · Strategy",
    "general":  "🧠 MATE",
    "system":   "🧠 MATE · System",
    "search":   "🧠 MATE · Search",
}

_DEFAULT_LABEL = "🧠 MATE"


# ═══════════════════════════════════════════════════════════════════════════════
# Loader Key Resolution — routes by query type / tool name / domain
# ═══════════════════════════════════════════════════════════════════════════════

# Map tool names (from agent.py) to loader keys
_TOOL_LOADER_MAP = {
    "get_live_price": "market",
    "get_market_summary": "market",
    "get_signal_stats": "signal",
    "get_signal_count": "signal",
    "get_active_signals": "signal",
    "explain_signal": "signal",
    "get_account_state": "account",
    "get_risk_state": "account",
    "explain_concept": "strategy",
    "get_session_schedule": "strategy",
    "get_strategy_params": "strategy",
    "get_gate_pipeline": "strategy",
    "get_system_health": "system",
    "get_pipeline_diagnostics": "system",
    "web_search": "search",
    "news_search": "search",
    "read_url": "search",
    "scan_url": "search",
    "security_check": "search",
}

_DOMAIN_LOADER_MAP = {
    "market_data": "market",
    "signal_intel": "signal",
    "account": "account",
    "strategy": "strategy",
    "user": "account",
    "system": "system",
    "general_chat": "general",
    "agent": "signal",
}

# Legacy query type → loader mapping (for fallback path)
_QUERY_TYPE_LOADER_MAP = {
    "price_query": "market",
    "market_summary": "market",
    "signal_count": "signal",
    "signal_explanation": "signal",
    "performance": "signal",
    "performance_explainer": "signal",
    "active_signals": "signal",
    "account_summary": "account",
    "risk_state": "account",
    "strategy_concept": "strategy",
    "gate_pipeline": "strategy",
    "session_schedule": "strategy",
    "system_status": "system",
    "auto_trade_diagnostics": "system",
    "general_chat": "general",
    "hard_no": "general",
    "web_search": "search",
    "news_search": "search",
}


def _resolve_loader_key(query_type: str, domain: str = "") -> str:
    """Resolve query_type and domain to a loader key (market/signal/account/strategy/general/system/search/document)."""
    # Direct key pass-through (handler now sends "market", "signal", etc. directly)
    if query_type in _DOMAIN_LABELS:
        return query_type
    # Try tool name first (agent mode)
    if query_type in _TOOL_LOADER_MAP:
        return _TOOL_LOADER_MAP[query_type]
    # Try legacy query type
    if query_type in _QUERY_TYPE_LOADER_MAP:
        return _QUERY_TYPE_LOADER_MAP[query_type]
    # Try domain
    if domain in _DOMAIN_LOADER_MAP:
        return _DOMAIN_LOADER_MAP[domain]
    # Default
    return "general"


def get_loader_label(query_type: str, domain: str = "") -> str:
    """
    Get the static label text for a domain.
    This text is sent once and never edited — it stays fixed while the spinner animates.

    Args:
        query_type: The detected query type, tool name, or query type string
        domain:     The intent domain (e.g., "market_data", "signal_intel")

    Returns:
        Static label string like "🧠 MATE · Market"
    """
    key = _resolve_loader_key(query_type, domain)
    return _DOMAIN_LABELS.get(key, _DEFAULT_LABEL)


def get_initial_spinner() -> str:
    """Get the first spinner character for immediate display."""
    return _SPIN[0]


def get_spinner_frames() -> list[str]:
    """
    Get the spinner character sequence for animation.
    Returns the 10 braille spinner characters in order.
    The animation loop cycles through these repeatedly.
    """
    return list(_SPIN)


# ═══════════════════════════════════════════════════════════════════════════════
# Backward Compatibility — old API still works for any code that calls these
# ═══════════════════════════════════════════════════════════════════════════════

# These return the OLD-style combined frames for any legacy callers.
# New code should use get_loader_label() + get_spinner_frames() instead.

MARKET_FRAMES = [f"{s} 🧠 MATE · Market" for s in _SPIN[:8]]
SIGNAL_FRAMES = [f"{s} 🧠 MATE · Signals" for s in _SPIN[:8]]
ACCOUNT_FRAMES = [f"{s} 🧠 MATE · Account" for s in _SPIN[:8]]
STRATEGY_FRAMES = [f"{s} 🧠 MATE · Strategy" for s in _SPIN[:8]]
GENERAL_FRAMES = [f"{s} 🧠 MATE" for s in _SPIN[:8]]
SYSTEM_FRAMES = [f"{s} 🧠 MATE · System" for s in _SPIN[:8]]
SEARCH_FRAMES = [f"{s} 🧠 MATE · Search" for s in _SPIN[:8]]
MAX_FRAMES = 8

_FRAME_SETS = {
    "market": MARKET_FRAMES,
    "signal": SIGNAL_FRAMES,
    "account": ACCOUNT_FRAMES,
    "strategy": STRATEGY_FRAMES,
    "general": GENERAL_FRAMES,
    "system": SYSTEM_FRAMES,
    "search": SEARCH_FRAMES,
}


def get_loader_frames(query_type: str, domain: str = "") -> list[str]:
    """
    [Legacy] Get combined frame sequence (spinner + label in one string).
    Prefer get_loader_label() + get_spinner_frames() for new code.
    """
    key = _resolve_loader_key(query_type, domain)
    frames = _FRAME_SETS.get(key, GENERAL_FRAMES)

    # Add tiny randomness — swap two adjacent frames occasionally
    if len(frames) > 2 and random.random() > 0.6:
        idx = random.randint(1, len(frames) - 2)
        frames = frames.copy()
        frames[idx], frames[idx + 1] = frames[idx + 1], frames[idx]

    return frames


def get_initial_frame(query_type: str, domain: str = "") -> str:
    """[Legacy] Get the first combined frame. Prefer get_loader_label() for new code."""
    frames = get_loader_frames(query_type, domain)
    return frames[0] if frames else f"{_SPIN[0]} {_DEFAULT_LABEL}"


# ═══════════════════════════════════════════════════════════════════════════════
# Animation Timing
# ═══════════════════════════════════════════════════════════════════════════════

# Fast timing — snappy, feels alive
FRAME_DELAY_MIN = 0.25  # seconds — quick spinner rotation
FRAME_DELAY_MAX = 0.35  # seconds — smooth but fast


def get_frame_delay() -> float:
    """Get a random frame delay in the safe Telegram range."""
    return random.uniform(FRAME_DELAY_MIN, FRAME_DELAY_MAX)
