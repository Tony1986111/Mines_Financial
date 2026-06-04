# Mines Financial — ASX Mining RAG Chatbot

A production-style, multi-agent RAG chatbot that answers questions about the annual reports of five major ASX-listed mining companies: **BHP, Rio Tinto (RIO), Fortescue (FMG), Mineral Resources (MIN), and Northern Star (NST)** across fiscal years FY2023–FY2025.

Built on [LangGraph](https://github.com/langchain-ai/langgraph) with a Next.js frontend, FastAPI backend, PostgreSQL conversation persistence, and a hybrid (dense + BM25) retrieval engine.

---

## Features

- **Multi-agent supervisor graph** — a LangGraph state machine orchestrates independent retrieval, calculation, and news agents in parallel.
- **Hybrid retrieval** — combines Jina dense vector search (ChromaDB) with BM25 keyword search for high-precision document recall.
- **Vision-aware ingest pipeline** — PyMuPDF page-filtering + Gemini vision model extracts structured financial tables from PDF pages that text extraction would miss.
- **Two-tier semantic cache** — past answers are embedded and re-used (L1: direct cache hit at ≥0.95 similarity; L2: context seeding at ≥0.80).
- **Adaptive clarification** — the graph interrupts and asks the user for clarification when the query is ambiguous, then resumes.
- **Dynamic tool selection** — an LLM router decides at runtime whether to call the retrieval agent, the news agent (Tavily web search), or both, and whether arithmetic calculation is required.
- **Calculator agent** — a ReAct agent equipped with financial math tools (growth rate, ratio, average) that operates strictly on retrieved numbers.
- **Guardrails node** — every answer path passes through a validation node before reaching the user; failures route to a graceful fallback.
- **Streaming API** — Server-Sent Events stream graph node progress to the frontend in real time.
- **Persistent conversation threads** — PostgreSQL checkpointer stores full conversation state per thread; threads are resumable across server restarts.
- **Eval framework** — four evaluation suites (routing, retrieval, calculation, boundary) with mock and real modes.

---

## Architecture

```
User Query
    │
    ▼
compress_context ──► memory ──► [cache hit] ──────────────────► answer ──► END
                         │
                         └── [miss] ──► retrieve_decision
                                              │
                              ┌───────────────┼───────────────┐
                           clarify    dynamic_tool_selector  guardrails
                              │               │
                              └──►  ┌─────────┴──────────┐
                                    │                     │
                               retrieval_agent        news_agent
                               (sub-graph)           (Tavily)
                                    │                     │
                                    └─────────┬───────────┘
                                           aggregate
                                              │
                                     [needs_calculation?]
                                        yes │    no │
                                  calculator_agent  │
                                              │     │
                                           guardrails
                                          pass │  fail │
                                           answer   fallback ──► END
                                              │
                                             END
```

**Retrieval sub-graph** (runs per query, fans out per company):

```
query_rewrite ──► [fan-out: retrieve per company in parallel] ──► merge
                                                                      │
                                                                  grade_docs
                                                                 pass │  fail (retry < 2)
                                                              synthesize  ──► query_rewrite
                                                                  │
                                                             grade_answer
                                                             pass │  fail (retry < 2)
                                                               END    ──► query_rewrite
```

---

## Tech Stack

| Layer             | Technology                                               |
| ----------------- | -------------------------------------------------------- |
| Orchestration     | LangGraph 0.6+, LangChain 0.3+                           |
| LLM               | OpenAI API (GPT-4o class), DeepSeek                      |
| Embeddings        | Jina AI (`jina-embeddings-v3`)                         |
| Vector store      | ChromaDB                                                 |
| Keyword search    | BM25 (`rank-bm25`)                                     |
| Web search        | Tavily                                                   |
| PDF processing    | PyMuPDF                                                  |
| Vision extraction | Google Gemini (ingest only)                              |
| Backend API       | FastAPI + Uvicorn                                        |
| Frontend          | Next.js 15, React 19, TypeScript, Tailwind CSS, Chart.js |
| Database          | PostgreSQL 16 (conversation checkpointing)               |
| Tracing           | LangSmith                                                |
| Package manager   | `uv`                                                   |
| Python            | >= 3.12                                                  |

---

## Project Structure

```
mines_financial/
├── app.py                      # FastAPI application and all REST/SSE endpoints
├── graph.py                    # Main supervisor LangGraph definition
├── graph_for_studio.py         # Variant compatible with LangGraph Studio
├── state.py                    # All TypedDict state definitions
├── langgraph.json              # LangGraph deployment config
├── docker-compose.yml          # PostgreSQL service
├── pyproject.toml              # Python dependencies (uv)
│
├── nodes/                      # Supervisor graph nodes
│   ├── compress_context.py     # Trim conversation history when context grows long
│   ├── memory.py               # Semantic cache lookup (L1 / L2 hit detection)
│   ├── retrieve_decision.py    # Classify query: needs retrieval? needs clarification?
│   ├── dynamic_tool_selector.py# LLM router: retrieval / news / calculation flags
│   ├── clarify.py              # Interrupt and ask the user for clarification
│   ├── aggregate.py            # Merge retrieval + news results into one context block
│   ├── guardrails.py           # Validate answer length and quality before delivery
│   ├── fallback.py             # Graceful response when guardrails fail
│   └── answer.py               # Format and emit final answer + chart data + sources
│
├── agents/
│   ├── retrieval_agent.py      # Retrieval sub-graph (query rewrite → retrieve → grade → synthesize)
│   ├── calculator_agent.py     # ReAct financial calculator agent
│   └── news_agent.py           # Tavily web search agent
│
├── retrieval_nodes/            # Nodes used only inside the retrieval sub-graph
│   ├── query_rewrite.py        # Rewrite and decompose query per company
│   ├── retrieve_parallel.py    # Fan-out: parallel BM25 + vector search per company
│   ├── merge.py                # Deduplicate and rank retrieved chunks
│   ├── grade_docs.py           # LLM grades relevance of merged docs
│   ├── synthesize.py           # Draft answer from graded docs
│   └── grade_answer.py         # LLM grades answer quality; triggers retry if needed
│
├── memory/
│   └── semantic.py             # ChromaDB-backed semantic cache (conclusions store)
│
├── tools/
│   └── calculator.py           # Math tools: growth rate, ratio, average, generic calculate
│
├── utils/
│   ├── llm.py                  # Shared LLM client factory
│   ├── chart.py                # Chart data extraction helpers
│   └── citation.py             # Source citation formatting
│
├── db/
│   └── checkpointer.py         # PostgreSQL checkpointer setup helpers
│
├── ingest/                     # One-time PDF to ChromaDB pipeline (see below)
│   ├── step_1_ingest_text.py
│   ├── step_2_PyMuPDF_filter.py
│   ├── step_3_ingest_vision.py
│   ├── step_3_prompts.py
│   ├── step_4_embed_vision.py
│   └── step_5_bm25.py
│
├── evals/                      # Evaluation framework
│   ├── run_eval.py
│   └── evaluators/
│       ├── common.py
│       ├── routing.py
│       ├── retrieval.py
│       ├── calculation.py
│       └── boundary.py
│
├── tests/                      # pytest unit tests
└── frontend/                   # Next.js 15 chat UI
```

---

## Prerequisites

- Python >= 3.12
- [`uv`](https://github.com/astral-sh/uv) package manager (`pip install uv`)
- Node.js >= 18 and npm
- Docker (for PostgreSQL)
- API keys: OpenAI, Jina AI, Tavily; optionally DeepSeek and LangSmith

---

## Quick Start

### 1. Clone and install

```bash
git clone <repo-url>
cd mines_financial

# Python dependencies
uv sync

# Frontend dependencies
cd frontend && npm install && cd ..
```

### 2. Configure environment variables

```bash
cp .env.example .env
```

Edit `.env`:

```env
OPENAI_API_KEY=sk-...
JINA_API_KEY=jina_...
TAVILY_API_KEY=tvly-...
DEEPSEEK_API_KEY=...          # optional, if using DeepSeek as the LLM
LANGSMITH_API_KEY=...         # optional, enables LangSmith tracing
LANGSMITH_TRACING=true
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/mines_financial
```

### 3. Start PostgreSQL

```bash
docker compose up -d
```

### 4. Ingest PDF reports

Before the chatbot can answer questions, run the ingest pipeline to populate ChromaDB. See the [Ingest Pipeline](#ingest-pipeline) section below.

### 5. Start the backend

```bash
uv run uvicorn app:app --reload --port 8000
```

### 6. Start the frontend

```bash
cd frontend
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) in your browser.

---

## Ingest Pipeline

The ingest pipeline converts raw PDF annual reports into a searchable ChromaDB vector store and a BM25 keyword index. Run it once before first use, and re-run steps 1–5 whenever you add new PDFs.

PDF filenames must follow the pattern `{COMPANY}_{FY}.pdf` — for example `BHP_FY2024.pdf`, `RIO_FY2023.pdf`. The scripts parse the company ticker and fiscal year from the filename.

### Step 1 — Text extraction and embedding

Splits PDF pages into overlapping text chunks (1,000 chars / 200 char overlap), embeds them with Jina, and stores them in ChromaDB. Idempotent — already-processed chunks are skipped based on their deterministic chunk ID.

```bash
uv run python ingest/step_1_ingest_text.py
# process a single PDF:
uv run python ingest/step_1_ingest_text.py --pdf BHP_FY2024.pdf
```

### Step 2 — Filter pages for vision processing

Scans every page with PyMuPDF and identifies pages that likely contain tables or data-dense charts. Saves results to `ingest/filtered_pages.json`. Parallelised across 15 worker threads and resumable.

```bash
uv run python ingest/step_2_PyMuPDF_filter.py
# single PDF or a page range:
uv run python ingest/step_2_PyMuPDF_filter.py --pdf RIO_FY2024.pdf --pages 101-200
```

### Step 3 — Vision table extraction

Renders filtered pages to PNG and calls Gemini vision to extract structured tables (title, headers, rows). Saves to `ingest/output_vison.json`. Resumable — a checkpoint file tracks completed pages.

```bash
uv run python ingest/step_3_ingest_vision.py
```

Requires `GOOGLE_API_KEY` in `.env`.

### Step 4 — Embed vision tables

Embeds the extracted vision tables into ChromaDB using distinct chunk IDs (`__vision` suffix). Idempotent.

```bash
uv run python ingest/step_4_embed_vision.py
```

### Step 5 — Build BM25 index

Reads all chunks from ChromaDB (text + vision) and builds a BM25 keyword index saved as `bm25_index.pkl` in the project root. Must be re-run after any ingest that adds or removes chunks.

```bash
uv run python ingest/step_5_bm25.py
```

---

## API Reference

All endpoints are served by `app.py` on port 8000 by default.

| Method     | Path                                 | Description                                                 |
| ---------- | ------------------------------------ | ----------------------------------------------------------- |
| `POST`   | `/api/threads`                     | Create a new conversation thread; returns `{ thread_id }` |
| `GET`    | `/api/threads`                     | List the 30 most recently updated threads                   |
| `GET`    | `/api/threads/{thread_id}/history` | Return the full message history for a thread                |
| `DELETE` | `/api/threads/{thread_id}`         | Delete all checkpoint data for a thread                     |
| `POST`   | `/api/chat`                        | Single-shot chat; returns the complete answer synchronously |
| `POST`   | `/api/chat/stream`                 | SSE streaming endpoint                                      |
| `GET`    | `/api/graph/mermaid`               | Return the supervisor graph as a Mermaid diagram string     |

### Chat request body

```json
{
  "thread_id": "uuid-string",
  "message": "What was BHP's revenue in FY2024?",
  "resume": false
}
```

Set `resume: true` when the user is responding to a clarification question from the chatbot.

### SSE event types (streaming endpoint)

| Event          | Key fields                                              | Description                                                 |
| -------------- | ------------------------------------------------------- | ----------------------------------------------------------- |
| `node_start` | `node`                                                | A graph node has started executing                          |
| `node_done`  | `node`, `state`                                     | A graph node finished; includes a serialised state snapshot |
| `done`       | `answer`, `chart_data`, `sources`, `confidence` | Final answer is ready                                       |
| `interrupt`  | `question`                                            | The graph needs clarification from the user                 |
| `error`      | `detail`                                              | An unhandled exception occurred                             |

---

## Evaluation Framework

The eval runner supports four suites and two execution modes.

**Suites:** `routing`, `retrieval`, `calculation`, `boundary`

**Modes:**

- `mock` — fast and free; validates evaluator logic with synthetic outputs, no LLM or API calls
- `real` — invokes the actual LLM and/or retrieval nodes; consumes API credits

```bash
# Run all mock evals (recommended before every commit)
uv run python evals/run_eval.py --mode mock

# Run one suite in real mode with a cost cap
uv run python evals/run_eval.py --mode real --suite routing --limit 3

# Debug a single case by ID
uv run python evals/run_eval.py --mode real --suite routing --id routing_003_single_report_fact

# Run multiple specific cases
uv run python evals/run_eval.py --mode mock --suite routing \
  --id routing_003_single_report_fact --id routing_005_calculation_required

# Show all CLI options
uv run python evals/run_eval.py --help
```

---

## Running Tests

```bash
uv run pytest tests/
```

---

## LangGraph Studio

A `graph_for_studio.py` entry point and `langgraph.json` config are included for use with [LangGraph Studio](https://github.com/langchain-ai/langgraph-studio).

```bash
# Ensure the CLI dev dependency is installed
uv sync --group dev

# Launch Studio (reads langgraph.json automatically)
langgraph dev
```

---

## License

This project is released for educational and portfolio purposes. No license for commercial use is granted.
