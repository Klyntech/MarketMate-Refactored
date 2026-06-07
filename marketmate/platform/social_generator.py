"""
marketmate/platform/social_generator.py
──────────────────────────────────────────
AI-powered marketing content generator for MarketMate social channels.

Generates MARKETING and EXPOSURE posts — NOT trading signal posts.
Content types focus on brand awareness, feature highlights, community
engagement, and promotional campaigns.

Post types:
  - brand_awareness    — Who MarketMate is and what we do
  - feature_highlight  — Deep dives into specific capabilities
  - community_engage   — Questions, polls, engagement hooks
  - educational_tip    — Market intelligence knowledge drops
  - milestone          — Growth metrics, launches, achievements
  - promotional        — API key promotions, limited offers
  - social_proof       — Testimonials, usage stats, case studies
"""

from __future__ import annotations

import random
from datetime import datetime, timezone
from typing import Optional

from marketmate.core.logger import get_logger
from marketmate.core.config import cfg

log = get_logger("platform.social_generator")


# ═══════════════════════════════════════════════════════════════════════════════
# Marketing post templates — each returns a dict with "content" and "platforms"
# ═══════════════════════════════════════════════════════════════════════════════

BRAND_AWARENESS_TEMPLATES = [
    {
        "content": (
            "Market Intelligence. Not Market Noise. 🔥\n\n"
            "MarketMate converts live market structure, liquidity behavior, "
            "and regime transitions into structured, machine-readable intelligence.\n\n"
            "5 Brains. 8 Gates. 1 Conviction Score.\n\n"
            "→ marketmate.io"
        ),
        "platforms": ["twitter", "facebook", "telegram"],
    },
    {
        "content": (
            "What if your trading tools could THINK? 🧠\n\n"
            "MarketMate's 5-Brain Architecture doesn't just react to price — "
            "it understands market structure, detects institutional flow, and "
            "scores conviction in real-time.\n\n"
            "This is financial intelligence infrastructure.\n\n"
            "→ marketmate.io"
        ),
        "platforms": ["twitter", "facebook", "instagram", "telegram"],
    },
    {
        "content": (
            "Stop guessing. Start understanding. 💡\n\n"
            "MarketMate doesn't give you signals — it gives you STRUCTURE.\n\n"
            "Real-time market state engine converting conviction, regime, "
            "bias, and liquidity behavior into actionable intelligence.\n\n"
            "Built for traders who think differently.\n\n"
            "→ marketmate.io"
        ),
        "platforms": ["twitter", "facebook", "telegram"],
    },
    {
        "content": (
            "The market speaks a language. MarketMate translates it. 📡\n\n"
            "Our 5-Brain Architecture processes:\n"
            "→ Strategy alignment\n"
            "→ Directional bias\n"
            "→ Liquidity sweeps\n"
            "→ Supply/demand zones\n"
            "→ Multi-timeframe confirmation\n\n"
            "All compiled into one conviction score.\n\n"
            "→ marketmate.io"
        ),
        "platforms": ["twitter", "facebook", "instagram", "telegram"],
    },
]

