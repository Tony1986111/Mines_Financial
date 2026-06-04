# Ingest Pipeline — Tutorial & Design Notes

This document explains how to run the full ingest pipeline that converts raw PDF annual reports into a searchable ChromaDB vector store plus a BM25 keyword index.

---

## Required Files

| File | Role |
|------|------|
| `step_1_ingest_text.py` | Extract plain text from PDFs → embed → store in ChromaDB |
| `step_2_PyMuPDF_filter.py` | Scan PDFs and identify pages worth vision-processing |
| `step_3_ingest_vision.py` | Call Gemini vision model on filtered pages → extract structured tables |
| `step_3_prompts.py` | Prompt templates and few-shot examples for the vision model (imported by step 3) |
| `step_4_embed_vision.py` | Embed extracted vision tables → store in ChromaDB |
| `step_5_bm25.py` | Build BM25 keyword index from all chunks in ChromaDB |
| `fewshot.png` / `fewshot2.png` / `fewshot3.png` / `fewshot4.png` | Few-shot reference images used in the vision prompt |

---

## Prerequisites

### 1. Python environment

```bash
uv sync          # or: pip install -r requirements.txt
```

### 2. Environment variables

Create a `.env` file in the project root:

```
JINA_API_KEY=jina_...          # required — used for embedding (steps 1, 3b, 4)
JINA_API_KEY_1=jina_...        # optional — second key for round-robin rate spreading
GOOGLE_API_KEY=AIza...         # required for step 3 (Gemini vision model)
```

### 3. PDF files

Place all PDF annual reports in a single folder on your machine, e.g.:

```
/Users/yourname/Downloads/annual_reports/
├── BHP_FY2023.pdf
├── BHP_FY2024.pdf
└── ...
```

Each filename must follow the pattern `{COMPANY}_{FY}.pdf` (e.g. `RIO_FY2024.pdf`) so the scripts can parse company name and fiscal year from it.

---

## Step-by-Step Instructions

### Step 1 — Text extraction and embedding

```bash
uv run python ingest/step_1_ingest_text.py
```

You will be prompted to enter the path to your PDF folder:

```
PDF reports directory (e.g. /Users/yourname/Downloads/annual_reports):
```

This script processes every PDF, splits pages into overlapping text chunks, embeds them using Jina, and writes them into ChromaDB. It is safe to re-run — already-embedded chunks are skipped based on their ID.

To process a single PDF:

```bash
uv run python ingest/step_1_ingest_text.py --pdf BHP_FY2024.pdf
```

---

### Step 2 — Filter pages for vision processing

```bash
uv run python ingest/step_2_PyMuPDF_filter.py
```

You will be prompted for the PDF folder path again. This script scans every page of every PDF and identifies pages that likely contain tables or data-dense charts. The result is saved to `ingest/filtered_pages.json`.

To scan a single PDF or a page range:

```bash
uv run python ingest/step_2_PyMuPDF_filter.py --pdf RIO_FY2024.pdf
uv run python ingest/step_2_PyMuPDF_filter.py --pdf RIO_FY2024.pdf --pages 101-200
```

---

### Step 3 — Vision table extraction

```bash
uv run python ingest/step_3_ingest_vision.py
```

You will be prompted for the PDF folder path. This script reads `filtered_pages.json`, renders each listed page as a PNG, and calls the Gemini vision model to extract structured tables (title, headers, rows). Results are saved to `ingest/output_vison.json`.

The script is resumable — a checkpoint file (`ingest/step_3_checkpoint.jsonl`) tracks which pages have been successfully processed. If interrupted, simply re-run and it will skip already-completed pages.

---

### Step 4 — Embed vision tables

```bash
uv run python ingest/step_4_embed_vision.py
```

This script reads `ingest/output_vison.json` and embeds each table into ChromaDB. Like step 1, it is safe to re-run; already-embedded chunks are skipped.

---

### Step 5 — Build BM25 index

```bash
uv run python ingest/step_5_bm25.py
```

This reads all chunks (text + vision) from ChromaDB and builds a BM25 keyword index, saved as `bm25_index.pkl` in the project root. Run this after both step 1 and step 4 are complete. Re-run it any time the ChromaDB collection changes.

---

## Design Notes

### `step_1_ingest_text.py`

**Chunking strategy.** Each PDF page's text is split with `RecursiveCharacterTextSplitter` using a chunk size of 1,000 characters and 200-character overlap. The overlap ensures that sentences spanning chunk boundaries remain recoverable at query time.

**Rate-limit management.** Jina's free tier caps throughput at 100K tokens per minute. Chunks are sent in batches of 50 with a 35-second pause between batches. If two API keys are provided, the delay is halved via round-robin key rotation.

**Idempotency.** Each chunk receives a deterministic ID (`{source}__p{page}__c{chunk_index}`). ChromaDB's `add_documents` upserts, so re-running the script does not create duplicates.

---

### `step_2_PyMuPDF_filter.py`

**Why filter at all.** Calling a vision model on every page of 15 PDFs (~4,000+ pages total) would be extremely slow and costly. This script pre-screens pages so the vision step only touches pages that plausibly contain data tables or charts.

**Detection logic.** Three independent signals are checked (any one is sufficient to include a page):
- `TABLE`: PyMuPDF's `find_tables()` detects at least one table structure.
- `IMAGE`: the page contains a raster image and has sufficient numeric density.
- `DRAWING`: the page has many vector paths (typical of bar/line charts) and numeric density.

**Numeric density** is defined as `digit_characters / non-whitespace_characters`. A threshold of 5% is used — pages with very little numeric content are unlikely to contain financial data worth extracting.

