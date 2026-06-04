from utils.chart import extract_chart_data


# Verify extraction returns no chart when there is no input data.
def test_returns_empty_when_no_docs_and_no_text():
    # Confirm empty docs and empty text produce no chart payloads.
    assert extract_chart_data([], "") == []


# Verify a single extracted point is not enough to draw a chart.
def test_single_data_point_is_skipped():
    """One (company, fy, metric) hit is below the >=2 threshold - no chart."""
    # Provide one document with one revenue value.
    doc = {"company": "BHP", "fy": "FY2024", "content": "BHP revenue was A$21.0 billion."}
    # Confirm the chart threshold skips single-point data.
    assert extract_chart_data([doc]) == []


# Verify billion-denominated values are normalized to A$M.
def test_billion_scale_converts_to_millions():
    """A$21.0 billion must be stored as 21000.0 in A$M units."""
    # Provide two A$ revenue values so extraction can build one chart.
    docs = [
        {"company": "BHP", "fy": "FY2024", "content": "BHP revenue was A$21.0 billion."},
        {"company": "RIO", "fy": "FY2024", "content": "RIO revenue was A$18.0 billion."},
    ]
    # Extract chart data from the document content.
    result = extract_chart_data(docs)

    # Confirm one bar chart is produced for A$ revenue.
    assert len(result) == 1
    chart = result[0]
    assert chart["type"] == "bar"
    assert chart["title"] == "Revenue (A$M)"

    # Locate company columns and the FY2024 dataset row.
    bhp_idx = chart["labels"].index("BHP")
    rio_idx = chart["labels"].index("RIO")
    fy_row = next(d for d in chart["datasets"] if d["label"] == "FY2024")

    # Confirm billion values are converted to millions.
    assert fy_row["data"][bhp_idx] == 21000.0
    assert fy_row["data"][rio_idx] == 18000.0


# Verify different currencies are grouped into separate chart payloads.
def test_different_currencies_produce_separate_charts():
    """A$ and US$ figures must not share the same y-axis chart.

    Each currency group needs >=2 total data points to produce a chart,
    so we give BHP two A$ FYs and RIO two US$ FYs.
    """
    # Provide enough A$ and US$ values for each currency group to pass threshold.
    docs = [
        {"company": "BHP", "fy": "FY2023", "content": "BHP revenue was A$19.0 billion."},
        {"company": "BHP", "fy": "FY2024", "content": "BHP revenue was A$21.0 billion."},
        {"company": "RIO", "fy": "FY2023", "content": "RIO revenue was US$16.0 billion."},
        {"company": "RIO", "fy": "FY2024", "content": "RIO revenue was US$18.0 billion."},
    ]
    # Extract charts and collect their display titles.
    result = extract_chart_data(docs)

    # Confirm separate chart titles exist for each currency unit.
    assert len(result) == 2
    titles = {c["title"] for c in result}
    assert "Revenue (A$M)" in titles
    assert "Revenue (US$M)" in titles


# Verify duplicate company/FY/metric values keep the first observed value.
def test_same_company_fy_metric_deduplicated_keeps_first():
    """When the same (company, fy, metric) appears in two chunks, keep the first value."""
    # Provide two conflicting BHP values and one RIO value for the same FY.
    docs = [
        {"company": "BHP", "fy": "FY2024", "content": "BHP revenue was A$21.0 billion."},
        {"company": "BHP", "fy": "FY2024", "content": "BHP revenue was A$99.0 billion."},
        {"company": "RIO", "fy": "FY2024", "content": "RIO revenue was A$18.0 billion."},
    ]
    # Extract chart data after deduplication.
    result = extract_chart_data(docs)

    # Confirm the chart uses the first BHP value rather than the later duplicate.
    assert len(result) == 1
    chart = result[0]
    bhp_idx = chart["labels"].index("BHP")
    fy_row = next(d for d in chart["datasets"] if d["label"] == "FY2024")
    assert fy_row["data"][bhp_idx] == 21000.0


# Verify missing company/FY values are represented as None.
def test_missing_fy_values_filled_with_none():
    """When a company has no data for a given FY, its slot in the dataset is None."""
    # Provide BHP values for two years and RIO for only FY2024.
    docs = [
        {"company": "BHP", "fy": "FY2023", "content": "BHP revenue was A$19.0 billion."},
        {"company": "BHP", "fy": "FY2024", "content": "BHP revenue was A$21.0 billion."},
        {"company": "RIO", "fy": "FY2024", "content": "RIO revenue was A$18.0 billion."},
    ]
    # Extract the chart and find RIO's column in the FY2023 row.
    result = extract_chart_data(docs)

    # Confirm RIO's missing FY2023 value is explicitly None.
    assert len(result) == 1
    chart = result[0]
    rio_idx = chart["labels"].index("RIO")
    fy2023_row = next(d for d in chart["datasets"] if d["label"] == "FY2023")
    assert fy2023_row["data"][rio_idx] is None


# Verify synthesized answer text can produce chart data without docs.
def test_extracts_company_fy_metric_value_from_synthesised_prose():
    """Text-mode extraction must find company, FY, metric, and value from plain prose."""
    # Provide prose that mentions company, FY, metric, currency, and value.
    text = (
        "BHP reported FY2024 revenue of A$21.0 billion. "
        "RIO also reported FY2024 revenue of A$18.0 billion."
    )
    # Extract chart data from text-only input.
    result = extract_chart_data([], text=text)

    # Confirm both companies appear in the generated A$ revenue chart.
    assert len(result) == 1
    chart = result[0]
    assert "BHP" in chart["labels"]
    assert "RIO" in chart["labels"]
    assert chart["title"] == "Revenue (A$M)"
