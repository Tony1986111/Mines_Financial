from __future__ import annotations

import re

from langchain_core.messages import AIMessage, HumanMessage, SystemMessage

from memory.semantic import save_conclusion
from state import ChartData, MainState, RetrievalResult, RetrievedDoc, Source, UnsupportedClaim
from utils.chart import extract_chart_data
from utils.citation import apply_superscripts, build_prompt_sources, filter_and_renumber
from utils.llm_large import llm_large as llm

# Matches leading metadata lines like "Source: FMG_FY2023.pdf | Page: 133"
# that some document loaders embed at the start of page_content.
_METADATA_LINE_RE = re.compile(r'^(?:Source:[^\n]*\n?)+', re.IGNORECASE)


def _build_preview(doc: dict, max_chars: int = 250) -> str:
    content = (doc.get("content") or "").strip()
    content = _METADATA_LINE_RE.sub("", content).strip()
    return content[:max_chars]


_SYSTEM_PROMPT = """You are a financial analyst assistant for an ASX mining company chatbot.

You will receive the user's question and a combined context that may include:
  - 【Annual Report Data】: synthesised excerpts from annual reports
  - 【Recent News】: recent web search snippets about the companies
  - 【Calculation Result】: arithmetic result computed from the above data

Your task:
  1. Synthesise all available sections into one coherent, well-structured answer.
  2. Insert citation markers [N] immediately after each fact drawn from an annual report,
     where N matches the source list provided below.
  3. Reference news and calculation results naturally within the answer (no citation needed).
  4. If sections contradict each other, prefer annual report data and note the discrepancy.
  5. Be concise and factual. Do not repeat the section headers in your answer."""

_CITATION_INSTRUCTIONS = """

Citation rules — follow exactly:
  - Place [N] immediately after the claim it supports, before any punctuation.
  - Multiple sources for one claim: [1,3] — comma-separated, no spaces inside brackets.
  - Omit citation markers for general knowledge or your own reasoning.
  - Only use numbers that appear in the source list below. Never invent a number.

Available sources:
{sources}

Examples:
  Single source:
    "BHP's FY2024 revenue reached A$53.6 billion [1], an 8% increase year-on-year."

  Multiple sources supporting one claim:
    "Both BHP and RIO grew dividends in FY2024 [1,3], reflecting strong free cash flow [2]."

  Mixing cited and uncited facts:
    "Iron ore remains Australia's largest export commodity. BHP's production volume
     rose 4% to 260 Mt [1], while FMG shipped 192 Mt [4]." """

_CHART_INSTRUCTIONS = """

Available charts (insert placeholder on its own line after the paragraph discussing that metric):
{chart_lines}

Only use exact names listed above. Do not invent chart names."""


def _build_system_prompt(
    prompt_sources: str,
    chart_map: dict[str, dict],
) -> str:
    """Assemble the full system prompt by appending citation and chart sections."""
    prompt = _SYSTEM_PROMPT

    if prompt_sources:
        prompt += _CITATION_INSTRUCTIONS.format(sources=prompt_sources)

    if chart_map:
        chart_lines = "\n".join(
            f"  - {name} → {{{{chart:{name}}}}}" for name in chart_map
        )
        prompt += _CHART_INSTRUCTIONS.format(chart_lines=chart_lines)

    return prompt


_OUT_OF_SCOPE_REPLY = (
    "I can only answer questions about BHP, RIO, FMG, MIN, and NST financial data "
    "from their annual reports. Please ask a relevant question."
)


