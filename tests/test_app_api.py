from __future__ import annotations

import json
import os
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from wiki.models.page import PageSection, WikiPage


def _sample_page() -> WikiPage:
    ref = {
        "document_id": "doc-test-0001",
        "fragment_id": "frag-1",
        "file_name": "policy.pdf",
        "anchor_label": "p.1",
        "quote": "企业应当建立质量管理体系并保持其有效性。",
    }
    return WikiPage(
        page_id="质量管理体系",
        title="质量管理体系",
        page_type="concept",
        summary="质量管理体系是企业确保产品符合法规要求的核心框架。",
        sections=[PageSection(heading="关键依据", content="企业应当建立质量管理体系。", source_refs=[ref])],
        aliases=["QMS"],
        source_refs=[ref],
        linked_pages=["风险管理"],
        review_status="published",
        page_version=1,
        updated_at="2026-04-29T09:00:00",
    )


def test_health_endpoint():
    from App.api import app

    client = TestClient(app)
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_runtime_ready_handles_bootstrap_storage_permission_error(tmp_path):
    from App import api

    with patch.object(api, "PARSED_DIR", tmp_path), patch("App.api.load_all_pages", return_value=[]), patch(
        "App.api.bootstrap_pages", side_effect=PermissionError("locked by storage provider")
    ):
        pages = api._ensure_runtime_ready(force_bootstrap_if_empty=True)

    assert pages == []


def test_ingest_candidates_endpoint():
    from App.api import app

    client = TestClient(app)
    candidate = SimpleNamespace(
        candidate_id="candidate-1",
        page_type="concept",
        title="质量管理体系",
        status="pending",
        confidence=0.91,
        content={"summary": "摘要", "keywords": ["QMS"], "related_titles": ["风险管理"]},
        source_doc_ids=["doc-test-0001"],
    )

    with patch("App.api.IngestAgent.list_candidates", return_value=[candidate]):
        response = client.get("/api/ingest/candidates")

    payload = response.json()
    assert response.status_code == 200
    assert payload["items"][0]["candidate_id"] == "candidate-1"
    assert payload["items"][0]["keywords"] == ["QMS"]
    assert payload["items"][0]["document_ids"] == ["doc-test-0001"]


def test_ingest_review_packages_endpoint():
    from App.api import app

    client = TestClient(app)
    review_package = SimpleNamespace(
        package_id="review-doc-1",
        document_id="doc-test-0001",
        status="pending_review",
        identity_decision="pending",
        document_identity=SimpleNamespace(
            title="质量管理体系培训讲义",
            business_type="external_reference",
            effective_level="reference_only",
            version="",
            scope="",
            is_binding=False,
            confidence=0.82,
            notes=["当前文档更像解释性材料，不能直接等同于法规正文。"],
        ),
        evidence_refs=[{"document_id": "doc-test-0001", "fragment_id": "frag-1", "anchor_label": "p.1", "quote": "质量管理体系是企业确保产品符合法规要求的核心框架。"}],
        confirmed_business_type="",
        confirmed_effective_level="",
        confirmed_is_binding=None,
        review_notes="",
        reviewed_at="",
        reviewed_by="",
        issues=[SimpleNamespace(issue_id="issue-1", issue_type="boundary_risk", detail="不能直接作为强制要求发布。", severity="high")],
        human_questions=[SimpleNamespace(question_id="q-1", question="文档身份是否正确？", rationale="文档身份会直接决定后续结论能否作为要求使用。", target="doc-test-0001")],
        extracted_objects=[],
        extracted_relations=[],
        candidate_page_titles=["质量管理体系"],
        tool_trace=["App.agents.ingest_agent._build_review_package"],
    )

    with patch("App.api.list_review_packages", return_value=[review_package]):
        response = client.get("/api/ingest/review-packages")

    payload = response.json()
    assert response.status_code == 200
    assert payload["items"][0]["package_id"] == "review-doc-1"
    assert payload["items"][0]["business_type"] == "external_reference"
    assert payload["items"][0]["issues"][0]["severity"] == "high"


