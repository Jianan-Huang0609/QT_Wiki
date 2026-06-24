from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from Tool.chunking.section_chunks import SectionChunk, build_section_chunks, normalize_search_text
from Tool.contracts.canonical import CanonicalDocument, load_canonical_document
from Tool.evals.parser_quality import evaluate_parser_quality
from Tool.evals.release0_smoke import release0_retrieval_eval_cases
from Tool.evals.retrieval_eval import evaluate_retrieval_cases
from Tool.pipelines.common import PARSED_DIR
from Tool.retrieval.retrievers import FullTextRetriever, HybridRetriever, RuleSectionRetriever

RELEASE0_DOCUMENT_ALIAS_MAP = {
    "ct_pep": "doc-20260611163219-f56c6cf9",
    "mi_pep": "doc-20260611163304-4cbf18e4",
    "xp_pep": "doc-20260611163330-ea3c2cc8",
}


def release0_parser_rag_smoke_report(
    *,
    parsed_dir: str | Path = PARSED_DIR,
    document_alias_map: dict[str, str] | None = None,
    cases: list[dict[str, Any]] | None = None,
    top_k: int = 8,
) -> dict[str, Any]:
    alias_map = document_alias_map or RELEASE0_DOCUMENT_ALIAS_MAP
    eval_cases = cases or release0_retrieval_eval_cases()
    resolved_cases = [_resolve_case_aliases(case, alias_map) for case in eval_cases]
    required_document_ids = _required_document_ids(resolved_cases)
    canonicals, missing_documents = _load_required_canonicals(Path(parsed_dir), required_document_ids)
    chunks = [chunk for canonical in canonicals for chunk in build_section_chunks(canonical)]
    retriever = HybridRetriever([RuleSectionRetriever(), FullTextRetriever()])
    retrieval_report = evaluate_retrieval_cases(chunks, resolved_cases, top_k=top_k, retriever=retriever)
    case_diagnostics = [
        _case_diagnostic(case, result, chunks)
        for case, result in zip(resolved_cases, retrieval_report["cases"])
    ]
    missing_document_findings = [
        {
            "case_id": "document-load",
            "status": "fail",
            "failure_category": "parser_structure_gap",
            "message": "required parsed canonical document is missing",
            "details": item,
        }
        for item in missing_documents
    ]
    findings = [*missing_document_findings, *[item for item in case_diagnostics if item["status"] != "pass"]]
    return {
        "schema_version": "release0-parser-rag-smoke-v0.1",
        "purpose": "Classify whether Release-0 smoke misses come from chat routing, chunks/source context, parser structure, tables, or OCR gaps.",
        "document_alias_map": dict(alias_map),
        "documents": [_document_quality(canonical) for canonical in canonicals],
        "chunk_quality": _chunk_quality(chunks),
        "retrieval_metrics": retrieval_report["metrics"],
        "retrieval_eval_summary": retrieval_report["eval_summary"],
        "failure_summary": _failure_summary(findings),
        "case_diagnostics": case_diagnostics,
        "findings": findings,
    }


def _resolve_case_aliases(case: dict[str, Any], alias_map: dict[str, str]) -> dict[str, Any]:
    resolved = dict(case)
    scope = dict(case.get("source_scope") or {})
    document_ids = [alias_map.get(str(item), str(item)) for item in scope.get("document_ids", [])]
    if scope.get("mode") == "selected_docs" and document_ids:
        scope["document_ids"] = document_ids
    resolved["source_scope"] = scope
    return resolved


def _required_document_ids(cases: list[dict[str, Any]]) -> list[str]:
    ids: list[str] = []
    for case in cases:
        scope = case.get("source_scope") or {}
        for document_id in scope.get("document_ids", []):
            if document_id not in ids:
                ids.append(str(document_id))
    return ids


def _load_required_canonicals(parsed_dir: Path, document_ids: list[str]) -> tuple[list[CanonicalDocument], list[dict[str, str]]]:
    canonicals: list[CanonicalDocument] = []
    missing: list[dict[str, str]] = []
    for document_id in document_ids:
        path = parsed_dir / f"{document_id}.json"
        if not path.exists():
            missing.append({"document_id": document_id, "path": str(path)})
            continue
        canonicals.append(load_canonical_document(path))
    return canonicals, missing


def _document_quality(canonical: CanonicalDocument) -> dict[str, Any]:
    workflow = canonical.document.metadata.get("parse_workflow") or {}
    eval_summary = workflow.get("eval_summary") or canonical.document.metadata.get("eval_summary") or {}
    quality_report = evaluate_parser_quality(canonical)
    return {
        "document_id": canonical.document.document_id,
        "file_name": canonical.document.file_name,
        "parse_status": canonical.parse_status,
        "counts": {
            "sections": len(canonical.sections),
            "fragments": len(canonical.fragments),
            "tables": len(canonical.tables),
            "figures": len(canonical.figures),
        },
        "eval_summary": eval_summary,
        "quality_metrics": quality_report["metrics"],
        "review_eval_ids": [str(item.get("eval_id")) for item in workflow.get("review_items", [])],
    }


