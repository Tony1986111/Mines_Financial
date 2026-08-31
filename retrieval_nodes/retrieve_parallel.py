"""
retrieve_parallel.py - Parallel Retrieval Node

This module is the core retrieval layer in the RAG architecture.
It implements hybrid retrieval by combining keyword search (BM25)
with vector semantic search (ChromaDB), fuses the two result sets with
EnsembleRetriever, and reranks the fused pool with a cross-encoder.

Basic RAG flow:
  User question
     │
     ▼
  Retriever (this file) ──→ find relevant excerpts from the document store
     │
     ▼
  LLM generates an answer using retrieved excerpts as context

Why hybrid retrieval?
  - BM25 is strong at exact keyword matching, such as company names, financial terms, and years.
  - Vector search is strong at semantic matching, such as matching "profitability" to related earnings terms.
  - Combining both improves coverage and reduces the blind spots of either approach alone.
"""

from __future__ import annotations

import os
import pickle
import threading
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
# EnsembleRetriever merges multiple retriever result sets into one ranked list.
from langchain_classic.retrievers import EnsembleRetriever
# JinaEmbeddings converts text into vectors for semantic similarity search.
from langchain_community.embeddings import JinaEmbeddings
# Chroma is the local vector store used to persist and query embeddings.
from langchain_chroma import Chroma
# JinaRerank is a cross-encoder reranker: it scores each query/document pair
# directly instead of fusing rank positions the way EnsembleRetriever does.
from langchain_community.document_compressors import JinaRerank
# Document is LangChain's standard container for page content and metadata.
from langchain_core.documents import Document

# CompanyDocsState carries the company and query for one retrieval branch.
from state import CompanyDocsState, RetrievedDoc

load_dotenv()  # Load API keys and other environment variables from .env.

# --- Path configuration -------------------------------------------------------
# Path(__file__) points to this file; parents[1] resolves to the project root.
BASE_DIR = Path(__file__).resolve().parents[1]
CHROMA_DIR = BASE_DIR / "chroma_db"       # ChromaDB persistence directory.
BM25_DIR = BASE_DIR / "bm25_index"      # Per-company BM25 pkl directory.
COLLECTION_NAME = "reports"               # Chroma collection name.
EMBED_MODEL = "jina-embeddings-v3"        # Jina embedding model name.

# --- Retrieval parameters -----------------------------------------------------
# These values directly affect retrieval quality and are common RAG tuning knobs.
 
# Candidate pools are deliberately wider than FINAL_K: the cross-encoder rerank
# below picks the final FINAL_K from them by reading content, so a wide pool
# raises the recall ceiling without increasing downstream token cost.
BM25_K = 20  # Number of BM25 candidates to retrieve.
CHROMA_K = 20  # Number of vector-search candidates to retrieve.
FINAL_K = 8  # Final number of deduped documents passed downstream.

# Fusion weights for the two retrieval paths. They should sum to 1.0.
# Chroma is weighted slightly higher to favor semantic matching.
# Increase BM25_WEIGHT when exact financial terms are more important.
BM25_WEIGHT = 0.45
CHROMA_WEIGHT = 0.55

# Cross-encoder used to rerank the fused candidate pool. Unlike RRF above, it
# reads the actual query/document text rather than fusing rank positions only.
RERANK_MODEL = "jina-reranker-v2-base-multilingual"


# --- Lazy retriever loading ---------------------------------------------------
# LangGraph calls node functions as the graph advances.
# Loading indexes and embedding clients on every call would be slow, so these
# module-level singleton loaders initialize once and then reuse the same objects.

_bm25_lock = threading.Lock()
_bm25_cache: dict[str, Any] = {}  # company → BM25Retriever

def _load_bm25_retriever(company: str):
    """
    Load the per-company BM25 retriever, initialising once and caching.

    Each company has its own pkl file under BM25_DIR (e.g. bm25_index/FMG.pkl)
    built from only that company's chunks, so BM25 results are always
    company-scoped and never wasted on cross-company documents.
    """
    if company in _bm25_cache:
        return _bm25_cache[company]
    with _bm25_lock:
        if company not in _bm25_cache:
            pkl_path = BM25_DIR / f"{company}.pkl"
            if not pkl_path.exists():
                raise FileNotFoundError(
                    f"BM25 index not found at {pkl_path}. "
                    f"Run `uv run python ingest/step_5_bm25.py` first."
                )
            with pkl_path.open("rb") as f:
                retriever = pickle.load(f)
            retriever.k = BM25_K
            _bm25_cache[company] = retriever
    return _bm25_cache[company]


