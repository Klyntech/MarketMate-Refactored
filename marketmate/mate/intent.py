"""
marketmate.mate.intent
──────────────────────
Intent Classifier — routes natural language to the correct MATE brain.

This is the brainstem of MATE. It maps infinite human questions
to 7 finite capability domains. Not question handlers — capability domains.

Classification Strategy (v2 — LLM-first):
  1. HARD_NO fast-path: keyword check (safety gate, no LLM needed)
  2. LLM classification: the LLM understands context, phrasing, and nuance
     that keywords can never capture. No more adding keywords endlessly.
  3. Keyword fallback: if LLM fails or returns invalid output, the original
     keyword system catches it. This is the safety net.

Guardrails (so the LLM doesn't get carried away):
  - Output validated against VALID_INTENTS — only known (domain, function) pairs
  - Very low temperature (0.1) for deterministic classification
  - Very short max_tokens (80) — no room to wander
  - Confidence threshold — if LLM is unsure (< 0.5), fall back
  - Entity extraction stays deterministic — no hallucinated symbols/days

7 Capability Domains (Brains):
  MARKET_DATA     -> MarketDataBrain   -- price, trend, volatility, session
  SIGNAL_INTEL    -> SignalIntelBrain  -- counts, stats, explanations, active
  ACCOUNT         -> AccountBrain      -- balance, drawdown, equity, risk
  STRATEGY        -> StrategyBrain     -- academy, BOS/CHoCH, gates, sessions
  USER            -> UserBrain         -- subscription, trade history, timeline
  SYSTEM          -> SystemBrain       -- health, providers, diagnostics, config
  GENERAL_CHAT    -> GeneralBrain      -- lightweight general intelligence

Critical Rule:
  Never let the LLM answer a question if the answer exists in
  structured data. The LLM is the narrator. The brains are the intelligence.

Symbol Support:
  XAUUSD, XAGUSD, EURUSD, GBPUSD, USDJPY, BTCUSD, ETHUSD + aliases
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Optional, Set, Tuple

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger

log = get_logger("mate.intent")

# ── Feature flag: enable/disable LLM classification ──────────────────────────
# Set MATE_LLM_CLASSIFY=false to disable LLM classification and use keywords only
_LLM_CLASSIFY_ENABLED = os.environ.get("MATE_LLM_CLASSIFY", "true").lower() in ("true", "1", "yes")


# ═════════════════════════════════════════════════════════════════════════════
# Intent Domain Constants
# ═════════════════════════════════════════════════════════════════════════════

class IntentDomain:
    """The 7 capability domains — NOT question types.

    Domains 1-6 are Institutional Mode (80% priority).
    Domain 7 is Lightweight General Mode (20% — like GitHub Copilot).

    MATE is market-native intelligence that ALSO understands general conversation.
    Market is ALWAYS priority. General is minimal support.
    """
    # ── Institutional Mode (80%) ────────────────────────────────────────────
    MARKET_DATA  = "market_data"
    SIGNAL_INTEL = "signal_intel"
    ACCOUNT      = "account"
    STRATEGY     = "strategy"
    USER         = "user"
    SYSTEM       = "system"

    # ── Lightweight General Mode (20%) ──────────────────────────────────────
    GENERAL_CHAT = "general_chat"


# ═════════════════════════════════════════════════════════════════════════════
# Intent Data
# ═════════════════════════════════════════════════════════════════════════════

@dataclass
class Intent:
    """
    The result of intent classification.

    Attributes:
        domain:     Which brain to route to (one of IntentDomain)
        function:   Which brain function to call
        confidence: How confident the classifier is (0.0 - 1.0)
    """
    domain: str
    function: str
    confidence: float = 1.0


# ═════════════════════════════════════════════════════════════════════════════
# LLM Intent Classification Prompt
# ═════════════════════════════════════════════════════════════════════════════

INTENT_CLASSIFICATION_SYSTEM = (
    "You are a precise intent classifier for MATE, a market-native trading intelligence system. "
    "Classify the user's query into exactly one of the listed categories. "
    "Respond ONLY with a JSON object. No explanation, no markdown, no extra text."
)

INTENT_CLASSIFICATION_PROMPT = """Classify this user query for MATE (a trading intelligence system).

