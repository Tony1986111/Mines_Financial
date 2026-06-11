from utils.citation import (
    apply_superscripts,
    build_prompt_sources,
    filter_and_renumber,
)


# Provide small, deterministic citation fixtures that mirror retriever output.
def _sample_docs():
    """Return representative annual-report docs used by citation tests.

    The real retriever returns dictionaries with metadata such as company,
    fiscal year, page, section, and content. These fixtures keep the same shape
    while staying small and deterministic.
    """
    # Keep examples small while covering duplicates, blank sections, and pages.
    return [
        {
            "company": "BHP",
            "fy": "FY2024",
            "page": 12,
            "section": "Financial performance",
            "content": "BHP revenue source text.",
        },
        {
            "company": "BHP",
            "fy": "FY2024",
            "page": 12,
            "section": "Financial performance",
            "content": "Duplicate BHP source text from the same page.",
        },
        {
            "company": "RIO",
            "fy": "FY2024",
            "page": 8,
            "section": "Income statement",
            "content": "RIO profit source text.",
        },
        {
            "company": "FMG",
            "fy": "FY2023",
            "page": 33,
            "section": "",
            "content": "FMG cash flow source text.",
        },
    ]


# Verify prompt sources collapse duplicate company/FY/page entries.
def test_build_prompt_sources_deduplicates_sources_by_company_fy_and_page():
    """Prompt sources should be numbered exactly as the LLM is expected to cite them.

    The first two sample docs refer to the same company, fiscal year, and page.
    They should collapse into a single source entry so the model sees a stable,
    compact source list.
    """
    # Build the source list from representative retriever documents.
    sources = build_prompt_sources(_sample_docs())

    # Confirm numbering is stable and duplicate BHP page data appears once.
    assert sources.splitlines() == [
        "[1] BHP Annual Report FY2024, Financial performance, p.12",
        "[2] RIO Annual Report FY2024, Income statement, p.8",
        "[3] FMG Annual Report FY2023, p.33",
    ]



# Verify cited sources are filtered and renumbered without gaps.
def test_filter_and_renumber_keeps_only_cited_sources_and_compacts_numbers():
    """Only cited documents should appear in the final Sources section.

    In this answer, the model cites source [2] and [3] from the deduplicated
    source list. The final answer should renumber them to [1] and [2], and the
    BHP source should be removed because it was never cited.
    """
    # Start with an answer that cites only RIO and FMG from the source list.
    answer = "RIO profit was discussed in the report [2]. FMG cash flow was also cited [3]."

    # Run filtering so unused docs are dropped and remaining citations are compacted.
    body, sources_section, cited_docs, cited_labels = filter_and_renumber(
        answer,
        _sample_docs(),
    )

    # Confirm citation markers in the answer body were rewritten to [1] and [2].
    assert body == (
        "RIO profit was discussed in the report [1]. "
        "FMG cash flow was also cited [2]."
    )
    # Confirm the final Sources section includes only the cited documents.
    assert sources_section == (
        "Sources:\n"
        "[1] RIO Annual Report FY2024, Income statement, p.8\n"
        "[2] FMG Annual Report FY2023, p.33"
    )
    # Confirm the helper returns cited document objects and labels in display order.
    assert [doc["company"] for doc in cited_docs] == ["RIO", "FMG"]
    assert cited_labels == [
        "RIO Annual Report FY2024, Income statement, p.8",
        "FMG Annual Report FY2023, p.33",
    ]


# Verify comma-separated citation markers keep each valid source.
def test_filter_and_renumber_handles_multi_source_citation_markers():
    """A marker like [1,3] should preserve both valid citations after renumbering."""
    # Use one marker that cites two non-adjacent source numbers.
    answer = "BHP and FMG both require support from annual reports [1,3]."

    # Renumber the multi-source marker against the deduplicated source list.
    body, sources_section, cited_docs, cited_labels = filter_and_renumber(
        answer,
        _sample_docs(),
    )

    # Confirm both cited sources remain and are compacted into adjacent labels.
    assert body == "BHP and FMG both require support from annual reports [1,2]."
    assert "[1] BHP Annual Report FY2024, Financial performance, p.12" in sources_section
    assert "[2] FMG Annual Report FY2023, p.33" in sources_section
    # Confirm returned docs and labels match the two cited reports.
    assert [doc["company"] for doc in cited_docs] == ["BHP", "FMG"]
    assert cited_labels == [
        "BHP Annual Report FY2024, Financial performance, p.12",
        "FMG Annual Report FY2023, p.33",
    ]


# Verify hallucinated citation numbers are removed from the answer.
def test_filter_and_renumber_removes_invalid_citation_numbers():
    """Invalid citation numbers should not create broken source references.

    The model might hallucinate a marker such as [99]. This function should
    remove that marker while preserving valid citations.
    """
    # Mix one valid citation with one number outside the available source range.
    answer = "BHP is supported [1], but this marker is invalid [99]."

    # Filter the answer so invalid markers cannot point at missing sources.
    body, sources_section, cited_docs, cited_labels = filter_and_renumber(
        answer,
        _sample_docs(),
    )

    # Confirm the valid BHP citation remains and the invalid marker is stripped.
    assert body == "BHP is supported [1], but this marker is invalid ."
    assert sources_section == "Sources:\n[1] BHP Annual Report FY2024, Financial performance, p.12"
    assert [doc["company"] for doc in cited_docs] == ["BHP"]
    assert cited_labels == ["BHP Annual Report FY2024, Financial performance, p.12"]


# Verify answers without citation markers return no Sources section.
def test_filter_and_renumber_returns_empty_sources_when_answer_has_no_citations():
    """Uncited answers should not append an unrelated Sources section."""
    # Use an answer body with no bracketed citation markers.
    answer = "This answer contains no citation markers."

    # Run the filter with normal source fixtures to prove none are appended.
    body, sources_section, cited_docs, cited_labels = filter_and_renumber(
        answer,
        _sample_docs(),
    )

    # Confirm the body is unchanged and all citation outputs are empty.
    assert body == answer
    assert sources_section == ""
    assert cited_docs == []
    assert cited_labels == []


# Verify basic citation markers are converted to superscript HTML.
def test_apply_superscripts_without_cited_docs_adds_plain_sup_tags():
    """Citation markers should become HTML superscripts for frontend rendering."""
    # Convert a plain inline marker without source-preview metadata.
    html = apply_superscripts("BHP revenue increased [1].")

    # Confirm the marker becomes the expected superscript element.
    assert html == 'BHP revenue increased <sup class="citation">[1]</sup>.'


# Verify superscripts include lookup attributes when cited docs are provided.
def test_apply_superscripts_with_cited_docs_adds_hover_lookup_attribute():
    """When cited docs are supplied, superscripts should include data-n attributes.

    The frontend uses data-n to look up source previews on hover. This test
    protects that contract.
    """
    # Convert a marker while passing cited docs for hover previews.
    html = apply_superscripts(
        "BHP revenue increased [1].",
        cited_docs=[{"content": "BHP revenue source text."}],
    )

    # Confirm the superscript includes data-n for frontend lookup.
    assert html == 'BHP revenue increased <sup class="citation" data-n="1">[1]</sup>.'

