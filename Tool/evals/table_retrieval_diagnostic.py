from __future__ import annotations

from pathlib import Path
from typing import Any

from Tool.chunking.section_chunks import SectionChunk, build_section_chunks, normalize_search_text
from Tool.evals.parser_rag_smoke import RELEASE0_DOCUMENT_ALIAS_MAP, _load_required_canonicals
from Tool.evals.semantic_rag_smoke import EmbedText, _embedding_function, is_semantic_enabled_for_route
from Tool.pipelines.common import PARSED_DIR
from Tool.retrieval.retrievers import FullTextRetriever, HybridRetriever, RuleSectionRetriever, VectorRetriever
from Tool.workflows.answer import parse_question_intent

DEFAULT_ARTIFACT_PATH = Path("Design/review-artifacts/table-retrieval-diagnostic.md")


def table_retrieval_diagnostic_report(
    *,
    parsed_dir: str | Path = PARSED_DIR,
    document_alias_map: dict[str, str] | None = None,
    cases: list[dict[str, Any]] | None = None,
    chunks: list[SectionChunk] | None = None,
    embed_text: EmbedText | None = None,
    top_k: int = 8,
) -> dict[str, Any]:
    alias_map = document_alias_map or RELEASE0_DOCUMENT_ALIAS_MAP
    eval_cases = [_resolve_case_aliases(case, alias_map) for case in (cases or _default_cases())]
    all_chunks = chunks if chunks is not None else _load_chunks(Path(parsed_dir), eval_cases)
    lexical_retriever = HybridRetriever([RuleSectionRetriever(), FullTextRetriever()])
    route_gated_retriever = _route_gated_retriever(all_chunks, embed_text)
    diagnostics = [
        _case_diagnostic(
            case,
            all_chunks,
            lexical_retriever=lexical_retriever,
            route_gated_retriever=route_gated_retriever,
            top_k=top_k,
        )
        for case in eval_cases
    ]
    return {
        "schema_version": "table-retrieval-diagnostic-v0.1",
        "purpose": "Diagnose whether real table questions can reach table chunks, anchored cells, and extractable row/cell evidence.",
        "metrics": _metrics(diagnostics),
        "case_diagnostics": diagnostics,
        "findings": [item for item in diagnostics if item["status"] != "pass"],
    }


def write_table_retrieval_diagnostic_artifact(report: dict[str, Any], *, output_path: str | Path = DEFAULT_ARTIFACT_PATH) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_table_retrieval_diagnostic_markdown(report), encoding="utf-8")
    return path


