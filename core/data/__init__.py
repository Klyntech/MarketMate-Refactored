"""
marketmate.data
───────────────
Unified market data package for MarketMate.

Re-exports the most commonly used items so that downstream modules
can import from the package root:

    from signal_engine.data import MarketDataEngine, fetch_ohlcv

All other items remain available via their full module path:

    from signal_engine.data.providers.binance import BinanceProvider
    from signal_engine.data.validators import validate_ohlcv
    from signal_engine.data.transformers import resample_candles
    from signal_engine.data.cache import warm_cache

Architecture Overview
─────────────────────
  MarketDataEngine          ← main entry point
      ├── providers/        ← pluggable data sources
      │   ├── base.py       ← DataProvider ABC
      │   ├── binance.py    ← Binance REST klines
      │   ├── alpha_vantage.py  ← Alpha Vantage (with 1h→4h resample)
      │   └── twelve_data.py    ← Twelve Data time series
      ├── cache.py          ← MongoDB-backed candle warehouse
      ├── validators.py     ← OHLCV integrity + cross-source validation
      └── transformers.py   ← Resampling, normalization, timezone handling

Migration from Legacy Code
──────────────────────────
  data/market_data.py      → marketmate/data/engine.py + providers/
  data/candle_store.py     → marketmate/data/cache.py
  data/validators.py       → marketmate/data/validators.py (merged)
  services/data_validator.py → marketmate/data/validators.py (merged)

The ``fetch_ohlcv()`` function signature is preserved for backward
compatibility during migration.
"""

# ── Engine (primary entry point) ──────────────────────────────────────────────
from signal_engine.data.engine import MarketDataEngine, fetch_ohlcv

# ── Providers ─────────────────────────────────────────────────────────────────
from signal_engine.data.providers.base import DataProvider, SYMBOL_MAP
from signal_engine.data.providers.binance import BinanceProvider
from signal_engine.data.providers.alpha_vantage import AlphaVantageProvider
from signal_engine.data.providers.twelve_data import TwelveDataProvider
from signal_engine.data.providers import PROVIDER_CLASSES, get_available_providers

# ── Validators ────────────────────────────────────────────────────────────────
from signal_engine.data.validators import (
    validate_ohlcv,
    validate_freshness,
    validate_weekly_data,
    REQUIRED_COLUMNS,
    MAX_CLOSE_CHANGE_PCT,
    MIN_CANDLES,
)

# ── Transformers ──────────────────────────────────────────────────────────────
from signal_engine.data.transformers import (
    resample_candles,
    normalize_outputs,
    handle_timezone,
    CANONICAL_COLUMNS,
)

# ── Cache ─────────────────────────────────────────────────────────────────────
from signal_engine.data.cache import (
    get_candles,
    store_live_candles,
    warm_cache,
    check_candle_freshness,
    connect as cache_connect,
    FRESHNESS_THRESHOLDS,
    DEFAULT_FRESHNESS,
)

__all__ = [
    # Engine
    "MarketDataEngine",
    "fetch_ohlcv",
    # Providers
    "DataProvider",
    "SYMBOL_MAP",
    "BinanceProvider",
    "AlphaVantageProvider",
    "TwelveDataProvider",
    "PROVIDER_CLASSES",
    "get_available_providers",
    # Validators
    "validate_ohlcv",
    "validate_freshness",
    "validate_weekly_data",
    "REQUIRED_COLUMNS",
    "MAX_CLOSE_CHANGE_PCT",
    "MIN_CANDLES",
    # Transformers
    "resample_candles",
    "normalize_outputs",
    "handle_timezone",
    "CANONICAL_COLUMNS",
    # Cache
    "get_candles",
    "store_live_candles",
    "warm_cache",
    "check_candle_freshness",
    "cache_connect",
    "FRESHNESS_THRESHOLDS",
    "DEFAULT_FRESHNESS",
]