def answer_node(state: MainState) -> dict:
    if state.get("is_out_of_scope", False):
        return {
            "final_answer": _OUT_OF_SCOPE_REPLY,
            "chart_data": [],
            "sources": [],
            "confidence": "",
            "messages": [AIMessage(content=_OUT_OF_SCOPE_REPLY)],
        }

    # L1 cache hit: skip RAG entirely, return the stored answer as-is.
    # The cached answer is already fully formatted (superscripts + Sources section).
    # sources was pre-loaded into state by memory_node from the cache.
    if state.get("cache_hit"):
        cached = state.get("semantic_context", "")
        return {
            "final_answer": cached,
            "chart_data": [],
            "sources": state.get("sources") or [],
            "confidence": "",
            "messages": [AIMessage(content=cached)],
        }

    query = state.get("query", "").strip()
    aggregated = (state.get("aggregated_context") or "").strip()
    retrieval_result: RetrievalResult = state.get("retrieval_result") or {}
    docs: list[RetrievedDoc] = retrieval_result.get("documents", [])

    # Groundedness from grade_answer: "yes" / "partial" / "no"
    grounded = retrieval_result.get("grounded", "yes")
    unsupported: list[UnsupportedClaim] = retrieval_result.get("unsupported") or []
    _conf_map = {"yes": "high", "partial": "medium", "no": "low"}
    confidence = _conf_map.get(grounded, "high")

    # Build citation source list and chart map before calling LLM,
    # so both can be injected into the system prompt.
    prompt_sources = build_prompt_sources(docs)
    chart_data: list[ChartData] = extract_chart_data(docs, text=aggregated)
    chart_map = {c["title"].split(" (")[0]: c for c in chart_data}

    # Call LLM to synthesise all sources into one coherent answer.
    # Falls back to raw aggregated_context if the LLM call fails.
    if aggregated and query:
        try:
            response = llm.invoke([
                SystemMessage(content=_build_system_prompt(prompt_sources, chart_map)),
                HumanMessage(content=f"Question: {query}\n\nContext:\n{aggregated}"),
            ])
            final_answer = response.content.strip()
        except Exception:
            final_answer = aggregated
    else:
        final_answer = aggregated

    # Remove uncited sources and renumber [N] markers before converting to HTML.
    # Must run on plain [N] text — apply_superscripts would break the regex.
    final_answer, sources_section, cited_docs, cited_labels = filter_and_renumber(final_answer, docs)

    # Convert [N] → <sup class="citation" data-n="N">[N]</sup>.
    final_answer = apply_superscripts(final_answer, cited_docs)

    # Build sources list for frontend hover preview.
    sources: list[Source] = [
        {
            "label": label,
            "preview": _build_preview(doc),
            "source_type": doc.get("source_type", "text"),
            "full_content": (doc.get("content") or "").strip(),
        }
        for label, doc in zip(cited_labels, cited_docs)
    ]

    if sources_section:
        final_answer = f"{final_answer}\n\n{sources_section}"

    # Persist to semantic memory BEFORE appending confidence note,
    # so cached answers stay clean.
    if final_answer and retrieval_result.get("grade", "pass") == "pass" and grounded != "no":
        companies = list({d.get("company", "") for d in docs if d.get("company")})
        fys = list({d.get("fy", "") for d in docs if d.get("fy")})
        save_conclusion(
            query=query,
            answer=final_answer,
            companies=companies,
            fy=fys[0] if fys else "",
            sources=sources,
        )

    # Append inline confidence note for medium/low — high needs no caveat.
    if confidence in ("medium", "low"):
        claims = (unsupported or [])[:3]

        if claims:
            _basis_labels = {"calculation": "calculated from report data", "interpolation": "estimated from report data", "general_knowledge": "from LLM knowledge, but not found in reports"}
            formatted = "; ".join(
                f"{c['claim']} ({_basis_labels.get(c.get('basis', ''), c.get('basis', ''))})"
                if isinstance(c, dict) else c
                for c in claims
            )
            note = f"⚠️ Some claims in this answer could not be fully verified against the retrieved documents: {formatted}."
        else:
            note = "⚠️ This answer could not be fully verified against the retrieved documents."

        if confidence == "low":
            note += " Please cross-check with the original annual reports."
        final_answer += f"\n\n{note}"

    return {
        "final_answer": final_answer,
        "chart_data": chart_data,
        "sources": sources,
        "confidence": confidence,
        "unsupported_claims": unsupported,
        "messages": [AIMessage(content=final_answer)],
    }
