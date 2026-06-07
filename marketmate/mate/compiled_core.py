"""
marketmate.mate.compiled_core
───────────────────────────────
Compiled Core — assembles minimal LLM context from the 7-Brain Architecture.

The CompiledCore is the bridge between the MATE data layer and the LLM.
It produces structured, minimal contexts that keep token usage low.

Pipeline:
  User Query
       ↓
  IntentClassifier → domain + function
       ↓
  EntityExtractor → symbol, timeframe, days
       ↓
  QueryRouter → Brain Function Call
       ↓
  Context Compilation (this file)
       ↓
  LLM Narration

The LLM is the narrator. The brains are the intelligence.
Never let the LLM answer a question if the answer exists in structured data.
"""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.mate.query_router import query_router, QueryType
from marketmate.mate.intent import intent_classifier, IntentDomain

log = get_logger("mate.compiled_core")

# System identification
SYSTEM_ID = "mate-7.0.0"
POLICY_VERSION = "2.0"


def _compute_policy_hash() -> str:
    """Compute a hash of the current strategy configuration."""
    policy = {
        "risk_per_trade": cfg.risk.risk_per_trade_pct,
        "max_trades_per_day": cfg.strategy.max_trades_per_day,
        "min_rr": cfg.strategy.min_rr,
        "pairs": sorted(cfg.strategy.pairs),
        "dedup_cooldown": cfg.strategy.dedup_cooldown_minutes,
    }
    raw = json.dumps(policy, sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:12]


class CompiledCore:
    """
    Assembles minimal LLM context from the 7-Brain Architecture.

    The CompiledCore routes natural language through the intent classifier,
    extracts entities, calls the appropriate brain, and compiles the result
    into a minimal context for LLM narration.
    """

    def __init__(self) -> None:
        self._policy_hash = _compute_policy_hash()
        self._compile_count: int = 0

    async def compile(
        self,
        query: str,
        query_type: Optional[str] = None,
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Compile a user query into a minimal LLM context.

        If query_type is provided, routes directly. Otherwise uses
        the IntentClassifier to determine the correct brain.
        """
        self._compile_count += 1

        if query_type is not None:
            # Explicit query type — route directly
            route_kwargs = dict(kwargs)
            # Extract symbol from intent classifier if not in kwargs
            if "symbol" not in route_kwargs:
                symbol = intent_classifier.extract_symbol(query)
                if symbol:
                    route_kwargs["symbol"] = symbol
            if "days" not in route_kwargs:
                days = intent_classifier.extract_days(query)
                if days:
                    route_kwargs["days"] = days
            # Pass query text for general brain (needs it for LLM prompt)
            if "query" not in route_kwargs:
                route_kwargs["query"] = query

            result = await query_router.route(query_type, **route_kwargs)
        else:
            # Natural language — route through intent classifier
            # route_natural() takes query as first positional arg and
            # internally adds it to its own kwargs for self.route().
            # Do NOT add query to route_kwargs to avoid "got multiple
            # values for argument 'query'" error.
            route_kwargs = dict(kwargs)
            route_kwargs.pop("query", None)
            result = await query_router.route_natural(query, **route_kwargs)

        # Extract the data and intent
        data = result.get("data", result.get("error", {}))
        intent = result.get("intent", {})
        detected_type = result.get("query_type", query_type or "unknown")

        # Compile into minimal format
        compiled = {
            "system_id": SYSTEM_ID,
            "policy_hash": self._policy_hash,
            "state": self._minimize_state(data),
            "query": query,
            "query_type": detected_type,
            "intent": intent,
        }

        log.debug(
            "compiled_context",
            query_type=detected_type,
            domain=intent.get("domain", ""),
            state_tokens=self._estimate_tokens(compiled["state"]),
        )

        return compiled

    def _minimize_state(self, data: Any) -> Any:
        """
        Minimize state data to keep token count low.

        Removes verbose fields, rounds numbers, and flattens
        nested structures where possible.
        """
        if isinstance(data, dict):
            minimized = {}
            for key, value in data.items():
                # Skip metadata fields that add tokens without value
                if key in ("_id", "metadata", "fetched_at",
                           "updated_at", "created_at"):
                    continue

                if isinstance(value, float):
                    minimized[key] = round(value, 4)
                elif isinstance(value, dict):
                    minimized[key] = {
                        k: round(v, 4) if isinstance(v, float) else v
                        for k, v in value.items()
                        if k not in ("_id", "metadata")
                    }
                elif isinstance(value, list):
                    # Cap lists at 5 items to keep tokens low
                    minimized[key] = value[:5]
                else:
                    minimized[key] = value
            return minimized

        return data

    def _estimate_tokens(self, data: Any) -> int:
        """Rough token estimate for a data structure."""
        text = json.dumps(data, default=str)
        return len(text) // 4

    async def get_system_prompt(self) -> str:
        """
        Return the MATE system prompt.

        This is installed ONCE at the start of an LLM session.
        Subsequent requests only send the dynamic state + query.
        """
        policy = {
            "risk_pct": cfg.risk.risk_per_trade_pct,
            "max_trades": cfg.strategy.max_trades_per_day,
            "min_rr": cfg.strategy.min_rr,
            "pairs": cfg.strategy.pairs,
        }
        return (
            f"You are MATE v{SYSTEM_ID}, a market-native financial intelligence layer.\n"
            f"You are like GitHub Copilot for trading — markets are your priority, "
            f"general questions are secondary support.\n"
            f"Policy: {json.dumps(policy)}\n"
            f"Rules:\n"
            f"- You are the narrator. The brains are the intelligence.\n"
            f"- Only report data from compiled state, never fabricate.\n"
            f"- Use exact numbers from state, do not round or estimate.\n"
            f"- If state is empty, say 'No data currently available'.\n"
            f"- Be concise: under 50 words unless user asks for detail.\n"
            f"- All balances derived from event-sourced replay.\n"
            f"- Never speculate on market conditions not in the state.\n"
        )


# ─── Singleton ────────────────────────────────────────────────────────────────

compiled_core = CompiledCore()