FEATURE_HIGHLIGHT_TEMPLATES = [
    {
        "content": (
            "⚡ MATE — Your Market Intelligence Co-Pilot\n\n"
            "Ask MATE anything about market structure, conviction, or regime. "
            "Get AI-powered interpretations built on compiled market state, not raw indicators.\n\n"
            "Like GitHub Copilot, but for financial intelligence.\n\n"
            "→ marketmate.io/#mate"
        ),
        "platforms": ["twitter", "facebook", "telegram"],
    },
    {
        "content": (
            "🚦 The Gate Pipeline: 8 Layers of Signal Quality\n\n"
            "Most market noise fails at Gate 1-3. By Gate 8, only validated "
            "intelligence remains.\n\n"
            "G1: Structural Alignment\n"
            "G2: Timeframe Confluence\n"
            "G3: Volume Validation\n"
            "G4: Liquidity Context\n"
            "G5: Regime Compatibility\n"
            "G6: Conviction Threshold\n"
            "G7: Recency Check\n"
            "G8: Final Compilation\n\n"
            "Quality over quantity. Every time."
        ),
        "platforms": ["twitter", "facebook", "instagram", "telegram"],
    },
    {
        "content": (
            "💧 SweepBrain: Detecting Institutional Order Flow\n\n"
            "When price moves beyond a key level to trigger stops then REVERSES — "
            "that's a liquidity sweep. That's institutional order flow in action.\n\n"
            "SweepBrain detects these in real-time and scores confidence "
            "based on rejection speed, volume, and multi-brain confluence.\n\n"
            "→ marketmate.io"
        ),
        "platforms": ["twitter", "facebook", "telegram"],
    },
    {
        "content": (
            "📊 Conviction Scoring: -1.0 to +1.0\n\n"
            "Not a binary BUY/SELL signal. A continuous spectrum of market state quality.\n\n"
            "+0.5 to +1.0 → Strong bullish conditions\n"
            "-0.5 to -1.0 → Strong bearish pressure\n"
            "Near 0 → Transitional — be careful\n\n"
            "5 Brains contribute. CompiledCore aggregates. "
            "The result is nuanced, not noise.\n\n"
            "→ marketmate.io"
        ),
        "platforms": ["twitter", "facebook", "instagram", "telegram"],
    },
    {
        "content": (
            "🔌 Developer? We built this for you.\n\n"
            "The MarketMate API gives you programmatic access to real-time "
            "market intelligence:\n\n"
            "• REST API + WebSocket streams\n"
            "• Official SDKs (Python, TypeScript)\n"
            "• Conviction, regime, bias — all structured\n"
            "• Sandbox environment for testing\n\n"
            "Get your API key → marketmate.io"
        ),
        "platforms": ["twitter", "facebook", "telegram"],
    },
]

COMMUNITY_ENGAGE_TEMPLATES = [
    {
        "content": (
            "Question for the community: 🤔\n\n"
            "What's your biggest challenge with market analysis?\n\n"
            "A) Too much noise, not enough signal\n"
            "B) No structured approach to conviction\n"
            "C) Emotion-driven decisions\n"
            "D) All of the above\n\n"
            "Drop your answer below 👇"
        ),
        "platforms": ["twitter", "facebook", "instagram"],
    },
    {
        "content": (
            "Hot take: Most trading tools give you MORE data when what you need "
            "is MORE STRUCTURE. 🎯\n\n"
            "Agree or disagree? Let's discuss."
        ),
        "platforms": ["twitter", "facebook"],
    },
    {
        "content": (
            "The best traders don't predict the market.\n"
            "They UNDERSTAND the market. 🧠\n\n"
            "What's one market structure concept that changed your trading? "
            "Share below 👇"
        ),
        "platforms": ["twitter", "facebook", "instagram"],
    },
]

EDUCATIONAL_TIP_TEMPLATES = [
    {
        "content": (
            "📚 Market Intelligence 101: What is a Liquidity Sweep?\n\n"
            "A liquidity sweep occurs when price moves beyond a key level "
            "to trigger stop losses, then rapidly reverses.\n\n"
            "Why it matters:\n"
            "• It reveals institutional order flow\n"
            "• The reversal often leads to significant moves\n"
            "• Smart money uses sweeps to fill large positions\n\n"
            "MarketMate's SweepBrain detects these in real-time.\n\n"
            "→ marketmate.io"
        ),
        "platforms": ["twitter", "facebook", "instagram", "telegram"],
    },
    {
        "content": (
            "📚 Market Intelligence 101: Regime Detection\n\n"
            "Every market is in one of three states:\n\n"
            "Trending → Momentum plays, trend-following\n"
            "Ranging → Mean-reversion, fade the extremes\n"
            "Volatile → Reduced sizing, wait for confirmation\n\n"
            "Applying the wrong strategy to the wrong regime = losses.\n\n"
            "MarketMate detects regime in real-time so you always "
            "have the right framework.\n\n"
            "→ marketmate.io"
        ),
        "platforms": ["twitter", "facebook", "telegram"],
    },
    {
        "content": (
            "📚 Market Intelligence 101: The -1.0 to +1.0 Conviction Spectrum\n\n"
            "Most tools give you BUY or SELL. MarketMate gives you a "
            "continuous conviction score.\n\n"
            "Why continuous?\n"
            "• Markets aren't binary\n"
            "• Low conviction ≠ wrong, it means WAIT\n"
            "• The transition from low to high conviction IS the opportunity\n\n"
            "Structure over noise. Always.\n\n"
            "→ marketmate.io"
        ),
        "platforms": ["twitter", "facebook", "instagram", "telegram"],
    },
]

