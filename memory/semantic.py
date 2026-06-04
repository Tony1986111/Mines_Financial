from __future__ import annotations

import json
import os
import threading
from pathlib import Path

from langchain_chroma import Chroma
from langchain_community.embeddings import JinaEmbeddings
from langchain_core.documents import Document

BASE_DIR = Path(__file__).resolve().parents[1]
CHROMA_DIR        = BASE_DIR / "chroma_db"
COLLECTION_NAME    = "conclusions"          # separate from the "reports" collection
EMBED_MODEL        = "jina-embeddings-v3"
CACHE_THRESHOLD   = 0.95   # L1: direct cache hit — return answer without RAG
CONTEXT_THRESHOLD = 0.80   # L2: supplementary context — run full pipeline but seed LLM

_vs_lock: threading.Lock = threading.Lock()
_vs_instance: Chroma | None = None


def _get_vectorstore() -> Chroma:
    """Lazy-load the conclusions ChromaDB collection (thread-safe)."""
    global _vs_instance
    if _vs_instance is not None:
        return _vs_instance
    with _vs_lock:
        if _vs_instance is None:
            api_key = os.getenv("JINA_API_KEY") or os.getenv("JINA_API_KEY_1")
            if not api_key:
                raise RuntimeError("JINA_API_KEY or JINA_API_KEY_1 is required.")
            embeddings = JinaEmbeddings(jina_api_key=api_key, model_name=EMBED_MODEL)
            _vs_instance = Chroma(
                collection_name=COLLECTION_NAME,
                embedding_function=embeddings,
                persist_directory=str(CHROMA_DIR),
            )
    return _vs_instance


def search_conclusions(query: str) -> tuple[str, list, float]:
    """Search for a semantically similar past answer.

    Returns (answer, sources, score). On no match: ("", [], 0.0).
    Callers use the score to decide which tier applies:
      score >= CACHE_THRESHOLD  → L1: skip RAG, return answer directly
      score >= CONTEXT_THRESHOLD → L2: run full pipeline, seed LLM with answer
    """
    if not query.strip():
        return "", [], 0.0
    try:
        results = _get_vectorstore().similarity_search_with_relevance_scores(query, k=1)
        if results and results[0][1] >= CONTEXT_THRESHOLD:
            meta    = results[0][0].metadata
            answer  = meta.get("answer", "")
            try:
                sources = json.loads(meta.get("sources", "[]"))
            except Exception:
                sources = []
            return answer, sources, results[0][1]
    except Exception:
        pass
    return "", [], 0.0


def save_conclusion(
    query: str,
    answer: str,
    companies: list[str],
    fy: str,
    sources: list | None = None,
) -> None:
    """Persist a high-quality answer so it can be surfaced as context in future queries.

    Stores the query as page_content so similarity search compares query-to-query.
    The answer and sources are kept in metadata and retrieved on a cache hit.
    """
    if not query.strip() or not answer.strip():
        return
    try:
        doc = Document(
            page_content=query,
            metadata={
                "answer":    answer,
                "companies": ",".join(companies),
                "fy":        fy,
                "sources":   json.dumps(sources or []),
            },
        )
        _get_vectorstore().add_documents([doc])
    except Exception:
        pass
