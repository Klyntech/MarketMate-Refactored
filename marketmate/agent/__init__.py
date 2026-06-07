"""
marketmate.agent
─────────────────
LangGraph-based agent pipeline for the MATE AI system.

This module provides a graph-based workflow that routes queries
through different brains and tools. It degrades gracefully when
langgraph is not installed — falling back to a simple sequential
pipeline that calls the LLM directly.

Usage:
    from marketmate.agent import MateAgentPipeline, mate_pipeline

    # Use the pre-built singleton
    result = await mate_pipeline.run(
        query="What's the price of gold?",
        session_id="user_123",
    )

    # Or create a custom instance
    pipeline = MateAgentPipeline(
        authority_level=1,
        memory_store=my_redis_store,
    )
    result = await pipeline.run(query="Check system health")

Exports:
    MateAgentPipeline — The main pipeline class
    mate_pipeline     — Pre-configured singleton instance
"""

from marketmate.agent.pipeline import MateAgentPipeline

__all__ = [
    "MateAgentPipeline",
    "mate_pipeline",
]

# ─── Singleton ────────────────────────────────────────────────────────────────

mate_pipeline = MateAgentPipeline()
