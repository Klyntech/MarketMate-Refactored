"""
marketmate.memory.vector_store
───────────────────────────────
ChromaDB-backed persistent vector memory for the MATE AI agent
and MATE-Ops system.

Provides semantic search over conversations, observations, and
arbitrary documents. Uses ChromaDB with the default
all-MiniLM-L6-v2 embedding model (via sentence-transformers).

All ChromaDB calls are synchronous — async methods wrap them
with ``asyncio.to_thread()`` to avoid blocking the event loop.

Falls back to an in-memory dict when ChromaDB is not installed,
so the rest of the application can start without it.
"""

from __future__ import annotations

import asyncio
import json
import os
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from marketmate.core.logger import get_logger

log = get_logger("memory.vector_store")

# ── ChromaDB availability check ──────────────────────────────────────────────

try:
    import chromadb
    from chromadb.config import Settings as ChromaSettings
    _CHROMA_AVAILABLE = True
except ImportError:
    _CHROMA_AVAILABLE = False


# ── Helpers ──────────────────────────────────────────────────────────────────

def _default_persist_dir() -> str:
    """Return the ChromaDB persist directory.

    Priority:
      1. ``CHROMA_PERSIST_DIR`` environment variable
      2. ``./data/chroma`` fallback
    """
    return os.getenv("CHROMA_PERSIST_DIR", "./data/chroma")


def _now_iso() -> str:
    """Current UTC timestamp in ISO 8601 format."""
    return datetime.now(timezone.utc).isoformat()


def _new_id(provided: Optional[str] = None) -> str:
    """Return a document ID — use *provided* if given, else generate UUID4."""
    return provided or str(uuid.uuid4())


# ── In-Memory Fallback ───────────────────────────────────────────────────────
# Used when ChromaDB is not installed. Stores documents in a plain dict
# and does simple substring matching instead of semantic search.

class _InMemoryStore:
    """Minimal in-memory fallback when ChromaDB is unavailable."""

    def __init__(self) -> None:
        self._docs: Dict[str, Dict[str, Any]] = {}

    def add(self, doc_id: str, text: str, metadata: Optional[dict] = None) -> str:
        self._docs[doc_id] = {
            "id": doc_id,
            "text": text,
            "metadata": metadata or {},
        }
        return doc_id

    def search(self, query: str, n_results: int = 5, filter_metadata: Optional[dict] = None) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        results: List[Dict[str, Any]] = []
        for doc in self._docs.values():
            meta = doc.get("metadata", {})
            # Apply metadata filters
            if filter_metadata:
                match = all(
                    meta.get(k) == v for k, v in filter_metadata.items()
                )
                if not match:
                    continue
            # Simple substring matching
            if query_lower in doc["text"].lower():
                results.append({
                    "id": doc["id"],
                    "text": doc["text"],
                    "metadata": meta,
                    "distance": 0.0,
                })
        return results[:n_results]

    def delete(self, doc_id: str) -> bool:
        if doc_id in self._docs:
            del self._docs[doc_id]
            return True
        return False

    def count(self) -> int:
        return len(self._docs)

    def clear(self) -> int:
        count = len(self._docs)
        self._docs.clear()
        return count


# ── MemoryStore ──────────────────────────────────────────────────────────────

