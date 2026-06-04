from __future__ import annotations

# Standard-library imports used for JSON parsing and filesystem paths.
import json
from pathlib import Path
from typing import Any


# Resolve project root (two levels above this file) and derive the canonical
# directory where all eval case JSONL files are stored.
ROOT = Path(__file__).resolve().parents[2]
CASES_DIR = ROOT / "evals" / "cases"


class CaseValidationError(ValueError):
    """Raised when an eval case is malformed.

    These evaluators are intentionally lightweight. They first verify that the
    JSONL files are shaped correctly, then provide helper functions that can be
    reused by a future `evals/run_eval.py` script once real agent outputs are
    available.
    """


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    """Load a JSONL file and attach line numbers for better error messages."""
    rows: list[dict[str, Any]] = []
    for line_no, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        # Skip blank / whitespace-only lines that are common in JSONL files.
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except json.JSONDecodeError as exc:
            raise CaseValidationError(f"{path}:{line_no}: invalid JSON: {exc}") from exc
        # Attach the 1-based line number so downstream error messages can pinpoint the bad case.
        row["_line_no"] = line_no
        rows.append(row)
    return rows


def require_case_fields(case: dict[str, Any], case_type: str) -> None:
    """Validate fields shared by every eval case."""
    # First pass: ensure all mandatory top-level keys are present before
    # inspecting their values, so error messages are maximally informative.
    required = ["id", "type", "query", "expected", "why_it_matters"]
    for field in required:
        if field not in case:
            raise CaseValidationError(f"{case.get('id', '<missing id>')}: missing '{field}'")

    # Second pass: validate the type tag and the shape of key fields.
    if case["type"] != case_type:
        raise CaseValidationError(
            f"{case['id']}: expected type '{case_type}', got '{case['type']}'"
        )
    if not isinstance(case["expected"], dict):
        raise CaseValidationError(f"{case['id']}: 'expected' must be an object")
    if not isinstance(case["why_it_matters"], str) or not case["why_it_matters"].strip():
        raise CaseValidationError(f"{case['id']}: 'why_it_matters' must be a non-empty string")


def require_expected_fields(case: dict[str, Any], fields: list[str]) -> None:
    """Validate required keys inside the `expected` object."""
    expected = case["expected"]
    for field in fields:
        if field not in expected:
            raise CaseValidationError(f"{case['id']}: expected missing '{field}'")


def require_list_field(case: dict[str, Any], field: str) -> None:
    """Validate that expected[field] is a list when present."""
    expected = case["expected"]
    if field in expected and not isinstance(expected[field], list):
        raise CaseValidationError(f"{case['id']}: expected.{field} must be a list")


def require_bool_field(case: dict[str, Any], field: str) -> None:
    """Validate that expected[field] is a bool when present."""
    expected = case["expected"]
    if field in expected and not isinstance(expected[field], bool):
        raise CaseValidationError(f"{case['id']}: expected.{field} must be a boolean")


def missing_expected_values(expected_values: list[Any], actual_values: list[Any]) -> list[Any]:
    """Return expected values that are not present in actual_values."""
    # Normalise to uppercase strings for case-insensitive membership testing
    # (e.g. ticker "aapl" should match "AAPL").
    actual_set = {str(value).upper() for value in actual_values}
    return [value for value in expected_values if str(value).upper() not in actual_set]


def check_bool(name: str, expected: dict[str, Any], output: dict[str, Any]) -> list[str]:
    """Compare a boolean field when the case defines it."""
    if name not in expected:
        return []
    if output.get(name) != expected[name]:
        return [f"{name}: expected {expected[name]!r}, got {output.get(name)!r}"]
    return []


def check_list_contains(
    name: str,
    expected: dict[str, Any],
    output: dict[str, Any],
    output_name: str | None = None,
) -> list[str]:
    """Check that output list contains all values from expected list."""
    if name not in expected:
        return []
    actual_name = output_name or name
    actual = output.get(actual_name) or []
    missing = missing_expected_values(expected[name], actual)
    if missing:
        return [f"{actual_name}: missing {missing!r}; actual={actual!r}"]
    return []


def print_validation_result(path: Path, cases: list[dict[str, Any]]) -> None:
    """Print a small CLI-friendly summary for standalone evaluator scripts."""
    print(f"Validated {len(cases)} cases from {path}")
    for case in cases:
        print(f"PASS {case['id']}: {case['query']!r}")
