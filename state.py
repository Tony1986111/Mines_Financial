from __future__ import annotations

import operator
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage


# ── RetrievalState classes ─────────────────────────────────────────────────────

def _merge_company_status(existing: dict, update: dict) -> dict:
    """Merge two company_status dicts. Used as a LangGraph reducer so parallel
    retrieve_company nodes can each write their own company's status without
    overwriting each other."""
    return {**existing, **update}


class CompanyQuery(TypedDict):
    company: str
    query: str


class RetrievedDoc(TypedDict):
    content: str
    metadata: dict
    source: str
    page: int
    company: str
    fy: str
    chunk_index: int
    source_type: str
    title: str


class UnsupportedClaim(TypedDict):
    claim: str
    basis: str  # "calculation", "interpolation", or "general_knowledge"


class RetrievalResult(TypedDict):
    documents: list[RetrievedDoc]
    answer_draft: str
    grounded: str           # "yes", "partial", or "no"
    unsupported: list[UnsupportedClaim]
    grade: str              # "pass" or "fail"
    company_status: dict[str, bool]
    retrieved_count: int
    company_queries: list[CompanyQuery]
    rewritten_query: str

class CompanyDocsState(TypedDict):
    company: str
    query: str
    docs: list[RetrievedDoc]

class RetrievalState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    query: str
    semantic_context: str

    rewritten_query: str
    companies: list[str]
    company_queries: list[CompanyQuery]
    retrieved_docs: Annotated[list[RetrievedDoc], operator.add]
    graded_docs: list[RetrievedDoc]
    retrieved_count: int
    answer_draft: str
    grade: str
    grounded: str               
    unsupported_hints: list[str] 
    retry_count: int
    retrieval_result: RetrievalResult
    company_status: Annotated[dict[str, bool], _merge_company_status]


class RetrievalOutput(TypedDict):
    retrieval_result: RetrievalResult


# ── MainState classes ──────────────────────────────────────────────────────────

class Source(TypedDict):
    label: str
    preview: str
    source_type: str
    full_content: str


class ChartDataset(TypedDict):
    label: str
    data: list


class ChartData(TypedDict):
    type: str
    title: str
    labels: list[str]
    datasets: list[ChartDataset]


class MainState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    needs_retrieval: bool
    needs_news: bool
    needs_clarification: bool
    needs_calculation: bool
    cache_hit: bool
    guardrails_passed: bool
    is_out_of_scope: bool
    compressed: bool

    clarification_question: str
    query: str
    news_context: str
    aggregated_context: str
    semantic_context: str
    confidence: str
    final_answer: str
    
    chart_data: list[ChartData]
    sources: list[Source]
    retrieval_result: RetrievalResult
    unsupported_claims: list[UnsupportedClaim]
    
    
