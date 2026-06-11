from unittest.mock import patch

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from nodes.compress_context import (
    COMPRESS_THRESHOLD,
    KEEP_RECENT,
    _format_history,
    compress_context_node,
)


# Build alternating chat messages so compression tests have realistic history.
def _make_messages(n: int) -> list:
    """Return n alternating Human/AI messages."""
    # Setup: start with an empty list and append messages by index parity.
    msgs = []
    for i in range(n):
        # Even indexes simulate user questions; odd indexes simulate AI answers.
        if i % 2 == 0:
            msgs.append(HumanMessage(content=f"question {i}"))
        else:
            msgs.append(AIMessage(content=f"answer {i}"))
    return msgs


# Verify context at the threshold is left unchanged.
def test_no_compression_below_threshold():
    """Exactly COMPRESS_THRESHOLD messages is a no-op and returns {}."""
    # Setup: create exactly the maximum number of messages before compression.
    msgs = _make_messages(COMPRESS_THRESHOLD)

    # Assertion: no state update is returned at the threshold.
    assert compress_context_node({"messages": msgs}) == {}


# Verify an empty message list does not trigger compression.
def test_no_compression_for_empty_messages():
    # Assertion: empty history is a no-op.
    assert compress_context_node({"messages": []}) == {}


# Verify missing message state is treated as a no-op.
def test_no_compression_for_missing_messages_key():
    # Assertion: absent messages return no state update.
    assert compress_context_node({}) == {}


# Verify compression is attempted once the message count exceeds the threshold.
def test_compression_triggered_above_threshold():
    """COMPRESS_THRESHOLD + 1 messages attempts summarization."""
    # Setup: create one more message than the compression threshold allows.
    msgs = _make_messages(COMPRESS_THRESHOLD + 1)

    # Patching: replace summarization with deterministic text for the test.
    with patch("nodes.compress_context._summarize", return_value="summary text") as mock_sum:
        # Action: run the compression node with oversized history.
        result = compress_context_node({"messages": msgs})

    # Assertions: summarization ran and the node returned message updates.
    mock_sum.assert_called_once()
    assert "messages" in result


# Verify compression removes old messages and appends a summary message.
def test_compression_result_contains_removals_and_summary():
    """Older messages should be removed and replaced with one SystemMessage."""
    # Setup: create enough messages to require compression.
    msgs = _make_messages(COMPRESS_THRESHOLD + 1)

    # Patching: make summarization deterministic so only node behavior is tested.
    with patch("nodes.compress_context._summarize", return_value="A summary."):
        # Action: compress the oversized message history.
        result = compress_context_node({"messages": msgs})

    # Expected data: removals cover older messages, plus one summary at the end.
    returned = result["messages"]
    older_count = len(msgs) - KEEP_RECENT
    # First `older_count` items are RemoveMessages, last item is the summary.
    assert len(returned) == older_count + 1

    # Assertions: the final returned item is a SystemMessage containing summary text.
    summary_msg = returned[-1]
    assert isinstance(summary_msg, SystemMessage)
    assert "A summary." in summary_msg.content


# Verify failed summarization aborts compression without state changes.
def test_compression_aborts_when_summarization_fails():
    """If _summarize returns '', leave messages unchanged (return {})."""
    # Setup: create enough messages that compression would normally run.
    msgs = _make_messages(COMPRESS_THRESHOLD + 1)

    # Patching: simulate summarization failure with an empty string.
    with patch("nodes.compress_context._summarize", return_value=""):
        # Action: run the compression node after summarization fails.
        result = compress_context_node({"messages": msgs})

    # Assertion: failed summarization returns no updates.
    assert result == {}


# Verify history formatting writes one role-prefixed line per message.
def test_format_history_produces_role_colon_content_lines():
    # Setup: include each supported message role in a short history.
    msgs = [
        HumanMessage(content="hello"),
        AIMessage(content="world"),
        SystemMessage(content="system note"),
    ]

    # Action: format the history into plain text lines.
    output = _format_history(msgs)
    lines = output.splitlines()

    # Assertions: each line preserves role and message content.
    assert lines[0] == "Human: hello"
    assert lines[1] == "AI: world"
    assert lines[2] == "System: system note"


# Verify the compression boundary changes exactly one message above threshold.
def test_threshold_boundary_exactly_one_above():
    """The threshold is a no-op, while one extra message triggers compression."""
    # Setup: compare histories at the threshold and one message above it.
    at_threshold = _make_messages(COMPRESS_THRESHOLD)
    one_above = _make_messages(COMPRESS_THRESHOLD + 1)

    # Assertion: exactly at the threshold remains a no-op.
    assert compress_context_node({"messages": at_threshold}) == {}

    # Patching: make the above-threshold compression deterministic.
    with patch("nodes.compress_context._summarize", return_value="summary"):
        # Action: run compression on the above-threshold history.
        result = compress_context_node({"messages": one_above})

    # Assertion: above the threshold returns message updates.
    assert "messages" in result