_vectorstore_lock = threading.Lock()
_vectorstore_instance: Chroma | None = None

def _load_vectorstore() -> Chroma:
    """
    Load the ChromaDB vector store.

    Vector retrieval works in two stages:
    1. Ingest time: each document chunk is embedded and stored in Chroma.
    2. Query time: the user query is embedded and matched against nearby vectors.

    JinaEmbeddings calls Jina's API, so JINA_API_KEY is required.
    """
    global _vectorstore_instance
    if _vectorstore_instance is not None:
        return _vectorstore_instance
    with _vectorstore_lock:
        if _vectorstore_instance is None:
            if not CHROMA_DIR.exists():
                raise FileNotFoundError(
                    f"ChromaDB not found at {CHROMA_DIR}. Run `uv run python ingest.py` first."
                )
            api_key = os.getenv("JINA_API_KEY")
            if not api_key:
                raise RuntimeError("JINA_API_KEY is required.")
            embeddings = JinaEmbeddings(jina_api_key=api_key, model_name=EMBED_MODEL)
            # persist_directory tells Chroma where to store data on disk.
            _vectorstore_instance = Chroma(
                collection_name=COLLECTION_NAME,
                embedding_function=embeddings,
                persist_directory=str(CHROMA_DIR),
            )
    return _vectorstore_instance


# --- Helpers ------------------------------------------------------------------

def _matches_company(doc: Document, company: str) -> bool:
    """
    Return whether a document belongs to the requested company.

    Metadata is written during ingest, for example:
      {"company": "APPL", "source": "reports/APPL_2023.pdf", "page": 12, ...}
    The comparison is case-insensitive.
    """
    return str((doc.metadata or {}).get("company", "")).upper() == company


def _doc_key(doc: Document) -> tuple[Any, ...]:
    """
    Build a deduplication key for a document.

    BM25 and vector search can return the same chunk. Use
    (source, page, chunk_index) as a stable identifier when available.
    For older documents without full metadata, fall back to the first
    300 characters of the document content.
    """
    meta = doc.metadata or {}
    source = meta.get("source")
    page = meta.get("page")
    chunk_index = meta.get("chunk_index")
    source_type = meta.get("source_type", "text")
    if source is not None and page is not None and chunk_index is not None:
        return (source, page, source_type, chunk_index)
    # Fallback for documents that do not have complete metadata.
    return (doc.page_content[:300],)


def _document_to_dict(doc: Document) -> RetrievedDoc:
    """
    Convert a LangChain Document into a plain dict.

    LangGraph state can be checkpointed, so values should be easy to
    serialize. Converting Document objects to dictionaries also promotes
    commonly used metadata fields to top-level keys for downstream nodes.
    """
    metadata = dict(doc.metadata or {})
    return {
        "content": doc.page_content,
        "metadata": metadata,
        "source": metadata.get("source"),
        "page": metadata.get("page"),
        "company": metadata.get("company"),
        "fy": metadata.get("fy"),        # Fiscal year.
        "chunk_index": metadata.get("chunk_index"),
        "source_type": metadata.get("source_type", "text"),
        "title": metadata.get("title", ""),
    }


def _rerank_documents(docs: list[Document], query: str) -> list[Document]:
    """
    Reorder the fused candidate pool by cross-encoder relevance score.

    EnsembleRetriever above fuses BM25 and vector results by rank position only
    and never reads the text, so a chunk that actually contains the requested
    figure can be ranked below topically similar boilerplate. This pass sends
    the query and every candidate to Jina's reranker, which scores each
    query/document pair directly, and returns the pool in score order.

    A fresh JinaRerank client is built per call on purpose: it holds a
    requests.Session, which is not thread-safe, and five company branches run
    in parallel. Construction costs microseconds against a ~800ms API call.

    Args:
        docs: Fused candidate documents for one company.
        query: The company-specific retrieval query.

    Returns:
        The same documents in relevance order, each carrying a
        "relevance_score" metadata key. Returns docs unchanged when reranking
        is unavailable, which leaves the caller on EnsembleRetriever's RRF order.
    """
    api_key = os.getenv("JINA_API_KEY")
    if not docs or not api_key:
        return docs
    try:
        reranker = JinaRerank(model=RERANK_MODEL, top_n=FINAL_K, jina_api_key=api_key)
        return list(reranker.compress_documents(docs, query))
    except Exception:
        # Reranking is an optional precision layer, not a dependency. On network
        # failure, rate limiting, or a bad response, fall back to the RRF order.
        return docs


