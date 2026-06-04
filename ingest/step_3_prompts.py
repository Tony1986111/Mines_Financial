"""Prompts and few-shot examples for step_3_ingest_vision.py."""

import base64
import json
from pathlib import Path

_SYSTEM = (
    "You are a financial table extractor for ASX mining company annual reports. "
    "Extract every table and data figure visible on the page into structured JSON. "
    "Be precise—copy values exactly as shown, do not infer or estimate. "
    "CRITICAL: The '=' sign is NEVER a cell separator under any circumstances. "
    "Text on both sides of '=' belongs in the same cell value (e.g. '• Threshold rTSR = 50th percentile = 50% vest' is one cell)."
)

_USER_TMPL = """\
    This is page {page_num} from {source}.

    Extract ALL tables and data figures (including bar charts and stacked charts with a color Key or Legend) on this page.
    Return a JSON array. Each element represents one table/figure using the schema below.

    IMPORTANT: Preserve the table structure, not only the text content. First identify the table hierarchy
    and layout structure, including title, parent headers, child headers, merged cells, row/column spans,
    and cells split into nested sub-rows. Only after the structure is identified, fill each cell's content
    value. If a cell's content cannot be determined from the image, output null for that cell value. Do not
    guess, infer, copy, or repeat uncertain values.

    ━━━ OUTPUT SCHEMA ━━━

    Table object:
    {{
    "title": "string",
    "headers": [ <Row>, ... ],
    "rows":    [ <Row>, ... ]
    }}

    <Row> = {{ "cells": [ <Cell>, ... ] }}

    <Cell> — pick EXACTLY ONE form:
    Leaf cell   : {{ "value": "string|null", "col_span": N }}
    Nested cell : {{ "col_span": N, "sub_rows": [ <SubRow>, ... ] }}

    Use a NESTED cell when:
        • a single visual cell is divided vertically into 2+ sub-rows, OR
        • adjacent columns are merged (col_span > 1) AND the merged area is
        itself divided into sub-rows.
    "col_span" defaults to 1 — omit it when it equals 1.

    <SubRow> = {{ "cells": [ <SubCell>, ... ] }}

    <SubCell> — pick EXACTLY ONE form:
    Leaf sub-cell   : {{ "value": "string|null", "col_span": N }}
    Nested sub-cell : {{ "col_span": N, "sub_rows": [ <LeafRow>, ... ] }}

    <LeafRow> = {{ "cells": [ <LeafCell>, ... ] }}

    <LeafCell> = {{ "value": "string|null", "col_span": N }}
    ← MAXIMUM DEPTH. Never add sub_rows inside a LeafCell.

    ━━━ STRUCTURE EXAMPLE (all values are generic placeholders — never reproduce them) ━━━

    JSON representation:
    [
    {{
        "title": "[Table title]",
        "headers": [
        {{"cells": [{{"value":"[Header A]"}},{{"value":"[Header B]"}},{{"value":"[Header C]"}},{{"value":"[Header D]"}},{{"value":"[Header E]"}},{{"value":"[Header F]"}}]}}
        ],
        "rows": [
        {{
            "cells": [
            {{"value": "[Row group A]"}},
            {{"value": "[Measure description A]"}},
            {{
                "sub_rows": [
                {{"cells": [{{"value":"[Metric bullet 1]"}},{{"value":"[Result 1]"}}]}},
                {{"cells": [{{"value":"[Metric bullet 2]"}},{{"value":"[Result 2]"}}]}},
                {{"cells": [{{"value":"[Condition note]","col_span":2}}]}}
                ]
            }},
            {{"value": "N%"}},
            {{"value": "Nth [unit]"}},
            {{"value": "N.N%"}}
            ]
        }},
        {{
            "cells": [
            {{"value": "[Row group B]"}},
            {{"value": "[Measure description B]"}},
            {{
                "sub_rows": [
                {{"cells": [{{"value":"[Metric bullet 1]"}},{{"value":"[Result 1]"}}]}},
                {{"cells": [{{"value":"[Metric bullet 2]"}},{{"value":"[Result 2]"}}]}}
                ]
            }},
            {{"value": "N%"}},
            {{
                "sub_rows": [
                {{"cells": [{{"value":"[Sub-value A]"}}]}},
                {{"cells": [{{"value":"[Sub-value B]"}}]}}
                ]
            }},
            {{"value": "N%"}}
            ]
        }},
        {{
            "cells": [
            {{"value": "[Group label]", "row_span": 2}},
            {{"value": "[Condition text A]", "col_span": 3}},
            {{"value": "[Result A]", "col_span": 2}}
            ]
        }},
        {{
            "cells": [
            {{"value": "[Condition text B]", "col_span": 3}},
            {{"value": "[Result B]", "col_span": 2}}
            ]
        }},
        {{
            "cells": [
            {{"value": "[Total label]"}}, {{"value": ""}}, {{"value": ""}},
            {{"value": "NN%"}}, {{"value": ""}}, {{"value": "NN.N%"}}
            ]
        }}
        ]
    }}
    ]

    ━━━ CRITICAL RULES ━━━

    1. TWO-PASS EXTRACTION: For complex tables, do NOT solve structure and values in one mental pass.
    • Pass 1 — restore structure only: identify row/column layout, merged cells, parent/child header
        hierarchy, row_span/col_span, and nested/split cells.
    • Pass 2 — fill values: using the structure from Pass 1, read and place each cell value exactly in
        its corresponding cell.
    This is required to reduce column misalignment and value drift.

    2. STRUCTURE RESTORATION ORDER: When processing table structure, follow these three steps:
    • First give the overall large nesting hierarchy of the table.
    • Then identify cells that are subdivided or visually cut into smaller cells/sub-rows.
    • Then identify cells that are merged across rows or columns.

    3. COLUMN COMPLETENESS: Count columns before extracting. Extract ALL column groups — do not stop at the middle column.

    4. VISUAL ENCODING LABELS — integrate into column headers, do not extract separately:
    • Scan the ENTIRE page for any visual mapping that links colors, patterns, or shading to text labels.
        This mapping may be labeled "Key", "Legend", "Note", or have NO label at all (e.g. colored swatches
        followed by words, or a color band with a caption).
    • Once found, determine WHICH data columns in the chart/table each label corresponds to, based on
        the visual left-to-right order of the color segments (e.g. first color segment = first label).
    • Use those labels as the column header values for those data columns in your extracted table.
    • Do NOT output the Key/Legend as a separate standalone table — fold it into the headers.
    Example: a stacked bar chart with colors [dark, teal, green, purple] and Key "FAR STI LTI CRR"
    → headers should include cells with values "FAR", "STI", "LTI", "CRR" (in that order).

    5. NO DATA INFERENCE — STRICT:
    • Extract ONLY what is literally printed in the source. Never infer, copy, repeat, or guess values
        for cells that are visually blank/empty in the original.
    • A cell that appears empty in the source MUST be output as "" — even if a logically "obvious"
        value exists nearby (e.g. a merged label from an adjacent row, or a repeated name).
    • A cell whose printed content exists but cannot be confidently read MUST be output as null.
    • This rule overrides any instinct to "fill in" missing context. Empty means "".

    6. FOOTNOTE MARKERS: Strip superscript footnote numbers from values ("2.9¹³¹" → "2.9", "CO₂¹³⁸" → "CO₂").

    7. MATHEMATICAL SYMBOLS: Preserve =, >, <, ≥, ≤, % exactly. The "=" inside metric bullet descriptions is data, not a separator.

    8. NO EXTRA DEPTH: Never add sub_rows inside a LeafCell.

    9. ONE ARRAY ONLY: Output exactly ONE JSON array containing ALL tables from the page.
    Even if the page has 10 tables, they all go into a single [...] array.
    NEVER output multiple separate arrays. NEVER output a bare object {{...}}.
    The response must start with "[" and end with "]".

    10. BLANK HEADER LABELS: When a column has no visible header text (e.g. the leftmost
    "row description" column whose header area is visually empty), you MUST still include
    that cell in the headers row. Output it as {{"value": "none"}}.
    NEVER skip or omit header cells, even if their area is blank in the image.
    Count the number of data columns first; the header row MUST have the same count.

    11. NO-TABLE PAGES: If the page contains no tables or data figures
    (e.g. a portrait photo, a blank page, a full-page illustration with no numeric data),
    return an empty JSON array: []. Do NOT fabricate or borrow values from the examples.

    Output ONLY valid JSON. No markdown fences, no explanations.
    """

