from langchain_core.messages import AIMessage

from nodes.fallback import fallback_node


# Verify that no context and no documents produces a retrieval failure message.
def test_fallback_empty_context_no_docs_returns_not_found_reason():
    # Run fallback with an empty state to simulate total upstream failure.
    result = fallback_node({})

    # The final answer should explain that no relevant information was found.
    assert "No relevant information" in result["final_answer"]


# Verify that short context with documents is reported as insufficient evidence.
def test_fallback_non_empty_but_short_context_returns_insufficient_reason():
    """Non-empty context that is too short means insufficient, not synthesis failure."""
    # Include a document but keep aggregated context below the useful threshold.
    state = {
        "aggregated_context": "short",
        "retrieval_result":   {"documents": [{"content": "some doc"}]},
    }

    # Fallback should classify this as incomplete context rather than no docs.
    result = fallback_node(state)
    assert "insufficient to form a complete answer" in result["final_answer"]


# Verify that documents without synthesized context produce a synthesis failure.
def test_fallback_empty_context_with_docs_returns_synthesis_reason():
    """Docs present but context empty means synthesis failed, not retrieval failed."""
    # Provide retrieved documents but omit aggregated_context entirely.
    state = {
        "retrieval_result": {"documents": [{"content": "some doc"}]},
    }

    # The response should tell the user synthesis failed after retrieval.
    result = fallback_node(state)
    assert "could not be synthesised" in result["final_answer"]


# Verify that fallback appends an AIMessage for graph message history.
def test_fallback_messages_contains_ai_message():
    # Generate a fallback response from the simplest failure state.
    result = fallback_node({})

    # The node should return exactly one AI message for downstream consumers.
    messages = result["messages"]
    assert len(messages) == 1
    assert isinstance(messages[0], AIMessage)


# Verify that the stored AIMessage mirrors the returned final answer text.
def test_fallback_ai_message_content_matches_final_answer():
    # Run fallback and compare both response channels.
    result = fallback_node({})

    # Message history and final_answer should stay in sync.
    assert result["messages"][0].content == result["final_answer"]


# Verify that fallback guidance names every supported mining company ticker.
def test_fallback_guidance_text_lists_all_companies():
    # Get the default fallback answer shown when retrieval finds nothing.
    result = fallback_node({})
    answer = result["final_answer"]

    # The guidance should list each supported ticker so users can retry clearly.
    for ticker in ("BHP", "RIO", "FMG", "MIN", "NST"):
        assert ticker in answer
