from __future__ import annotations

import re
from typing import Literal

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel

from state import RetrievalState, RetrievalResult, RetrievedDoc, UnsupportedClaim
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
    cannot be verified in those documents.

    Match facts semantically, not by exact string. A claim IS supported when:
    - The underlying numeric value appears in the documents, regardless of unit/scale/prefix
    formatting (e.g. "29,016" in a US$M column supports "US$29,016 million"; "53.6" in an
    A$B column supports "A$53,600 million"; "0.042" in a ratio column supports "4.2%").
    - Minor rounding is present (e.g. "29,016" supports "approximately US$29 billion").
    - Accounting sign notation differs ("(1,234)" supports "a loss of US$1,234 million").
    - The metric name is a minor variation of the same concept ("Underlying EBITDA" supports
    a claim about "EBITDA"; "NPAT" supports "net profit after tax").
    - The time period is expressed differently ("year ended 30 June 2024" = "FY2024").

    Only flag a claim as unsupported if its underlying value or fact is genuinely absent
    from ALL retrieved documents — not merely expressed or formatted differently.

    For each unsupported claim, also classify its likely basis:
    - "calculation"       — the value appears to be arithmetically derived from numbers present in the documents
    - "interpolation"     — the value appears to be estimated or extrapolated from a trend visible in the documents
    - "general_knowledge" — the claim has no traceable connection to any retrieved document

    For each unsupported claim, write a short identifying label (≤8 words) — do NOT reproduce
    the full sentence or embed the specific value. The label names the metric and context only.
    Good: "RIO FY2025 revenue", "BHP FY2024 EBITDA", "FMG dividend yield FY2023"
    Bad:  "Rio Tinto FY2025 consolidated sales revenue was US$57.6 billion"

    Return an empty list if every fact in the answer is supported by the source documents."""


class _UnsupportedClaim(BaseModel):
    claim: str  # short phrase describing the unverifiable fact
    basis: Literal["calculation", "interpolation", "general_knowledge"]


class _GradeResult(BaseModel):
    grade: Literal["pass", "fail"]
    unsupported: list[_UnsupportedClaim]


_grading_llm = llm.with_structured_output(_GradeResult, method="function_calling")


# Matches financial unit tokens that appear in table header rows,
# e.g. "US$M", "A$M", "US$B", "A$'000", "%".
_TABLE_UNIT_RE = re.compile(
    r'\b(US\$[MB]|A\$[MB]|NZ\$[MB]|\$[MB]|[A-Z]{2,3}\$[MB]|US\$\'000|A\$\'000|[A-Z]{2,3}\$\'000|%)\b'
)
_UNIT_EXPAND = {
    "US$M": "US$ millions", "A$M": "A$ millions", "NZ$M": "NZ$ millions",
    "$M": "$ millions", "US$B": "US$ billions", "A$B": "A$ billions",
    "$B": "$ billions", "US$'000": "US$ thousands", "A$'000": "A$ thousands", "%": "percent",
}


def _table_unit_note(content: str) -> str | None:
    """Return an explicit unit annotation for table docs by scanning Headers lines.

    Financial tables store the unit (e.g. 'US$M') in a header cell, disconnected
    from the raw numbers in data rows. Without this annotation the grading LLM
    cannot reliably match '29,016' in a US$M table to 'US$29,016 million'.
    """
    for line in content.split("\n"):
        if not line.startswith("Headers:"):
            continue
        m = _TABLE_UNIT_RE.search(line)
        if m:
            token = m.group(0)
            expanded = _UNIT_EXPAND.get(token, token)
            return f"[Table unit: all bare numeric values in this table are in {expanded} ({token})]"
    return None


def _format_docs(docs: list[RetrievedDoc]) -> str:
    parts = []
    for i, doc in enumerate(docs, 1):
        company = doc.get("company", "Unknown")
        fy = doc.get("fy", "")
        page = doc.get("page", "")
        content = (doc.get("content") or "").strip()
        header = f"[{i}] {company}" + (f" {fy}" if fy else "") + (f", p.{page}" if page != "" else "")

        if doc.get("source_type") == "vision":
            unit_note = _table_unit_note(content)
            if unit_note:
                parts.append(f"{header}\n{unit_note}\n{content}")
                continue

        parts.append(f"{header}\n{content}")
    return "\n\n".join(parts)


def grade_answer_node(state: RetrievalState) -> dict:
    query = state.get("query", "").strip()
    answer_draft = state.get("answer_draft", "").strip()
    graded_docs: list[RetrievedDoc] = state.get("graded_docs") or []
    company_status = state.get("company_status") or {}

    if not answer_draft:
        # no answer = no claims to verify; grade="fail" is the real signal
        grade = "fail"
        grounded = "yes"
        unsupported: list[UnsupportedClaim] = []
    else:
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
            grade = result.grade
            unsupported: list[UnsupportedClaim] = [{"claim": u.claim, "basis": u.basis} for u in (result.unsupported or [])]
        except Exception:
            grade = "pass"
            unsupported = []

        n = len(unsupported)
        grounded = "yes" if n == 0 else ("partial" if n <= 3 else "no")

    retrieval_result: RetrievalResult = {
        "documents": graded_docs,
        "answer_draft": answer_draft,
        "grounded": grounded,
        "unsupported": unsupported,
        "grade": grade,
        "company_status": company_status,
        "retrieved_count": state.get("retrieved_count", 0),
        "company_queries": state.get("company_queries") or [],
        "rewritten_query": state.get("rewritten_query") or "",
    }

    # When grounded=="no", extract claim labels for use as targeted retry queries,
    # and reset company_status for companies with unverified claims so the retry
    # path re-retrieves specifically for them.
    unsupported_hints = []
    retry_company_status = {}
    if n >= 2:
        for u in unsupported:
            unsupported_hints.append(u["claim"])
        for hint in unsupported_hints:
            for c in company_status:
                if c in hint:
                    retry_company_status[c] = False

    return {
        "grade": grade,
        "grounded": grounded,
        "unsupported_hints": unsupported_hints,
        "company_status": retry_company_status,
        "retrieval_result": retrieval_result,
    }
