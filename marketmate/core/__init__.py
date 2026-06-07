"""
marketmate.core
───────────────
Core infrastructure package for MarketMate.

Re-exports the most commonly used items so that downstream modules
can import from the package root instead of reaching into sub-modules:

    from marketmate.core import cfg, get_logger, llm_provider

All other items remain available via their full module path:

    from marketmate.core.exceptions import DataEngineError

    from marketmate.core.healthcheck import start_healthcheck
"""

# ── Config ────────────────────────────────────────────────────────────────────
from marketmate.core.config import (
    Config,
    cfg,
    TelegramConfig,
    DataConfig,
    StrategyConfig,
    RiskConfig,
    SimConfig,
    MongoConfig,
    SubscriptionConfig,
    RecapConfig,
    AppConfig,
    GroqConfig,
    LLMConfig,
    GoogleOAuthConfig,
    DeliveryConfig,
    AnalyticsConfig,
    PlatformConfig,
    validate_telegram,
)

# ── Logger ────────────────────────────────────────────────────────────────────
from marketmate.core.logger import get_logger

# ── Healthcheck ───────────────────────────────────────────────────────────────
from marketmate.core.healthcheck import start_healthcheck

# ── LLM ──────────────────────────────────────────────────────────────────────
from marketmate.core.llm import (
    llm_provider,
    LLMProvider,
    ProviderResult,
    BaseProvider,
    LLMRateLimitError,
    LLMPayloadTooLargeError,
    LLMAuthError,
    LLMAllProvidersFailedError,
    estimate_tokens,
    truncate_to_budget,
    CROSS_PROVIDER_MODEL_MAP,
    MODEL_CONTEXT_LIMITS,
    PROVIDER_CLASSES,
)

# ── Exceptions ────────────────────────────────────────────────────────────────
from marketmate.core.exceptions import (
    MarketMateError,
    SignalPipelineError,
    PersistenceError,
    DataEngineError,
    DeliveryError,
)

# ── Events ────────────────────────────────────────────────────────────────────
from marketmate.core.events import EventBus, event_bus, EventType

# ── Scheduler ─────────────────────────────────────────────────────────────────
from marketmate.core.scheduler import Scheduler

__all__ = [
    # Config
    "Config",
    "cfg",
    "TelegramConfig",
    "DataConfig",
    "StrategyConfig",
    "RiskConfig",
    "SimConfig",
    "MongoConfig",
    "SubscriptionConfig",
    "RecapConfig",
    "AppConfig",
    "GroqConfig",
    "LLMConfig",
    "GoogleOAuthConfig",
    "DeliveryConfig",
    "AnalyticsConfig",
    "PlatformConfig",
    "validate_telegram",
    # Logger
    "get_logger",
    # Healthcheck
    "start_healthcheck",
    # LLM
    "llm_provider",
    "LLMProvider",
    "ProviderResult",
    "BaseProvider",
    "LLMRateLimitError",
    "LLMPayloadTooLargeError",
    "LLMAuthError",
    "LLMAllProvidersFailedError",
    "estimate_tokens",
    "truncate_to_budget",
    "CROSS_PROVIDER_MODEL_MAP",
    "MODEL_CONTEXT_LIMITS",
    "PROVIDER_CLASSES",
    # Exceptions
    "MarketMateError",
    "SignalPipelineError",
    "PersistenceError",
    "DataEngineError",
    "DeliveryError",
    # Events
    "EventBus",
    "event_bus",
    "EventType",
    # Scheduler
    "Scheduler",
]
