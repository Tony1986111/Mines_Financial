from __future__ import annotations

import os
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.checkpoint.postgres import PostgresSaver

from state import MainState
from nodes.compress_context import compress_context_node
from nodes.memory import memory_node
from nodes.retrieve_decision import retrieve_decision_node
from nodes.clarify import clarify_node
from nodes.aggregate import aggregate_node
from nodes.guardrails import guardrails_node
from nodes.fallback import fallback_node
from nodes.answer import answer_node
from agents.retrieval_agent import retrieval_graph
from agents.calculator_agent import calculator_agent_node
from agents.news_agent import news_agent_node


# ── Routing functions ──────────────────────────────────────────────────────────

def route_after_memory(state: MainState) -> str:
    return "answer" if state.get("cache_hit") else "retrieve_decision"


def _make_sends(state: MainState) -> list[Send]:
    sends = []
    if state.get("needs_retrieval"):
        sends.append(Send("retrieval_agent", {
            "query": state.get("query", ""),
            "messages": state.get("messages", []),
            "semantic_context": state.get("semantic_context", ""),
        }))
    if state.get("needs_news"):
        sends.append(Send("news_agent", state))
    return sends


def route_retrieve_decision(state: MainState) -> str | list[Send]:
    if state.get("is_out_of_scope", False):
        return "answer"

    if state.get("needs_retrieval") or state.get("needs_news"):
        if state.get("needs_clarification", False):
            return "clarify"
        return _make_sends(state)

    return "guardrails"


def route_after_aggregate(state: MainState) -> str:
    return "calculator_agent" if state.get("needs_calculation") else "guardrails"


def route_guardrails(state: MainState) -> str:
    return "fallback" if state.get("guardrails_passed") is False else "answer"


# ── Build supervisor graph ─────────────────────────────────────────────────────

builder = StateGraph(MainState)

builder.add_node("compress_context", compress_context_node)
builder.add_node("memory", memory_node)
builder.add_node("retrieve_decision", retrieve_decision_node)
builder.add_node("clarify", clarify_node)
builder.add_node("retrieval_agent", retrieval_graph)
builder.add_node("calculator_agent", calculator_agent_node)
builder.add_node("news_agent", news_agent_node)
builder.add_node("aggregate", aggregate_node)
builder.add_node("guardrails", guardrails_node)
builder.add_node("fallback", fallback_node)
builder.add_node("answer", answer_node)

builder.add_edge(START, "compress_context")
builder.add_edge("compress_context", "memory")
builder.add_conditional_edges(
    "memory",
    route_after_memory,
    {"answer": "answer", "retrieve_decision": "retrieve_decision"},
)

# path_map serves two purposes: (1) static lookup when the routing fn returns a string,
# and (2) telling LangGraph's compiler which nodes are reachable from here (used for
# visualisation in Studio). When route_retrieve_decision returns Send objects it bypasses
# this map entirely at runtime, but "retrieval_agent" and "news_agent" must still be
# listed here so Studio draws the edges and those nodes don't appear as isolated islands.
builder.add_conditional_edges(
    "retrieve_decision",
    route_retrieve_decision,
    {
        "clarify": "clarify",
        "guardrails": "guardrails",
        "answer": "answer",
        "retrieval_agent": "retrieval_agent",
        "news_agent": "news_agent",
    },
)

builder.add_edge("clarify", "retrieve_decision")

builder.add_edge("retrieval_agent", "aggregate")
builder.add_edge("news_agent", "aggregate")

builder.add_conditional_edges(
    "aggregate",
    route_after_aggregate,
    {"calculator_agent": "calculator_agent", "guardrails": "guardrails"},
)

builder.add_edge("calculator_agent", "guardrails")

builder.add_conditional_edges(
    "guardrails",
    route_guardrails,
    {"answer": "answer", "fallback": "fallback"},
)

builder.add_edge("fallback", END)
builder.add_edge("answer", END)


database_url = os.getenv("DATABASE_URL")
if not database_url:
    raise RuntimeError("DATABASE_URL is not set")

_pool = ConnectionPool(
    database_url,
    max_size=10,
    kwargs={"autocommit": True, "prepare_threshold": 0},
)
checkpointer = PostgresSaver(_pool)
checkpointer.setup()

# use graph = builder.compile() instead for langsmith studio
graph = builder.compile(checkpointer=checkpointer)
