from __future__ import annotations

from pathlib import Path
from typing import Any

from common import (
    CASES_DIR,
    check_bool,
    check_list_contains,
    load_jsonl,
    print_validation_result,
    require_bool_field,
    require_case_fields,
    require_expected_fields,
    require_list_field,
)


# Path to the JSONL file holding all boundary test cases, and the label used
# to identify this evaluator's case type throughout the eval framework.
CASE_FILE = CASES_DIR / "boundary.jsonl"
CASE_TYPE = "boundary"


def validate_case(case: dict[str, Any]) -> None:
    """Validate one boundary case.

    Boundary cases describe important failure modes: empty input, vague input,
    unsupported companies, prompt injection, unsupported fiscal years, and
    no-context fallback behaviour.
    """
    # Confirm the case has the mandatory top-level fields and the required expected keys.
    require_case_fields(case, CASE_TYPE)
    require_expected_fields(
        case,
        [
            "needs_retrieval",
            "needs_clarification",
            "needs_calculation",
            "should_have_citation",
        ],
    )
    # Assert every flag field is a boolean so comparisons behave predictably.
    for field in [
        "needs_retrieval",
        "needs_clarification",
        "needs_calculation",
        "should_have_citation",
        "guardrails_passed",
        "should_ignore_instruction_override",
        "should_fallback_or_state_missing_data",
    ]:
        require_bool_field(case, field)
    # Assert every collection field is a list (may be empty) to prevent type errors during eval.
    for field in [
        "companies",
        "fiscal_years",
        "metrics",
        "supported_companies_only",
        "known_supported_fiscal_years",
    ]:
        require_list_field(case, field)


def evaluate_boundary_output(case: dict[str, Any], output: dict[str, Any]) -> list[str]:
    """Compare a boundary case against actual graph/node output."""
    expected = case["expected"]
    failures: list[str] = []

    # Check that each boolean routing flag in the output matches what the case expects.
    for field in [
        "needs_retrieval",
        "needs_clarification",
        "needs_calculation",
        "guardrails_passed",
    ]:
        failures.extend(check_bool(field, expected, output))

    # Verify that the output lists contain at least the items declared in the expected lists.
    failures.extend(check_list_contains("companies", expected, output))
    failures.extend(check_list_contains("fiscal_years", expected, output))
    failures.extend(check_list_contains("metrics", expected, output))

    # When the case requires a citation, ensure the answer contains a reference marker or Sources section.
    if expected.get("should_have_citation"):
        answer = output.get("final_answer") or output.get("answer") or ""
        if "[1]" not in answer and "Sources:" not in answer:
            failures.append("final_answer: expected citation marker or Sources section")

    # When the case expects graceful degradation, ensure the answer signals missing or unavailable data.
    if expected.get("should_fallback_or_state_missing_data"):
        answer = (output.get("final_answer") or output.get("answer") or "").lower()
        fallback_signals = ["not found", "insufficient", "missing", "could not", "available data"]
        if answer and not any(signal in answer for signal in fallback_signals):
            failures.append("final_answer: expected fallback/missing-data wording")

    return failures


# Load and validate all boundary cases from the JSONL file,
# raising an error early if any case is malformed.
def load_cases(path: Path = CASE_FILE) -> list[dict[str, Any]]:
    cases = load_jsonl(path)
    for case in cases:
        validate_case(case)
    return cases


# Entry point: load cases and print a summary of validation results to stdout.
def main() -> None:
    cases = load_cases()
    print_validation_result(CASE_FILE, cases)


if __name__ == "__main__":
    main()
