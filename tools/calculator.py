from __future__ import annotations
import math
from langchain_core.tools import tool
from simpleeval import simple_eval


@tool
def calculate(expression: str) -> str:
    """Evaluate a plain arithmetic expression: +, -, *, /, **, parentheses.

    Use this for one-off calculations that do not fit the specialised tools:
    subtraction (e.g. Revenue - Costs), multiplication (e.g. currency conversion
    42.3 * 0.648), addition across companies (e.g. 42.3 + 38.1), or any
    intermediate step before calling calculate_ratio / calculate_growth_rate.

    Args:
        expression: A valid arithmetic string, e.g. "55.67 - 38.42" or
                    "(10.5 + 11.2) / 2" or "42.3 * 0.648".
                    Do NOT include variable names or units — numbers only.
    """
    try:
        result = simple_eval(expression.strip())
        return f"{expression} = {result:.6g}"
    except ZeroDivisionError:
        return "Error: division by zero"
    except Exception:
        return f"Error: could not parse '{expression}' — use numbers and operators only."


@tool
def calculate_growth_rate(values: list[float], labels: list[str]) -> str:
    """Calculate period-over-period growth rates and CAGR from a chronological series.

    Args:
        values: Financial values in chronological order, oldest first
                (e.g. [13.4, 12.9, 7.9] for FY2023/24/25 net profit in $B).
        labels: Period labels matching each value (e.g. ["FY2023", "FY2024", "FY2025"]).
    """
    if len(values) < 2:
        return "Error: need at least 2 values to calculate growth rate."
    if len(values) != len(labels):
        return "Error: 'values' and 'labels' must be the same length."

    lines = []
    for i in range(1, len(values)):
        base = values[i - 1]
        if base == 0:
            lines.append(f"{labels[i-1]} → {labels[i]}: N/A (base period is zero)")
            continue
        rate = (values[i] - base) / abs(base) * 100
        sign = "+" if rate >= 0 else ""
        lines.append(f"{labels[i-1]} → {labels[i]}: {sign}{rate:.2f}%")

    if len(values) >= 3 and values[0] != 0 and (values[-1] / values[0]) > 0:
        n = len(values) - 1
        try:
            cagr = (math.pow(values[-1] / values[0], 1.0 / n) - 1) * 100
            sign = "+" if cagr >= 0 else ""
            lines.append(f"CAGR ({n}-yr): {sign}{cagr:.2f}%")
        except (ValueError, ZeroDivisionError):
            pass

    return "\n".join(lines)


@tool
def calculate_ratio(numerator: float, denominator: float, ratio_name: str) -> str:
    """Calculate a financial ratio (e.g. profit margin, ROE, ROA, debt-to-equity).

    Args:
        numerator: Top value (e.g. net profit for profit margin).
        denominator: Bottom value (e.g. revenue for profit margin).
        ratio_name: Descriptive label for the ratio being calculated.
    """
    if denominator == 0:
        return f"{ratio_name}: undefined (denominator is zero)"
    ratio = numerator / denominator
    return f"{ratio_name} = {ratio:.4f}  ({ratio * 100:.2f}%)"


@tool
def calculate_average(values: list[float], labels: list[str]) -> str:
    """Calculate average, total, min, and max for a financial series.

    Args:
        values: List of financial values.
        labels: Period labels matching each value.
    """
    if not values:
        return "Error: no values provided."
    if len(values) != len(labels):
        return "Error: 'values' and 'labels' must be the same length."

    avg = sum(values) / len(values)
    total = sum(values)
    min_val = min(values)
    max_val = max(values)
    min_label = labels[values.index(min_val)]
    max_label = labels[values.index(max_val)]

    return (
        f"Average : {avg:.4g}\n"
        f"Total   : {total:.4g}\n"
        f"Min     : {min_val:.4g}  ({min_label})\n"
        f"Max     : {max_val:.4g}  ({max_label})\n"
        f"Periods : {len(values)}"
    )

