from __future__ import annotations

from unittest.mock import patch

from fastapi.testclient import TestClient

from Tool.contracts.canonical import CanonicalDocument, DocumentMeta, FigureData, Fragment, Section, TableData
from Tool.parsers import parse_document as _parse_document
from Tool.workflows.document_parse import apply_parse_workflow_contract

_ = _parse_document


def _pep_document(document_id: str = "ct-pep") -> CanonicalDocument:
    return CanonicalDocument(
        document=DocumentMeta(
            document_id=document_id,
            title="CT PEP",
            source_path="Raw/ct.pdf",
            file_name="ct.pdf",
            source_type="pdf",
            doc_type="pep",
        ),
        sections=[
            Section(section_id="sec-history", title="0 History / 修改历史", level=1, page_range=[5]),
            Section(section_id="sec-r2", title="5.3.2 R2 Responsibilities", level=2, page_range=[21]),
        ],
        fragments=[
            Fragment(
                fragment_id="frag-history",
                section_id="sec-history",
                fragment_type="paragraph",
                text="Template change: add Product Owner check item in the R2 template.",
                anchors={"page": 5, "paragraph_index": 1, "heading_path": ["0 History / 修改历史"]},
            ),
            Fragment(
                fragment_id="frag-r2-a",
                section_id="sec-r2",
                fragment_type="paragraph",
                text="At R2, the Product Owner prepares QMP evidence and confirms product definition readiness.",
                anchors={"page": 21, "paragraph_index": 2, "heading_path": ["5.3.2 R2 Responsibilities"]},
            ),
            Fragment(
                fragment_id="frag-r2-b",
                section_id="sec-r2",
                fragment_type="paragraph",
                text="The project can proceed to R3 when the required tasks are understood.",
                anchors={"page": 21, "paragraph_index": 3, "heading_path": ["5.3.2 R2 Responsibilities"]},
            ),
        ],
        tables=[
            TableData(
                table_id="tbl-history",
                section_id="sec-history",
                page=5,
                rows=[
                    ["Nr", "Page", "Version", "Change description", "CR No."],
                    ["1", "All", "01", "Add Product Owner check item in R2 template", "PCR-1"],
                ],
                anchors={"page": 5, "table_type": "document_history"},
            )
        ],
        figures=[
            FigureData(
                figure_id="fig-vmodel",
                section_id="sec-r2",
                page=15,
                caption="Figure 1/图 1: V-model/V 字型模式",
                anchors={"page": 15, "source": "pdf_text_caption"},
            )
        ],
        source_anchors=[
            {"fragment_id": "frag-history", "anchors": {"page": 5, "paragraph_index": 1}},
            {"fragment_id": "frag-r2-a", "anchors": {"page": 21, "paragraph_index": 2}},
            {"fragment_id": "frag-r2-b", "anchors": {"page": 21, "paragraph_index": 3}},
            {"table_id": "tbl-history", "anchors": {"page": 5, "table_type": "document_history"}},
            {"figure_id": "fig-vmodel", "anchors": {"page": 15, "source": "pdf_text_caption"}},
        ],
    )


def test_section_chunks_keep_section_boundary_and_source_refs():
    from Tool.chunking.section_chunks import build_section_chunks

    chunks = build_section_chunks(_pep_document(), max_chars=220)
    r2_chunk = next(chunk for chunk in chunks if chunk.section_id == "sec-r2" and chunk.chunk_type == "section")

    assert r2_chunk.document_id == "ct-pep"
    assert r2_chunk.section_path == ["5.3.2 R2 Responsibilities"]
    assert "Product Owner prepares QMP evidence" in r2_chunk.text
    assert "Template change" not in r2_chunk.text
    assert r2_chunk.source_refs[0]["fragment_id"] == "frag-r2-a"
    assert r2_chunk.source_refs[0]["anchor_label"] == "p.21"


def test_table_chunks_add_metadata_without_changing_text():
    from Tool.chunking.section_chunks import build_section_chunks

    canonical = _pep_document()
    canonical.tables.append(
        TableData(
            table_id="tbl-deliverables",
            section_id="sec-r2",
            page=22,
            rows=[
                ["Deliverable", "Owner", "Approver"],
                ["QMP", "Project Manager", "Product Owner"],
                ["Risk Management Plan", "System Engineering", "Project Manager"],
            ],
            anchors={"page": 22, "table_index": 2, "cell_range": "R1C1:R3C3"},
        )
    )

    chunks = build_section_chunks(canonical)
    table_chunk = next(chunk for chunk in chunks if chunk.anchors.get("table_index") == 2)

    assert table_chunk.text == "5.3.2 R2 Responsibilities Deliverable | Owner | Approver QMP | Project Manager | Product Owner Risk Management Plan | System Engineering | Project Manager"
    assert table_chunk.metadata["table_type"] == "role_deliverable"
    assert table_chunk.metadata["column_headers"] == ["Deliverable", "Owner", "Approver"]
    assert table_chunk.metadata["row_labels"] == ["QMP", "Risk Management Plan"]


