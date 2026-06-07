"""
marketmate.mate.query_router
──────────────────────────────
Query Router — routes MATE queries through the 7-Brain Architecture.

The router delegates to specialized brain modules instead of doing
direct DB queries. Each brain is a capability domain:

  MarketDataBrain   — price, trend, volatility, session
  SignalIntelBrain  — counts, stats, explanations, active signals
  AccountBrain      — balance, drawdown, equity, risk
  StrategyBrain     — academy, BOS/CHoCH, gates, sessions
  UserBrain         — subscription, trade history, timeline
  SystemBrain       — health, providers, diagnostics, config
  GeneralBrain      — lightweight general intelligence (20% mode)

Dual-Mode Cognition:
  Institutional Mode (80%):  Brains 1-6 — deterministic, data-driven
  Lightweight General (20%): Brain 7   — constrained LLM, no heavy retrieval

Architectural Rule:
  The LLM is the narrator. The brains are the intelligence.
  Never let the LLM answer a question if the answer exists in
  structured data.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from marketmate.core.logger import get_logger
from marketmate.mate.intent import IntentClassifier, IntentDomain, intent_classifier

log = get_logger("mate.query_router")


class QueryType:
    """Canonical query types — maintained for backward compatibility."""
    SYMBOL_STATUS          = "symbol_status"
    ACCOUNT_SUMMARY        = "account_summary"
    PERFORMANCE            = "performance"
    TRADE_HISTORY          = "trade_history"
    SYSTEM_STATUS          = "system_status"
    ACTIVE_SIGNALS         = "active_signals"
    SIGNAL_EXPLANATION     = "signal_explanation"
    PERFORMANCE_EXPLAINER  = "performance_explainer"
    AUTO_TRADE_DIAGNOSTICS = "auto_trade_diagnostics"
    PRICE_QUERY            = "price_query"
    SIGNAL_COUNT           = "signal_count"
    MARKET_SUMMARY         = "market_summary"
    STRATEGY_CONCEPT       = "strategy_concept"
    GATE_PIPELINE          = "gate_pipeline"
    SESSION_SCHEDULE       = "session_schedule"
    RISK_STATE             = "risk_state"
    USER_STATUS            = "user_status"
    GENERAL_CHAT           = "general_chat"
    HARD_NO                = "hard_no"
    HELP                   = "help"


class QueryRouter:
    """
    Routes MATE queries through the 7-Brain Architecture.

    The router accepts either:
      1. A query_type (legacy) — routes to the correct brain handler
      2. A natural language query — uses IntentClassifier to find the right brain

    Each brain is a financial cognition primitive. The router is the switchboard
    that connects questions to the right brain function.
    """

    def __init__(self) -> None:
        self._query_count: Dict[str, int] = {}

    async def route(self, query_type: str, **kwargs) -> Dict[str, Any]:
        """
        Route a query and return the result.

        Delegates to the appropriate brain function based on query_type.
        Each brain function returns structured data that the LLM narrates.

        Args:
            query_type: One of QueryType constants
            **kwargs:   Query-specific parameters (symbol, days, etc.)

        Returns:
            Dict with the query result and metadata.
        """
        self._query_count[query_type] = self._query_count.get(query_type, 0) + 1

        handlers = {
            # ── Market Data Brain ────────────────────────────────────────
            QueryType.PRICE_QUERY:            self._brain_market_price,
            QueryType.MARKET_SUMMARY:         self._brain_market_summary,

            # ── Signal Intelligence Brain ────────────────────────────────
            QueryType.SIGNAL_COUNT:           self._brain_signal_count,
            QueryType.SIGNAL_EXPLANATION:     self._brain_signal_explanation,
            QueryType.PERFORMANCE_EXPLAINER:  self._brain_performance_explainer,
            QueryType.ACTIVE_SIGNALS:         self._brain_active_signals,

            # ── Account Brain ────────────────────────────────────────────
            QueryType.ACCOUNT_SUMMARY:        self._brain_account_state,
            QueryType.RISK_STATE:             self._brain_risk_state,

            # ── Signal Intel + Account (shared) ──────────────────────────
            QueryType.PERFORMANCE:            self._brain_signal_stats,
            QueryType.SYMBOL_STATUS:          self._brain_symbol_status,

            # ── Strategy Brain ───────────────────────────────────────────
            QueryType.STRATEGY_CONCEPT:       self._brain_strategy_concept,
            QueryType.GATE_PIPELINE:          self._brain_gate_pipeline,
            QueryType.SESSION_SCHEDULE:       self._brain_session_schedule,

            # ── User Brain ───────────────────────────────────────────────
            QueryType.TRADE_HISTORY:          self._brain_trade_history,
            QueryType.USER_STATUS:            self._brain_user_status,

            # ── System Brain ─────────────────────────────────────────────
            QueryType.SYSTEM_STATUS:          self._brain_system_health,
            QueryType.AUTO_TRADE_DIAGNOSTICS: self._brain_diagnostics,

            # ── General Brain (Lightweight General Mode, 20%) ────────────
            QueryType.GENERAL_CHAT:           self._brain_general,
            QueryType.HARD_NO:                self._brain_hard_no,

            # ── Help ─────────────────────────────────────────────────────
            QueryType.HELP:                   self._brain_help,
        }

        handler = handlers.get(query_type)
        if handler is None:
            return {
                "error": f"Unknown query type: {query_type}",
                "available_types": list(handlers.keys()),
            }

        try:
            result = await handler(**kwargs)
            return {
                "query_type": query_type,
                "data": result,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as exc:
            log.error("query_router_error",
                      query_type=query_type, error=str(exc))
            return {
                "query_type": query_type,
                "error": str(exc),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def route_natural(self, query: str, **kwargs) -> Dict[str, Any]:
        """
        Route a natural language query through the full MATE pipeline.

        This is the primary entry point for MATE intelligence:
          1. Intent classification (which brain?)
          2. Entity extraction (which symbol? how many days?)
          3. Brain function call
          4. Return structured data for LLM narration
        """
        intent = await intent_classifier.classify(query)
        symbol = intent_classifier.extract_symbol(query)
        days = intent_classifier.extract_days(query)

        # Inject extracted entities into kwargs
        route_kwargs = dict(kwargs)
        if symbol and "symbol" not in route_kwargs:
            route_kwargs["symbol"] = symbol
        if days and "days" not in route_kwargs:
            route_kwargs["days"] = days
        # Always pass the original query for general brain access
        if "query" not in route_kwargs:
            route_kwargs["query"] = query

        # Map intent to QueryType
        intent_to_query_type = {
            (IntentDomain.MARKET_DATA, "get_live_price"):     QueryType.PRICE_QUERY,
            (IntentDomain.MARKET_DATA, "get_market_summary"): QueryType.MARKET_SUMMARY,
            (IntentDomain.SIGNAL_INTEL, "get_signal_count"):  QueryType.SIGNAL_COUNT,
            (IntentDomain.SIGNAL_INTEL, "get_signal_stats"):  QueryType.PERFORMANCE,
            (IntentDomain.SIGNAL_INTEL, "explain_signal"):    QueryType.SIGNAL_EXPLANATION,
            (IntentDomain.SIGNAL_INTEL, "get_active_signals"): QueryType.ACTIVE_SIGNALS,
            (IntentDomain.SIGNAL_INTEL, "get_performance_explainer"): QueryType.PERFORMANCE_EXPLAINER,
            (IntentDomain.ACCOUNT, "get_state"):              QueryType.ACCOUNT_SUMMARY,
            (IntentDomain.ACCOUNT, "get_risk_state"):         QueryType.RISK_STATE,
            (IntentDomain.STRATEGY, "explain_concept"):       QueryType.STRATEGY_CONCEPT,
            (IntentDomain.STRATEGY, "explain_gate_pipeline"):  QueryType.GATE_PIPELINE,
            (IntentDomain.STRATEGY, "get_session_schedule"):   QueryType.SESSION_SCHEDULE,
            (IntentDomain.STRATEGY, "get_strategy_params"):    QueryType.PERFORMANCE,
            (IntentDomain.USER, "get_user_status"):            QueryType.USER_STATUS,
            (IntentDomain.USER, "get_trade_history"):          QueryType.TRADE_HISTORY,
            (IntentDomain.SYSTEM, "get_system_health"):        QueryType.SYSTEM_STATUS,
            (IntentDomain.SYSTEM, "get_pipeline_diagnostics"): QueryType.AUTO_TRADE_DIAGNOSTICS,
            # ── Lightweight General Mode (20%) ──────────────────────────────
            (IntentDomain.GENERAL_CHAT, "general_response"):   QueryType.GENERAL_CHAT,
            (IntentDomain.GENERAL_CHAT, "hard_no"):            QueryType.HARD_NO,
        }

        query_type = intent_to_query_type.get(
            (intent.domain, intent.function), QueryType.GENERAL_CHAT
        )

        result = await self.route(query_type, **route_kwargs)
        result["intent"] = {
            "domain": intent.domain,
            "function": intent.function,
            "confidence": intent.confidence,
        }
        return result

    # ═════════════════════════════════════════════════════════════════════════
    # Brain Delegators — Market Data Brain
    # ═════════════════════════════════════════════════════════════════════════

    async def _brain_market_price(self, **kwargs) -> Dict[str, Any]:
        """MarketDataBrain: Get live price."""
        from marketmate.mate.brains.market_data import market_data_brain
        symbol = kwargs.get("symbol", "XAUUSD")
        return await market_data_brain.get_live_price(symbol)

    async def _brain_market_summary(self, **kwargs) -> Dict[str, Any]:
        """MarketDataBrain: Get market summary (price + trend + volatility)."""
        from marketmate.mate.brains.market_data import market_data_brain
        symbol = kwargs.get("symbol", "XAUUSD")
        return await market_data_brain.get_market_summary(symbol)

    # ═════════════════════════════════════════════════════════════════════════
    # Brain Delegators — Signal Intelligence Brain
    # ═════════════════════════════════════════════════════════════════════════

    async def _brain_signal_count(self, **kwargs) -> Dict[str, Any]:
        """SignalIntelBrain: Count signals in a time window."""
        from marketmate.mate.brains.signal_intel import signal_intel_brain
        days = kwargs.get("days", 7)
        return await signal_intel_brain.get_signal_count(days)

    async def _brain_signal_stats(self, **kwargs) -> Dict[str, Any]:
        """SignalIntelBrain: Get performance statistics."""
        from marketmate.mate.brains.signal_intel import signal_intel_brain
        days = kwargs.get("days", 30)
        return await signal_intel_brain.get_signal_stats(days)

    async def _brain_signal_explanation(self, **kwargs) -> Dict[str, Any]:
        """SignalIntelBrain: Explain a signal."""
        from marketmate.mate.brains.signal_intel import signal_intel_brain
        symbol = kwargs.get("symbol", "")
        return await signal_intel_brain.explain_signal(symbol)

    async def _brain_active_signals(self, **kwargs) -> Dict[str, Any]:
        """SignalIntelBrain: Get active signals."""
        from marketmate.mate.brains.signal_intel import signal_intel_brain
        return await signal_intel_brain.get_active_signals()

    async def _brain_performance_explainer(self, **kwargs) -> Dict[str, Any]:
        """SignalIntelBrain + AccountBrain: Explain why performance changed."""
        from marketmate.mate.brains.signal_intel import signal_intel_brain
        from marketmate.mate.brains.account import account_brain

        stats_7 = await signal_intel_brain.get_signal_stats(7)
        stats_30 = await signal_intel_brain.get_signal_stats(30)
        symbol_breakdown = await signal_intel_brain.get_per_symbol_stats()
        account = await account_brain.get_state()

        return {
            "stats_7d": stats_7,
            "stats_30d": stats_30,
            "symbol_breakdown": symbol_breakdown,
            "account": account,
        }

    async def _brain_symbol_status(self, **kwargs) -> Dict[str, Any]:
        """MarketDataBrain + SignalIntelBrain: Symbol-specific state."""
        from marketmate.mate.brains.market_data import market_data_brain
        from marketmate.mate.brains.signal_intel import signal_intel_brain
        from marketmate.mate.state_store import redis_state_store

        symbol = kwargs.get("symbol", "XAUUSD")

        # Redis fast path
        state = await redis_state_store.get_symbol_state(symbol)
        if state is not None:
            return state

        # Fallback: combine market + signal data
        market = await market_data_brain.get_live_price(symbol)
        signals = await signal_intel_brain.explain_signal(symbol)

        result = {"symbol": symbol}
        if market.get("price"):
            result["price"] = market["price"]
        if signals.get("direction"):
            result["last_signal_direction"] = signals["direction"]
            result["bias"] = signals["direction"].lower()
        if signals.get("status"):
            result["status"] = signals["status"]

        result["source"] = "brain_fallback"
        return result

    # ═════════════════════════════════════════════════════════════════════════
    # Brain Delegators — Account Brain
    # ═════════════════════════════════════════════════════════════════════════

    async def _brain_account_state(self, **kwargs) -> Dict[str, Any]:
        """AccountBrain: Get full account state."""
        from marketmate.mate.brains.account import account_brain
        return await account_brain.get_state()

    async def _brain_risk_state(self, **kwargs) -> Dict[str, Any]:
        """AccountBrain: Get risk configuration and state."""
        from marketmate.mate.brains.account import account_brain
        return await account_brain.get_risk_state()

    # ═════════════════════════════════════════════════════════════════════════
    # Brain Delegators — Strategy Brain
    # ═════════════════════════════════════════════════════════════════════════

    async def _brain_strategy_concept(self, **kwargs) -> Dict[str, Any]:
        """StrategyBrain: Explain an SMC concept."""
        from marketmate.mate.brains.strategy import strategy_brain
        concept = kwargs.get("concept", kwargs.get("symbol", ""))
        return await strategy_brain.explain_concept(concept)

    async def _brain_gate_pipeline(self, **kwargs) -> Dict[str, Any]:
        """StrategyBrain: Explain the gate pipeline."""
        from marketmate.mate.brains.strategy import strategy_brain
        return await strategy_brain.explain_gate_pipeline()

    async def _brain_session_schedule(self, **kwargs) -> Dict[str, Any]:
        """StrategyBrain: Get session schedule."""
        from marketmate.mate.brains.strategy import strategy_brain
        return await strategy_brain.get_session_schedule()

    # ═════════════════════════════════════════════════════════════════════════
    # Brain Delegators — User Brain
    # ═════════════════════════════════════════════════════════════════════════

    async def _brain_trade_history(self, **kwargs) -> Dict[str, Any]:
        """UserBrain: Get recent trade history."""
        from marketmate.mate.brains.user import user_brain
        limit = kwargs.get("limit", 10)
        return await user_brain.get_trade_history(limit)

    async def _brain_user_status(self, **kwargs) -> Dict[str, Any]:
        """UserBrain: Get user subscription status."""
        from marketmate.mate.brains.user import user_brain
        chat_id = kwargs.get("chat_id", "")
        return await user_brain.get_user_status(chat_id)

    # ═════════════════════════════════════════════════════════════════════════
    # Brain Delegators — System Brain
    # ═════════════════════════════════════════════════════════════════════════

    async def _brain_system_health(self, **kwargs) -> Dict[str, Any]:
        """SystemBrain: Get system health."""
        from marketmate.mate.brains.system import system_brain
        return await system_brain.get_system_health()

    async def _brain_diagnostics(self, **kwargs) -> Dict[str, Any]:
        """SystemBrain: Get pipeline diagnostics."""
        from marketmate.mate.brains.system import system_brain
        return await system_brain.get_pipeline_diagnostics()

    # ═════════════════════════════════════════════════════════════════════════
    # Brain Delegators — General Brain (Lightweight General Mode, 20%)
    # ═════════════════════════════════════════════════════════════════════════

    async def _brain_general(self, **kwargs) -> Dict[str, Any]:
        """GeneralBrain: Lightweight general response (20% mode)."""
        from marketmate.mate.brains.general import general_brain
        query = kwargs.get("query", kwargs.get("text", ""))
        if not query:
            return {"response": "Ask me something!", "mode": "lightweight_general"}
        return await general_brain.general_response(query)

    async def _brain_hard_no(self, **kwargs) -> Dict[str, Any]:
        """GeneralBrain: Hard NO — banned topic rejection."""
        from marketmate.mate.brains.general import general_brain
        query = kwargs.get("query", kwargs.get("text", ""))
        return await general_brain.hard_no(query)

    # ═════════════════════════════════════════════════════════════════════════
    # Help
    # ═════════════════════════════════════════════════════════════════════════

    async def _brain_help(self, **kwargs) -> Dict[str, Any]:
        """Return available query types organized by brain."""
        return {
            "market_data_brain": {
                "PRICE_QUERY": "Get live price for a symbol",
                "MARKET_SUMMARY": "Get price + trend + volatility + session",
            },
            "signal_intel_brain": {
                "SIGNAL_COUNT": "Count signals in a time window",
                "PERFORMANCE": "Get win rate, avg RR, stats",
                "SIGNAL_EXPLANATION": "Explain a signal (gate trace, BOS/CHoCH)",
                "ACTIVE_SIGNALS": "Get currently open signals",
                "PERFORMANCE_EXPLAINER": "Explain WHY performance changed",
            },
            "account_brain": {
                "ACCOUNT_SUMMARY": "Get balance, equity, drawdown",
                "RISK_STATE": "Get risk per trade, limits",
            },
            "strategy_brain": {
                "STRATEGY_CONCEPT": "Explain BOS, CHoCH, FVG, OB, sweep",
                "GATE_PIPELINE": "Explain G1-G8 gate logic",
                "SESSION_SCHEDULE": "Get London/NY session times",
            },
            "user_brain": {
                "TRADE_HISTORY": "Get recent closed trades",
                "USER_STATUS": "Get subscription status",
            },
            "system_brain": {
                "SYSTEM_STATUS": "Get system health",
                "AUTO_TRADE_DIAGNOSTICS": "Diagnose trade execution issues",
            },
            "general_brain": {
                "GENERAL_CHAT": "Lightweight general questions (20% mode)",
                "HARD_NO": "Banned topic rejection",
            },
        }

    @property
    def query_stats(self) -> Dict[str, int]:
        """Return query count by type."""
        return dict(self._query_count)


# ─── Singleton ────────────────────────────────────────────────────────────────

query_router = QueryRouter()
