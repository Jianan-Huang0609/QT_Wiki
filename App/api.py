from __future__ import annotations

import json
import re
import threading
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from App.agents.ingest_agent import IngestAgent
from App.agents.lint_agent import LintAgent
from App.agents.query_agent import QueryAgent
from App.agents.structured_knowledge import (
    build_mapping_matrix,
    build_slides_outline,
    build_structured_context,
)
from App.schemas import (
    AgentUploadResponse,
    ChatQueryRequest,
    ChatQueryResponse,
    DashboardResponse,
    HealthResponse,
    ReviewPackageDecisionRequest,
    ReviewPackageRelationDecisionRequest,
    SessionQueryRequest,
)
from Tool.document_processor import process_document
from Tool.contracts.canonical import load_canonical_document
from Tool.chunking.section_chunks import build_section_chunks
from Tool.pipelines.common import PARSED_DIR
from Tool.retrieval.retrievers import FullTextRetriever, HybridRetriever, RuleSectionRetriever
from Tool.workflows.answer import AnswerEvidencePackage, EvidenceItem, build_answer_evidence_package, parse_question_intent
from Tool.workflows.document_parse import build_parse_workflow_summary
from Tool.workflows.route_catalog import get_route_entry, route_answer_slot_dicts, route_query_terms
from wiki.builders.bootstrap import PAGE_BLUEPRINTS, bootstrap_pages
from wiki.indexing import build_index, load_page_index, rank_page_index
from wiki.models.page import WikiPage
from wiki.store import (
    PAGE_DIR,
    list_review_packages,
    load_all_pages,
    load_page,
    render_page_markdown,
    update_review_package_decision,
    update_review_package_relation_decision,
)

try:
    from fastapi import FastAPI, File, Form, HTTPException, UploadFile
    from fastapi.middleware.cors import CORSMiddleware
except ModuleNotFoundError as exc:  # pragma: no cover - runtime guard
    raise RuntimeError(
        "FastAPI is required to run App.api. Install fastapi, uvicorn, and python-multipart first."
    ) from exc


REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = REPO_ROOT / "Raw"
RUN_DIR = REPO_ROOT / "App" / "output" / "runs"
INDEX_DIR = PAGE_DIR.parent / "index"
INDEX_PAGE_PATH = INDEX_DIR / "pages.jsonl"
INDEX_TERMS_PATH = INDEX_DIR / "terms.json"
INDEX_SOURCES_PATH = INDEX_DIR / "sources.jsonl"
_BOOTSTRAP_LOCK = threading.Lock()
DEFAULT_MODEL_PROFILE = "azure-gpt-5.4"
MODEL_PROFILE_CONFIGS = {
    "azure-gpt-4o": "config/azure_gpt4o_config.json",
    "azure-gpt-5": "config/azure_gpt5_config.json",
    "azure-gpt-5.4": "config/azure_gpt5_4_config.json",
    "azure-gpt-5.5": "config/azure_gpt5_5_config.json",
    "azure-gpt-5-multimodal": "config/azure_gpt5_multimodal_config.json",
}

