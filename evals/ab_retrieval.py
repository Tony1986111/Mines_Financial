"""Retrieval-layer A/B harness for the numeric ground-truth cases.

Runs `retrieve_company_node` directly instead of the full graph, so no LLM is
called and the measured difference comes only from retrieval configuration.
Scores each case by whether a document containing the known correct figure
reaches the caller, and at which rank.

Cases come from evals/cases/retrieval_numeric.jsonl, whose expected.values are
figures verified to exist in the ingested chunks.

Usage:
    uv run python evals/ab_retrieval.py
"""

from __future__ import annotations

import json
import sys
import time
from pathlib import Path
from typing import Any, Callable

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import retrieval_nodes.retrieve_parallel as rp  # noqa: E402

CASE_FILE = ROOT / "evals" / "cases" / "retrieval_numeric.jsonl"

# Jina enforces 100,000 rerank tokens per minute and one case costs roughly
# 9,000, so the reranked config is paced rather than run flat out.
RERANK_PAUSE_SEC = 12

_ORIGINAL_RERANK = rp._rerank_documents


# ─── Case loading ─────────────────────────────────────────────────────────────

def load_cases(path: Path = CASE_FILE) -> list[dict[str, Any]]:
    """Load numeric retrieval cases and check every required field is present.

    Args:
        path: JSONL file holding the cases.

    Returns:
        The parsed cases in file order.

    Raises:
        ValueError: If a case is missing a field the harness depends on.
    """
    cases = [json.loads(line) for line in path.read_text().splitlines() if line.strip()]
    for case in cases:
        expected = case.get("expected") or {}
        for field in ["company", "retrieval_query", "values", "top_k"]:
            if not expected.get(field):
                raise ValueError(f"{case.get('id')}: expected.{field} is required")
    return cases


# ─── Scoring ──────────────────────────────────────────────────────────────────

def first_hit_rank(docs: list[dict], values: list[str]) -> int:
    """Return the 1-based rank of the first document containing every value.

    Args:
        docs: Retrieved documents in the order the node returned them.
        values: Ground-truth figures as they appear in the source tables.

    Returns:
        The rank of the first matching document, or 0 when none matches.
    """
    for rank, doc in enumerate(docs, 1):
        content = str(doc.get("content") or "")
        if all(value in content for value in values):
            return rank
    return 0


# ─── Configurations ───────────────────────────────────────────────────────────

def run_case(case: dict[str, Any], k: int, rerank: bool) -> list[dict]:
    """Retrieve documents for one case under a specific retrieval configuration.

    BM25_K is baked into the retriever when its pickle is loaded, so the
    per-company cache is cleared whenever k changes.

    Args:
        case: A numeric retrieval case.
        k: Candidate pool size for both BM25 and vector search.
        rerank: Whether to apply the cross-encoder rerank pass.

    Returns:
        The retrieved documents for the case's company.
    """
    rp.BM25_K = k
    rp.CHROMA_K = k
    rp._bm25_cache.clear()
    rp._rerank_documents = _ORIGINAL_RERANK if rerank else (lambda docs, query: docs)

    expected = case["expected"]
    result = rp.retrieve_company_node(
        {"company": expected["company"], "query": expected["retrieval_query"]}
    )
    return result["retrieved_docs"]


# ─── Report ───────────────────────────────────────────────────────────────────

def _summarise(ranks: list[int], top_k: int) -> dict[str, Any]:
    """Aggregate per-case ranks into hit rates and a mean hit rank."""
    hits_k = [r for r in ranks if 0 < r <= top_k]
    hits_5 = [r for r in ranks if 0 < r <= 5]
    return {
        f"hit@{top_k}": len(hits_k),
        "hit@5": len(hits_5),
        "mean_rank": round(sum(hits_k) / len(hits_k), 2) if hits_k else None,
    }


def main() -> None:
    """Run both configurations over every case and print a comparison table."""
    cases = load_cases()
    configs: list[tuple[str, int, bool, int]] = [
        ("old", 8, False, 0),
        ("new", 20, True, RERANK_PAUSE_SEC),
    ]

    ranks: dict[str, list[int]] = {}
    for name, k, rerank, pause in configs:
        ranks[name] = []
        for case in cases:
            docs = run_case(case, k, rerank)
            ranks[name].append(first_hit_rank(docs, case["expected"]["values"]))
            if pause:
                time.sleep(pause)

    print(f"\n{'case':34} {'value':>11} {'old':>6} {'new':>6}   verdict")
    print("-" * 74)
    for i, case in enumerate(cases):
        old, new = ranks["old"][i], ranks["new"][i]
        if old == new:
            verdict = "same"
        elif old == 0:
            verdict = "NEW FOUND IT"
        elif new == 0:
            verdict = "NEW LOST IT"
        else:
            verdict = f"rank {old} -> {new}" + ("  better" if new < old else "  worse")
        print(
            f"{case['id']:34} {case['expected']['values'][0]:>11} "
            f"{old or '-':>6} {new or '-':>6}   {verdict}"
        )

    top_k = cases[0]["expected"]["top_k"]
    print("-" * 74)
    for name in ["old", "new"]:
        stats = _summarise(ranks[name], top_k)
        print(f"{name:>4}: {stats}  (n={len(cases)})")


if __name__ == "__main__":
    main()
