from __future__ import annotations

from collections import Counter
from typing import Any

from Tool.chunking.section_chunks import SectionChunk
from Tool.retrieval.section_index import retrieve_sections

STATUS_KEYS = ("pass", "warn", "fail", "na")


def evaluate_retrieval_cases(
    chunks: list[SectionChunk],
    cases: list[dict[str, Any]],
    *,
    top_k: int = 8,
    retriever: Any | None = None,
) -> dict[str, Any]:
    case_results: list[dict[str, Any]] = []
    findings: list[dict[str, Any]] = []
    for case in cases:
        question = str(case.get("question", ""))
        source_scope = case.get("source_scope") or {"mode": "all_sources"}
        result = (
            retriever.retrieve(question, chunks, source_scope=source_scope, top_k=top_k)
            if retriever is not None
            else retrieve_sections(question, chunks, source_scope=source_scope, top_k=top_k)
        )
        failures = _case_failures(case, result)
        status = "fail" if failures else "pass"
        finding = {
            "eval_id": "R1-01",
            "case_id": case.get("case_id", "unknown"),
            "status": status,
            "message": "retrieval expected evidence found" if not failures else "retrieval missed expected evidence",
            "reference": "REF-RETRIEVAL",
            "details": failures,
        }
        findings.append(finding)
        case_results.append(
            {
                "case_id": case.get("case_id", "unknown"),
                "question": case.get("question", ""),
                "status": status,
                "top_hits": [_hit_summary(hit.to_dict()) for hit in result.hits],
                "strategy_used": result.strategy_used,
                "evidence_coverage": result.evidence_coverage,
                "details": failures,
            }
        )

    pass_count = len([case for case in case_results if case["status"] == "pass"])
    total = len(case_results)
    return {
        "eval_summary": _summary(findings),
        "metrics": {"case_count": total, "recall_at_k": round(pass_count / total, 4) if total else 0.0},
        "findings": findings,
        "cases": case_results,
    }


def compare_retrieval_backends(
    chunks: list[SectionChunk],
    cases: list[dict[str, Any]],
    *,
    retrievers: dict[str, Any],
    top_k: int = 8,
) -> dict[str, Any]:
    backend_reports: dict[str, Any] = {}
    findings: list[dict[str, Any]] = []
    for backend_name, retriever in retrievers.items():
        report = evaluate_retrieval_cases(chunks, cases, top_k=top_k, retriever=retriever)
        backend_reports[backend_name] = report
        failures = report["eval_summary"]["fail"]
        findings.append(
            {
                "eval_id": "R2-01",
                "backend": backend_name,
                "status": "pass" if failures == 0 else "warn",
                "message": "retrieval backend passed eval cases" if failures == 0 else "retrieval backend missed eval cases",
                "reference": "REF-RETRIEVAL",
                "details": {"failures": failures, "metrics": report["metrics"]},
            }
        )
    best_backend = _best_backend(backend_reports)
    return {
        "schema_version": "retrieval-backend-comparison-v0.1",
        "backends": backend_reports,
        "best_backend": best_backend,
        "eval_summary": _summary(findings),
        "findings": findings,
    }


def _case_failures(case: dict[str, Any], result: Any) -> dict[str, Any]:
    hits = result.hits
    hit_docs = [hit.chunk.document_id for hit in hits]
    hit_section_text = "\n".join(" ".join([hit.chunk.section_title, *hit.chunk.section_path]) for hit in hits).casefold()
    primary_section_text = "\n".join(" ".join([hit.chunk.section_title, *hit.chunk.section_path]) for hit in hits[:1]).casefold()
    hit_text = "\n".join(hit.chunk.text for hit in hits).casefold()
    failures: dict[str, Any] = {}

    expected_docs_any = [str(item) for item in case.get("expected_document_ids_any", [])]
    if expected_docs_any and not any(doc in hit_docs for doc in expected_docs_any):
        failures["missing_expected_document_ids_any"] = expected_docs_any

    expected_docs_all = [str(item) for item in case.get("expected_document_ids_all", [])]
    missing_docs_all = [doc for doc in expected_docs_all if doc not in hit_docs]
    if missing_docs_all:
        failures["missing_expected_document_ids_all"] = missing_docs_all

    expected_sections = [str(item) for item in case.get("expected_section_terms_any", [])]
    if expected_sections and not any(term.casefold() in hit_section_text for term in expected_sections):
        failures["missing_expected_section_terms"] = expected_sections

    expected_terms = [str(item) for item in case.get("expected_terms_any", [])]
    if expected_terms and not any(term.casefold() in hit_text for term in expected_terms):
        failures["missing_expected_terms"] = expected_terms

    forbidden_sections = [str(item) for item in case.get("forbidden_section_terms", [])]
    forbidden_hits = [term for term in forbidden_sections if term.casefold() in primary_section_text]
    if forbidden_hits:
        failures["forbidden_primary_section_terms_found"] = forbidden_hits

    if not hits:
        failures["no_hits"] = True
    return failures


def _hit_summary(hit_payload: dict[str, Any]) -> dict[str, Any]:
    chunk = hit_payload["chunk"]
    return {
        "chunk_id": chunk["chunk_id"],
        "document_id": chunk["document_id"],
        "section_id": chunk["section_id"],
        "section_title": chunk["section_title"],
        "chunk_type": chunk["chunk_type"],
        "score": hit_payload["score"],
        "matched_terms": hit_payload["matched_terms"],
        "quote": chunk["quote"],
        "source_refs": chunk["source_refs"],
    }


def _summary(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(finding.get("status", "na")) for finding in findings)
    return {key: int(counts.get(key, 0)) for key in STATUS_KEYS}


def _best_backend(backend_reports: dict[str, Any]) -> dict[str, Any]:
    if not backend_reports:
        return {"name": "", "metrics": {}}
    name, report = max(
        backend_reports.items(),
        key=lambda item: (float(item[1]["metrics"].get("recall_at_k", 0.0)), -int(item[1]["eval_summary"].get("fail", 0))),
    )
    return {"name": name, "metrics": report["metrics"]}