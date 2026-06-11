"""
Tier 3 integration tests for graph routing logic.

graph.py opens a PostgreSQL connection at module level and raises RuntimeError
when DATABASE_URL is unset. The three module-level patches below intercept all
three failure points so the routing functions can be imported and tested without
a real database or API key.

What is tested here:
  The five pure routing functions that wire the LangGraph edges together.
  These are deterministic state-to-str or state-to-list[Send] functions; no LLM is called.
"""
import os
from unittest.mock import MagicMock, patch

from langgraph.checkpoint.memory import MemorySaver as _MemorySaver

# Must set before graph.py module-level code runs.
os.environ.setdefault("DATABASE_URL", "postgresql://test/testdb")

# LangGraph validates checkpointer type, so use MemorySaver for compile().
_p_conn = patch("psycopg.Connection.connect", return_value=MagicMock())
_mock_saver = _MemorySaver()
_mock_saver.setup = lambda: None
_p_pg = patch("langgraph.checkpoint.postgres.PostgresSaver", return_value=_mock_saver)
_p_conn.start()
_p_pg.start()

from graph import (          # noqa: E402  (import after env + patches)
    route_after_memory,
    route_retrieve_decision,
    route_after_aggregate,
    route_guardrails,
    _make_sends,
)


# route_after_memory

# Verifies a cache hit can skip retrieval and go straight to answer.
def test_cache_hit_routes_to_answer():
    # Assert the routing target for the cached-answer path.
    assert route_after_memory({"cache_hit": True}) == "answer"


# Verifies an explicit cache miss continues into retrieval planning.
def test_no_cache_hit_routes_to_retrieve_decision():
    # Assert the routing target when cache lookup did not find an answer.
    assert route_after_memory({"cache_hit": False}) == "retrieve_decision"


# Verifies missing cache metadata is treated like a cache miss.
def test_missing_cache_hit_defaults_to_retrieve_decision():
    # Assert the default route when cache_hit is absent from state.
    assert route_after_memory({}) == "retrieve_decision"


# route_retrieve_decision

# Verifies direct-answer decisions still pass through guardrails.
def test_no_retrieval_needed_routes_to_guardrails():
    """Direct answers (greetings, concept questions) still pass through guardrails."""
    # Assert no-retrieval states move to safety validation before answering.
    assert route_retrieve_decision({"needs_retrieval": False}) == "guardrails"


# Verifies retrieval requests that need user detail route to clarification.
def test_needs_clarification_routes_to_clarify():
    # Build state where retrieval is needed but the query is under-specified.
    state = {"needs_retrieval": True, "needs_clarification": True}

    # Assert the graph asks a clarifying question next.
    assert route_retrieve_decision(state) == "clarify"


# Verifies clear retrieval requests fan out directly to agent sends.
def test_retrieval_no_clarification_returns_agent_sends():
    # Build state where retrieval can proceed without more user input.
    state = {"needs_retrieval": True, "needs_clarification": False}

    # Assert the routing returns a list of Send objects targeting retrieval_agent.
    result = route_retrieve_decision(state)
    assert isinstance(result, list)
    assert result[0].node == "retrieval_agent"


# Verifies clarification has priority when both routing flags are true.
def test_clarification_takes_priority_over_retrieval_flag():
    """When both flags are True, clarify is returned so the user answers first."""
    # Build the overlapping state to exercise routing precedence.
    state = {"needs_retrieval": True, "needs_clarification": True}

    # Assert the user is asked for detail before retrieval starts.
    assert route_retrieve_decision(state) == "clarify"


# route_after_aggregate

# Verifies aggregation can request a calculator step.
def test_needs_calculation_routes_to_calculator_agent():
    # Assert calculation-needed states route to the calculator agent.
    assert route_after_aggregate({"needs_calculation": True}) == "calculator_agent"


# Verifies completed aggregation without math routes to guardrails.
def test_no_calculation_routes_to_guardrails():
    # Assert no-calculation states continue to safety validation.
    assert route_after_aggregate({"needs_calculation": False}) == "guardrails"


# Verifies missing calculation metadata defaults to no calculator step.
def test_missing_calculation_flag_routes_to_guardrails():
    # Assert absent needs_calculation is handled like False.
    assert route_after_aggregate({}) == "guardrails"


# route_guardrails

# Verifies passing guardrails allows the answer node to run.
def test_guardrails_passed_routes_to_answer():
    # Assert approved content routes to the answer node.
    assert route_guardrails({"guardrails_passed": True}) == "answer"


# Verifies failed guardrails route to the fallback response.
def test_guardrails_failed_routes_to_fallback():
    # Assert rejected content is handled by fallback instead of answer.
    assert route_guardrails({"guardrails_passed": False}) == "fallback"


# Verifies missing guardrails metadata allows direct-answer paths through.
def test_missing_guardrails_flag_defaults_to_answer():
    """Default is True: absence of the flag means context was never checked
    (e.g. direct-answer path), so allow through rather than block."""
    # Assert the route defaults to answer when the flag was never set.
    assert route_guardrails({}) == "answer"


# _make_sends

# Verifies retrieval-only path creates one retrieval send.
def test_make_sends_retrieval_only():
    sends = _make_sends({"needs_retrieval": True, "needs_news": False, "query": "BHP revenue"})
    assert len(sends) == 1
    assert sends[0].node == "retrieval_agent"


# Verifies news-only path creates one news send.
def test_make_sends_news_only():
    sends = _make_sends({"needs_retrieval": False, "needs_news": True, "query": "BHP news"})
    assert len(sends) == 1
    assert sends[0].node == "news_agent"


# Verifies both flags fan out to both agents.
def test_make_sends_both_agents():
    sends = _make_sends({"needs_retrieval": True, "needs_news": True, "query": "BHP"})
    nodes = {s.node for s in sends}
    assert nodes == {"retrieval_agent", "news_agent"}


# Verifies retrieval sends receive only the query payload, not the full state.
def test_make_sends_retrieval_input_contains_query():
    state = {"needs_retrieval": True, "needs_news": False, "query": "BHP FY2024", "extra_key": "noise"}
    sends = _make_sends(state)
    arg = sends[0].arg
    assert arg["query"] == "BHP FY2024"
    assert "extra_key" not in arg


# Verifies news sends receive the full state object.
def test_make_sends_news_agent_receives_full_state():
    state = {"needs_retrieval": False, "needs_news": True, "query": "BHP news", "news_context": "existing"}
    sends = _make_sends(state)
    assert sends[0].arg is state


# Verifies a news-only query routes to list[Send] targeting news_agent.
def test_news_only_query_returns_agent_sends():
    state = {"needs_news": True, "needs_clarification": False}
    result = route_retrieve_decision(state)
    assert isinstance(result, list)
    assert result[0].node == "news_agent"


# Verifies a news query with clarification needed routes to clarify.
def test_news_query_with_clarification_routes_to_clarify():
    state = {"needs_news": True, "needs_clarification": True}
    assert route_retrieve_decision(state) == "clarify"
