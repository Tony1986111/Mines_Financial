from __future__ import annotations

from state import MainState

# ── Section headers used when both sources are present ────────────────────────
_HEADER_REPORT = "【Annual Report Data】"
_HEADER_NEWS   = "【Recent News】"
_HEADER_CALC   = "【Calculation Result】"


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
        calc_result      : str   — calculator output; empty at this point because
                                   calculator_agent runs AFTER aggregate.
                                   Included here for completeness if state already
                                   has a value from a previous graph run.

    State field written:
        aggregated_context : str — the merged text passed to all downstream nodes.
    """

    # ── 1. Extract each source ─────────────────────────────────────────────────

    # retrieval_result is a dict produced by the retrieval subgraph.
    # "answer_draft" is the LLM-synthesised answer based on graded PDF chunks.
    retrieval_result = state.get("retrieval_result") or {}
    answer_draft     = (retrieval_result.get("answer_draft") or "").strip()

    # news_context is a plain string of Tavily search snippets (or empty if
    # news_agent was not selected by dynamic_tool_selector).
    news_context = (state.get("news_context") or "").strip()

    # calc_result is normally empty here (calculator runs after this node).
    # If somehow it already has a value, include it.
    calc_result = (state.get("calc_result") or "").strip()

    # ── 2. Build aggregated_context ────────────────────────────────────────────

    # Collect only the non-empty sections so we don't add blank headers.
    sections: list[str] = []

    if answer_draft:
        sections.append(f"{_HEADER_REPORT}\n{answer_draft}")

    if news_context:
        sections.append(f"{_HEADER_NEWS}\n{news_context}")

    if calc_result:
        sections.append(f"{_HEADER_CALC}\n{calc_result}")

    # Join sections with a blank line separator for readability.
    aggregated_context = "\n\n".join(sections)

    return {"aggregated_context": aggregated_context}
