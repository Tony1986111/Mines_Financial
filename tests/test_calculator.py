from tools.calculator import (
    calculate,
    calculate_average,
    calculate_growth_rate,
    calculate_ratio,
)


# Verify the generic calculator handles a simple safe arithmetic expression.
def test_calculate_evaluates_basic_arithmetic_expression():
    """The generic calculator should handle plain numeric expressions safely.

    The agent uses this tool for one-off arithmetic that does not fit a
    specialised helper. This test protects the basic AST-based evaluator:
    parentheses, addition, division, and the final formatting.
    """
    # Action: evaluate an expression with parentheses, addition, and division.
    result = calculate.invoke({"expression": "(10 + 5) / 3"})

    # Assertion: the calculator returns the formatted expression and result.
    assert result == "(10 + 5) / 3 = 5"


# Verify unsupported expressions fail instead of being evaluated.
def test_calculate_rejects_non_numeric_or_unsupported_expression():
    """The generic calculator must not evaluate names or arbitrary code.

    This project accepts model-generated tool inputs, so the calculator should
    fail closed when the expression contains variables, function calls, or any
    unsupported Python AST node.
    """
    # Action: pass a variable-based expression that the safe evaluator rejects.
    result = calculate.invoke({"expression": "revenue - costs"})

    # Assertions: the result is an error naming the unsupported AST node.
    assert result.startswith("Error:")
    assert "Unsupported expression node" in result


# Verify growth-rate output includes period changes and a multi-year CAGR.
def test_calculate_growth_rate_formats_period_growth_and_cagr():
    """Growth-rate output should include each period and a CAGR when possible.

    The financial agent needs this for questions such as "How did revenue grow
    from FY2022 to FY2024?". The expected values here are deterministic:
    100 -> 125 is +25.00%, 125 -> 150 is +20.00%, and the 2-year CAGR is +22.47%.
    """
    # Action: calculate growth across three labelled fiscal-year values.
    result = calculate_growth_rate.invoke(
        {
            "values": [100, 125, 150],
            "labels": ["FY2022", "FY2023", "FY2024"],
        }
    )

    # Assertions: each period and the two-year CAGR are formatted correctly.
    assert "FY2022 → FY2023: +25.00%" in result
    assert "FY2023 → FY2024: +20.00%" in result
    assert "CAGR (2-yr): +22.47%" in result


# Verify a zero base period is reported as not available.
def test_calculate_growth_rate_handles_zero_base_period():
    """A zero base period should not crash or produce an infinite growth rate.

    This is a realistic financial edge case: a prior-year value can be zero or
    near zero. The tool should mark that period as N/A and continue with later
    periods where possible.
    """
    # Action: calculate growth where the first base value is zero.
    result = calculate_growth_rate.invoke(
        {
            "values": [0, 50, 100],
            "labels": ["FY2022", "FY2023", "FY2024"],
        }
    )

    # Assertions: the zero-base period is N/A and later growth still works.
    assert "FY2022 → FY2023: N/A (base period is zero)" in result
    assert "FY2023 → FY2024: +100.00%" in result


# Verify growth-rate inputs require the same number of values and labels.
def test_calculate_growth_rate_validates_matching_labels():
    """The values and labels arrays must stay aligned.

    If these arrays have different lengths, the output would be misleading
    because a number could be displayed under the wrong fiscal year.
    """
    # Action: pass two values but only one label.
    result = calculate_growth_rate.invoke(
        {
            "values": [100, 120],
            "labels": ["FY2023"],
        }
    )

    # Assertion: mismatched arrays return the exact validation error.
    assert result == "Error: 'values' and 'labels' must be the same length."


# Verify ratios include both decimal and percentage formats.
def test_calculate_ratio_formats_decimal_and_percentage():
    """Financial ratios should expose both machine-readable and human-readable forms.

    The decimal value is useful for downstream calculations, while the
    percentage is what users usually expect in the final answer.
    """
    # Action: calculate a named ratio from numerator and denominator.
    result = calculate_ratio.invoke(
        {
            "numerator": 25,
            "denominator": 100,
            "ratio_name": "Profit margin",
        }
    )

    # Assertion: the result includes the expected decimal and percentage.
    assert result == "Profit margin = 0.2500  (25.00%)"


# Verify ratio division by zero returns a clear undefined message.
def test_calculate_ratio_handles_zero_denominator():
    """Division by zero should return a clear financial explanation."""
    # Action: calculate a ratio with a zero denominator.
    result = calculate_ratio.invoke(
        {
            "numerator": 25,
            "denominator": 0,
            "ratio_name": "Profit margin",
        }
    )

    # Assertion: the result explains why the ratio is undefined.
    assert result == "Profit margin: undefined (denominator is zero)"


# Verify averages report the full summary statistics used by the agent.
def test_calculate_average_reports_summary_statistics():
    """The average tool should return average, total, min, max, and period count.

    This supports comparison questions where the answer needs a compact summary
    of a metric across several fiscal years.
    """
    # Action: summarize three labelled values.
    result = calculate_average.invoke(
        {
            "values": [10, 20, 30],
            "labels": ["FY2022", "FY2023", "FY2024"],
        }
    )

    # Assertions: average, total, min, max, and period count are present.
    assert "Average : 20" in result
    assert "Total   : 60" in result
    assert "Min     : 10  (FY2022)" in result
    assert "Max     : 30  (FY2024)" in result
    assert "Periods : 3" in result


# Verify an empty value list returns the expected validation error.
def test_calculate_average_validates_empty_input():
    """An empty value series cannot produce a meaningful average."""
    # Action: ask for an average with no values.
    result = calculate_average.invoke({"values": [], "labels": []})

    # Assertion: empty input returns the exact error text.
    assert result == "Error: no values provided."
