from __future__ import annotations

from Tool.contracts.canonical import CanonicalDocument, DocumentMeta, Fragment
from Tool.parsers.fusion import (
    ExtractionBlock,
    FusionDecision,
    LayoutBlock,
    TableBlock,
    VisualCandidate,
    build_parser_fusion_metadata,
)
from Tool.workflows.document_parse import apply_parse_workflow_contract


def test_parser_fusion_contract_serializes_provider_blocks_and_decisions():
    extraction = ExtractionBlock(
        block_id="pdf-pypdf-p12-b03",
        provider="pypdf_fast_text",
        block_type="text",
        text="R2 Planning",
        anchors={"page": 12, "paragraph_index": 3},
        confidence=0.82,
        metadata={"raw_order": 42},
    )
    layout = LayoutBlock(
        block_id="docling-p12-layout-07",
        provider="docling",
        text="R2 Planning",
        layout_type="section_header",
        anchors={"page": 12, "bbox": [72, 130, 510, 155], "reading_order": 18},
        confidence=0.91,
    )
    table = TableBlock(
        block_id="docling-p14-table-01",
        provider="docling",
        rows=[["Role", "Deliverable"], ["PO", "QMP"]],
        anchors={"page": 14, "bbox": [64, 220, 530, 470]},
        confidence=0.87,
    )
    visual = VisualCandidate(
        candidate_id="visual-ct-p18-figure-01",
        provider="docling_ocr",
        candidate_type="figure_description",
        text="The figure shows the R2 review flow.",
        anchors={"page": 18, "crop_ref": "output/crops/ct-p18-figure-01.png"},
        confidence=0.76,
        review_status="pending_review",
    )
    decision = FusionDecision(
        decision_id="fusion-p12-heading-r2",
        decision_type="merge_blocks",
        selected_block_ids=["docling-p12-layout-07", "pdf-pypdf-p12-b03"],
        reason="docling reading order supplied bbox; pypdf text matched normalized heading",
        confidence=0.93,
        output_target="section_candidate",
    )

    metadata = build_parser_fusion_metadata(
        providers=["pypdf_fast_text", "docling", "docling"],
        extraction_blocks=[extraction],
        layout_blocks=[layout],
        table_blocks=[table],
        visual_candidates=[visual],
        fusion_decisions=[decision],
        canonical_output={"sections": 1, "fragments": 1, "tables": 1, "figures": 0},
    )

    assert metadata["schema_version"] == "parser-fusion-v0.1"
    assert metadata["providers"] == ["pypdf_fast_text", "docling"]
    assert metadata["provider_roles"]["pypdf_fast_text"] == "fast_text"
    assert metadata["provider_roles"]["docling"] == "layout_table_ocr"
    assert metadata["counts"] == {
        "extraction_blocks": 1,
        "layout_blocks": 1,
        "table_blocks": 1,
        "visual_candidates": 1,
        "fusion_decisions": 1,
    }
    assert metadata["samples"]["layout_blocks"][0]["anchors"]["reading_order"] == 18
    assert metadata["samples"]["table_blocks"][0]["rows"][1] == ["PO", "QMP"]
    assert metadata["visual_candidates"][0]["review_status"] == "pending_review"
    assert metadata["fusion_decisions"][0]["selected_block_ids"] == [
        "docling-p12-layout-07",
        "pdf-pypdf-p12-b03",
    ]
    assert metadata["canonical_output"]["tables"] == 1


def test_parse_workflow_attaches_default_parser_fusion_metadata():
    canonical = CanonicalDocument(
        document=DocumentMeta(
            document_id="doc-fusion",
            title="Fusion Doc",
            source_path="Raw/fusion.pdf",
            file_name="fusion.pdf",
            source_type="pdf",
            doc_type="pep",
        ),
        fragments=[
            Fragment(
                fragment_id="frag-1",
                section_id=None,
                fragment_type="paragraph",
                text="R2 Planning evidence.",
                anchors={"page": 12, "paragraph_index": 3},
            )
        ],
    )

    apply_parse_workflow_contract(canonical, parser_name="pdf_parser")

    parser_fusion = canonical.document.metadata["parser_fusion"]
    assert parser_fusion["schema_version"] == "parser-fusion-v0.1"
    assert parser_fusion["fusion_mode"] == "single_provider_passthrough"
    assert parser_fusion["providers"] == ["pypdf_fast_text"]
    assert parser_fusion["provider_roles"]["pypdf_fast_text"] == "fast_text"
    assert parser_fusion["canonical_output"]["fragments"] == 1
    assert parser_fusion["canonical_output"]["source_anchors"] == 0
    assert canonical.document.metadata["parse_workflow"]["parser_fusion"]["providers"] == ["pypdf_fast_text"]