def _chunk_quality(chunks: list[SectionChunk]) -> dict[str, Any]:
    missing_source_refs = [chunk.chunk_id for chunk in chunks if not chunk.source_refs]
    missing_quote = [chunk.chunk_id for chunk in chunks if not chunk.quote.strip()]
    missing_anchor = [chunk.chunk_id for chunk in chunks if not any(ref.get("anchor_label") or ref.get("anchors") for ref in chunk.source_refs)]
    type_counts = Counter(chunk.chunk_type for chunk in chunks)
    return {
        "chunk_count": len(chunks),
        "chunk_type_counts": dict(sorted(type_counts.items())),
        "chunks_without_source_refs": len(missing_source_refs),
        "chunks_without_quote": len(missing_quote),
        "chunks_without_anchor": len(missing_anchor),
        "sample_gaps": {
            "source_refs": missing_source_refs[:5],
            "quote": missing_quote[:5],
            "anchor": missing_anchor[:5],
        },
    }


def _case_diagnostic(case: dict[str, Any], retrieval_result: dict[str, Any], chunks: list[SectionChunk]) -> dict[str, Any]:
    scoped_chunks = _scoped_chunks(chunks, case.get("source_scope") or {})
    presence = _evidence_presence(case, scoped_chunks)
    category = "pass" if retrieval_result["status"] == "pass" else _failure_category(presence)
    return {
        "case_id": case.get("case_id", "unknown"),
        "question": case.get("question", ""),
        "status": retrieval_result["status"],
        "failure_category": category,
        "retrieval_details": retrieval_result.get("details", {}),
        "evidence_presence": presence,
        "top_hits": retrieval_result.get("top_hits", [])[:3],
    }


def _scoped_chunks(chunks: list[SectionChunk], source_scope: dict[str, Any]) -> list[SectionChunk]:
    if source_scope.get("mode") != "selected_docs":
        return chunks
    document_ids = {str(item) for item in source_scope.get("document_ids", [])}
    return [chunk for chunk in chunks if chunk.document_id in document_ids]


def _evidence_presence(case: dict[str, Any], chunks: list[SectionChunk]) -> dict[str, Any]:
    expected_terms = [str(item) for item in case.get("expected_terms_any", [])]
    expected_sections = [str(item) for item in case.get("expected_section_terms_any", [])]
    matching_chunks = [_chunk_match_summary(chunk, expected_terms, expected_sections) for chunk in chunks]
    matching_chunks = [item for item in matching_chunks if item["matched_terms"] or item["matched_section_terms"]]
    table_matches = [item for item in matching_chunks if item["chunk_type"] == "table"]
    section_matches = [item for item in matching_chunks if item["chunk_type"] == "section"]
    matching_without_source_context = [item for item in matching_chunks if not item["has_source_ref"] or not item["has_anchor"] or not item["has_quote"]]
    return {
        "scoped_chunk_count": len(chunks),
        "matched_chunk_count": len(matching_chunks),
        "section_match_count": len(section_matches),
        "table_match_count": len(table_matches),
        "matching_chunks_without_source_context": matching_without_source_context[:5],
        "matched_chunks": matching_chunks[:5],
    }


def _chunk_match_summary(chunk: SectionChunk, expected_terms: list[str], expected_sections: list[str]) -> dict[str, Any]:
    text = normalize_search_text(" ".join([chunk.text, " ".join(chunk.signals)]))
    section_text = normalize_search_text(" ".join([chunk.section_title, *chunk.section_path]))
    refs = chunk.source_refs
    return {
        "chunk_id": chunk.chunk_id,
        "document_id": chunk.document_id,
        "section_title": chunk.section_title,
        "chunk_type": chunk.chunk_type,
        "matched_terms": [term for term in expected_terms if term.casefold() in text],
        "matched_section_terms": [term for term in expected_sections if term.casefold() in section_text or term.casefold() in text],
        "has_source_ref": bool(refs),
        "has_anchor": any(ref.get("anchor_label") or ref.get("anchors") for ref in refs),
        "has_quote": bool(chunk.quote.strip()),
    }


def _failure_category(presence: dict[str, Any]) -> str:
    if presence["scoped_chunk_count"] == 0:
        return "parser_structure_gap"
    if presence["matched_chunk_count"] == 0:
        return "parser_structure_gap"
    if presence["table_match_count"] and not presence["section_match_count"]:
        return "table_gap"
    if presence["matching_chunks_without_source_context"]:
        return "chunk_source_context_gap"
    return "chat_route_query_answer_gap"


def _failure_summary(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(item.get("failure_category", "unknown")) for item in findings)
    return {key: int(counts.get(key, 0)) for key in ("chat_route_query_answer_gap", "chunk_source_context_gap", "parser_structure_gap", "table_gap", "scanning_ocr_gap")}
