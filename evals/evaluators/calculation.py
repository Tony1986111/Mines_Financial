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


# Path to the JSONL file holding calculation test cases, and the string tag for this case type.
CASE_FILE = CASES_DIR / "calculation.jsonl"
CASE_TYPE = "calculation"


# Exhaustive set of calculator tool names the agent is permitted to select.
# Any expected tool outside this set is treated as a misconfigured test case.
ALLOWED_TOOLS = {
    "calculate",
    "calculate_growth_rate",
    "calculate_ratio",
    "calculate_average",
}


def validate_case(case: dict[str, Any]) -> None:
    """Validate one calculation case.

    Calculation cases test whether the agent recognises arithmetic needs and
    routes toward the correct calculator tool after retrieval.
    """
    require_case_fields(case, CASE_TYPE)
    require_expected_fields(
        case,
        [
            "selected_agents",
            "needs_calculation",
            "calculation_type",
            "companies",
            "fiscal_years",
            "metrics",
            "tool_expected",
            "should_have_citation",
        ],
    )
    require_bool_field(case, "needs_calculation")
    require_bool_field(case, "should_have_citation")
    for field in ["selected_agents", "companies", "fiscal_years", "metrics"]:
        require_list_field(case, field)

    # Reject cases that name an unknown tool or forget to set needs_calculation=true.
    tool = case["expected"]["tool_expected"]
    if tool not in ALLOWED_TOOLS:
        raise ValueError(f"{case['id']}: unsupported expected tool {tool!r}")
    if case["expected"]["needs_calculation"] is not True:
        raise ValueError(f"{case['id']}: calculation cases should set needs_calculation=true")


def evaluate_calculation_output(case: dict[str, Any], output: dict[str, Any]) -> list[str]:
    """Compare a calculation case against an actual graph/tool output."""
    expected = case["expected"]
    failures: list[str] = []

    failures.extend(check_bool("needs_calculation", expected, output))
    failures.extend(check_list_contains("selected_agents", expected, output))
    failures.extend(check_list_contains("companies", expected, output))
    failures.extend(check_list_contains("fiscal_years", expected, output))
    failures.extend(check_list_contains("metrics", expected, output))

    # Accept either the live "tool_used" field or the echoed "tool_expected" field as evidence
    # of which tool the agent picked, then compare against the expected value.
    actual_tool = output.get("tool_used") or output.get("tool_expected")
    if actual_tool and actual_tool != expected["tool_expected"]:
        failures.append(f"tool_used: expected {expected['tool_expected']!r}, got {actual_tool!r}")

    # If the output contains a calculation result, it must be non-empty (whitespace doesn't count).
    calc_result = output.get("calc_result")
    if calc_result is not None and not str(calc_result).strip():
        failures.append("calc_result: expected non-empty calculation result")

    return failures


# Load all calculation test cases from disk and validate every one before returning them.
def load_cases(path: Path = CASE_FILE) -> list[dict[str, Any]]:
    cases = load_jsonl(path)
    for case in cases:
        validate_case(case)
    return cases


# CLI entry point: load and validate cases, then print a summary to stdout.
def main() -> None:
    cases = load_cases()
    print_validation_result(CASE_FILE, cases)


if __name__ == "__main__":
    main()
