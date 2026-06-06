from __future__ import annotations

import os
from dotenv import load_dotenv
from psycopg_pool import ConnectionPool
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from langgraph.checkpoint.postgres import PostgresSaver

from state import MainState
from nodes.compress_context      import compress_context_node
from nodes.memory                import memory_node
from nodes.retrieve_decision     import retrieve_decision_node
from nodes.dynamic_tool_selector import dynamic_tool_selector_node
from nodes.clarify               import clarify_node
from nodes.aggregate             import aggregate_node
from nodes.guardrails            import guardrails_node
from nodes.fallback              import fallback_node
from nodes.answer                import answer_node
from agents.retrieval_agent      import retrieval_graph
from agents.calculator_agent     import calculator_agent_node
from agents.news_agent           import news_agent_node


# ── Routing functions ──────────────────────────────────────────────────────────

def route_after_memory(state: MainState) -> str:
    return "answer" if state.get("cache_hit") else "retrieve_decision"


def route_retrieve_decision(state: MainState) -> str:
    if state.get("is_out_of_scope", False):
        return "answer"
    if state.get("needs_retrieval") or state.get("needs_news"):
        if state.get("needs_clarification", False):
            return "clarify"
        return "dynamic_tool_selector"
    return "guardrails"


def _make_sends(state: MainState) -> list[Send]:
    agents = state.get("selected_agents") or ["retrieval"]
    sends  = []
    retrieval_input = {
        "query":            state.get("query", ""),
        "messages":         state.get("messages", []),
        "semantic_context": state.get("semantic_context", ""),
    }
    if "retrieval" in agents: sends.append(Send("retrieval_agent", retrieval_input))
    if "news"      in agents: sends.append(Send("news_agent",      state))
    return sends


def route_dynamic_tool_selector(state: MainState) -> list[Send]:
    return _make_sends(state)


def route_after_aggregate(state: MainState) -> str:
    return "calculator_agent" if state.get("needs_calculation") else "guardrails"


def route_guardrails(state: MainState) -> str:
    return "answer" if state.get("guardrails_passed", True) else "fallback"


# ── Build supervisor graph ─────────────────────────────────────────────────────

builder = StateGraph(MainState)

builder.add_node("compress_context",      compress_context_node)
builder.add_node("memory",                memory_node)
builder.add_node("retrieve_decision",     retrieve_decision_node)
builder.add_node("dynamic_tool_selector", dynamic_tool_selector_node)
builder.add_node("clarify",               clarify_node)
builder.add_node("retrieval_agent",       retrieval_graph)
builder.add_node("calculator_agent",      calculator_agent_node)
builder.add_node("news_agent",            news_agent_node)
builder.add_node("aggregate",             aggregate_node)
builder.add_node("guardrails",            guardrails_node)
builder.add_node("fallback",              fallback_node)
builder.add_node("answer",                answer_node)

builder.add_edge(START,              "compress_context")
builder.add_edge("compress_context", "memory")
builder.add_conditional_edges(
    "memory",
    route_after_memory,
    {"answer": "answer", "retrieve_decision": "retrieve_decision"},
)

builder.add_conditional_edges(
    "retrieve_decision",
    route_retrieve_decision,
    {"dynamic_tool_selector": "dynamic_tool_selector", "clarify": "clarify", "guardrails": "guardrails", "answer": "answer"},
)

builder.add_edge("clarify", "dynamic_tool_selector")

builder.add_conditional_edges(
    "dynamic_tool_selector",
    route_dynamic_tool_selector,
    ["retrieval_agent", "news_agent"],
)

builder.add_edge("retrieval_agent", "aggregate")
builder.add_edge("news_agent",      "aggregate")

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
builder.add_edge("answer",   END)


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
