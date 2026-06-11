from __future__ import annotations

from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from state import MainState
from utils.llm import llm

_SYSTEM_PROMPT = """You are a routing agent for an ASX mining financial report chatbot.
    Analyse the user's question and decide how to handle it.

    is_out_of_scope: true if the question is completely unrelated to ASX mining companies
    (BHP, RIO, FMG, MIN, NST) or their financial data — e.g. writing poems, weather,
    cooking, programming help, or any topic with no connection to these companies.
    Set to false for anything related to mining, finance, or these companies, even loosely.

    needs_retrieval: true if the question requires financial data from ASX mining company
    annual reports — metrics such as revenue, profit, EBITDA, capex, dividends, production
    volumes, debt, or cash flow for BHP, RIO, FMG, MIN, or NST across any fiscal year.
    Set to false for: greetings, general knowledge about mining concepts, questions about
    how you work, thank-yous, or anything not tied to specific company financial data.

    needs_news: true if the question asks about recent events, latest news, current market
    conditions, analyst outlooks, or anything requiring up-to-date web information beyond
    what annual reports contain. Examples: "latest news about FMG", "current share price",
    "recent project updates", "what is happening with RIO right now".

    needs_clarification: true only when the question is so vague that retrieval cannot
    meaningfully proceed — e.g. "tell me about this company" with no company named, or
    "what were the numbers last year" with no company or metric. For questions that are
    clear enough to attempt (even if some details are missing), set to false.

    clarification_question: if needs_clarification is true, write a short, specific question
    to resolve the ambiguity. Leave empty otherwise.

    direct_answer: if needs_retrieval, needs_news, needs_clarification, and is_out_of_scope
    are all false, provide a concise helpful answer. Leave empty otherwise.

    Examples:
    "BHP FY2024 revenue?" → is_out_of_scope=false, needs_retrieval=true, needs_clarification=false
    "Compare FMG and RIO profit margins over three years" → is_out_of_scope=false, needs_retrieval=true, needs_clarification=false
    "Tell me about this company" → is_out_of_scope=false, needs_retrieval=true, needs_clarification=true,
        clarification_question="Which company are you asking about? (BHP, RIO, FMG, MIN, or NST)"
    "What does EBITDA stand for?" → is_out_of_scope=false, needs_retrieval=false,
        direct_answer="EBITDA stands for Earnings Before Interest, Taxes, Depreciation and Amortisation..."
    "Hello, what can you help with?" → is_out_of_scope=false, needs_retrieval=false,
        direct_answer="I can analyse financial data from ASX mining company annual reports..."
    "Write me a poem" → is_out_of_scope=true
    "What is the weather today?" → is_out_of_scope=true
    """


class _RoutingDecision(BaseModel):
    is_out_of_scope: bool = Field(default=False, description="True if the question is completely unrelated to ASX mining companies or their financial data.")
    needs_retrieval: bool = Field(description="True if financial data from reports is needed.")
    needs_news: bool = Field(default=False, description="True if recent news or web search is needed.")
    needs_clarification: bool = Field(description="True if the question is too vague to proceed.")
    clarification_question: str  = Field(default="", description="Question to ask the user if clarification is needed.")
    direct_answer: str  = Field(default="", description="Direct answer when no retrieval or news is needed.")


# DeepSeek rejects json_schema response_format; function_calling is required
_structured_llm = llm.with_structured_output(_RoutingDecision, method="function_calling")


def retrieve_decision_node(state: MainState) -> dict:
    query = state.get("query", "").strip()
    if not query:
        return {"needs_retrieval": False, "needs_clarification": False}

    try:
        result: _RoutingDecision = _structured_llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=query),
        ])
        out: dict = {
            "is_out_of_scope": result.is_out_of_scope,
            "needs_retrieval": result.needs_retrieval,
            "needs_news": result.needs_news,
            "needs_clarification": result.needs_clarification,
        }
        if result.is_out_of_scope:
            return out

        if result.needs_clarification:
            out["clarification_question"] = (
                result.clarification_question
                or "Could you clarify which company (BHP, RIO, FMG, MIN, NST), "
                   "fiscal year, and metric you are asking about?"
            )

        # Retrieval/news path: agents will populate context downstream
        if result.needs_retrieval or result.needs_news:
            return out

        # Direct answer path: routing LLM answered inline, store it as context
        if result.direct_answer:
            out["aggregated_context"] = result.direct_answer
        else:
            # LLM skipped retrieval but provided no direct answer — force retrieval as fallback
            out["needs_retrieval"] = True

        return out
        
    except Exception:
        # Fail safe: always retrieve, never block on clarification
        return {"is_out_of_scope": False, "needs_retrieval": True, "needs_clarification": False}
