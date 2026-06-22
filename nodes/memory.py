from __future__ import annotations
import re
from memory.semantic import search_conclusions, CACHE_THRESHOLD
from state import MainState, Source

# Entity extraction constants

# Match the five known company tickers. \b is a word boundary, which prevents
# false positives such as "BHPX".
_TICKER_RE = re.compile(r'\b(BHP|RIO|FMG|MIN|NST)\b')

# Match fiscal year format FY20XX. re.IGNORECASE also matches values like fy2024.
_FY_RE = re.compile(r'\bFY20\d{2}\b', re.IGNORECASE)

# Full-name/alias to ticker mapping for cases where users write company names.
_ALIASES: dict[str, str] = {
    "fortescue": "FMG",
    "rio tinto": "RIO",
    "mineral resources": "MIN",
    "northern star": "NST",
}

# Maximum number of prior messages to scan (6 messages is roughly 3 recent turns).
_CONTEXT_MESSAGES = 6
    

# Helper functions

def _extract_entities(text: str) -> tuple[set[str], set[str]]:
    """Extract company ticker and fiscal year sets from text.

    Returns: (companies, fiscal_years)
    Example: _extract_entities("BHP FY2024 revenue") -> ({"BHP"}, {"FY2024"})
    """
    # findall returns all matched strings; set() removes duplicates.
    tickers: set[str] = set(_TICKER_RE.findall(text))

    # Check full-name aliases with text.lower() to avoid case mismatches.
    for alias, ticker in _ALIASES.items():
        if alias in text.lower():
            tickers.add(ticker)

    # Normalize casing so fy2024 also becomes FY2024.
    fys: set[str] = {m.upper() for m in _FY_RE.findall(text)}

    return tickers, fys

def _enrich_query(query: str, messages: list) -> str:
    """Fill missing company or fiscal-year context from recent message history.

    The query is changed only when an entity is actually missing, which avoids
    unnecessary state writes.

    Enrichment example:
        History:  "What was BHP's FY2024 revenue?"
        Current:  "What about their dividends?"
        Enriched: "What about their dividends? [BHP, FY2024]"

    The enriched query is used for the semantic cache lookup in memory_node and
    is also written back to state for query_rewrite_node to use as retrieval
    keywords.
    """
    companies_in_q, fys_in_q = _extract_entities(query)

    # The current query already has complete context.
    if companies_in_q and fys_in_q:
        return query

    # Take the latest _CONTEXT_MESSAGES history messages, excluding the current
    # query message. messages[-7:-1] means from the 7th-last item through the
    # 2nd-last item, excluding the final item.
    recent = messages[-(_CONTEXT_MESSAGES + 1):-1] if len(messages) > 1 else []

    context_companies: set[str] = set()
    context_fys: set[str] = set()

    # Scan backward from the most recent message so the latest context wins.
    for msg in reversed(recent):
        content = getattr(msg, "content", "")
        # Skip non-string content; multimodal message content can be a list.
        if not isinstance(content, str):
            continue
        c, f = _extract_entities(content)
        context_companies |= c
        context_fys |= f

    # Add only the parts missing from the current query.
    hints: list[str] = []
    if not companies_in_q and context_companies:
        hints.extend(sorted(context_companies))   # Stable order keeps tests deterministic.
    if not fys_in_q and context_fys:
        hints.extend(sorted(context_fys))

    if hints:
        return f"{query} [{', '.join(hints)}]"
    return query


# Node entry point

def memory_node(state: MainState) -> dict:
    """Read memory layers and inject context before the main pipeline starts.

    Layer 1 - conversation entity enrichment:
        Extract company names and fiscal years from recent message history, then
        fill missing entities in follow-up questions so queries like
        "What about their dividends?" do not lose company/fiscal-year context.

    Layer 2 - semantic cache lookup (ChromaDB):
        Search historical Q&A with similarity >= 0.85 and inject the result into
        semantic_context for synthesize_node to use as supplementary reference.
        Uses the enriched query so lookup and save share the same embedding.
    """
    query = state.get("query", "").strip()
    messages = state.get("messages") or []

    if not query:
        return {}

    # Layer 1: conversation entity enrichment
    enriched_query = _enrich_query(query, messages)
    # Layer 2: semantic cache lookup
    # Returns (answer, sources, score): score >= CACHE_THRESHOLD -> L2 direct hit,
    # score >= CONTEXT_THRESHOLD -> L2 supplementary context only.
    cached_answer: str
    cached_sources: list[Source]
    cached_answer, cached_sources, score = search_conclusions(enriched_query)
    cache_hit = score >= CACHE_THRESHOLD

    out: dict = {
        "semantic_context": cached_answer,
        "cache_hit": cache_hit,
        "sources": cached_sources if cache_hit else [],
    }

    # Write query back to state only when it actually changed.
    if enriched_query != query:
        out["query"] = enriched_query

    return out
