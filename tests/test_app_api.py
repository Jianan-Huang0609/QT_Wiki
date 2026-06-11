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
