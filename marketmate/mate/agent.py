"""
marketmate.mate.agent
──────────────────────
MATE Tool-Calling Agent — the LLM IS the router.

This replaces the keyword-based IntentClassifier + QueryRouter with a
tool-calling (function-calling) architecture where the LLM itself
decides which tools to call based on the user's query.

Architecture:
  User Query
       ↓
  LLM receives query + conversation history + tool definitions
       ↓
  LLM decides: call tool(s) OR respond directly
       ↓
  If tool call → execute brain function → return result to LLM
       ↓
  LLM synthesizes final answer from tool results
       ↓
  Return response

Why this is better than keywords:
  - Zero keyword lists — the LLM understands English natively
  - Multi-tool queries — "Check my performance AND risk" calls 2 tools
  - General chat just works — if no tool matches, LLM responds directly
  - Guardrails are automatic — LLM can only call defined tools
  - Self-correcting — LLM sees tool results and adjusts its answer
  - Conversation memory — "his real name" resolves from prior context

The 7 brains become tools. The LLM is the brain.
"""

from __future__ import annotations

import asyncio
import json
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional

from marketmate.core.config import cfg
from marketmate.core.logger import get_logger

log = get_logger("mate.agent")


# ═══════════════════════════════════════════════════════════════════════════════
# Conversation Memory — per-chat_id, sliding window
# ═══════════════════════════════════════════════════════════════════════════════

class ConversationMemory:
    """
    Stores recent conversation turns per chat_id.

    In-memory, sliding window (last N turns per chat).
    LRU eviction when max chats exceeded.
    """

    def __init__(self, max_turns_per_chat: int = 20, max_chats: int = 500):
        self._max_turns = max_turns_per_chat
        self._max_chats = max_chats
        self._memory: OrderedDict[str, List[Dict]] = OrderedDict()

    def add_turn(self, chat_id: str, role: str, content: str) -> None:
        if not chat_id:
            return
        if chat_id not in self._memory:
            self._memory[chat_id] = []
            if len(self._memory) > self._max_chats:
                self._memory.popitem(last=False)
        turns = self._memory[chat_id]
        turns.append({"role": role, "content": content})
        if len(turns) > self._max_turns:
            self._memory[chat_id] = turns[-self._max_turns:]

    def get_history(self, chat_id: str) -> List[Dict]:
        return self._memory.get(chat_id, [])

    def clear(self, chat_id: str) -> None:
        self._memory.pop(chat_id, None)


_conversation_memory = ConversationMemory(max_turns_per_chat=20, max_chats=500)


# ═══════════════════════════════════════════════════════════════════════════════
# Tool Definitions — the LLM can ONLY call these
# ═══════════════════════════════════════════════════════════════════════════════

