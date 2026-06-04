from __future__ import annotations

from state import RetrievalState


def _doc_key(doc: dict) -> tuple:
    """Return a deduplication key for a document dict.

    retrieve_parallel.py already deduplicates within each company's results.
    This key is used here to catch any cross-company duplicates (rare but
    possible if the same chunk is indexed under multiple company metadata values).

    Uses (source, page, chunk_index) when all three are present, otherwise
    falls back to the first 300 characters of content.
    """
    source      = doc.get("source")
    page        = doc.get("page")
    chunk_index = doc.get("chunk_index")
    source_type = doc.get("source_type", "text")

    if source is not None and page is not None and chunk_index is not None:
        return (source, page, source_type, chunk_index)
    return (doc.get("content", "")[:300],)


def merge_node(state: RetrievalState) -> dict:
    """Deduplicate documents gathered from all parallel company retrievals.

    retrieve_parallel.py runs once per company via the Send API fan-out.
    Each run appends its results to retrieved_docs via the operator.add reducer,
    so retrieved_docs is the flat concatenation of all companies' results.

    This node:
      1. Removes cross-company duplicates (same chunk appearing in multiple runs).
      2. Preserves the original ordering — each company's docs are already
         ranked by relevance by EnsembleRetriever, so we just keep that order.

    Output goes to merged_docs, which is the input for grade_docs_node.
    """
    docs = state.get("retrieved_docs") or []

    seen: set = set()
    merged: list[dict] = []

    for doc in docs:
        key = _doc_key(doc)
        if key not in seen:
            seen.add(key)
            merged.append(doc)

    return {"merged_docs": merged}
