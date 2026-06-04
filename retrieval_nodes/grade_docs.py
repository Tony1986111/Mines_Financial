from __future__ import annotations

from pydantic import BaseModel

from state import RetrievalState
from utils.llm import llm

_DOC_PREVIEW_CHARS = 500
_SYSTEM_PROMPT = """\
You are grading retrieved document chunks for relevance to a financial query.

A document is RELEVANT if it contains specific financial figures, metrics, or \
facts (revenue, profit, EBITDA, capex, dividends, production volumes, etc.) \
that could help answer the query.

A document is NOT RELEVANT if it covers unrelated topics such as corporate \
governance, board composition, ESG reporting, risk factor boilerplate, or \
auditor's reports — unless the query specifically asks about those topics.

Return only the indices of relevant documents."""


class _GradingResult(BaseModel):
    relevant_indices: list[int]


_grading_llm = llm.with_structured_output(_GradingResult, method="function_calling")


def _build_prompt(query: str, docs: list[dict]) -> str:
    lines = [f"Query: {query}\n\nDocuments:"]
    for i, doc in enumerate(docs):
        company = doc.get("company", "?")
        fy      = doc.get("fy", "?")
        page    = doc.get("page", "?")
        label   = " [table]" if doc.get("source_type") == "vision" else ""
        preview = doc.get("content", "")[:_DOC_PREVIEW_CHARS].replace("\n", " ")
        lines.append(f"[{i}] {company} {fy} p.{page}{label} — {preview}")
    return "\n".join(lines)


def grade_docs_node(state: RetrievalState) -> dict:
    merged_docs    = state.get("merged_docs") or []
    query          = state.get("rewritten_query") or state.get("query", "")
    retry_count    = state.get("retry_count", 0) + 1
    company_status = state.get("company_status") or {}

    if not merged_docs:
        return {"graded_docs": [], "grade": "retry", "retry_count": retry_count}

    try:
        result: _GradingResult = _grading_llm.invoke([
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": _build_prompt(query, merged_docs)},
        ])
        graded_docs = [
            merged_docs[i]
            for i in result.relevant_indices
            if 0 <= i < len(merged_docs)
        ]
    except Exception:
        # LLM failure: pass all docs through rather than breaking the pipeline
        graded_docs = merged_docs

    # Correct company_status: a company is only truly "found" if it has graded docs.
    # This is more accurate than the initial signal set in retrieve_companies_node.
    out: dict = {"graded_docs": graded_docs, "grade": "pass" if graded_docs else "retry", "retry_count": retry_count}
    if company_status:
        companies_with_docs = {d.get("company") for d in graded_docs}
        out["company_status"] = {c: (c in companies_with_docs) for c in company_status}
    return out