def test_review_package_decision_endpoint():
    from App.api import app

    client = TestClient(app)
    review_package = SimpleNamespace(
        package_id="review-doc-1",
        document_id="doc-test-0001",
        status="identity_confirmed",
        identity_decision="confirmed",
        document_identity=SimpleNamespace(
            title="质量管理体系培训讲义",
            business_type="external_reference",
            effective_level="reference_only",
            version="",
            scope="",
            is_binding=False,
            confidence=0.82,
            notes=[],
        ),
        evidence_refs=[],
        confirmed_business_type="external_reference",
        confirmed_effective_level="reference_only",
        confirmed_is_binding=False,
        review_notes="只可作为解释材料使用。",
        reviewed_at="2026-04-29T10:00:00",
        reviewed_by="qa.lead",
        relation_decision="pending",
        relation_review_notes="",
        relation_reviewed_at="",
        relation_reviewed_by="",
        issues=[],
        human_questions=[],
        extracted_objects=[],
        extracted_relations=[
            SimpleNamespace(
                relation_id="rel-1",
                relation_type="responsible_for",
                from_object_id="obj-1",
                to_object_id="obj-2",
                claim_type="mandatory",
                direction="forward",
                confidence=0.68,
                human_required=True,
                evidence_refs=[],
            )
        ],
        candidate_page_titles=[],
        tool_trace=[],
    )

    with patch("App.api.list_review_packages", return_value=[review_package]), patch(
        "App.api.update_review_package_decision", return_value=review_package
    ):
        response = client.post(
            "/api/ingest/review-packages/review-doc-1/decision",
            json={
                "identity_decision": "confirmed",
                "confirmed_business_type": "external_reference",
                "confirmed_effective_level": "reference_only",
                "confirmed_is_binding": False,
                "review_notes": "只可作为解释材料使用。",
                "reviewed_by": "qa.lead",
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["item"]["identity_decision"] == "confirmed"


def test_review_package_relation_decision_endpoint():
    from App.api import app

    client = TestClient(app)
    review_package = SimpleNamespace(
        package_id="review-doc-1",
        document_id="doc-test-0001",
        status="ready_to_publish",
        identity_decision="confirmed",
        relation_decision="confirmed",
        document_identity=SimpleNamespace(
            title="质量管理体系培训讲义",
            business_type="external_reference",
            effective_level="reference_only",
            version="",
            scope="",
            is_binding=False,
            confidence=0.82,
            notes=[],
        ),
        evidence_refs=[],
        confirmed_business_type="external_reference",
        confirmed_effective_level="reference_only",
        confirmed_is_binding=False,
        review_notes="只可作为解释材料使用。",
        reviewed_at="2026-04-29T10:00:00",
        reviewed_by="qa.lead",
        relation_review_notes="关键关系成立。",
        relation_reviewed_at="2026-04-29T10:05:00",
        relation_reviewed_by="qa.lead",
        issues=[],
        human_questions=[],
        extracted_objects=[],
        extracted_relations=[
            SimpleNamespace(
                relation_id="rel-1",
                relation_type="responsible_for",
                from_object_id="obj-1",
                to_object_id="obj-2",
                claim_type="mandatory",
                direction="forward",
                confidence=0.68,
                human_required=True,
                evidence_refs=[],
            )
        ],
        candidate_page_titles=[],
        tool_trace=[],
    )

    with patch("App.api.list_review_packages", return_value=[review_package]), patch(
        "App.api.update_review_package_relation_decision", return_value=review_package
    ):
        response = client.post(
            "/api/ingest/review-packages/review-doc-1/relations/decision",
            json={
                "relation_decision": "confirmed",
                "relation_review_notes": "关键关系成立。",
                "relation_reviewed_by": "qa.lead",
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["ok"] is True
    assert payload["item"]["relation_decision"] == "confirmed"


def test_wiki_pages_endpoint_returns_markdown():
    from App.api import app

    client = TestClient(app)
    page = _sample_page()

    with patch("App.api.load_all_pages", return_value=[page]):
        response = client.get("/api/wiki/pages")

    payload = response.json()
    assert response.status_code == 200
    assert payload["items"][0]["page_id"] == "质量管理体系"
    assert "# 质量管理体系" in payload["items"][0]["markdown"]


def test_chat_query_returns_matched_pages_and_citations():
    from App.api import app

    client = TestClient(app)
    page = _sample_page()
    ranked_entry = {
        "page_id": page.page_id,
        "title": page.title,
        "page_type": page.page_type,
        "summary": page.summary,
        "aliases": page.aliases,
        "keywords": ["质量管理体系", "QMS"],
        "linked_pages": page.linked_pages,
        "review_status": page.review_status,
        "updated_at": page.updated_at,
        "source_count": 1,
        "relevance_score": 8.0,
    }

    with patch("App.api.load_page_index", return_value=[ranked_entry]), \
         patch("App.api.rank_page_index", return_value=[ranked_entry]), \
         patch("App.api.load_page", return_value=page):
        response = client.post(
            "/chat/query",
            json={
                "question": "什么是QMS？",
                "use_llm": False,
                "top_k_pages": 5,
                "top_k_citations": 5,
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["matched_pages"][0]["page_id"] == "质量管理体系"
    assert payload["citations"][0]["citation_id"] == "c1"
    assert payload["suggested_questions"]
    assert "质量管理体系" in payload["answer"]


def test_approve_candidate_requires_confirmed_identity():
    from App.api import app

    client = TestClient(app)

    with patch("App.api.IngestAgent.can_approve_candidate", return_value=False):
        response = client.post("/api/ingest/candidates/candidate-1/approve")

    assert response.status_code == 409


def test_agent_upload_returns_current_run_context():
    from App.api import app

    client = TestClient(app)
    processed = SimpleNamespace(
        document_id="doc-test-0009",
        title="上传文档",
        metadata={
            "parse_status": "parsed",
            "section_count": 3,
            "fragment_count": 12,
            "table_count": 1,
            "structure_quality": {"anchor_coverage": 1.0, "section_confidence": 0.9, "noise_rate": 0.0},
            "eval_summary": {"pass": 3, "warn": 0, "fail": 0, "na": 0},
            "review_items": [],
        },
    )
    candidates = [
        SimpleNamespace(candidate_id="candidate-1", status="pending"),
        SimpleNamespace(candidate_id="candidate-2", status="pending"),
    ]

    with patch("App.api.process_document", return_value=processed), patch(
        "App.api.IngestAgent.ingest", return_value=candidates
    ):
        response = client.post(
            "/agent/upload",
            files={"file": ("demo.pdf", b"fake pdf content", "application/pdf")},
            data={"use_llm": "true"},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["document_id"] == "doc-test-0009"
    assert payload["review_package_id"] == "review-doc-test-0009"
    assert payload["candidate_ids"] == ["candidate-1", "candidate-2"]
    assert payload["parse_status"] == "parsed"
    assert payload["section_count"] == 3
    assert payload["fragment_count"] == 12
    assert payload["table_count"] == 1
    assert payload["structure_quality"]["anchor_coverage"] == 1.0
    assert payload["eval_summary"]["fail"] == 0
    assert payload["review_items"] == []


def test_agent_upload_skips_candidate_generation_when_parse_failed():
    from App.api import app

    client = TestClient(app)
    processed = SimpleNamespace(
        document_id="doc-failed-parse",
        title="失败文档",
        metadata={
            "parse_status": "failed",
            "section_count": 0,
            "fragment_count": 0,
            "table_count": 0,
            "structure_quality": {"anchor_coverage": 0.0},
            "eval_summary": {"pass": 0, "warn": 0, "fail": 2, "na": 0},
            "review_items": [{"eval_id": "P0-02", "status": "fail"}],
        },
    )

    with patch("App.api.process_document", return_value=processed), patch("App.api.IngestAgent.ingest") as mock_ingest:
        response = client.post(
            "/agent/upload",
            files={"file": ("demo.pdf", b"fake pdf content", "application/pdf")},
            data={"use_llm": "false"},
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["parse_status"] == "failed"
    assert payload["review_package_id"] is None
    assert payload["proposals_created"] == 0
    assert payload["pending_review_count"] == 0
    assert payload["review_items"][0]["eval_id"] == "P0-02"
    mock_ingest.assert_not_called()


def test_ingest_runs_endpoint_returns_recent_runs(tmp_path):
    from App.api import app

    client = TestClient(app)
    run_dir = tmp_path / "runs"
    run_dir.mkdir()
    older_path = run_dir / "older.json"
    newer_path = run_dir / "newer.json"
    older_path.write_text(
        json.dumps(
            {
                "run_id": "run-older",
                "document_id": "doc-older",
                "file_name": "older.pdf",
                "review_package_id": "review-doc-older",
                "candidate_ids": ["candidate-1"],
                "pending_review_count": 1,
                "proposals_created": 1,
                "use_llm": False,
            }
        ),
        encoding="utf-8",
    )
    newer_path.write_text(
        json.dumps(
            {
                "run_id": "run-newer",
                "document_id": "doc-newer",
                "file_name": "newer.pdf",
                "review_package_id": "review-doc-newer",
                "candidate_ids": ["candidate-2", "candidate-3"],
                "pending_review_count": 2,
                "proposals_created": 2,
                "use_llm": True,
            }
        ),
        encoding="utf-8",
    )
    os.utime(older_path, (1000, 1000))
    os.utime(newer_path, (2000, 2000))

    with patch("App.api.RUN_DIR", run_dir):
        response = client.get("/api/ingest/runs?limit=1")

    payload = response.json()
    assert response.status_code == 200
    assert len(payload["items"]) == 1
    assert payload["items"][0]["run_id"] == "run-newer"
    assert payload["items"][0]["document_id"] == "doc-newer"
    assert payload["items"][0]["review_package_id"] == "review-doc-newer"
    assert payload["items"][0]["candidate_ids"] == ["candidate-2", "candidate-3"]


def test_chat_query_includes_structured_matches():
    from App.api import app

    client = TestClient(app)
    page = _sample_page()
    ranked_entry = {
        "page_id": page.page_id,
        "title": page.title,
        "page_type": page.page_type,
        "summary": page.summary,
        "aliases": page.aliases,
        "keywords": ["质量管理体系", "QMS"],
        "linked_pages": page.linked_pages,
        "review_status": page.review_status,
        "updated_at": page.updated_at,
        "source_count": 1,
        "relevance_score": 8.0,
    }
    review_package = SimpleNamespace(
        package_id="review-doc-1",
        document_id="doc-test-0001",
        identity_decision="confirmed",
        relation_decision="confirmed",
        confirmed_business_type="external_mandatory",
        updated_at="2026-04-29T10:05:00",
        created_at="2026-04-29T10:00:00",
        document_identity=SimpleNamespace(title="设计开发控制", business_type="external_mandatory"),
        extracted_objects=[
            SimpleNamespace(object_id="obj-1", object_type="requirement", name="设计开发应建立控制程序", confidence=0.9, evidence_refs=[]),
            SimpleNamespace(object_id="obj-2", object_type="process_step", name="设计开发", confidence=0.8, evidence_refs=[]),
        ],
        extracted_relations=[
            SimpleNamespace(
                relation_id="rel-1",
                relation_type="requires",
                from_object_id="obj-1",
                to_object_id="obj-2",
                claim_type="mandatory",
                direction="forward",
                confidence=0.88,
                human_required=True,
                evidence_refs=[
                    {
                        "document_id": "doc-test-0001",
                        "fragment_id": "frag-2",
                        "file_name": "regulation.pdf",
                        "anchor_label": "p.2",
                        "quote": "设计开发应建立控制程序。",
                    }
                ],
            )
        ],
        evidence_refs=[],
    )

    with patch("App.api.load_page_index", return_value=[ranked_entry]), \
         patch("App.api.rank_page_index", return_value=[ranked_entry]), \
         patch("App.api.load_page", return_value=page), \
         patch("App.agents.structured_knowledge.list_review_packages", return_value=[review_package]):
        response = client.post(
            "/chat/query",
            json={
                "question": "设计开发要求对应哪个流程步骤？",
                "use_llm": False,
                "top_k_pages": 5,
                "top_k_citations": 5,
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["structured_matches"][0]["package_id"] == "review-doc-1"
    assert "设计开发应建立控制程序" in payload["answer"]
    assert any(item["fragment_id"] == "frag-2" for item in payload["citations"])


def test_mapping_matrix_export_endpoint():
    from App.api import app

    client = TestClient(app)
    review_package = SimpleNamespace(
        package_id="review-doc-1",
        document_id="doc-test-0001",
        identity_decision="confirmed",
        relation_decision="confirmed",
        confirmed_business_type="external_mandatory",
        updated_at="2026-04-29T10:05:00",
        created_at="2026-04-29T10:00:00",
        document_identity=SimpleNamespace(title="设计开发控制", business_type="external_mandatory"),
        extracted_objects=[
            SimpleNamespace(object_id="obj-1", object_type="requirement", name="设计开发应建立控制程序", confidence=0.9, evidence_refs=[]),
            SimpleNamespace(object_id="obj-2", object_type="process_step", name="设计开发", confidence=0.8, evidence_refs=[]),
            SimpleNamespace(object_id="obj-3", object_type="record", name="设计开发记录", confidence=0.8, evidence_refs=[]),
            SimpleNamespace(object_id="obj-4", object_type="role", name="质量负责人", confidence=0.8, evidence_refs=[]),
        ],
        extracted_relations=[
            SimpleNamespace(relation_id="rel-1", relation_type="requires", from_object_id="obj-1", to_object_id="obj-2", claim_type="mandatory", direction="forward", confidence=0.88, human_required=True, evidence_refs=[]),
            SimpleNamespace(relation_id="rel-2", relation_type="produces", from_object_id="obj-2", to_object_id="obj-3", claim_type="mandatory", direction="forward", confidence=0.82, human_required=False, evidence_refs=[]),
            SimpleNamespace(relation_id="rel-3", relation_type="responsible_for", from_object_id="obj-4", to_object_id="obj-2", claim_type="mandatory", direction="forward", confidence=0.8, human_required=False, evidence_refs=[]),
        ],
        evidence_refs=[],
    )

    with patch("App.agents.structured_knowledge.list_review_packages", return_value=[review_package]):
        response = client.get("/api/exports/mapping-matrix")

    payload = response.json()
    assert response.status_code == 200
    assert payload["row_count"] == 1
    assert payload["rows"][0]["mapped_process_steps"][0]["name"] == "设计开发"
    assert payload["rows"][0]["mapped_records"][0]["name"] == "设计开发记录"
    assert payload["rows"][0]["mapped_roles"][0]["name"] == "质量负责人"


def test_slides_outline_export_endpoint():
    from App.api import app

    client = TestClient(app)
    review_package = SimpleNamespace(
        package_id="review-doc-1",
        document_id="doc-test-0001",
        identity_decision="confirmed",
        relation_decision="confirmed",
        confirmed_business_type="external_mandatory",
        review_notes="作为正式要求使用。",
        relation_review_notes="关键关系已确认。",
        updated_at="2026-04-29T10:05:00",
        created_at="2026-04-29T10:00:00",
        document_identity=SimpleNamespace(title="设计开发控制", business_type="external_mandatory"),
        extracted_objects=[
            SimpleNamespace(object_id="obj-1", object_type="requirement", name="设计开发应建立控制程序", confidence=0.9, evidence_refs=[]),
            SimpleNamespace(object_id="obj-2", object_type="process_step", name="设计开发", confidence=0.8, evidence_refs=[]),
        ],
        extracted_relations=[
            SimpleNamespace(relation_id="rel-1", relation_type="requires", from_object_id="obj-1", to_object_id="obj-2", claim_type="mandatory", direction="forward", confidence=0.88, human_required=True, evidence_refs=[]),
        ],
        evidence_refs=[],
    )

    with patch("App.agents.structured_knowledge.list_review_packages", return_value=[review_package]):
        response = client.get("/api/exports/slides-outline")

    payload = response.json()
    assert response.status_code == 200
    assert payload["slide_count"] >= 3
    assert payload["slides"][0]["title"] == "批准知识基线"
    assert "Slides Outline" in payload["markdown"]


def test_session_handoff_endpoint_returns_real_tree_graph_and_chat_contract(tmp_dir):
    from App import api
    from App.api import app
    from Tool.contracts.canonical import CanonicalDocument, DocumentMeta, FigureData, Fragment, Section, TableData
    from Tool.workflows.document_parse import apply_parse_workflow_contract

    parsed_dir = tmp_dir / "parsed"
    parsed_dir.mkdir()
    canonical = CanonicalDocument(
        document=DocumentMeta(
            document_id="ct-pep",
            title="CT PEP",
            source_path="Raw/ct.pdf",
            file_name="ct.pdf",
            source_type="pdf",
            doc_type="pep",
        ),
        sections=[
            Section(section_id="sec-r2", title="5.3.2 R2 Responsibilities", level=1, page_range=[21]),
            Section(section_id="sec-716", title="7.16 Regulatory Approval Plan", level=1, page_range=[41]),
        ],
        fragments=[
            Fragment(
                fragment_id="frag-r2",
                section_id="sec-r2",
                fragment_type="paragraph",
                text="At R2, the Product Owner prepares QMP evidence.",
                anchors={"page": 21, "paragraph_index": 2, "heading_path": ["5.3.2 R2 Responsibilities"]},
            ),
            Fragment(
                fragment_id="frag-716",
                section_id="sec-716",
                fragment_type="paragraph",
                text="The regulatory approval plan contains submission evidence.",
                anchors={"page": 41, "paragraph_index": 1, "heading_path": ["7.16 Regulatory Approval Plan"]},
            ),
        ],
        tables=[
            TableData(
                table_id="tbl-role",
                section_id="sec-r2",
                page=21,
                rows=[["Role", "Deliverable"], ["PO", "QMP"]],
                anchors={"page": 21, "table_index": 1, "cell_range": "R1C1:R2C2"},
            )
        ],
        figures=[FigureData(figure_id="fig-flow", section_id="sec-r2", page=22, caption="Figure 1: R2 flow", anchors={"page": 22, "visual_analysis": "reviewed"})],
        source_anchors=[{"fragment_id": "frag-r2", "anchors": {"page": 21}}],
    )
    apply_parse_workflow_contract(canonical, parser_name="pdf_parser")
    canonical.save(parsed_dir / "ct-pep.json")

    with patch.object(api, "PARSED_DIR", parsed_dir):
        response = TestClient(app).get("/api/session/handoff/ct-pep")

    payload = response.json()
    assert response.status_code == 200
    assert payload["schema_version"] == "session-handoff-v0.1"
    assert payload["source"]["document_id"] == "ct-pep"
    assert payload["source"]["parse_status"] == "parsed"
    assert payload["tree"]["root_id"] == "doc-ct-pep"
    assert any(item["node_type"] == "section" and item["section_id"] == "sec-r2" for item in payload["tree"]["items"])
    assert any(node["node_type"] == "chunk" for node in payload["graph"]["nodes"])
    assert any(edge["relation_type"] == "contains" for edge in payload["graph"]["edges"])
    assert payload["retrieval"]["available_retrievers"] == ["rule_section", "full_text", "vector", "hybrid"]
    assert payload["retrieval"]["preview_chunks"]
    assert payload["chat"]["source_scope"] == {"mode": "selected_docs", "document_ids": ["ct-pep"]}
    assert payload["chat"]["answer_contract"]["requires_citations"] is True
    assert payload["quality"]["eval_summary"]["fail"] == 0
    assert payload["quality"]["parser_fusion"]["schema_version"] == "parser-fusion-v0.1"


def test_session_query_uses_selected_pep_chunks_for_process_question(tmp_dir):
    from App import api
    from App.api import app
    from Tool.contracts.canonical import CanonicalDocument, DocumentMeta, Fragment, Section
    from Tool.workflows.document_parse import apply_parse_workflow_contract

    parsed_dir = tmp_dir / "parsed"
    parsed_dir.mkdir()
    canonical = CanonicalDocument(
        document=DocumentMeta(
            document_id="mi-pep",
            title="0 History / 修改历史",
            source_path="Raw/mi.pdf",
            file_name="20260611163304-MI PEP AND 308 11.pdf",
            source_type="pdf",
            doc_type="pep",
        ),
        sections=[
            Section(section_id="sec-purpose", title="1 Purpose and scope", level=1, page_range=[5]),
            Section(section_id="sec-procedure", title="4 Procedure and Requirement", level=1, page_range=[12]),
            Section(section_id="sec-review", title="5 Review deliverables", level=1, page_range=[14]),
        ],
        fragments=[
            Fragment(
                fragment_id="frag-purpose",
                section_id="sec-purpose",
                fragment_type="paragraph",
                text="The PEP defines the product development process and the responsibilities for each phase.",
                anchors={"page": 5, "paragraph_index": 1, "heading_path": ["1 Purpose and scope"]},
            ),
            Fragment(
                fragment_id="frag-procedure",
                section_id="sec-procedure",
                fragment_type="paragraph",
                text="The procedure describes how to operate the PEP workflow: confirm scope, follow development phases, prepare QMP evidence, and review deliverables.",
                anchors={"page": 12, "paragraph_index": 3, "heading_path": ["4 Procedure and Requirement"]},
            ),
            Fragment(
                fragment_id="frag-review",
                section_id="sec-review",
                fragment_type="paragraph",
                text="Review outputs confirm records and deliverables after the operation workflow has been followed.",
                anchors={"page": 14, "paragraph_index": 1, "heading_path": ["5 Review deliverables"]},
            ),
        ],
    )
    apply_parse_workflow_contract(canonical, parser_name="pdf_parser")
    canonical.save(parsed_dir / "mi-pep.json")

    with patch.object(api, "PARSED_DIR", parsed_dir):
        response = TestClient(app).post(
            "/api/session/query",
            json={
                "question": "PEP 文档的流程如何操作？",
                "source_scope": {"mode": "selected_docs", "document_ids": ["mi-pep"]},
                "use_llm": False,
            },
        )

    payload = response.json()
    assert response.status_code == 200
    assert payload["used_llm"] is False
    assert payload["citations"]
    assert payload["citations"][0]["document_id"] == "mi-pep"
    assert payload["citations"][0]["file_name"] == "20260611163304-MI PEP AND 308 11.pdf"
    assert any("PEP workflow" in citation["quote"] for citation in payload["citations"])
    workflow_citation = next(citation for citation in payload["citations"] if "PEP workflow" in citation["quote"])
    assert workflow_citation["source_context"]["chunk_id"]
    assert "product development process" in workflow_citation["source_context"]["context_before"]
    assert "PEP workflow" in workflow_citation["source_context"]["context_text"]
    assert "Review outputs" in workflow_citation["source_context"]["context_after"]
    assert "当前选中文档证据" in payload["answer"]
    assert "文档细节" in payload["answer"]
    assert "可追溯位置" in payload["answer"]
    assert "selected_docs" in " > ".join(payload["trace"])
    assert any("hybrid retriever fanout" in item for item in payload["trace"])
    assert payload["suggested_questions"]
    assert all("0 History" not in item for item in payload["suggested_questions"])
    assert any("MI PEP AND 308 11.pdf" in item for item in payload["suggested_questions"])
    assert payload["answer_run"]["schema_version"] == "answer-run-v0.1"
    assert [step["step_id"] for step in payload["answer_run"]["steps"]] == [
        "input",
        "context",
        "planning",
        "execution",
        "generation",
        "memory",
    ]
    assert payload["answer_run"]["steps"][1]["outputs"]["chunk_count"] == 3
    assert payload["answer_run"]["steps"][2]["outputs"]["intent_type"] == "process_explanation"
    assert payload["answer_run"]["steps"][2]["outputs"]["route_id"] == "process_operation"
    query_rewrite = payload["answer_run"]["steps"][2]["outputs"]["query_rewrite"]
    assert query_rewrite["rewritten_query"].startswith("PEP 文档的流程如何操作？")
    assert "operation steps" in query_rewrite["route_terms"]
    tool_plan = payload["answer_run"]["steps"][2]["outputs"]["tool_plan"]
    assert any(item["tool"] == "section_search" for item in tool_plan["planned"])
    assert any(item["tool"] == "vector_search" and item["reason"] == "persistent vector index not enabled" for item in tool_plan["skipped"])
    assert any(call["tool"] == "hybrid_retrieve_sections" for call in payload["answer_run"]["steps"][3]["outputs"]["tool_calls"])
    assert any(call["tool"] == "prioritize_process_operation_evidence" for call in payload["answer_run"]["steps"][3]["outputs"]["tool_calls"])
    assert payload["answer_run"]["steps"][3]["outputs"]["tool_plan"]["executed"]
    answer_plan = payload["answer_run"]["steps"][4]["outputs"]["answer_plan"]
    assert answer_plan["route_id"] == "process_operation"
    assert any(slot["slot_id"] == "operation_sequence" and slot["citation_ids"] for slot in answer_plan["slots"])
    answer_style = payload["answer_run"]["steps"][4]["outputs"]["answer_style"]
    assert answer_style["schema_version"] == "answer-style-v0.1"
    assert answer_style["numbering"] == "continuous_numbered_steps"
    assert payload["answer_run"]["steps"][3]["outputs"]["evidence_preview"]
    assert payload["answer_run"]["steps"][4]["outputs"]["self_check"]["route_label"] == "流程操作办法"
    assert payload["answer_run"]["steps"][4]["outputs"]["self_check"]["quality_notes"]
    assert "操作主线" in payload["answer"]
    assert "\n- 具体做法" not in payload["answer"]
    assert "\n- 文档细节" not in payload["answer"]
    assert "References：" not in payload["answer"]
    assert payload["answer_run"]["steps"][5]["status"] == "deferred"


def test_session_query_can_use_selected_llm_model_profile(tmp_dir):
    from App import api
    from App.api import app
    from Tool.contracts.canonical import CanonicalDocument, DocumentMeta, Fragment, Section
    from Tool.workflows.document_parse import apply_parse_workflow_contract

    parsed_dir = tmp_dir / "parsed"
    parsed_dir.mkdir()
    canonical = CanonicalDocument(
        document=DocumentMeta(
            document_id="mi-pep",
            title="MI PEP",
            source_path="Raw/mi.pdf",
            file_name="MI PEP.pdf",
            source_type="pdf",
            doc_type="pep",
        ),
        sections=[Section(section_id="sec-procedure", title="4 Procedure and Requirement", level=1, page_range=[12])],
        fragments=[
            Fragment(
                fragment_id="frag-procedure",
                section_id="sec-procedure",
                fragment_type="paragraph",
                text="The Product Owner prepares QMP evidence during R2 and reviews deliverables.",
                anchors={"page": 12, "paragraph_index": 3, "heading_path": ["4 Procedure and Requirement"]},
            ),
        ],
    )
    apply_parse_workflow_contract(canonical, parser_name="pdf_parser")
    canonical.save(parsed_dir / "mi-pep.json")

    with patch.object(api, "PARSED_DIR", parsed_dir), patch(
        "Tool.llm.client.ask_llm",
        return_value="PO 在 R2 阶段准备 QMP evidence 并 review deliverables。[c1]",
    ) as mock_ask:
        response = TestClient(app).post(
            "/api/session/query",
            json={
                "question": "R2 阶段 PO 应该做什么？",
                "source_scope": {"mode": "selected_docs", "document_ids": ["mi-pep"]},
                "use_llm": True,
                "model_profile": "azure-gpt-5.4",
            },
        )

    payload = response.json()
    generation_step = next(step for step in payload["answer_run"]["steps"] if step["step_id"] == "generation")
    assert response.status_code == 200
    assert payload["used_llm"] is True
    assert "[c1]" in payload["answer"]
    assert generation_step["outputs"]["composer"] == "llm_session_answer"
    assert generation_step["outputs"]["model_profile"] == "azure-gpt-5.4"
    assert any("azure-gpt-5.4" in item for item in payload["trace"])
    mock_ask.assert_called_once()
    assert mock_ask.call_args.kwargs["config_path"] == "config/azure_gpt5_4_config.json"
    prompt = mock_ask.call_args.args[0]
    assert "context_hit:" in prompt
    assert "不要输出独立的'识别与路线'或'References'栏目" in prompt
    assert "不要只罗列章节标题" in prompt


def test_session_query_defaults_to_gpt54_and_supports_gpt55_profile():
    from App.api import DEFAULT_MODEL_PROFILE, _model_config_path
    from App.schemas import ChatQueryRequest, SessionQueryRequest

    assert DEFAULT_MODEL_PROFILE == "azure-gpt-5.4"
    assert ChatQueryRequest(question="流程怎么做？").model_profile == "azure-gpt-5.4"
    assert SessionQueryRequest(question="流程怎么做？").model_profile == "azure-gpt-5.4"
    assert _model_config_path("") == "config/azure_gpt5_4_config.json"
    assert _model_config_path("unknown-profile") == "config/azure_gpt5_4_config.json"
    assert _model_config_path("azure-gpt-5") == "config/azure_gpt5_config.json"
    assert _model_config_path("azure-gpt-5.5") == "config/azure_gpt5_5_config.json"


def test_process_operation_route_does_not_inject_stage_specific_terms():
    from App.api import _session_retrieval_question, _session_route_plan
    from Tool.workflows.answer import parse_question_intent

    intent = parse_question_intent("PEP 文档的流程如何操作？")
    route_plan = _session_route_plan("PEP 文档的流程如何操作？", intent)
    retrieval_question = _session_retrieval_question("PEP 文档的流程如何操作？", intent, route_plan).casefold()

    assert route_plan["route_id"] == "process_operation"
    assert "operation steps" in retrieval_question
    assert "purpose scope" in retrieval_question
    assert "process model" in retrieval_question
    assert "lifecycle" in retrieval_question
    assert "r2" not in retrieval_question
    assert "r3" not in retrieval_question


def test_session_route_plan_handles_stage_transition_deliverable_and_tailoring_questions():
    from App.api import _session_answer_plan, _session_query_rewrite, _session_route_plan
    from Tool.workflows.answer import AnswerEvidencePackage, EvidenceItem, parse_question_intent

    cases = [
        (
            "R4到R5之间需要完成哪些工作？",
            "stage_transition_work",
            ["stage transition", "R4", "R5", "work items", "entry exit criteria"],
            {"transition_scope", "work_items", "exit_readiness"},
        ),
        (
            "QMP需要包含哪些内容？谁负责撰写QMP？",
            "deliverable_detail",
            ["QMP", "quality management plan", "content", "owner", "responsible", "author"],
            {"required_contents", "owner_author", "review_approval"},
        ),
        (
            "采用敏捷方法开发，可以裁剪哪些评审？哪些评审不可被裁剪？",
            "tailoring_policy",
            ["agile", "tailoring", "review", "cannot be tailored", "mandatory review"],
            {"agile_applicability", "tailorable_reviews", "non_tailorable_reviews"},
        ),
    ]

    for question, expected_route, expected_terms, expected_slots in cases:
        intent = parse_question_intent(question)
        route_plan = _session_route_plan(question, intent)
        query_rewrite = _session_query_rewrite(question, intent, route_plan)
        plan = _session_answer_plan(
            route_plan=route_plan,
            evidence_package=AnswerEvidencePackage(
                question=question,
                intent=intent.to_dict(),
                source_scope={"mode": "selected_docs", "document_ids": ["mi-pep"]},
                strategy_used="test",
                evidence_items=[
                    EvidenceItem(
                        evidence_id="ev-1",
                        document_id="mi-pep",
                        file_name="MI PEP.pdf",
                        section_id="sec-1",
                        section_title="Procedure and Requirement",
                        section_path=["Procedure and Requirement"],
                        anchor_label="p.12",
                        quote="R4 to R5 transition work includes QMP content, responsible author, agile tailoring, mandatory review, and exit readiness.",
                        source_refs=[],
                        score=9.0,
                        matched_terms=[],
                        signals=[],
                    )
                ],
                coverage={"document_count": 1},
            ),
            citations=[
                {
                    "citation_id": "c1",
                    "evidence_id": "ev-1",
                    "document_id": "mi-pep",
                    "file_name": "MI PEP.pdf",
                    "fragment_id": "frag-1",
                    "anchor_label": "p.12",
                    "quote": "R4 to R5 transition work includes QMP content, responsible author, agile tailoring, mandatory review, and exit readiness.",
                }
            ],
        )

        assert route_plan["route_id"] == expected_route
        for term in expected_terms:
            assert term in query_rewrite["route_terms"]
        assert expected_slots.issubset({slot["slot_id"] for slot in plan["slots"]})


def test_process_operation_route_does_not_hardcode_pep_for_generic_docs():
    from App.api import _session_retrieval_question, _session_route_plan
    from Tool.workflows.answer import parse_question_intent

    question = "SOP 文档的流程如何操作？"
    intent = parse_question_intent(question)
    route_plan = _session_route_plan(question, intent)
    retrieval_question = _session_retrieval_question(question, intent, route_plan).casefold()

    assert route_plan["route_id"] == "process_operation"
    assert "pep" not in route_plan["summary"].casefold()
    assert "pep" not in retrieval_question
    assert "process document" in retrieval_question


def test_process_operation_route_downranks_local_compliance_noise():
    from App.api import _route_aware_retrieval_result
    from Tool.chunking.section_chunks import SectionChunk
    from Tool.retrieval.section_index import RetrievalHit, RetrievalResult

    def chunk(chunk_id: str, title: str, text: str, page: int) -> SectionChunk:
        return SectionChunk(
            chunk_id=chunk_id,
            document_id="mi-pep",
            document_title="MI PEP",
            file_name="MI PEP.pdf",
            section_id=chunk_id,
            section_title=title,
            section_path=[title],
            chunk_type="section",
            text=text,
            quote=text[:500],
            source_refs=[{"document_id": "mi-pep", "fragment_id": f"frag-{chunk_id}", "file_name": "MI PEP.pdf", "anchor_label": f"p.{page}", "quote": text}],
            anchors={"page": page},
            signals=[],
        )

    labeling = RetrievalHit(
        chunk=chunk(
            "sec-labeling",
            "5.13.3 Labeling Requirements 标识要求",
            "China RoHS hazardous substances labeling requirements and Environment-Friendly Use Period symbols for electrical products.",
            26,
        ),
        score=30.0,
        matched_terms=["requirements", "scope"],
    )
    purpose = RetrievalHit(
        chunk=chunk(
            "sec-purpose",
            "1 Purpose and scope / 目的和适用范围",
            "This procedure describes the product development workflow and its applicable scope.",
            5,
        ),
        score=12.0,
        matched_terms=["procedure", "scope"],
    )
    design_output = RetrievalHit(
        chunk=chunk(
            "sec-design-output",
            "4.1 V-model/Requirement Tracing / V 型模式/需求跟踪",
            "Design output procedures shall contain acceptance criteria and support proper functioning of the device.",
            11,
        ),
        score=11.0,
        matched_terms=["procedure", "requirements"],
    )
    transition = RetrievalHit(
        chunk=chunk(
            "sec-transition",
            "7 Provisional solution and backward method / 过渡措施和补救办法",
            "For on-going projects before design review R5, the QMP must specify how and when transition will be made to the process.",
            31,
        ),
        score=10.0,
        matched_terms=["review", "process"],
    )
    result = RetrievalResult(
        question="PEP 文档的流程如何操作？",
        strategy_used="scoped_section_retrieval",
        source_scope={"mode": "selected_docs", "document_ids": ["mi-pep"]},
        hits=[labeling, purpose, design_output, transition],
        evidence_coverage={"documents": ["mi-pep"], "sections": ["sec-labeling", "sec-purpose", "sec-design-output", "sec-transition"], "hit_count": 4},
        trace=[],
    )

    reranked = _route_aware_retrieval_result(result, {"route_id": "process_operation"}, top_k=3)

    section_ids = [hit.chunk.section_id for hit in reranked.hits]
    assert "sec-labeling" not in section_ids
    assert section_ids == ["sec-purpose", "sec-design-output", "sec-transition"]


def test_process_operation_answer_skips_heading_only_evidence():
    from App.api import _session_process_operation_evidence
    from Tool.workflows.answer import EvidenceItem

    heading_only = EvidenceItem(
        evidence_id="ev-heading",
        document_id="mi-pep",
        file_name="MI PEP.pdf",
        section_id="sec-procedure",
        section_title="4 Procedure& Requirement / 过程和需求",
        section_path=["4 Procedure& Requirement / 过程和需求"],
        anchor_label="p.9",
        quote="4 Procedure& Requirement / 过程和需求 4. Procedure& Requirement / 过程和需求",
        source_refs=[{"document_id": "mi-pep", "fragment_id": "frag-heading", "file_name": "MI PEP.pdf", "anchor_label": "p.9", "quote": "4 Procedure& Requirement / 过程和需求"}],
        score=9.0,
        matched_terms=["procedure"],
        signals=[],
    )
    substantive = EvidenceItem(
        evidence_id="ev-output",
        document_id="mi-pep",
        file_name="MI PEP.pdf",
        section_id="sec-output",
        section_title="4.1 V-model/Requirement Tracing / V 型模式/需求跟踪",
        section_path=["4.1 V-model/Requirement Tracing / V 型模式/需求跟踪"],
        anchor_label="p.11",
        quote="Design output procedures shall contain or refer to acceptance criteria and shall ensure proper functioning of the device.",
        source_refs=[{"document_id": "mi-pep", "fragment_id": "frag-output", "file_name": "MI PEP.pdf", "anchor_label": "p.11", "quote": "Design output procedures shall contain acceptance criteria."}],
        score=8.0,
        matched_terms=["procedure"],
        signals=[],
    )

    operation_evidence = _session_process_operation_evidence([
        (heading_only, {"citation_id": "c1"}),
        (substantive, {"citation_id": "c2"}),
    ])

    assert [evidence.evidence_id for _label, evidence, _citation in operation_evidence] == ["ev-output"]


def test_process_overview_route_handles_conceptual_overview_questions():
    from App.api import _session_retrieval_question, _session_route_plan
    from Tool.workflows.answer import parse_question_intent

    question = "PEP 文档的目的和适用范围是什么？"
    intent = parse_question_intent(question)
    route_plan = _session_route_plan(question, intent)
    retrieval_question = _session_retrieval_question(question, intent, route_plan).casefold()

    assert route_plan["route_id"] == "process_overview"
    assert "purpose scope" in retrieval_question
    assert "process model" in retrieval_question
    assert "operation steps" not in retrieval_question


def test_process_overview_fallback_uses_evidence_details_without_fixed_framework():
    from App.api import _session_deterministic_answer
    from Tool.workflows.answer import AnswerEvidencePackage, EvidenceItem

    evidence = EvidenceItem(
        evidence_id="ev-purpose",
        document_id="mi-pep",
        file_name="MI PEP.pdf",
        section_id="sec-purpose",
        section_title="1 Purpose and scope / 目的和适用范围",
        section_path=["1 Purpose and scope / 目的和适用范围"],
        anchor_label="p.5",
        quote="Describes the SSME MI procedure for product development and provides interactions to ensure an integrated high quality process.",
        source_refs=[{"document_id": "mi-pep", "fragment_id": "frag-purpose", "file_name": "MI PEP.pdf", "anchor_label": "p.5", "quote": "Describes the SSME MI procedure for product development."}],
        score=9.0,
        matched_terms=["purpose", "scope"],
        signals=[],
    )
    package = AnswerEvidencePackage(
        question="风险管理在质量管理体系里扮演什么角色？",
        intent={},
        source_scope={"mode": "selected_docs", "document_ids": ["mi-pep"]},
        strategy_used="test",
        evidence_items=[evidence],
        coverage={"document_count": 1},
    )
    citations = [
        {
            "citation_id": "c1",
            "evidence_id": "ev-purpose",
            "document_id": "mi-pep",
            "fragment_id": "frag-purpose",
            "file_name": "MI PEP.pdf",
            "anchor_label": "p.5",
            "quote": evidence.quote,
            "source_context": {"context_before": "", "context_text": evidence.quote, "context_after": "Review outputs confirm records."},
        }
    ]

    answer = _session_deterministic_answer(
        package.question,
        package,
        citations,
        route_plan={"route_id": "process_overview", "summary": "overview"},
    )

    assert "识别与路线" not in answer
    assert "流程操作拆解" not in answer
    assert "关键结论" in answer
    assert "具体含义" in answer
    assert "文档细节" in answer
    assert "\n- 具体含义" not in answer
    assert "\n- 文档细节" not in answer
    assert "Review outputs" in answer


def test_process_overview_route_prioritizes_overview_evidence():
    from App.api import _route_aware_retrieval_result
    from Tool.chunking.section_chunks import SectionChunk
    from Tool.retrieval.section_index import RetrievalHit, RetrievalResult

    def chunk(chunk_id: str, title: str, text: str, page: int) -> SectionChunk:
        return SectionChunk(
            chunk_id=chunk_id,
            document_id="xp-pep",
            document_title="XP PEP",
            file_name="XP PEP.pdf",
            section_id=chunk_id,
            section_title=title,
            section_path=[title],
            chunk_type="section",
            text=text,
            quote=text[:500],
            source_refs=[{"document_id": "xp-pep", "fragment_id": f"frag-{chunk_id}", "file_name": "XP PEP.pdf", "anchor_label": f"p.{page}", "quote": text}],
            anchors={"page": page},
            signals=[],
        )

    local_r2 = RetrievalHit(
        chunk=chunk(
            "sec-r2-local",
            "R2 closer to R3, below procedures must be followed",
            "Interfaces between Process phases: technical expert should join the phase handover review.",
            17,
        ),
        score=30.0,
        matched_terms=["procedure", "process"],
    )
    purpose = RetrievalHit(
        chunk=chunk(
            "sec-purpose",
            "1 Purpose and scope/目的和适用范围",
            "This QR describes the product engineering process and product development process scope.",
            6,
        ),
        score=12.0,
        matched_terms=["purpose", "scope", "process"],
    )
    vmodel = RetrievalHit(
        chunk=chunk(
            "sec-vmodel",
            "5.1 V-model/Requirement Tracing/ V型模式/需求跟踪",
            "The product engineering process follows the V-model and requirement tracing.",
            9,
        ),
        score=8.0,
        matched_terms=["v-model", "process"],
    )
    result = RetrievalResult(
        question="PEP 文档的流程如何操作？",
        strategy_used="scoped_section_retrieval",
        source_scope={"mode": "selected_docs", "document_ids": ["xp-pep"]},
        hits=[local_r2, purpose, vmodel],
        evidence_coverage={"documents": ["xp-pep"], "sections": ["sec-r2-local", "sec-purpose", "sec-vmodel"], "hit_count": 3},
        trace=[],
    )

    reranked = _route_aware_retrieval_result(result, {"route_id": "process_overview"}, top_k=2)

    assert [hit.chunk.section_id for hit in reranked.hits] == ["sec-purpose", "sec-vmodel"]
    assert reranked.strategy_used == "process_overview_route_retrieval"
    assert any("process overview rerank" in item for item in reranked.trace)


def test_session_citations_filter_out_of_scope_or_unanchored_evidence():
    from App.api import _session_citations
    from Tool.workflows.answer import AnswerEvidencePackage, EvidenceItem

    package = AnswerEvidencePackage(
        question="R2 阶段 PO 应该做什么？",
        intent={},
        source_scope={"mode": "selected_docs", "document_ids": ["mi-pep"]},
        strategy_used="scoped_section_retrieval",
        coverage={"documents": ["mi-pep"], "sections": ["sec-r2"], "evidence_count": 4, "missing": []},
        evidence_items=[
            EvidenceItem(
                evidence_id="ev-1",
                document_id="ct-pep",
                file_name="CT PEP.pdf",
                section_id="sec-r2",
                section_title="R2 CT",
                section_path=["R2 CT"],
                anchor_label="p.21",
                quote="CT evidence must not leak into MI selected-doc answers.",
                source_refs=[{"document_id": "ct-pep", "fragment_id": "frag-ct", "file_name": "CT PEP.pdf", "anchor_label": "p.21", "quote": "CT evidence"}],
                score=9.0,
                matched_terms=["R2"],
                signals=["stage_r2"],
            ),
            EvidenceItem(
                evidence_id="ev-2",
                document_id="mi-pep",
                file_name="MI PEP.pdf",
                section_id="sec-r2",
                section_title="R2 MI",
                section_path=["R2 MI"],
                anchor_label="",
                quote="MI evidence without anchor must not become a citation.",
                source_refs=[{"document_id": "mi-pep", "fragment_id": "frag-no-anchor", "file_name": "MI PEP.pdf", "quote": "MI evidence without anchor"}],
                score=8.0,
                matched_terms=["R2"],
                signals=["stage_r2"],
            ),
            EvidenceItem(
                evidence_id="ev-3",
                document_id="mi-pep",
                file_name="MI PEP.pdf",
                section_id="sec-r2",
                section_title="R2 MI",
                section_path=["R2 MI"],
                anchor_label="p.12",
                quote="",
                source_refs=[{"document_id": "mi-pep", "fragment_id": "frag-no-quote", "file_name": "MI PEP.pdf", "anchor_label": "p.12"}],
                score=7.0,
                matched_terms=["R2"],
                signals=["stage_r2"],
            ),
            EvidenceItem(
                evidence_id="ev-4",
                document_id="mi-pep",
                file_name="MI PEP.pdf",
                section_id="sec-r2",
                section_title="R2 MI",
                section_path=["R2 MI"],
                anchor_label="p.13",
                quote="The Product Owner prepares QMP evidence during R2.",
                source_refs=[{"document_id": "mi-pep", "fragment_id": "frag-mi", "file_name": "MI PEP.pdf", "anchor_label": "p.13", "quote": "The Product Owner prepares QMP evidence during R2."}],
                score=6.0,
                matched_terms=["R2", "PO"],
                signals=["stage_r2", "role_product_owner", "deliverable_qmp"],
            ),
        ],
    )

    citations = _session_citations(package, limit=5)

    assert [item["document_id"] for item in citations] == ["mi-pep"]
    assert citations[0]["fragment_id"] == "frag-mi"
    assert citations[0]["anchor_label"] == "p.13"
    assert citations[0]["quote"] == "The Product Owner prepares QMP evidence during R2."


def test_session_answer_keeps_quote_specific_citation_labels():
    from App.api import _session_citations, _session_deterministic_answer
    from Tool.workflows.answer import AnswerEvidencePackage, EvidenceItem

    package = AnswerEvidencePackage(
        question="R2 阶段 PO 应该做什么？",
        intent={},
        source_scope={"mode": "selected_docs", "document_ids": ["mi-pep"]},
        strategy_used="scoped_section_retrieval",
        coverage={"documents": ["mi-pep"], "sections": ["sec-r2"], "evidence_count": 2, "missing": []},
        evidence_items=[
            EvidenceItem(
                evidence_id="ev-quote-1",
                document_id="mi-pep",
                file_name="MI PEP.pdf",
                section_id="sec-r2",
                section_title="R2 MI",
                section_path=["R2 MI"],
                anchor_label="p.13",
                quote="The Product Owner prepares QMP evidence during R2.",
                source_refs=[{"document_id": "mi-pep", "fragment_id": "frag-mi", "file_name": "MI PEP.pdf", "anchor_label": "p.13", "quote": "The Product Owner prepares QMP evidence during R2."}],
                score=8.0,
                matched_terms=["R2", "PO"],
                signals=["stage_r2", "role_product_owner"],
            ),
            EvidenceItem(
                evidence_id="ev-quote-2",
                document_id="mi-pep",
                file_name="MI PEP.pdf",
                section_id="sec-r2",
                section_title="R2 MI",
                section_path=["R2 MI"],
                anchor_label="p.13",
                quote="The Product Owner aligns the plan with required records.",
                source_refs=[{"document_id": "mi-pep", "fragment_id": "frag-mi", "file_name": "MI PEP.pdf", "anchor_label": "p.13", "quote": "The Product Owner aligns the plan with required records."}],
                score=7.0,
                matched_terms=["R2", "PO"],
                signals=["stage_r2", "role_product_owner"],
            ),
        ],
    )

    citations = _session_citations(package, limit=5)
    answer = _session_deterministic_answer(package.question, package, citations)

    assert [item["citation_id"] for item in citations] == ["c1", "c2"]
    assert citations[0]["quote"] == "The Product Owner prepares QMP evidence during R2."
    assert citations[1]["quote"] == "The Product Owner aligns the plan with required records."
    assert "The Product Owner prepares QMP evidence during R2.”[c1]" in answer
    assert "The Product Owner aligns the plan with required records.”[c2]" in answer
