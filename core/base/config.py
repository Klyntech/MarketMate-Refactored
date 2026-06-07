"""
signal_engine/core/config.py
──────────────────────────
Single source of truth for all configuration.

Simplified from the original MarketMate config — removed:
  GroqConfig, LLMConfig, GoogleOAuthConfig, RedisConfig, BackupConfig,
  MateConfig, StateConfig, SocialConfig, SubscriptionConfig, RecapConfig,
  AnalyticsConfig, PlatformConfig

Kept ONLY:
  TelegramConfig, DataConfig, StrategyConfig, RiskConfig, SimConfig,
  MongoConfig, AppConfig (simplified), DeliveryConfig
"""

import os
from dataclasses import dataclass, field
from typing import List

from dotenv import load_dotenv

load_dotenv()


def _require(key: str) -> str:
    """Strict env-var check — only used for truly required runtime values."""
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
    bot_token:      str = field(default_factory=lambda: _optional("TELEGRAM_BOT_TOKEN", ""))
    chat_id:        str = field(default_factory=lambda: _optional("TELEGRAM_CHAT_ID", ""))
    admin_chat_id:  str = field(default_factory=lambda: _optional("TELEGRAM_ADMIN_CHAT_ID", ""))

    @property
    def is_configured(self) -> bool:
        """Return True if bot_token and chat_id are both set."""
        return bool(self.bot_token and self.chat_id)


def validate_telegram() -> None:
    """
    Runtime validation for Telegram configuration.
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

    htf_candles:    int   = 250
    ltf_candles:    int   = 50
    swing_lookback: int   = 7

    max_retries:        int   = 3
    retry_backoff_base: float = 2.0
    request_timeout:    int   = 10


# ─── Strategy ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class StrategyConfig:
    version: str = field(
        default_factory=lambda: _optional("STRATEGY_VERSION", "MarketMate v2.1")
    )
    pairs: List[str] = field(
        default_factory=lambda: _optional("PAIRS", "XAUUSD,BTCUSD,ETHUSD,EURUSD").split(",")
    )
    max_trades_per_day: int   = int(_optional("MAX_TRADES_PER_DAY", "5"))
    max_trades_per_direction_per_day: int = int(
        _optional("MAX_TRADES_PER_DIRECTION_PER_DAY", "2")
    )
    min_rr:             float = float(_optional("MIN_RR", "1.5"))
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
    wait_queue_timeout_ms: int = int(_optional("MONGO_WAIT_QUEUE_TIMEOUT_MS", "5000"))
    server_timeout_ms: int = 3000


# ─── App ─────────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class AppConfig:
    env:       str  = _optional("ENV", "production")
    debug:     bool = _optional("DEBUG", "false").lower() == "true"
    log_level: str  = _optional("LOG_LEVEL", "INFO")
    scan_interval_seconds: int = int(_optional("SCAN_INTERVAL", "300"))


# ─── Delivery ────────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class DeliveryConfig:
    max_concurrent_deliveries: int = int(_optional("MAX_CONCURRENT_DELIVERIES", "5"))
    retry_delay_seconds: int = int(_optional("DELIVERY_RETRY_DELAY", "30"))
    max_retries: int = int(_optional("DELIVERY_MAX_RETRIES", "3"))
    quiet_hours_enabled: bool = _optional("DELIVERY_QUIET_HOURS", "false").lower() == "true"
    quiet_hours_start: str = _optional("DELIVERY_QUIET_HOURS_START", "22:00")
    quiet_hours_end: str = _optional("DELIVERY_QUIET_HOURS_END", "07:00")


# ─── Root Config ─────────────────────────────────────────────────────────────

@dataclass(frozen=True)
class Config:
    telegram:     TelegramConfig     = field(default_factory=TelegramConfig)
    data:         DataConfig         = field(default_factory=DataConfig)
    strategy:     StrategyConfig     = field(default_factory=StrategyConfig)
    risk:         RiskConfig         = field(default_factory=RiskConfig)
    sim:          SimConfig          = field(default_factory=SimConfig)
    mongo:        MongoConfig        = field(default_factory=MongoConfig)
    app:          AppConfig          = field(default_factory=AppConfig)
    delivery:     DeliveryConfig     = field(default_factory=DeliveryConfig)


cfg = Config()
