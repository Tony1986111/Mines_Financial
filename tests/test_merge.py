from retrieval_nodes.merge import merge_node


# Create a minimal retrieved document shaped like the merge node expects.
def _make_doc(source="report.pdf", page=1, chunk_index=0, content="text"):
    # Keep the helper small so tests can vary only the dedupe fields they need.
    return {"source": source, "page": page, "chunk_index": chunk_index, "content": content}


# Verify that an explicit empty retrieved_docs list stays empty.
def test_merge_returns_empty_list_for_empty_input():
    # Empty input should not produce placeholder documents.
    assert merge_node({"retrieved_docs": []})["merged_docs"] == []


# Verify that missing retrieved_docs is treated as no retrieved documents.
def test_merge_returns_empty_list_for_missing_key():
    # The node should be defensive when upstream retrieval has not run.
    assert merge_node({})["merged_docs"] == []


# Verify that duplicate chunks are collapsed by source, page, and chunk index.
def test_merge_deduplicates_by_source_page_chunk_index():
    """Two docs with identical (source, page, chunk_index) keep only the first."""
    # Build two documents that share the same metadata key but different content.
    doc_a = _make_doc(content="first")
    doc_b = _make_doc(content="duplicate")

    # Merge should keep the first occurrence of the duplicate key.
    result = merge_node({"retrieved_docs": [doc_a, doc_b]})["merged_docs"]
    assert len(result) == 1
    assert result[0]["content"] == "first"


# Verify that chunk_index remains part of the dedupe identity.
def test_merge_keeps_docs_with_different_chunk_index():
    # Use the same source/page but distinct chunk_index values.
    doc_a = _make_doc(chunk_index=0)
    doc_b = _make_doc(chunk_index=1)

    # Different chunk indexes should survive as separate documents.
    result = merge_node({"retrieved_docs": [doc_a, doc_b]})["merged_docs"]
    assert len(result) == 2


# Verify fallback deduplication for documents missing metadata fields.
def test_merge_falls_back_to_content_key_when_metadata_missing():
    """Docs without source/page/chunk_index dedup by content[:300]."""
    # Metadata-free docs need content-based deduplication.
    doc_a = {"content": "same content"}
    doc_b = {"content": "same content"}
    doc_c = {"content": "different content"}

    # Two identical content keys should collapse to one document.
    result = merge_node({"retrieved_docs": [doc_a, doc_b, doc_c]})["merged_docs"]
    assert len(result) == 2


# Verify that merge preserves first-seen ordering for unique documents.
def test_merge_preserves_original_ordering():
    # Arrange unique documents in a known order.
    docs = [
        _make_doc(source="a.pdf", chunk_index=0),
        _make_doc(source="b.pdf", chunk_index=0),
        _make_doc(source="c.pdf", chunk_index=0),
    ]

    # The merge pass should not reorder unique documents.
    result = merge_node({"retrieved_docs": docs})["merged_docs"]
    assert [d["source"] for d in result] == ["a.pdf", "b.pdf", "c.pdf"]


# Verify that duplicate chunks indexed under different companies are removed.
def test_merge_cross_company_duplicate_removed():
    """Same chunk accidentally indexed under two companies keeps the first."""
    # Use identical metadata but different content to simulate cross-company duplication.
    doc_a = _make_doc(source="shared.pdf", page=5, chunk_index=2, content="bhp data")
    doc_b = _make_doc(source="shared.pdf", page=5, chunk_index=2, content="rio data")

    # The first matching chunk should win.
    result = merge_node({"retrieved_docs": [doc_a, doc_b]})["merged_docs"]
    assert len(result) == 1
    assert result[0]["content"] == "bhp data"
