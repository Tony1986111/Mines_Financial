from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage

from state import RetrievalState, RetrievedDoc
from utils.llm_large import llm_large as llm

_SYSTEM_PROMPT = """You are a financial analyst specialising in ASX mining companies.
    Answer the user's question using ONLY the document excerpts provided.

    Rules:
    - Cite sources inline as [N] immediately after each key fact, where N is the document number shown in the excerpts above.
    - CRITICAL: Each citation [N] must only support a claim about the SAME company whose annual report that document belongs to. The company name is shown in every excerpt header (e.g. "[3] FMG FY2024, p.39"). Never use a BHP document to support an FMG or RIO claim, and never use an FMG document to support an NST claim.
    - CRITICAL: If you cannot find a specific company's data in the provided excerpts, you MUST explicitly state "[Company] FY20XX [metric]: data not found in provided documents." Do NOT estimate, infer, or borrow numbers from another company's documents.
    - If excerpts cover multiple companies, compare them side-by-side.
    - Match the language of your answer to the language of the user's question."""


def _format_docs(docs: list[RetrievedDoc]) -> str:
    parts = []
    for i, doc in enumerate(docs, 1):
        company = doc.get("company", "Unknown")
        fy = doc.get("fy", "")
        page = doc.get("page", "")
        source_type = doc.get("source_type", "text")
        content = doc.get("content", "").strip()
        label = " [table]" if source_type == "vision" else ""
        header = f"[{i}] {company}" + (f" {fy}" if fy else "") + (f", p.{page}" if page != "" else "") + label
        parts.append(f"{header}\n{content}")
    return "\n\n".join(parts)


def synthesize_node(state: RetrievalState) -> dict:
    docs: list[RetrievedDoc] = state.get("graded_docs") or []
    query = state.get("query", "").strip()
    semantic_context = state.get("semantic_context", "").strip()

    if not docs or not query:
        return {"answer_draft": ""}

    user_message = f"Question: {query}\n\nDocument excerpts:\n{_format_docs(docs)}"

    # Inject past conclusion as supplementary reference when available.
    # The LLM should still ground its answer in the document excerpts above.
    if semantic_context:
        user_message += f"\n\nPast analysis on a similar question (for reference only):\n{semantic_context}"

    try:
        response = llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=user_message),
        ])
        return {"answer_draft": response.content}
    except Exception:
        return {"answer_draft": ""}