**Two-column layout edge case.** Full-page tables in two-column annual report layouts are sometimes detected as a single bounding box covering >80% of the page area, which distorts local density calculations. For these cases the script falls back to absolute character counts (`text_chars ≥ 100` and `digit_count ≥ 20`) instead of the density ratio.

**Parallelism and checkpointing.** 15 worker threads scan PDFs concurrently (page rendering is CPU-bound and benefits from parallelism). A checkpoint is written every 50 pages under a lock, so the script can resume from an intermediate state if interrupted on large corpora.

---

### `step_3_ingest_vision.py` + `step_3_prompts.py`

**Two-pass processing per PDF.** Pass 1 renders pages to PNG bytes sequentially — PyMuPDF (`fitz`) is not thread-safe for rendering. Pass 2 submits all rendered images to the vision API concurrently (32 workers) to maximise throughput.

**Structured output format.** Rather than asking the model to return free text, the prompt specifies a strict JSON schema: each table has a `title`, a `headers` array (rows of header cells), and a `rows` array (data rows). Downstream embedding converts this structure back to a flat text representation for search, while preserving the original structure for display.

**Few-shot examples.** Four reference images (`fewshot*.png`) with corresponding JSON answers are included in every prompt. This teaches the model the expected output format and reduces the likelihood of the model inventing a different structure. Critically, **all values in the few-shot answers are generic placeholders** (`[Row group A]`, `[Result N]`, etc.) rather than real financial data — this prevents the model from copying few-shot answer values verbatim into unrelated pages, a form of hallucination observed during development.

Each image targets a specific structural challenge:

- **`fewshot.png`** — An LTI performance measures table with deeply nested structure: cells subdivided into `sub_rows`, KPI groups spanning multiple rows via `row_span`, "Other conditions" entries using `col_span` across the full width, and a Total row. This is the primary example that teaches the core nested-cell schema.

- **`fewshot2.png`** — A simpler LTI table whose main purpose is to demonstrate that the `=` sign is **never** a cell separator. Metric bullets appear as `"• Threshold rTSR = 50th percentile = 50% vest"` — the entire string belongs in one cell value. Without this example, models consistently split on `=` and misalign columns.

- **`fewshot3.png`** — A stacked bar chart showing executive remuneration mix across three fiscal years for multiple individuals. Two lessons: (1) a color legend at the bottom of the chart (e.g. FAR / STI / LTI / CRR) must be **folded into column headers**, not extracted as a separate table; (2) when a color segment is absent for a given year, the corresponding cell must be output as `""` (empty string), not omitted — column count must stay consistent across all rows.

- **`fewshot4.png`** — A plain data table where the leftmost column has no visible header text. This teaches that blank header cells must still be included in the headers row as `{"value": "none"}` — they must never be skipped. Without this rule, models omit the empty cell and shift all subsequent header values left, misaligning them with the data columns.

**JSON repair.** Model output occasionally includes markdown code fences or multiple concatenated JSON arrays. The `_extract_json` function strips fences and falls back to a bracket-depth parser to extract any valid JSON arrays from the response.

**Retry and rate-limit handling.** Each page is attempted up to 3 times. On a `RateLimitError`, the script waits 65 seconds before retrying. Pages that fail all retries are recorded in the checkpoint as `failed` and will be retried automatically on the next run.

**Concurrent write safety.** Multiple workers may complete simultaneously and all call `_write_tables` to append to the same JSON file. This is serialised under a `threading.Lock`, and a `try/except` guards against reading an empty or partially-written file between workers.

---

### `step_4_embed_vision.py`

**Table-to-text serialisation.** ChromaDB stores flat strings. Each structured table is converted to a line-delimited text representation: title, source/page, header rows, then data rows joined by ` | `. This preserves enough structure for keyword and semantic search while fitting into a single embedding call.

**Chunk ID scheme.** Vision chunk IDs use the format `{source}__p{page}__t{table_index}__vision`, distinct from text chunk IDs. This allows the application layer to filter or weight results by source type.

**Idempotency.** Already-embedded chunk IDs are fetched from ChromaDB at startup. Only new chunks are sent to Jina, so the script is safe to re-run after a partial failure.

---

### `step_5_bm25.py`

**Why BM25 alongside vector search.** Dense vector search excels at semantic similarity but can miss exact keyword matches (company names, specific metric names, fiscal year codes like "FY2024"). BM25 is a classical term-frequency retrieval method that handles exact matches well. The application uses hybrid retrieval: BM25 for keyword precision, ChromaDB for semantic coverage.

**Paginated reads.** ChromaDB's SQLite backend has a hard limit on the number of SQL variables per query (~32,766). Fetching all ~33,000 chunks in a single call raises `too many SQL variables`. The script reads in batches of 5,000 chunks using `limit` + `offset` to stay within this limit.

**Rebuild policy.** BM25 is an in-memory index serialised to `bm25_index.pkl`. It must be rebuilt from scratch whenever the ChromaDB collection changes — there is no incremental update. Re-run step 4 after any ingest that adds or removes chunks.

---

### A note on vision chunk quality

Accurately extracting tables and data figures from PDF annual reports is a non-trivial problem. Different files use different visual conventions — some tables rely on explicit grid lines for structure, others use background colour fills or whitespace alone, and charts may embed their legends in arbitrary positions. A robust production pipeline would tailor its detection and cropping strategy to each file's characteristics: using line-based detection where grids are present, falling back to text-anchor or colour-fill detection where they are not, and validating each crop before sending it to the vision model.

This project is intended as a demo, so the current approach is intentionally coarse: all candidate pages are passed to the vision model as full-page screenshots, and the extracted output is embedded uniformly without per-file tuning. This trades extraction precision for pipeline simplicity. If higher-quality vision chunks are required — fewer missed tables, tighter bounding boxes, less irrelevant context — the pipeline would benefit from deeper per-file optimisation at both the detection and the prompting stages.
