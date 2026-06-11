from unittest.mock import MagicMock, patch

from nodes.aggregate import aggregate_node

_PATCH = "nodes.aggregate._structured_llm"


def _mock_calc(needs_calculation=False):
    m = MagicMock()
    m.needs_calculation = needs_calculation
    return m

_HEADER_REPORT = "【Annual Report Data】"
_HEADER_NEWS = "【Recent News】"


# Verify that aggregate_node returns an empty context when no sources exist.
def test_aggregate_returns_empty_string_when_all_sources_empty():
    # Run the node with an empty state to simulate no upstream agent output.
    result = aggregate_node({})

    # With no usable sections, the aggregated context should stay blank.
    assert result["aggregated_context"] == ""


# Verify that retrieval output is wrapped in the annual report section header.
def test_aggregate_only_retrieval_result_shows_report_header():
    state = {"retrieval_result": {"answer_draft": "BHP revenue was $21B."}}

    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.return_value = _mock_calc()
        result = aggregate_node(state)
    ctx = result["aggregated_context"]

    assert _HEADER_REPORT in ctx
    assert _HEADER_NEWS not in ctx
    assert "BHP revenue was $21B." in ctx


# Verify that news-only output receives the news section header.
def test_aggregate_only_news_context_shows_news_header():
    state = {"news_context": "BHP shares rose today."}

    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.return_value = _mock_calc()
        result = aggregate_node(state)
    ctx = result["aggregated_context"]

    assert _HEADER_NEWS in ctx
    assert _HEADER_REPORT not in ctx
    assert "BHP shares rose today." in ctx


# Verify that report and news sections are joined with a blank line.
def test_aggregate_report_and_news_joined_with_blank_line():
    state = {
        "retrieval_result": {"answer_draft": "Report data."},
        "news_context": "News data.",
    }

    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.return_value = _mock_calc()
        result = aggregate_node(state)
    ctx = result["aggregated_context"]

    assert _HEADER_REPORT in ctx
    assert _HEADER_NEWS in ctx

    sections = ctx.split("\n\n")
    assert len(sections) == 2


# Verify that whitespace-only source values are ignored.
def test_aggregate_whitespace_only_sources_treated_as_empty():
    # Use whitespace in available source slots to confirm trimming behavior.
    state = {
        "retrieval_result": {"answer_draft": "   "},
        "news_context": "\n",
    }

    # Aggregate should drop both empty-looking sections.
    result = aggregate_node(state)
    assert result["aggregated_context"] == ""


# Verify that malformed retrieval_result objects do not crash aggregation.
def test_aggregate_missing_answer_draft_key_handled_gracefully():
    # Simulate retrieval_result existing without the expected answer_draft field.
    state = {"retrieval_result": {}}

    # Missing answer_draft should simply produce no report section.
    result = aggregate_node(state)
    assert result["aggregated_context"] == ""


# Verify that None source values are safely skipped.
def test_aggregate_none_values_handled_gracefully():
    state = {"retrieval_result": None, "news_context": None, "calc_result": None}

    result = aggregate_node(state)
    assert result["aggregated_context"] == ""


# Verify that needs_calculation is false when no context was produced.
def test_aggregate_empty_context_sets_needs_calculation_false_without_llm():
    with patch(_PATCH) as mock_llm:
        result = aggregate_node({})

    mock_llm.invoke.assert_not_called()
    assert result["needs_calculation"] is False


# Verify that needs_calculation is set from the LLM decision when context exists.
def test_aggregate_needs_calculation_true_when_llm_decides_arithmetic_needed():
    state = {
        "query": "How did BHP's profit grow from FY2023 to FY2024?",
        "retrieval_result": {"answer_draft": "FY2023 profit: $12B. FY2024 profit: $15B."},
    }

    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.return_value = _mock_calc(needs_calculation=True)
        result = aggregate_node(state)

    assert result["needs_calculation"] is True


# Verify that needs_calculation is false when context already has the answer.
def test_aggregate_needs_calculation_false_when_answer_precomputed():
    state = {
        "query": "What was BHP's profit margin in FY2024?",
        "retrieval_result": {"answer_draft": "BHP's net profit margin in FY2024 was 18.3%."},
    }

    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.return_value = _mock_calc(needs_calculation=False)
        result = aggregate_node(state)

    assert result["needs_calculation"] is False


# Verify that LLM errors default needs_calculation to false.
def test_aggregate_llm_exception_defaults_needs_calculation_to_false():
    state = {"retrieval_result": {"answer_draft": "Some data."}}

    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.side_effect = RuntimeError("LLM unavailable")
        result = aggregate_node(state)

    assert result["needs_calculation"] is False
