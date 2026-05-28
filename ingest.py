"""
ingest.py — 把 data/reports/ 里的所有 PDF 向量化并建立索引
运行方式：python ingest.py
只需要运行一次，之后的检索直接读 chroma_db/ 和 bm25_index.pkl
"""

import os
import pickle
import time
import datetime
import fitz                          # pymupdf
from pathlib import Path
from dotenv import load_dotenv
from tqdm import tqdm                # 进度条


def log(msg: str) -> None:
    ts = datetime.datetime.now().strftime("%H:%M:%S")
    print(f"[{ts}] {msg}", flush=True)

from langchain_core.documents import Document
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_community.embeddings import JinaEmbeddings
from langchain_chroma import Chroma
from langchain_community.retrievers import BM25Retriever

load_dotenv()


class RoundRobinEmbeddings:
    """轮流使用多个 Jina key，均摊速率限制。"""
    def __init__(self, instances: list):
        self._instances = instances
        self._i = 0

    def embed_documents(self, texts: list[str]) -> list[list[float]]:
        emb = self._instances[self._i % len(self._instances)]
        self._i += 1
        return emb.embed_documents(texts)

    def embed_query(self, text: str) -> list[float]:
        return self._instances[0].embed_query(text)

# ── 配置 ──────────────────────────────────────────────────────────────
REPORTS_DIR   = "data/reports"
CHROMA_DIR    = "chroma_db"
BM25_PATH     = "bm25_index.pkl"
CHUNK_SIZE        = 1000
CHUNK_OVERLAP     = 200
EMBED_MODEL       = "jina-embeddings-v3"
EMBED_BATCH_SIZE  = 50    # chunks per API call (~37K tokens)
EMBED_BATCH_DELAY = 35    # seconds between batches → ~75K TPM, under 100K limit


# ── Step 1: 解析 PDF ──────────────────────────────────────────────────
def parse_filename(filename: str) -> tuple[str, str]:
    stem = Path(filename).stem
    parts = stem.split("_")
    return parts[0], parts[1]   # company, fy


def extract_pages(pdf_path: str) -> list[dict]:
    filename = os.path.basename(pdf_path)
    company, fy = parse_filename(filename)

    doc = fitz.open(pdf_path)
    pages = []

    for page_num in range(len(doc)):
        text = doc[page_num].get_text()
        if len(text.strip()) < 100:
            continue
        pages.append({
            "text":    text,
            "source":  filename,
            "page":    page_num + 1,
            "company": company,
            "fy":      fy,
        })

    doc.close()
    return pages


# ── Step 2: 切块 ──────────────────────────────────────────────────────
def pages_to_documents(pages: list[dict]) -> list[Document]:
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=CHUNK_SIZE,
        chunk_overlap=CHUNK_OVERLAP,
        separators=["\n\n", "\n", " ", ""],
    )
    documents = []
    for page in pages:
        chunks = splitter.split_text(page["text"])
        for i, chunk_text in enumerate(chunks):
            documents.append(Document(
                page_content=chunk_text,
                metadata={
                    "source":      page["source"],
                    "page":        page["page"],
                    "company":     page["company"],
                    "fy":          page["fy"],
                    "chunk_index": i,
                }
            ))
    return documents


# ── Step 3: 存入 ChromaDB ─────────────────────────────────────────────
def init_vectorstore() -> Chroma:
    keys = [k for k in [os.getenv("JINA_API_KEY"), os.getenv("JINA_API_KEY_1")] if k]
    log(f"使用 {len(keys)} 个 Jina API key，初始化 ChromaDB...")
    instances = [JinaEmbeddings(jina_api_key=k, model_name=EMBED_MODEL) for k in keys]
    embeddings = RoundRobinEmbeddings(instances) if len(instances) > 1 else instances[0]
    store = Chroma(
        collection_name="reports",
        embedding_function=embeddings,
        persist_directory=CHROMA_DIR,
    )
    log("ChromaDB 初始化完成")
    return store


def add_to_chroma(documents: list[Document], vectorstore: Chroma, delay: int = EMBED_BATCH_DELAY) -> None:
    ids = [
        f"{doc.metadata['source']}__p{doc.metadata['page']}__c{doc.metadata['chunk_index']}"
        for doc in documents
    ]
    total_batches = (len(documents) + EMBED_BATCH_SIZE - 1) // EMBED_BATCH_SIZE
    for i in range(0, len(documents), EMBED_BATCH_SIZE):
        batch_num  = i // EMBED_BATCH_SIZE + 1
        batch_docs = documents[i : i + EMBED_BATCH_SIZE]
        batch_ids  = ids[i : i + EMBED_BATCH_SIZE]
        log(f"  → 批次 {batch_num}/{total_batches}，发送 {len(batch_docs)} 个 chunk 到 Jina...")
        vectorstore.add_documents(documents=batch_docs, ids=batch_ids)
        log(f"  ✓ 批次 {batch_num} 完成")
        if i + EMBED_BATCH_SIZE < len(documents):
            log(f"  ⏳ 等待 {delay}s（限速）...")
            time.sleep(delay)


# ── Step 4: 建立 BM25 索引 ────────────────────────────────────────────
def build_bm25(documents: list[Document]) -> None:
    retriever = BM25Retriever.from_documents(documents)
    retriever.k = 5
    with open(BM25_PATH, "wb") as f:
        pickle.dump(retriever, f)
    print(f"  BM25 索引已保存 → {BM25_PATH}")


# ── 主流程 ────────────────────────────────────────────────────────────
def main():
    pdf_files = sorted(Path(REPORTS_DIR).glob("*.pdf"))
    if not pdf_files:
        print(f"错误：{REPORTS_DIR} 里没有找到 PDF 文件")
        return

    print(f"找到 {len(pdf_files)} 个 PDF 文件，开始处理...\n")

    key_count   = sum(1 for k in [os.getenv("JINA_API_KEY"), os.getenv("JINA_API_KEY_1")] if k)
    batch_delay = EMBED_BATCH_DELAY // key_count   # 2 keys → 17s，速度翻倍
    vectorstore = init_vectorstore()
    all_documents = []

    for pdf_path in tqdm(pdf_files, desc="处理 PDF"):
        log(f"\n── {pdf_path.name} ──")
        log("解析 PDF 页面...")
        pages = extract_pages(str(pdf_path))
        log(f"提取 {len(pages)} 页，切块中...")
        documents = pages_to_documents(pages)
        log(f"生成 {len(documents)} 个 chunk，开始 embedding...")
        add_to_chroma(documents, vectorstore, delay=batch_delay)

        all_documents.extend(documents)

    # 所有 PDF 处理完之后，用全量 documents 建立 BM25 索引
    print("\n建立 BM25 索引...")
    build_bm25(all_documents)

    # 汇总
    print(f"\n✅ 完成！")
    print(f"   处理 PDF：{len(pdf_files)} 个")
    print(f"   总 chunk 数：{len(all_documents)}")
    print(f"   ChromaDB 位置：{CHROMA_DIR}/")
    print(f"   BM25 索引位置：{BM25_PATH}")


if __name__ == "__main__":
    main()