# ── Few-shot example (Table 9 screenshot + hand-verified JSON output) ─────────
_FEW_SHOT_PATH = Path("ingest/fewshot.png")
_FEW_SHOT_B64: str | None = (
    base64.b64encode(_FEW_SHOT_PATH.read_bytes()).decode()
    if _FEW_SHOT_PATH.exists() else None
)

_FEW_SHOT_PROMPT = (
    "[STRUCTURAL EXAMPLE — all values shown are fictitious placeholders. "
    "Never reproduce them. Learn the JSON format and nesting structure only.]\n"
    "Extract all tables from this page following the schema above."
)

_FEW_SHOT_ANSWER = json.dumps([{
  "title": "Table N FYxx LTI performance measures (date range) & vesting outcome",
  "headers": [{"cells": [
    {"value": "KPIs"}, {"value": "Measure"}, {"value": "Metric"},
    {"value": "Weighting"}, {"value": "Outcome"}, {"value": "% Vesting"}
  ]}],
  "rows": [
    # Row 1 — group A: Metric subdivided into 5 bullet sub-rows
    {"cells": [
      {"value": "[Row group A]"},
      {"value": "[Measure description A]"},
      {"sub_rows": [
        {"cells": [{"value": "[Metric bullet 1]"}, {"value": "[Result 1]"}]},
        {"cells": [{"value": "[Metric bullet 2]"}, {"value": "[Result 2]"}]},
        {"cells": [{"value": "[Metric bullet 3]"}, {"value": "[Result 3]"}]},
        {"cells": [{"value": "[Metric bullet 4]"}, {"value": "[Result 4]"}]},
        {"cells": [{"value": "[Condition note]", "col_span": 2}]}
      ]},
      {"value": "N%"},
      {"value": "Nth [unit]"},
      {"value": "N.N%"}
    ]},
    # Row 2 — group B: Metric subdivided; Outcome subdivided into 2 sub-values
    {"cells": [
      {"value": "[Row group B]"},
      {"value": "[Measure description B]"},
      {"sub_rows": [
        {"cells": [{"value": "[Metric bullet 1]"}, {"value": "[Result 1]"}]},
        {"cells": [{"value": "[Metric bullet 2]"}, {"value": "[Result 2]"}]},
        {"cells": [{"value": "[Metric bullet 3]"}, {"value": "[Result 3]"}]},
        {"cells": [{"value": "[Metric bullet 4]"}, {"value": "[Result 4]"}]},
        {"cells": [{"value": "[Condition note]", "col_span": 2}]}
      ]},
      {"value": "N%"},
      {"sub_rows": [
        {"cells": [{"value": "[Sub-value A]"}]},
        {"cells": [{"value": "[Sub-value B]"}]}
      ]},
      {"value": "N%"}
    ]},
    # Row 3 — group C: KPIs cell row_span=3 covers rows 3-4-5
    {"cells": [
      {"value": "[Row group C]", "row_span": 3},
      {"value": "[Measure description C]"},
      {"value": "[Metric description C]"},
      {"value": "N%"}, {"value": "NNN,NNN[unit]"}, {"value": "N%"}
    ]},
    # Row 4 — group C continued: KPIs covered by row_span
    {"cells": [
      {"value": "[Measure description D]"},
      {"value": "[Metric description D]"},
      {"value": "N%"}, {"value": "N%"}, {"value": "N%"}
    ]},
    # Row 5 — group C continued: Metric subdivided; Outcome subdivided with row_span
    {"cells": [
      {"value": "[Measure description E]"},
      {"sub_rows": [
        {"cells": [{"value": "[Metric bullet 1]"}, {"value": "[Result 1]"}]},
        {"cells": [{"value": "[Metric bullet 2]"}, {"value": "[Result 2]"}]},
        {"cells": [{"value": "[Metric bullet 3]"}, {"value": "[Result 3]"}]},
        {"cells": [{"value": "[Metric bullet 4]"}, {"value": "[Result 4]"}]},
        {"cells": [{"value": "[Condition note]", "col_span": 2}]}
      ]},
      {"value": "N%"},
      {"sub_rows": [
        {"cells": [{"value": "[Sub-value A]", "row_span": 3}]},
        {"cells": []},
        {"cells": []},
        {"cells": [{"value": "[Result]"}]}
      ]},
      {"value": "N%"}
    ]},
    # Row 6 — Other conditions: row_span=2; text col_span=3; result col_span=2
    {"cells": [
      {"value": "[Other conditions label]", "row_span": 2},
      {"value": "[Condition text A]", "col_span": 3},
      {"value": "[Result A]", "col_span": 2}
    ]},
    # Row 7 — Other conditions continued: KPIs covered by row_span
    {"cells": [
      {"value": "[Condition text B]", "col_span": 3},
      {"value": "[Result B]", "col_span": 2}
    ]},
    # Row 8 — Total: flat row, no nesting
    {"cells": [
      {"value": "[Total label]"}, {"value": ""}, {"value": ""},
      {"value": "NN%"}, {"value": ""}, {"value": "NN.N%"}
    ]}
  ]
}], ensure_ascii=False)


