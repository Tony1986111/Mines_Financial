from __future__ import annotations

from langchain_tavily import TavilySearch
from langchain_core.tools import tool

from state import MainState

# ── Tavily tool ────────────────────────────────────────────────────────────────

_tavily = TavilySearch(max_results=5, include_raw_content=False)


@tool
def search_mining_news(query: str) -> str:
    """Search for recent news about ASX mining companies (BHP, RIO, FMG, MIN, NST).

    Use for: recent events, current market conditions, analyst outlooks,
    project updates, regulatory changes, or anything not covered by annual reports.
    Do NOT use for historical financial figures — those come from annual reports.
    """
    asx_query = f"ASX mining {query}"
    try:
        # TavilySearch.invoke() returns a pre-formatted string when called directly.
        result = _tavily.invoke(asx_query)
        return result if result else "No recent news found for this query."
    except Exception as e:
        return f"News search failed: {e}"


# ── Node ───────────────────────────────────────────────────────────────────────

def news_agent_node(state: MainState) -> dict:
    query = state.get("query", "").strip()
    if not query:
        return {"news_context": ""}

    # Pass query directly — search_mining_news already adds the "ASX mining" prefix.
    news = search_mining_news.invoke(query)
    return {"news_context": news}
