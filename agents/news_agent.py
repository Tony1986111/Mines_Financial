from __future__ import annotations

from langchain_tavily import TavilySearch
from langchain_core.tools import tool

from state import MainState

# ── Tavily tool ────────────────────────────────────────────────────────────────

_tavily = TavilySearch(max_results=5, include_raw_content=False)

def search_mining_news(query: str) -> str:
    """Search for recent news about ASX mining companies (BHP, RIO, FMG, MIN, NST).

    Use for: recent events, current market conditions, analyst outlooks,
    project updates, regulatory changes, or anything not covered by annual reports.
    Do NOT use for historical financial figures — those come from annual reports.
    """
    asx_query = f"ASX mining {query}"
    try:
        result = _tavily.invoke(asx_query)
        # Newer langchain_tavily returns a dict instead of a pre-formatted string.
        if isinstance(result, dict):
            snippets = []
            if result.get("answer"):
                snippets.append(result["answer"])
            for r in result.get("results", []):
                title = r.get("title", "")
                url = r.get("url", "")
                content = r.get("content", "")
                snippets.append(f"• {title} ({url})\n  {content}")
            result = "\n\n".join(snippets) if snippets else ""
        return result if result else "No recent news found for this query."
    except Exception as e:
        return f"News search failed: {e}"


# ── Node ───────────────────────────────────────────────────────────────────────

def news_agent_node(state: MainState) -> dict:
    query = state.get("query", "")
    news = search_mining_news.invoke(query)
    return {"news_context": news}