# ── Few-shot example 2 (Table 12 screenshot + verified JSON) ──────────────────
_FEW_SHOT2_PATH = Path("ingest/fewshot2.png")
_FEW_SHOT2_B64: str | None = (
    base64.b64encode(_FEW_SHOT2_PATH.read_bytes()).decode()
    if _FEW_SHOT2_PATH.exists() else None
)

_FEW_SHOT2_ANSWER = json.dumps([{
  "title": "Table N FYxx LTI performance measures (date range)",
  "headers": [{"cells": [
    {"value": "[Header A]"}, {"value": "[Header B]"}, {"value": "[Header C]"}, {"value": "[Header D]"}
  ]}],
  "rows": [
    # Row 1 — group A: Metric subdivided; each bullet+result is ONE cell (= is not a separator)
    {"cells": [
      {"value": "[Row group A]"},
      {"value": "[Measure description A]"},
      {"sub_rows": [
        {"cells": [{"value": "[Metric bullet 1] = [Result 1]"}]},
        {"cells": [{"value": "[Metric bullet 2] = [Result 2]"}]},
        {"cells": [{"value": "[Metric bullet 3] = [Result 3]"}]},
        {"cells": [{"value": "[Metric bullet 4] = [Result 4]"}]}
      ]},
      {"value": "N%"}
    ]},
    # Row 2 — group B: same pattern; = is part of text, not a separator
    {"cells": [
      {"value": "[Row group B]"},
      {"value": "[Measure description B]"},
      {"sub_rows": [
        {"cells": [{"value": "[Metric bullet 1] = [Result 1]"}]},
        {"cells": [{"value": "[Metric bullet 2] = [Result 2]"}]},
        {"cells": [{"value": "[Metric bullet 3] = [Result 3]"}]},
        {"cells": [{"value": "[Metric bullet 4] = [Result 4]"}]}
      ]},
      {"value": "N%"}
    ]},
    # Row 3 — group C: flat row
    {"cells": [
      {"value": "[Row group C]"},
      {"value": "[Measure description C]"},
      {"value": "[Metric description C]"},
      {"value": "N%"}
    ]},
    # Row 4 — Other conditions: KPIs row_span=2; text spans remaining 3 columns
    {"cells": [
      {"value": "[Other conditions label]", "row_span": 2},
      {"value": "[Condition text A]", "col_span": 3}
    ]},
    # Row 5 — KPIs covered by row_span
    {"cells": [
      {"value": "[Condition text B]", "col_span": 3}
    ]},
    # Row 6 — Total: flat
    {"cells": [
      {"value": "[Total label]"}, {"value": ""}, {"value": ""}, {"value": "NN%"}
    ]}
  ]
}], ensure_ascii=False)


