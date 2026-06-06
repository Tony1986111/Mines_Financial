from __future__ import annotations

import operator
from typing import Annotated
from typing_extensions import TypedDict
from langgraph.graph.message import add_messages
from langchain_core.messages import AnyMessage


def _merge_company_status(existing: dict, update: dict) -> dict:
    """Merge two company_status dicts. Used as a LangGraph reducer so parallel
    retrieve_companies nodes can each write their own company's status without
    overwriting each other."""
    return {**existing, **update}


class MainState(TypedDict):
    messages:               Annotated[list[AnyMessage], add_messages]
    needs_retrieval:        bool
    needs_news:             bool
    needs_clarification:    bool
    selected_agents:        list[str]
    clarification_question: str
    query:                  str
    retrieval_result:       dict
    calc_result:            str
    news_context:           str
    aggregated_context:     str
    needs_calculation:      bool
    semantic_context:       str
    cache_hit:              bool
    guardrails_passed:      bool
    is_out_of_scope:        bool
    final_answer:           str
    chart_data:             list
    sources:                list
    confidence:             str
    compressed:             bool


class RetrievalState(TypedDict):
    messages:         Annotated[list[AnyMessage], add_messages]
    query:            str
    rewritten_query:  str
    companies:        list[str]
    company_queries:  list[dict]
    semantic_context: str
    retrieved_docs:   Annotated[list[dict], operator.add]
    merged_docs:      list[dict]
    graded_docs:      list[dict]
    answer_draft:     str
    grade:            str
    retry_count:      int
    retrieval_result: dict
    company_status:   Annotated[dict[str, bool], _merge_company_status]


class CompanyDocsState(TypedDict):
    company: str
    query:   str
    docs:    list[dict]


class RetrievalOutput(TypedDict):
    retrieval_result: dict
