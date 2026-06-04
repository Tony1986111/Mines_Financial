from __future__ import annotations
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from state import RetrievalState, RetrievalOutput
from retrieval_nodes.query_rewrite import query_rewrite_node
from retrieval_nodes.retrieve_parallel import retrieve_companies_node
from retrieval_nodes.merge import merge_node
from retrieval_nodes.grade_docs import grade_docs_node
from retrieval_nodes.grade_answer import grade_answer_node
from retrieval_nodes.synthesize import synthesize_node


ALL_COMPANIES = ["BHP", "RIO", "FMG", "MIN", "NST"]

def fan_out_retrieve(state: RetrievalState) -> list[Send]:
    """Fan-out to one retrieve_companies node per company via Send API.
    On retry, company_queries already contains only missing companies,
    so this function naturally targets only those.
    Falls back to all 5 companies (minus already-found ones) when company_queries is empty.
    """
    company_queries = state.get("company_queries") or []
    if company_queries:
        return [
            Send("retrieve_companies", {"company": item["company"], "query": item["rewritten_query"]})
            for item in company_queries
        ]

    # Fallback: skip companies already confirmed found.
    company_status = state.get("company_status") or {}
    companies = state.get("companies") or ALL_COMPANIES
    if company_status:
        companies = [c for c in companies if not company_status.get(c, False)]
    query = state.get("rewritten_query") or state.get("query", "")
    return [Send("retrieve_companies", {"company": c, "query": query}) for c in companies]


def after_grade_docs(state: RetrievalState) -> str:
    if state.get("grade") != "pass" and state.get("retry_count", 0) < 2:
        return "query_rewrite"
    return "synthesize"


def after_grade_answer(state: RetrievalState) -> str:
    if state.get("retry_count", 0) >= 2:
        return END
    if state.get("grade") == "fail":
        return "query_rewrite"
    # grade == "pass" but some companies still have no relevant docs — retry for them.
    company_status = state.get("company_status") or {}
    if company_status and any(not found for found in company_status.values()):
        return "query_rewrite"
    return END


builder = StateGraph(RetrievalState, output=RetrievalOutput)

builder.add_node("query_rewrite",    query_rewrite_node)
builder.add_node("retrieve_companies", retrieve_companies_node)
builder.add_node("merge",            merge_node)
builder.add_node("grade_docs",       grade_docs_node)
builder.add_node("synthesize",        synthesize_node)
builder.add_node("grade_answer",     grade_answer_node)

builder.add_edge(START, "query_rewrite")
builder.add_conditional_edges("query_rewrite", fan_out_retrieve, ["retrieve_companies"])
builder.add_edge("retrieve_companies", "merge")
builder.add_edge("merge", "grade_docs")

builder.add_conditional_edges(
    "grade_docs",
    after_grade_docs,
    {"synthesize": "synthesize", "query_rewrite": "query_rewrite"},
)

builder.add_edge("synthesize", "grade_answer")

builder.add_conditional_edges(
    "grade_answer",
    after_grade_answer,
    {END: END, "query_rewrite": "query_rewrite"},
)

retrieval_graph = builder.compile()
