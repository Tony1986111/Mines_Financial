from __future__ import annotations
from langgraph.prebuilt import create_react_agent
from state import MainState
from tools.calculator import calculate_growth_rate, calculate_ratio, calculate_average, calculate
from utils.llm import llm

_SYSTEM_PROMPT = """You are a precise financial calculator for ASX mining company annual reports.
    Companies: BHP, Rio Tinto (RIO), Fortescue (FMG), Northern Star (NST), Mineral Resources (MIN).
    Fiscal years covered: FY2023, FY2024, FY2025.

    You will receive the user's question and a context block containing already-retrieved
    data (from annual reports and/or news). Your job:
    1. Extract the specific numerical values needed from the provided context.
    2. Call the appropriate calculation tool — do not do arithmetic in your head.
    3. Return a concise, clearly labelled result with units (e.g. USD billions, %).

    Rules:
    - Keep units consistent; normalise before calculating if values mix $B and $M.
    - Never guess or estimate financial figures — only use numbers present in the context.
    - If the context lacks the numbers required, state what is missing.
    - For growth rates, confirm chronological order (oldest value first)."""

_agent = create_react_agent(
    llm,
    [calculate_growth_rate, calculate_ratio, calculate_average, calculate],
    prompt=_SYSTEM_PROMPT,
)


def calculator_agent_node(state: MainState) -> dict:
    query = state.get("query", "")
    context = state.get("aggregated_context", "")

    user_content = f"Question: {query}\n\nRetrieved context:\n{context}"

    result = _agent.invoke({"messages": [{"role": "user", "content": user_content}]})
    calc_result = result["messages"][-1].content
    updated = f"{context}\n\n【Calculation Result】\n{calc_result}".strip()

    return {"calc_result": calc_result, "aggregated_context": updated}