# ── Few-shot example 3 (Figure 6 stacked bar chart — Key folded into headers) ──
_FEW_SHOT3_PATH = Path("ingest/fewshot3.png")
_FEW_SHOT3_B64: str | None = (
    base64.b64encode(_FEW_SHOT3_PATH.read_bytes()).decode()
    if _FEW_SHOT3_PATH.exists() else None
)

_FEW_SHOT3_ANSWER = json.dumps([{
  "title": "Figure N Individual Executive KMP FYxx remuneration mix (compared to FYxx & FYxx)",
  # Key at bottom of chart (FAR=dark, STI=teal, LTI=green, CRR=purple) is folded into column headers.
  # Do NOT output the Key as a separate table.
  "headers": [{"cells": [
    {"value": "Year"},
    {"value": "FAR"},
    {"value": "STI"},
    {"value": "LTI"},
    {"value": "CRR"},
    {"value": "% at risk"}
  ]}],
  "rows": [
    # Person name rows use col_span=6 to act as group separators within the single table.
    {"cells": [{"value": "Person A, Role A", "col_span": 6}]},
    # FY23 has all 4 color segments visible → CRR has a value
    {"cells": [{"value":"FYxx"},{"value":"N%"},{"value":"N%"},{"value":"N%"},{"value":"N%"},{"value":"N%"}]},
    # FY24/FY25: CRR bar segment absent → output "" (do NOT infer or omit the column)
    {"cells": [{"value":"FYyy"},{"value":"N%"},{"value":"N%"},{"value":"N%"},{"value":""},{"value":"N%"}]},
    {"cells": [{"value":"FYzz"},{"value":"N%"},{"value":"N%"},{"value":"N%"},{"value":""},{"value":"N%"}]},

    {"cells": [{"value": "Person B, Role B", "col_span": 6}]},
    {"cells": [{"value":"FYxx"},{"value":"N%"},{"value":"N%"},{"value":"N%"},{"value":"N%"},{"value":"N%"}]},
    {"cells": [{"value":"FYyy"},{"value":"N%"},{"value":"N%"},{"value":"N%"},{"value":""},{"value":"N%"}]},
    {"cells": [{"value":"FYzz"},{"value":"N%"},{"value":"N%"},{"value":"N%"},{"value":""},{"value":"N%"}]},

    {"cells": [{"value": "Person C, Role C", "col_span": 6}]},
    {"cells": [{"value":"FYxx"},{"value":"N%"},{"value":"N%"},{"value":"N%"},{"value":"N%"},{"value":"N%"}]},
    {"cells": [{"value":"FYyy"},{"value":"N%"},{"value":"N%"},{"value":"N%"},{"value":""},{"value":"N%"}]},
    {"cells": [{"value":"FYzz"},{"value":"N%"},{"value":"N%"},{"value":"N%"},{"value":""},{"value":"N%"}]},

    {"cells": [{"value": "Person D, Role D", "col_span": 6}]},
    {"cells": [{"value":"FYxx"},{"value":"N%"},{"value":"N%"},{"value":"N%"},{"value":"N%"},{"value":"N%"}]},
    {"cells": [{"value":"FYyy"},{"value":"N%"},{"value":"N%"},{"value":"N%"},{"value":""},{"value":"N%"}]},
    {"cells": [{"value":"FYzz"},{"value":"N%"},{"value":"N%"},{"value":"N%"},{"value":""},{"value":"N%"}]}
  ]
}], ensure_ascii=False)


