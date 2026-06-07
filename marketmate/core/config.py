"""
marketmate/core/config.py
──────────────────────────
Single source of truth for all configuration.

Migrated from ``config/settings.py`` into the ``marketmate.core`` package.
All values sourced from environment variables — no hardcoded secrets.

New in this version:
  - DeliveryConfig   — notification delivery settings
  - AnalyticsConfig  — analytics & tracking settings
  - PlatformConfig   — platform-level settings (web, API)

"""

import os
from dataclasses import dataclass, field
from typing import Dict, List

from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    """Strict env-var check — only used for truly required runtime values.

    IMPORTANT: Do NOT call this at module level / dataclass default_factory.
    It is intended for runtime validation only (e.g. inside methods that
    are called after the app has started). For config fields that may be
    absent during development or migration, use _optional() instead.
    """
    val = os.getenv(key)
    if not val:
        raise EnvironmentError(f"Required environment variable '{key}' is not set.")
    return val


def _warn_if_missing(key: str, context: str = "") -> str:
    """Return the env var value or empty string, with a warning if missing."""
    val = os.getenv(key, "")
    if not val:
        import warnings
        warnings.warn(
            f"Environment variable '{key}' is not set."
            + (f" Required for {context}." if context else ""),
            stacklevel=3,
        )
    return val


def _optional(key: str, default: str = "") -> str:
    return os.getenv(key, default)


# ─── Telegram ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class TelegramConfig:
    # LAZY VALIDATION: bot_token and chat_id use _optional() so the app
    # can start without .env (e.g. during migration, testing, or dev).
    # Call validate_telegram() at runtime before using Telegram features.
    bot_token:      str = field(default_factory=lambda: _optional("TELEGRAM_BOT_TOKEN", ""))
    chat_id:        str = field(default_factory=lambda: _optional("TELEGRAM_CHAT_ID", ""))
    # Your personal chat ID — receives payment notifications and admin alerts.
    # Set TELEGRAM_ADMIN_CHAT_ID in Render env vars.
    admin_chat_id:  str = field(default_factory=lambda: _optional("TELEGRAM_ADMIN_CHAT_ID", ""))
    # Random secret token for the webhook endpoint — prevents spoofed updates.
    # MUST be set via WEBHOOK_SECRET env var. No default — fail fast if missing.
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    webhook_secret: str = field(default_factory=lambda: _optional("WEBHOOK_SECRET", ""))
    # Separate path token for the webhook URL. This is the value in /webhook/{path_token}.
    # Using a separate token from webhook_secret means the URL-path secret doesn't
    # appear in the same validation as the header secret, and the two can be rotated
    # independently. If not set, falls back to webhook_secret for backward compat.
    webhook_path_token: str = field(default_factory=lambda: _optional("WEBHOOK_PATH_TOKEN", ""))

    @property
    def is_configured(self) -> bool:
        """Return True if bot_token and chat_id are both set."""
        return bool(self.bot_token and self.chat_id)


def validate_telegram() -> None:
    """
    Runtime validation for Telegram configuration.
    Call this before creating Bot instances or sending messages.
    Raises EnvironmentError if bot_token or chat_id is missing.
    """
    if not cfg.telegram.bot_token:
        raise EnvironmentError(
            "TELEGRAM_BOT_TOKEN is not set. "
            "Set it in .env or environment variables to enable Telegram delivery."
        )
    if not cfg.telegram.chat_id:
        raise EnvironmentError(
            "TELEGRAM_CHAT_ID is not set. "
            "Set it in .env or environment variables to enable Telegram delivery."
        )


