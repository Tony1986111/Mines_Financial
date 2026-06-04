from __future__ import annotations

from state import MainState

# Minimum character count for aggregated_context to be considered a real answer.
# Anything shorter is almost certainly an empty or degenerate response.
_MIN_LENGTH = 10


def guardrails_node(state: MainState) -> dict:
    """Validate that aggregated_context contains a substantive answer.

    This node sits on every path that leads to answer_node — both the normal
    retrieval path and the direct-answer path (needs_retrieval=False).

    Rules (rule-based, no LLM call):
      - FAIL if aggregated_context is empty or missing
      - FAIL if aggregated_context is shorter than _MIN_LENGTH characters
      - PASS otherwise

    Downstream routing (graph.py route_guardrails):
      pass  → answer_node
      fail  → fallback_node
    """
    content = (state.get("aggregated_context") or "").strip()

    if not content or len(content) < _MIN_LENGTH:
        return {"guardrails_passed": False}

    return {"guardrails_passed": True}
