"""
marketmate.mate.brains.general
──────────────────────────────
General Intelligence Brain — lightweight 20% mode for non-market queries.

This is NOT a full chatGPT. It's the GitHub Copilot model:
  - Market-native intelligence that ALSO understands general conversation
  - Coding help, simple explanations, productivity questions
  - Casual conversation, platform guidance
  - Summarization, basic reasoning

HARD NO (never handled here):
  - Therapy / relationship advice
  - Uncensored roleplay
  - Political / war discussions
  - Infinite research oracle
  - Fake consciousness simulation

Architecture:
  Mode 1 (Institutional, 80%): 6 market brains → deterministic data
  Mode 2 (Lightweight General, 20%): This brain → small LLM, no heavy retrieval

Token budget: minimal. No Redis, no MongoDB, no event streams.
Just the LLM with a tight system prompt and short max_tokens.
"""

from __future__ import annotations

from typing import Any, Dict

from marketmate.core.logger import get_logger

log = get_logger("mate.brains.general")


# ── System prompt for Lightweight General Mode ──────────────────────────────

GENERAL_SYSTEM_PROMPT = (
    "You are MATE, a market-native AI intelligence that also helps with general questions. "
    "Your primary expertise is financial markets and trading. You CAN answer general questions "
    "but always keep it brief and redirect to your core strength when relevant.\n\n"
    "Rules:\n"
    "- Keep responses under 80 words for general questions\n"
    "- If a question is even slightly market-related, give a market-flavored answer\n"
    "- Never provide therapy, relationship advice, or medical guidance\n"
    "- Never engage in roleplay, political debates, or war discussions\n"
    "- For coding questions, give concise, practical answers — you can help with code\n"
    "- Be friendly but efficient — you're not a chatbot, you're an intelligence layer\n"
    "- If asked about something outside your scope, briefly say so and suggest your strengths\n"
    "- You CAN act as a coding assistant, analyst, or helper — those are capabilities, not roleplay\n"
)

# ── Hard NO response template ───────────────────────────────────────────────

HARD_NO_RESPONSE = (
    "I'm MATE — a market-native intelligence. I focus on financial markets, "
    "trading signals, and strategy. I can't help with that topic, but ask me "
    "about markets, signals, or your account anytime."
)


class GeneralBrain:
    """
    Lightweight general intelligence for non-market queries.

    This brain uses the LLM directly with a constrained system prompt.
    No Redis, no MongoDB, no event streams — just LLM with guardrails.

    Cheap. Fast. Contained.
    """

    async def general_response(self, query: str) -> Dict[str, Any]:
        """
        Generate a lightweight general response.

        Uses LLM with tight constraints — no heavy retrieval.
        """
        try:
            from marketmate.core.llm import llm_provider

            response = await llm_provider.chat(
                system_prompt=GENERAL_SYSTEM_PROMPT,
                user_prompt=query,
                max_tokens=200,  # Enough for coding help, brief explanations
                temperature=0.5,
            )
            return {
                "response": response.strip() if response else "",
                "mode": "lightweight_general",
                "source": "llm_direct",
            }
        except Exception as exc:
            log.warning("general_brain_llm_failed", error=str(exc))
            return {
                "response": "I'm having trouble with that question right now. "
                           "Try asking about markets, signals, or your account — "
                           "that's where I shine.",
                "mode": "lightweight_general",
                "source": "fallback",
                "error": str(exc),
            }

    async def hard_no(self, query: str) -> Dict[str, Any]:
        """
        Handle a hard-no topic (banned content).

        Returns a firm but polite rejection that reinforces MATE's identity.
        """
        return {
            "response": HARD_NO_RESPONSE,
            "mode": "hard_no",
            "source": "policy",
        }

    async def greeting(self, query: str) -> Dict[str, Any]:
        """
        Handle greetings and identity questions.

        Reinforces MATE's market-native identity on every interaction.
        """
        q = query.lower().strip()

        if any(kw in q for kw in ["who are you", "what are you", "what can you do"]):
            return {
                "response": (
                    "I'm MATE — market-native intelligence for trading signals, "
                    "performance, and strategy. Ask me about prices, win rates, "
                    "signal explanations, or any market question. I also help "
                    "with coding and general questions when needed."
                ),
                "mode": "lightweight_general",
                "source": "identity",
            }

        # Generic greeting
        return {
            "response": "Hey! I'm MATE — your market intelligence. Ask me about signals, prices, performance, or anything trading-related. I'm here to help.",
            "mode": "lightweight_general",
            "source": "greeting",
        }


# ─── Singleton ────────────────────────────────────────────────────────────────

general_brain = GeneralBrain()