# ─── Market Data ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DataConfig:
    binance_api_key:   str = field(default_factory=lambda: _optional("BINANCE_API_KEY"))
    binance_secret:    str = field(default_factory=lambda: _optional("BINANCE_SECRET"))
    alpha_vantage_key: str = field(default_factory=lambda: _optional("ALPHA_VANTAGE_KEY"))
    twelve_data_key:   str = field(default_factory=lambda: _optional("TWELVE_DATA_KEY"))

    htf_timeframes: List[str] = field(default_factory=lambda: ["1d", "4h"])
    ltf_timeframes: List[str] = field(default_factory=lambda: ["15m", "5m"])

    # MUST be > ema_period + 10 (200 + 10 = 210).
    # 250 gives 40 candles of headroom above the minimum threshold.
    htf_candles:    int   = 250
    ltf_candles:    int   = 50
    swing_lookback: int   = 7

    max_retries:        int   = 3
    retry_backoff_base: float = 2.0
    request_timeout:    int   = 10


# ─── Strategy ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StrategyConfig:
    pairs: List[str] = field(
        default_factory=lambda: _optional("PAIRS", "XAUUSD,BTCUSD,ETHUSD,EURUSD").split(",")
    )
    max_trades_per_day: int   = int(_optional("MAX_TRADES_PER_DAY", "5"))
    # Per-direction daily limit: max BUY or SELL signals per day.
    # Prevents the common pattern of 4+ BUY signals in one day.
    max_trades_per_direction_per_day: int = int(
        _optional("MAX_TRADES_PER_DIRECTION_PER_DAY", "2")
    )
    min_rr:             float = float(_optional("MIN_RR", "1.5"))
    # Dedup cooldown: minimum minutes between signals for the same pair+direction.
    # Reduced from 60 to 30 min — 60 was too aggressive, missed legitimate
    # follow-up setups while still allowing duplicates after restarts.
    dedup_cooldown_minutes: int = int(_optional("DEDUP_COOLDOWN_MINUTES", "30"))

    min_fvg_pct:           float = float(_optional("MIN_FVG_PCT", "0.001"))
    fvg_freshness_candles: int   = int(_optional("FVG_FRESHNESS_CANDLES", "10"))

    min_ob_displacement_candles: int = 3
    ob_expiry_candles:           int = 20
    ob_search_lookback:          int = 20

    sweep_freshness_candles: int   = int(_optional("SWEEP_FRESHNESS_CANDLES", "20"))
    min_sweep_pct:           float = float(_optional("MIN_SWEEP_PCT", "0.0005"))

    ema_period: int = 200

    london_open:  str = _optional("LONDON_OPEN",  "07:00")
    london_close: str = _optional("LONDON_CLOSE", "12:00")
    ny_open:      str = _optional("NY_OPEN",      "12:00")
    ny_close:     str = _optional("NY_CLOSE",     "17:00")


# ─── Risk ────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RiskConfig:
    risk_per_trade_pct:     float = float(_optional("RISK_PER_TRADE_PCT", "1.0"))
    account_size:           float = float(_optional("ACCOUNT_SIZE", "10000"))
    max_consecutive_losses: int   = int(_optional("MAX_CONSECUTIVE_LOSSES", "3"))
    atr_sl_multiplier:      float = 1.5
    atr_period:             int   = 14


# ─── Simulated Execution ─────────────────────────────────────────────────────

@dataclass(frozen=True)
class SimConfig:
    lot_size:                    float = float(_optional("SIM_LOT_SIZE", "0.01"))
    evaluation_interval_seconds: int   = int(_optional("SIM_EVAL_INTERVAL", "600"))
    eval_timeframe:              str   = _optional("SIM_EVAL_TF", "15m")
    eval_candles:                int   = 30


# ─── MongoDB ─────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class MongoConfig:
    uri:               str = field(default_factory=lambda: _optional(
        "MONGO_URI", "mongodb://localhost:27017"
    ))
    db_name:           str = field(default_factory=lambda: _optional(
        "MONGO_DB", "marketmate"
    ))
    collection:        str = "training_data"
    max_pool_size:     int = int(_optional("MONGO_MAX_POOL_SIZE", "20"))
    # Timeout for waiting for a connection from the pool (ms)
    wait_queue_timeout_ms: int = int(_optional("MONGO_WAIT_QUEUE_TIMEOUT_MS", "5000"))
    server_timeout_ms: int = 3000
    # Replica URI for dual-write backup
    replica_uri:       str = field(default_factory=lambda: _optional(
        "MONGODB_REPLICA_URI", ""
    ))


