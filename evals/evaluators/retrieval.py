from __future__ import annotations

from pathlib import Path
from typing import Any

from common import (
    CASES_DIR,
    load_jsonl,
    missing_expected_values,
    print_validation_result,
    require_bool_field,
    require_case_fields,
    require_expected_fields,
    require_list_field,
)


# Path to the JSONL file that holds retrieval eval cases, and the canonical type label.
CASE_FILE = CASES_DIR / "retrieval.jsonl"
CASE_TYPE = "retrieval"


def validate_case(case: dict[str, Any]) -> None:
    """Validate one retrieval case.

    Retrieval cases focus on whether retrieved documents contain the expected
    company, fiscal year, and financial metric evidence.
    """
    require_case_fields(case, CASE_TYPE)
    require_expected_fields(case, ["companies", "fiscal_years", "metrics", "top_k"])
    # Ensure companies, fiscal_years, and metrics are lists, not scalars.
    for field in ["companies", "fiscal_years", "metrics"]:
        require_list_field(case, field)
    # Ensure all boolean retrieval-intent flags are actually booleans.
    for field in [
        "should_contain_company",
        "should_contain_all_companies",
        "should_contain_fy",
        "should_contain_multiple_fys",
        "should_have_citation",
    ]:
        require_bool_field(case, field)

    # top_k controls how many retrieved docs to evaluate; must be a positive integer.
    top_k = case["expected"]["top_k"]
    if not isinstance(top_k, int) or top_k <= 0:
        raise ValueError(f"{case['id']}: expected.top_k must be a positive integer")


# Normalizes different output shapes from the retrieval pipeline into a flat list of docs.
def _documents_from_output(output: dict[str, Any]) -> list[dict[str, Any]]:
    """Extract document dictionaries from several likely output shapes."""
    if "documents" in output:
        return output.get("documents") or []
    retrieval_result = output.get("retrieval_result") or {}
    if "documents" in retrieval_result:
        return retrieval_result.get("documents") or []
    return output.get("retrieved_docs") or output.get("graded_docs") or []


def evaluate_retrieval_output(case: dict[str, Any], output: dict[str, Any]) -> list[str]:
    """Compare a retrieval case against retrieved document metadata/content."""
    expected = case["expected"]
    docs = _documents_from_output(output)
    # Respect the top_k limit so we only judge the documents the system surfaced.
    top_k = expected.get("top_k", len(docs))
    docs = docs[:top_k]

    failures: list[str] = []
    # Collect per-doc metadata fields for structured checks.
    companies = [doc.get("company") for doc in docs]
    fys = [doc.get("fy") for doc in docs]
    # Concatenate all document text into one string for keyword presence checks.
    joined_text = " ".join(
        str(doc.get("content") or doc.get("text") or doc.get("page_content") or "")
        for doc in docs
    ).lower()

    # Check company coverage: either all expected companies or just the primary one.
    if expected.get("should_contain_all_companies"):
        missing = missing_expected_values(expected.get("companies", []), companies)
        if missing:
            failures.append(f"documents: missing companies {missing!r}; actual={companies!r}")
    elif expected.get("should_contain_company"):
        missing = missing_expected_values(expected.get("companies", [])[:1], companies)
        if missing:
            failures.append(f"documents: missing company {missing!r}; actual={companies!r}")

    # Check fiscal-year coverage: either multiple FYs or just the primary one.
    if expected.get("should_contain_multiple_fys"):
        missing = missing_expected_values(expected.get("fiscal_years", []), fys)
        if missing:
            failures.append(f"documents: missing fiscal years {missing!r}; actual={fys!r}")
    elif expected.get("should_contain_fy"):
        missing = missing_expected_values(expected.get("fiscal_years", [])[:1], fys)
        if missing:
            failures.append(f"documents: missing fiscal year {missing!r}; actual={fys!r}")

    # Verify that each expected financial metric keyword appears in the retrieved text.
    for metric in expected.get("metrics", []):
        if str(metric).lower() not in joined_text:
            failures.append(f"documents: metric text not found in top_k content: {metric!r}")

    return failures


# Load and validate all retrieval cases from the JSONL file.
def load_cases(path: Path = CASE_FILE) -> list[dict[str, Any]]:
    cases = load_jsonl(path)
    for case in cases:
        validate_case(case)
    return cases


# Entry point: load cases and print a human-readable validation summary.
def main() -> None:
    cases = load_cases()
    print_validation_result(CASE_FILE, cases)


if __name__ == "__main__":
    main()
