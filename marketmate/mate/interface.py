"""
marketmate.mate.interface
──────────────────────────
MATE Interface — the public AI interface for MarketMate.

This is the single entry point for all AI interactions. It:
  1. Accepts natural language queries
  2. Routes through IntentClassifier → Brain → Context
  3. Sends compiled state to the LLM as narrator
  4. Returns the response

Dual-Mode Cognition:
  Institutional Mode (80%): Market is priority
    - Uses Redis, MongoDB, event streams, repositories, live market data
    - LLM only narrates — never answers if data exists

  Lightweight General Mode (20%): General is minimal
    - Uses constrained LLM directly — no heavy retrieval
    - Short responses, tight token budget
    - Like GitHub Copilot: coding is priority, general is secondary

  The LLM is the narrator. The brains are the intelligence.
  Never let the LLM answer a question if the answer exists in structured data.

7 Brains:
  MarketDataBrain   — price, trend, volatility, session
  SignalIntelBrain  — counts, stats, explanations, active
  AccountBrain      — balance, drawdown, equity, risk
  StrategyBrain     — academy, BOS/CHoCH, gates, sessions
  UserBrain         — subscription, trade history, timeline
  SystemBrain       — health, providers, diagnostics, config
  GeneralBrain      — lightweight general intelligence (20% mode)
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger
from marketmate.mate.compiled_core import compiled_core
from marketmate.mate.intent import IntentDomain

log = get_logger("mate.interface")


# ═════════════════════════════════════════════════════════════════════════════
# Brain-Aware System Prompts
# ═════════════════════════════════════════════════════════════════════════════

BRAIN_SYSTEM_PROMPTS = {
    # ── Market Data Brain ────────────────────────────────────────────────────
    IntentDomain.MARKET_DATA: (
        "You are MATE, a market intelligence interface. Report prices, trends, and "
        "market movement from compiled state only. State the price clearly with the "
        "symbol name. Include open/high/low if available. Describe trend direction "
        "and volatility if present. Do NOT speculate on price direction or future movement. "
        "Keep it factual and concise. Under 50 words for price queries, 80 for summaries."
    ),

    # ── Signal Intelligence Brain ────────────────────────────────────────────
    IntentDomain.SIGNAL_INTEL: (
        "You are MATE, a signal intelligence interface. Report signal counts, win rates, "
        "and trade statistics from compiled state. State exact numbers: total signals, "
        "wins, losses, open trades, win rate. For signal explanations, cite gate trace, "
        "sweep, BOS/CHoCH, and RR data from state. For performance explainer, identify "
        "patterns from the breakdown data. Do NOT estimate. Under 80 words."
    ),

    # ── Account Brain ────────────────────────────────────────────────────────
    IntentDomain.ACCOUNT: (
        "You are MATE, an account intelligence interface. Report balance, drawdown, "
        "equity, and risk state from compiled state. Use exact numbers. Include "
        "consecutive losses and drawdown pause status if available. Do NOT speculate "
        "on account trajectory. Under 50 words."
    ),

    # ── Strategy Brain ───────────────────────────────────────────────────────
    IntentDomain.STRATEGY: (
        "You are MATE, a strategy education interface. Explain SMC concepts clearly "
        "using the definitions from compiled state. For gate pipeline questions, explain "
        "the G1-G8 filter sequence. For session questions, state the exact times. "
        "Be educational but concise. Under 100 words for concepts, 80 for pipeline/sessions."
    ),

    # ── User Brain ───────────────────────────────────────────────────────────
    IntentDomain.USER: (
        "You are MATE, a user account interface. Report subscription status, trade "
        "history, and user timeline from compiled state. State exact dates and status. "
        "Do NOT reveal sensitive information. Under 60 words."
    ),

    # ── System Brain ─────────────────────────────────────────────────────────
    IntentDomain.SYSTEM: (
        "You are MATE, a system diagnostics interface. Report system health, provider "
        "status, and pipeline diagnostics from compiled state. For trade diagnostics, "
        "cite specific gate numbers and rejection reasons. Do NOT speculate. "
        "Format: [Check]: [Result]. Under 80 words."
    ),

    # ── General Brain (Lightweight General Mode, 20%) ────────────────────────
    IntentDomain.GENERAL_CHAT: (
        "You are MATE, a market-native AI that also helps with general questions. "
        "Keep it brief — under 80 words. If the question is even slightly market-related, "
        "give a market-flavored answer. Never provide therapy, relationship advice, "
        "or medical guidance. Never roleplay. For coding questions, be concise and practical. "
        "You CAN act as a coding assistant or analyst — those are capabilities, not roleplay."
    ),
}

# Default system prompt (fallback)
DEFAULT_SYSTEM_PROMPT = (
    "You are MATE, a concise financial intelligence interface over MarketMate's "
    "7-Brain Architecture. Report ONLY compiled state data. Never fabricate. "
    "Use exact numbers. If state is empty, say 'No data currently available'. "
    "Be concise: under 50 words unless asked for detail."
)

# Query-type specific prompt overrides (for backward compat and fine-tuning)
QUERY_TYPE_PROMPTS = {
    "signal_explanation": (
        "You are MATE, explaining a trade signal from the MarketMate SMC pipeline. "
        "Use ONLY the gate trace, sweep, BOS/CHoCH, HTF bias, zone type, and RR data "
        "from compiled state. Be specific: cite which gate passed/failed, what type of "
        "sweep, what type of confirmation. Format: [Pipeline Step]: [State Data]. Under 100 words."
    ),
    "performance_explainer": (
        "You are MATE, explaining WHY performance changed. Use ONLY the compiled state: "
        "7d vs 30d stats, symbol breakdown, direction breakdown. Identify patterns: "
        "which symbols are losing, which direction is weaker, whether RR is compressing. "
        "Cite exact numbers. Under 100 words."
    ),
    "auto_trade_diagnostics": (
        "You are MATE, diagnosing why a trade was or wasn't executed. Use ONLY the "
        "compiled state: open trades count, account status, gate rejection reasons, "
        "system limits. Cite specific gate numbers. Format: [Check]: [Result]. Under 80 words."
    ),
    "price_query": (
        "You are MATE, reporting a live price. State the price clearly with the symbol "
        "name. Include open/high/low if available. Do NOT speculate on direction. Under 30 words."
    ),
    "market_summary": (
        "You are MATE, providing a market summary. Report price, trend, volatility, "
        "recent structure, and session context from compiled state. Be factual and "
        "institutional. Under 80 words."
    ),
    "signal_count": (
        "You are MATE, reporting signal counts. State exact numbers: total signals, "
        "wins, losses, open trades, win rate. Do NOT estimate. Under 50 words."
    ),
    "strategy_concept": (
        "You are MATE, explaining an SMC concept. Use the definition from compiled "
        "state. Be clear and educational. Under 100 words."
    ),
    "general_chat": (
        "You are MATE, a market-native intelligence that also handles general questions. "
        "Be brief (under 80 words). Market-flavored answers when possible. No therapy, "
        "roleplay, or medical advice. Practical and efficient. You CAN help with coding."
    ),
    "hard_no": (
        "You are MATE. Politely but firmly decline. You are a market-native intelligence. "
        "State what you CAN help with: markets, signals, trading, strategy. Under 40 words."
    ),
}


class MATEInterface:
    """
    The public AI interface for MarketMate.

    Usage:
        mate = MATEInterface()
        response = await mate.ask("What's gold's current price?")
        response = await mate.ask("How many signals last week?")
        response = await mate.ask("Explain BOS")
    """

    def __init__(self) -> None:
        self._session_active = False
        self._query_count: int = 0
        self._system_prompt_installed = False

    async def ask(
        self,
        query: str,
        query_type: Optional[str] = None,
        mode: str = "compiled",
        **kwargs,
    ) -> Dict[str, Any]:
        """
        Ask MATE a question and get an AI-generated response.

        v3 Architecture: Tool-Calling Agent (primary) + Legacy fallback.

        The LLM IS the router. It decides which tools (brains) to call
        based on the user's query. No keyword lists. No hardcoded routing.

        If tool-calling fails (rate limits, errors), falls back to the
        legacy keyword-based routing system.

        Args:
            query:      Natural language question
            query_type: Optional explicit query type (legacy)
            mode:       "compiled" (default) or "direct"
            **kwargs:   Additional parameters (chat_id for user queries)

        Returns:
            Dict with response, metadata, and token usage info.
        """
        self._query_count += 1

        try:
            # ── Primary: Tool-Calling Agent ────────────────────────────────
            # The LLM decides what to do. Tools = brains.
            if query_type is None:
                try:
                    from marketmate.mate.agent import mate_agent

                    chat_id = kwargs.get("chat_id", "")
                    agent_result = await mate_agent.ask(query=query, chat_id=chat_id)

                    # Determine query_type from tool calls for logging/display
                    tool_calls = agent_result.get("tool_calls", [])
                    if tool_calls:
                        detected_type = tool_calls[0].get("tool", "tool_call")
                    else:
                        detected_type = "general_chat"

                    return {
                        "response": agent_result["response"],
                        "query": query,
                        "query_type": detected_type,
                        "intent": {
                            "domain": "agent" if tool_calls else "general_chat",
                            "function": "tool_call" if tool_calls else "direct",
                            "confidence": 1.0,
                        },
                        "mode": agent_result.get("mode", "agent"),
                        "tool_calls": tool_calls,
                        "timestamp": datetime.now(timezone.utc).isoformat(),
                    }
                except Exception as exc:
                    log.warning(
                        "mate_agent_fallback",
                        error=str(exc),
                        hint="Falling back to legacy keyword routing",
                    )

            # ── Fallback: Legacy keyword-based routing ─────────────────────
            # Used when: explicit query_type given, or agent fails
            compiled = await compiled_core.compile(
                query=query,
                query_type=query_type,
                **kwargs,
            )

            detected_type = compiled.get("query_type", "unknown")
            intent = compiled.get("intent", {})
            domain = intent.get("domain", "")

            # ── Dual-Mode Routing ────────────────────────────────────────────
            # Lightweight General Mode (20%): bypass compiled state narration
            # General brain already returns a response directly
            if domain == IntentDomain.GENERAL_CHAT:
                state = compiled.get("state", {})
                # General brain returns {"response": "...", "mode": "..."}
                if isinstance(state, dict) and state.get("response"):
                    response = state["response"]
                else:
                    # Fallback: use LLM with general system prompt
                    response = await self._send_to_llm(compiled)

                return {
                    "response": response,
                    "query": query,
                    "query_type": detected_type,
                    "intent": intent,
                    "mode": "lightweight_general",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # Hard NO: immediate rejection, no LLM needed
            if detected_type == "hard_no":
                state = compiled.get("state", {})
                response = (
                    state.get("response", "")
                    if isinstance(state, dict)
                    else ""
                ) or "I'm MATE — a market-native intelligence. I focus on markets, signals, and trading strategy. I can't help with that topic."

                return {
                    "response": response,
                    "query": query,
                    "query_type": detected_type,
                    "intent": intent,
                    "mode": "hard_no",
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                }

            # ── Institutional Mode (80%): full compiled state → LLM narration
            if mode == "compiled":
                response = await self._send_to_llm(compiled)
            else:
                response = await self._send_direct(query)

            return {
                "response": response,
                "query": query,
                "query_type": detected_type,
                "intent": intent,
                "mode": mode,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

        except Exception as exc:
            log.error("mate_ask_failed", query=query, error=str(exc))
            return {
                "response": "I encountered an error processing your query. Please try again.",
                "error": str(exc),
                "query": query,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def _send_to_llm(self, compiled: Dict[str, Any]) -> str:
        """
        Send compiled state to the LLM as narrator.

        The LLM receives:
          1. A brain-specific system prompt (tells it how to narrate)
          2. The compiled state (the actual data)
          3. The user's query (what they asked)

        The LLM is NEVER the intelligence source. It only formats.
        """
        try:
            from marketmate.core.llm import llm_provider

            query_type = compiled.get("query_type", "")
            intent = compiled.get("intent", {})
            domain = intent.get("domain", "")

            # Select system prompt: query-type specific → brain-specific → default
            system = QUERY_TYPE_PROMPTS.get(query_type)
            if not system:
                system = BRAIN_SYSTEM_PROMPTS.get(domain, DEFAULT_SYSTEM_PROMPT)

            # Build the prompt from compiled state
            domain_label = domain.replace("_", " ").title() if domain else "General"
            prompt = (
                f"[MATE {compiled['system_id']} | brain:{domain_label} | "
                f"policy:{compiled['policy_hash']}]\n"
                f"State: {compiled['state']}\n"
                f"Query: {compiled['query']}"
            )

            # Token limits by brain domain
            token_limits = {
                IntentDomain.MARKET_DATA: 150,
                IntentDomain.SIGNAL_INTEL: 200,
                IntentDomain.ACCOUNT: 150,
                IntentDomain.STRATEGY: 250,
                IntentDomain.USER: 150,
                IntentDomain.SYSTEM: 200,
                IntentDomain.GENERAL_CHAT: 200,
            }
            max_tokens = token_limits.get(domain, 150)

            # Higher limits for explanation types
            if query_type in ("signal_explanation", "performance_explainer",
                            "auto_trade_diagnostics"):
                max_tokens = 300

            response = await llm_provider.chat(
                system_prompt=system,
                user_prompt=prompt,
                max_tokens=max_tokens,
                temperature=0.3,
            )
            return response.strip() if response else "No response generated."

        except Exception as exc:
            log.warning("mate_llm_failed", error=str(exc))
            return self._format_state_response(compiled)

    async def _send_direct(self, query: str) -> str:
        """Send a query directly to the LLM (admin mode)."""
        try:
            from marketmate.core.llm import llm_provider
            response = await llm_provider.chat(
                system_prompt=DEFAULT_SYSTEM_PROMPT,
                user_prompt=query,
                max_tokens=300,
                temperature=0.5,
            )
            return response.strip() if response else "No response generated."
        except Exception as exc:
            return f"LLM unavailable: {exc}"

    def _format_state_response(self, compiled: Dict[str, Any]) -> str:
        """Format compiled state into a human-readable response when LLM is unavailable."""
        state = compiled.get("state", {})

        if not state:
            return "No data currently available for this query."

        lines = []
        for key, value in state.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    lines.append(f"{sub_key}: {sub_value}")
            else:
                lines.append(f"{key}: {value}")

        return "\n".join(lines[:10])

    async def install_system_prompt(self) -> str:
        """Install the MATE system prompt for the current LLM session."""
        prompt = await compiled_core.get_system_prompt()
        self._system_prompt_installed = True
        self._session_active = True
        return prompt

    @property
    def status(self) -> Dict[str, Any]:
        """Return MATE interface status."""
        return {
            "session_active": self._session_active,
            "system_prompt_installed": self._system_prompt_installed,
            "total_queries": self._query_count,
            "system_id": "mate-9.0.0",
            "architecture": "8-brain",
            "brains": [
                "market_data", "signal_intel", "account",
                "strategy", "user", "system", "general", "state_intel",
            ],
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

mate_interface = MATEInterface()
