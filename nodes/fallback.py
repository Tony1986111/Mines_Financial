from __future__ import annotations

from langchain_core.messages import AIMessage

from state import MainState, RetrievalResult, RetrievedDoc

_GUIDANCE = """
Available data covers:
  • Companies   : BHP, Rio Tinto (RIO), Fortescue (FMG), Northern Star (NST), Mineral Resources (MIN)
  • Fiscal years : FY2023, FY2024, FY2025
  • Topics       : revenue, profit, EBITDA, capex, dividends, production volumes, debt, cash flow

Try rephrasing with a specific company and fiscal year, for example:
  "What was BHP's revenue in FY2024?"
  "Compare FMG and RIO profit margins in FY2024."\
"""


def _detect_reason(state: MainState) -> str:
    """Map the two guardrails failure cases to a human-readable explanation.

    Guardrails fails in exactly two ways:
      1. aggregated_context is empty  → nothing was retrieved or synthesis returned nothing
      2. aggregated_context too short → something came back but it was not substantive
    """
    aggregated = (state.get("aggregated_context") or "").strip()

    if not aggregated:
        # Case 1: empty — distinguish whether docs were at least retrieved
        retrieval_result: RetrievalResult = state.get("retrieval_result") or {}
        docs: list[RetrievedDoc] = retrieval_result.get("documents") or []
        if docs:
            return "Relevant documents were retrieved but could not be synthesised into an answer."
        return "No relevant information was found in the annual reports or recent news."

    # Case 2: content exists but too short to be useful
    return "The retrieved information was insufficient to form a complete answer."


def fallback_node(state: MainState) -> dict:
    """Return a contextual fallback response when guardrails rejects the answer.

    Fallback routes directly to END (bypasses answer_node), so this node sets
    both final_answer and AIMessage to keep the conversation history intact.
    """
    reason = _detect_reason(state)
    message = reason + _GUIDANCE

    return {
        "final_answer": message,
        "messages": [AIMessage(content=message)],
    }
