from __future__ import annotations

from Tool.chunking.section_chunks import build_section_chunks
from Tool.contracts.canonical import CanonicalDocument, DocumentMeta, Fragment, Section, TableData
from Tool.parsers.fusion import LayoutBlock, TableBlock
from Tool.parsers.providers.docling_provider import DoclingProviderOutput
from Tool.parsers.docx_fusion import build_docx_fusion_metadata


def test_docx_fusion_merges_xml_tables_with_docling_table_layout_metadata():
    canonical = CanonicalDocument(
        document=DocumentMeta(
            document_id="doc-docx-fusion",
            title="DOCX PEP",
            source_path="Raw/docx-pep.docx",
            file_name="docx-pep.docx",
            source_type="docx",
            doc_type="pep",
        ),
        sections=[Section(section_id="sec-r2", title="R2 Planning", level=1)],
        fragments=[
            Fragment(
                fragment_id="frag-r2-heading",
                section_id="sec-r2",
                fragment_type="paragraph",
                text="R2 Planning",
                anchors={"paragraph_index": 1, "heading_path": ["R2 Planning"]},
            )
        ],
        tables=[
            TableData(
                table_id="tbl-1",
                section_id="sec-r2",
                page=None,
                rows=[["Role", "Deliverable"], ["PO", "QMP"]],
                anchors={
                    "table_index": 1,
                    "cell_range": "R1C1:R2C2",
                    "row_count": 2,
                    "column_count": 2,
                    "heading_path": ["R2 Planning"],
                },
            )
        ],
        source_anchors=[
            {"fragment_id": "frag-r2-heading", "anchors": {"paragraph_index": 1}},
            {"table_id": "tbl-1", "anchors": {"table_index": 1, "cell_range": "R1C1:R2C2"}},
        ],
    )
    docling_output = DoclingProviderOutput(
        layout_blocks=[
            LayoutBlock(
                block_id="docling-layout-r2",
                provider="docling",
                text="R2 Planning",
                layout_type="section_header",
                anchors={"bbox": [72, 120, 510, 145], "reading_order": 3},
                confidence=0.91,
            )
        ],
        table_blocks=[
            TableBlock(
                block_id="docling-table-r2",
                provider="docling",
                rows=[["Role", "Deliverable"], ["PO", "QMP"]],
                anchors={"bbox": [72, 180, 520, 260], "reading_order": 4},
                confidence=0.88,
            )
        ],
    )

    metadata = build_docx_fusion_metadata(canonical, docling_output=docling_output)

    assert metadata["schema_version"] == "parser-fusion-v0.1"
    assert metadata["fusion_mode"] == "docx_provider_fusion"
    assert metadata["providers"] == ["docx_xml", "docling"]
    assert metadata["provider_roles"]["docx_xml"] == "structure_preserving"
    assert metadata["counts"]["extraction_blocks"] == 1
    assert metadata["counts"]["layout_blocks"] == 1
    assert metadata["counts"]["table_blocks"] == 2
    assert metadata["counts"]["fusion_decisions"] == 2
    table_decision = next(decision for decision in metadata["fusion_decisions"] if decision["decision_type"] == "merge_tables")
    assert table_decision["selected_block_ids"] == ["docx-tbl-1", "docling-table-r2"]
    assert table_decision["metadata"] == {
        "canonical_table_id": "tbl-1",
        "docling_block_id": "docling-table-r2",
        "merged_anchors": {
            "table_index": 1,
            "cell_range": "R1C1:R2C2",
            "row_count": 2,
            "column_count": 2,
            "heading_path": ["R2 Planning"],
            "bbox": [72, 180, 520, 260],
            "reading_order": 4,
        },
    }
    layout_decision = next(decision for decision in metadata["fusion_decisions"] if decision["decision_type"] == "merge_blocks")
    assert layout_decision["selected_block_ids"] == ["docx-frag-r2-heading", "docling-layout-r2"]


def test_docx_table_chunks_keep_cell_range_anchor_labels_and_table_signals():
    canonical = CanonicalDocument(
        document=DocumentMeta(
            document_id="doc-docx-table",
            title="DOCX Table",
            source_path="Raw/docx-table.docx",
            file_name="docx-table.docx",
            source_type="docx",
            doc_type="pep",
        ),
        sections=[Section(section_id="sec-r2", title="R2 Planning", level=1)],
        tables=[
            TableData(
                table_id="tbl-1",
                section_id="sec-r2",
                page=None,
                rows=[["Role", "Deliverable"], ["Product Owner", "QMP"]],
                anchors={"table_index": 1, "cell_range": "R1C1:R2C2", "row_count": 2, "column_count": 2},
            )
        ],
    )

    table_chunk = next(chunk for chunk in build_section_chunks(canonical) if chunk.chunk_type == "table")

    assert table_chunk.source_refs[0]["anchor_label"] == "tbl.1 R1C1:R2C2"
    assert table_chunk.anchors["cell_range"] == "R1C1:R2C2"
    assert table_chunk.metadata == {"row_count": 2, "column_count": 2}
    assert "role_table" in table_chunk.signals
    assert "deliverable_table" in table_chunk.signals