# ── Few-shot example 4 (table with blank first-column header → "none") ────────
_FEW_SHOT4_PATH = Path("ingest/fewshot4.png")
_FEW_SHOT4_B64: str | None = (
    base64.b64encode(_FEW_SHOT4_PATH.read_bytes()).decode()
    if _FEW_SHOT4_PATH.exists() else None
)

_FEW_SHOT4_ANSWER = json.dumps([{
  "title": "[Table title]",
  # The leftmost column has NO header text in the original — it must be {"value": "none"}.
  # Header row has N cells to match the N data columns.
  "headers": [{"cells": [
    {"value": "none"},
    {"value": "Unit"},
    {"value": "FYxx"},
    {"value": "FYxx"},
    {"value": "FYxx"},
    {"value": "FYxx baseline"}
  ]}],
  "rows": [
    {"cells": [
      {"value": "Row label A"},
      {"value": "unit A"},
      {"value": "X.X"},
      {"value": "X.X"},
      {"value": "X.X"},
      {"value": "X.X"}
    ]},
    {"cells": [
      {"value": "Row label B"},
      {"value": "unit B"},
      {"value": "X.XX"},
      {"value": "X.XX"},
      {"value": "X.XX"},
      {"value": "X.XX"}
    ]},
    {"cells": [
      {"value": "Row label C"},
      {"value": "unit C"},
      {"value": "X.XXX"},
      {"value": "X.XXX"},
      {"value": "X.XXX"},
      {"value": "X.XXX"}
    ]},
    {"cells": [
      {"value": "Row label D"},
      {"value": "unit D"},
      {"value": "X.XX"},
      {"value": "X.XX"},
      {"value": "X.XX"},
      {"value": "X.XX"}
    ]},
    {"cells": [
      {"value": "Row label E"},
      {"value": "unit E"},
      {"value": "X.XX"},
      {"value": "X.XX"},
      {"value": "X.XX"},
      {"value": "X.XX"}
    ]},
    {"cells": [
      {"value": "[Footnote text spanning all columns]", "col_span": 6}
    ]}
  ]
}], ensure_ascii=False)


def build_vision_messages(img_b64: str, source: str, page_num: int) -> list[dict]:
    """Build chat messages for the vision extraction request."""
    messages: list[dict] = [{"role": "system", "content": _SYSTEM}]

    # Prepend few-shot examples (image + expected output) when available.
    few_shots = [
        (_FEW_SHOT_B64, _FEW_SHOT_ANSWER),
        (_FEW_SHOT2_B64, _FEW_SHOT2_ANSWER),
        (_FEW_SHOT3_B64, _FEW_SHOT3_ANSWER),
        (_FEW_SHOT4_B64, _FEW_SHOT4_ANSWER),
    ]
    for few_shot_b64, few_shot_answer in few_shots:
        if not few_shot_b64:
            continue
        messages += [
            {"role": "user", "content": [
                {"type": "text", "text": _FEW_SHOT_PROMPT},
                {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{few_shot_b64}"}},
            ]},
            {"role": "assistant", "content": few_shot_answer},
        ]

    messages.append({"role": "user", "content": [
        {"type": "text", "text": _USER_TMPL.format(page_num=page_num, source=source)},
        {"type": "image_url", "image_url": {"url": f"data:image/png;base64,{img_b64}"}},
    ]})
    return messages
