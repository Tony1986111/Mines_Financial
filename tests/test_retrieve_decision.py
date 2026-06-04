from unittest.mock import MagicMock, patch

from nodes.retrieve_decision import retrieve_decision_node

_PATCH = "nodes.retrieve_decision._structured_llm"


# Creates a fake structured LLM decision object for retrieve_decision_node tests.
def _mock_decision(
    needs_retrieval=True,
    needs_clarification=False,
    clarification_question="",
    direct_answer="",
):
    # Populate the same attributes the production structured response exposes.
    m = MagicMock()
    m.needs_retrieval        = needs_retrieval
    m.needs_clarification    = needs_clarification
    m.clarification_question = clarification_question
    m.direct_answer          = direct_answer
    return m


# Verifies an empty query short-circuits without calling the LLM.
def test_empty_query_returns_false_false_without_llm_call():
    # Patch the structured LLM so any unexpected invocation is observable.
    with patch(_PATCH) as mock_llm:
        # Run the node with an empty query.
        result = retrieve_decision_node({"query": ""})

    # Assert the LLM was skipped and retrieval is not needed.
    mock_llm.invoke.assert_not_called()
    assert result == {"needs_retrieval": False, "needs_clarification": False}


# Verifies whitespace-only queries are treated as empty.
def test_whitespace_query_also_skips_llm():
    # Patch the structured LLM so the short-circuit can be checked.
    with patch(_PATCH) as mock_llm:
        # Run the node with only spaces.
        result = retrieve_decision_node({"query": "   "})

    # Assert no model call happened and retrieval remains disabled.
    mock_llm.invoke.assert_not_called()
    assert result["needs_retrieval"] is False


# Verifies the node forwards a positive retrieval decision.
def test_needs_retrieval_true_forwarded():
    # Mock the LLM to request retrieval.
    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.return_value = _mock_decision(needs_retrieval=True)

        # Run the node on a financial query.
        result = retrieve_decision_node({"query": "BHP revenue?"})

    # Assert the retrieval flag is preserved and clarification stays false.
    assert result["needs_retrieval"] is True
    assert result["needs_clarification"] is False


# Verifies clarification text is included only when clarification is needed.
def test_clarification_question_set_only_when_needs_clarification_true():
    # Mock the LLM to require a clarification question.
    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.return_value = _mock_decision(
            needs_retrieval=True,
            needs_clarification=True,
            clarification_question="Which company?",
        )

        # Run the node on an ambiguous query.
        result = retrieve_decision_node({"query": "tell me about this company"})

    # Assert the clarification flag and question are returned.
    assert result["needs_clarification"] is True
    assert result["clarification_question"] == "Which company?"


# Verifies no clarification_question key is emitted when it is not needed.
def test_clarification_question_absent_when_no_clarification_needed():
    # Mock the LLM to say clarification is unnecessary.
    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.return_value = _mock_decision(needs_clarification=False)

        # Run the node on a specific query.
        result = retrieve_decision_node({"query": "BHP FY2024 profit?"})

    # Assert no clarification question is added to the result.
    assert "clarification_question" not in result


# Verifies blank LLM clarification text is replaced with fallback copy.
def test_empty_clarification_question_gets_fallback_text():
    """If LLM sets needs_clarification but leaves the question blank, use the fallback."""
    # Mock the LLM to require clarification but omit the question text.
    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.return_value = _mock_decision(
            needs_retrieval=True,
            needs_clarification=True,
            clarification_question="",
        )

        # Run the node on an ambiguous query.
        result = retrieve_decision_node({"query": "tell me about the company"})

    # Assert fallback text is present and points the user toward specificity.
    assert result["clarification_question"]
    assert "BHP" in result["clarification_question"] or "company" in result["clarification_question"].lower()


# Verifies direct LLM answers are stored as aggregated context.
def test_no_retrieval_with_direct_answer_sets_aggregated_context():
    """When LLM answers directly (greeting etc.), store it as aggregated_context."""
    # Mock the LLM to provide a direct answer without retrieval.
    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.return_value = _mock_decision(
            needs_retrieval=False,
            direct_answer="Hello! I can help with mining financials.",
        )

        # Run the node on a greeting.
        result = retrieve_decision_node({"query": "hello"})

    # Assert the answer is passed forward as aggregated context.
    assert result["needs_retrieval"] is False
    assert result["aggregated_context"] == "Hello! I can help with mining financials."


# Verifies no-retrieval decisions without an answer fall back to retrieval.
def test_no_retrieval_with_empty_direct_answer_flips_needs_retrieval_to_true():
    """LLM said no retrieval but gave no answer, so flip to retrieval."""
    # Mock the LLM to decline retrieval but provide no direct answer.
    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.return_value = _mock_decision(
            needs_retrieval=False,
            direct_answer="",
        )

        # Run the node on a query that still needs a useful response.
        result = retrieve_decision_node({"query": "something vague"})

    # Assert the node chooses retrieval to avoid an empty downstream answer.
    assert result["needs_retrieval"] is True


# Verifies LLM failures fail open to retrieval instead of stopping the graph.
def test_llm_exception_returns_fail_safe_retrieval():
    # Mock the LLM to raise like an unavailable model or service.
    with patch(_PATCH) as mock_llm:
        mock_llm.invoke.side_effect = RuntimeError("LLM unavailable")

        # Run the node on a query that would normally call the model.
        result = retrieve_decision_node({"query": "BHP revenue?"})

    # Assert the fail-safe decision asks the graph to retrieve context.
    assert result == {"needs_retrieval": True, "needs_clarification": False}
