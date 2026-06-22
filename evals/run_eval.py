from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any, Callable


# Make both the project root and evals/evaluators importable when this script is
# executed directly with `uv run python evals/run_eval.py`.
ROOT = Path(__file__).resolve().parents[1]
EVALUATORS_DIR = ROOT / "evals" / "evaluators"
for path in (ROOT, EVALUATORS_DIR):
    if str(path) not in sys.path:
        sys.path.insert(0, str(path))

import boundary  # noqa: E402
import calculation  # noqa: E402
import retrieval  # noqa: E402
import routing  # noqa: E402


Suite = dict[str, Any]


# Registry mapping each suite name to its case-loader and evaluator functions.
# Adding a new eval suite only requires inserting an entry here.
SUITES: dict[str, Suite] = {
    "routing": {
        "load_cases": routing.load_cases,
        "evaluate": routing.evaluate_routing_output,
    },
    "retrieval": {
        "load_cases": retrieval.load_cases,
        "evaluate": retrieval.evaluate_retrieval_output,
    },
    "calculation": {
        "load_cases": calculation.load_cases,
        "evaluate": calculation.evaluate_calculation_output,
    },
    "boundary": {
        "load_cases": boundary.load_cases,
        "evaluate": boundary.evaluate_boundary_output,
    },
}


# Financial metric keywords used to detect what a query is asking about.
# These are matched case-insensitively against the raw query text.
METRIC_KEYWORDS = [
    "revenue growth",
    "profit margin",
    "capital expenditure",
    "production volumes",
    "market outlook",
    "project news",
    "cash flow",
    "revenue",
    "profit",
    "EBITDA",
    "capex",
    "dividends",
    "production",
    "debt",
    "cash",
    "results",
]


def _extract_fiscal_years(query: str) -> list[str]:
    """Extract fiscal years from the query with a deterministic regex."""
    return [f"FY{year}" for year in re.findall(r"\bFY\s?(20\d{2})\b", query, flags=re.I)]


def _extract_metrics(query: str) -> list[str]:
    """Extract metric keywords that are explicitly present in the query."""
    query_lower = query.lower()
    found = []
    for metric in METRIC_KEYWORDS:
        if metric.lower() in query_lower:
            found.append(metric)
    return found


def _expected_document_rows(expected: dict[str, Any]) -> list[dict[str, Any]]:
    """Build fake retrieved documents for mock mode.

    Mock mode is not meant to prove the real retriever works. It proves the
    evaluator logic and JSONL cases are wired correctly. These synthetic docs
    include the expected company, fiscal year, and metric values so retrieval
    evaluators can pass without external services.
    """
    companies = expected.get("companies") or ["BHP"]
    fiscal_years = expected.get("fiscal_years") or ["FY2024"]
    metrics = expected.get("metrics") or []
    docs = []
    for company in companies:
        for fy in fiscal_years:
            docs.append({
                "company": company,
                "fy": fy,
                "page": 1,
                "section": "Mock annual report section",
                "content": f"{company} {fy} " + " ".join(metrics),
            })
    return docs


# Constructs a synthetic agent output dict that looks like a real successful run,
# allowing evaluators to be tested without calling any LLM or retrieval service.
def build_mock_output(case: dict[str, Any]) -> dict[str, Any]:
    """Return an output shaped like a successful agent result for one case."""
    expected = dict(case["expected"])
    output = dict(expected)

    if expected.get("should_fallback_or_state_missing_data"):
        output["final_answer"] = "Mock fallback: missing or insufficient available data for this question."
    elif expected.get("should_have_citation"):
        output["final_answer"] = "Mock answer supported by annual report data [1].\n\nSources:\n[1] Mock Annual Report"
    else:
        output["final_answer"] = "Mock direct or fallback answer."

    output["documents"] = _expected_document_rows(expected)
    output["retrieval_result"] = {"documents": output["documents"]}

    if expected.get("tool_expected"):
        output["tool_used"] = expected["tool_expected"]

    return output


def _enrich_output_from_query(output: dict[str, Any], query: str) -> dict[str, Any]:
    """Add deterministic query metadata that the current graph may not expose.

    The main graph state tracks route and tool decisions, but it does not expose
    parsed fiscal years or metric keywords as top-level fields. These fields are
    useful for lightweight showcase evals, so the runner derives them from the
    query when the graph output does not provide them.
    """
    output = dict(output)
    output.setdefault("fiscal_years", _extract_fiscal_years(query))
    output.setdefault("metrics", _extract_metrics(query))
    return output