# ─── Redis (for MATE Intelligence Layer) ────────────────────────────────────

@dataclass(frozen=True)
class RedisConfig:
    url:            str = field(default_factory=lambda: _optional(
        "REDIS_URL", ""
    ))
    max_connections: int = 5
    default_ttl:    int = 3600  # 1 hour default TTL


# ─── Backup ──────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class BackupConfig:
    # Google Drive service account JSON key file path
    gdrive_service_account_path: str = field(default_factory=lambda: _optional(
        "GOOGLE_DRIVE_SERVICE_ACCOUNT_PATH", ""
    ))
    # Google Drive folder ID for backups
    gdrive_folder_id: str = field(default_factory=lambda: _optional(
        "GOOGLE_DRIVE_BACKUP_FOLDER_ID", ""
    ))
    # Daily backup time (UTC hour)
    backup_hour_utc: int = int(_optional("BACKUP_HOUR_UTC", "2"))
    # Maximum backups to keep on Drive
    max_backups:     int = int(_optional("MAX_BACKUPS", "30"))
    # Enable dual-write replication
    dual_write_enabled: bool = _optional("DUAL_WRITE_ENABLED", "true").lower() == "true"


# ─── Subscription ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class SubscriptionConfig:
    monthly_price_ngn:   int = 30_000         # ₦30,000/month
    quarterly_price_ngn: int = 80_000         # ₦80,000 / 3 months (saves ₦10,000)
    trial_days:          int = 7              # Free trial length
    bank_name:         str = field(default_factory=lambda: _optional("BANK_NAME", "OPay"))
    account_number:    str = field(default_factory=lambda: _optional("BANK_ACCOUNT_NUMBER", ""))
    account_name:      str = field(default_factory=lambda: _optional("BANK_ACCOUNT_NAME", ""))
    tos_version:       str = "1.0"          # Bump when ToS changes


# ─── Weekly Recap ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class RecapConfig:
    # Max % difference on any OHLC point before recap is held for admin review
    validation_threshold_pct: float = float(_optional("RECAP_VALIDATION_THRESHOLD_PCT", "0.20"))
    # Which external source to validate against
    external_source: str = _optional("RECAP_EXTERNAL_SOURCE", "twelve_data")


# ─── App ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AppConfig:
    env:       str  = _optional("ENV", "production")
    debug:     bool = _optional("DEBUG", "false").lower() == "true"
    log_level: str  = _optional("LOG_LEVEL", "INFO")
    db_path:   str  = _optional("DB_PATH", "./db/marketmate.db")
    scan_interval_seconds: int = int(_optional("SCAN_INTERVAL", "300"))
    port: int = int(_optional("PORT", "8000"))
    # SECURITY: Used to sign session tokens. MUST be set via SESSION_SECRET env var.
    # Empty default allows startup during development, but sessions will be
    # rejected if the secret is empty. Generate with:
    #   python -c "import secrets; print(secrets.token_hex(32))"
    session_secret: str = field(default_factory=lambda: _warn_if_missing("SESSION_SECRET", "session security"))
    # Admin secret for authenticating privileged API requests (e.g. chart generation).
    # MUST be set via ADMIN_SECRET env var. No default.
    # Generate with: python -c "import secrets; print(secrets.token_hex(32))"
    admin_secret: str = field(default_factory=lambda: _optional("ADMIN_SECRET", ""))


# ─── Groq API (legacy — kept for backward compat) ─────────────────────────

@dataclass(frozen=True)
class GroqConfig:
    api_key: str = field(default_factory=lambda: _optional("GROQ_API_KEY"))
    default_model: str = "llama-3.3-70b-versatile"
    generate_model: str = "llama-3.3-70b-versatile"
    review_models: tuple = (
        "llama-3.3-70b-versatile",
        "meta-llama/llama-4-scout-17b-16e-instruct",
        "qwen/qwen3-32b",
    )


