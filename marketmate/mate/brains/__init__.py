"""
marketmate.mate.brains
──────────────────────
MATE 7-Brain Architecture — Financial Cognition Primitives.

Each brain is a capability domain, NOT a question handler.
Humans ask infinite questions but they ask them about finite systems.

Brains:
  1. MarketDataBrain   — live price, OHLCV, trend, volatility, session
  2. SignalIntelBrain  — signal counts, stats, active signals, explanations
  3. AccountBrain      — balance, drawdown, equity curve, risk state
  4. StrategyBrain     — academy, education, BOS/CHoCH/RR explanations
  5. UserBrain         — subscription status, trade history, timeline
  6. SystemBrain       — health, provider status, pipeline diagnostics
  7. GeneralBrain      — lightweight general intelligence (20% mode)

Dual-Mode Cognition:
  Institutional Mode (80%):  Brains 1-6 — deterministic, data-driven
  Lightweight General (20%): Brain 7   — constrained LLM, no heavy retrieval

Architectural Rule:
  NEVER let the LLM answer a question if:
    - the answer exists in structured data
    - the answer requires live state
    - the answer can be queried deterministically

  The LLM is the narrator. The brains are the intelligence.
"""

from marketmate.mate.brains.market_data import MarketDataBrain
from marketmate.mate.brains.signal_intel import SignalIntelBrain
from marketmate.mate.brains.account import AccountBrain
from marketmate.mate.brains.strategy import StrategyBrain
from marketmate.mate.brains.user import UserBrain
from marketmate.mate.brains.system import SystemBrain
from marketmate.mate.brains.general import GeneralBrain

__all__ = [
    "MarketDataBrain",
    "SignalIntelBrain",
    "AccountBrain",
    "StrategyBrain",
    "UserBrain",
    "SystemBrain",
    "GeneralBrain",
]