MILESTONE_TEMPLATES = [
    {
        "content": (
            "📈 Milestone: MarketMate is LIVE!\n\n"
            "Financial Intelligence Infrastructure is now accessible to "
            "every trader and developer.\n\n"
            "• Real-time market state engine\n"
            "• AI-powered MATE interpreter\n"
            "• REST API + WebSocket streams\n"
            "• Official SDKs\n\n"
            "This is just the beginning. 🚀\n\n"
            "→ marketmate.io"
        ),
        "platforms": ["twitter", "facebook", "instagram", "telegram"],
    },
    {
        "content": (
            "🎉 MATE v2.0 is here!\n\n"
            "Your Market Intelligence Co-Pilot just got a major upgrade:\n\n"
            "✓ Enhanced 5-Brain context\n"
            "✓ Real-time interpretation\n"
            "✓ Natural language queries\n"
            "✓ Conviction analysis on demand\n\n"
            "Like GitHub Copilot, but for market intelligence.\n\n"
            "→ marketmate.io/#mate"
        ),
        "platforms": ["twitter", "facebook", "telegram"],
    },
]

PROMOTIONAL_TEMPLATES = [
    {
        "content": (
            "🔑 Get your MarketMate API key — FREE\n\n"
            "Access real-time market intelligence:\n"
            "• Conviction scores for major pairs\n"
            "• Regime detection (Trending/Ranging/Volatile)\n"
            "• Liquidity sweep alerts\n"
            "• WebSocket real-time streams\n\n"
            "No credit card required. Start building today.\n\n"
            "→ marketmate.io"
        ),
        "platforms": ["twitter", "facebook", "telegram"],
    },
    {
        "content": (
            "⚡ FREE API Key — Limited Time\n\n"
            "Get programmatic access to MarketMate's intelligence layer:\n\n"
            "→ GET /market-state — All tracked instruments\n"
            "→ POST /mate/query — AI market interpretation\n"
            "→ WS /stream — Real-time WebSocket updates\n\n"
            "Python & TypeScript SDKs included.\n\n"
            "Claim yours → marketmate.io"
        ),
        "platforms": ["twitter", "facebook", "telegram"],
    },
]

SOCIAL_PROOF_TEMPLATES = [
    {
        "content": (
            "Numbers don't lie. 📊\n\n"
            "MarketMate's 5-Brain Architecture processes:\n"
            "→ Strategy alignment\n"
            "→ Directional bias\n"
            "→ Liquidity sweeps\n"
            "→ Supply/demand zones\n"
            "→ Multi-timeframe confirmation\n\n"
            "And compiles it all into ONE conviction score.\n\n"
            "Structured intelligence > gut feelings.\n\n"
            "→ marketmate.io"
        ),
        "platforms": ["twitter", "facebook", "instagram", "telegram"],
    },
]

# ═══════════════════════════════════════════════════════════════════════════════
# Template registry
# ═══════════════════════════════════════════════════════════════════════════════

TEMPLATE_REGISTRY: dict[str, list[dict]] = {
    "brand_awareness": BRAND_AWARENESS_TEMPLATES,
    "feature_highlight": FEATURE_HIGHLIGHT_TEMPLATES,
    "community_engage": COMMUNITY_ENGAGE_TEMPLATES,
    "educational_tip": EDUCATIONAL_TIP_TEMPLATES,
    "milestone": MILESTONE_TEMPLATES,
    "promotional": PROMOTIONAL_TEMPLATES,
    "social_proof": SOCIAL_PROOF_TEMPLATES,
}

