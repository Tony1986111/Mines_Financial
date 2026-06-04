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

# Path to the JSONL file holding routing eval test cases, and the
# string tag that identifies this evaluator's case type.
CASE_FILE = CASES_DIR / "routing.jsonl"
CASE_TYPE = "routing"


def validate_case(case: dict[str, Any]) -> None:
    """Validate one routing case.

    Routing cases test the supervisor decision fields used by
    `retrieve_decision_node` and `dynamic_tool_selector_node`.
    """
    require_case_fields(case, CASE_TYPE)
    require_expected_fields(
        case,
        [
            "needs_retrieval",
            "needs_clarification",
            "selected_agents",
            "needs_calculation",
            "should_have_citation",
        ],
    )
    # Ensure every boolean decision flag is actually a bool, not a string or None.
    for field in [
        "needs_retrieval",
        "needs_clarification",
        "needs_calculation",
        "should_have_citation",
    ]:
        require_bool_field(case, field)
    # Ensure entity/metric fields are lists so membership checks work correctly.
    for field in ["selected_agents", "companies", "fiscal_years", "metrics"]:
        require_list_field(case, field)


def evaluate_routing_output(case: dict[str, Any], output: dict[str, Any]) -> list[str]:
    """Compare a routing case against an actual agent state/output.

    The returned list is empty when the output passes. Each string in the list
    explains one mismatch. A future `run_eval.py` script can call this after it
    invokes the graph or individual routing nodes.
    """
    expected = case["expected"]
    failures: list[str] = []

    # Check each boolean routing decision against the expected value.
    for field in ["needs_retrieval", "needs_clarification", "needs_calculation"]:
        failures.extend(check_bool(field, expected, output))

    # Verify that all expected list items (agents, entities, dates, metrics)
    # are present in the actual output — order-independent subset check.
    failures.extend(check_list_contains("selected_agents", expected, output))
    failures.extend(check_list_contains("companies", expected, output))
    failures.extend(check_list_contains("fiscal_years", expected, output))
    failures.extend(check_list_contains("metrics", expected, output))

    return failures


# Load and validate all routing cases from disk, raising early if any case is malformed.
def load_cases(path: Path = CASE_FILE) -> list[dict[str, Any]]:
    cases = load_jsonl(path)
    for case in cases:
        validate_case(case)
    return cases


# Entry point: load cases and print a human-readable validation summary to stdout.
def main() -> None:
    cases = load_cases()
    print_validation_result(CASE_FILE, cases)


if __name__ == "__main__":
    main()