# ─── Multi-Provider LLM ────────────────────────────────────────────────────
# Replaces the Groq-only approach with a configurable fallback stack.
# Providers without API keys are silently skipped at runtime.
#
# CRITICAL: Model names in generation_model and review_models use
# "logical" names (e.g. "gemini-2.0-flash"). Each provider resolves
# these to its own equivalent via llm.py's CROSS_PROVIDER_MODEL_MAP.
# This prevents sending "gemini-2.0-flash" to OpenRouter (400) or Groq (404).

@dataclass(frozen=True)
class LLMConfig:
    # Provider stack: comma-separated list of provider names tried in order.
    # Default: gemini (huge context, generous free tier) -> openrouter (one API,
    # many models) -> groq (fast but small context, last resort).
    # Providers without API keys are silently skipped.
    provider_stack: List[str] = field(
        default_factory=lambda: [
            s.strip()
            for s in _optional("LLM_PROVIDER_STACK", "gemini,openrouter,groq").split(",")
            if s.strip()
        ]
    )
    # Model for generation tasks (module drafts, expansion, depth pass).
    # Should be a model with a large context window.
    # This is a "logical" model name — each provider resolves it to its
    # own equivalent (e.g. OpenRouter -> google/gemini-2.0-flash-001).
    generation_model: str = _optional("LLM_GENERATION_MODEL", "gemini-2.0-flash")
    # Models for triple review (comma-separated). These run sequentially
    # with a small delay between calls.
    # Format: "model_name" or "provider:model_name" (provider prefix forces
    # a specific provider; without it, each provider resolves the model).
    review_models: List[str] = field(
        default_factory=lambda: [
            s.strip()
            for s in _optional(
                "LLM_REVIEW_MODELS",
                "gemini-2.0-flash,openrouter:google/gemini-2.0-flash-001,groq:llama-3.3-70b-versatile"
            ).split(",")
            if s.strip()
        ]
    )
    # Maximum retries per provider before falling through to the next one.
    max_retries_per_provider: int = int(_optional("LLM_MAX_RETRIES", "1"))
    # ── Per-provider rate limits (client-side throttling) ───────────────
    # These prevent hitting provider 429s by throttling requests BEFORE
    # they're sent. Each provider has its own RPM limit that defaults to
    # a safe value for the free tier. Override via env vars if you have a
    # paid API key with higher limits.
    # Gemini RPM limit (client-side). Default: 12 (free tier is ~15 RPM,
    # we stay under to avoid 429s). Set GEMINI_RPM_LIMIT=0 to disable.
    gemini_rpm_limit: int = int(_optional("GEMINI_RPM_LIMIT", "12"))


# ─── Google OAuth ────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class GoogleOAuthConfig:
    client_id:     str = field(default_factory=lambda: _optional("GOOGLE_CLIENT_ID"))
    client_secret: str = field(default_factory=lambda: _optional("GOOGLE_CLIENT_SECRET"))
    redirect_uri:  str = field(default_factory=lambda: _optional("GOOGLE_REDIRECT_URI", ""))
    scopes:        str = "openid email profile"


# ─── Delivery (new) ──────────────────────────────────────────────────────────
# Controls how signals and notifications are delivered to users.

@dataclass(frozen=True)
class DeliveryConfig:
    # Maximum concurrent delivery tasks (Telegram sends, etc.)
    max_concurrent_deliveries: int = int(_optional("MAX_CONCURRENT_DELIVERIES", "5"))
    # Seconds to wait before retrying a failed delivery
    retry_delay_seconds: int = int(_optional("DELIVERY_RETRY_DELAY", "30"))
    # Maximum delivery retry attempts
    max_retries: int = int(_optional("DELIVERY_MAX_RETRIES", "3"))
    # Enable quiet hours (no signals sent during specified hours)
    quiet_hours_enabled: bool = _optional("DELIVERY_QUIET_HOURS", "false").lower() == "true"
    quiet_hours_start: str = _optional("DELIVERY_QUIET_HOURS_START", "22:00")
    quiet_hours_end: str = _optional("DELIVERY_QUIET_HOURS_END", "07:00")