VALID_POST_TYPES = list(TEMPLATE_REGISTRY.keys())


# ═══════════════════════════════════════════════════════════════════════════════
# AI-powered generation (using MarketMate's LLM stack)
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_ai_marketing_post(
    post_type: str,
    context: str = "",
    platforms: list[str] | None = None,
) -> dict | None:
    """
    Generate a marketing post using AI (via the LLM stack).

    Returns a dict with "content" and "platforms", or None on failure.
    """
    if post_type not in VALID_POST_TYPES:
        log.warning("invalid_post_type", post_type=post_type)
        return None

    try:
        from marketmate.core.llm import generate_text

        platform_hint = ", ".join(platforms) if platforms else "Twitter, Facebook, Instagram, Telegram"

        prompt = f"""You are MarketMate's social media marketing manager. Generate a {post_type.replace('_', ' ')} post for the MarketMate brand.

About MarketMate:
- Financial Intelligence Infrastructure company
- Real-time market state engine for traders, developers, and automated systems
- 5-Brain Architecture (StrategyBrain, BiasBrain, SweepBrain, ZoneBrain, ConfirmBrain)
- 8-Gate Pipeline for signal quality validation
- Conviction Scoring: -1.0 to +1.0 continuous spectrum
- MATE: AI-powered Market Intelligence Co-Pilot (like GitHub Copilot for financial intelligence)
- REST API + WebSocket streams, Python & TypeScript SDKs
- Website: marketmate.io

Post requirements:
- Type: {post_type.replace('_', ' ')}
- Target platforms: {platform_hint}
- Engaging, professional, and on-brand
- Include relevant emojis sparingly
- End with → marketmate.io where appropriate
- Keep it under 280 characters for Twitter compatibility
- Do NOT include trading signals or specific price predictions
- Focus on MARKETING and EXPOSURE, not trading advice
{f"- Additional context: {context}" if context else ""}

Generate ONLY the post text, nothing else."""

        content = await generate_text(prompt, max_tokens=300)

        if content and len(content.strip()) > 10:
            return {
                "content": content.strip(),
                "platforms": platforms or ["twitter", "facebook", "telegram"],
            }

    except Exception as exc:
        log.warning("ai_generation_failed", error=str(exc), post_type=post_type)

    return None


# ═══════════════════════════════════════════════════════════════════════════════
# Template-based generation (fallback)
# ═══════════════════════════════════════════════════════════════════════════════

def generate_template_post(
    post_type: str,
    platforms: list[str] | None = None,
) -> dict | None:
    """
    Generate a marketing post from pre-written templates.

    Returns a dict with "content" and "platforms", or None if no templates.
    """
    templates = TEMPLATE_REGISTRY.get(post_type, [])
    if not templates:
        log.warning("no_templates_for_type", post_type=post_type)
        return None

    template = random.choice(templates)
    result = {
        "content": template["content"],
        "platforms": platforms or template["platforms"],
    }
    return result


# ═══════════════════════════════════════════════════════════════════════════════
# Main generation entry point
# ═══════════════════════════════════════════════════════════════════════════════

async def generate_marketing_post(
    post_type: str = "brand_awareness",
    use_ai: bool = True,
    context: str = "",
    platforms: list[str] | None = None,
) -> dict | None:
    """
    Generate a marketing post for MarketMate's social channels.

    Tries AI generation first (if enabled), falls back to template-based.

    Returns a dict with "content" and "platforms", or None on failure.
    """
    if post_type not in VALID_POST_TYPES:
        log.warning("invalid_post_type", post_type=post_type,
                     valid_types=VALID_POST_TYPES)
        return None

    # Try AI generation first
    if use_ai and cfg.social.use_ai_generation:
        result = await generate_ai_marketing_post(
            post_type=post_type,
            context=context,
            platforms=platforms,
        )
        if result:
            log.info("marketing_post_generated_ai", post_type=post_type)
            return result

    # Fallback to template
    result = generate_template_post(post_type, platforms)
    if result:
        log.info("marketing_post_generated_template", post_type=post_type)

    return result