def render_table_retrieval_diagnostic_markdown(report: dict[str, Any]) -> str:
    metrics = report.get("metrics", {})
    lines = [
        "# Table Retrieval Diagnostic",
        "",
        f"Schema: `{report.get('schema_version', '')}`",
        "",
        "## Summary",
        "",
        f"- Case count: {metrics.get('case_count', 0)}",
        f"- Pass count: {metrics.get('pass_count', 0)}",
        f"- Pass rate: {metrics.get('pass_rate', 0.0)}",
        f"- Table-hit rate: {metrics.get('table_hit_rate', 0.0)}",
        "",
        "## Cases",
        "",
    ]
    for item in report.get("case_diagnostics", []):
        lines.extend(
            [
                f"### {item.get('case_id', 'unknown')}",
                "",
                f"- Status: `{item.get('status', '')}`",
                f"- Failure category: `{item.get('failure_category', '')}`",
                f"- Route: `{item.get('actual_route_id', '')}` / expected `{item.get('expected_route_id', '')}`",
                f"- Route-gated semantic enabled: `{item.get('route_gated_semantic_enabled', False)}`",
                f"- Scoped table chunks: {item.get('scoped_table_chunk_count', 0)}",
                f"- Top table hit: `{item.get('top_table_hit', {}).get('chunk_id', '')}`",
                f"- Question: {item.get('question', '')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _default_cases() -> list[dict[str, Any]]:
    return [
        {
            "case_id": "rag03-mi-qmp-table-owner",
            "question": "MI PEP 这个表格里 QMP 的交付物责任是什么？",
            "source_scope": {"mode": "selected_docs", "document_aliases": ["mi_pep"]},
            "expected_route_id": "table_lookup",
            "expected_terms_any": ["QMP", "responsibility", "responsible", "责任"],
            "expected_table_signals_any": ["role_table", "deliverable_table"],
        }
    ]


def _resolve_case_aliases(case: dict[str, Any], alias_map: dict[str, str]) -> dict[str, Any]:
    resolved = dict(case)
    scope = dict(case.get("source_scope") or {})
    aliases = list(scope.get("document_aliases", []))
    document_ids = aliases or list(scope.get("document_ids", []))
    resolved["source_scope"] = {
        "mode": "selected_docs" if scope.get("mode") in {"selected_docs", "multi_docs"} else scope.get("mode", "selected_docs"),
        "document_ids": [alias_map.get(str(item), str(item)) for item in document_ids],
    }
    return resolved


def _load_chunks(parsed_dir: Path, cases: list[dict[str, Any]]) -> list[SectionChunk]:
    document_ids: list[str] = []
    for case in cases:
        for document_id in (case.get("source_scope") or {}).get("document_ids", []):
            if document_id not in document_ids:
                document_ids.append(str(document_id))
    canonicals, _missing = _load_required_canonicals(parsed_dir, document_ids)
    return [chunk for canonical in canonicals for chunk in build_section_chunks(canonical)]


def _route_gated_retriever(chunks: list[SectionChunk], embed_text: EmbedText | None) -> HybridRetriever:
    vector_embed = _embedding_function(embed_text, chunks)
    return HybridRetriever([RuleSectionRetriever(), FullTextRetriever(), VectorRetriever(embed_text=vector_embed)])


def _case_diagnostic(
    case: dict[str, Any],
    chunks: list[SectionChunk],
    *,
    lexical_retriever: HybridRetriever,
    route_gated_retriever: HybridRetriever,
    top_k: int,
) -> dict[str, Any]:
    from App.api import _route_aware_retrieval_result, _session_query_rewrite, _session_route_plan

    question = str(case.get("question", ""))
    source_scope = case.get("source_scope") or {"mode": "selected_docs", "document_ids": []}
    intent = parse_question_intent(question)
    route_plan = _session_route_plan(question, intent)
    query_rewrite = _session_query_rewrite(question, intent, route_plan)
    route_plan = {**route_plan, "query_pack": query_rewrite.get("query_pack", {})}
    route_id = str(route_plan.get("route_id", ""))
    semantic_enabled = is_semantic_enabled_for_route(route_id)
    retriever = route_gated_retriever if semantic_enabled else lexical_retriever
    retrieval_result = retriever.retrieve(str(query_rewrite.get("rewritten_query") or question), chunks, source_scope=source_scope, top_k=top_k)
    retrieval_result = _route_aware_retrieval_result(retrieval_result, route_plan, top_k=top_k)
    scoped_table_chunks = _scoped_table_chunks(chunks, source_scope)
    failures = _case_failures(case, route_plan, retrieval_result.hits, scoped_table_chunks)
    top_table_hit = next((_hit_summary(hit) for hit in retrieval_result.hits if _is_table_chunk(hit.chunk)), {})
    return {
        "case_id": case.get("case_id", "unknown"),
        "question": question,
        "status": "fail" if failures else "pass",
        "failure_category": _failure_category(failures),
        "expected_route_id": case.get("expected_route_id", ""),
        "actual_route_id": route_id,
        "route_gated_semantic_enabled": semantic_enabled,
        "scoped_table_chunk_count": len(scoped_table_chunks),
        "top_table_hit": top_table_hit,
        "top_hits": [_hit_summary(hit) for hit in retrieval_result.hits[:5]],
        "details": failures,
    }


def _case_failures(case: dict[str, Any], route_plan: dict[str, Any], hits: list[Any], scoped_table_chunks: list[SectionChunk]) -> dict[str, Any]:
    failures: dict[str, Any] = {}
    expected_route = str(case.get("expected_route_id", ""))
    if expected_route and route_plan.get("route_id") != expected_route:
        failures["route_mismatch"] = {"expected": expected_route, "actual": route_plan.get("route_id")}
    if not scoped_table_chunks:
        failures["no_scoped_table_chunks"] = True
        return failures
    table_hits = [hit for hit in hits if _is_table_chunk(hit.chunk)]
    if not table_hits:
        failures["no_table_hit_in_top_k"] = True
        return failures
    if not any(_has_table_anchor(hit.chunk) for hit in table_hits):
        failures["missing_table_anchor"] = True
    expected_terms = [str(item) for item in case.get("expected_terms_any", [])]
    hit_text = normalize_search_text("\n".join(hit.chunk.text for hit in table_hits))
    if expected_terms and not any(normalize_search_text(term) in hit_text for term in expected_terms):
        failures["missing_expected_cell_terms"] = expected_terms
    expected_signals = [str(item) for item in case.get("expected_table_signals_any", [])]
    hit_signals = {signal for hit in table_hits for signal in hit.chunk.signals}
    if expected_signals and not any(signal in hit_signals for signal in expected_signals):
        failures["missing_expected_table_signals"] = expected_signals
    return failures


def _failure_category(failures: dict[str, Any]) -> str:
    if not failures:
        return "pass"
    if "route_mismatch" in failures:
        return "query_rewrite_gap"
    if "no_scoped_table_chunks" in failures:
        return "parser_provider_gap"
    if "no_table_hit_in_top_k" in failures or "missing_expected_table_signals" in failures:
        return "table_chunk_flattening_gap"
    if "missing_table_anchor" in failures:
        return "table_anchor_gap"
    return "composer_table_answer_gap"


def _scoped_table_chunks(chunks: list[SectionChunk], source_scope: dict[str, Any]) -> list[SectionChunk]:
    document_ids = set(source_scope.get("document_ids", [])) if source_scope.get("mode") == "selected_docs" else set()
    scoped = [chunk for chunk in chunks if not document_ids or chunk.document_id in document_ids]
    return [chunk for chunk in scoped if _is_table_chunk(chunk)]


def _is_table_chunk(chunk: SectionChunk) -> bool:
    return chunk.chunk_type == "table" or "role_table" in chunk.signals or "deliverable_table" in chunk.signals


def _has_table_anchor(chunk: SectionChunk) -> bool:
    return bool(chunk.anchors.get("cell_range") or chunk.anchors.get("page") or chunk.anchors.get("table_index"))


def _hit_summary(hit: Any) -> dict[str, Any]:
    return {
        "chunk_id": hit.chunk.chunk_id,
        "document_id": hit.chunk.document_id,
        "section_id": hit.chunk.section_id,
        "section_title": hit.chunk.section_title,
        "chunk_type": hit.chunk.chunk_type,
        "score": hit.score,
        "matched_terms": list(hit.matched_terms),
        "signals": list(hit.chunk.signals),
        "anchors": dict(hit.chunk.anchors),
        "quote": hit.chunk.quote,
    }


def _metrics(diagnostics: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(diagnostics)
    passed = len([item for item in diagnostics if item["status"] == "pass"])
    table_hits = len([item for item in diagnostics if item.get("top_table_hit")])
    return {
        "case_count": total,
        "pass_count": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "table_hit_rate": round(table_hits / total, 4) if total else 0.0,
    }