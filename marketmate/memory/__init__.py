"""
marketmate.memory
──────────────────
ChromaDB vector memory for the MATE AI agent and MATE-Ops system.

Provides persistent semantic search over conversations, observations,
and arbitrary documents. Uses ChromaDB with all-MiniLM-L6-v2 embeddings
by default; falls back to an in-memory store when ChromaDB is not installed.

Quick start::

    from marketmate.memory import memory_store

    # Add a document
    doc_id = await memory_store.add("XAUUSD bullish bias", metadata={"source": "signal"})

    # Semantic search
    results = await memory_store.search("gold trend")

    # Store a conversation turn
    await memory_store.add_conversation("What is the bias?", "Bullish on XAUUSD", session_id="s1")

    # Store a MATE-Ops observation
    await memory_store.add_observation({"source": "api", "status": "ok", "message": "API healthy"})
"""

from marketmate.memory.vector_store import MemoryStore

__all__ = [
    "MemoryStore",
    "memory_store",
]

# ── Singleton ────────────────────────────────────────────────────────────────
# Lazily created on first import. Uses CHROMA_PERSIST_DIR env var
# or falls back to ./data/chroma.

memory_store = MemoryStore()
