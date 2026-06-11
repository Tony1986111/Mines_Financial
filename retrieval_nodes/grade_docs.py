from __future__ import annotations

from pydantic import BaseModel

from state import RetrievalState, RetrievedDoc
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


def _build_prompt(query: str, docs: list[RetrievedDoc]) -> str:
    lines = [f"Query: {query}\n\nDocuments:"]
    for i, doc in enumerate(docs):
        company = doc.get("company", "?")
        fy = doc.get("fy", "?")
        page = doc.get("page", "?")
        label = " [table]" if doc.get("source_type") == "vision" else ""
        preview = doc.get("content", "")[:_DOC_PREVIEW_CHARS].replace("\n", " ")
        lines.append(f"[{i}] {company} {fy} p.{page}{label} — {preview}")
    return "\n".join(lines)


def grade_docs_node(state: RetrievalState) -> dict:
    all_docs: list[RetrievedDoc] = state.get("retrieved_docs") or []
    query = state.get("rewritten_query") or state.get("query", "")
    retry_count = state.get("retry_count", 0) + 1
    company_status = state.get("company_status") or {}

    if not all_docs:
        return {"graded_docs": [], "grade": "retry", "retry_count": retry_count}

    try:
        result: _GradingResult = _grading_llm.invoke([
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user",   "content": _build_prompt(query, all_docs)},
        ])
        graded_docs: list[RetrievedDoc] = []
        for i in result.relevant_indices:
            if 0 <= i < len(all_docs):
                graded_docs.append(all_docs[i])
    except Exception:
        # LLM failure: pass all docs through rather than breaking the pipeline
        graded_docs = all_docs

    # Correct company_status: a company is only truly "found" if it has graded docs.
    # This is more accurate than the initial signal set in retrieve_company_node.
    out: dict = {"graded_docs": graded_docs, "grade": "pass" if graded_docs else "retry", "retry_count": retry_count, "retrieved_count": len(all_docs)}

    companies_with_docs = set()
    for d in graded_docs:
        companies_with_docs.add(d.get("company"))
        
    updated_company_status = {}
    for c in company_status:
        updated_company_status[c] = bool(c in companies_with_docs)
    out["company_status"] = updated_company_status
    return out
