from __future__ import annotations


def test_table_retrieval_diagnostic_passes_when_table_chunk_has_cell_anchor():
    from Tool.chunking.section_chunks import SectionChunk
    from Tool.evals.table_retrieval_diagnostic import table_retrieval_diagnostic_report

    table_chunk = SectionChunk(
        chunk_id="chunk-table",
        document_id="mi-pep",
        document_title="MI PEP",
        file_name="MI PEP.pdf",
        section_id="sec-table",
        section_title="Responsibility Matrix",
        section_path=["Responsibility Matrix"],
        chunk_type="table",
        text="Responsibility Matrix\nDeliverable | Responsibility | Approver\nQMP | Project Manager responsible | Product Owner",
        quote="Deliverable | Responsibility | Approver\nQMP | Project Manager responsible | Product Owner",
        source_refs=[{"document_id": "mi-pep", "table_id": "tbl-1", "anchor_label": "tbl.1 R1C1:R2C3", "quote": "QMP | Project Manager | Product Owner"}],
        anchors={"table_index": 1, "cell_range": "R1C1:R2C3", "page": 12},
        signals=["role_table", "deliverable_table", "table"],
    )
    cases = [
        {
            "case_id": "qmp-owner-table",
            "question": "MI PEP 这个表格里 QMP 的交付物责任是什么？",
            "source_scope": {"mode": "selected_docs", "document_ids": ["mi-pep"]},
            "expected_route_id": "table_lookup",
            "expected_terms_any": ["QMP", "responsible", "Approver"],
            "expected_table_signals_any": ["role_table", "deliverable_table"],
        }
    ]

    def fake_embed(text: str) -> list[float]:
        return [1.0, 0.0] if "qmp" in text.casefold() or "owner" in text.casefold() else [0.0, 1.0]

    report = table_retrieval_diagnostic_report(chunks=[table_chunk], cases=cases, embed_text=fake_embed)
    item = report["case_diagnostics"][0]

    assert report["schema_version"] == "table-retrieval-diagnostic-v0.1"
    assert item["status"] == "pass"
    assert item["actual_route_id"] == "table_lookup"
    assert item["route_gated_semantic_enabled"] is True
    assert item["top_table_hit"]["chunk_id"] == "chunk-table"
    assert item["top_table_hit"]["anchors"]["cell_range"] == "R1C1:R2C3"


def test_table_retrieval_diagnostic_classifies_missing_table_chunks_as_parser_provider_gap():
    from Tool.chunking.section_chunks import SectionChunk
    from Tool.evals.table_retrieval_diagnostic import table_retrieval_diagnostic_report

    section_chunk = SectionChunk(
        chunk_id="chunk-section",
        document_id="mi-pep",
        document_title="MI PEP",
        file_name="MI PEP.pdf",
        section_id="sec-qmp",
        section_title="QMP Responsibility",
        section_path=["QMP Responsibility"],
        chunk_type="section",
        text="QMP responsibility is described in prose, but no table chunk is available.",
        quote="QMP responsibility is described in prose, but no table chunk is available.",
        source_refs=[],
        anchors={"page": 12},
        signals=["deliverable_qmp"],
    )
    cases = [
        {
            "case_id": "qmp-owner-table-missing",
            "question": "MI PEP 这个表格里 QMP 的交付物责任是什么？",
            "source_scope": {"mode": "selected_docs", "document_ids": ["mi-pep"]},
            "expected_route_id": "table_lookup",
            "expected_terms_any": ["QMP", "responsible", "Approver"],
            "expected_table_signals_any": ["role_table", "deliverable_table"],
        }
    ]

    def fake_embed(_text: str) -> list[float]:
        return [1.0]

    report = table_retrieval_diagnostic_report(chunks=[section_chunk], cases=cases, embed_text=fake_embed)
    item = report["case_diagnostics"][0]

    assert item["status"] == "fail"
    assert item["failure_category"] == "parser_provider_gap"
    assert item["details"]["no_scoped_table_chunks"] is True
    assert report["metrics"]["table_hit_rate"] == 0.0