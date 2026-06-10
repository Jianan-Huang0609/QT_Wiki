from __future__ import annotations

from Tool.contracts.canonical import CanonicalDocument, DocumentMeta, FigureData, Fragment, Section, TableData
from Tool.parsers import parse_document
from Tool.workflows.document_parse import apply_parse_workflow_contract


def _meta(metadata: dict | None = None) -> DocumentMeta:
    return DocumentMeta(
        document_id="doc-quality",
        title="Quality Doc",
        source_path="Raw/quality.md",
        file_name="quality.md",
        source_type="md",
        doc_type="general",
        metadata=metadata or {},
    )


def _review_eval_ids(canonical: CanonicalDocument) -> set[str]:
    workflow = canonical.document.metadata["parse_workflow"]
    return {item["eval_id"] for item in workflow["review_items"]}


def test_quality_eval_keeps_clean_sectioned_markdown_parsed():
    canonical = CanonicalDocument(
        document=_meta(),
        sections=[Section(section_id="sec-1", title="R2 Readiness", level=1)],
        fragments=[
            Fragment(
                fragment_id="frag-1",
                section_id="sec-1",
                fragment_type="paragraph",
                text="PO prepares QMP evidence.",
                anchors={"line_start": 3, "line_end": 3, "heading_path": ["R2 Readiness"]},
            )
        ],
        source_anchors=[{"fragment_id": "frag-1", "anchors": {"line_start": 3, "line_end": 3}}],
    )

    apply_parse_workflow_contract(canonical, parser_name="markdown_parser")

    workflow = canonical.document.metadata["parse_workflow"]
    assert canonical.parse_status == "parsed"
    assert workflow["eval_summary"]["fail"] == 0
    assert workflow["eval_summary"]["warn"] == 0
    assert workflow["review_items"] == []


def test_quality_eval_flags_missing_expected_headings_as_capture_gap():
    canonical = CanonicalDocument(
        document=_meta({"quality_expectations": {"expected_headings": ["R2 Readiness", "R3 Transfer"]}}),
        sections=[Section(section_id="sec-1", title="R2 Readiness", level=1)],
        fragments=[
            Fragment(
                fragment_id="frag-1",
                section_id="sec-1",
                fragment_type="paragraph",
                text="PO prepares QMP evidence.",
                anchors={"line_start": 3, "line_end": 3, "heading_path": ["R2 Readiness"]},
            )
        ],
        source_anchors=[{"fragment_id": "frag-1", "anchors": {"line_start": 3, "line_end": 3}}],
    )

    apply_parse_workflow_contract(canonical, parser_name="markdown_parser")

    assert canonical.parse_status == "needs_review"
    assert "P1-01" in _review_eval_ids(canonical)
    assert canonical.document.metadata["parse_workflow"]["review_items"][0]["details"]["missing_expected_items"] == ["R3 Transfer"]


def test_quality_eval_flags_section_drift_and_invalid_section_refs():
    canonical = CanonicalDocument(
        document=_meta(),
        sections=[Section(section_id="sec-1", title="R2 Readiness", level=1)],
        fragments=[
            Fragment(
                fragment_id="frag-1",
                section_id="sec-missing",
                fragment_type="paragraph",
                text="This fragment points to a missing section.",
                anchors={"line_start": 3, "line_end": 3, "heading_path": ["R2 Readiness"]},
            )
        ],
        source_anchors=[{"fragment_id": "frag-1", "anchors": {"line_start": 3, "line_end": 3}}],
    )

    apply_parse_workflow_contract(canonical, parser_name="markdown_parser")

    assert canonical.parse_status == "failed"
    assert "P2-02" in _review_eval_ids(canonical)


