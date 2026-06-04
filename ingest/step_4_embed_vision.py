"""
step_3b_embed_vision.py — Embed vision tables from output_vision.json into ChromaDB.

Reads ingest/output_vision.json (produced by step_3_ingest_vision.py), converts each
table to searchable text, embeds via Jina, and upserts into ChromaDB.
Already-embedded tables are skipped, so this script is safe to re-run.

Usage:
    uv run python ingest/step_3b_embed_vision.py
"""

import datetime
import json
import os
import time
from pathlib import Path

from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_community.embeddings import JinaEmbeddings
from langchain_core.documents import Document

load_dotenv()

_ROOT       = Path(__file__).parent.parent
OUT_JSON    = Path("ingest/output_vison.json")
CHROMA_DIR  = str(_ROOT / "chroma_db")

EMBED_MODEL       = "jina-embeddings-v3"
EMBED_BATCH_SIZE  = 50
EMBED_BATCH_DELAY = 35   # seconds between batches to stay under 100 K TPM


def _log(msg: str) -> None:
    print(f"[{datetime.datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


# ── Embeddings ────────────────────────────────────────────────────────────────

class RoundRobinEmbeddings:
    """Rotate across multiple Jina API keys to spread rate-limit usage evenly."""
    def __init__(self, instances: list):
        self._instances = instances
        self._i = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        emb = self._instances[self._i % len(self._instances)]
        self._i += 1
        return emb.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._instances[0].embed_query(text)


def init_vectorstore() -> Chroma:
    keys = [k for k in [os.getenv("JINA_API_KEY"), os.getenv("JINA_API_KEY_1")] if k]
    if not keys:
        raise RuntimeError("No Jina API key found. Set JINA_API_KEY in .env")
    _log(f"Initialising ChromaDB with {len(keys)} Jina key(s)...")
    instances  = [JinaEmbeddings(jina_api_key=k, model_name=EMBED_MODEL) for k in keys]
    embeddings = RoundRobinEmbeddings(instances) if len(instances) > 1 else instances[0]
    return Chroma(collection_name="reports", embedding_function=embeddings, persist_directory=CHROMA_DIR)


# ── Table → text ──────────────────────────────────────────────────────────────

def _cell_values(cell) -> list[str]:
    """Recursively extract all non-empty text values from a cell (handles sub_rows)."""
    if cell is None:
        return []
    if not isinstance(cell, dict):
        return [str(cell)] if cell not in ("", "none") else []
    if "value" in cell:
        v = cell["value"]
        return [str(v)] if v not in (None, "", "none") else []
    values = []
    for sub_row in cell.get("sub_rows") or []:
        if not isinstance(sub_row, dict):
            continue
        for c in sub_row.get("cells") or []:
            values.extend(_cell_values(c))
    return values


def _row_to_str(row) -> str:
    if row is None:
        return ""
    if not isinstance(row, dict):
        return str(row) if row not in ("", "none") else ""
    parts = []
    for cell in row.get("cells") or []:
        parts.extend(_cell_values(cell))
    return " | ".join(parts)


def table_to_text(table: dict) -> str:
    """Convert a structured table dict to a flat searchable string."""
    lines = []
    if table.get("title"):
        lines.append(f"Title: {table['title']}")
    lines.append(f"Source: {table['source']} | Page: {table['page']}")
    for row in table.get("headers", []):
        s = _row_to_str(row)
        if s:
            lines.append(f"Headers: {s}")
    for row in table.get("rows", []):
        s = _row_to_str(row)
        if s:
            lines.append(s)
    return "\n".join(lines)


# ── Helpers ───────────────────────────────────────────────────────────────────

def _chunk_id(table: dict) -> str:
    return f"{table['source']}__p{table['page']}__t{table['table_index']}__vision"


def _parse_filename(filename: str) -> tuple[str, str]:
    """Return (company, fy) from a filename like BHP_FY2024.pdf."""
    parts = Path(filename).stem.split("_")
    return parts[0], parts[1]


# ── ChromaDB upsert ───────────────────────────────────────────────────────────

def add_to_chroma(documents: list[Document], ids: list[str], vectorstore: Chroma, delay: int) -> None:
    total_batches = (len(documents) + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE
    for i in range(0, len(documents), EMBED_BATCH_SIZE):
        batch_num  = i // EMBED_BATCH_SIZE + 1
        batch_docs = documents[i : i + EMBED_BATCH_SIZE]
        batch_ids  = ids[i : i + EMBED_BATCH_SIZE]
        _log(f"  Batch {batch_num}/{total_batches}: embedding {len(batch_docs)} chunks...")
        vectorstore.add_documents(documents=batch_docs, ids=batch_ids)
        _log(f"  Batch {batch_num} done.")
        if i + EMBED_BATCH_SIZE < len(documents):
            _log(f"  Sleeping {delay}s (rate limit)...")
            time.sleep(delay)


# ── Entry point ───────────────────────────────────────────────────────────────

def main() -> None:
    if not OUT_JSON.exists():
        print(f"Error: {OUT_JSON} not found. Run step_3_ingest_vision.py first.")
        return

    tables = json.loads(OUT_JSON.read_text(encoding="utf-8"))
    _log(f"Loaded {len(tables)} tables from {OUT_JSON}")

    vectorstore = init_vectorstore()

    # Filter out empty shell tables (no title, no headers, no rows)
    def _is_empty(t: dict) -> bool:
        return (not t.get("title") and not t.get("headers") and not t.get("rows"))

    non_empty = [t for t in tables if not _is_empty(t)]
    skipped   = len(tables) - len(non_empty)
    if skipped:
        _log(f"Filtered out {skipped} empty table shell(s) (no title/headers/rows)")

    # Skip tables already in ChromaDB
    existing = set(vectorstore._collection.get(include=[])["ids"])
    pending  = [t for t in non_empty if _chunk_id(t) not in existing]
    _log(f"Already embedded: {len(non_empty) - len(pending)}  |  To embed: {len(pending)}")

    if not pending:
        _log("Nothing to do.")
        return

    key_count   = sum(1 for k in [os.getenv("JINA_API_KEY"), os.getenv("JINA_API_KEY_1")] if k)
    batch_delay = EMBED_BATCH_DELAY // max(key_count, 1)

    documents: list[Document] = []
    ids: list[str] = []
    for t in pending:
        company, fy = _parse_filename(t["source"])
        documents.append(Document(
            page_content=table_to_text(t),
            metadata={
                "source":      t["source"],
                "page":        t["page"],
                "company":     company,
                "fy":          fy,
                "chunk_index": t["table_index"],
                "title":       t.get("title", ""),
                "source_type": "vision",
            },
        ))
        ids.append(_chunk_id(t))

    add_to_chroma(documents, ids, vectorstore, batch_delay)

    _log(f"Done. {len(documents)} vision chunks written to ChromaDB.")
    _log(f"ChromaDB collection size: {vectorstore._collection.count()}")


if __name__ == "__main__":
    main()
