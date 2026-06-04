from __future__ import annotations

from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from state import RetrievalState
from utils.llm import llm

_SYSTEM_PROMPT = """\
You are evaluating a financial analyst's draft answer on two dimensions.

=== TASK 1: QUALITY GRADE ===
Grade "pass" when the answer:
- Contains specific financial figures, metrics, or facts that address the question
- Provides a substantive response, even if it notes that some data is unavailable

Grade "fail" when the answer:
- Is empty or consists entirely of disclaimers such as "I don't have enough information"
- Contains no financial data relevant to the question

Be lenient — only grade "fail" when there is genuinely nothing useful in the answer.

=== TASK 2: GROUNDEDNESS ===
Using ONLY the source documents provided, identify factual claims in the answer that
cannot be verified in those documents (e.g. specific numbers, percentages, conclusions
that do not appear in the source text).

Return each unsupported claim as a short phrase (e.g. "revenue A$53.6B", "dividend yield 4.2%").
Return an empty list if every fact in the answer is supported by the source documents."""


class _GradeResult(BaseModel):
    grade:       Literal["pass", "fail"]
    unsupported: list[str]  # claims not found in source docs; empty = fully grounded


_grading_llm = llm.with_structured_output(_GradeResult, method="function_calling")


def _format_docs(docs: list[dict]) -> str:
    parts = []
    for i, doc in enumerate(docs, 1):
        company = doc.get("company", "Unknown")
        fy      = doc.get("fy", "")
        page    = doc.get("page", "")
        content = (doc.get("content") or "").strip()
        header  = f"[{i}] {company}" + (f" {fy}" if fy else "") + (f", p.{page}" if page != "" else "")
        parts.append(f"{header}\n{content}")
    return "\n\n".join(parts)


def grade_answer_node(state: RetrievalState) -> dict:
    query        = state.get("query", "").strip()
    answer_draft = state.get("answer_draft", "").strip()
    graded_docs  = state.get("graded_docs") or []

    if not answer_draft:
        company_status = state.get("company_status") or {}
        return {
            "grade": "fail",
            "retrieval_result": {
                "documents":      graded_docs,
                "answer_draft":   answer_draft,
                "grounded":       "no",
                "unsupported":    [],
                "grade":          "fail",
                "company_status": company_status,
            },
        }

    docs_text = _format_docs(graded_docs)
    try:
        result: _GradeResult = _grading_llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=(
                f"Question: {query}\n\n"
                f"Source documents:\n{docs_text}\n\n"
                f"Draft answer:\n{answer_draft}"
            )),
        ])
        grade       = result.grade
        unsupported = result.unsupported or []
    except Exception:
        grade       = "pass"
        unsupported = []

    n        = len(unsupported)
    grounded = "yes" if n == 0 else ("partial" if n <= 2 else "no")

    company_status = state.get("company_status") or {}
    return {
        "grade": grade,
        "retrieval_result": {
            "documents":      graded_docs,
            "answer_draft":   answer_draft,
            "grounded":       grounded,
            "unsupported":    unsupported,
            "grade":          grade,
            "company_status": company_status,
        },
    }
