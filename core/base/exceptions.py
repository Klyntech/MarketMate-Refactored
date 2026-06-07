"""Custom exceptions for the signal engine."""

class SignalEngineError(Exception):
    """Base exception for the signal engine."""

class DataProviderError(SignalEngineError):
    """Error fetching market data."""

class ConfigError(SignalEngineError):
    """Configuration error."""