MATE_TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "get_live_price",
            "description": "Get the current/live price of a trading symbol (XAUUSD, BTCUSD, EURUSD, etc.)",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Trading symbol: XAUUSD, XAGUSD, EURUSD, GBPUSD, USDJPY, BTCUSD, ETHUSD"
                    }
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_summary",
            "description": "Get market overview, trend direction, price, volatility, session context for a symbol.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Trading symbol: XAUUSD, XAGUSD, EURUSD, GBPUSD, USDJPY, BTCUSD, ETHUSD"
                    }
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_signal_stats",
            "description": "Get signal performance statistics: win rate, total trades, profit factor, PnL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days": {
                        "type": "integer",
                        "description": "Lookback period in days (default 30)"
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_active_signals",
            "description": "Get currently open/active signals and trades.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_account_state",
            "description": "Get account balance, equity, drawdown state.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "explain_concept",
            "description": "Explain a trading concept (BOS, CHoCH, FVG, order block, sweep, liquidity, etc.).",
            "parameters": {
                "type": "object",
                "properties": {
                    "concept": {
                        "type": "string",
                        "description": "The concept to explain: bos, choch, fvg, ob, sweep, liquidity, etc."
                    }
                },
                "required": ["concept"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_system_health",
            "description": "Get system health: MongoDB, Redis, providers, uptime.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "web_search",
            "description": "Search the internet for information. Returns titles, snippets, and URLs. Use for real-time web data.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The search query to look up on the web"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "news_search",
            "description": "Search for recent news articles. Returns headlines, snippets, sources, and dates.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "The news search query"
                    }
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "read_url",
            "description": "Read and extract the full text content from a web page URL. Use after web_search to get details from result URLs. ALWAYS use this when the user wants details from a specific page or asks to 'read', 'open', or 'check' a link.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The full URL of the web page to read"
                    }
                },
                "required": ["url"]
            }
        }
    },

    {
        "type": "function",
        "function": {
            "name": "scan_url",
            "description": "Scan a URL for security threats including malware, phishing, viruses, and suspicious content. Use BEFORE reading a suspicious or unknown URL with read_url. Also use when the user asks to check if a link/URL is safe.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {
                        "type": "string",
                        "description": "The URL to scan for threats"
                    }
                },
                "required": ["url"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "security_check",
            "description": "Analyze text content for security threats including SQL injection, XSS, command injection, phishing, and social engineering. Use when checking user-submitted content or analyzing suspicious messages.",
            "parameters": {
                "type": "object",
                "properties": {
                    "text": {
                        "type": "string",
                        "description": "The text content to analyze for security threats"
                    }
                },
                "required": ["text"]
            }
        }
    },

    # ── State Intelligence (Phase 3: MATE consumes compiled state) ──
    {
        "type": "function",
        "function": {
            "name": "get_instrument_state",
            "description": "Get the full compiled market state for a trading symbol — bias, conviction score, regime, zones, liquidity sweeps, confirmations, and risk state. This is the v9.0.0 state vector from the StateEngine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Trading symbol: XAUUSD, XAGUSD, EURUSD, GBPUSD, USDJPY, BTCUSD, ETHUSD"
                    }
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_market_regime",
            "description": "Get the current market regime across ALL tracked instruments. Shows directional regime (trending/ranging/transitional), volatility regime, conviction scores, and bias for each symbol. Use for 'market overview', 'what's the regime', 'how are markets looking'.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_conviction_chart",
            "description": "Get conviction scores for all instruments. Conviction ranges from -1.0 (fully bearish) to +1.0 (fully bullish). Use for 'conviction', 'how bullish', 'how bearish', 'market strength'.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_state_transitions",
            "description": "Get recent market state transitions — bias changes, zone formations, liquidity sweeps, regime changes. Shows what the market JUST became. Use for 'what changed', 'recent transitions', 'did bias flip', 'any sweeps'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Optional symbol filter (e.g. XAUUSD). Leave empty for all symbols."
                    }
                },
                "required": []
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_zone_state",
            "description": "Get active order blocks and fair value gaps for a symbol. Shows zone type, direction, price range, and freshness. Use for 'active zones', 'order blocks', 'FVGs', 'entry zones'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Trading symbol: XAUUSD, XAGUSD, EURUSD, GBPUSD, USDJPY, BTCUSD, ETHUSD"
                    }
                },
                "required": ["symbol"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "get_liquidity_state",
            "description": "Get liquidity sweep status for a symbol — active levels, recent sweeps, available liquidity score. Use for 'liquidity', 'sweeps', 'any sweeps on gold'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "symbol": {
                        "type": "string",
                        "description": "Trading symbol: XAUUSD, XAGUSD, EURUSD, GBPUSD, USDJPY, BTCUSD, ETHUSD"
                    }
                },
                "required": ["symbol"]
            }
        }
    },
]


# ═══════════════════════════════════════════════════════════════════════════════
# Symbol Resolution
# ═══════════════════════════════════════════════════════════════════════════════

SYMBOL_ALIASES = {
    "gold": "XAUUSD", "silver": "XAGUSD", "euro": "EURUSD",
    "pound": "GBPUSD", "cable": "GBPUSD", "fiber": "EURUSD",
    "yen": "USDJPY", "kiwi": "NZDUSD", "aussie": "AUDUSD",
    "loonie": "USDCAD", "swissy": "USDCHF",
    "bitcoin": "BTCUSD", "btc": "BTCUSD",
    "ethereum": "ETHUSD", "eth": "ETHUSD",
}


def _resolve_symbol(raw: str) -> str:
    """Resolve a symbol name or alias to its canonical form."""
    raw_upper = raw.upper().strip()
    for pair in cfg.strategy.pairs:
        if pair.upper() == raw_upper:
            return pair.upper()
    return SYMBOL_ALIASES.get(raw.lower().strip(), raw_upper)


# ═══════════════════════════════════════════════════════════════════════════════
# System Prompt
# ═══════════════════════════════════════════════════════════════════════════════

