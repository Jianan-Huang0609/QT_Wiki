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
        ("这个表格里 R2 的交付物是什么", "table_lookup"),
        ("总结一下这份流程文档", "summary_request"),
        ("R4到R5之间需要完成哪些工作？", "stage_transition_work"),
        ("QMP需要包含哪些内容？谁负责撰写QMP？", "deliverable_detail"),
        ("采用敏捷方法开发，可以裁剪哪些评审？哪些评审不可被裁剪？", "tailoring_policy"),
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


def test_answer_evidence_package_prefers_chunk_quote_over_title_only_ref():
    from Tool.workflows.answer import build_answer_evidence_package, parse_question_intent

    intent = parse_question_intent("PEP 文档的流程如何操作？")
    chunk = _chunk(
        "overview",
        section_id="sec-overview",
        section_title="1 Purpose and scope/目的和适用范围",
        text="1 Purpose and scope/目的和适用范围\nThis QR describes the product engineering process and product development process scope.",
        quote="1 Purpose and scope/目的和适用范围 This QR describes the product engineering process and product development process scope.",
        source_refs=[
            {
                "document_id": "ct-pep",
                "fragment_id": "frag-title",
                "file_name": "ct.pdf",
                "section_id": "sec-overview",
                "section_title": "1 Purpose and scope/目的和适用范围",
                "anchor_label": "p.6",
                "anchors": {"page": 6, "paragraph_index": 1},
                "quote": "1 Purpose and scope/目的和适用范围",
            }
        ],
        signals=[],
    )
    result = RetrievalResult(
        question="PEP 文档的流程如何操作？",
        strategy_used="process_overview_route_retrieval",
        source_scope={"mode": "selected_docs", "document_ids": ["ct-pep"]},
        hits=[RetrievalHit(chunk=chunk, score=8.0, matched_terms=["purpose", "scope"])],
        evidence_coverage={"documents": ["ct-pep"], "sections": ["sec-overview"], "hit_count": 1},
        trace=[],
    )

    package = build_answer_evidence_package(result, intent=intent)

    assert len(package.evidence_items) == 1
    assert "product engineering process" in package.evidence_items[0].quote
    assert package.evidence_items[0].source_refs[0]["quote"] == "1 Purpose and scope/目的和适用范围"


def test_answer_evidence_package_selects_question_relevant_passage():
    from Tool.workflows.answer import build_answer_evidence_package, parse_question_intent

    intent = parse_question_intent("PEP 文档的流程如何操作？")
    text = (
        "1 Purpose and scope. This opening paragraph describes the document scope and applicability. "
        "It is useful background, but it does not describe the user's operational question.\n\n"
        "4 Procedure and Requirement. To operate the PEP workflow, confirm the applicable scope, follow the development phases, "
        "prepare evidence for the required reviews, and verify deliverables before moving to the next process phase."
    )
    chunk = _chunk(
        "operation-passage",
        section_id="sec-procedure",
        section_title="4 Procedure and Requirement",
        text=text,
        quote=text[:120],
        source_refs=[
            {
                "document_id": "ct-pep",
                "fragment_id": "frag-procedure-title",
                "file_name": "ct.pdf",
                "section_id": "sec-procedure",
                "section_title": "4 Procedure and Requirement",
                "anchor_label": "p.12",
                "anchors": {"page": 12, "paragraph_index": 3},
                "quote": "4 Procedure and Requirement",
            }
        ],
        signals=[],
    )
    result = RetrievalResult(
        question="PEP 文档的流程如何操作？",
        strategy_used="process_operation_route_retrieval",
        source_scope={"mode": "selected_docs", "document_ids": ["ct-pep"]},
        hits=[RetrievalHit(chunk=chunk, score=9.0, matched_terms=["operate", "workflow", "phase", "deliverables"])],
        evidence_coverage={"documents": ["ct-pep"], "sections": ["sec-procedure"], "hit_count": 1},
        trace=[],
    )

    package = build_answer_evidence_package(result, intent=intent)

    quote = package.evidence_items[0].quote
    assert "To operate the PEP workflow" in quote
    assert "verify deliverables" in quote
    assert "opening paragraph" not in quote


