"""
MarketMate Python SDK
~~~~~~~~~~~~~~~~~~~~~

Official Python client for the MarketMate API.

Real-time market intelligence infrastructure for traders, developers,
and automated systems. Convert live market structure into machine-readable
intelligence.

Usage::

    from marketmate import MarketMate

    client = MarketMate(api_key="mk_live_...")

    # Get real-time market state
    state = client.get_market_state("BTC-USD")
    print(f"Regime: {state.regime}, Conviction: {state.conviction}")

    # Get active signals
    signals = client.get_signals()
    for signal in signals:
        print(f"{signal.symbol} {signal.direction} @ {signal.entry_zone}")

    # Get liquidity analysis
    liquidity = client.get_liquidity("BTC-USD")
    print(f"Liquidity score: {liquidity.score}")

    # Get historical data
    history = client.get_historical("BTC-USD", hours=24)
    for point in history.data:
        print(f"{point.timestamp}: {point.regime} @ {point.close}")

:copyright: (c) 2024 MarketMate
:license: MIT
"""

__version__ = "2.1.0"
__author__ = "MarketMate"

from marketmate.client import MarketMate
from marketmate.models import (
    MarketState,
    Signal,
    SignalsResponse,
    LiquidityAnalysis,
    HistoricalDataPoint,
    HistoricalResponse,
    ErrorResponse,
)

__all__ = [
    "MarketMate",
    "MarketState",
    "Signal",
    "SignalsResponse",
    "LiquidityAnalysis",
    "HistoricalDataPoint",
    "HistoricalResponse",
    "ErrorResponse",
]
