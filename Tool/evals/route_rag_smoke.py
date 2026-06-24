from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from Tool.chunking.section_chunks import SectionChunk, build_section_chunks, normalize_search_text
from Tool.evals.parser_rag_smoke import RELEASE0_DOCUMENT_ALIAS_MAP, _chunk_quality, _document_quality, _load_required_canonicals
from Tool.evals.release0_smoke import release0_smoke_cases
from Tool.pipelines.common import PARSED_DIR
from Tool.workflows.answer import parse_question_intent


def release0_route_rag_smoke_report(
    *,
    parsed_dir: str | Path = PARSED_DIR,
    document_alias_map: dict[str, str] | None = None,
    cases: list[dict[str, Any]] | None = None,
    top_k: int = 8,
) -> dict[str, Any]:
    alias_map = document_alias_map or RELEASE0_DOCUMENT_ALIAS_MAP
    eval_cases = cases or release0_smoke_cases()
    resolved_cases = [_resolve_case_aliases(case, alias_map) for case in eval_cases]
    required_document_ids = _required_document_ids(resolved_cases)
    canonicals, missing_documents = _load_required_canonicals(Path(parsed_dir), required_document_ids)
    chunks = [chunk for canonical in canonicals for chunk in build_section_chunks(canonical)]
    case_diagnostics = [_route_case_diagnostic(case, chunks, top_k=top_k) for case in resolved_cases]
    missing_document_findings = [
        {
            "case_id": "document-load",
            "status": "fail",
            "failure_category": "document_load_gap",
            "message": "required parsed canonical document is missing",
            "details": item,
        }
        for item in missing_documents
    ]
    findings = [*missing_document_findings, *[item for item in case_diagnostics if item["status"] != "pass"]]
    return {
        "schema_version": "release0-route-rag-smoke-v0.1",
        "purpose": "Validate Release-0 questions through the session runtime route, query pack, hybrid retrieval, and route-aware rerank path.",
        "document_alias_map": dict(alias_map),
        "documents": [_document_quality(canonical) for canonical in canonicals],
        "chunk_quality": _chunk_quality(chunks),
        "metrics": _metrics(case_diagnostics),
        "failure_summary": _failure_summary(findings),
        "case_diagnostics": case_diagnostics,
        "findings": findings,
    }


def _resolve_case_aliases(case: dict[str, Any], alias_map: dict[str, str]) -> dict[str, Any]:
    resolved = dict(case)
    scope = dict(case.get("source_scope") or {})
    aliases = list(scope.get("document_aliases", []))
    document_ids = aliases or list(scope.get("document_ids", []))
    resolved_scope = {
        "mode": "selected_docs" if scope.get("mode") in {"selected_docs", "multi_docs"} else scope.get("mode", "selected_docs"),
        "document_ids": [alias_map.get(str(item), str(item)) for item in document_ids],
    }
    resolved["source_scope"] = resolved_scope
    return resolved


def _required_document_ids(cases: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for case in cases:
        for document_id in (case.get("source_scope") or {}).get("document_ids", []):
            if document_id not in ids:
                ids.append(str(document_id))
    return ids


def _route_case_diagnostic(case: dict[str, Any], chunks: list[SectionChunk], *, top_k: int) -> dict[str, Any]:
    from App.api import _route_aware_retrieval_result, _session_query_rewrite, _session_retrieval_top_k, _session_retrieve_sections, _session_route_plan

    question = str(case.get("question", ""))
    source_scope = case.get("source_scope") or {"mode": "selected_docs", "document_ids": []}
    intent = parse_question_intent(question)
    route_plan = _session_route_plan(question, intent)
    query_rewrite = _session_query_rewrite(question, intent, route_plan)
    route_plan = {**route_plan, "query_pack": query_rewrite.get("query_pack", {})}
    retrieval_result = _session_retrieve_sections(
        str(query_rewrite["rewritten_query"]),
        chunks,
        source_scope=source_scope,
        top_k=_session_retrieval_top_k(top_k, route_plan),
    )
    retrieval_result = _route_aware_retrieval_result(retrieval_result, route_plan, top_k=top_k)
    failures = _case_failures(case, route_plan, retrieval_result.hits)
    return {
        "case_id": case.get("case_id", "unknown"),
        "question": question,
        "status": "fail" if failures else "pass",
        "failure_category": _failure_category(failures),
        "expected_route_id": case.get("expected_route_id", ""),
        "actual_route_id": route_plan.get("route_id", ""),
        "query_pack": query_rewrite.get("query_pack", {}),
        "strategy_used": retrieval_result.strategy_used,
        "top_hits": [_hit_summary(hit) for hit in retrieval_result.hits[:5]],
        "details": failures,
    }


def _case_failures(case: dict[str, Any], route_plan: dict[str, Any], hits: list[Any]) -> dict[str, Any]:
    failures: dict[str, Any] = {}
    expected_route = str(case.get("expected_route_id", ""))
    if expected_route and route_plan.get("route_id") != expected_route:
        failures["route_mismatch"] = {"expected": expected_route, "actual": route_plan.get("route_id")}

    expected = case.get("expected_evidence") or {}
    section_terms = [str(item) for item in expected.get("section_terms_any", [])]
    evidence_terms = [str(item) for item in expected.get("terms_any", [])]
    hit_section_text = normalize_search_text("\n".join(" ".join([hit.chunk.section_title, *hit.chunk.section_path]) for hit in hits))
    hit_text = normalize_search_text("\n".join(" ".join([hit.chunk.text, hit.chunk.quote, " ".join(hit.chunk.signals)]) for hit in hits))
    if section_terms and not any(normalize_search_text(term) in hit_section_text for term in section_terms):
        failures["missing_expected_section_terms"] = section_terms
    if evidence_terms and not any(normalize_search_text(term) in hit_text for term in evidence_terms):
        failures["missing_expected_terms"] = evidence_terms
    if not hits:
        failures["no_hits"] = True
    return failures


def _failure_category(failures: dict[str, Any]) -> str:
    if not failures:
        return "pass"
    if "route_mismatch" in failures:
        return "route_gap"
    if "no_hits" in failures:
        return "retrieval_gap"
    return "route_rerank_gap"


def _hit_summary(hit: Any) -> dict[str, Any]:
    return {
        "chunk_id": hit.chunk.chunk_id,
        "document_id": hit.chunk.document_id,
        "section_id": hit.chunk.section_id,
        "section_title": hit.chunk.section_title,
        "chunk_type": hit.chunk.chunk_type,
        "score": hit.score,
        "matched_terms": list(hit.matched_terms),
        "quote": hit.chunk.quote,
        "source_refs": hit.chunk.source_refs,
    }


def _metrics(case_diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(case_diagnostics)
    passed = len([item for item in case_diagnostics if item["status"] == "pass"])
    route_matches = len([item for item in case_diagnostics if item.get("actual_route_id") == item.get("expected_route_id")])
    return {
        "case_count": total,
        "pass_count": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "route_accuracy": round(route_matches / total, 4) if total else 0.0,
    }


def _failure_summary(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(item.get("failure_category", "unknown")) for item in findings)
    return {key: int(counts.get(key, 0)) for key in ("route_gap", "route_rerank_gap", "retrieval_gap", "document_load_gap")}