def _dedupe_documents(docs: list[Document], company: str) -> list[Document]:
    """
    Deduplicate documents, filter by company, and keep at most FINAL_K.

    Steps:
    1. Skip documents from other companies.
    2. Track seen keys in a set and skip duplicates.
    3. Stop once FINAL_K documents have been kept.

    Larger FINAL_K gives the LLM more context at higher token cost.
    Smaller FINAL_K is cheaper and faster but may miss useful facts.
    """
    seen: set = set()
    result = []
    for doc in docs:
        if not _matches_company(doc, company):
            continue                # Skip documents from other companies.
        key = _doc_key(doc)
        if key in seen:
            continue                # Skip duplicate documents.
        seen.add(key)
        result.append(doc)
        if len(result) >= FINAL_K:
            break                   # Stop once the limit is reached.
    return result


# --- LangGraph node -----------------------------------------------------------

def retrieve_company_node(state: CompanyDocsState) -> dict:
    """
    Run hybrid retrieval for one company and return relevant documents.

    LangGraph node convention:
    - Input: the full state object (TypedDict).
    - Output: a dict containing only fields to update.
      LangGraph merges the returned dict back into state.
    - The function is side-effect free except for file/network reads,
      which makes it easier to test and replay.

    Parallel retrieval context:
    In the parent RetrievalState graph, companies is a list such as
    ["BHP", "RIO"]. LangGraph's Send API expands that list and starts
    one retrieve_company_node per company in parallel. Each branch's
    retrieved_docs are merged into parent state with operator.add.

    Retrieval flow:
    1. Read company and query from state.
    2. Build BM25 and Chroma retrievers, then fuse them with EnsembleRetriever.
    3. Invoke retrieval, falling back to BM25 if vector retrieval fails.
    4. Rerank the fused pool with a cross-encoder, falling back to the RRF
       order if the reranker is unavailable.
    5. Deduplicate, filter, serialize to dictionaries, and return the list.
    """
    company = state.get("company", "").strip().upper()
    query = state.get("query",   "").strip()

    # Return early for empty queries to avoid pointless retrieval calls.
    if not query:
        return {"retrieved_docs": []}

    # Chroma metadata filter: restrict vector search to that company.
    search_kwargs: dict = {"k": CHROMA_K, "filter": {"company": company}}

    # Load retrievers. The first call initializes them; later calls reuse them.
    bm25_retriever = _load_bm25_retriever(company)
    chroma_retriever = _load_vectorstore().as_retriever(search_kwargs=search_kwargs)

    # EnsembleRetriever fuses both paths with Reciprocal Rank Fusion (RRF).
    # Higher-ranked documents receive larger reciprocal-rank scores.
    retriever = EnsembleRetriever(
        retrievers=[bm25_retriever, chroma_retriever],
        weights=[BM25_WEIGHT, CHROMA_WEIGHT],
    )

    try:
        docs = retriever.invoke(query)  # Invoke both retrieval paths and fuse results.
    except Exception:
        # Vector retrieval depends on an external API. Fall back to company BM25
        # when the vector path fails so the system can still return results.
        docs = bm25_retriever.invoke(query)

    # Cross-encoder rerank: decides which candidates survive the FINAL_K cut by
    # reading their content, rather than leaving that cut to RRF rank arithmetic.
    docs = _rerank_documents(docs, query)

    # Deduplicate, filter by company, serialize to dicts, and write to state.
    # company_status uses a merge reducer so parallel company nodes don't overwrite each other.
    docs_found: list[RetrievedDoc] = [_document_to_dict(doc) for doc in _dedupe_documents(docs, company)]
    return {
        "retrieved_docs": docs_found,
        "company_status": {company: bool(docs_found)},
    }