app = FastAPI(title="QT Wiki API", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(status="ok")


@app.get("/api/dashboard", response_model=DashboardResponse)
def dashboard() -> DashboardResponse:
    ingest_agent = IngestAgent()
    lint_agent = LintAgent()
    pages = _ensure_runtime_ready()
    candidates = ingest_agent.list_candidates()
    review_packages = list_review_packages()
    issues = _lint_items(lint_agent.run_health_check(use_llm=False))
    index_status = _build_index_status()
    return DashboardResponse(
        agents=_agent_summaries(candidates, review_packages, issues),
        index=index_status,
        pages=[_wiki_page_payload(page) for page in pages[:12]],
        issues=issues,
    )


@app.get("/api/ingest/candidates")
def ingest_candidates() -> dict[str, list[dict[str, Any]]]:
    agent = IngestAgent()
    items = [_candidate_payload(candidate) for candidate in agent.list_candidates()]
    items.sort(key=lambda item: (item["status"] != "pending", -item["confidence"], item["title"]))
    return {"items": items}


@app.get("/api/ingest/review-packages")
def ingest_review_packages() -> dict[str, list[dict[str, Any]]]:
    items = [_review_package_payload(item) for item in list_review_packages()]
    items.sort(key=lambda item: (item["status"] != "pending_review", item["title"]))
    return {"items": items}


@app.get("/api/ingest/runs")
def ingest_runs(limit: int = 12) -> dict[str, list[dict[str, Any]]]:
    return {"items": _load_recent_runs(limit=max(1, min(limit, 50)))}


@app.post("/api/ingest/review-packages/{package_id}/decision")
def decide_review_package(package_id: str, payload: ReviewPackageDecisionRequest) -> dict[str, Any]:
    existing = next((item for item in list_review_packages() if item.package_id == package_id), None)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Review package not found: {package_id}")

    reviewed_at = datetime.now().isoformat(timespec="seconds")

    review_package = update_review_package_decision(
        package_id,
        identity_decision=payload.identity_decision.value,
        confirmed_business_type=payload.confirmed_business_type or "",
        confirmed_effective_level=payload.confirmed_effective_level or "",
        confirmed_is_binding=payload.confirmed_is_binding,
        review_notes=payload.review_notes,
        reviewed_by=payload.reviewed_by,
        reviewed_at=reviewed_at,
    )
    return {"ok": True, "item": _review_package_payload(review_package)}


@app.post("/api/ingest/review-packages/{package_id}/relations/decision")
def decide_review_package_relations(package_id: str, payload: ReviewPackageRelationDecisionRequest) -> dict[str, Any]:
    existing = next((item for item in list_review_packages() if item.package_id == package_id), None)
    if existing is None:
        raise HTTPException(status_code=404, detail=f"Review package not found: {package_id}")
    if existing.identity_decision != "confirmed":
        raise HTTPException(status_code=409, detail="identity must be confirmed before relation review")
    if not getattr(existing, "extracted_relations", []):
        raise HTTPException(status_code=409, detail="no extracted relations available for review")

    relation_reviewed_at = datetime.now().isoformat(timespec="seconds")

    review_package = update_review_package_relation_decision(
        package_id,
        relation_decision=payload.relation_decision.value,
        relation_review_notes=payload.relation_review_notes,
        relation_reviewed_by=payload.relation_reviewed_by,
        relation_reviewed_at=relation_reviewed_at,
    )
    return {"ok": True, "item": _review_package_payload(review_package)}


@app.post("/api/ingest/candidates/{candidate_id}/approve")
def approve_candidate(candidate_id: str) -> dict[str, Any]:
    agent = IngestAgent()
    if not agent.can_approve_candidate(candidate_id):
        raise HTTPException(
            status_code=409,
            detail=f"Candidate cannot be published before identity and relation review gates are satisfied: {candidate_id}",
        )
    if not agent.approve_candidate(candidate_id):
        raise HTTPException(status_code=404, detail=f"Candidate not found or not pending: {candidate_id}")
    return {"ok": True, "candidate_id": candidate_id}


@app.post("/api/ingest/candidates/{candidate_id}/reject")
def reject_candidate(candidate_id: str) -> dict[str, Any]:
    agent = IngestAgent()
    if not agent.reject_candidate(candidate_id):
        raise HTTPException(status_code=404, detail=f"Candidate not found: {candidate_id}")
    return {"ok": True, "candidate_id": candidate_id}


@app.get("/api/wiki/pages")
def wiki_pages() -> dict[str, list[dict[str, Any]]]:
    pages = [_wiki_page_payload(page) for page in _ensure_runtime_ready()]
    pages.sort(key=lambda item: item["title"])
    return {"items": pages}


@app.get("/api/documents/{document_id}/parse-summary")
def document_parse_summary(document_id: str) -> dict[str, Any]:
    canonical = _load_parsed_document(document_id)
    workflow = _parse_workflow_payload(canonical)
    return {
        "document_id": canonical.document.document_id,
        "file_name": canonical.document.file_name,
        "title": canonical.document.title,
        "parse_status": workflow.get("parse_status", canonical.parse_status),
        "section_count": len(canonical.sections),
        "fragment_count": len(canonical.fragments),
        "table_count": len(canonical.tables),
        "structure_quality": workflow.get("structure_quality", {}),
        "eval_summary": workflow.get("eval_summary", {}),
        "review_items": workflow.get("review_items", []),
        "visual_review_items": workflow.get("visual_review_items", []),
        "parse_workflow": workflow,
    }


@app.get("/api/documents/{document_id}/sections")
def document_sections(document_id: str) -> dict[str, Any]:
    canonical = _load_parsed_document(document_id)
    fragment_counts: dict[str | None, int] = {}
    for fragment in canonical.fragments:
        fragment_counts[fragment.section_id] = fragment_counts.get(fragment.section_id, 0) + 1
    return {
        "document_id": canonical.document.document_id,
        "items": [
            {
                "section_id": section.section_id,
                "title": section.title,
                "level": section.level,
                "parent_id": section.parent_id,
                "page_range": section.page_range,
                "fragment_count": fragment_counts.get(section.section_id, 0),
            }
            for section in canonical.sections
        ],
    }


@app.get("/api/documents/{document_id}/chunks")
def document_chunks(document_id: str, max_chars: int = 1800) -> dict[str, Any]:
    canonical = _load_parsed_document(document_id)
    chunks = build_section_chunks(canonical, max_chars=max(200, min(max_chars, 8000)))
    return {
        "document_id": canonical.document.document_id,
        "chunk_count": len(chunks),
        "items": [chunk.to_dict() for chunk in chunks],
    }


@app.get("/api/session/handoff/{document_id}")
def session_handoff(document_id: str, max_chars: int = 1800, preview_limit: int = 12) -> dict[str, Any]:
    canonical = _load_parsed_document(document_id)
    workflow = _parse_workflow_payload(canonical)
    chunks = build_section_chunks(canonical, max_chars=max(200, min(max_chars, 8000)))
    preview_chunks = chunks[: max(1, min(preview_limit, 50))]
    return {
        "schema_version": "session-handoff-v0.1",
        "document_id": canonical.document.document_id,
        "source": _handoff_source(canonical, workflow, chunks),
        "tree": _handoff_tree(canonical, chunks, workflow),
        "graph": _handoff_graph(canonical, chunks),
        "retrieval": _handoff_retrieval(chunks, preview_chunks),
        "chat": _handoff_chat_contract(canonical),
        "quality": _handoff_quality(workflow),
    }


@app.post("/api/session/query", response_model=ChatQueryResponse)
def session_query(payload: SessionQueryRequest) -> ChatQueryResponse:
    source_scope = _normalize_session_source_scope(payload.source_scope)
    canonicals = _load_session_canonicals(source_scope)
    chunks = [chunk for canonical in canonicals for chunk in build_section_chunks(canonical)]
    intent = parse_question_intent(payload.question)
    route_plan = _session_route_plan(payload.question, intent)
    query_rewrite = _session_query_rewrite(payload.question, intent, route_plan)
    retrieval_question = str(query_rewrite["rewritten_query"])
    tool_plan = _session_tool_plan(route_plan=route_plan, query_rewrite=query_rewrite, source_scope=source_scope, use_llm=payload.use_llm)
    retrieval_result = _session_retrieve_sections(
        retrieval_question,
        chunks,
        source_scope=source_scope,
        top_k=_session_retrieval_top_k(payload.top_k, route_plan),
    )
    retrieval_result = _route_aware_retrieval_result(retrieval_result, route_plan, top_k=payload.top_k)
    retrieval_result.question = payload.question
    retrieval_result.trace.append(f"source scope: {source_scope['mode']}")
    if retrieval_question != payload.question:
        retrieval_result.trace.append(f"route query expanded for {route_plan['route_id']}")
    evidence_package = build_answer_evidence_package(retrieval_result, intent=intent)
    citations, citation_validation = _session_citations_with_validation(
        evidence_package,
        limit=payload.top_k_citations,
        chunks=chunks,
    )
    answer_plan = _session_answer_plan(route_plan=route_plan, evidence_package=evidence_package, citations=citations)
    used_llm = False
    llm_error = ""
    if payload.use_llm and citations:
        try:
            answer = _session_llm_answer(
                payload.question,
                evidence_package,
                citations,
                model_profile=payload.model_profile,
                route_plan=route_plan,
                answer_plan=answer_plan,
            )
            used_llm = True
        except Exception as exc:
            llm_error = str(exc)
            answer = _session_deterministic_answer(payload.question, evidence_package, citations, route_plan=route_plan)
    else:
        answer = _session_deterministic_answer(payload.question, evidence_package, citations, route_plan=route_plan)
    confidence = _session_confidence(evidence_package, citations)
    return ChatQueryResponse(
        answer=answer,
        confidence=confidence,
        used_llm=used_llm,
        matched_pages=_session_matched_sections(evidence_package),
        citations=citations,
        structured_matches=[evidence_package.to_dict()],
        suggested_questions=_session_suggested_questions(payload.question, canonicals),
        trace=[
            f"load {len(canonicals)} parsed documents",
            f"build {len(chunks)} section chunks",
            *evidence_package.trace,
            _session_citation_trace(citation_validation),
            _session_llm_trace(payload.use_llm, used_llm, payload.model_profile, llm_error),
        ],
        answer_run=_session_answer_run(
            question=payload.question,
            source_scope=source_scope,
            canonicals=canonicals,
            chunk_count=len(chunks),
            intent=intent,
            route_plan=route_plan,
            retrieval_question=retrieval_question,
            query_rewrite=query_rewrite,
            tool_plan=tool_plan,
            evidence_package=evidence_package,
            citations=citations,
            citation_validation=citation_validation,
            answer_plan=answer_plan,
            answer=answer,
            confidence=confidence,
            used_llm=used_llm,
            model_profile=payload.model_profile,
            llm_error=llm_error,
        ),
    )


@app.post("/chat/reindex")
def reindex() -> dict[str, Any]:
    pages = _ensure_runtime_ready(force_bootstrap_if_empty=True)
    if pages:
        build_index(pages=pages, index_dir=INDEX_DIR)
    return _build_index_status()


@app.post("/chat/query", response_model=ChatQueryResponse)
def chat_query(payload: ChatQueryRequest) -> ChatQueryResponse:
    question = payload.question
    use_llm = payload.use_llm
    top_k_pages = payload.top_k_pages
    top_k_citations = payload.top_k_citations

    pages = _ensure_runtime_ready()
    entries = load_page_index()
    if not entries and pages:
        build_index(pages=pages, index_dir=INDEX_DIR)
        entries = load_page_index()

    ranked_entries = rank_page_index(question, entries, limit=top_k_pages)
    matched_pages_data = _pages_from_ranked_entries(ranked_entries)
    structured_context = build_structured_context(question, package_limit=min(top_k_pages, 4), relation_limit=8)
    citations = _collect_citations(matched_pages_data, limit=top_k_citations)
    citations = _append_structured_citations(citations, structured_context, limit=top_k_citations)
    matched_pages = [
        {
            "page_id": entry.get("page_id", ""),
            "title": entry.get("title", ""),
            "page_type": entry.get("page_type", ""),
            "summary": entry.get("summary", ""),
            "score": float(entry.get("relevance_score", 0.0)),
        }
        for entry in ranked_entries
    ]

    if use_llm:
        answer_result = QueryAgent(config_path=_model_config_path(payload.model_profile)).query(question, use_llm=True, interactive=False)
        answer_text = answer_result.answer_text
        confidence_value = answer_result.confidence
        used_llm = answer_result.used_llm
    else:
        answer_text = _deterministic_answer(question, matched_pages_data, citations, structured_context)
        confidence_value = 0.72 if structured_context.get("relations") else (
            min(1.0, sum(item["score"] for item in matched_pages[:3]) / 18) if matched_pages else 0.0
        )
        used_llm = False

    return ChatQueryResponse(
        answer=answer_text,
        confidence=_confidence_label(confidence_value),
        used_llm=used_llm,
        matched_pages=matched_pages,
        citations=citations,
        structured_matches=structured_context["packages"],
        suggested_questions=_suggested_questions(question, matched_pages, structured_context),
        trace=[
            f"wiki pages ready: {len(pages)}",
            "load pages.jsonl",
            f"rank top {len(matched_pages)} pages",
            f"load {len(matched_pages_data)} wiki pages",
            f"load {len(structured_context['packages'])} approved review packages",
            f"attach {len(structured_context['relations'])} structured relations",
            f"collect {len(citations)} citations",
        ],
    )


@app.get("/api/exports/mapping-matrix")
def export_mapping_matrix() -> dict[str, Any]:
    return build_mapping_matrix()


@app.get("/api/exports/slides-outline")
def export_slides_outline() -> dict[str, Any]:
    return build_slides_outline()


@app.post("/api/lint/scan")
def lint_scan() -> dict[str, list[dict[str, Any]]]:
    report = LintAgent().run_health_check(use_llm=False)
    return {"items": _lint_items(report)}


@app.post("/agent/upload", response_model=AgentUploadResponse)
async def agent_upload(
    file: UploadFile = File(...),
    use_llm: bool = Form(False),
) -> AgentUploadResponse:
    if not file.filename:
        raise HTTPException(status_code=400, detail="file is required")

    RAW_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
    safe_name = f"{timestamp}-{Path(file.filename).name}"
    target = RAW_DIR / safe_name
    target.write_bytes(await file.read())

    processed = process_document(target)
    processed_metadata = getattr(processed, "metadata", {}) or {}
    parse_status = str(processed_metadata.get("parse_status", "unknown"))
    eval_summary = dict(processed_metadata.get("eval_summary", {}))
    parse_blocks_ingest = parse_status in {"failed", "ocr_required"} or int(eval_summary.get("fail", 0)) > 0
    candidates = [] if parse_blocks_ingest else IngestAgent().ingest(processed.document_id, use_llm=use_llm)
    run_id = datetime.now().strftime("%Y%m%d%H%M%S")
    RUN_DIR.mkdir(parents=True, exist_ok=True)
    run_path = RUN_DIR / f"{run_id}.json"
    pending_count = len([item for item in candidates if item.status == "pending"])
    review_package_id = None if parse_blocks_ingest else f"review-{processed.document_id}"
    candidate_ids = [item.candidate_id for item in candidates]
    run_path.write_text(
        json.dumps(
            {
                "run_id": run_id,
                "file_name": file.filename,
                "document_id": processed.document_id,
                "review_package_id": review_package_id,
                "candidate_ids": candidate_ids,
                "parse_status": parse_status,
                "section_count": processed_metadata.get("section_count", 0),
                "fragment_count": processed_metadata.get("fragment_count", 0),
                "table_count": processed_metadata.get("table_count", 0),
                "structure_quality": processed_metadata.get("structure_quality", {}),
                "eval_summary": processed_metadata.get("eval_summary", {}),
                "review_items": processed_metadata.get("review_items", []),
                "documents_parsed": 1,
                "proposals_created": len(candidates),
                "pages_published": 0,
                "pending_review_count": pending_count,
                "workflow_engine": "IngestAgent",
                "use_llm": use_llm,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    return AgentUploadResponse(
        run_id=run_id,
        document_id=processed.document_id,
        file_name=file.filename,
        parse_status=parse_status,
        section_count=int(processed_metadata.get("section_count", 0)),
        fragment_count=int(processed_metadata.get("fragment_count", 0)),
        table_count=int(processed_metadata.get("table_count", 0)),
        structure_quality=dict(processed_metadata.get("structure_quality", {})),
        eval_summary=dict(processed_metadata.get("eval_summary", {})),
        review_items=list(processed_metadata.get("review_items", [])),
        review_package_id=review_package_id,
        candidate_ids=candidate_ids,
        documents_parsed=1,
        proposals_created=len(candidates),
        pending=pending_count,
        pending_review_count=pending_count,
        workflow_engine="IngestAgent",
    )


def _agent_summaries(candidates: list[Any], review_packages: list[Any], issues: list[dict[str, Any]]) -> list[dict[str, Any]]:
    pending_candidates = len([item for item in candidates if item.status == "pending"])
    pending_packages = len([item for item in review_packages if item.status == "pending_review"])
    open_issues = len([item for item in issues if item["status"] != "resolved"])
    index_status = _build_index_status()
    return [
        {
            "key": "ingest",
            "name": "IngestAgent",
            "status": "ready" if pending_packages == 0 and pending_candidates == 0 else "running",
            "headline": f"{pending_packages} 个解析结果待校正，{pending_candidates} 个候选页待发布",
            "queue": max(pending_packages, pending_candidates),
            "lastRun": index_status["lastBuilt"],
            "accent": "teal",
        },
        {
            "key": "query",
            "name": "QueryAgent",
            "status": "ready",
            "headline": f"索引已覆盖 {index_status['pages']} 个页面",
            "queue": 0,
            "lastRun": index_status["lastBuilt"],
            "accent": "blue",
        },
        {
            "key": "lint",
            "name": "LintAgent",
            "status": "blocked" if open_issues else "ready",
            "headline": f"{open_issues} 个健康问题待处理",
            "queue": open_issues,
            "lastRun": index_status["lastBuilt"],
            "accent": "amber",
        },
    ]


def _candidate_payload(candidate: Any) -> dict[str, Any]:
    return {
        "candidate_id": candidate.candidate_id,
        "document_ids": list(candidate.source_doc_ids),
        "page_type": candidate.page_type,
        "title": candidate.title,
        "status": candidate.status,
        "confidence": candidate.confidence,
        "summary": candidate.content.get("summary", ""),
        "keywords": candidate.content.get("keywords", []),
        "related_titles": candidate.content.get("related_titles", []),
        "source_refs": [{"document_id": item} for item in candidate.source_doc_ids],
    }


def _load_parsed_document(document_id: str):
    parsed_path = PARSED_DIR / f"{document_id}.json"
    if not parsed_path.exists():
        raise HTTPException(status_code=404, detail=f"Parsed document not found: {document_id}")
    return load_canonical_document(parsed_path)


def _parse_workflow_payload(canonical: Any) -> dict[str, Any]:
    workflow = canonical.document.metadata.get("parse_workflow")
    if workflow:
        return workflow
    parser_name = str(canonical.document.metadata.get("parser_name", f"{canonical.document.source_type}_parser"))
    return build_parse_workflow_summary(canonical, parser_name=parser_name)


def _normalize_session_source_scope(source_scope: dict[str, Any]) -> dict[str, Any]:
    mode = str(source_scope.get("mode", "selected_docs"))
    if mode == "selected_docs":
        document_ids = [str(item).strip() for item in source_scope.get("document_ids", []) if str(item).strip()]
        if not document_ids:
            raise HTTPException(status_code=400, detail="selected_docs source_scope requires document_ids")
        return {"mode": "selected_docs", "document_ids": document_ids}
    if mode == "all_sources":
        return {"mode": "all_sources"}
    raise HTTPException(status_code=400, detail=f"unsupported source_scope mode: {mode}")


def _load_session_canonicals(source_scope: dict[str, Any]) -> list[Any]:
    if source_scope.get("mode") == "selected_docs":
        return [_load_parsed_document(document_id) for document_id in source_scope.get("document_ids", [])]

    canonicals = []
    for path in sorted(PARSED_DIR.glob("*.json")):
        try:
            canonicals.append(load_canonical_document(path))
        except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
            print(f"[App.api] skip invalid parsed document {path.name}: {exc}")
    if not canonicals:
        raise HTTPException(status_code=404, detail="No parsed documents available for session query")
    return canonicals


def _expanded_session_question(question: str, intent_type: str) -> str:
    if intent_type == "process_explanation":
        return " ".join(
            [
                question,
                "procedure requirement workflow development phase r2 r3 qmp pmp role responsibility deliverable scope",
            ]
        )
    if intent_type == "role_action_guidance":
        return " ".join([question, "responsibility deliverable qmp evidence phase role action"])
    return question


def _session_route_plan(question: str, intent: Any) -> dict[str, Any]:
    normalized_terms = getattr(intent, "normalized_terms", {}) or {}
    has_specific_terms = any(normalized_terms.get(key) for key in ("stage", "role", "deliverable", "section"))
    if intent.intent_type == "stage_transition_work":
        stages = normalized_terms.get("stage", [])
        stage_label = " -> ".join(stages[:2]) if stages else "阶段转换"
        return _route_plan_payload(
            "stage_transition_work",
            intent.intent_type,
            summary=f"识别为阶段转换工作问题，优先检索 {stage_label} 之间的输入、工作项、评审交付和退出/进入条件。",
        )
    if intent.intent_type == "deliverable_detail":
        deliverables = normalized_terms.get("deliverable", [])
        deliverable_label = "/".join(deliverables) if deliverables else "交付物"
        return _route_plan_payload(
            "deliverable_detail",
            intent.intent_type,
            summary=f"识别为 {deliverable_label} 内容和责任问题，优先检索内容要求、责任人、撰写/维护和评审批准证据。",
        )
    if intent.intent_type == "tailoring_policy":
        return _route_plan_payload("tailoring_policy", intent.intent_type)
    if intent.intent_type in {"process_explanation", "definition_lookup"} and not has_specific_terms and _is_process_overview_question(question):
        return _route_plan_payload("process_overview", intent.intent_type)
    if intent.intent_type == "process_explanation" and not has_specific_terms and _is_process_operation_question(question):
        return _route_plan_payload("process_operation", intent.intent_type)
    if intent.intent_type == "process_explanation" and not has_specific_terms:
        return _route_plan_payload(
            "process_overview",
            intent.intent_type,
            summary="识别为泛流程说明，优先检索当前文档总览、适用范围、流程主线、通用要求和阶段主干。",
        )
    return _route_plan_payload(
        intent.intent_type,
        intent.intent_type,
        summary="识别为带明确阶段、角色、交付物或章节的定向问题，优先检索匹配证据。",
    )


def _route_plan_payload(route_id: str, intent_type: str, *, summary: str | None = None) -> dict[str, Any]:
    entry = get_route_entry(route_id)
    payload: dict[str, Any] = {
        "route_id": route_id,
        "intent_type": intent_type,
        "summary": summary or (entry.summary if entry else "识别为带明确阶段、角色、交付物或章节的定向问题，优先检索匹配证据。"),
        "needs_overview_evidence": bool(entry.needs_overview_evidence) if entry else False,
    }
    if entry:
        payload.update(
            {
                "risk_level": entry.risk_level,
                "citation_policy": entry.citation_policy,
                "evidence_needs": list(entry.evidence_needs),
            }
        )
    return payload


def _is_process_operation_question(question: str) -> bool:
    normalized = question.casefold()
    operation_terms = ["如何操作", "怎么操作", "如何执行", "怎么执行", "怎么做", "操作办法", "操作步骤", "流程如何", "流程怎么", "how to operate", "operation steps", "how to follow"]
    process_terms = ["pep", "sop", "wi", "文档", "流程", "规程", "规范", "制度", "作业指导", "process", "procedure", "workflow", "directive"]
    return any(term in normalized for term in operation_terms) and any(term in normalized for term in process_terms)


def _is_process_overview_question(question: str) -> bool:
    normalized = question.casefold()
    overview_terms = ["目的", "适用范围", "scope", "purpose", "概览", "overview", "是什么"]
    process_terms = ["pep", "sop", "wi", "文档", "流程", "规程", "规范", "制度", "作业指导", "process", "procedure", "workflow", "directive"]
    return any(term in normalized for term in overview_terms) and any(term in normalized for term in process_terms)


def _session_retrieval_question(question: str, intent: Any, route_plan: dict[str, Any]) -> str:
    return str(_session_query_rewrite(question, intent, route_plan)["rewritten_query"])


def _session_query_rewrite(question: str, intent: Any, route_plan: dict[str, Any]) -> dict[str, Any]:
    route_id = str(route_plan.get("route_id") or intent.intent_type)
    normalized_terms = getattr(intent, "normalized_terms", {}) or {}
    route_terms = route_query_terms(route_id, normalized_terms)
    entry = get_route_entry(route_id)
    excluded_terms = list(entry.excluded_terms) if entry else []
    reason = "沿用原始问题检索。"
    if entry:
        reason = entry.rewrite_reason
    elif intent.intent_type == "process_explanation":
        route_terms = ["procedure requirement workflow", "development phase", "role responsibility", "deliverable scope"]
        reason = "流程类问题默认补充流程、阶段、职责和交付物检索信号。"

    rewritten_query = " ".join([question, *route_terms]).strip()
    return {
        "schema_version": "query-rewrite-v0.1",
        "route_id": route_id,
        "original_query": question,
        "rewritten_query": rewritten_query or question,
        "route_terms": route_terms,
        "excluded_terms": excluded_terms,
        "reason": reason,
        "expanded": bool(route_terms),
    }


def _session_retrieval_top_k(top_k: int, route_plan: dict[str, Any]) -> int:
    entry = get_route_entry(str(route_plan.get("route_id") or ""))
    if entry and entry.expands_retrieval:
        return min(max(top_k * entry.top_k_multiplier, 12), 60)
    return top_k


def _session_retrieve_sections(
    question: str,
    chunks: list[Any],
    *,
    source_scope: dict[str, Any],
    top_k: int,
) -> Any:
    retriever = HybridRetriever([RuleSectionRetriever(), FullTextRetriever()])
    return retriever.retrieve(question, chunks, source_scope=source_scope, top_k=top_k)


def _route_aware_retrieval_result(retrieval_result: Any, route_plan: dict[str, Any], *, top_k: int) -> Any:
    route_id = route_plan.get("route_id")
    entry = get_route_entry(str(route_id or ""))
    if not entry or not entry.rerank_enabled:
        return retrieval_result

    reranked = sorted(
        retrieval_result.hits,
        key=lambda hit: hit.score + _route_evidence_bonus(hit, route_id),
        reverse=True,
    )
    selected: list[Any] = []
    per_section: dict[str, int] = {}
    for hit in reranked:
        section_key = hit.chunk.section_id or hit.chunk.section_title or hit.chunk.chunk_id
        if per_section.get(section_key, 0) >= 2:
            continue
        selected.append(hit)
        per_section[section_key] = per_section.get(section_key, 0) + 1
        if len(selected) >= top_k:
            break

    retrieval_result.hits = selected
    retrieval_result.evidence_coverage = _session_retrieval_coverage(selected)
    retrieval_result.strategy_used = f"{route_id}_route_retrieval"
    retrieval_result.trace.extend(
        [
            f"route-aware {str(route_id).replace('_', ' ')} rerank applied",
            "overview and operation backbone sections boosted; stage-specific local procedure snippets downranked",
        ]
    )
    return retrieval_result


def _route_evidence_bonus(hit: Any, route_id: str) -> float:
    bonus = _process_overview_bonus(hit)
    if route_id == "process_operation":
        bonus += _process_operation_bonus(hit)
    if route_id == "stage_transition_work":
        bonus += _stage_transition_bonus(hit)
    if route_id == "deliverable_detail":
        bonus += _deliverable_detail_bonus(hit)
    if route_id == "tailoring_policy":
        bonus += _tailoring_policy_bonus(hit)
    return bonus


def _process_overview_bonus(hit: Any) -> float:
    title = str(hit.chunk.section_title or "").casefold()
    searchable = " ".join([title, str(hit.chunk.text or "").casefold(), " ".join(hit.chunk.section_path).casefold()])
    bonus = 0.0
    bonus += _local_compliance_noise_penalty(searchable)
    if "purpose" in title and "scope" in title:
        bonus += 8.0
    if "v-model" in title or "requirement tracing" in title:
        bonus += 5.0
    if "general requirements valid for all process phases" in title:
        bonus += 5.0
    if "process" in searchable or "workflow" in searchable or "procedure" in searchable or "development process" in searchable:
        bonus += 4.0
    if "procedure" in title and "requirement" in title:
        bonus += 3.0
    if "r2 closer to r3" in title or "below procedures must be followed" in title:
        bonus -= 12.0
    if "interfaces between process phases" in searchable:
        bonus -= 6.0
    if re.fullmatch(r"r\d[\sr\d]*", title.replace("/", " ").strip()):
        bonus -= 4.0
    return bonus


def _process_operation_bonus(hit: Any) -> float:
    title = str(hit.chunk.section_title or "").casefold()
    searchable = " ".join([title, str(hit.chunk.text or "").casefold(), " ".join(hit.chunk.section_path).casefold()])
    bonus = 0.0
    bonus += _local_compliance_noise_penalty(searchable)
    if "country-specific approvals" in title or "各国市场准入" in title or "market access" in title:
        bonus -= 8.0
    if "procedure" in title or "requirement" in title:
        bonus += 5.0
    if "operation" in searchable or "operate" in searchable or "workflow" in searchable:
        bonus += 4.0
    if "phase" in searchable or "process phases" in searchable:
        bonus += 3.0
    if "deliverable" in searchable or "review" in searchable or "evidence" in searchable:
        bonus += 2.0
    return bonus


def _stage_transition_bonus(hit: Any) -> float:
    title = str(hit.chunk.section_title or "").casefold()
    searchable = " ".join([title, str(hit.chunk.text or "").casefold(), " ".join(hit.chunk.section_path).casefold()])
    bonus = 0.0
    if "r4" in searchable and "r5" in searchable:
        bonus += 8.0
    if "transition" in searchable or "between" in searchable or "entry" in searchable or "exit" in searchable:
        bonus += 5.0
    if "work" in searchable or "activity" in searchable or "task" in searchable or "phase" in searchable:
        bonus += 3.0
    if "deliverable" in searchable or "review" in searchable or "readiness" in searchable:
        bonus += 3.0
    return bonus


def _deliverable_detail_bonus(hit: Any) -> float:
    title = str(hit.chunk.section_title or "").casefold()
    searchable = " ".join([title, str(hit.chunk.text or "").casefold(), " ".join(hit.chunk.section_path).casefold()])
    bonus = 0.0
    if "qmp" in searchable or "quality management plan" in searchable:
        bonus += 8.0
    if "content" in searchable or "include" in searchable or "contains" in searchable:
        bonus += 4.0
    if "owner" in searchable or "responsible" in searchable or "author" in searchable or "write" in searchable:
        bonus += 5.0
    if "review" in searchable or "approval" in searchable or "maintain" in searchable:
        bonus += 3.0
    return bonus


def _tailoring_policy_bonus(hit: Any) -> float:
    title = str(hit.chunk.section_title or "").casefold()
    searchable = " ".join([title, str(hit.chunk.text or "").casefold(), " ".join(hit.chunk.section_path).casefold()])
    bonus = 0.0
    if "agile" in searchable or "敏捷" in searchable:
        bonus += 5.0
    if "tailor" in searchable or "裁剪" in searchable:
        bonus += 7.0
    if "review" in searchable or "评审" in searchable:
        bonus += 4.0
    if "mandatory" in searchable or "cannot be tailored" in searchable or "不可" in searchable or "shall" in searchable:
        bonus += 4.0
    if "approval" in searchable or "evidence" in searchable or "record" in searchable:
        bonus += 3.0
    return bonus


def _local_compliance_noise_penalty(searchable: str) -> float:
    local_markers = (
        "labeling requirements",
        "product scope",
        "china rohs",
        "hazardous substances",
        "environment-friendly use period",
        "electrical and electronic products",
        "标识要求",
        "产品范围",
        "有害物质",
        "环保使用期限",
        "电气和电子产品",
    )
    return -28.0 if any(marker in searchable for marker in local_markers) else 0.0


def _session_retrieval_coverage(hits: list[Any]) -> dict[str, Any]:
    documents = sorted({hit.chunk.document_id for hit in hits})
    sections = sorted({hit.chunk.section_id for hit in hits if hit.chunk.section_id})
    return {"documents": documents, "sections": sections, "hit_count": len(hits)}


def _model_config_path(model_profile: str) -> str:
    normalized = str(model_profile or DEFAULT_MODEL_PROFILE).strip().lower()
    return MODEL_PROFILE_CONFIGS.get(normalized, MODEL_PROFILE_CONFIGS[DEFAULT_MODEL_PROFILE])


def _session_llm_answer(
    question: str,
    evidence_package: AnswerEvidencePackage,
    citations: list[dict[str, Any]],
    *,
    model_profile: str,
    route_plan: dict[str, Any],
    answer_plan: dict[str, Any] | None = None,
) -> str:
    citable_evidence = _session_citable_evidence(evidence_package, citations)
    if not citable_evidence:
        raise ValueError("no validated citations available for LLM composer")

    evidence_lines: list[str] = []
    for evidence, citation in citable_evidence[:8]:
        source_context = citation.get("source_context") if isinstance(citation.get("source_context"), dict) else {}
        context_before = str(source_context.get("context_before") or "").strip()
        context_text = str(source_context.get("context_text") or "").strip()
        context_after = str(source_context.get("context_after") or "").strip()
        evidence_lines.extend(
            [
                f"[{citation['citation_id']}] {citation['file_name']} / {evidence.section_title} / {citation['anchor_label']}",
                f"quote: {citation['quote']}",
                f"context_before: {context_before or '-'}",
                f"context_hit: {context_text or '-'}",
                f"context_after: {context_after or '-'}",
                "",
            ]
        )
    missing_lines = []
    for item in evidence_package.missing_evidence[:5]:
        terms = ", ".join(str(term) for term in item.get("terms", [])) or str(item.get("term_type", "evidence"))
        missing_lines.append(f"- {terms}: {item.get('reason', 'missing evidence')}")
    answer_plan_lines = _answer_plan_prompt_lines(answer_plan or {})
    answer_style_lines = _answer_style_prompt_lines(_session_answer_style(route_plan))

    prompt = "\n".join(
        [
            "你是企业流程知识问答助手。请只基于下面通过校验的 evidence 回答，不要补充证据外事实。",
            f"用户问题: {question}",
            f"意图路由: {route_plan.get('route_id')} - {route_plan.get('summary')}",
            "",
            "已校验 evidence:",
            *evidence_lines,
            "证据缺口:",
            *(missing_lines or ["- 无"]),
            "",
            "AnswerPlan slots:",
            *(answer_plan_lines or ["- 无结构化 slot plan"]),
            "",
            "AnswerStyle:",
            *answer_style_lines,
            "",
            "输出要求:",
            "- 用中文直接回答用户问题，表达清楚、具体、可执行。",
            "- 不要输出独立的'识别与路线'或'References'栏目，也不要复述系统工具执行过程。",
            "- 开头先用 1-2 句给出结论；随后优先按 AnswerPlan slots 的顺序组织，但输出要像 chatbox 自然回答。",
            "- 默认使用短段落和少量小标题；只有操作顺序、对比项或检查项需要编号。",
            "- 编号项必须连续，不要在编号项之间插入 bullet 子项；需要补充动作、依据、引用时写在同一个编号项里。",
            "- 避免整段答案都是 bullet point。证据缺口可以用简短 bullet 或一句话说明。",
            "- 每个步骤都要写出从 quote 或 context 里能看到的具体动作、条件、交付物或评审要求；不要只罗列章节标题。",
            "- 每个事实性句子都带引用标签，例如 [c1]。",
            "- 如果证据不足，直接说明缺口。",
            "- 保留原文术语，不要把未出现的责任、记录或阶段写成事实。",
        ]
    )
    from Tool.llm import client as llm_client

    answer = llm_client.ask_llm(
        prompt,
        config_path=_model_config_path(model_profile),
        max_tokens=2500,
        temperature=0.2,
        top_p=0.6,
    ).strip()
    citation_labels = {f"[{citation['citation_id']}]" for citation in citations}
    if not answer or not any(label in answer for label in citation_labels):
        raise ValueError("LLM answer did not include validated citation labels")
    return answer


def _answer_plan_prompt_lines(answer_plan: dict[str, Any]) -> list[str]:
    lines: list[str] = []
    for slot in answer_plan.get("slots", [])[:8]:
        if not isinstance(slot, dict):
            continue
        citation_labels = " ".join(f"[{item}]" for item in slot.get("citation_ids", []) if item)
        status = str(slot.get("status") or "missing")
        label = str(slot.get("label") or slot.get("slot_id") or "slot")
        summary = str(slot.get("summary") or slot.get("missing_reason") or "")
        lines.append(f"- {label} ({status}) {citation_labels}: {summary}")
    return lines


def _session_answer_style(route_plan: dict[str, Any] | None = None) -> dict[str, Any]:
    route_id = str((route_plan or {}).get("route_id") or "session_rag")
    numbered_routes = {"process_operation", "stage_transition_work", "deliverable_detail", "bu_comparison", "gap_check"}
    compact_comparison_routes = {"tailoring_policy"}
    return {
        "schema_version": "answer-style-v0.1",
        "layout": "compact_comparison" if route_id in compact_comparison_routes else "conversational_structured",
        "opening": "1-2 sentence conclusion",
        "body": "short paragraphs with compact headings",
        "numbering": "continuous_numbered_steps" if route_id in numbered_routes else "use_numbering_only_when_needed",
        "bullet_policy": "use sparingly; no nested bullets inside numbered steps",
        "citation_policy": "inline validated citation labels only",
    }


def _answer_style_prompt_lines(answer_style: dict[str, Any]) -> list[str]:
    return [
        f"- schema: {answer_style.get('schema_version')}",
        f"- layout: {answer_style.get('layout')}",
        f"- opening: {answer_style.get('opening')}",
        f"- body: {answer_style.get('body')}",
        f"- numbering: {answer_style.get('numbering')}",
        f"- bullet_policy: {answer_style.get('bullet_policy')}",
        f"- citation_policy: {answer_style.get('citation_policy')}",
    ]


def _session_llm_trace(requested: bool, used_llm: bool, model_profile: str, llm_error: str) -> str:
    if used_llm:
        return f"LLM composer used model profile: {model_profile}"
    if requested:
        return f"LLM composer fell back to evidence-first answer: {llm_error or 'not available'}"
    return "LLM composer disabled; used evidence-first answer"


def _session_tool_plan(
    *,
    route_plan: dict[str, Any],
    query_rewrite: dict[str, Any],
    source_scope: dict[str, Any],
    use_llm: bool,
) -> dict[str, Any]:
    route_id = str(route_plan.get("route_id") or "session_rag")
    route_entry = get_route_entry(route_id)
    planned = [
        {"tool": "section_search", "reason": "按 section chunks 保留章节结构和 anchor。"},
        {"tool": "fulltext_search", "reason": "补充关键词召回，覆盖 chunk 正文中的术语。"},
        {"tool": "hybrid_retrieve", "reason": "融合 section/fulltext 结果，作为当前真实 RAG 主路径。"},
        {"tool": "build_answer_evidence_package", "reason": "把 retrieval hits 转成 quote/source_ref/supports 可审计证据。"},
        {"tool": "validate_citations", "reason": "过滤跨 source scope、缺 anchor、缺 quote 或重复 citation。"},
        {"tool": "reference_context_read", "reason": "从本轮 chunks 回读 citation 前后文，帮助核查引用支撑。"},
        {"tool": "answer_planner", "reason": "按 route slot 组织证据，减少章节堆叠式回答。"},
        {
            "tool": "llm_session_answer" if use_llm else "deterministic_session_answer",
            "reason": "基于 AnswerPlan 和已校验证据生成回答。",
        },
    ]
    if route_entry and route_entry.rerank_enabled:
        planned.insert(3, {"tool": "route_rerank", "reason": f"按 {route_entry.route_label} route 提升关键证据，降低低相关噪音。"})

    skipped = [
        {"tool": "vector_search", "reason": "persistent vector index not enabled"},
        {"tool": "table_lookup", "reason": "table index not enabled" if route_id == "table_lookup" else "question is not routed as table lookup"},
        {"tool": "direct_section_read", "reason": "no explicit section/page target" if route_id != "reference_lookup" else "dedicated direct-read tool not enabled"},
        {"tool": "compare_documents", "reason": "route is not comparison" if route_id != "bu_comparison" else "comparison tool not enabled"},
    ]
    return {
        "schema_version": "tool-plan-v0.1",
        "route_id": route_id,
        "source_scope": source_scope,
        "query_rewrite_id": query_rewrite.get("schema_version"),
        "route_strategy": {
            "risk_level": route_entry.risk_level,
            "citation_policy": route_entry.citation_policy,
            "evidence_needs": list(route_entry.evidence_needs),
            "answer_shape": route_entry.answer_shape,
        }
        if route_entry
        else {},
        "planned": planned,
        "executed": [],
        "skipped": skipped,
    }


def _session_executed_tool_plan(tool_plan: dict[str, Any], *, evidence_count: int, citation_count: int) -> dict[str, Any]:
    executed = []
    for item in tool_plan.get("planned", []):
        if not isinstance(item, dict):
            continue
        tool = str(item.get("tool") or "")
        result = "done"
        if tool == "build_answer_evidence_package":
            result = f"{evidence_count} evidence items"
        elif tool == "validate_citations":
            result = f"{citation_count} validated citations"
        executed.append({**item, "status": "done", "result": result})
    return {**tool_plan, "executed": executed}


def _session_tool_calls(route_plan: dict[str, Any], used_llm: bool) -> list[dict[str, Any]]:
    calls = [
        {
            "tool": "parse_question_intent",
            "purpose": "识别问题类型、企业术语和回答形态。",
            "status": "done",
        },
        {
            "tool": "hybrid_retrieve_sections",
            "purpose": "在当前 source scope 中用规则检索和全文检索召回 section chunks，并用 RRF 融合。",
            "route": route_plan.get("route_id"),
            "status": "done",
        },
    ]
    if route_plan.get("route_id") == "process_overview":
        calls.append(
            {
                "tool": "prioritize_process_overview_evidence",
                "purpose": "提升 Purpose/Scope/V-model/全流程通用要求，降低局部 R2/R3 程序片段。",
                "status": "done",
            }
        )
    if route_plan.get("route_id") == "process_operation":
        calls.append(
            {
                "tool": "prioritize_process_operation_evidence",
                "purpose": "提升流程主干、操作顺序、阶段关系、交付/评审依据，并保留 Purpose/V-model 总览证据。",
                "status": "done",
            }
        )
    calls.extend(
        [
            {
                "tool": "build_answer_evidence_package",
                "purpose": "把 retrieval hits 转成可引用 evidence package。",
                "status": "done",
            },
            {
                "tool": "validate_citations",
                "purpose": "校验 source scope、document identity、anchor 和 quote。",
                "status": "done",
            },
            {
                "tool": "llm_session_answer" if used_llm else "deterministic_session_answer",
                "purpose": "基于已校验证据生成回答。",
                "status": "done",
            },
        ]
    )
    return calls


def _session_answer_run(
    *,
    question: str,
    source_scope: dict[str, Any],
    canonicals: list[Any],
    chunk_count: int,
    intent: Any,
    route_plan: dict[str, Any],
    retrieval_question: str,
    query_rewrite: dict[str, Any],
    tool_plan: dict[str, Any],
    evidence_package: AnswerEvidencePackage,
    citations: list[dict[str, Any]],
    citation_validation: dict[str, Any],
    answer_plan: dict[str, Any],
    answer: str,
    confidence: str,
    used_llm: bool,
    model_profile: str,
    llm_error: str,
) -> dict[str, Any]:
    evidence_count = len(evidence_package.evidence_items)
    missing_count = len(evidence_package.missing_evidence)
    executed_tool_plan = _session_executed_tool_plan(tool_plan, evidence_count=evidence_count, citation_count=len(citations))
    answer_style = _session_answer_style(route_plan)
    return {
        "schema_version": "answer-run-v0.1",
        "run_id": f"answer-{uuid4().hex[:12]}",
        "loop": "input -> context -> planning -> execution -> generation -> memory",
        "steps": [
            {
                "step_id": "input",
                "label": "输入",
                "status": "done",
                "summary": "已接收并规范化用户问题。",
                "inputs": {"raw_question": question},
                "outputs": {"content_type": "text", "question": question, "question_length": len(question)},
            },
            {
                "step_id": "context",
                "label": "上下文装配",
                "status": "done" if canonicals and chunk_count else "warning",
                "summary": f"已装配 {_session_source_label(canonicals)} 的解析文档和 section chunks。",
                "inputs": {"source_scope": source_scope},
                "outputs": {
                    "source_scope": source_scope,
                    "document_count": len(canonicals),
                    "chunk_count": chunk_count,
                    "source_label": _session_source_label(canonicals),
                },
            },
            {
                "step_id": "planning",
                "label": "推理规划",
                "status": "done",
                "summary": f"已识别为 {intent.intent_type}，选择 session RAG evidence-first 策略。",
                "inputs": {"question": question},
                "outputs": {
                    "intent_type": intent.intent_type,
                    "route_id": route_plan.get("route_id"),
                    "route_summary": route_plan.get("summary"),
                    "answer_shape": intent.answer_shape,
                    "reference_density": intent.reference_density,
                    "risk_level": intent.risk_level,
                    "strategy": evidence_package.strategy_used,
                    "retrieval_question": retrieval_question,
                    "query_rewrite": query_rewrite,
                    "tool_plan": tool_plan,
                    "question_expanded": retrieval_question != question,
                },
            },
            {
                "step_id": "execution",
                "label": "执行",
                "status": "done" if evidence_count and citations else "warning",
                "summary": "已完成 section 检索、证据包构建和 citation 校验。",
                "inputs": {"top_k_scope": source_scope},
                "outputs": {
                    "tool_calls": _session_tool_calls(route_plan, bool(used_llm)),
                    "tool_plan": executed_tool_plan,
                    "evidence_count": evidence_count,
                    "citation_count": len(citations),
                    "missing_evidence_count": missing_count,
                    "evidence_preview": _session_evidence_preview(evidence_package, citations),
                    "citation_validation": citation_validation,
                },
            },
            {
                "step_id": "generation",
                "label": "生成",
                "status": "done" if confidence != "low" and citations else "warning",
                "summary": "已基于通过校验的证据生成回答，并保留可定位引用。",
                "inputs": {"evidence_count": evidence_count, "citation_count": len(citations)},
                "outputs": {
                    "composer": "llm_session_answer" if used_llm else "deterministic_session_answer",
                    "used_llm": used_llm,
                    "model_profile": model_profile,
                    "llm_error": llm_error,
                    "confidence": confidence,
                    "answer_length": len(answer),
                    "answer_plan": answer_plan,
                    "answer_style": answer_style,
                    "self_check": _session_answer_self_check(
                        route_plan=route_plan,
                        evidence_package=evidence_package,
                        citations=citations,
                        citation_validation=citation_validation,
                        confidence=confidence,
                    ),
                },
            },
            {
                "step_id": "memory",
                "label": "记忆回写",
                "status": "deferred",
                "summary": "当前版本已支持前端 Pin 到 Session Note；持久化会话记忆作为下一阶段接入。",
                "inputs": {"answer_run_id": "pending_client_pin"},
                "outputs": {"pinnable": True, "durable_memory": False, "next_target": "session_memory_store"},
            },
        ],
    }


def _session_evidence_preview(evidence_package: AnswerEvidencePackage, citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
    citation_by_evidence_id = {citation.get("evidence_id"): citation for citation in citations if citation.get("evidence_id")}
    preview: list[dict[str, Any]] = []
    for evidence in evidence_package.evidence_items:
        citation = citation_by_evidence_id.get(evidence.evidence_id)
        if not citation:
            continue
        preview.append(
            {
                "citation_id": citation.get("citation_id"),
                "section_title": evidence.section_title,
                "anchor_label": evidence.anchor_label,
                "quote_preview": _short_answer_quote(evidence.quote, limit=150),
                "matched_terms": evidence.matched_terms[:5],
                "signals": evidence.signals[:5],
            }
        )
        if len(preview) >= 5:
            break
    return preview


def _session_answer_self_check(
    *,
    route_plan: dict[str, Any],
    evidence_package: AnswerEvidencePackage,
    citations: list[dict[str, Any]],
    citation_validation: dict[str, Any],
    confidence: str,
) -> dict[str, Any]:
    route_id = str(route_plan.get("route_id") or "session_rag")
    missing_count = len(evidence_package.missing_evidence)
    valid_count = int(citation_validation.get("valid_count") or 0)
    skipped_count = int(citation_validation.get("skipped_count") or 0)
    sections = [evidence.section_title for evidence in evidence_package.evidence_items if evidence.section_title]
    unique_sections = list(dict.fromkeys(sections))[:5]
    route_entry = get_route_entry(route_id)
    route_label = route_entry.route_label if route_entry else "证据检索问答"
    notes = [
        f"问题被按“{route_label}”处理，回答应优先覆盖操作顺序、适用边界、交付/评审依据和可追溯引用。",
        f"检索后保留 {len(evidence_package.evidence_items)} 条候选证据，{valid_count} 条通过 citation 校验。",
    ]
    if unique_sections:
        notes.append(f"主要证据来自：{' / '.join(unique_sections)}。")
    if skipped_count:
        notes.append(f"有 {skipped_count} 条候选证据因为 source、anchor、quote 或重复问题被排除。")
    if missing_count:
        notes.append(f"仍有 {missing_count} 个证据缺口，回答需要保留边界提示。")
    else:
        notes.append("本轮没有发现必须显式提示的证据缺口，但仍只代表当前选中文档和已召回证据。")
    if confidence == "low":
        notes.append("confidence 为 low，适合提示用户缩小阶段、角色或交付物范围后重问。")
    elif confidence == "medium":
        notes.append("confidence 为 medium，答案可用，但需要优先查看引用原文。")
    else:
        notes.append("confidence 为 high，说明引用数量和证据覆盖较好；准确性仍以可展开原文为准。")
    return {
        "route_id": route_id,
        "route_label": route_label,
        "coverage": evidence_package.coverage,
        "confidence": confidence,
        "quality_notes": notes,
        "reference_policy": "正文只放短 citation 小标；点击后在 Reference Viewer 展开 quote、章节和 anchor。",
    }


def _session_answer_plan(
    *,
    route_plan: dict[str, Any],
    evidence_package: AnswerEvidencePackage,
    citations: list[dict[str, Any]],
) -> dict[str, Any]:
    route_id = str(route_plan.get("route_id") or "session_rag")
    citable_evidence = _session_citable_evidence(evidence_package, citations)
    slots = []
    for slot_def in _answer_plan_slot_defs(route_id):
        matched = _slot_evidence(slot_def, citable_evidence)
        slots.append(_answer_plan_slot_payload(slot_def, matched))
    missing_slots = [
        {"slot_id": slot["slot_id"], "label": slot["label"], "reason": slot["missing_reason"]}
        for slot in slots
        if slot["required"] and slot["status"] != "filled"
    ]
    return {
        "schema_version": "answer-plan-v0.1",
        "route_id": route_id,
        "answer_shape": _answer_plan_shape(route_id),
        "slots": slots,
        "missing_slots": missing_slots,
        "evidence_count": len(citable_evidence),
        "citation_count": len(citations),
    }


def _answer_plan_slot_defs(route_id: str) -> list[dict[str, Any]]:
    catalog_slots = route_answer_slot_dicts(route_id)
    if catalog_slots:
        return catalog_slots
    return [
        {"slot_id": "direct_answer", "label": "直接回答", "required": True, "terms": [], "missing_reason": "缺少可支撑直接回答的证据。"},
        {"slot_id": "source_support", "label": "引用支撑", "required": True, "terms": [], "missing_reason": "缺少可校验引用。"},
    ]


def _answer_plan_shape(route_id: str) -> str:
    entry = get_route_entry(route_id)
    return entry.answer_shape if entry else "direct answer -> supporting citations -> gaps"


def _slot_evidence(
    slot_def: dict[str, Any],
    citable_evidence: list[tuple[EvidenceItem, dict[str, Any]]],
) -> list[tuple[EvidenceItem, dict[str, Any]]]:
    terms = [str(term).casefold() for term in slot_def.get("terms", [])]
    if not terms:
        return citable_evidence[:3]
    matched = []
    for evidence, citation in citable_evidence:
        searchable = " ".join([evidence.section_title, evidence.quote, " ".join(evidence.section_path), " ".join(evidence.signals)]).casefold()
        if any(term in searchable for term in terms):
            matched.append((evidence, citation))
    return matched[:3]


def _answer_plan_slot_payload(slot_def: dict[str, Any], matched: list[tuple[EvidenceItem, dict[str, Any]]]) -> dict[str, Any]:
    citation_ids = [str(citation.get("citation_id")) for _evidence, citation in matched if citation.get("citation_id")]
    evidence_ids = [evidence.evidence_id for evidence, _citation in matched]
    summaries = [_short_answer_quote(evidence.quote, limit=120) for evidence, _citation in matched]
    return {
        "slot_id": slot_def["slot_id"],
        "label": slot_def["label"],
        "required": bool(slot_def.get("required")),
        "status": "filled" if citation_ids else "missing",
        "citation_ids": citation_ids,
        "evidence_ids": evidence_ids,
        "summary": summaries[0] if summaries else "",
        "missing_reason": "" if citation_ids else str(slot_def.get("missing_reason") or "missing evidence"),
    }


def _session_citations(evidence_package: AnswerEvidencePackage, *, limit: int) -> list[dict[str, Any]]:
    citations, _validation = _session_citations_with_validation(evidence_package, limit=limit)
    return citations


def _session_citations_with_validation(
    evidence_package: AnswerEvidencePackage,
    *,
    limit: int,
    chunks: list[Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str, str]] = set()
    skipped_reasons: dict[str, int] = {}
    for evidence in evidence_package.evidence_items:
        payload, reason = _session_citation_payload(evidence, evidence_package.source_scope)
        if reason:
            skipped_reasons[reason] = skipped_reasons.get(reason, 0) + 1
            continue
        assert payload is not None
        key = _citation_key_from_payload(payload)
        if key in seen:
            skipped_reasons["duplicate_citation"] = skipped_reasons.get("duplicate_citation", 0) + 1
            continue
        seen.add(key)
        payload["citation_id"] = f"c{len(citations) + 1}"
        payload["source_context"] = _session_reference_context(payload, chunks or [])
        citations.append(payload)
        if len(citations) >= limit:
            break
    validation = {
        "checked_count": len(evidence_package.evidence_items),
        "valid_count": len(citations),
        "skipped_count": sum(skipped_reasons.values()),
        "skipped_reasons": skipped_reasons,
        "source_scope": evidence_package.source_scope,
        "requires_citations": True,
    }
    return citations, validation


def _session_citation_payload(
    evidence: Any,
    source_scope: dict[str, Any],
) -> tuple[dict[str, Any] | None, str | None]:
    first_ref = evidence.source_refs[0] if evidence.source_refs else {}
    document_id = str(evidence.document_id or first_ref.get("document_id") or "").strip()
    ref_document_id = str(first_ref.get("document_id") or document_id).strip()
    allowed_documents = set(source_scope.get("document_ids", [])) if source_scope.get("mode") == "selected_docs" else set()
    if not document_id:
        return None, "missing_document_id"
    if ref_document_id and ref_document_id != document_id:
        return None, "source_ref_document_mismatch"
    if allowed_documents and document_id not in allowed_documents:
        return None, "out_of_scope_document"

    anchor_label = str(evidence.anchor_label or first_ref.get("anchor_label") or "").strip()
    if not anchor_label:
        return None, "missing_anchor"

    quote = str(evidence.quote or first_ref.get("quote") or "").strip()
    if not quote:
        return None, "missing_quote"

    source_id = str(
        first_ref.get("fragment_id")
        or first_ref.get("table_id")
        or first_ref.get("figure_id")
        or evidence.section_id
        or ""
    ).strip()
    if not source_id:
        return None, "missing_source_id"

    file_name = str(evidence.file_name or first_ref.get("file_name") or "").strip()
    if not file_name:
        return None, "missing_file_name"

    return {
        "citation_id": "pending",
        "page_title": evidence.section_title or file_name,
        "file_name": file_name,
        "anchor_label": anchor_label,
        "quote": quote[:2000],
        "document_id": document_id,
        "fragment_id": source_id,
        "section_id": evidence.section_id,
        "evidence_id": evidence.evidence_id,
        "anchors": dict(first_ref.get("anchors") or {}),
    }, None


def _session_reference_context(citation: dict[str, Any], chunks: list[Any]) -> dict[str, Any]:
    if not chunks:
        return {}
    match_index = _citation_chunk_index(citation, chunks)
    if match_index is None:
        return {}

    chunk = chunks[match_index]
    context = {
        "source": "section_chunk_window",
        "chunk_id": str(getattr(chunk, "chunk_id", "") or ""),
        "chunk_type": str(getattr(chunk, "chunk_type", "") or ""),
        "section_id": str(getattr(chunk, "section_id", "") or ""),
        "section_title": str(getattr(chunk, "section_title", "") or ""),
        "anchor_label": _chunk_context_anchor_label(chunk) or str(citation.get("anchor_label") or ""),
        "context_before": _adjacent_chunk_excerpt(chunks, match_index, direction=-1),
        "context_text": _citation_chunk_excerpt(str(getattr(chunk, "text", "") or ""), str(citation.get("quote") or "")),
        "context_after": _adjacent_chunk_excerpt(chunks, match_index, direction=1),
    }
    return {key: value for key, value in context.items() if value}


def _citation_chunk_index(citation: dict[str, Any], chunks: list[Any]) -> int | None:
    scored: list[tuple[int, int]] = []
    for index, chunk in enumerate(chunks):
        score = _citation_chunk_match_score(citation, chunk)
        if score > 0:
            scored.append((score, index))
    if not scored:
        return None
    scored.sort(key=lambda item: (-item[0], item[1]))
    return scored[0][1]


def _citation_chunk_match_score(citation: dict[str, Any], chunk: Any) -> int:
    document_id = str(citation.get("document_id") or "")
    if document_id and str(getattr(chunk, "document_id", "") or "") != document_id:
        return 0

    score = 1
    section_id = str(citation.get("section_id") or "")
    if section_id and section_id == str(getattr(chunk, "section_id", "") or ""):
        score += 8

    source_id = str(citation.get("fragment_id") or "")
    anchor_label = str(citation.get("anchor_label") or "")
    source_refs = list(getattr(chunk, "source_refs", []) or [])
    for ref in source_refs:
        ref_ids = [ref.get("fragment_id"), ref.get("table_id"), ref.get("figure_id")]
        if source_id and source_id in {str(item) for item in ref_ids if item}:
            score += 14
        if anchor_label and anchor_label == str(ref.get("anchor_label") or ""):
            score += 4

    chunk_text = str(getattr(chunk, "text", "") or "")
    quote = str(citation.get("quote") or "")
    if quote and _normalized_contains(chunk_text, quote):
        score += 10
    elif quote and any(_normalized_contains(str(ref.get("quote") or ""), quote[:160]) for ref in source_refs):
        score += 5
    return score


def _adjacent_chunk_excerpt(chunks: list[Any], match_index: int, *, direction: int) -> str:
    matched_document_id = str(getattr(chunks[match_index], "document_id", "") or "")
    index = match_index + direction
    while 0 <= index < len(chunks):
        chunk = chunks[index]
        if str(getattr(chunk, "document_id", "") or "") == matched_document_id:
            return _chunk_context_excerpt(chunk, limit=420)
        index += direction
    return ""


def _citation_chunk_excerpt(text: str, quote: str, *, limit: int = 1600) -> str:
    compact_text = re.sub(r"\s+", " ", text).strip()
    if not compact_text:
        return ""
    compact_quote = re.sub(r"\s+", " ", quote).strip()
    if not compact_quote or len(compact_text) <= limit:
        return _short_answer_quote(compact_text, limit=limit)

    needle = compact_quote[: min(len(compact_quote), 180)].casefold()
    position = compact_text.casefold().find(needle)
    if position < 0:
        return _short_answer_quote(compact_text, limit=limit)

    half_window = max((limit - len(needle)) // 2, 120)
    start = max(position - half_window, 0)
    end = min(position + len(needle) + half_window, len(compact_text))
    excerpt = compact_text[start:end].strip()
    if start > 0:
        excerpt = f"...{excerpt}"
    if end < len(compact_text):
        excerpt = f"{excerpt}..."
    return excerpt


def _chunk_context_excerpt(chunk: Any, *, limit: int) -> str:
    title = str(getattr(chunk, "section_title", "") or "").strip()
    text = str(getattr(chunk, "text", "") or getattr(chunk, "quote", "") or "").strip()
    excerpt = _short_answer_quote(text, limit=limit)
    if title and title not in excerpt[: len(title) + 20]:
        return _short_answer_quote(f"{title}: {excerpt}", limit=limit)
    return excerpt


def _chunk_context_anchor_label(chunk: Any) -> str:
    source_refs = list(getattr(chunk, "source_refs", []) or [])
    labels = [str(ref.get("anchor_label") or "").strip() for ref in source_refs if str(ref.get("anchor_label") or "").strip()]
    if labels:
        return labels[0]
    anchors = getattr(chunk, "anchors", {}) or {}
    pages = anchors.get("pages") if isinstance(anchors, dict) else None
    if isinstance(pages, list) and pages:
        return f"p.{pages[0]}"
    if isinstance(anchors, dict) and anchors.get("page") is not None:
        return f"p.{anchors['page']}"
    return ""


def _normalized_contains(text: str, needle: str) -> bool:
    normalized_text = re.sub(r"\s+", " ", text).strip().casefold()
    normalized_needle = re.sub(r"\s+", " ", needle).strip().casefold()
    if not normalized_text or not normalized_needle:
        return False
    return normalized_needle in normalized_text


def _session_citation_trace(validation: dict[str, Any]) -> str:
    if validation.get("skipped_count"):
        return f"citation validation kept {validation.get('valid_count', 0)} and skipped {validation.get('skipped_count', 0)} evidence items"
    return f"citation validation kept {validation.get('valid_count', 0)} evidence items"


def _session_matched_sections(evidence_package: AnswerEvidencePackage) -> list[dict[str, Any]]:
    return [
        {
            "page_id": evidence.section_id or evidence.evidence_id,
            "title": evidence.section_title or evidence.file_name,
            "page_type": "section",
            "summary": evidence.quote[:240],
            "score": evidence.score,
        }
        for evidence in evidence_package.evidence_items[:8]
    ]


def _session_deterministic_answer(
    question: str,
    evidence_package: AnswerEvidencePackage,
    citations: list[dict[str, Any]],
    route_plan: dict[str, Any] | None = None,
) -> str:
    citable_evidence = _session_citable_evidence(evidence_package, citations)
    if not citable_evidence:
        return (
            f"针对问题“{question}”，当前选中文档没有通过校验的可引用证据。"
            "请先核查 source scope、章节锚点和引用 quote，或换一个更具体的阶段、角色、交付物再问。"
        )

    if route_plan and route_plan.get("route_id") == "process_operation":
        operation_evidence = _session_process_operation_evidence(citable_evidence)
        operation_items = operation_evidence[:7]
        lines = [
            f"针对问题“{question}”，当前选中文档证据支持按操作办法来读；核心是先确认适用范围，再沿流程阶段执行，并在评审时保留可追溯交付和记录。具体结论仍以每条引用原文为准。",
            "",
            "操作主线：",
        ]
        for index, (label, evidence, citation) in enumerate(operation_items, 1):
            citation_label = f"[{citation['citation_id']}]"
            trace_location = f"{citation.get('file_name', evidence.file_name)} · {citation.get('anchor_label', evidence.anchor_label)} · {evidence.section_title}"
            lines.append(
                f"{index}. {label} {citation_label} 具体做法：{_process_operation_action(label)} "
                f"文档细节：{_evidence_detail_sentence(evidence, citation)} "
                f"可追溯位置：{trace_location}。"
            )
        if evidence_package.missing_evidence:
            lines.extend(["", "需要补证或人审确认："])
            for item in evidence_package.missing_evidence[:3]:
                terms = ", ".join(str(term) for term in item.get("terms", [])) or str(item.get("term_type", "evidence"))
                lines.append(f"- {terms}: {item.get('reason', 'missing evidence')}")
        return "\n".join(lines)

    if route_plan and route_plan.get("route_id") == "process_overview":
        lines = [
            f"针对问题“{question}”，当前选中文档证据支持先给出文档内可核查的结论。下面只基于已校验引用整理：",
            "",
            "关键结论：",
        ]
        for index, (evidence, citation) in enumerate(citable_evidence[:5], 1):
            citation_label = f"[{citation['citation_id']}]"
            lines.append(
                f"{index}. {evidence.section_title} {citation_label} 具体含义：{_overview_answer_sentence(evidence)} "
                f"文档细节：{_evidence_detail_sentence(evidence, citation)}"
            )
        if evidence_package.missing_evidence:
            lines.extend(["", "需要人审确认的缺口："])
            for item in evidence_package.missing_evidence[:3]:
                terms = ", ".join(str(term) for term in item.get("terms", [])) or str(item.get("term_type", "evidence"))
                lines.append(f"- {terms}: {item.get('reason', 'missing evidence')}")
        return "\n".join(lines)

    lines = [f"针对问题“{question}”，我先按当前选中文档证据回答：", ""]
    lines.append("证据回答：")
    for index, (evidence, citation) in enumerate(citable_evidence[:4], 1):
        citation_label = f"[{citation['citation_id']}]"
        lines.append(
            f"{index}. {evidence.section_title} {citation_label} 具体含义：{_overview_answer_sentence(evidence)} "
            f"文档细节：{_evidence_detail_sentence(evidence, citation)}"
        )
    if evidence_package.missing_evidence:
        lines.extend(["", "需要人审确认的缺口："])
        for item in evidence_package.missing_evidence[:3]:
            terms = ", ".join(str(term) for term in item.get("terms", [])) or str(item.get("term_type", "evidence"))
            lines.append(f"- {terms}: {item.get('reason', 'missing evidence')}")
    return "\n".join(lines)


def _evidence_detail_sentence(evidence: EvidenceItem, citation: dict[str, Any]) -> str:
    quote = _short_answer_quote(str(citation.get("quote") or evidence.quote), limit=260)
    citation_label = f"[{citation['citation_id']}]" if citation.get("citation_id") else ""
    source_context = citation.get("source_context") if isinstance(citation.get("source_context"), dict) else {}
    before = _short_answer_quote(str(source_context.get("context_before") or ""), limit=130)
    after = _short_answer_quote(str(source_context.get("context_after") or ""), limit=130)
    context_parts = [part for part in [before, after] if part and part != quote]
    if context_parts:
        return f"原文命中“{quote}”{citation_label}；相邻上下文还提示“{' / '.join(context_parts[:2])}”{citation_label}。"
    return f"原文命中“{quote}”{citation_label}。"


def _overview_answer_sentence(evidence: EvidenceItem) -> str:
    searchable = " ".join([evidence.section_title, evidence.quote, " ".join(evidence.section_path)]).casefold()
    if "purpose" in searchable or "scope" in searchable or "适用范围" in searchable:
        return "先用该段确定文档目的、适用对象和流程边界，避免把局部章节当成全流程结论。"
    if "v-model" in searchable or "requirement tracing" in searchable or "需求跟踪" in searchable:
        return "用该段理解需求、设计输入/输出、验证/确认之间的追踪关系。"
    if "design input" in searchable:
        return "该段可支撑设计输入相关结论，重点看用户需要、预期用途、适用标准和输入完整性。"
    if "design output" in searchable:
        return "该段可支撑设计输出相关结论，重点看验收准则、输出文件和与设计输入的回连。"
    if "review" in searchable or "deliverable" in searchable or "交付" in searchable or "评审" in searchable:
        return "该段可支撑交付物或评审依据相关结论，适合核对记录、输出和评审节点。"
    if "verification" in searchable or "验证" in searchable:
        return "该段可支撑验证相关结论，重点看工作结果是否满足已定义需求或规格。"
    if "validation" in searchable or "确认" in searchable:
        return "该段可支撑确认相关结论，重点看产品是否满足用户需要和预期使用场景。"
    return "把该段作为当前问题的直接证据，优先抽取其中出现的动作、条件、对象和约束。"


def _session_process_operation_evidence(
    citable_evidence: list[tuple[EvidenceItem, dict[str, Any]]],
) -> list[tuple[str, EvidenceItem, dict[str, Any]]]:
    ranked: list[tuple[int, str, EvidenceItem, dict[str, Any]]] = []
    used_labels: set[str] = set()
    for evidence, citation in citable_evidence:
        if not _operation_evidence_is_actionable(evidence):
            continue
        rank, label = _process_operation_step_label(evidence)
        if label in used_labels:
            continue
        used_labels.add(label)
        ranked.append((rank, label, evidence, citation))
    ranked.sort(key=lambda item: item[0])
    return [(label, evidence, citation) for _rank, label, evidence, citation in ranked]


def _process_operation_step_label(evidence: EvidenceItem) -> tuple[int, str]:
    searchable = " ".join([evidence.section_title, evidence.quote, " ".join(evidence.section_path)]).casefold()
    if "purpose" in searchable or "scope" in searchable or "适用范围" in searchable:
        return 10, "先确认这份文档适用的产品、项目和流程边界"
    if "design input" in searchable and ("intended use" in searchable or "user" in searchable or "patient" in searchable or "预期用途" in searchable):
        return 21, "确认 design input 覆盖预期用途、用户和患者需要"
    if "design output" in searchable and ("acceptance criteria" in searchable or "proper functioning" in searchable or "验收" in searchable):
        return 22, "确认 design output 有验收准则并支撑设备正常运行"
    if "v-model" in searchable or "requirement tracing" in searchable or "v 型" in searchable or "v字" in searchable:
        return 20, "再按 V-model/需求跟踪主线理解开发阶段的先后关系"
    if "procedure" in searchable and "requirement" in searchable:
        return 30, "进入具体 Procedure/Requirement，按文档规定执行和留证"
    if "general requirements" in searchable or "all process phases" in searchable or "concurrent engineering" in searchable:
        return 40, "执行时遵守所有过程阶段通用规则，尤其是阶段重叠和主评审顺序"
    if "verification" in searchable or "验证" in searchable:
        return 50, "用设计验证确认工作结果与需求或规格相符"
    if "validation" in searchable or "确认" in searchable:
        return 60, "用设计确认判断产品是否满足用户规格和预期使用场景"
    if "provisional" in searchable or "backward" in searchable or "过渡" in searchable or "补救" in searchable:
        return 70, "对已在途项目按过渡措施判断是否必须追随新流程"
    return 90, f"结合 {evidence.section_title} 补充操作依据"


def _process_operation_action(label: str) -> str:
    if "适用" in label or "流程边界" in label:
        return "先确认当前项目、产品族、流程版本和适用范围，再决定后续章节是否能作为本轮操作依据。"
    if "V-model" in label or "需求跟踪" in label:
        return "把流程读成需求、设计、验证、确认和追踪关系的链条，后续每一步都要能回到需求或设计证据。"
    if "design input" in label:
        return "把用户需要、预期用途、患者/用户输入和适用标准整理成设计输入，并确认输入适当、完整、可追踪。"
    if "design output" in label:
        return "检查输出文件、设计结果和验收准则，确认关键输出能支持设备正常运行并回连到设计输入。"
    if "Procedure" in label or "Requirement" in label:
        return "进入具体 procedure / requirement 后，逐条确认动作、责任、输入输出和需要留存的 evidence。"
    if "通用规则" in label or "主评审" in label:
        return "阶段可以并行或重叠时，要记录未关闭事项，并保持主评审和交付物的先后关系可追踪。"
    if "设计验证" in label:
        return "用验证活动确认设计输出满足已定义需求或规格，验证结果应能回到相应需求。"
    if "设计确认" in label:
        return "用确认活动判断产品或升级是否满足用户需要和预期使用场景，未 release 前不能作为正式使用依据。"
    if "过渡" in label or "补救" in label:
        return "对已经在途的项目按过渡条款判断是否追随新流程、补做证据或保留旧版本路径。"
    return "把该章节作为补充依据，抽取其中的动作、条件、交付物和评审要求。"


def _operation_evidence_is_actionable(evidence: EvidenceItem) -> bool:
    searchable = " ".join([evidence.section_title, evidence.quote, " ".join(evidence.section_path)]).casefold()
    if _local_compliance_noise_penalty(searchable) < 0:
        return False
    compact = re.sub(r"\s+", " ", evidence.quote or "").strip()
    if len(compact) < 72:
        return False
    title_tokens = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", evidence.section_title.casefold()).split()
    quote_tokens = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", " ", compact.casefold()).split()
    if quote_tokens and title_tokens:
        title_token_set = set(title_tokens)
        overlap = sum(1 for token in quote_tokens if token in title_token_set)
        if overlap / max(len(quote_tokens), 1) > 0.72:
            return False
    return bool(
        re.search(
            r"\b(describes?|shall|must|ensure|contains?|applied|specify|transition|acceptance|validate|verify|input|output)\b",
            compact,
            flags=re.IGNORECASE,
        )
        or re.search(r"(应|必须|确保|适用|规定|确认|验证|输入|输出|评审|过渡)", compact)
    )


def _short_answer_quote(quote: str, limit: int = 520) -> str:
    compact = re.sub(r"\s+", " ", quote).strip()
    if len(compact) <= limit:
        return compact
    return compact[: limit - 1].rstrip() + "…"


def _session_citable_evidence(
    evidence_package: AnswerEvidencePackage,
    citations: list[dict[str, Any]],
) -> list[tuple[Any, dict[str, Any]]]:
    citations_by_key = {_citation_key_from_payload(citation): citation for citation in citations}
    items: list[tuple[Any, dict[str, Any]]] = []
    for evidence in evidence_package.evidence_items:
        payload, reason = _session_citation_payload(evidence, evidence_package.source_scope)
        if reason or payload is None:
            continue
        citation = citations_by_key.get(_citation_key_from_payload(payload))
        if citation:
            items.append((evidence, citation))
    return items


def _citation_key_from_payload(payload: dict[str, Any]) -> tuple[str, str, str, str]:
    return (
        str(payload.get("document_id", "")),
        str(payload.get("fragment_id", "")),
        str(payload.get("anchor_label", "")),
        str(payload.get("quote", "")),
    )


def _session_confidence(evidence_package: AnswerEvidencePackage, citations: list[dict[str, Any]] | None = None) -> str:
    if citations is not None and not citations:
        return "low"
    citation_count = len(citations) if citations is not None else len(evidence_package.evidence_items)
    if len(evidence_package.evidence_items) >= 3 and citation_count >= 3 and not evidence_package.missing_evidence:
        return "high"
    if evidence_package.evidence_items and citation_count:
        return "medium"
    return "low"


def _session_suggested_questions(question: str, canonicals: list[Any]) -> list[str]:
    title = _session_source_label(canonicals)
    suggestions = [
        f"{title} 的 R2 阶段入口和出口条件是什么？",
        f"{title} 里 PO / PM / RA 分别负责什么？",
        "把当前回答的证据按章节和 quote 列出来。",
    ]
    if "差异" not in question:
        suggestions.append("当前选中文档之间的流程差异在哪里？")
    return suggestions


def _session_source_label(canonicals: list[Any]) -> str:
    if not canonicals:
        return "当前文档"
    if len(canonicals) > 1:
        return "当前选中的文件"
    document = canonicals[0].document
    file_name = str(getattr(document, "file_name", "") or "").strip()
    title = str(getattr(document, "title", "") or "").strip()
    if file_name:
        return file_name
    return title or "当前文档"


def _handoff_source(canonical: Any, workflow: dict[str, Any], chunks: list[Any]) -> dict[str, Any]:
    return {
        "document_id": canonical.document.document_id,
        "title": canonical.document.title,
        "file_name": canonical.document.file_name,
        "source_type": canonical.document.source_type,
        "doc_type": canonical.document.doc_type,
        "parse_status": workflow.get("parse_status", canonical.parse_status),
        "section_count": len(canonical.sections),
        "fragment_count": len(canonical.fragments),
        "table_count": len(canonical.tables),
        "figure_count": len(canonical.figures),
        "chunk_count": len(chunks),
    }


def _handoff_tree(canonical: Any, chunks: list[Any], workflow: dict[str, Any]) -> dict[str, Any]:
    fragment_counts: dict[str | None, int] = {}
    chunk_counts: dict[str | None, int] = {}
    for fragment in canonical.fragments:
        fragment_counts[fragment.section_id] = fragment_counts.get(fragment.section_id, 0) + 1
    for chunk in chunks:
        chunk_counts[chunk.section_id] = chunk_counts.get(chunk.section_id, 0) + 1
    root_id = f"doc-{canonical.document.document_id}"
    items = [
        {
            "node_id": root_id,
            "node_type": "document",
            "parent_id": None,
            "document_id": canonical.document.document_id,
            "title": canonical.document.title,
            "parse_status": workflow.get("parse_status", canonical.parse_status),
            "fragment_count": len(canonical.fragments),
            "chunk_count": len(chunks),
        }
    ]
    for section in canonical.sections:
        items.append(
            {
                "node_id": f"section-{section.section_id}",
                "node_type": "section",
                "parent_id": f"section-{section.parent_id}" if section.parent_id else root_id,
                "document_id": canonical.document.document_id,
                "section_id": section.section_id,
                "title": section.title,
                "level": section.level,
                "page_range": list(section.page_range),
                "fragment_count": fragment_counts.get(section.section_id, 0),
                "chunk_count": chunk_counts.get(section.section_id, 0),
                "anchor_label": _section_anchor_label(section.page_range),
            }
        )
    return {"root_id": root_id, "items": items}


def _handoff_graph(canonical: Any, chunks: list[Any]) -> dict[str, Any]:
    nodes: list[dict[str, Any]] = [
        {"node_id": f"doc-{canonical.document.document_id}", "node_type": "document", "label": canonical.document.title}
    ]
    edges: list[dict[str, Any]] = []
    seen_nodes = {nodes[0]["node_id"]}
    for section in canonical.sections:
        section_node_id = f"section-{section.section_id}"
        if section_node_id not in seen_nodes:
            nodes.append({"node_id": section_node_id, "node_type": "section", "label": section.title, "section_id": section.section_id})
            seen_nodes.add(section_node_id)
        parent_id = f"section-{section.parent_id}" if section.parent_id else f"doc-{canonical.document.document_id}"
        edges.append(_graph_edge(parent_id, section_node_id, "contains"))
    for chunk in chunks:
        chunk_node_id = f"chunk-{chunk.chunk_id}"
        if chunk_node_id not in seen_nodes:
            nodes.append({"node_id": chunk_node_id, "node_type": "chunk", "label": chunk.section_title or chunk.chunk_type, "chunk_id": chunk.chunk_id})
            seen_nodes.add(chunk_node_id)
        section_node_id = f"section-{chunk.section_id}" if chunk.section_id else f"doc-{canonical.document.document_id}"
        edges.append(_graph_edge(section_node_id, chunk_node_id, "contains"))
        for signal in chunk.signals[:8]:
            signal_node_id = f"signal-{signal}"
            if signal_node_id not in seen_nodes:
                nodes.append({"node_id": signal_node_id, "node_type": "signal", "label": signal})
                seen_nodes.add(signal_node_id)
            edges.append(_graph_edge(chunk_node_id, signal_node_id, "mentions"))
    return {"nodes": nodes, "edges": edges}


def _handoff_retrieval(chunks: list[Any], preview_chunks: list[Any]) -> dict[str, Any]:
    return {
        "available_retrievers": ["rule_section", "full_text", "vector", "hybrid"],
        "default_retriever": "hybrid",
        "chunk_count": len(chunks),
        "preview_chunks": [chunk.to_dict() for chunk in preview_chunks],
    }


def _handoff_chat_contract(canonical: Any) -> dict[str, Any]:
    source_scope = {"mode": "selected_docs", "document_ids": [canonical.document.document_id]}
    return {
        "source_scope": source_scope,
        "request_contract": {
            "question": "string",
            "source_scope": source_scope,
            "retriever": "hybrid",
            "top_k": 8,
        },
        "answer_contract": {
            "requires_citations": True,
            "evidence_package": "AnswerEvidencePackage",
            "citation_fields": ["document_id", "section_id", "anchor_label", "quote"],
            "quality_gates": ["missing_citation", "unsupported_claim", "missing_evidence"],
        },
    }


def _handoff_quality(workflow: dict[str, Any]) -> dict[str, Any]:
    return {
        "parse_status": workflow.get("parse_status", "unknown"),
        "structure_quality": workflow.get("structure_quality", {}),
        "eval_summary": workflow.get("eval_summary", {}),
        "review_items": workflow.get("review_items", []),
        "visual_review_items": workflow.get("visual_review_items", []),
        "parser_fusion": workflow.get("parser_fusion", {}),
    }


def _section_anchor_label(page_range: list[int]) -> str:
    if not page_range:
        return ""
    if len(page_range) == 1:
        return f"p.{page_range[0]}"
    return f"p.{page_range[0]}-{page_range[-1]}"


def _graph_edge(source_id: str, target_id: str, relation_type: str) -> dict[str, Any]:
    return {
        "edge_id": f"{relation_type}-{source_id}-{target_id}",
        "relation_type": relation_type,
        "source": source_id,
        "target": target_id,
    }


def _load_recent_runs(limit: int = 12) -> list[dict[str, Any]]:
    if not RUN_DIR.exists():
        return []

    runs: list[dict[str, Any]] = []
    for path in sorted(RUN_DIR.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as exc:
            print(f"[App.api] skip invalid run file {path.name}: {exc}")
            continue

        document_id = str(data.get("document_id", "")).strip()
        run_id = str(data.get("run_id", path.stem)).strip() or path.stem
        if not document_id:
            continue
        runs.append(
            {
                "run_id": run_id,
                "document_id": document_id,
                "file_name": str(data.get("file_name", "")),
                "review_package_id": str(data.get("review_package_id", f"review-{document_id}")),
                "candidate_ids": list(data.get("candidate_ids", [])),
                "pending_review_count": int(data.get("pending_review_count", 0)),
                "proposals_created": int(data.get("proposals_created", 0)),
                "use_llm": bool(data.get("use_llm", False)),
                "created_at": datetime.fromtimestamp(path.stat().st_mtime).isoformat(timespec="seconds"),
            }
        )
        if len(runs) >= limit:
            break
    return runs


def _review_package_payload(review_package: Any) -> dict[str, Any]:
    identity = review_package.document_identity
    return {
        "package_id": review_package.package_id,
        "document_id": review_package.document_id,
        "status": review_package.status,
        "identity_decision": review_package.identity_decision,
        "title": identity.title or review_package.document_id,
        "business_type": identity.business_type,
        "effective_level": identity.effective_level,
        "version": identity.version,
        "scope": identity.scope,
        "is_binding": identity.is_binding,
        "confidence": identity.confidence,
        "notes": list(identity.notes),
        "confirmed_business_type": review_package.confirmed_business_type,
        "confirmed_effective_level": review_package.confirmed_effective_level,
        "confirmed_is_binding": review_package.confirmed_is_binding,
        "review_notes": review_package.review_notes,
        "reviewed_at": review_package.reviewed_at,
        "reviewed_by": review_package.reviewed_by,
        "relation_decision": getattr(review_package, "relation_decision", "pending"),
        "relation_review_notes": getattr(review_package, "relation_review_notes", ""),
        "relation_reviewed_at": getattr(review_package, "relation_reviewed_at", ""),
        "relation_reviewed_by": getattr(review_package, "relation_reviewed_by", ""),
        "source_refs": review_package.evidence_refs,
        "issues": [
            {
                "issue_id": issue.issue_id,
                "issue_type": issue.issue_type,
                "detail": issue.detail,
                "severity": issue.severity,
            }
            for issue in getattr(review_package, "issues", [])
        ],
        "human_questions": [
            {
                "question_id": question.question_id,
                "question": question.question,
                "rationale": question.rationale,
                "target": question.target,
            }
            for question in getattr(review_package, "human_questions", [])
        ],
        "extracted_objects": [
            {
                "object_id": item.object_id,
                "object_type": item.object_type,
                "name": item.name,
                "confidence": item.confidence,
                "review_risk": item.review_risk,
                "evidence_refs": list(item.evidence_refs),
            }
            for item in getattr(review_package, "extracted_objects", [])
        ],
        "extracted_relations": [
            {
                "relation_id": item.relation_id,
                "relation_type": item.relation_type,
                "from_object_id": item.from_object_id,
                "to_object_id": item.to_object_id,
                "claim_type": item.claim_type,
                "direction": item.direction,
                "confidence": item.confidence,
                "human_required": item.human_required,
                "evidence_refs": list(item.evidence_refs),
            }
            for item in getattr(review_package, "extracted_relations", [])
        ],
        "candidate_page_titles": list(getattr(review_package, "candidate_page_titles", [])),
        "tool_trace": list(getattr(review_package, "tool_trace", [])),
    }


def _wiki_page_payload(page: WikiPage) -> dict[str, Any]:
    return {
        "page_id": page.page_id,
        "title": page.title,
        "page_type": page.page_type,
        "review_status": page.review_status,
        "summary": page.summary,
        "aliases": page.aliases,
        "linked_pages": page.linked_pages,
        "updated_at": page.updated_at,
        "source_refs": page.source_refs,
        "markdown": render_page_markdown(page),
    }


def _build_index_status() -> dict[str, Any]:
    ready_pages = _ensure_runtime_ready()
    pages = _count_lines(INDEX_PAGE_PATH)
    terms = len(json.loads(INDEX_TERMS_PATH.read_text(encoding="utf-8"))) if INDEX_TERMS_PATH.exists() else 0
    sources = _count_lines(INDEX_SOURCES_PATH)
    state = "fresh" if INDEX_PAGE_PATH.exists() and pages > 0 else "missing"
    last_built = (
        datetime.fromtimestamp(INDEX_PAGE_PATH.stat().st_mtime).isoformat(timespec="seconds")
        if INDEX_PAGE_PATH.exists()
        else ""
    )
    return {
        "state": state,
        "pages": max(pages, len(ready_pages)),
        "terms": terms,
        "sources": sources,
        "lastBuilt": last_built,
    }


def _ensure_runtime_ready(*, force_bootstrap_if_empty: bool = False) -> list[WikiPage]:
    pages = load_all_pages()
    needs_bootstrap = force_bootstrap_if_empty or not pages or _missing_core_pages(pages)
    bootstrapped_now = False
    if needs_bootstrap and PARSED_DIR.exists():
        with _BOOTSTRAP_LOCK:
            pages = load_all_pages()
            if force_bootstrap_if_empty or not pages or _missing_core_pages(pages):
                try:
                    bootstrapped = bootstrap_pages(use_llm=False)
                except OSError as exc:
                    print(f"[runtime] skip wiki bootstrap after storage error: {exc}")
                    bootstrapped = []
                if bootstrapped:
                    pages = load_all_pages()
                    bootstrapped_now = True
    if pages and (bootstrapped_now or not INDEX_PAGE_PATH.exists() or _count_lines(INDEX_PAGE_PATH) == 0):
        build_index(pages=pages, index_dir=INDEX_DIR)
    return pages


def _missing_core_pages(pages: list[WikiPage]) -> bool:
    if not pages:
        return True
    existing_ids = {page.page_id for page in pages}
    core_ids = {str(item.get("page_id", "")).strip() for item in PAGE_BLUEPRINTS if item.get("page_id")}
    return not core_ids.issubset(existing_ids)


def _count_lines(path: Path) -> int:
    if not path.exists():
        return 0
    return len([line for line in path.read_text(encoding="utf-8").splitlines() if line.strip()])


def _pages_from_ranked_entries(ranked_entries: list[dict[str, Any]]) -> list[WikiPage]:
    pages: list[WikiPage] = []
    for entry in ranked_entries:
        page_id = entry.get("page_id", "")
        if not page_id:
            continue
        try:
            pages.append(load_page(page_id))
        except FileNotFoundError:
            continue
    return pages


def _collect_citations(pages: list[WikiPage], *, limit: int) -> list[dict[str, Any]]:
    citations: list[dict[str, Any]] = []
    seen: set[tuple[str, str, str]] = set()
    counter = 1
    for page in pages:
        refs = list(page.source_refs)
        for section in page.sections:
            refs.extend(section.source_refs)
        for ref in refs:
            key = (
                str(ref.get("document_id", "")),
                str(ref.get("fragment_id", "")),
                str(ref.get("anchor_label", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                {
                    "citation_id": f"c{counter}",
                    "page_title": page.title,
                    "file_name": ref.get("file_name", ref.get("document_id", "")),
                    "anchor_label": ref.get("anchor_label", "source"),
                    "quote": ref.get("quote", "") or _ref_quote_from_page(page, ref),
                    "document_id": ref.get("document_id", ""),
                    "fragment_id": ref.get("fragment_id", ""),
                }
            )
            counter += 1
            if len(citations) >= limit:
                return citations
    return citations


def _append_structured_citations(
    citations: list[dict[str, Any]],
    structured_context: dict[str, Any],
    *,
    limit: int,
) -> list[dict[str, Any]]:
    if len(citations) >= limit:
        return citations

    seen = {
        (
            str(item.get("document_id", "")),
            str(item.get("fragment_id", "")),
            str(item.get("anchor_label", "")),
        )
        for item in citations
    }
    next_index = len(citations) + 1
    for relation in structured_context.get("relations", []):
        for ref in relation.get("evidence_refs", []):
            key = (
                str(ref.get("document_id", "")),
                str(ref.get("fragment_id", "")),
                str(ref.get("anchor_label", "")),
            )
            if key in seen:
                continue
            seen.add(key)
            citations.append(
                {
                    "citation_id": f"c{next_index}",
                    "page_title": relation.get("title", relation.get("package_id", "review-package")),
                    "file_name": ref.get("file_name", ref.get("document_id", "")),
                    "anchor_label": ref.get("anchor_label", "source"),
                    "quote": ref.get("quote", ""),
                    "document_id": ref.get("document_id", ""),
                    "fragment_id": ref.get("fragment_id", ""),
                }
            )
            next_index += 1
            if len(citations) >= limit:
                return citations
    return citations


def _ref_quote_from_page(page: WikiPage, ref: dict[str, Any]) -> str:
    for section in page.sections:
        if ref in section.source_refs:
            return section.content[:200]
    return page.summary[:200]


def _deterministic_answer(
    question: str,
    pages: list[WikiPage],
    citations: list[dict[str, Any]],
    structured_context: dict[str, Any],
) -> str:
    structured_relations = structured_context.get("relations", [])
    if not pages and not structured_relations:
        return "根据现有 Wiki 内容，无法回答此问题。"

    lines = [f"针对问题“{question}”，当前可复用的已审批知识如下：", ""]
    if structured_relations:
        lines.append("结构化映射：")
        for index, relation in enumerate(structured_relations[:5], 1):
            citation_label = f"[c{index}]" if index <= len(citations) else ""
            lines.append(
                f"{index}. {relation['from_object_name']} -> {relation['to_object_name']} "
                f"({relation['relation_type']} / {relation['claim_type']}){citation_label}"
            )
        lines.append("")
    if pages:
        lines.append("相关 Wiki 页面：")
        for index, page in enumerate(pages[:3], 1):
            citation_offset = len(structured_relations[:5]) + index
            citation_label = f"[c{citation_offset}]" if citation_offset <= len(citations) else ""
            lines.append(f"{index}. {page.title}：{page.summary}{citation_label}")
    if citations:
        lines.extend(["", "优先证据："])
        for citation in citations[:4]:
            lines.append(f"- [{citation['citation_id']}] {citation['quote']}")
    return "\n".join(lines)


def _confidence_label(value: float) -> str:
    if value >= 0.75:
        return "high"
    if value >= 0.35:
        return "medium"
    return "low"


def _suggested_questions(
    question: str,
    matched_pages: list[dict[str, Any]],
    structured_context: dict[str, Any],
) -> list[str]:
    normalized = question.lower()
    suggestions: list[str] = []
    if "r2" in normalized or "po" in normalized:
        suggestions.extend(
            [
                "R2 阶段的入口条件和出口条件分别是什么？",
                "R2 阶段 PO 需要准备哪些记录或模板？",
                "R2 阶段哪些职责需要 RA、QA 或 PM 参与？",
            ]
        )
    if "reference" in normalized or "引用" in question or "来源" in question:
        suggestions.append("把这些结论按文件、章节和 quote 列成 Reference 表。")
    if structured_context.get("relations"):
        suggestions.append("这些流程步骤分别由哪些角色负责，产出哪些记录？")
    if matched_pages:
        first_title = str(matched_pages[0].get("title", "")).strip()
        if first_title:
            suggestions.append(f"基于《{first_title}》生成一个可粘贴到飞书的流程说明。")
    suggestions.extend(
        [
            "这份流程文档如何操作？",
            "现在在 R2 阶段，我作为 PO 应该做什么？",
            "不同 BU 对这个流程有哪些差异？",
        ]
    )
    deduped: list[str] = []
    for item in suggestions:
        if item and item not in deduped:
            deduped.append(item)
    return deduped[:5]


def _lint_items(report: Any) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, issue in enumerate(report.issues, 1):
        items.append(
            {
                "issue_id": f"lint-{index:03d}",
                "type": issue.issue_type,
                "title": issue.description.split("，")[0][:60],
                "target": issue.page_id,
                "severity": issue.severity,
                "detail": issue.description,
                "suggestion": issue.suggestion,
                "status": "proposed" if issue.auto_fixable else "open",
            }
        )
    return items


if __name__ == "__main__":  # pragma: no cover - manual run
    import uvicorn

    uvicorn.run("App.api:app", host="127.0.0.1", port=8000, reload=False)
