"""
step_1_ingest_text.py — Extract plain text from PDF annual reports and store as chunks in ChromaDB.

Run step_4_bm25.py afterwards to rebuild the BM25 index.

Usage:
    uv run python ingest/step_1_ingest_text.py                        # all PDFs
    uv run python ingest/step_1_ingest_text.py --pdf BHP_FY2024.pdf   # single PDF
"""

import argparse
import datetime
import os
import sys
import time
from pathlib import Path

import fitz
from dotenv import load_dotenv
from langchain_chroma import Chroma
from langchain_community.embeddings import JinaEmbeddings
from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter

load_dotenv()

_ROOT = Path(__file__).parent.parent
CHROMA_DIR = str(_ROOT / "chroma_db")

CHUNK_SIZE = 1000
CHUNK_OVERLAP = 200
EMBED_MODEL = "jina-embeddings-v3"
EMBED_BATCH_SIZE = 50    # chunks per Jina API call (~37 K tokens)
EMBED_BATCH_DELAY = 35    # seconds between batches to stay under 100 K TPM


def _get_reports_dir(cli_path: str | None) -> Path:
    if cli_path:
        d = Path(cli_path)
    else:
        raw = input("PDF reports directory (e.g. /Users/yourname/Downloads/annual_reports): ").strip()
        d = Path(raw)
    if not d.is_dir():
        print(f"Error: '{d}' is not a directory.", file=sys.stderr)
        sys.exit(1)
    return d


def _log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)


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
    instances = [JinaEmbeddings(jina_api_key=k, model_name=EMBED_MODEL) for k in keys]
    embeddings = RoundRobinEmbeddings(instances) if len(instances) > 1 else instances[0]
    store = Chroma(
        collection_name="reports",
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR,
    )
    _log("ChromaDB ready.")
    return store


# ── PDF → text chunks ─────────────────────────────────────────────────────────

def _parse_filename(filename: str) -> tuple[str, str]:
    """Return (company, fy) from a filename like BHP_FY2024.pdf."""
    stem = Path(filename).stem
    parts = stem.split("_")
    return parts[0], parts[1]


def extract_pages(pdf_path: Path) -> list[dict]:
    """Read every page of a PDF and return non-empty text pages as dicts."""
    filename = pdf_path.name
    company, fy = _parse_filename(filename)
    doc = fitz.open(str(pdf_path))
    pages: list[dict] = []
    for page_idx in range(len(doc)):
        text = doc[page_idx].get_text()
        if len(text.strip()) < 100:
            continue
        pages.append({
            "text": text,
            "source": filename,
            "page": page_idx + 1,
            "company": company,
            "fy": fy,
        })
    doc.close()
    return pages


def pages_to_documents(pages: list[dict]) -> list[Document]:
    """Split page texts into overlapping chunks and wrap as LangChain Documents."""
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""],
    )
    documents: list[Document] = []
    for page in pages:
        for i, chunk_text in enumerate(splitter.split_text(page["text"])):
            documents.append(Document(
                page_content=chunk_text,
                metadata={
                    "source": page["source"],
                    "page": page["page"],
                    "company": page["company"],
                    "fy": page["fy"],
                    "chunk_index": i,
                    "source_type": "text",
                },
            ))
    return documents


# ── ChromaDB ──────────────────────────────────────────────────────────────────

def add_to_chroma(
    documents: list[Document],
    vectorstore: Chroma,
    delay: int = EMBED_BATCH_DELAY,
) -> None:
    """Embed documents and upsert into ChromaDB in rate-limited batches."""
    ids = [
        f"{d.metadata['source']}__p{d.metadata['page']}__c{d.metadata['chunk_index']}"
        for d in documents
    ]
    total_batches = (len(documents) + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE
    for i in range(0, len(documents), EMBED_BATCH_SIZE):
        batch_num = i // EMBED_BATCH_SIZE + 1
        batch_docs = documents[i : i + EMBED_BATCH_SIZE]
        batch_ids = ids[i : i + EMBED_BATCH_SIZE]
        _log(f"  Batch {batch_num}/{total_batches}: sending {len(batch_docs)} chunks to Jina...")
        vectorstore.add_documents(documents=batch_docs, ids=batch_ids)
        _log(f"  Batch {batch_num} done.")
        if i + EMBED_BATCH_SIZE < len(documents):
            _log(f"  Sleeping {delay}s (rate limit)...")
            time.sleep(delay)


# ── Entry point ───────────────────────────────────────────────────────────────

def process_pdf(pdf_path: Path, vectorstore: Chroma, batch_delay: int) -> int:
    """Extract, chunk, and embed one PDF. Returns chunk count."""
    _log(f"── {pdf_path.name} ──")
    pages = extract_pages(pdf_path)
    docs = pages_to_documents(pages)
    _log(f"  {len(pages)} pages → {len(docs)} chunks. Embedding...")
    add_to_chroma(docs, vectorstore, delay=batch_delay)
    _log(f"  Done: {len(docs)} chunks stored.")
    return len(docs)


def main() -> None:
    parser = argparse.ArgumentParser(description="Ingest PDF text into ChromaDB.")
    parser.add_argument("--reports-dir", help="Path to folder containing PDF files (e.g. /Users/yourname/Downloads/annual_reports)")
    parser.add_argument("--pdf", help="Process a single PDF (name only, e.g. BHP_FY2024.pdf)")
    args = parser.parse_args()

    reports_dir = _get_reports_dir(args.reports_dir)
    key_count = sum(1 for k in [os.getenv("JINA_API_KEY"), os.getenv("JINA_API_KEY_1")] if k)
    batch_delay = EMBED_BATCH_DELAY // max(key_count, 1)
    vectorstore = init_vectorstore()

    if args.pdf:
        pdf_path = reports_dir / args.pdf
        if not pdf_path.exists():
            print(f"Error: {pdf_path} not found.")
            return
        n = process_pdf(pdf_path, vectorstore, batch_delay)
        print(f"\nDone. {n} chunks stored for {args.pdf}.")
        print("Run step_4_bm25.py to rebuild the BM25 index.")
        return

    pdf_files = sorted(reports_dir.glob("*.pdf"))
    if not pdf_files:
        print(f"Error: no PDF files found in {reports_dir}")
        return

    _log(f"Found {len(pdf_files)} PDF files.")
    total = sum(process_pdf(p, vectorstore, batch_delay) for p in pdf_files)

    print(f"\nDone.")
    print(f"  PDFs processed : {len(pdf_files)}")
    print(f"  Total chunks   : {total}")
    print(f"  ChromaDB       : {CHROMA_DIR}")
    print("Run step_4_bm25.py to rebuild the BM25 index.")


if __name__ == "__main__":
    main()
