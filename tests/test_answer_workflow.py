from __future__ import annotations

from Tool.chunking.section_chunks import SectionChunk
from Tool.retrieval.section_index import RetrievalHit, RetrievalResult


def _chunk(
    chunk_id: str,
    *,
    chunk_type: str = "section",
    section_id: str | None = "sec-r2",
    section_title: str = "5.3.2 R2 Responsibilities",
    text: str = "At R2, the Product Owner prepares QMP evidence and confirms product definition readiness.",
    quote: str | None = None,
    source_refs: list[dict] | None = None,
    signals: list[str] | None = None,
) -> SectionChunk:
    return SectionChunk(
        chunk_id=chunk_id,
        document_id="ct-pep",
        document_title="CT PEP",
        file_name="ct.pdf",
        section_id=section_id,
        section_title=section_title,
        section_path=[section_title] if section_title else [],
        chunk_type=chunk_type,
        text=text,
        quote=quote or text[:500],
        source_refs=source_refs if source_refs is not None else [
            {
                "document_id": "ct-pep",
                "fragment_id": f"frag-{chunk_id}",
                "file_name": "ct.pdf",
                "section_id": section_id,
                "section_title": section_title,
                "anchor_label": "p.21",
                "anchors": {"page": 21, "paragraph_index": 2},
                "quote": text,
            }
        ],
        anchors={"pages": [21]},
        signals=signals or ["stage_r2", "role_product_owner", "deliverable_qmp"],
    )


def test_question_intent_detects_role_action_guidance_and_normalizes_terms():
    from Tool.workflows.answer import parse_question_intent

    intent = parse_question_intent("R2阶段我作为PO应该做什么")

    assert intent.intent_type == "role_action_guidance"
    assert intent.normalized_terms["stage"] == ["R2"]
    assert intent.normalized_terms["role"] == ["Product Owner"]
    assert intent.reference_density == "high"
    assert intent.risk_level == "process_compliance"
    assert intent.requires_abstention_check is True


def test_question_intent_recognizes_gate6_mvp_intent_types():
    from Tool.workflows.answer import parse_question_intent

    cases = [
        ("PEP流程如何操作", "process_explanation"),
        ("7.16 在哪个文件哪个章节", "reference_lookup"),
        ("CT 和 XP 的 R2 有什么差异", "bu_comparison"),
        ("QMP 是什么", "definition_lookup"),
        ("现在证据够不够，还缺什么", "gap_check"),
    ]

    for question, expected in cases:
        assert parse_question_intent(question).intent_type == expected


def test_enterprise_terms_can_merge_question_terms_and_chunk_signals():
    from Tool.workflows.answer import normalize_enterprise_terms

    terms = normalize_enterprise_terms(
        "PO 在 R2 要准备 QMP，参考 7.16 和 M150",
        chunk_signals=["stage_r3", "role_project_manager", "bu_ct"],
    )

    assert terms["stage"] == ["R2", "R3"]
    assert terms["role"] == ["Product Owner", "Project Manager"]
    assert terms["deliverable"] == ["QMP"]
    assert terms["milestone"] == ["M150"]
    assert terms["section"] == ["7.16"]
    assert terms["bu"] == ["CT"]


def test_answer_evidence_package_keeps_primary_source_refs_and_skips_history():
    from Tool.workflows.answer import build_answer_evidence_package, parse_question_intent

    intent = parse_question_intent("R2阶段我作为PO应该做什么")
    r2_hit = RetrievalHit(chunk=_chunk("r2"), score=9.5, matched_terms=["R2", "Product Owner", "QMP"])
    history_hit = RetrievalHit(
        chunk=_chunk(
            "history",
            chunk_type="document_history",
            section_id="sec-history",
            section_title="0 History / 修改历史",
            text="Template change: add Product Owner check item in the R2 template.",
            signals=["document_history", "stage_r2", "role_product_owner"],
        ),
        score=3.0,
        matched_terms=["R2", "Product Owner"],
    )
    no_ref_hit = RetrievalHit(
        chunk=_chunk("no-ref", source_refs=[], text="R2 evidence without source refs."),
        score=2.0,
        matched_terms=["R2"],
    )
    result = RetrievalResult(
        question="R2阶段我作为PO应该做什么",
        strategy_used="scoped_section_retrieval",
        source_scope={"mode": "selected_docs", "document_ids": ["ct-pep"]},
        hits=[r2_hit, history_hit, no_ref_hit],
        evidence_coverage={"documents": ["ct-pep"], "sections": ["sec-r2", "sec-history"], "hit_count": 3},
        trace=["query normalized"],
    )

    package = build_answer_evidence_package(result, intent=intent)

    assert package.question == "R2阶段我作为PO应该做什么"
    assert package.strategy_used == "scoped_section_retrieval"
    assert len(package.evidence_items) == 1
    evidence = package.evidence_items[0]
    assert evidence.document_id == "ct-pep"
    assert evidence.file_name == "ct.pdf"
    assert evidence.section_id == "sec-r2"
    assert evidence.anchor_label == "p.21"
    assert "Product Owner prepares QMP evidence" in evidence.quote
    assert evidence.supports == ["stage", "role", "deliverable"]
    assert package.coverage["documents"] == ["ct-pep"]
    assert package.coverage["sections"] == ["sec-r2"]
    assert not package.missing_evidence


def test_answer_evidence_package_reports_missing_required_terms():
    from Tool.workflows.answer import build_answer_evidence_package, parse_question_intent

    intent = parse_question_intent("R2阶段我作为PO应该做什么")
    result = RetrievalResult(
        question="R2阶段我作为PO应该做什么",
        strategy_used="scoped_section_retrieval",
        source_scope={"mode": "selected_docs", "document_ids": ["ct-pep"]},
        hits=[
            RetrievalHit(
                chunk=_chunk(
                    "r2-no-role",
                    text="At R2, project readiness is reviewed.",
                    signals=["stage_r2"],
                ),
                score=4.0,
                matched_terms=["R2"],
            )
        ],
        evidence_coverage={"documents": ["ct-pep"], "sections": ["sec-r2"], "hit_count": 1},
        trace=[],
    )

    package = build_answer_evidence_package(result, intent=intent)

    missing_by_type = {item["term_type"]: item["terms"] for item in package.missing_evidence}
    assert missing_by_type["role"] == ["Product Owner"]