def test_quality_eval_flags_complex_table_and_figure_risks():
    canonical = CanonicalDocument(
        document=_meta(),
        sections=[Section(section_id="sec-1", title="Evidence Table", level=1)],
        fragments=[
            Fragment(
                fragment_id="frag-1",
                section_id="sec-1",
                fragment_type="paragraph",
                text="Table introduction.",
                anchors={"line_start": 3, "line_end": 3, "heading_path": ["Evidence Table"]},
            )
        ],
        tables=[
            TableData(
                table_id="tbl-1",
                section_id="sec-1",
                page=None,
                rows=[["Role", "Evidence"], ["PO"]],
                anchors={"line_start": 5, "line_end": 6},
            )
        ],
        figures=[FigureData(figure_id="fig-1", section_id="sec-1", page=None, caption="", anchors={})],
        source_anchors=[{"fragment_id": "frag-1", "anchors": {"line_start": 3, "line_end": 3}}],
    )

    apply_parse_workflow_contract(canonical, parser_name="markdown_parser")

    eval_ids = _review_eval_ids(canonical)
    assert canonical.parse_status == "needs_review"
    assert "P1-02" in eval_ids
    assert "P1-03" in eval_ids


def test_markdown_parser_table_blocks_are_checked_by_quality_eval(tmp_dir, sample_manifest):
    markdown_path = tmp_dir / "table.md"
    markdown_path.write_text(
        "# Evidence Table\n\n| Role | Evidence |\n| --- | --- |\n| PO |\n",
        encoding="utf-8",
    )
    sample_manifest["stored_path"] = str(markdown_path)
    sample_manifest["file_name"] = markdown_path.name

    result = parse_document(markdown_path, sample_manifest)

    assert result.tables
    assert result.parse_status == "needs_review"
    assert "P1-02" in _review_eval_ids(result)


def test_quality_eval_flags_llm_assist_without_evidence():
    canonical = CanonicalDocument(
        document=_meta({"llm_assist": [{"label": "R2 readiness", "summary": "PO must approve all deliverables."}]}),
        sections=[Section(section_id="sec-1", title="R2 Readiness", level=1)],
        fragments=[
            Fragment(
                fragment_id="frag-1",
                section_id="sec-1",
                fragment_type="paragraph",
                text="PO prepares QMP evidence.",
                anchors={"line_start": 3, "line_end": 3, "heading_path": ["R2 Readiness"]},
            )
        ],
        source_anchors=[{"fragment_id": "frag-1", "anchors": {"line_start": 3, "line_end": 3}}],
    )

    apply_parse_workflow_contract(canonical, parser_name="markdown_parser")

    assert canonical.parse_status == "failed"
    assert "L1-01" in _review_eval_ids(canonical)


def test_quality_eval_rejects_fake_llm_evidence_ids():
    canonical = CanonicalDocument(
        document=_meta({"llm_assist": [{"summary": "PO must approve all deliverables.", "evidence_fragment_ids": ["frag-missing"]}]}),
        sections=[Section(section_id="sec-1", title="R2 Readiness", level=1)],
        fragments=[
            Fragment(
                fragment_id="frag-1",
                section_id="sec-1",
                fragment_type="paragraph",
                text="PO prepares QMP evidence.",
                anchors={"line_start": 3, "line_end": 3, "heading_path": ["R2 Readiness"]},
            )
        ],
        source_anchors=[{"fragment_id": "frag-1", "anchors": {"line_start": 3, "line_end": 3}}],
    )

    apply_parse_workflow_contract(canonical, parser_name="markdown_parser")

    assert canonical.parse_status == "failed"
    assert "L1-01" in _review_eval_ids(canonical)


def test_quality_eval_accepts_llm_assist_with_valid_fragment_evidence():
    canonical = CanonicalDocument(
        document=_meta({"llm_assist": [{"summary": "PO prepares QMP evidence.", "evidence_fragment_ids": ["frag-1"]}]}),
        sections=[Section(section_id="sec-1", title="R2 Readiness", level=1)],
        fragments=[
            Fragment(
                fragment_id="frag-1",
                section_id="sec-1",
                fragment_type="paragraph",
                text="PO prepares QMP evidence.",
                anchors={"line_start": 3, "line_end": 3, "heading_path": ["R2 Readiness"]},
            )
        ],
        source_anchors=[{"fragment_id": "frag-1", "anchors": {"line_start": 3, "line_end": 3}}],
    )

    apply_parse_workflow_contract(canonical, parser_name="markdown_parser")

    assert canonical.parse_status == "parsed"
    assert "L1-01" not in _review_eval_ids(canonical)