# Runs only the routing-related nodes (retrieve decision, query rewrite)
# instead of the full graph, keeping real-mode routing evals fast and isolated.
def run_real_routing_like_case(case: dict[str, Any]) -> dict[str, Any]:
    """Run the real LLM routing nodes without invoking the full graph."""
    from nodes.retrieve_decision import retrieve_decision_node
    from retrieval_nodes.query_rewrite import query_rewrite_node

    query = case["query"]
    output: dict[str, Any] = {"query": query}

    decision = retrieve_decision_node({"query": query, "messages": []})
    output.update(decision)

    if output.get("needs_retrieval") and not output.get("needs_clarification"):
        rewrite = query_rewrite_node({"query": query, "messages": []})
        output.update({
            "rewritten_query": rewrite.get("rewritten_query", ""),
            "companies": rewrite.get("companies", []),
            "company_queries": rewrite.get("company_queries", []),
        })
    else:
        output.setdefault("needs_calculation", False)

    return _enrich_output_from_query(output, query)


def run_real_retrieval_case(case: dict[str, Any]) -> dict[str, Any]:
    """Run the real retrieval subgraph for one retrieval case.

    This can call external embedding services and local Chroma/BM25 indexes,
    depending on your environment. It is intentionally separate from mock mode
    so you can keep cheap checks and real checks under one CLI.
    """
    from langchain_core.messages import HumanMessage

    from agents.retrieval_agent import retrieval_graph

    query = case["query"]
    result = retrieval_graph.invoke(
        {"query": query, "messages": [HumanMessage(content=query)]},
        config={"configurable": {"thread_id": f"eval-{case['id']}"}},
    )
    output = dict(result or {})
    retrieval_result = output.get("retrieval_result") or {}

    # Normalize retrieved documents to a consistent top-level key regardless
    # of which internal field the graph populated them under.
    if "documents" in retrieval_result:
        output["documents"] = retrieval_result["documents"]
    elif "documents" not in output:
        output["documents"] = output.get("graded_docs") or []
    return _enrich_output_from_query(output, query)


# Routes a real (non-mock) case to the appropriate execution path based on suite type.
def run_real_case(suite_name: str, case: dict[str, Any]) -> dict[str, Any]:
    """Dispatch one real eval case to the cheapest useful real execution path."""
    if suite_name == "retrieval":
        return run_real_retrieval_case(case)
    return run_real_routing_like_case(case)


# Validates the requested suite name and expands "all" to every registered suite.
def selected_suites(name: str) -> list[str]:
    if name == "all":
        return list(SUITES)
    if name not in SUITES:
        raise SystemExit(f"Unknown suite {name!r}. Choose one of: all, {', '.join(SUITES)}")
    return [name]


# Loads and optionally filters cases, then runs each one and prints PASS/FAIL
# per case along with a per-suite score summary.
def run_suite(
    suite_name: str,
    *,
    mode: str,
    limit: int | None,
    ids: set[str] | None,
) -> tuple[int, int]:
    load_cases: Callable[[], list[dict[str, Any]]] = SUITES[suite_name]["load_cases"]
    evaluate: Callable[[dict[str, Any], dict[str, Any]], list[str]] = SUITES[suite_name]["evaluate"]

    cases = load_cases()
    if ids:
        cases = [case for case in cases if case["id"] in ids]
    if limit is not None:
        cases = cases[:limit]

    passed = 0
    total = 0

    print(f"\n== {suite_name.upper()} ({mode}) ==")
    for case in cases:
        total += 1
        try:
            output = build_mock_output(case) if mode == "mock" else run_real_case(suite_name, case)
            failures = evaluate(case, output)
        except Exception as exc:
            failures = [f"runner error: {exc}"]

        if failures:
            print(f"FAIL {case['id']}: {case['query']!r}")
            for failure in failures:
                print(f"  - {failure}")
        else:
            print(f"PASS {case['id']}: {case['query']!r}")
            passed += 1

    print(f"Score: {passed}/{total}")
    return passed, total


# Defines CLI flags: --mode (mock/real), --suite, --limit, and --id filters.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run showcase eval cases.")
    parser.add_argument(
        "--mode",
        choices=["mock", "real"],
        default="mock",
        help="mock validates evaluator wiring cheaply; real calls LLM/retrieval nodes.",
    )
    parser.add_argument(
        "--suite",
        choices=["all", *SUITES.keys()],
        default="all",
        help="Which eval suite to run.",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Run only the first N cases per selected suite.",
    )
    parser.add_argument(
        "--id",
        action="append",
        default=None,
        help="Run a specific case id. Can be passed multiple times.",
    )
    return parser.parse_args()


# Entry point: parses args, runs all selected suites, prints overall score,
# and exits with code 1 if any case failed.
def main() -> None:
    args = parse_args()
    ids = set(args.id) if args.id else None

    total_passed = 0
    total_cases = 0
    for suite_name in selected_suites(args.suite):
        passed, total = run_suite(
            suite_name,
            mode=args.mode,
            limit=args.limit,
            ids=ids,
        )
        total_passed += passed
        total_cases += total

    print(f"\nOverall: {total_passed}/{total_cases}")
    if total_passed != total_cases:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