class MemoryStore:
    """
    Persistent vector memory powered by ChromaDB.

    Provides semantic search over documents, conversation turns,
    and MATE-Ops observations. Falls back to an in-memory store
    when ChromaDB is not installed.

    Usage::

        store = MemoryStore()
        doc_id = await store.add("XAUUSD bullish bias", metadata={"source": "signal"})
        results = await store.search("gold trend")
    """

    def __init__(
        self,
        persist_dir: str = "",
        collection_name: str = "mate_memory",
    ) -> None:
        self._persist_dir = persist_dir or _default_persist_dir()
        self._collection_name = collection_name
        self._client: Any = None
        self._collection: Any = None
        self._fallback = _InMemoryStore()
        self._enabled: bool = False

        self._init_chroma()

    # ── Initialisation ────────────────────────────────────────────────────

    def _init_chroma(self) -> None:
        """Attempt to initialise the ChromaDB persistent client."""
        if not _CHROMA_AVAILABLE:
            log.warning(
                "chromadb_not_available",
                reason="chromadb package not installed",
                hint="pip install chromadb sentence-transformers",
            )
            return

        try:
            self._client = chromadb.PersistentClient(
                path=self._persist_dir,
            )
            self._collection = self._client.get_or_create_collection(
                name=self._collection_name,
                metadata={"hnsw:space": "cosine"},
            )
            self._enabled = True
            log.info(
                "chromadb_initialised",
                persist_dir=self._persist_dir,
                collection=self._collection_name,
                existing_docs=self._collection.count(),
            )
        except Exception as exc:
            log.warning(
                "chromadb_init_failed",
                error=str(exc),
                hint="Falling back to in-memory vector store",
            )
            self._client = None
            self._collection = None

    # ── Core Operations ───────────────────────────────────────────────────

    async def add(
        self,
        text: str,
        metadata: Optional[dict] = None,
        doc_id: Optional[str] = None,
    ) -> str:
        """Add a document to the vector store and return its ID.

        Args:
            text: The document text to embed and store.
            metadata: Optional key-value metadata attached to the document.
            doc_id: Optional explicit ID; auto-generated UUID4 if omitted.

        Returns:
            The document ID (either provided or generated).
        """
        doc_id = _new_id(doc_id)
        metadata = metadata or {}
        metadata.setdefault("created_at", _now_iso())

        if self._enabled and self._collection is not None:
            try:
                await asyncio.to_thread(
                    self._collection.add,
                    ids=[doc_id],
                    documents=[text],
                    metadatas=[metadata],
                )
                log.debug("document_added", doc_id=doc_id, text_len=len(text))
                return doc_id
            except Exception as exc:
                log.warning(
                    "chromadb_add_failed",
                    doc_id=doc_id,
                    error=str(exc),
                    hint="Falling back to in-memory store for this document",
                )

        # Fallback
        self._fallback.add(doc_id, text, metadata)
        log.debug("document_added_fallback", doc_id=doc_id, text_len=len(text))
        return doc_id

    async def search(
        self,
        query: str,
        n_results: int = 5,
        filter_metadata: Optional[dict] = None,
    ) -> List[Dict[str, Any]]:
        """Semantic search across all stored documents.

        Args:
            query: The search query text.
            n_results: Maximum number of results to return.
            filter_metadata: Optional ChromaDB metadata filter
                (e.g. ``{"source": "signal"}``).

        Returns:
            List of dicts with keys ``id``, ``text``, ``metadata``, ``distance``.
        """
        if self._enabled and self._collection is not None:
            try:
                kwargs: Dict[str, Any] = {
                    "query_texts": [query],
                    "n_results": n_results,
                }
                if filter_metadata:
                    kwargs["where"] = filter_metadata

                results = await asyncio.to_thread(
                    self._collection.query,
                    **kwargs,
                )

                # ChromaDB returns parallel lists — zip them into dicts
                ids = results.get("ids", [[]])[0]
                documents = results.get("documents", [[]])[0]
                metadatas = results.get("metadatas", [[]])[0]
                distances = results.get("distances", [[]])[0]

                return [
                    {
                        "id": doc_id,
                        "text": doc,
                        "metadata": meta,
                        "distance": dist,
                    }
                    for doc_id, doc, meta, dist in zip(
                        ids, documents, metadatas, distances
                    )
                ]
            except Exception as exc:
                log.warning(
                    "chromadb_search_failed",
                    error=str(exc),
                    hint="Falling back to in-memory search",
                )

        # Fallback
        return self._fallback.search(query, n_results, filter_metadata)

    async def delete(self, doc_id: str) -> bool:
        """Delete a document by ID.

        Args:
            doc_id: The document ID to delete.

        Returns:
            ``True`` if the document was found and deleted, ``False`` otherwise.
        """
        if self._enabled and self._collection is not None:
            try:
                await asyncio.to_thread(
                    self._collection.delete,
                    ids=[doc_id],
                )
                log.debug("document_deleted", doc_id=doc_id)
                return True
            except Exception as exc:
                log.warning("chromadb_delete_failed", doc_id=doc_id, error=str(exc))

        # Fallback
        return self._fallback.delete(doc_id)

    async def clear(self) -> int:
        """Clear all documents from the collection.

        Returns:
            The number of documents that were deleted.
        """
        if self._enabled and self._collection is not None:
            try:
                count = await asyncio.to_thread(self._collection.count)
                # Delete all by getting all IDs first
                all_ids_result = await asyncio.to_thread(
                    self._collection.get,
                )
                all_ids = all_ids_result.get("ids", [])
                if all_ids:
                    await asyncio.to_thread(
                        self._collection.delete,
                        ids=all_ids,
                    )
                log.info("collection_cleared", deleted_count=count)
                return count
            except Exception as exc:
                log.warning("chromadb_clear_failed", error=str(exc))

        # Fallback
        return self._fallback.clear()

    async def get_stats(self) -> Dict[str, Any]:
        """Return collection statistics.

        Returns:
            Dict with at least ``document_count`` and ``enabled`` keys.
        """
        if self._enabled and self._collection is not None:
            try:
                count = await asyncio.to_thread(self._collection.count)
                return {
                    "document_count": count,
                    "enabled": True,
                    "backend": "chromadb",
                    "persist_dir": self._persist_dir,
                    "collection_name": self._collection_name,
                }
            except Exception as exc:
                log.warning("chromadb_stats_failed", error=str(exc))

        return {
            "document_count": self._fallback.count(),
            "enabled": False,
            "backend": "in_memory_fallback",
        }

    # ── Conversation Helpers ──────────────────────────────────────────────

    async def add_conversation(
        self,
        user_msg: str,
        assistant_msg: str,
        session_id: str = "",
    ) -> str:
        """Store a conversation turn with metadata.

        The user and assistant messages are stored as a single combined
        document so that semantic search can match across the full context
        of the exchange.

        Args:
            user_msg: The user's message.
            assistant_msg: The assistant's reply.
            session_id: Optional session identifier for grouping turns.

        Returns:
            The document ID of the stored conversation turn.
        """
        combined = f"User: {user_msg}\nAssistant: {assistant_msg}"
        metadata: Dict[str, Any] = {
            "type": "conversation",
            "user_msg": user_msg,
            "assistant_msg": assistant_msg,
            "session_id": session_id,
            "created_at": _now_iso(),
        }
        doc_id = _new_id()
        return await self.add(combined, metadata=metadata, doc_id=doc_id)

    async def search_conversations(
        self,
        query: str,
        session_id: str = "",
        n_results: int = 5,
    ) -> List[Dict[str, Any]]:
        """Search conversation history.

        Args:
            query: The search query.
            session_id: If provided, restrict results to this session.
            n_results: Maximum number of results.

        Returns:
            List of matching conversation turns.
        """
        filter_meta: Dict[str, Any] = {"type": "conversation"}
        if session_id:
            filter_meta["session_id"] = session_id

        return await self.search(query, n_results=n_results, filter_metadata=filter_meta)

    # ── MATE-Ops Observation Helpers ──────────────────────────────────────

    async def add_observation(self, observation: dict) -> str:
        """Store a MATE-Ops observation for historical analysis.

        Args:
            observation: A dict representing an observation. Expected keys
                include ``source``, ``status``, ``message``, ``details``,
                ``timestamp`` — but any structure is accepted.

        Returns:
            The document ID of the stored observation.
        """
        # Build a searchable text representation
        source = observation.get("source", "unknown")
        status = observation.get("status", "unknown")
        message = observation.get("message", "")
        details = observation.get("details", {})

        text = f"[{source}] {status}: {message}"
        if details:
            text += f" | Details: {json.dumps(details, default=str)}"

        metadata: Dict[str, Any] = {
            "type": "observation",
            "source": source,
            "status": status,
            "created_at": observation.get("timestamp", _now_iso()),
        }

        doc_id = _new_id()
        return await self.add(text, metadata=metadata, doc_id=doc_id)

    async def search_observations(
        self,
        query: str,
        source: str = "",
        n_results: int = 10,
    ) -> List[Dict[str, Any]]:
        """Search past MATE-Ops observations.

        Args:
            query: The search query.
            source: If provided, restrict results to this observation source
                (e.g. ``"api"``, ``"redis"``, ``"mongodb"``).
            n_results: Maximum number of results.

        Returns:
            List of matching observations.
        """
        filter_meta: Dict[str, Any] = {"type": "observation"}
        if source:
            filter_meta["source"] = source

        return await self.search(query, n_results=n_results, filter_metadata=filter_meta)
