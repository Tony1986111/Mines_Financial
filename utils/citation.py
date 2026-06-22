from __future__ import annotations
# Enables modern type annotation syntax (e.g. list[str]) on Python < 3.10.

import re

from state import RetrievedDoc

# Matches [N] and [1,2] citation markers embedded in body text.
# Examples: "billion [1]," / "growth [1,3]." / "reported [2,4,5]"
_INLINE_CITATION_RE = re.compile(r'\[(\d+(?:,\d+)*)\]')


# ─── Private helpers ──────────────────────────────────────────────────────────

def _build_entries_detail(docs: list[RetrievedDoc]) -> tuple[list[str], list[RetrievedDoc]]:
    """Return (entries, rep_docs) where rep_docs[i] is the first doc for entries[i].
    Dedup key is (company, fy, page). Includes section name when available.
    """
    seen: set[tuple] = set()
    entries: list[str] = []
    rep_docs: list[RetrievedDoc] = []

    for doc in docs:
        company = doc.get("company", "Unknown")
        fy = doc.get("fy", "")
        page = doc.get("page", "")

        key = (company, fy, page)
        if key in seen:
            continue
        seen.add(key)

        entry = f"{company} Annual Report"
        if fy:
            entry += f" {fy}"
        if page != "" and page is not None:
            entry += f", p.{page}"

        entries.append(entry)
        rep_docs.append(doc)

    return entries, rep_docs


def _build_entries(docs: list[RetrievedDoc]) -> list[str]:
    entries, _ = _build_entries_detail(docs)
    return entries


# ─── Public functions ─────────────────────────────────────────────────────────

def build_prompt_sources(docs: list[RetrievedDoc]) -> str:
    """Return a numbered source list for injection into the LLM system prompt.

    The LLM uses these numbers to insert [N] citation markers at the
    appropriate positions in its answer. Numbering is identical to
    format_sources_section so markers resolve correctly on the frontend.

    Example output:
        [1] BHP Annual Report FY2024, p.12
        [2] BHP Annual Report FY2024, p.34
        [3] RIO Annual Report FY2024, p.7
    """
    entries = _build_entries(docs)
    if not entries:
        return ""
    # No "Sources:" header — this string goes into the LLM prompt, not the answer
    return "\n".join(f"[{i}] {line}" for i, line in enumerate(entries, 1))

def filter_and_renumber(
    answer_body: str, docs: list[RetrievedDoc]
) -> tuple[str, str, list[RetrievedDoc], list[str]]:
    """Remove uncited sources and renumber [N] markers consistently.

    Call BEFORE apply_superscripts — this function operates on plain [N] text.

    Returns (rewritten_body, sources_section, cited_docs, cited_labels):
      - cited_docs:   representative doc dict for each cited entry (hover preview)
      - cited_labels: formatted label string for each cited entry (hover header)

    If the LLM cited nothing, returns (answer_body, "", [], []).
    """
    entries, rep_docs = _build_entries_detail(docs)
    if not entries:
        return answer_body, "", [], []

    valid_cited: list[int] = []
    seen: set[int] = set()
    for m in _INLINE_CITATION_RE.finditer(answer_body):
        for part in m.group(1).split(","):
            try:
                n = int(part.strip())
                if n not in seen and 1 <= n <= len(entries):
                    valid_cited.append(n)
                    seen.add(n)
            except ValueError:
                pass
    if not valid_cited:
        return answer_body, "", [], []

    renumber: dict[int, int] = {old: new for new, old in enumerate(valid_cited, 1)}

    def _rewrite(match: re.Match) -> str:
        new_parts: list[int] = []
        for part in match.group(1).split(","):
            try:
                n = int(part.strip())
                if n in renumber:
                    new_parts.append(renumber[n])
            except ValueError:
                pass
        new_parts.sort()
        return "[" + ",".join(str(x) for x in new_parts) + "]" if new_parts else ""

    renumbered_body = _INLINE_CITATION_RE.sub(_rewrite, answer_body)

    cited_docs = [rep_docs[n - 1] for n in valid_cited]
    cited_labels = [entries[n - 1] for n in valid_cited]
    numbered = "\n".join(f"[{i}] {e}" for i, e in enumerate(cited_labels, 1))
    sources_section = f"Sources:\n{numbered}"

    return renumbered_body, sources_section, cited_docs, cited_labels

def apply_superscripts(answer_body: str, cited_docs: list[RetrievedDoc] | None = None) -> str:
    """Convert inline [N] citation markers to HTML superscript tags.
    Call this on the answer body BEFORE appending the Sources section.
    When cited_docs is provided (returned by filter_and_renumber), adds a
    data-n attribute so the frontend can look up hover preview by index.
    """

    def _replace(m: re.Match) -> str:
        nums = m.group(1)
        first_n = int(nums.split(",")[0].strip())
        data_n = f' data-n="{first_n}"' if 1 <= first_n <= len(cited_docs) else ""
        return f'<sup class="citation"{data_n}>[{nums}]</sup>'

    return _INLINE_CITATION_RE.sub(_replace, answer_body)


