"""Tests for memory_node execution order: entity enrichment before cache lookup.

The key behavioral guarantee is that _enrich_query runs before search_conclusions,
so follow-up queries like "What about their dividends?" are enriched with context
from message history (e.g., "[BHP, FY2024]") before the semantic cache lookup.
"""
from __future__ import annotations

from unittest.mock import patch, call
from langchain_core.messages import HumanMessage, AIMessage

from nodes.memory import memory_node


def _make_state(query: str, messages: list) -> dict:
    """Build a minimal MainState dict for memory_node."""
    return {"query": query, "messages": messages}


class TestMemoryNodeEnrichmentBeforeCacheLookup:
    """Verify that entity enrichment precedes the semantic cache lookup."""

    def test_enriched_query_passed_to_search_conclusions(self):
        """search_conclusions must receive the enriched query, not the raw follow-up."""
        history = [
            HumanMessage(content="What was BHP's FY2024 revenue?"),
            AIMessage(content="BHP FY2024 revenue was $53.6 billion."),
        ]
        follow_up = "What about their dividends?"
        state = _make_state(follow_up, history)

        captured: list[str] = []

        def fake_search(query: str):
            captured.append(query)
            return "", [], 0.0

        with patch("nodes.memory.search_conclusions", side_effect=fake_search):
            result = memory_node(state)

        assert len(captured) == 1, "search_conclusions should be called exactly once"
        assert captured[0] != follow_up, (
            "search_conclusions should NOT receive the raw follow-up query"
        )
        assert "BHP" in captured[0], "enriched query must contain company from history"
        assert "FY2024" in captured[0], "enriched query must contain FY from history"

    def test_enriched_query_written_to_state(self):
        """memory_node must update state['query'] with the enriched version."""
        history = [
            HumanMessage(content="Tell me about RIO FY2023."),
            AIMessage(content="RIO FY2023 was solid."),
        ]
        follow_up = "What were the dividends?"
        state = _make_state(follow_up, history)

        with patch("nodes.memory.search_conclusions", return_value=("", [], 0.0)):
            result = memory_node(state)

        assert "query" in result, "state must contain updated query when enrichment changed it"
        assert "RIO" in result["query"]
        assert "FY2023" in result["query"]

    def test_no_query_update_when_already_complete(self):
        """State query must not be rewritten when the query already has entities."""
        history = [
            HumanMessage(content="Unrelated message."),
        ]
        full_query = "What was BHP's FY2024 revenue?"
        state = _make_state(full_query, history)

        with patch("nodes.memory.search_conclusions", return_value=("", [], 0.0)):
            result = memory_node(state)

        assert "query" not in result, (
            "state must NOT overwrite query when it already has complete context"
        )

    def test_cache_hit_uses_enriched_query(self):
        """On a cache hit, the stored answer must come from the enriched-query lookup."""
        history = [
            HumanMessage(content="What was FMG's FY2024 production?"),
            AIMessage(content="FMG shipped 192 Mt in FY2024."),
        ]
        follow_up = "What about their costs?"
        state = _make_state(follow_up, history)

        cached_answer = "FMG C1 costs were US$18/wmt in FY2024."
        captured: list[str] = []

        from memory.semantic import CACHE_THRESHOLD

        def fake_search(query: str):
            captured.append(query)
            return cached_answer, [], CACHE_THRESHOLD

        with patch("nodes.memory.search_conclusions", side_effect=fake_search):
            result = memory_node(state)

        assert result["cache_hit"] is True
        assert result["semantic_context"] == cached_answer
        assert "FMG" in captured[0], "cache hit used raw query instead of enriched query"
        assert "FY2024" in captured[0], "cache hit used raw query instead of enriched query"

    def test_empty_query_returns_early(self):
        """memory_node must return an empty dict without calling search when query is blank."""
        state = _make_state("", [])

        with patch("nodes.memory.search_conclusions") as mock_search:
            result = memory_node(state)

        mock_search.assert_not_called()
        assert result == {}