def test_answer_evidence_package_skips_short_heading_like_passage():
    from Tool.workflows.answer import build_answer_evidence_package, parse_question_intent

    intent = parse_question_intent("这份流程文档的目的和适用范围是什么？")
    text = (
        "1 Purpose and scope/目的和适用范围 1.\n\n"
        "This procedure is effective for the selected product family and defines the applicable scope, "
        "responsibilities, and process requirements that must be followed by development projects."
    )
    chunk = _chunk(
        "purpose-substantive",
        section_id="sec-purpose",
        section_title="1 Purpose and scope/目的和适用范围",
        text=text,
        quote="1 Purpose and scope/目的和适用范围 1.",
        source_refs=[
            {
                "document_id": "ct-pep",
                "fragment_id": "frag-purpose-title",
                "file_name": "ct.pdf",
                "section_id": "sec-purpose",
                "section_title": "1 Purpose and scope/目的和适用范围",
                "anchor_label": "p.6",
                "anchors": {"page": 6, "paragraph_index": 1},
                "quote": "1 Purpose and scope/目的和适用范围 1.",
            }
        ],
        signals=[],
    )
    result = RetrievalResult(
        question="这份流程文档的目的和适用范围是什么？",
        strategy_used="process_overview_route_retrieval",
        source_scope={"mode": "selected_docs", "document_ids": ["ct-pep"]},
        hits=[RetrievalHit(chunk=chunk, score=8.0, matched_terms=["purpose", "scope"])],
        evidence_coverage={"documents": ["ct-pep"], "sections": ["sec-purpose"], "hit_count": 1},
        trace=[],
    )

    package = build_answer_evidence_package(result, intent=intent)

    quote = package.evidence_items[0].quote
    assert "applicable scope" in quote
    assert quote != "1 Purpose and scope/目的和适用范围 1."


def test_answer_evidence_package_prefers_prose_over_table_like_fragment():
    from Tool.workflows.answer import build_answer_evidence_package, parse_question_intent

    intent = parse_question_intent("这份流程文档如何操作？")
    text = (
        "This procedure describes the process model and lifecycle sequence that teams follow when operating the workflow.\n\n"
        "integration test specification Component test specification Single function test Subsystem integration Risk analysis "
        "Check the actions from the risk analysis * *2 Traceability of requirements from the PRS and FS *3"
    )
    chunk = _chunk(
        "prose-vs-table",
        section_id="sec-model",
        section_title="5.1 Process model / lifecycle",
        text=text,
        quote=text[:120],
        source_refs=[
            {
                "document_id": "ct-pep",
                "fragment_id": "frag-model",
                "file_name": "ct.pdf",
                "section_id": "sec-model",
                "section_title": "5.1 Process model / lifecycle",
                "anchor_label": "p.9",
                "anchors": {"page": 9, "paragraph_index": 2},
                "quote": text,
            }
        ],
        signals=[],
    )
    result = RetrievalResult(
        question="这份流程文档如何操作？",
        strategy_used="process_operation_route_retrieval",
        source_scope={"mode": "selected_docs", "document_ids": ["ct-pep"]},
        hits=[RetrievalHit(chunk=chunk, score=8.0, matched_terms=["process model", "lifecycle", "traceability", "requirements"])],
        evidence_coverage={"documents": ["ct-pep"], "sections": ["sec-model"], "hit_count": 1},
        trace=[],
    )

    package = build_answer_evidence_package(result, intent=intent)

    quote = package.evidence_items[0].quote
    assert "process model and lifecycle sequence" in quote
    assert "Component test specification" not in quote


def test_answer_evidence_package_strips_repeated_section_heading_prefix():
    from Tool.workflows.answer import build_answer_evidence_package, parse_question_intent

    intent = parse_question_intent("这份流程文档如何操作？")
    text = (
        "5.1 V-model/Requirement Tracing/ V型模式/需求跟踪 "
        "5.1 V-model/Requirement Tracing/ V型模式/需求跟踪 "
        "This QR describes the product engineering process based on the V-model of product engineering."
    )
    chunk = _chunk(
        "repeated-heading",
        section_id="sec-model",
        section_title="5.1 V-model/Requirement Tracing/ V型模式/需求跟踪",
        text=text,
        quote=text,
        source_refs=[
            {
                "document_id": "ct-pep",
                "fragment_id": "frag-model",
                "file_name": "ct.pdf",
                "section_id": "sec-model",
                "section_title": "5.1 V-model/Requirement Tracing/ V型模式/需求跟踪",
                "anchor_label": "p.9",
                "anchors": {"page": 9, "paragraph_index": 2},
                "quote": text,
            }
        ],
        signals=[],
    )
    result = RetrievalResult(
        question="这份流程文档如何操作？",
        strategy_used="process_operation_route_retrieval",
        source_scope={"mode": "selected_docs", "document_ids": ["ct-pep"]},
        hits=[RetrievalHit(chunk=chunk, score=8.0, matched_terms=["process", "V-model"])],
        evidence_coverage={"documents": ["ct-pep"], "sections": ["sec-model"], "hit_count": 1},
        trace=[],
    )

    package = build_answer_evidence_package(result, intent=intent)

    quote = package.evidence_items[0].quote
    assert quote.startswith("This QR describes")
    assert "5.1 V-model" not in quote


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