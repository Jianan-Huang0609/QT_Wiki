from __future__ import annotations

from Tool.contracts.canonical import CanonicalDocument, DocumentMeta, Fragment, Section
from Tool.parsers.fusion import ExtractionBlock, LayoutBlock, TableBlock, VisualCandidate
from Tool.parsers.providers.docling_provider import DoclingProviderOutput
from Tool.parsers.pdf_fusion import build_pdf_fusion_metadata


def test_pdf_fusion_merges_pypdf_text_with_docling_layout_table_and_visual_candidates():
    canonical = CanonicalDocument(
        document=DocumentMeta(
            document_id="doc-pdf-fusion",
            title="CT PEP",
            source_path="Raw/ct-pep.pdf",
            file_name="ct-pep.pdf",
            source_type="pdf",
            doc_type="pep",
        ),
        sections=[
            Section(
                section_id="sec-r2",
                title="R2 Planning",
                level=1,
                page_range=[12],
            )
        ],
        fragments=[
            Fragment(
                fragment_id="frag-r2-heading",
                section_id="sec-r2",
                fragment_type="paragraph",
                text="R2 Planning",
                anchors={"page": 12, "paragraph_index": 1},
            ),
            Fragment(
                fragment_id="frag-r2-body",
                section_id="sec-r2",
                fragment_type="paragraph",
                text="PO prepares the R2 planning package.",
                anchors={"page": 12, "paragraph_index": 2},
            ),
        ],
        source_anchors=[
            {"fragment_id": "frag-r2-heading", "anchors": {"page": 12, "paragraph_index": 1}},
            {"fragment_id": "frag-r2-body", "anchors": {"page": 12, "paragraph_index": 2}},
        ],
    )
    docling_output = DoclingProviderOutput(
        extraction_blocks=[
            ExtractionBlock(
                block_id="docling-text-r2",
                provider="docling",
                block_type="text",
                text="R2 Planning",
                anchors={"page": 12, "bbox": [72, 130, 510, 155], "reading_order": 18},
                confidence=0.91,
            )
        ],
        layout_blocks=[
            LayoutBlock(
                block_id="docling-layout-r2",
                provider="docling",
                text="R2 Planning",
                layout_type="section_header",
                anchors={"page": 12, "bbox": [72, 130, 510, 155], "reading_order": 18},
                confidence=0.91,
            )
        ],
        table_blocks=[
            TableBlock(
                block_id="docling-table-r2",
                provider="docling",
                rows=[["Role", "Deliverable"], ["PO", "QMP"]],
                anchors={"page": 14, "bbox": [64, 220, 530, 470]},
                confidence=0.87,
            )
        ],
        visual_candidates=[
            VisualCandidate(
                candidate_id="docling-visual-r2-flow",
                provider="docling_ocr",
                candidate_type="picture",
                text="R2 review flow diagram",
                anchors={"page": 18, "bbox": [80, 180, 500, 430]},
                confidence=0.76,
            )
        ],
    )

    metadata = build_pdf_fusion_metadata(canonical, docling_output=docling_output)

    assert metadata["schema_version"] == "parser-fusion-v0.1"
    assert metadata["fusion_mode"] == "pdf_provider_fusion"
    assert metadata["providers"] == ["pypdf_fast_text", "docling", "docling_ocr"]
    assert metadata["canonical_output"] == {
        "sections": 1,
        "fragments": 2,
        "tables": 0,
        "figures": 0,
        "source_anchors": 2,
    }
    assert metadata["counts"]["extraction_blocks"] == 3
    assert metadata["counts"]["layout_blocks"] == 1
    assert metadata["counts"]["table_blocks"] == 1
    assert metadata["counts"]["visual_candidates"] == 1
    assert metadata["counts"]["fusion_decisions"] == 1
    assert metadata["samples"]["extraction_blocks"][0]["provider"] == "pypdf_fast_text"
    assert metadata["samples"]["extraction_blocks"][0]["anchors"]["paragraph_index"] == 1
    assert metadata["fusion_decisions"][0]["decision_type"] == "merge_blocks"
    assert metadata["fusion_decisions"][0]["selected_block_ids"] == [
        "pypdf-frag-r2-heading",
        "docling-layout-r2",
    ]
    assert metadata["fusion_decisions"][0]["metadata"] == {
        "canonical_fragment_id": "frag-r2-heading",
        "docling_block_id": "docling-layout-r2",
        "merged_anchors": {"page": 12, "paragraph_index": 1, "bbox": [72, 130, 510, 155], "reading_order": 18},
    }
    assert metadata["samples"]["table_blocks"][0]["rows"][1] == ["PO", "QMP"]
    assert metadata["visual_candidates"][0]["review_status"] == "pending_review"


def test_pdf_fusion_preserves_canonical_top_level_schema():
    canonical = CanonicalDocument(
        document=DocumentMeta(
            document_id="doc-schema-stable",
            title="Schema Stable PDF",
            source_path="Raw/schema.pdf",
            file_name="schema.pdf",
            source_type="pdf",
            doc_type="pep",
        ),
        fragments=[
            Fragment(
                fragment_id="frag-1",
                section_id=None,
                fragment_type="paragraph",
                text="Only pypdf text is available.",
                anchors={"page": 1, "paragraph_index": 1},
            )
        ],
    )
    before_keys = set(canonical.to_dict().keys())

    metadata = build_pdf_fusion_metadata(canonical, docling_output=None)
    canonical.document.metadata["parser_fusion"] = metadata

    assert set(canonical.to_dict().keys()) == before_keys
    assert canonical.document.metadata["parser_fusion"]["fusion_mode"] == "pdf_provider_fusion"
    assert metadata["providers"] == ["pypdf_fast_text"]
    assert metadata["counts"]["extraction_blocks"] == 1
    assert metadata["counts"]["fusion_decisions"] == 0