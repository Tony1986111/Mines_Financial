from nodes.aggregate import aggregate_node

_HEADER_REPORT = "【Annual Report Data】"
_HEADER_NEWS   = "【Recent News】"
_HEADER_CALC   = "【Calculation Result】"


# Verify that aggregate_node returns an empty context when no sources exist.
def test_aggregate_returns_empty_string_when_all_sources_empty():
    # Run the node with an empty state to simulate no upstream agent output.
    result = aggregate_node({})

    # With no usable sections, the aggregated context should stay blank.
    assert result["aggregated_context"] == ""


# Verify that retrieval output is wrapped in the annual report section header.
def test_aggregate_only_retrieval_result_shows_report_header():
    # Build a state containing only an answer draft from report retrieval.
    state = {"retrieval_result": {"answer_draft": "BHP revenue was $21B."}}

    # Aggregate the available source sections into a single context string.
    result = aggregate_node(state)
    ctx = result["aggregated_context"]

    # The report section should appear and unrelated section headers should not.
    assert _HEADER_REPORT in ctx
    assert _HEADER_NEWS not in ctx
    assert _HEADER_CALC not in ctx
    assert "BHP revenue was $21B." in ctx


# Verify that news-only output receives the news section header.
def test_aggregate_only_news_context_shows_news_header():
    # Build a state where recent news is the only available source.
    state = {"news_context": "BHP shares rose today."}

    # Aggregate the state and inspect the rendered context.
    result = aggregate_node(state)
    ctx = result["aggregated_context"]

    # The news section should appear without a report header.
    assert _HEADER_NEWS in ctx
    assert _HEADER_REPORT not in ctx
    assert "BHP shares rose today." in ctx


# Verify that report, news, and calculation sections are joined predictably.
def test_aggregate_all_three_sources_joined_with_blank_line():
    # Provide all three upstream outputs so the node must keep each section.
    state = {
        "retrieval_result": {"answer_draft": "Report data."},
        "news_context":     "News data.",
        "calc_result":      "Calc data.",
    }

    # Aggregate and split the rendered text into section-sized chunks.
    result = aggregate_node(state)
    ctx = result["aggregated_context"]

    # All headers should be present when every source contributes content.
    assert _HEADER_REPORT in ctx
    assert _HEADER_NEWS in ctx
    assert _HEADER_CALC in ctx

    # Blank lines separate the three sections for readable final-answer input.
    sections = ctx.split("\n\n")
    assert len(sections) == 3


# Verify that whitespace-only source values are ignored.
def test_aggregate_whitespace_only_sources_treated_as_empty():
    # Use whitespace in available source slots to confirm trimming behavior.
    state = {
        "retrieval_result": {"answer_draft": "   "},
        "news_context":     "\n",
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
    # Pass None for every source slot to exercise defensive input handling.
    state = {"retrieval_result": None, "news_context": None, "calc_result": None}

    # None values should be treated as absent sections.
    result = aggregate_node(state)
    assert result["aggregated_context"] == ""
