from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from state import MainState, RetrievalResult
from utils.llm import llm

_CALC_PROMPT = """Decide whether answering the query requires explicit arithmetic.
    needs_calculation: true only if the context contains raw numbers that must be combined
    to produce the answer — e.g. computing a growth rate, ratio, year-over-year change, or
    average across multiple reported figures. Set to false if the context already contains
    a pre-computed answer or if no arithmetic is needed."""


class _CalcDecision(BaseModel):
    needs_calculation: bool = Field(description="True if explicit arithmetic is required.")


# DeepSeek rejects json_schema response_format; function_calling is required
_structured_llm = llm.with_structured_output(_CalcDecision, method="function_calling")
 

# ── Section headers used when both sources are present ────────────────────────
_HEADER_REPORT = "【Annual Report Data】"
_HEADER_NEWS = "【Recent News】"


def aggregate_node(state: MainState) -> dict:
    """Merge outputs from all parallel agents into a single aggregated_context string.

    This node sits between the parallel agents (retrieval_agent, news_agent) and
    the downstream nodes (calculator_agent → guardrails → answer). Its job is to
    combine whatever data was retrieved into one clean block of text.

    Flow:
        retrieval_agent ──┐
                          ├─► aggregate ─► calculator_agent ─► guardrails ─► answer
        news_agent      ──┘

    State fields read:
        retrieval_result : dict  — output of the retrieval subgraph;
                                   contains "answer_draft" (synthesised text)
        news_context     : str   — raw Tavily snippets from news_agent

    State fields written:
        aggregated_context : str  — the merged text passed to all downstream nodes.
        needs_calculation  : bool — whether the answer requires explicit arithmetic,
                                    decided by an LLM call on the aggregated context.
    """

    # ── 1. Extract each source ────────────────────────────────────────────────

    # retrieval_result is a dict produced by the retrieval subgraph.
    # "answer_draft" is the LLM-synthesised answer based on graded PDF chunks.
    retrieval_result: RetrievalResult = state.get("retrieval_result") or {}
    answer_draft = (retrieval_result.get("answer_draft") or "").strip()

    # news_context is a plain string of Tavily search snippets (or empty if
    # news search was not needed).
    news_context = (state.get("news_context") or "").strip()

    # ── 2. Build aggregated_context ────────────────────────────────────────────

    # Collect only the non-empty sections so we don't add blank headers.
    sections: list[str] = []

    if answer_draft:
        sections.append(f"{_HEADER_REPORT}\n{answer_draft}")

    if news_context:
        sections.append(f"{_HEADER_NEWS}\n{news_context}")

    # Join sections with a blank line separator for readability.
    aggregated_context = "\n\n".join(sections)

    out: dict = {"aggregated_context": aggregated_context}

    # Decide whether the answer requires explicit arithmetic now that we can see
    # what data was actually retrieved (rather than guessing from the query alone).
    if not aggregated_context:
        out["needs_calculation"] = False
        return out

    query = (state.get("query") or "").strip()
    try:
        decision: _CalcDecision = _structured_llm.invoke([
            SystemMessage(content=_CALC_PROMPT),
            HumanMessage(content=f"Query: {query}\n\nContext:\n{aggregated_context}"),
        ])
        out["needs_calculation"] = decision.needs_calculation
    except Exception:
        out["needs_calculation"] = False

    return out
