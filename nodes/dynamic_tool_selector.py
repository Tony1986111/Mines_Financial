from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from state import MainState
from utils.llm import llm

# ── Prompt ─────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """You are an agent router for an ASX mining financial report chatbot.

    Decide which data sources are needed to answer the question.

    use_retrieval: true when the question requires financial data from ASX mining company
    annual reports (BHP, RIO, FMG, MIN, NST) — e.g. revenue, profit, EBITDA, capex,
    dividends, production volumes, debt, or cash flow for any past fiscal year.

    use_news: true when the question asks about recent events, current market conditions,
    latest company news, ongoing projects, or anything that requires up-to-date web
    information beyond what annual reports contain.

    needs_calculation: true when answering requires explicit arithmetic — e.g. computing
    a growth rate, year-over-year change, profit margin, ratio, or average across multiple
    reported numbers. Set to false for qualitative questions or when a single number
    from a report is sufficient.

    Note: both use_retrieval and use_news can be true at the same time for questions
    that combine historical data with recent context.

    Examples:
    "BHP FY2024 revenue?"
        → use_retrieval=true,  use_news=false, needs_calculation=false

    "How did BHP's profit grow from FY2023 to FY2024?"
        → use_retrieval=true,  use_news=false, needs_calculation=true

    "What's happening with FMG's iron ore projects right now?"
        → use_retrieval=false, use_news=true,  needs_calculation=false

    "Compare RIO's FY2024 results with its latest analyst outlook"
        → use_retrieval=true,  use_news=true,  needs_calculation=false

    "What is BHP's latest profit margin and how does it compare to last year?"
        → use_retrieval=true,  use_news=false, needs_calculation=true
    """

# ── Pydantic schema for structured LLM output ──────────────────────────────────

class _AgentSelection(BaseModel):
    # Using individual booleans instead of a list so the LLM reasons about each
    # dimension independently — less error-prone than asking it to build a list.
    use_retrieval:     bool = Field(description="True if annual report data is needed.")
    use_news:          bool = Field(description="True if recent news / web search is needed.")
    needs_calculation: bool = Field(description="True if explicit arithmetic is required.")


_structured_llm = llm.with_structured_output(_AgentSelection, method="function_calling")

# ── Node ───────────────────────────────────────────────────────────────────────

def dynamic_tool_selector_node(state: MainState) -> dict:
    query = state.get("query", "").strip()
    if not query:
        # No query to analyse — default to retrieval only, no calculation.
        return {"selected_agents": ["retrieval"], "needs_calculation": False}

    try:
        result: _AgentSelection = _structured_llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=query),
        ])

        # Build the agent list from the two boolean flags.
        # At least one agent is always selected; 
        # fall back to retrieval if both are somehow false (shouldn't happen given the prompt, but defensive).
        selected: list[str] = []
        if result.use_retrieval:
            selected.append("retrieval")
        if result.use_news:
            selected.append("news")
        if not selected:
            selected = ["retrieval"]

        return {
            "selected_agents":   selected,
            "needs_calculation": result.needs_calculation,
        }

    except Exception:
        # Fail safe: run retrieval, skip news and calculation.
        return {"selected_agents": ["retrieval"], "needs_calculation": False}
