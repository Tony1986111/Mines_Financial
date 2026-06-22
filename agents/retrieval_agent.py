from __future__ import annotations
from langgraph.graph import StateGraph, START, END
from langgraph.types import Send
from state import CompanyDocsState, CompanyQuery, RetrievalState, RetrievalOutput
from retrieval_nodes.query_rewrite import query_rewrite_node
from retrieval_nodes.retrieve_parallel import retrieve_company_node
from retrieval_nodes.grade_docs import grade_docs_node
from retrieval_nodes.grade_answer import grade_answer_node
from retrieval_nodes.synthesize import synthesize_node

 
ALL_COMPANIES = ["BHP", "RIO", "FMG", "MIN", "NST"]

def fan_out_retrieve(state: RetrievalState) -> list[Send]:
    """Fan-out to one retrieve_company node per company via Send API.
    On retry, company_queries already contains only missing companies,
    so this function naturally targets only those.
    Falls back to ALL_COMPANIES when query is not tied to specific companies.
    """
    company_queries: list[CompanyQuery] = state.get("company_queries") or []
    if company_queries:
        return [
            Send("retrieve_company", {"company": item["company"], "query": item["query"]})
            for item in company_queries
        ]

    # Fallback: general question with no specific companies — search all.
    query = state.get("rewritten_query") or state.get("query", "")
    return [Send("retrieve_company", {"company": c, "query": query}) for c in ALL_COMPANIES]


def after_grade_docs(state: RetrievalState) -> str:
    if state.get("grade") != "pass" and state.get("retry_count", 0) < 2:
        return "query_rewrite"
    return "synthesize"


def after_grade_answer(state: RetrievalState) -> str:
    company_status = state.get("company_status") or {}

    has_missing = False
    for found in company_status.values():
        if not found:
            has_missing = True
            break

    needs_retry = (
        state.get("grade") == "fail"
        or has_missing
        or len(state.get("unsupported_hints") or []) >= 2
    )
    
    if needs_retry and state.get("retry_count", 0) < 2:
        return "query_rewrite"
    return END


builder = StateGraph(RetrievalState, output=RetrievalOutput)

builder.add_node("query_rewrite", query_rewrite_node)
builder.add_node("retrieve_company", retrieve_company_node)
builder.add_node("grade_docs", grade_docs_node)
builder.add_node("synthesize", synthesize_node)
builder.add_node("grade_answer", grade_answer_node)

builder.add_edge(START, "query_rewrite")
builder.add_conditional_edges("query_rewrite", fan_out_retrieve, ["retrieve_company"])
builder.add_edge("retrieve_company", "grade_docs")

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