# ─── Analytics (new) ─────────────────────────────────────────────────────────
# Controls analytics, tracking, and ML training data collection.

@dataclass(frozen=True)
class AnalyticsConfig:
    # Enable / disable analytics tracking
    enabled: bool = _optional("ANALYTICS_ENABLED", "true").lower() == "true"
    # How often (seconds) to flush analytics events to storage
    flush_interval_seconds: int = int(_optional("ANALYTICS_FLUSH_INTERVAL", "300"))
    # Maximum events to buffer before forcing a flush
    max_buffer_size: int = int(_optional("ANALYTICS_MAX_BUFFER", "1000"))
    # Enable ML training data collection
    training_data_enabled: bool = _optional("TRAINING_DATA_ENABLED", "true").lower() == "true"
    # Backtest lookback days when generating weekly recaps
    backtest_lookback_days: int = int(_optional("BACKTEST_LOOKBACK_DAYS", "90"))


# ─── Platform (new) ──────────────────────────────────────────────────────────
# Controls web platform, API, and cross-cutting platform concerns.

@dataclass(frozen=True)
class PlatformConfig:
    # Base URL for the public-facing web app
    base_url: str = _optional("PLATFORM_BASE_URL", "https://newmarketmate.onrender.com")
    # API rate limit (requests per minute per IP)
    api_rate_limit_rpm: int = int(_optional("API_RATE_LIMIT_RPM", "60"))
    # Enable CORS for the API
    cors_enabled: bool = _optional("CORS_ENABLED", "true").lower() == "true"
    # Allowed CORS origins (comma-separated)
    cors_origins: List[str] = field(
        default_factory=lambda: [
            s.strip()
            for s in _optional("CORS_ORIGINS", "").split(",")
            if s.strip()
        ]
    )
    # Enable the educational academy module
    academy_enabled: bool = _optional("ACADEMY_ENABLED", "true").lower() == "true"


# ─── MATE Intelligence Layer ──────────────────────────────────────────────

@dataclass(frozen=True)
class MateConfig:
    # Per-user rate limit for MATE queries (requests per minute per user).
    # Prevents LLM cost amplification — each MATE query triggers one or more
    # LLM API calls, so unbounded access = unlimited costs.
    #
    # IMPORTANT: Reduced from 20 to 10 RPM. Here's why:
    #   - Gemini free tier = ~15 RPM (shared across ALL users)
    #   - Each MATE query spawns 1-8 LLM calls (agent loop iterations)
    #   - At 20 RPM × 3 avg iterations = 60 Gemini calls/min per user
    #   - 2 concurrent users = 120 calls/min, exhausting Gemini in seconds
    #   - 10 RPM × 3 avg iterations = 30 calls/min per user, leaving headroom
    # The client-side rate limiter in llm.py further caps Gemini at 12 RPM
    # total (not per-user), so even at 10 RPM/user the system stays safe.
    rate_limit_rpm: int = int(_optional("MATE_RATE_LIMIT_RPM", "10"))


# ─── State Engine ───────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StateConfig:
    """Configuration for the Market Intelligence State Engine (v8.0.0)."""
    # Snapshot interval in minutes for MongoDB warm-layer persistence.
    # Default: every 15 minutes during active sessions.
    snapshot_interval_minutes: int = int(_optional("STATE_SNAPSHOT_INTERVAL_MIN", "15"))
    # Maximum number of expired zones to retain per instrument.
    max_expired_zones: int = int(_optional("STATE_MAX_EXPIRED_ZONES", "20"))
    # Maximum number of recent confirmation patterns to retain.
    max_recent_patterns: int = int(_optional("STATE_MAX_RECENT_PATTERNS", "10"))
    # Minimum conviction score change to trigger a bias_changed event.
    conviction_change_threshold: float = float(_optional("STATE_CONVICTION_CHANGE_THRESHOLD", "0.2"))


