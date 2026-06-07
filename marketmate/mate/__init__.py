"""
marketmate.mate
───────────────
MATE Intelligence Layer — a compiled financial OS with AI interface.

The MATE layer NEVER touches raw DB queries. It only reads precomputed
structured outputs (Redis state + MongoDB metrics) and compiles them
into a minimal context for LLM consumption.

7-Brain Architecture (v7.0.0):
  Each brain is a capability domain, NOT a question handler.
  Humans ask infinite questions but they ask them about finite systems.

  1. MarketDataBrain   — price, trend, volatility, session
  2. SignalIntelBrain  — counts, stats, explanations, active signals
  3. AccountBrain      — balance, drawdown, equity, risk state
  4. StrategyBrain     — academy, BOS/CHoCH, gates, sessions
  5. UserBrain         — subscription, trade history, timeline
  6. SystemBrain       — health, providers, diagnostics, config
  7. GeneralBrain      — lightweight general intelligence (20% mode)

Dual-Mode Cognition:
  Institutional Mode (80%):  Brains 1-6 — deterministic, data-driven
  Lightweight General (20%): Brain 7   — constrained LLM, no heavy retrieval

  Market is ALWAYS priority. General is minimal support.
  Like GitHub Copilot: coding is priority, general is secondary.

Pipeline:
  User Query
       ↓
  IntentClassifier → domain + function
       ↓
  EntityExtractor → symbol, timeframe, days
       ↓
  QueryRouter → Brain Function Call
       ↓
  Context Compiler → minimal structured state
       ↓
  LLM Narration

Critical Rule:
  Never let the LLM answer a question if:
    - the answer exists in structured data
    - the answer requires live state
    - the answer can be queried deterministically

  The LLM is the narrator. The brains are the intelligence.
"""

from marketmate.mate.state_store import RedisStateStore
from marketmate.mate.pipeline import EventStatePipeline
from marketmate.mate.query_router import QueryRouter, QueryType
from marketmate.mate.compiled_core import CompiledCore
from marketmate.mate.interface import MATEInterface
from marketmate.mate.intent import IntentClassifier, IntentDomain
from marketmate.mate.brains.general import GeneralBrain

__all__ = [
    "RedisStateStore",
    "EventStatePipeline",
    "QueryRouter",
    "QueryType",
    "CompiledCore",
    "MATEInterface",
    "IntentClassifier",
    "IntentDomain",
    "GeneralBrain",
]
