from nodes.guardrails import guardrails_node


# Verify that a completely missing context is blocked before answer generation.
def test_guardrails_fails_when_aggregated_context_is_missing():
    """Empty context must not be allowed to reach the final answer node.

    In this project, guardrails sits on every path before answer generation.
    If retrieval, news, or direct-answer routing produced no usable context, the
    graph should route to fallback instead of letting the LLM invent an answer.
    """
    # Run guardrails with no aggregated_context key to simulate an empty state.
    result = guardrails_node({})

    # The node should mark the state as unsafe for final answer generation.
    assert result == {"guardrails_passed": False}


# Verify that an explicitly blank context is treated the same as missing data.
def test_guardrails_fails_when_aggregated_context_is_empty_string():
    """Whitespace-only or empty context is equivalent to missing context."""
    # Pass whitespace so the test covers trimming inside the guardrails node.
    result = guardrails_node({"aggregated_context": "   "})

    # Blank context must route downstream to fallback, not answer.
    assert result == {"guardrails_passed": False}


# Verify that tiny context fragments are not accepted as substantive evidence.
def test_guardrails_fails_when_context_is_too_short_to_be_substantive():
    """Very short context is treated as a degenerate answer.

    The current implementation uses a small character-count threshold. This is
    intentionally simple, but it still protects the graph from returning short
    fragments such as "ok" or "N/A" as if they were real financial analysis.
    """
    # Use a non-empty but short phrase to exercise the minimum-length check.
    result = guardrails_node({"aggregated_context": "too short"})

    # Short fragments should fail even though the key is present.
    assert result == {"guardrails_passed": False}


# Verify that a normal evidence paragraph is allowed through the guardrail.
def test_guardrails_passes_substantive_context():
    """A non-empty, substantive context should pass through to answer_node."""
    # Provide enough report-like context to satisfy the guardrail threshold.
    result = guardrails_node(
        {
            "aggregated_context": (
                "BHP FY2024 revenue was retrieved from the annual report."
            )
        }
    )

    # Substantive context should keep the graph on the answer path.
    assert result == {"guardrails_passed": True}


# Verify that surrounding whitespace is ignored before checking context length.
def test_guardrails_trims_context_before_checking_length():
    """Leading and trailing whitespace should not affect the substantive check."""
    # Wrap a valid context in spaces to confirm trimming happens first.
    result = guardrails_node(
        {
            "aggregated_context": (
                "   RIO FY2024 EBITDA was retrieved from annual report data.   "
            )
        }
    )

    # After trimming, the context remains long enough to pass.
    assert result == {"guardrails_passed": True}
