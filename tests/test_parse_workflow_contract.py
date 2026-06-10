from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import patch

from Tool.contracts.canonical import CanonicalDocument, DocumentMeta, Fragment, load_canonical_document
from Tool.parsers import parse_document


def test_parse_document_attaches_gate1_workflow_summary(tmp_dir, sample_manifest):
    markdown_path = tmp_dir / "sample.md"
    markdown_path.write_text("# R2 Readiness\n\nPO should prepare QMP evidence.\n", encoding="utf-8")
    sample_manifest["stored_path"] = str(markdown_path)
    sample_manifest["file_name"] = markdown_path.name

    result = parse_document(markdown_path, sample_manifest)

    workflow = result.document.metadata["parse_workflow"]
    assert workflow["document_id"] == sample_manifest["document_id"]
    assert workflow["parser_version"] == "multi-input-v0.1"
    assert workflow["counts"]["fragments"] == len(result.fragments)
    assert workflow["counts"]["sections"] == len(result.sections)
    assert workflow["structure_quality"]["anchor_coverage"] == 1.0
    assert workflow["eval_summary"]["fail"] == 0
    assert workflow["review_items"] == []
    assert result.parse_status == workflow["parse_status"]


def test_unsupported_file_has_failed_workflow_summary(tmp_dir, sample_manifest):
    unsupported_path = tmp_dir / "sample.unsupported"
    unsupported_path.write_text("dummy", encoding="utf-8")
    sample_manifest["stored_path"] = str(unsupported_path)
    sample_manifest["file_name"] = unsupported_path.name

    result = parse_document(unsupported_path, sample_manifest)

    workflow = result.document.metadata["parse_workflow"]
    assert result.parse_status == "failed"
    assert workflow["parser_name"] == "unsupported_parser"
    assert workflow["eval_summary"]["fail"] >= 1
    assert any(item["eval_id"] == "P0-01" for item in workflow["review_items"])


def test_load_processed_document_exposes_gate1_metadata(tmp_dir):
    from Tool import document_processor
    from Tool.document_processor import load_processed_document
    from Tool.workflows.document_parse import apply_parse_workflow_contract

    parsed_dir = tmp_dir / "parsed"
    parsed_dir.mkdir()
    canonical = CanonicalDocument(
        document=DocumentMeta(
            document_id="doc-gate1",
            title="Gate 1",
            source_path="Raw/gate1.md",
            file_name="gate1.md",
            source_type="md",
            doc_type="generic",
        ),
        fragments=[
            Fragment(
                fragment_id="frag-1",
                section_id=None,
                fragment_type="paragraph",
                text="R2 evidence",
                anchors={"line_start": 1, "line_end": 1},
            )
        ],
    )
    apply_parse_workflow_contract(canonical, parser_name="markdown_parser")
    canonical.save(parsed_dir / "doc-gate1.json")

    with patch.object(document_processor, "PARSED_DIR", parsed_dir):
        processed = load_processed_document("doc-gate1")

    assert processed.metadata["parse_status"] == "parsed"
    assert processed.metadata["structure_quality"]["anchor_coverage"] == 1.0
    assert processed.metadata["eval_summary"]["fail"] == 0
    assert processed.metadata["review_items"] == []


def test_parse_summary_endpoint_returns_gate1_contract(tmp_dir):
    from App import api
    from App.api import app
    from fastapi.testclient import TestClient
    from Tool.workflows.document_parse import apply_parse_workflow_contract

    parsed_dir = tmp_dir / "parsed"
    parsed_dir.mkdir()
    canonical = CanonicalDocument(
        document=DocumentMeta(
            document_id="doc-summary",
            title="Summary Doc",
            source_path="Raw/summary.md",
            file_name="summary.md",
            source_type="md",
            doc_type="generic",
        ),
        fragments=[
            Fragment(
                fragment_id="frag-1",
                section_id=None,
                fragment_type="paragraph",
                text="Evidence line",
                anchors={"line_start": 1, "line_end": 1},
            )
        ],
    )
    apply_parse_workflow_contract(canonical, parser_name="markdown_parser")
    canonical.save(parsed_dir / "doc-summary.json")

    with patch.object(api, "PARSED_DIR", parsed_dir):
        response = TestClient(app).get("/api/documents/doc-summary/parse-summary")

    payload = response.json()
    assert response.status_code == 200
    assert payload["document_id"] == "doc-summary"
    assert payload["parse_status"] == "parsed"
    assert payload["structure_quality"]["anchor_coverage"] == 1.0
    assert payload["eval_summary"]["fail"] == 0
    assert payload["review_items"] == []


def test_parse_summary_endpoint_uses_fallback_workflow_status_for_legacy_json(tmp_dir):
    from App import api
    from App.api import app
    from fastapi.testclient import TestClient

    parsed_dir = tmp_dir / "parsed"
    parsed_dir.mkdir()
    canonical = CanonicalDocument(
        document=DocumentMeta(
            document_id="doc-legacy",
            title="Legacy Doc",
            source_path="Raw/legacy.md",
            file_name="legacy.md",
            source_type="md",
            doc_type="generic",
            metadata={"llm_assist": [{"summary": "Unsupported generated claim."}]},
        ),
        fragments=[
            Fragment(
                fragment_id="frag-1",
                section_id=None,
                fragment_type="paragraph",
                text="Evidence line",
                anchors={"line_start": 1, "line_end": 1},
            )
        ],
        parse_status="parsed",
    )
    canonical.save(parsed_dir / "doc-legacy.json")

    with patch.object(api, "PARSED_DIR", parsed_dir):
        response = TestClient(app).get("/api/documents/doc-legacy/parse-summary")

    payload = response.json()
    assert response.status_code == 200
    assert payload["parse_status"] == "failed"
    assert payload["parse_workflow"]["parse_status"] == "failed"
    assert any(item["eval_id"] == "L1-01" for item in payload["review_items"])


def test_workflow_records_parser_errors_as_review_items():
    from Tool.workflows.document_parse import apply_parse_workflow_contract

    canonical = CanonicalDocument(
        document=DocumentMeta(
            document_id="doc-error",
            title="Error Doc",
            source_path="Raw/error.pdf",
            file_name="error.pdf",
            source_type="pdf",
            doc_type="generic",
        ),
        fragments=[
            Fragment(
                fragment_id="frag-1",
                section_id=None,
                fragment_type="paragraph",
                text="Extracted page text.",
                anchors={"page": 1, "paragraph_index": 1},
            )
        ],
        errors=["page 2: text extraction failed"],
    )

    apply_parse_workflow_contract(canonical, parser_name="pdf_parser")

    workflow = canonical.document.metadata["parse_workflow"]
    assert canonical.parse_status == "partially_parsed"
    assert any(item["eval_id"] == "P0-03" for item in workflow["review_items"])