from __future__ import annotations

import re
from collections import defaultdict

from state import ChartData, ChartDataset, RetrievedDoc

# ─── Metric classification ────────────────────────────────────────────────────

# Maps a display name to the keywords we look for in the surrounding text.
# Keep keywords lowercase; matching is done on lowercased content.
_METRICS: dict[str, list[str]] = {
    "Revenue": ["revenue", "sales", "turnover"],
    "Net Profit": ["net profit", "profit after tax", "npat", "net income"],
    "EBITDA": ["ebitda", "earnings before interest"],
    "Capex": ["capital expenditure", "capex"],
    "Operating Cash Flow": ["operating cash flow", "cash from operations"],
}

# ─── Number extraction ────────────────────────────────────────────────────────

# Matches currency-prefixed financial figures with a scale suffix.
# Examples that match:
#   A$21.0 billion   US$12,345 million   $4.5B   A$3.2bn   USD 17,800M
# Requires a currency prefix to avoid matching arbitrary numbers like "page 5M".
# Group 1: currency prefix, Group 2: number, Group 3: scale suffix.
_VALUE_RE = re.compile(
    r'(A\$|US\$|USD|AUD|\$)\s*([\d,]+(?:\.\d+)?)\s*'
    r'(billion|million|bn|mn|[BbMm])\b',
)

# Normalise currency prefixes to a canonical display symbol.
_CURRENCY_DISPLAY: dict[str, str] = {
    "A$": "A$",
    "AUD": "A$",
    "$": "A$",   # bare $ in ASX reports defaults to AUD
    "US$": "US$",
    "USD": "US$",
}

# Normalise every matched value to A$M so all charts share the same y-axis unit.
_TO_MILLIONS: dict[str, float] = {
    "billion": 1_000.0,
    "bn": 1_000.0,
    "b": 1_000.0,
    "million": 1.0,
    "mn": 1.0,
    "m": 1.0,
}

# How many characters before the dollar figure to scan for a metric keyword.
_CONTEXT_WINDOW = 200   # widened: synthesised prose can be longer than raw chunks

# ─── Company / FY detection (for text-based extraction) ──────────────────────

_FY_RE = re.compile(r'\bFY(20\d{2})\b', re.IGNORECASE)

# Each ticker mapped to the patterns that identify it in prose.
_COMPANY_PATTERNS: dict[str, re.Pattern[str]] = {
    "BHP": re.compile(r'\bBHP\b'),
    "RIO": re.compile(r'\b(?:RIO|Rio Tinto)\b', re.IGNORECASE),
    "FMG": re.compile(r'\b(?:FMG|Fortescue)\b', re.IGNORECASE),
    "MIN": re.compile(r'\b(?:MIN|Mineral Resources)\b', re.IGNORECASE),
    "NST": re.compile(r'\b(?:NST|Northern Star)\b', re.IGNORECASE),
}

# How many characters around a match to scan for company / FY labels.
_TEXT_WINDOW = 400


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _to_millions(raw: float, scale: str) -> float:
    return raw * _TO_MILLIONS.get(scale.lower(), 1.0)


def _classify_metric(window: str) -> str | None:
    """Return the first matching metric name for the text window, or None."""
    lower = window.lower()
    for metric, keywords in _METRICS.items():
        if any(kw in lower for kw in keywords):
            return metric
    return None


def _extract_from_doc(doc: RetrievedDoc) -> list[tuple[str, str, str, float, str]]:
    """Return (company, fy, metric, value_millions, currency) tuples found in one doc."""
    content = doc.get("content", "")
    company = doc.get("company", "")
    fy = doc.get("fy", "")

    if not (content and company and fy):
        return []

    hits: list[tuple[str, str, str, float, str]] = []
    for match in _VALUE_RE.finditer(content):
        start = max(0, match.start() - _CONTEXT_WINDOW)
        window = content[start : match.end()]

        metric = _classify_metric(window)
        if metric is None:
            continue

        currency = _CURRENCY_DISPLAY.get(match.group(1), match.group(1))
        raw = float(match.group(2).replace(",", ""))
        scale = match.group(3)
        hits.append((company, fy, metric, round(_to_millions(raw, scale), 1), currency))

    return hits


