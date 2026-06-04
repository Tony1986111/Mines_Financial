from __future__ import annotations

from langchain_core.messages import AnyMessage, HumanMessage, RemoveMessage, SystemMessage

from state import MainState
from utils.llm import llm

# Trigger compression once the message list exceeds this count (~5 conversation turns).
COMPRESS_THRESHOLD = 10

# Always keep this many recent messages verbatim so the LLM has immediate context.
KEEP_RECENT = 4

_SUMMARY_PROMPT = """Summarize the conversation history below in 2-3 concise sentences.
Focus on: ASX mining companies discussed, financial metrics mentioned
(revenue, profit, EBITDA, capex, dividends), fiscal years, and any
key conclusions reached. The summary replaces older messages to keep
the context window manageable."""


def _format_history(messages: list[AnyMessage]) -> str:
    lines = []
    for m in messages:
        role = type(m).__name__.replace("Message", "")
        lines.append(f"{role}: {m.content}")
    return "\n".join(lines)


def _summarize(messages: list[AnyMessage]) -> str:
    """Call the LLM to produce a short summary of the given messages."""
    try:
        response = llm.invoke([
            SystemMessage(content=_SUMMARY_PROMPT),
            HumanMessage(content=_format_history(messages)),
        ])
        return response.content.strip()
    except Exception:
        return ""


def compress_context_node(state: MainState) -> dict:
    """Compress message history when it grows too long.

    Strategy: summarize all messages older than KEEP_RECENT into a single
    SystemMessage, then delete the originals via RemoveMessage.  The most
    recent KEEP_RECENT messages are left untouched in state.

    Because MainState.messages uses the add_messages reducer, returning
    RemoveMessage(id=...) deletes a specific message by ID, and any new
    messages in the list are appended — so we only need to return the
    removals + the new summary message.
    """
    messages = state.get("messages") or []

    if len(messages) <= COMPRESS_THRESHOLD:
        return {"compressed": False}

    # Split: messages to compress vs. messages to keep verbatim.
    older  = messages[:-KEEP_RECENT]
    # recent stays in state; we don't return them (no duplication).

    summary_text = _summarize(older)
    if not summary_text:
        # Summarization failed — leave messages unchanged rather than risk data loss.
        return {"compressed": False}

    # Delete the older messages and inject one summary SystemMessage in their place.
    removals    = [RemoveMessage(id=m.id) for m in older]
    summary_msg = SystemMessage(
        content=f"[Earlier conversation compressed]: {summary_text}"
    )
    return {"messages": removals + [summary_msg], "compressed": True}
