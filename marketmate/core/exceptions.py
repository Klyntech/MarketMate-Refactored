"""
marketmate/core/exceptions.py
──────────────────────────────
Custom exception hierarchy for MarketMate.

All domain-specific exceptions inherit from MarketMateError so that
callers can catch the base class for a blanket handler or target a
specific subsystem error when finer control is needed.

Hierarchy:

    MarketMateError
    ├── SignalPipelineError   — errors during signal generation / dedup
    ├── PersistenceError      — database / storage layer failures
    ├── DataEngineError       — market-data fetching & validation failures
    └── DeliveryError         — message delivery (Telegram, etc.) failures
"""

from __future__ import annotations


class MarketMateError(Exception):
    """Base exception for all MarketMate domain errors."""

    def __init__(self, message: str = "", *, detail: str = "") -> None:
        self.detail = detail
        super().__init__(message)


class SignalPipelineError(MarketMateError):
    """Error during signal generation, scoring, or deduplication."""


class PersistenceError(MarketMateError):
    """Error in the database / storage layer (SQLite, MongoDB, etc.)."""


class DataEngineError(MarketMateError):
    """Error fetching or validating market data (candles, indicators)."""


class DeliveryError(MarketMateError):
    """Error delivering a message or notification (Telegram, email, etc.)."""