AVAILABLE INTENTS (pick exactly one):
1. market_data / get_live_price — asking for a current/live price of an asset
2. market_data / get_market_summary — asking about market overview, trend, direction, what's happening, what's trading
3. signal_intel / get_signal_count — asking how many signals/trades there are
4. signal_intel / get_signal_stats — asking about win rate, performance, accuracy, track record
5. signal_intel / explain_signal — asking why a signal was generated or why a trade was taken
6. signal_intel / get_active_signals — asking about currently open/active signals/trades/positions
7. signal_intel / get_performance_explainer — asking WHY performance changed, why losses, what went wrong
8. account / get_state — asking about balance, equity, drawdown, funds, account info
9. account / get_risk_state — asking about risk per trade, lot size, position sizing
10. strategy / explain_concept — asking about a trading concept (candlestick, BOS, CHoCH, FVG, order block, sweep, liquidity, smart money, etc.)
11. strategy / explain_gate_pipeline — asking about the signal generation pipeline/gates
12. strategy / get_session_schedule — asking about trading session times/hours/schedule
13. strategy / get_strategy_params — asking about strategy configuration/parameters
14. user / get_user_status — asking about subscription, account status, expiry
15. user / get_trade_history — asking about past trades, trade history, trade log
16. system / get_system_health — asking about system status, health, uptime, providers
17. system / get_pipeline_diagnostics — asking why a trade wasn't executed, auto-trade issues
18. general_chat / general_response — general conversation, greetings, off-topic questions, non-market questions, coding help, capability questions
19. general_chat / hard_no — ONLY for: relationship/therapy, roleplay pretense, politics, war, consciousness claims, writing papers

CLASSIFICATION RULES (READ CAREFULLY):
- Market questions ALWAYS get priority over general_chat
- "What's trading?", "How's the market?", "What's happening?" -> market_data / get_market_summary
- Questions about trading concepts (candlestick, support, resistance, etc.) -> strategy / explain_concept
- Questions about movies, sports, weather, or anything non-trading -> general_chat / general_response
- "How many signals?" -> signal_intel / get_signal_count
- "Win rate?" or "How am I doing?" -> signal_intel / get_signal_stats
- Greetings, casual chat -> general_chat / general_response
- Coding questions, tech help -> general_chat / general_response

CRITICAL — WHEN TO USE hard_no vs general_response:
  Use hard_no ONLY for these specific banned topics:
  - Relationship/therapy: "my girlfriend", "relationship advice", "my wife left me"
  - Roleplay pretense: "pretend you are a pirate", "roleplay as my girlfriend", "act as if you're a dog"
  - Political/war: "who should I vote for", "politics in Nigeria", "war in Ukraine"
  - Consciousness: "are you sentient", "do you have feelings"
  - Infinite writing: "write my thesis", "write a novel for me"

  Use general_response for EVERYTHING else, including:
  - "Can you be my coding agent" -> general_response (asking for coding help, NOT roleplay)
  - "Can you help me code" -> general_response
  - "Be my assistant" -> general_response (capability request, NOT roleplay)
  - "Can you debug this" -> general_response
  - "Top 10 movies" -> general_response (off-topic but not banned)
  - "What's the weather" -> general_response
  - "Tell me a joke" -> general_response

  KEY DISTINCTION: Asking MATE to USE its capabilities (coding, analysis, help) = general_response.
  Only asking MATE to PRETEND to be something it's not = hard_no.

User query: "{query}"