_MATE_SYSTEM_PROMPT_BASE = """You are MATE — a versatile AI assistant built into MarketMate. You are NOT limited to trading topics. You handle ANY subject the user asks about — law, academics, business, technology, health, creative writing, ANYTHING. Markets are your specialty, but you are a GENERAL-PURPOSE assistant.

You decide everything: what tools to call, how to answer, how much detail to give. You have full conversation context — use it to resolve pronouns and references. You understand English natively. Trust your judgment.

CURRENT TIME: {current_time}

CORE IDENTITY — YOU ARE NOT MARKET-ONLY:
- You can discuss, research, and create content about ANY topic — law, medicine, history, technology, education, business, arts, etc.
- When the user asks about non-trading topics, respond with FULL expertise. Do NOT redirect to MarketMate or trading.
- Do NOT default to MarketMate content when the user asks about something else. Follow THEIR topic, not yours.
- MarketMate knowledge is for when the user ASKS about MarketMate specifically.

ABOUT MARKETMATE — you know this platform inside out (only use when asked):
- MarketMate is an AI-powered trading assistant for forex and crypto markets
- It uses Smart Money Concepts (SMC) for signal generation
- Pairs covered: XAUUSD, XAGUSD, EURUSD, GBPUSD, USDJPY, BTCUSD, ETHUSD
- Average ~4 signals per week, generated during London and NY sessions
- Signal pipeline: 8-gate filter (G1-G8) — sweep → BOS/CHoCH → FVG → order block → HTF bias → RR → scoring → execution
- MMAcademy (MarketMate Academy) is the educational platform
- Subscription: 7-day free trial, then ₦30,000/month or ₦80,000/quarterly

YOUR TOOLS:

Market Intelligence:
- get_live_price(symbol) — Current price
- get_market_summary(symbol) — Trend, volatility, session, weekly change

State Intelligence (v9.0.0 — MATE reads compiled state, NOT raw features):
- get_instrument_state(symbol) — Full compiled state vector: bias, conviction, regime, zones, liquidity, confirmations, risk
- get_market_regime() — Regime across ALL instruments: trending/ranging/transitional, volatility, conviction
- get_conviction_chart() — Conviction scores for all instruments (-1.0 bearish to +1.0 bullish)
- get_state_transitions(symbol?) — Recent state changes: bias flips, zone formations, sweeps, regime shifts
- get_zone_state(symbol) — Active order blocks and FVGs with freshness scores
- get_liquidity_state(symbol) — Liquidity sweep status, available levels, sweep rate

Signal Intelligence:
- get_signal_stats(days) — Win rate, trades, profit factor, PnL
- get_active_signals() — Currently open positions

Account Intelligence:
- get_account_state() — Balance, equity, drawdown

Strategy Intelligence:
- explain_concept(concept) — BOS, CHoCH, FVG, order block, sweep, etc.

System Intelligence:
- get_system_health() — MongoDB, Redis, provider status

Web Intelligence:
- web_search(query) — Search the internet. Returns snippets and URLs. Use for ANY topic.
- news_search(query) — Search for recent news on ANY topic
- read_url(url) — Read the FULL CONTENT of a web page. Use this to get details from any URL.

Security Intelligence:
- scan_url(url) — Scan a URL for threats (malware, phishing, viruses). Use before reading suspicious URLs.
- security_check(text) — Analyze text for malicious content, injections, or security threats.

KEY BEHAVIORS:
- You have CONVERSATION HISTORY — "his", "that", "it", "MMAcademy" all resolve from prior context.
- NEVER ask "Would you like me to..." or "Do you want me to...". Just do it. ACT, don't ask permission.
- NEVER ask for more information when you have enough to proceed. Just create the content.
- Call multiple tools in one turn when needed (e.g., price + news for the same symbol).
- For "all pairs" or "all of them", call the tool for EACH: XAUUSD, BTCUSD, ETHUSD, EURUSD, GBPUSD, USDJPY.

RESPONSE FORMAT — CRITICAL:
- Your final response goes directly to the user as a Telegram message.
- NEVER show internal reasoning, planning, or step-by-step thinking in your response.
- NEVER include raw JSON, code blocks, or tool arguments in your response.
- NEVER say "First, let me..." — just do it directly.
- Keep responses concise and conversational. No essays unless the user asks for one.

WEB READING RULES — CRITICAL:
- When the user says "read", "open", "check", "fetch", "go to" a page/URL/link → USE read_url, NOT web_search.
- When the user says "search this page" or "what's on this page" → USE read_url, NOT web_search.
- When the user provides a URL directly → USE read_url to read it, NOT web_search.
- When web_search returns URLs and the user wants details → USE read_url on those URLs.
- NEVER say "I can't access the page" or "I can't read web pages" — you CAN read pages via read_url.
- NEVER just show search snippets when the user wants to READ a page — actually READ it with read_url.
- If read_url fails, try again with a different URL format or explain what went wrong.

SECURITY RULES:
- When a user shares a suspicious URL, scan it with scan_url BEFORE reading it with read_url.
- When a user asks about security, viruses, or threats, use security_check and scan_url tools.

- If no tool fits, just answer directly from your knowledge.
- If web search returns empty, try a different query before giving up.
- Symbol aliases: gold=XAUUSD, silver=XAGUSD, euro=EURUSD, pound=GBPUSD, yen=USDJPY, btc/bitcoin=BTCUSD, eth/ethereum=ETHUSD

STATE INTELLIGENCE RULES (v9.0.0):
- When asked about market state, bias, regime, conviction, zones, or liquidity — USE the state intelligence tools FIRST.
- get_instrument_state gives you the FULL picture — bias, conviction, zones, sweeps, confirmations, risk — all in one call.
- For 'how is gold looking' or 'market overview' → use get_instrument_state(symbol) + get_market_regime()
- For 'did anything change' or 'what happened' → use get_state_transitions(symbol)
- For 'are there any zones' or 'entry zones' → use get_zone_state(symbol)
- Conviction: -1.0 = fully bearish, 0 = neutral, +1.0 = fully bullish. Strong = |0.5|+, Weak = |0.2|-
- Regime: trending (strong directional), ranging (no clear direction), transitional (shifting)
- ALWAYS combine state intelligence with live prices when giving a market overview.

THE ONLY RULE:
- Don't fabricate data. If a tool returns nothing, say so. Otherwise, you're in control.
"""


