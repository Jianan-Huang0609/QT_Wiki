from __future__ import annotations

from copy import deepcopy
from typing import Any

FAILURE_RECORD_PATH = "Design/review-artifacts/release0-smoke-failures.md"


def release0_smoke_catalog() -> dict[str, Any]:
    return {
        "schema_version": "release0-smoke-cases-v0.1",
        "purpose": "Fixed CT/MI/XP smoke questions for Release-0 trusted selected-doc chat validation.",
        "failure_record_path": FAILURE_RECORD_PATH,
        "cases": deepcopy(_CASES),
    }


def release0_smoke_cases() -> list[dict[str, Any]]:
    return release0_smoke_catalog()["cases"]


def release0_retrieval_eval_cases() -> list[dict[str, Any]]:
    retrieval_cases: list[dict[str, Any]] = []
    for case in _CASES:
        retrieval_cases.append(
            {
                "case_id": case["case_id"],
                "question": case["question"],
                "source_scope": _retrieval_source_scope(case["source_scope"]),
                "expected_section_terms_any": list(case["expected_evidence"].get("section_terms_any", [])),
                "expected_terms_any": list(case["expected_evidence"].get("terms_any", [])),
            }
        )
    return retrieval_cases


def _case(
    case_id: str,
    *,
    question: str,
    case_kind: str,
    document_aliases: list[str],
    expected_route_id: str,
    terms_any: list[str],
    section_terms_any: list[str] | None = None,
    min_citation_count: int = 2,
    priority: str = "P0",
    manual_judgement: str,
) -> dict[str, Any]:
    return {
        "case_id": case_id,
        "priority": priority,
        "case_kind": case_kind,
        "question": question,
        "source_scope": {
            "mode": "multi_docs" if len(document_aliases) > 1 else "selected_docs",
            "document_aliases": document_aliases,
        },
        "expected_route_id": expected_route_id,
        "min_citation_count": min_citation_count,
        "expected_evidence": {
            "terms_any": terms_any,
            "section_terms_any": section_terms_any or [],
            "must_have_quote": True,
            "must_have_source_context": True,
        },
        "manual_judgement": manual_judgement,
        "failure_record": {
            "path": FAILURE_RECORD_PATH,
            "section": case_id,
        },
    }


def _retrieval_source_scope(source_scope: dict[str, Any]) -> dict[str, Any]:
    return {
        "mode": "selected_docs" if source_scope["mode"] in {"selected_docs", "multi_docs"} else source_scope["mode"],
        "document_ids": list(source_scope["document_aliases"]),
    }


_CASES: list[dict[str, Any]] = [
    _case(
        "r0-ct-process-operation",
        question="CT PEP 文档的流程如何操作？",
        case_kind="single_doc",
        document_aliases=["ct_pep"],
        expected_route_id="process_operation",
        section_terms_any=["Purpose", "scope", "process", "V-model", "General requirements"],
        terms_any=["operation", "process", "lifecycle", "verification", "validation"],
        manual_judgement="Answer should describe the operating flow with concrete actions and citations only from CT PEP.",
    ),
    _case(
        "r0-mi-r2-po-guidance",
        question="MI PEP 里 R2 阶段作为 PO 应该做什么？",
        case_kind="single_doc",
        document_aliases=["mi_pep"],
        expected_route_id="role_action_guidance",
        section_terms_any=["R2", "Planning", "Product Owner"],
        terms_any=["R2", "Product Owner", "PO", "responsible", "deliverable"],
        manual_judgement="Answer should identify PO-related R2 responsibilities and avoid using evidence from other PEP files.",
    ),
    _case(
        "r0-ct-section-716-reference",
        question="CT PEP 的 7.16 法规核准计划在哪里？关键内容是什么？",
        case_kind="single_doc",
        document_aliases=["ct_pep"],
        expected_route_id="reference_lookup",
        section_terms_any=["7.16", "Regulatory Approval Plan"],
        terms_any=["regulatory", "approval", "plan", "submission"],
        manual_judgement="Answer should locate section 7.16, summarize its key content, and show page/anchor citation.",
    ),
    _case(
        "r0-mi-r4-r5-transition",
        question="MI PEP 中 R4 到 R5 之间需要完成哪些工作？",
        case_kind="single_doc",
        document_aliases=["mi_pep"],
        expected_route_id="stage_transition_work",
        section_terms_any=["R4", "R5", "review", "verification", "validation", "确认", "系统测试", "设计转移"],
        terms_any=["R4", "R5", "transition", "work", "entry", "exit", "readiness"],
        manual_judgement="Answer should list transition work items and readiness/exit evidence, not a generic section summary.",
    ),
    _case(
        "r0-mi-qmp-deliverable",
        question="MI PEP 中 QMP 需要包含哪些内容？谁负责撰写 QMP？",
        case_kind="single_doc",
        document_aliases=["mi_pep"],
        expected_route_id="deliverable_detail",
        section_terms_any=["QMP", "Quality Management Plan", "responsibility"],
        terms_any=["QMP", "quality management plan", "content", "owner", "responsible", "author"],
        manual_judgement="Answer should separate required contents from owner/author responsibility and cite each claim.",
    ),
    _case(
        "r0-xp-agile-tailoring",
        question="XP PEP 采用敏捷方法开发，可以裁剪哪些评审？哪些评审不可被裁剪？",
        case_kind="single_doc",
        document_aliases=["xp_pep"],
        expected_route_id="tailoring_policy",
        section_terms_any=["agile", "tailoring", "review"],
        terms_any=["agile", "tailoring", "review", "mandatory", "cannot be tailored"],
        manual_judgement="Answer should distinguish tailorable and non-tailorable reviews with explicit uncertainty when evidence is incomplete.",
    ),
    _case(
        "r0-mi-unknown-fallback",
        question="MI PEP 里项目启动前有哪些容易被遗漏但影响后续质量门的准备事项？",
        case_kind="unknown_fallback",
        document_aliases=["mi_pep"],
        expected_route_id="generic_rag",
        section_terms_any=["planning", "preparation", "quality", "review"],
        terms_any=["preparation", "quality", "risk", "review", "evidence"],
        min_citation_count=1,
        manual_judgement="Fallback should provide a bounded answer with citations and uncertainty instead of inventing a new fixed route.",
    ),
    _case(
        "r0-ct-mi-xp-stage-comparison",
        question="CT、MI、XP 三份 PEP 对 R4 到 R5 阶段转换要求有什么相同点和差异？",
        case_kind="multi_doc_comparison",
        document_aliases=["ct_pep", "mi_pep", "xp_pep"],
        expected_route_id="bu_comparison",
        section_terms_any=["R4", "R5", "review", "verification", "validation"],
        terms_any=["same", "different", "R4", "R5", "transition", "review"],
        min_citation_count=3,
        priority="P1",
        manual_judgement="Answer should group citations by document, compare same/different/open gaps, and avoid unsupported cross-document claims.",
    ),
]