def test_retrieval_respects_source_scope_and_downranks_history_chunks():
    from Tool.chunking.section_chunks import build_section_chunks
    from Tool.retrieval.section_index import retrieve_sections

    ct_chunks = build_section_chunks(_pep_document("ct-pep"))
    mi_doc = _pep_document("mi-pep")
    mi_doc.fragments[1].text = "At R2, the Project Manager confirms system readiness."
    mi_chunks = build_section_chunks(mi_doc)

    result = retrieve_sections(
        "R2 Product Owner QMP evidence",
        [*ct_chunks, *mi_chunks],
        source_scope={"mode": "selected_docs", "document_ids": ["ct-pep"]},
        top_k=3,
    )

    assert result.strategy_used == "scoped_section_retrieval"
    assert result.hits[0].chunk.document_id == "ct-pep"
    assert result.hits[0].chunk.section_id == "sec-r2"
    assert "History" not in result.hits[0].chunk.section_title
    assert result.evidence_coverage["documents"] == ["ct-pep"]


def test_retrieval_eval_reports_expected_section_and_terms():
    from Tool.chunking.section_chunks import build_section_chunks
    from Tool.evals.retrieval_eval import evaluate_retrieval_cases

    chunks = build_section_chunks(_pep_document())
    report = evaluate_retrieval_cases(
        chunks,
        [
            {
                "case_id": "ct-r2-po",
                "question": "R2阶段 Product Owner 要准备什么 evidence?",
                "source_scope": {"mode": "selected_docs", "document_ids": ["ct-pep"]},
                "expected_document_ids_any": ["ct-pep"],
                "expected_section_terms_any": ["R2 Responsibilities"],
                "expected_terms_any": ["Product Owner", "QMP"],
                "forbidden_section_terms": ["History"],
            }
        ],
        top_k=3,
    )

    assert report["eval_summary"]["fail"] == 0
    assert report["metrics"]["recall_at_k"] == 1.0
    assert report["cases"][0]["top_hits"][0]["section_id"] == "sec-r2"


def test_retrieval_eval_flags_missing_expected_evidence():
    from Tool.chunking.section_chunks import build_section_chunks
    from Tool.evals.retrieval_eval import evaluate_retrieval_cases

    chunks = build_section_chunks(_pep_document())
    report = evaluate_retrieval_cases(
        chunks,
        [
            {
                "case_id": "missing-r4",
                "question": "R4 release evidence",
                "expected_section_terms_any": ["R4 Release"],
            }
        ],
        top_k=2,
    )

    assert report["eval_summary"]["fail"] == 1
    assert report["findings"][0]["eval_id"] == "R1-01"
    assert report["findings"][0]["details"]["missing_expected_section_terms"] == ["R4 Release"]


def test_parse_workflow_adds_visual_review_items_for_figures_and_complex_tables():
    canonical = _pep_document()
    canonical.tables.append(
        TableData(
            table_id="tbl-complex",
            section_id="sec-r2",
            page=22,
            rows=[["Role", "Evidence", "Gate"], ["PO", "QMP"], ["PM", "Plan", "R2", "M200"]],
            anchors={"page": 22},
        )
    )

    apply_parse_workflow_contract(canonical, parser_name="pdf_parser")

    workflow = canonical.document.metadata["parse_workflow"]
    visual_items = workflow["visual_review_items"]
    assert any(item["source_type"] == "figure" and item["recommended_tool"] == "multimodal" for item in visual_items)
    assert any(item["source_id"] == "tbl-complex" and item["recommended_tool"] == "ocr_or_multimodal" for item in visual_items)
    assert any(item["eval_id"] == "P1-05" for item in workflow["review_items"])


def test_document_chunks_endpoint_returns_chunk_contract(tmp_dir):
    from App import api
    from App.api import app

    parsed_dir = tmp_dir / "parsed"
    parsed_dir.mkdir()
    canonical = _pep_document()
    apply_parse_workflow_contract(canonical, parser_name="pdf_parser")
    canonical.save(parsed_dir / "ct-pep.json")

    with patch.object(api, "PARSED_DIR", parsed_dir):
        response = TestClient(app).get("/api/documents/ct-pep/chunks")

    payload = response.json()
    assert response.status_code == 200
    assert payload["document_id"] == "ct-pep"
    assert payload["items"][0]["chunk_id"]
    assert payload["items"][0]["source_refs"]