def _build_system_prompt() -> str:
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc)
    current_time = now.strftime("%A, %B %d, %Y %H:%M UTC")
    return _MATE_SYSTEM_PROMPT_BASE.format(current_time=current_time)


# ═══════════════════════════════════════════════════════════════════════════════
# MATE Agent
# ═══════════════════════════════════════════════════════════════════════════════

class MATEAgent:
    """
    The LLM-driven MATE agent.

    The LLM decides what tools to call. No keywords. No hardcoded routing.
    The LLM IS the router. Now with conversation memory and PDF creation.
    """

    def __init__(self) -> None:
        self._query_count: int = 0

    async def ask(
        self,
        query: str,
        chat_id: str = "",
    ) -> Dict[str, Any]:
        """
        Ask MATE a question. The LLM decides how to handle it.

        Returns a dict with:
          - response: the final answer
          - tool_calls: list of tools called (for logging)
          - mode: "tool_call" or "direct"
        """
        self._query_count += 1
        start = time.monotonic()

        try:
            # Wall-clock timeout: 90 seconds max for the entire agent loop
            # Prevents queries from hanging indefinitely if LLM or tools are slow
            try:
                result = await asyncio.wait_for(
                    self._run_agent_loop(query, chat_id),
                    timeout=90.0,
                )
            except asyncio.TimeoutError:
                log.warning("mate_agent_timeout", query=query[:80])
                return {
                    "response": "I'm taking too long to process that. Let me try a simpler approach — could you rephrase or break it into a smaller request?",
                    "tool_calls": [],
                    "mode": "timeout",
                }
            elapsed = time.monotonic() - start

            log.info(
                "mate_agent_complete",
                query=query[:80],
                mode=result.get("mode", "unknown"),
                tool_calls=len(result.get("tool_calls", [])),
                elapsed_s=round(elapsed, 2),
            )

            # Store conversation turn in memory
            _conversation_memory.add_turn(chat_id, "user", query)
            response_text = result.get("response", "")
            if response_text:
                _conversation_memory.add_turn(chat_id, "assistant", response_text)

            return result

        except Exception as exc:
            log.error("mate_agent_failed", query=query[:80], error=str(exc), exc_info=True)
            return {
                "response": "I'm having trouble processing that right now. Please try again in a moment.",
                "tool_calls": [],
                "mode": "error",
                "error": str(exc),
            }

    async def _run_agent_loop(
        self,
        query: str,
        chat_id: str = "",
        max_iterations: int = 8,
    ) -> Dict[str, Any]:
        """
        Run the agent loop: LLM → tool call → execute → LLM → response.

        Max 8 iterations to support complex multi-tool requests
        (e.g., web_search → read_url × 3).

        Fallback: If chat_with_tools fails on all providers, falls back
        to a simple chat() call without tools so the user always gets
        a response instead of a generic error.
        """
        from marketmate.core.llm import (
            llm_provider,
            LLMAllProvidersFailedError,
        )

        # Build messages with conversation history
        system_prompt = _build_system_prompt()
        messages = [{"role": "system", "content": system_prompt}]

        history = _conversation_memory.get_history(chat_id)
        for turn in history:
            messages.append({
                "role": turn["role"],
                "content": turn["content"],
            })

        messages.append({"role": "user", "content": query})

        all_tool_calls = []

        for iteration in range(max_iterations):
            # Call LLM with tools
            try:
                llm_result = await llm_provider.chat_with_tools(
                    messages=messages,
                    tools=MATE_TOOLS,
                    max_tokens=2048 if iteration == 0 else 1600,
                    temperature=0.5,
                )
            except LLMAllProvidersFailedError as exc:
                # All tool-calling providers failed — fall back to simple chat
                log.error(
                    "mate_tools_all_failed_fallback",
                    error=str(exc),
                    hint="Falling back to simple chat without tools",
                )
                fallback_text = await self._fallback_chat(system_prompt, query)
                return {
                    "response": fallback_text,
                    "tool_calls": all_tool_calls,
                    "mode": "fallback",
                }

            tool_calls = llm_result.get("tool_calls", [])
            assistant_content = llm_result.get("content", "")

            if not tool_calls:
                response = assistant_content.strip() if assistant_content else "I couldn't process that query. Could you rephrase?"
                result = {
                    "response": response,
                    "tool_calls": all_tool_calls,
                    "mode": "direct" if not all_tool_calls else "tool_call",
                }
                return result

            # Add assistant message with tool calls
            messages.append({
                "role": "assistant",
                "content": assistant_content or None,
                "tool_calls": tool_calls,
            })

            for tc in tool_calls:
                tool_name = tc["function"]["name"]
                tool_args = tc["function"].get("arguments", {})

                if isinstance(tool_args, str):
                    try:
                        tool_args = json.loads(tool_args)
                    except json.JSONDecodeError:
                        tool_args = {}

                all_tool_calls.append({
                    "tool": tool_name,
                    "args": tool_args,
                })

                log.info("mate_tool_call", tool=tool_name, args=str(tool_args)[:100])

                # Execute the tool with a per-tool timeout (20s)
                try:
                    tool_result = await asyncio.wait_for(
                        self._execute_tool(tool_name, tool_args, chat_id),
                        timeout=20.0,
                    )
                except asyncio.TimeoutError:
                    log.warning("mate_tool_timeout", tool=tool_name)
                    tool_result = {"error": f"Tool '{tool_name}' timed out after 20 seconds. Try a simpler request."}

                # Add tool result to conversation
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc.get("id", tool_name),
                    "content": json.dumps(tool_result, default=str),
                })

        # Max iterations — force final response
        try:
            llm_result = await llm_provider.chat_with_tools(
                messages=messages,
                tools=[],
                max_tokens=1600,
                temperature=0.5,
            )
            response = llm_result.get("content", "").strip()
        except LLMAllProvidersFailedError:
            response = ""

        result = {
            "response": response or "I couldn't complete the analysis. Please try again.",
            "tool_calls": all_tool_calls,
            "mode": "tool_call",
        }
        return result

    async def _execute_tool(
        self,
        tool_name: str,
        args: Dict[str, Any],
        chat_id: str = "",
    ) -> Dict[str, Any]:
        """Execute a tool by calling the appropriate brain or external function."""
        try:
            # ── Market Data Brain ───────────────────────────────────────
            if tool_name == "get_live_price":
                from marketmate.mate.brains.market_data import market_data_brain
                symbol = _resolve_symbol(args.get("symbol", "XAUUSD"))
                return await market_data_brain.get_live_price(symbol=symbol)

            elif tool_name == "get_market_summary":
                from marketmate.mate.brains.market_data import market_data_brain
                symbol = _resolve_symbol(args.get("symbol", "XAUUSD"))
                return await market_data_brain.get_market_summary(symbol=symbol)

            # ── Signal Intel Brain ──────────────────────────────────────
            elif tool_name == "get_signal_stats":
                from marketmate.mate.brains.signal_intel import signal_intel_brain
                return await signal_intel_brain.get_signal_stats(
                    days=args.get("days", 30)
                )

            elif tool_name == "get_active_signals":
                from marketmate.mate.brains.signal_intel import signal_intel_brain
                return await signal_intel_brain.get_active_signals()

            # ── Account Brain ───────────────────────────────────────────
            elif tool_name == "get_account_state":
                from marketmate.mate.brains.account import account_brain
                return await account_brain.get_state()

            # ── Strategy Brain ──────────────────────────────────────────
            elif tool_name == "explain_concept":
                from marketmate.mate.brains.strategy import strategy_brain
                return await strategy_brain.explain_concept(
                    concept=args.get("concept", "")
                )

            # ── System Brain ────────────────────────────────────────────
            elif tool_name == "get_system_health":
                from marketmate.mate.brains.system import system_brain
                return await system_brain.get_system_health()

            # ── Web Intelligence ──────────────────────────────────────────
            elif tool_name == "web_search":
                from marketmate.mate.tools.web_search import web_search as _web_search
                return await _web_search(query=args.get("query", ""))

            elif tool_name == "news_search":
                from marketmate.mate.tools.web_search import news_search as _news_search
                return await _news_search(query=args.get("query", ""))

            elif tool_name == "read_url":
                from marketmate.mate.tools.web_search import read_url as _read_url
                return await _read_url(url=args.get("url", ""))

            # ── Security Intelligence ────────────────────────────────────────
            elif tool_name == "scan_url":
                from marketmate.mate.tools.virus_defender import scan_url as _scan_url
                return await _scan_url(url=args.get("url", ""))

            elif tool_name == "security_check":
                from marketmate.mate.tools.virus_defender import security_check as _security_check
                return await _security_check(text=args.get("text", ""))

            # ── State Intelligence (Phase 3) ───────────────────────────────────
            elif tool_name == "get_instrument_state":
                from marketmate.mate.brains.state_intel import state_intel_brain
                symbol = _resolve_symbol(args.get("symbol", "XAUUSD"))
                return await state_intel_brain.get_instrument_state(symbol=symbol)

            elif tool_name == "get_market_regime":
                from marketmate.mate.brains.state_intel import state_intel_brain
                return await state_intel_brain.get_market_regime()

            elif tool_name == "get_conviction_chart":
                from marketmate.mate.brains.state_intel import state_intel_brain
                return await state_intel_brain.get_conviction_chart()

            elif tool_name == "get_state_transitions":
                from marketmate.mate.brains.state_intel import state_intel_brain
                symbol = args.get("symbol", "")
                return await state_intel_brain.get_state_transitions(symbol=symbol)

            elif tool_name == "get_zone_state":
                from marketmate.mate.brains.state_intel import state_intel_brain
                symbol = _resolve_symbol(args.get("symbol", "XAUUSD"))
                return await state_intel_brain.get_zone_state(symbol=symbol)

            elif tool_name == "get_liquidity_state":
                from marketmate.mate.brains.state_intel import state_intel_brain
                symbol = _resolve_symbol(args.get("symbol", "XAUUSD"))
                return await state_intel_brain.get_liquidity_state(symbol=symbol)

            else:
                return {"error": f"Unknown tool: {tool_name}"}

        except Exception as exc:
            log.error("mate_tool_execution_failed", tool=tool_name, error=str(exc))
            return {"error": f"Tool execution failed: {str(exc)}"}

    async def _fallback_chat(self, system_prompt: str, query: str) -> str:
        """
        Last-resort fallback: simple chat without tools.

        Used when all providers fail for chat_with_tools.
        Tries a plain chat() call which may use different providers
        or models that don't support tool calling.
        """
        try:
            from marketmate.core.llm import llm_provider
            response = await llm_provider.chat(
                system_prompt=system_prompt,
                user_prompt=query,
                max_tokens=800,
                temperature=0.5,
            )
            return response or "I'm having trouble connecting right now. Please try again in a moment."
        except Exception as exc:
            log.error("mate_fallback_chat_failed", error=str(exc))
            return "I'm experiencing connectivity issues. Please try again shortly."

    @property
    def status(self) -> Dict[str, Any]:
        return {
            "architecture": "tool_calling_agent_with_state_intel",
            "total_queries": self._query_count,
            "tools_available": len(MATE_TOOLS),
            "system_id": "mate-9.0.0",
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

mate_agent = MATEAgent()