Respond ONLY with valid JSON: {{"domain": "...", "function": "...", "confidence": 0.0-1.0}}"""


# ═════════════════════════════════════════════════════════════════════════════
# Valid Intent Set — guardrail for LLM output validation
# ═════════════════════════════════════════════════════════════════════════════

VALID_INTENTS: Set[Tuple[str, str]] = {
    (IntentDomain.MARKET_DATA, "get_live_price"),
    (IntentDomain.MARKET_DATA, "get_market_summary"),
    (IntentDomain.SIGNAL_INTEL, "get_signal_count"),
    (IntentDomain.SIGNAL_INTEL, "get_signal_stats"),
    (IntentDomain.SIGNAL_INTEL, "explain_signal"),
    (IntentDomain.SIGNAL_INTEL, "get_active_signals"),
    (IntentDomain.SIGNAL_INTEL, "get_performance_explainer"),
    (IntentDomain.ACCOUNT, "get_state"),
    (IntentDomain.ACCOUNT, "get_risk_state"),
    (IntentDomain.STRATEGY, "explain_concept"),
    (IntentDomain.STRATEGY, "explain_gate_pipeline"),
    (IntentDomain.STRATEGY, "get_session_schedule"),
    (IntentDomain.STRATEGY, "get_strategy_params"),
    (IntentDomain.USER, "get_user_status"),
    (IntentDomain.USER, "get_trade_history"),
    (IntentDomain.SYSTEM, "get_system_health"),
    (IntentDomain.SYSTEM, "get_pipeline_diagnostics"),
    (IntentDomain.GENERAL_CHAT, "general_response"),
    (IntentDomain.GENERAL_CHAT, "hard_no"),
}


# ═════════════════════════════════════════════════════════════════════════════
# Intent Classifier
# ═════════════════════════════════════════════════════════════════════════════

class IntentClassifier:
    """
    Classifies natural language into MATE brain domains and functions.

    v2 Architecture: LLM-first with keyword fallback.

    The LLM understands context and nuance that keywords never will.
    "Whats Candlestick?" -> strategy/explain_concept (not general_chat)
    "What's trading?" -> market_data/get_market_summary (not signal_intel)
    "Top 10 movies" -> general_chat/general_response (not market_data)

    But the LLM is constrained:
    - It can ONLY return intents from the VALID_INTENTS set
    - If it returns garbage, the keyword system catches it
    - Entity extraction (symbol, days) stays deterministic
    """

    # ── Keyword lists (retained as fallback) ───────────────────────────────

    # PRICE queries — highest priority (most common user question)
    PRICE_KEYWORDS = [
        "price", "current price", "what's the price", "whats the price",
        "how much is", "trading at", "quoted at", "spot price", "live price",
        "how much does", "what is the price",
        "what's it at", "whats it at", "where is", "where's",
    ]

    # MARKET SUMMARY queries (trend, movement, behavior)
    MARKET_SUMMARY_KEYWORDS = [
        "how has", "how is", "faring", "fairing", "performing",
        "trend", "direction", "bullish", "bearish",
        "moving", "movement", "behaving", "behavior",
        "what happened", "what's happening", "market summary",
        "what's trading", "whats trading", "what is trading",
        "what's the market", "whats the market", "what is the market",
        "market update", "market overview", "market status",
        "how's the market", "hows the market",
        "what's going on with", "whats going on with",
        "show me the market", "give me a market",
        "what's looking good", "whats looking good",
        "what's hot", "whats hot", "anything moving",
        "what are we trading", "what pairs are",
        "how are things", "how's things",
    ]

    # SIGNAL COUNT / STATS queries
    SIGNAL_COUNT_KEYWORDS = [
        "how many signals", "signal count", "how many trade",
        "signals given", "how many were given", "total signals",
        "signals last week", "signals this week", "signals last month",
        "how many signals were", "how many were given last",
        "how many", "signal_count",
        "any signals", "any trades today", "any signals today",
        "any open signals", "any active signals",
    ]

    # SIGNAL EXPLANATION queries
    SIGNAL_EXPLAIN_KEYWORDS = [
        "why was this signal", "explain this signal", "explain the signal",
        "why was this generated", "why did this trigger", "how was this signal",
        "why this trade", "explain this trade", "explain this setup",
        "why was gold", "why was eurusd", "why did xauusd",
        "gate trace", "what triggered", "why no signal",
    ]

    # WIN RATE / PERFORMANCE queries
    PERFORMANCE_KEYWORDS = [
        "win rate", "winrate", "performance", "profit", "accuracy",
        "stats", "track record", "results", "how am i doing",
        "pnl", "return",
    ]

    # PERFORMANCE EXPLAINER queries ("why" + performance)
    PERF_EXPLAIN_KEYWORDS = [
        "why did performance", "why is win rate", "why performance dropped",
        "why did performance drop", "performance drop", "why am i losing",
        "why losing", "why so many losses", "what went wrong",
        "strategy degrad", "why fewer signals", "why less signals",
    ]

    # ACCOUNT / BALANCE queries
    ACCOUNT_KEYWORDS = [
        "balance", "account", "equity", "funds", "money",
        "drawdown", "dd", "deposit", "margin",
    ]

    # RISK queries
    RISK_KEYWORDS = [
        "risk", "risk per trade", "how much risk", "lot size",
        "position size", "risk amount",
    ]

    # STRATEGY / ACADEMY queries
    STRATEGY_KEYWORDS = [
        "what is bos", "explain bos", "what is choch", "explain choch",
        "what is fvg", "explain fvg", "what is an order block", "explain order block",
        "what is a sweep", "explain sweep", "what is liquidity",
        "how does rr work", "risk reward", "explain rr",
        "what is htf", "higher timeframe", "smart money",
        "smc", "academy", "learn", "teach", "education",
        "how does the strategy", "how does marketmate", "how are signals",
        "gate pipeline", "g1 g2 g3", "how does signal generation",
        "session schedule", "when does", "trading hours", "scan hours",
    ]

    # AUTO-TRADE DIAGNOSTICS queries
    AUTOTRADE_KEYWORDS = [
        "why wasn't this trade executed", "why wasn't this executed",
        "why no trade", "why wasn't this trade", "trade rejected",
        "why rejected", "why not executed", "auto-trade",
        "autotrade", "why didn't it trade", "why no execution",
    ]

    # SYSTEM / HEALTH queries
    SYSTEM_KEYWORDS = [
        "system status", "health", "online", "is the bot", "uptime",
        "provider", "data source", "backup", "dual write",
        "mongodb status", "redis status",
    ]

    # SUBSCRIPTION / USER queries
    USER_KEYWORDS = [
        "my subscription", "my account", "when does my", "expiry",
        "am i still active", "subscription status",
    ]

    # TRADE HISTORY queries
    HISTORY_KEYWORDS = [
        "history", "recent trades", "last trade", "past trades",
        "trade log", "show me trades",
    ]

    # ── General Chat keywords (Lightweight General Mode) ────────────────────
    # These trigger ONLY if no market keyword matched.
    # MATE is market-native. General is minimal support.
    GENERAL_KEYWORDS = [
        # Coding / technical help
        "code", "programming", "python", "javascript", "function", "api",
        "debug", "error message", "how do i code", "coding agent",
        "be my coding", "be my assistant", "coding assistant",
        "help me code", "write code", "build a bot", "build an app",
        # Productivity
        "summarize", "summarise", "explain briefly", "help me understand",
        # Casual / greetings
        "hello", "hi ", "hey ", "good morning", "good evening", "how are you",
        "what can you do", "who are you", "what are you",
        "whats up", "what's up", "sup", "howdy",
        "what's going on", "whats going on", "anything happening",
        # Simple reasoning
        "difference between", "vs ", "compared to", "which is better",
        "should i ", "would you recommend",
        "what should i trade", "what should i buy",
        # General knowledge / off-topic (not banned, just not market)
        "movies", "weather", "sports", "joke", "tell me about",
        "top 10", "recommend", "suggest",
        # Platform guidance
        "how do i use", "how to use", "navigate", "where do i find",
        "how does this work",
    ]

    # ── Hard NO — topics MATE will NOT engage with ──────────────────────────
    HARD_NO_KEYWORDS = [
        # Therapist / relationship
        "my girlfriend", "my boyfriend", "relationship advice", "my wife",
        "my husband", "my partner",
        # Uncensored roleplay (very specific — don't catch capability requests)
        "roleplay as", "pretend you are", "rp as",
        "pretend to be a", "act like you are a",
        # Political / war
        "political", "politics", "war in", "who should i vote",
        # Fake consciousness
        "are you sentient", "are you conscious", "do you have feelings",
        "are you alive", "do you feel",
        # Infinite research
        "write me a paper", "write my thesis", "write my essay",
        "write a book", "write a novel",
    ]

    # ── Symbol aliases for entity extraction ────────────────────────────────
    # Includes BTCUSD + ETHUSD per user request
    SYMBOL_ALIASES = {
        "gold": "XAUUSD", "silver": "XAGUSD", "euro": "EURUSD",
        "pound": "GBPUSD", "cable": "GBPUSD", "fiber": "EURUSD",
        "yen": "USDJPY", "kiwi": "NZDUSD", "aussie": "AUDUSD",
        "loonie": "USDCAD", "swissy": "USDCHF",
        "bitcoin": "BTCUSD", "btc": "BTCUSD",
        "ethereum": "ETHUSD", "eth": "ETHUSD",
    }

    # ═════════════════════════════════════════════════════════════════════════
    # LLM Classification
    # ═════════════════════════════════════════════════════════════════════════

    async def classify(self, query: str) -> Intent:
        """
        Classify a natural language query into a brain domain + function.

        v2 Architecture: LLM-first with keyword fallback.

        Priority order:
          1. HARD_NO fast-path (keyword check — safety gate, no LLM needed)
          2. LLM classification (understands context and nuance)
          3. Keyword fallback (if LLM fails or returns invalid output)

        The LLM is constrained to only return valid (domain, function) pairs
        from VALID_INTENTS. If it returns garbage or low confidence, the
        keyword system catches it.
        """
        q = query.lower().strip()

        # ── 0. HARD NO — reject banned topics immediately (no LLM needed) ──
        if any(kw in q for kw in self.HARD_NO_KEYWORDS):
            return Intent(
                domain=IntentDomain.GENERAL_CHAT,
                function="hard_no",
                confidence=1.0,
            )

        # ── 1. LLM classification (primary path) ───────────────────────────
        if _LLM_CLASSIFY_ENABLED:
            try:
                intent = await self._classify_via_llm(query)
                if intent is not None:
                    return intent
            except Exception as exc:
                log.warning(
                    "llm_classify_failed",
                    error=str(exc),
                    hint="Falling back to keyword classification",
                )

        # ── 2. Keyword fallback (safety net) ────────────────────────────────
        return self._classify_via_keywords(query)

    async def _classify_via_llm(self, query: str) -> Optional[Intent]:
        """
        Use the LLM to classify intent. Returns None if classification fails
        or returns invalid output (triggers keyword fallback).

        Guardrails:
          - Low temperature (0.1) for deterministic output
          - Short max_tokens (80) — no room to wander
          - Output validated against VALID_INTENTS set
          - Confidence threshold (< 0.5 triggers fallback)
          - JSON parsing with markdown fence stripping
        """
        from marketmate.core.llm import llm_provider

        prompt = INTENT_CLASSIFICATION_PROMPT.format(query=query)

        response = await llm_provider.chat(
            system_prompt=INTENT_CLASSIFICATION_SYSTEM,
            user_prompt=prompt,
            max_tokens=80,
            temperature=0.1,
        )

        if not response:
            log.warning("llm_classify_empty_response")
            return None

        # ── Parse JSON response ─────────────────────────────────────────────
        raw = response.strip()

        # Strip markdown code fences if present (LLMs sometimes wrap JSON)
        if raw.startswith("```"):
            lines = raw.split("\n")
            # Remove first line (```json or ```) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            raw = "\n".join(lines).strip()

        try:
            data = json.loads(raw)
        except json.JSONDecodeError as exc:
            log.warning(
                "llm_classify_json_error",
                raw_response=raw[:200],
                error=str(exc),
            )
            return None

        domain = data.get("domain", "")
        function = data.get("function", "")
        confidence = data.get("confidence", 0.5)

        # ── Validate domain and function against allowed intents ────────────
        if (domain, function) not in VALID_INTENTS:
            log.warning(
                "llm_classify_invalid_intent",
                domain=domain,
                function=function,
                hint="Not in VALID_INTENTS — falling back to keywords",
            )
            return None

        # ── Validate confidence ─────────────────────────────────────────────
        try:
            confidence = float(confidence)
        except (TypeError, ValueError):
            confidence = 0.5

        if confidence < 0.5:
            log.info(
                "llm_classify_low_confidence",
                domain=domain,
                function=function,
                confidence=confidence,
                hint="Low confidence — falling back to keywords",
            )
            return None

        log.info(
            "llm_classify_success",
            domain=domain,
            function=function,
            confidence=confidence,
        )

        return Intent(domain=domain, function=function, confidence=confidence)

    # ═════════════════════════════════════════════════════════════════════════
    # Keyword Classification (fallback)
    # ═════════════════════════════════════════════════════════════════════════

    def _classify_via_keywords(self, query: str) -> Intent:
        """
        Classify using keyword matching (original v1 logic).

        This is the safety net — used when LLM classification fails
        or is disabled. Ordered by specificity: most specific matches first.
        """
        q = query.lower().strip()

        # ── 1. PRICE queries -> MarketDataBrain.get_live_price ───────────────
        if any(kw in q for kw in self.PRICE_KEYWORDS):
            return Intent(
                domain=IntentDomain.MARKET_DATA,
                function="get_live_price",
                confidence=0.95,
            )

        # ── 2. MARKET SUMMARY queries -> MarketDataBrain.get_market_summary ──
        if any(kw in q for kw in self.MARKET_SUMMARY_KEYWORDS):
            # Check if it's a "how many" question that should go to signal_intel
            if any(kw in q for kw in self.SIGNAL_COUNT_KEYWORDS):
                return Intent(
                    domain=IntentDomain.SIGNAL_INTEL,
                    function="get_signal_count",
                    confidence=0.9,
                )
            return Intent(
                domain=IntentDomain.MARKET_DATA,
                function="get_market_summary",
                confidence=0.9,
            )

        # ── 3. SIGNAL COUNT queries -> SignalIntelBrain.get_signal_count ─────
        if any(kw in q for kw in self.SIGNAL_COUNT_KEYWORDS):
            return Intent(
                domain=IntentDomain.SIGNAL_INTEL,
                function="get_signal_count",
                confidence=0.95,
            )

        # ── 4. SIGNAL EXPLANATION -> SignalIntelBrain.explain_signal ─────────
        if any(kw in q for kw in self.SIGNAL_EXPLAIN_KEYWORDS):
            return Intent(
                domain=IntentDomain.SIGNAL_INTEL,
                function="explain_signal",
                confidence=0.9,
            )

        # ── 5. PERFORMANCE EXPLAINER -> AccountBrain + SignalIntelBrain ──────
        if any(kw in q for kw in self.PERF_EXPLAIN_KEYWORDS):
            return Intent(
                domain=IntentDomain.SIGNAL_INTEL,
                function="get_performance_explainer",
                confidence=0.85,
            )

        # ── 6. AUTO-TRADE DIAGNOSTICS -> SystemBrain.get_pipeline_diagnostics
        if any(kw in q for kw in self.AUTOTRADE_KEYWORDS):
            return Intent(
                domain=IntentDomain.SYSTEM,
                function="get_pipeline_diagnostics",
                confidence=0.9,
            )

        # ── 7. WIN RATE / PERFORMANCE -> SignalIntelBrain.get_signal_stats ───
        if any(kw in q for kw in self.PERFORMANCE_KEYWORDS):
            return Intent(
                domain=IntentDomain.SIGNAL_INTEL,
                function="get_signal_stats",
                confidence=0.9,
            )

        # ── 8. ACCOUNT / BALANCE -> AccountBrain.get_state ───────────────────
        if any(kw in q for kw in self.ACCOUNT_KEYWORDS):
            return Intent(
                domain=IntentDomain.ACCOUNT,
                function="get_state",
                confidence=0.9,
            )

        # ── 9. RISK -> AccountBrain.get_risk_state ───────────────────────────
        if any(kw in q for kw in self.RISK_KEYWORDS):
            return Intent(
                domain=IntentDomain.ACCOUNT,
                function="get_risk_state",
                confidence=0.85,
            )

        # ── 10. STRATEGY / ACADEMY -> StrategyBrain ──────────────────────────
        if any(kw in q for kw in self.STRATEGY_KEYWORDS):
            concept_keys = ["bos", "choch", "fvg", "order block", "sweep", "liquidity",
                          "rr", "risk reward", "htf bias", "smart money"]
            if any(ck in q for ck in concept_keys):
                return Intent(
                    domain=IntentDomain.STRATEGY,
                    function="explain_concept",
                    confidence=0.9,
                )
            session_keys = ["session", "hours", "when does", "trading hours", "schedule"]
            if any(sk in q for sk in session_keys):
                return Intent(
                    domain=IntentDomain.STRATEGY,
                    function="get_session_schedule",
                    confidence=0.9,
                )
            gate_keys = ["gate", "pipeline", "g1", "g2", "g3", "signal generation"]
            if any(gk in q for gk in gate_keys):
                return Intent(
                    domain=IntentDomain.STRATEGY,
                    function="explain_gate_pipeline",
                    confidence=0.9,
                )
            return Intent(
                domain=IntentDomain.STRATEGY,
                function="get_strategy_params",
                confidence=0.8,
            )

        # ── 11. SYSTEM / HEALTH -> SystemBrain.get_system_health ─────────────
        if any(kw in q for kw in self.SYSTEM_KEYWORDS):
            return Intent(
                domain=IntentDomain.SYSTEM,
                function="get_system_health",
                confidence=0.9,
            )

        # ── 12. SUBSCRIPTION / USER -> UserBrain.get_user_status ─────────────
        if any(kw in q for kw in self.USER_KEYWORDS):
            return Intent(
                domain=IntentDomain.USER,
                function="get_user_status",
                confidence=0.85,
            )

        # ── 13. TRADE HISTORY -> UserBrain.get_trade_history ─────────────────
        if any(kw in q for kw in self.HISTORY_KEYWORDS):
            return Intent(
                domain=IntentDomain.USER,
                function="get_trade_history",
                confidence=0.85,
            )

        # ── 14. Symbol-specific queries -> check if symbol mentioned ──────────
        for symbol in cfg.strategy.pairs:
            if symbol.lower() in q:
                return Intent(
                    domain=IntentDomain.MARKET_DATA,
                    function="get_market_summary",
                    confidence=0.7,
                )

        # Check aliases
        for alias in self.SYMBOL_ALIASES:
            if alias in q:
                canonical = self.SYMBOL_ALIASES[alias]
                if canonical in [p.upper() for p in cfg.strategy.pairs]:
                    return Intent(
                        domain=IntentDomain.MARKET_DATA,
                        function="get_market_summary",
                        confidence=0.7,
                    )

        # ── 15. ACTIVE / OPEN signal queries ────────────────────────────────
        active_words = ["open", "running", "active", "current trade", "positions"]
        if any(w in q for w in active_words):
            return Intent(
                domain=IntentDomain.SIGNAL_INTEL,
                function="get_active_signals",
                confidence=0.8,
            )

        # ── 16. General Chat -> Lightweight General Mode (20%) ────────────────
        if any(kw in q for kw in self.GENERAL_KEYWORDS):
            return Intent(
                domain=IntentDomain.GENERAL_CHAT,
                function="general_response",
                confidence=0.7,
            )

        # ── Default: General Chat (lightweight mode) ────────────────────────
        # If nothing matched, it's not a structured market query.
        # Use lightweight general mode instead of forcing signal_intel.
        return Intent(
            domain=IntentDomain.GENERAL_CHAT,
            function="general_response",
            confidence=0.3,
        )

    # ═════════════════════════════════════════════════════════════════════════
    # Entity Extraction (deterministic — no LLM, no hallucination)
    # ═════════════════════════════════════════════════════════════════════════

    def extract_symbol(self, query: str) -> Optional[str]:
        """
        Extract a trading symbol from the query text.

        Returns the canonical symbol name (e.g. XAUUSD, BTCUSD) or None.
        Stays deterministic — no LLM, no hallucinated symbols.
        """
        q = query.lower()

        # Check canonical pairs first
        for symbol in cfg.strategy.pairs:
            if symbol.lower() in q:
                return symbol.upper()

        # Check common aliases
        for alias, canonical in self.SYMBOL_ALIASES.items():
            if alias in q and canonical in [p.upper() for p in cfg.strategy.pairs]:
                return canonical

        return None

    def extract_timeframe(self, query: str) -> Optional[str]:
        """
        Extract a timeframe reference from the query.

        Maps natural language to standard timeframes.
        """
        q = query.lower()

        # Direct timeframe mentions
        tf_map = {
            "1m": "1m", "5m": "5m", "15m": "15m", "1h": "1h",
            "4h": "4h", "1d": "1d", "1w": "1w",
            "daily": "1d", "hourly": "1h",
            "minute": "1m", "5 minute": "5m", "15 minute": "15m",
        }
        for key, tf in tf_map.items():
            if key in q:
                return tf

        return None

    def extract_days(self, query: str) -> int:
        """
        Extract a day range from the query for lookback period.

        Maps "last week" -> 7, "last month" -> 30, etc.
        """
        q = query.lower()

        if "last month" in q or "past month" in q or "30 day" in q:
            return 30
        if "last week" in q or "past week" in q or "7 day" in q:
            return 7
        if "this week" in q:
            return 7
        if "today" in q:
            return 1
        if "last 3 days" in q or "past 3 days" in q:
            return 3
        if "last 2 weeks" in q or "past 2 weeks" in q:
            return 14
        if "last few days" in q or "past few days" in q or "lately" in q:
            return 5

        return 7  # Default: last week


# ─── Singleton ────────────────────────────────────────────────────────────────

intent_classifier = IntentClassifier()
