"""
step_5_bm25.py — Build per-company BM25 indices from all chunks stored in ChromaDB.

Produces one pkl file per company under bm25_index/:
    bm25_index/BHP.pkl, bm25_index/RIO.pkl, bm25_index/FMG.pkl,
    bm25_index/MIN.pkl, bm25_index/NST.pkl

Run this after all chunks (text and/or vision) have been embedded into ChromaDB.

Usage:
    uv run python ingest/step_5_bm25.py
"""

import datetime
import os
import pickle
from collections import defaultdict
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_community.embeddings import JinaEmbeddings
from langchain_community.retrievers import BM25Retriever
from langchain_core.documents import Document

load_dotenv()

_ROOT       = Path(__file__).parent.parent
CHROMA_DIR  = str(_ROOT / "chroma_db")
BM25_DIR    = _ROOT / "bm25_index"
EMBED_MODEL = "jina-embeddings-v3"
_BATCH_SIZE = 5000


def _log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


def load_all_documents() -> list[Document]:
    """Load every chunk from ChromaDB as LangChain Documents, paginated to avoid SQLite variable limit."""
    key = os.getenv("JINA_API_KEY") or os.getenv("JINA_API_KEY_1")
    if not key:
        raise RuntimeError("No Jina API key found. Set JINA_API_KEY in .env")
    embeddings = JinaEmbeddings(jina_api_key=key, model_name=EMBED_MODEL)
    store = Chroma(
        collection_name="reports",
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR,
    )
    _log(f"Connected to ChromaDB at {CHROMA_DIR}")
    total = store._collection.count()
    _log(f"Total chunks in collection: {total}")

    docs: list[Document] = []
    offset = 0
    while offset < total:
        result = store._collection.get(
            include=["documents", "metadatas"],
            limit=_BATCH_SIZE,
            offset=offset,
        )
        for content, meta in zip(result["documents"], result["metadatas"]):
            docs.append(Document(page_content=content, metadata=meta))
        offset += _BATCH_SIZE
        _log(f"  Loaded {min(offset, total)}/{total} chunks...")

    _log(f"Loaded {len(docs)} chunks total.")
    return docs


def build_per_company_bm25(documents: list[Document]) -> None:
    """Group documents by company and build one BM25 index per company."""
    grouped: dict[str, list[Document]] = defaultdict(list)
    for doc in documents:
        company = str((doc.metadata or {}).get("company", "")).upper().strip()
        if company:
            grouped[company].append(doc)

    _log(f"Companies found: {sorted(grouped.keys())}")

    for company, docs in sorted(grouped.items()):
        _log(f"Building BM25 for {company} ({len(docs)} chunks)...")
        retriever = BM25Retriever.from_documents(docs)
        retriever.k = 8
        out_path = BM25_DIR / f"{company}.pkl"
        with open(out_path, "wb") as f:
            pickle.dump(retriever, f)
        _log(f"  Saved → {out_path}")


def main() -> None:
    if not BM25_DIR.exists():
        raise FileNotFoundError(
            f"bm25_index directory not found at {BM25_DIR}. Create it first."
        )
    docs = load_all_documents()
    if not docs:
        print("No chunks found in ChromaDB. Run ingest steps first.")
        return
    build_per_company_bm25(docs)
    print(f"\nDone. Per-company BM25 indices saved to {BM25_DIR}/")


if __name__ == "__main__":
    main()