def _extract_from_text(text: str) -> list[tuple[str, str, str, float, str]]:
    """Extract (company, fy, metric, value_millions, currency) from synthesised prose."""
    hits: list[tuple[str, str, str, float, str]] = []

    for match in _VALUE_RE.finditer(text):
        before = text[max(0, match.start() - _TEXT_WINDOW): match.start()]

        metric = _classify_metric(before)
        if metric is None:
            continue

        fy_matches = list(_FY_RE.finditer(before))
        if not fy_matches:
            continue
        fy = f"FY{fy_matches[-1].group(1)}"

        company: str | None = None
        best_pos = -1
        for ticker, pattern in _COMPANY_PATTERNS.items():
            for m in pattern.finditer(before):
                if m.start() > best_pos:
                    best_pos = m.start()
                    company = ticker
        if company is None:
            continue

        currency = _CURRENCY_DISPLAY.get(match.group(1), match.group(1))
        raw = float(match.group(2).replace(",", ""))
        scale = match.group(3)
        hits.append((company, fy, metric, round(_to_millions(raw, scale), 1), currency))

    return hits


# ─── Public API ───────────────────────────────────────────────────────────────

def extract_chart_data(docs: list[RetrievedDoc], text: str = "") -> list[ChartData]:
    """Extract Chart.js-compatible chart specs from graded financial documents.

    Called by answer_node with the list of graded docs from retrieval_result.

    How it works:
      1. Scan each doc's content for currency figures near metric keywords.
      2. Deduplicate across chunks (same figure often appears in multiple
         chunks of the same document — keep first hit per company/FY/metric).
      3. Group by metric and build one bar chart per metric.
      4. Return [] when no structured numeric data is found, so answer_node
         can safely skip the chart step.

    Output format per chart (Chart.js bar chart):
      {
        "type":     "bar",
        "title":    "Revenue (A$M)",
        "labels":   ["BHP", "FMG", "RIO"],      # x-axis: companies
        "datasets": [
          {"label": "FY2023", "data": [45000.0, 17200.0, None]},
          {"label": "FY2024", "data": [53600.0, 17800.0, 54200.0]},
        ]
      }
    None means no data was found for that company/FY combination.
    """
    if not docs and not text:
        return []

    # Deduplicate: keep the first hit per (company, fy, metric).
    # Value stored as (amount, currency) — currency from the source document.
    # Text-based extraction runs first (cleaner source); raw doc extraction
    # fills in anything the text scan missed.
    first_hit: dict[tuple[str, str, str], tuple[float, str]] = {}

    for company, fy, metric, value, currency in _extract_from_text(text):
        key = (company, fy, metric)
        if key not in first_hit:
            first_hit[key] = (value, currency)

    for doc in docs:
        for company, fy, metric, value, currency in _extract_from_doc(doc):
            key = (company, fy, metric)
            if key not in first_hit:
                first_hit[key] = (value, currency)

    if not first_hit:
        return []

    # Group: (metric, currency) → company → fy → value.
    # Different currencies produce separate charts so y-axes are never mixed.
    by_metric_currency: dict[tuple[str, str], dict[str, dict[str, float]]] = defaultdict(
        lambda: defaultdict(dict)
    )
    for (company, fy, metric), (value, currency) in first_hit.items():
        by_metric_currency[(metric, currency)][company][fy] = value

    charts: list[ChartData] = []
    for (metric, currency), company_map in sorted(by_metric_currency.items()):
        total_points = sum(len(fy_map) for fy_map in company_map.values())
        if total_points < 2:
            continue

        companies = sorted(company_map.keys())
        all_fys = sorted({fy for fy_map in company_map.values() for fy in fy_map})

        datasets: list[ChartDataset] = []
        for fy in all_fys:
            row = [company_map[c].get(fy) for c in companies]
            if any(v is not None for v in row):
                datasets.append({"label": fy, "data": row})

        if datasets:
            charts.append({
                "type": "bar",
                "title": f"{metric} ({currency}M)",
                "labels": companies,
                "datasets": datasets,
            })

    return charts
