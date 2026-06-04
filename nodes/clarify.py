from __future__ import annotations

from langgraph.types import interrupt

from state import MainState

_FALLBACK_QUESTION = (
    "Could you clarify which company (BHP, RIO, FMG, MIN, NST), "
    "fiscal year, and metric you are asking about?"
)


def clarify_node(state: MainState) -> dict:
    question = state.get("clarification_question") or _FALLBACK_QUESTION

    # Pauses execution and sends the question to the caller.
    # Resumes when app.py calls graph.invoke(Command(resume=user_answer)).
    # The return value of interrupt() is exactly what the user typed.
    user_answer: str = interrupt({"question": question})

    original_query = state.get("query", "").strip()
    merged_query = f"{original_query} {user_answer}".strip() if original_query else user_answer

    return {
        "query": merged_query,
        "needs_clarification": False,
    }
