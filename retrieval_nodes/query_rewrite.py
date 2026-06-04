from __future__ import annotations
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field
from state import RetrievalState
from utils.llm import llm

_SYSTEM_PROMPT = """You are a financial search query rewriter for ASX mining company annual reports.

Analyse the user's question and return three things:
1. rewritten_query — concise keywords optimised for document retrieval
2. companies — list of company ticker codes explicitly mentioned (BHP, RIO, FMG, MIN, NST).
   Return an empty list if no specific company is mentioned.
3. company_queries — one company-specific retrieval query per company-specific request.

Rules for rewritten_query:
- Keep company names and fiscal years explicit (e.g. "BHP FY2024").
- Use standard financial terminology (e.g. "net profit", "revenue", "EBITDA", "capital expenditure").
- Strip conversational filler ("please", "can you tell me", etc.).

Rules for companies:
- Only include companies explicitly named or clearly implied (e.g. "Fortescue" → "FMG").
- Use uppercase ticker codes only: BHP, RIO, FMG, MIN, NST.
- Return [] for general questions not tied to a specific company.

Rules for company_queries:
- Always create one item per company whenever multiple companies are mentioned, even if the same metric is requested for each.
- Each item must contain company and rewritten_query.
- The rewritten_query must include the company ticker, fiscal year if present, and the requested financial metric.
- Return [] only for general questions not tied to any specific company.

Examples:
  Input:  "What was BHP's FY2024 net profit?"
  Output: rewritten_query="BHP FY2024 net profit"  companies=["BHP"]  company_queries=[{"company":"BHP","rewritten_query":"BHP FY2024 net profit"}]

  Input:  "Compare revenue growth of Fortescue and Rio Tinto over three years"
  Output: rewritten_query="Fortescue FMG Rio Tinto revenue growth FY2023 FY2024 FY2025"  companies=["FMG","RIO"]  company_queries=[{"company":"FMG","rewritten_query":"FMG revenue growth FY2023 FY2024 FY2025"},{"company":"RIO","rewritten_query":"RIO revenue growth FY2023 FY2024 FY2025"}]

  Input:  "What was BHP's FY2023 profit and RIO's FY2024 dividends?"
  Output: rewritten_query="BHP FY2023 profit RIO FY2024 dividends"  companies=["BHP","RIO"]  company_queries=[{"company":"BHP","rewritten_query":"BHP FY2023 profit"},{"company":"RIO","rewritten_query":"RIO FY2024 dividends"}]

  Input:  "Rank BHP, RIO, FMG, MIN and NST by FY2024 EBITDA"
  Output: rewritten_query="BHP RIO FMG MIN NST FY2024 EBITDA ranking"  companies=["BHP","RIO","FMG","MIN","NST"]  company_queries=[{"company":"BHP","rewritten_query":"BHP FY2024 EBITDA"},{"company":"RIO","rewritten_query":"RIO FY2024 EBITDA"},{"company":"FMG","rewritten_query":"FMG FY2024 EBITDA"},{"company":"MIN","rewritten_query":"MIN FY2024 EBITDA"},{"company":"NST","rewritten_query":"NST FY2024 EBITDA"}]

  Input:  "How do mining companies usually report capital expenditure?"
  Output: rewritten_query="mining company capital expenditure reporting"  companies=[]  company_queries=[]"""


class _CompanyQuery(BaseModel):
    company: str = Field(description="Uppercase ticker: BHP, RIO, FMG, MIN, NST.")
    rewritten_query: str = Field(description="Company-specific retrieval query.")


class _QueryAnalysis(BaseModel):
    rewritten_query: str = Field(description="Retrieval keywords")
    companies: list[str] = Field(description="Uppercase tickers: BHP, RIO, FMG, MIN, NST. Empty if none.")
    company_queries: list[_CompanyQuery] = Field(description="Company-specific retrieval queries. Empty if none.")


_structured_llm = llm.with_structured_output(_QueryAnalysis, method="function_calling")


def query_rewrite_node(state: RetrievalState) -> dict:
    query = state.get("query", "").strip()
    company_status = state.get("company_status") or {}

    # Retry path: company_status already initialised — only target missing companies.
    # Skip the LLM call and build targeted queries directly from the base rewritten query.
    if company_status:
        missing = [c for c, found in company_status.items() if not found]
        if not missing:
            return {}
        base = state.get("rewritten_query") or query
        company_queries = [
            {"company": c, "rewritten_query": f"{c} {base}"}
            for c in missing
        ]
        return {"company_queries": company_queries}

    # First-run path: use LLM to rewrite query and initialise company_status.
    if not query:
        return {"rewritten_query": "", "companies": [], "company_queries": [], "company_status": {}}

    try:
        result: _QueryAnalysis = _structured_llm.invoke([
            SystemMessage(content=_SYSTEM_PROMPT),
            HumanMessage(content=query),
        ])
        return {
            "rewritten_query": result.rewritten_query,
            "companies": result.companies,
            "company_queries": [item.model_dump() for item in result.company_queries],
            "company_status": {c: False for c in result.companies},
        }
    except Exception:
        return {"rewritten_query": query, "companies": [], "company_queries": [], "company_status": {}}
