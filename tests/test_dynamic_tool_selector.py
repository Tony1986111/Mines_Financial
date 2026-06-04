from unittest.mock import MagicMock, patch

import pytest

from nodes.dynamic_tool_selector import dynamic_tool_selector_node

_PATCH = "nodes.dynamic_tool_selector._structured_llm"


# Build a fake structured LLM response with the selector fields under test.
def _mock_selection(use_retrieval=True, use_news=False, needs_calculation=False):
    # MagicMock lets the test attach simple attribute values like a parsed model.
    m = MagicMock()
    m.use_retrieval     = use_retrieval
    m.use_news          = use_news
    m.needs_calculation = needs_calculation
    return m


# Verify that an empty query bypasses the LLM and defaults to retrieval.
def test_empty_query_returns_retrieval_default_without_llm_call():
    # Patch the structured LLM so the test can prove it is not invoked.
    with patch(_PATCH) as mock_llm:
        result = dynamic_tool_selector_node({"query": ""})

    # Empty input should choose the safe retrieval path without calculation.
    mock_llm.invoke.assert_not_called()
    assert result["selected_agents"] == ["retrieval"]
    assert result["needs_calculation"] is False


# Verify that whitespace-only input follows the same bypass path.
def test_whitespace_query_also_skips_llm():
    # Whitespace should be stripped before deciding whether to call the LLM.
    with patch(_PATCH) as mock_llm:
        result = dynamic_tool_selector_node({"query": "   "})

    # The node should still return the default retrieval agent.
    mock_llm.invoke.assert_not_called()
    assert result["selected_agents"] == ["retrieval"]


# Verify that a retrieval-positive LLM decision selects the retrieval agent.
def test_use_retrieval_true_adds_retrieval_to_selected():
    # Mock the LLM decision so only retrieval is requested.
    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.return_value = _mock_selection(use_retrieval=True, use_news=False)
        result = dynamic_tool_selector_node({"query": "BHP FY2024 revenue?"})

    # The selected agents should include retrieval and exclude news.
    assert "retrieval" in result["selected_agents"]
    assert "news" not in result["selected_agents"]


# Verify that a news-positive LLM decision selects the news agent.
def test_use_news_true_adds_news_to_selected():
    # Mock the LLM decision so only news is requested.
    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.return_value = _mock_selection(use_retrieval=False, use_news=True)
        result = dynamic_tool_selector_node({"query": "latest BHP news?"})

    # The selected agents should include news and exclude retrieval.
    assert "news" in result["selected_agents"]
    assert "retrieval" not in result["selected_agents"]


# Verify that both LLM flags can select both downstream agents.
def test_both_flags_true_selects_both_agents():
    # Mock a query that needs annual report data and recent news.
    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.return_value = _mock_selection(use_retrieval=True, use_news=True)
        result = dynamic_tool_selector_node({"query": "BHP FY2024 and latest news?"})

    # Both agent names should be returned once.
    assert set(result["selected_agents"]) == {"retrieval", "news"}


# Verify that an all-false LLM response still leaves the graph with a route.
def test_both_flags_false_falls_back_to_retrieval():
    """When LLM returns both False, default to retrieval so the graph never stalls."""
    # Mock a selector response that declines every specialized path.
    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.return_value = _mock_selection(use_retrieval=False, use_news=False)
        result = dynamic_tool_selector_node({"query": "something?"})

    # Retrieval is the conservative default when no other agent is selected.
    assert result["selected_agents"] == ["retrieval"]


# Verify that the calculation flag is passed through to routing logic.
def test_needs_calculation_true_is_forwarded():
    # Mock the LLM decision to request calculation after retrieval.
    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.return_value = _mock_selection(use_retrieval=True, needs_calculation=True)
        result = dynamic_tool_selector_node({"query": "growth rate?"})

    # The selector output should preserve the calculation requirement.
    assert result["needs_calculation"] is True


# Verify that LLM errors fail safely to retrieval without calculation.
def test_llm_exception_returns_fail_safe_retrieval():
    # Raise from the patched LLM to simulate provider or parsing failure.
    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.side_effect = RuntimeError("LLM unavailable")
        result = dynamic_tool_selector_node({"query": "BHP revenue?"})

    # The graph should still have a deterministic fallback route.
    assert result["selected_agents"] == ["retrieval"]
    assert result["needs_calculation"] is False