# ─── Social Marketing Engine ──────────────────────────────────────────────
# Controls the social media marketing engine — AI-generated marketing
# and exposure posts for Twitter/X, Facebook, Instagram, and Telegram.
# NOT for trading signal broadcasts — this is marketing content only.

@dataclass(frozen=True)
class SocialConfig:
    # Master switch for the social marketing engine
    enabled: bool = _optional("SOCIAL_ENGINE_ENABLED", "true").lower() == "true"
    # Require admin approval before posts are published
    require_approval: bool = _optional("SOCIAL_REQUIRE_APPROVAL", "true").lower() == "true"
    # Use AI generation for marketing posts (fallback to templates if disabled)
    use_ai_generation: bool = _optional("SOCIAL_USE_AI", "true").lower() == "true"
    # Auto-generate marketing posts on a schedule
    auto_generate: bool = _optional("SOCIAL_AUTO_GENERATE", "false").lower() == "true"

    # Twitter/X credentials (OAuth 1.0a via tweepy)
    twitter_api_key: str = field(default_factory=lambda: _optional("TWITTER_API_KEY", ""))
    twitter_api_secret: str = field(default_factory=lambda: _optional("TWITTER_API_SECRET", ""))
    twitter_access_token: str = field(default_factory=lambda: _optional("TWITTER_ACCESS_TOKEN", ""))
    twitter_access_secret: str = field(default_factory=lambda: _optional("TWITTER_ACCESS_SECRET", ""))

    # Facebook Page credentials (Graph API)
    fb_page_id: str = field(default_factory=lambda: _optional("FB_PAGE_ID", ""))
    fb_access_token: str = field(default_factory=lambda: _optional("FB_ACCESS_TOKEN", ""))

    # Instagram Business Account (Content Publishing API via Facebook)
    ig_account_id: str = field(default_factory=lambda: _optional("IG_ACCOUNT_ID", ""))
    ig_access_token: str = field(default_factory=lambda: _optional("IG_ACCESS_TOKEN", ""))

    # Telegram channel for social broadcasts (separate from signal delivery)
    telegram_channel_id: str = field(default_factory=lambda: _optional("SOCIAL_TELEGRAM_CHANNEL_ID", ""))


# ─── Root Config ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Config:
    telegram:     TelegramConfig     = field(default_factory=TelegramConfig)
    data:         DataConfig         = field(default_factory=DataConfig)
    strategy:     StrategyConfig     = field(default_factory=StrategyConfig)
    risk:         RiskConfig         = field(default_factory=RiskConfig)
    sim:          SimConfig          = field(default_factory=SimConfig)
    mongo:        MongoConfig        = field(default_factory=MongoConfig)
    subscription: SubscriptionConfig = field(default_factory=SubscriptionConfig)
    app:          AppConfig          = field(default_factory=AppConfig)
    recap:        RecapConfig        = field(default_factory=RecapConfig)
    groq:         GroqConfig         = field(default_factory=GroqConfig)
    llm:          LLMConfig          = field(default_factory=LLMConfig)
    google_oauth: GoogleOAuthConfig  = field(default_factory=GoogleOAuthConfig)
    # ── New sections ─────────────────────────────────────────────────────
    delivery:     DeliveryConfig     = field(default_factory=DeliveryConfig)
    analytics:    AnalyticsConfig    = field(default_factory=AnalyticsConfig)
    platform:     PlatformConfig     = field(default_factory=PlatformConfig)
    # ── v6.2.0 sections ──────────────────────────────────────────────────
    redis:        RedisConfig        = field(default_factory=RedisConfig)
    backup:       BackupConfig       = field(default_factory=BackupConfig)
    # ── v7.0.0 sections ──────────────────────────────────────────────────
    mate:         MateConfig         = field(default_factory=MateConfig)
    # ── v8.0.0 sections ──────────────────────────────────────────────────
    state:        StateConfig        = field(default_factory=StateConfig)
    # ── v9.0.0 sections ──────────────────────────────────────────────────
    social:       SocialConfig       = field(default_factory=SocialConfig)


cfg = Config()
