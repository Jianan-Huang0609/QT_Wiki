from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from Tool.chunking.section_chunks import SectionChunk, build_section_chunks, normalize_search_text
from Tool.evals.parser_rag_smoke import RELEASE0_DOCUMENT_ALIAS_MAP, _load_required_canonicals
from Tool.evals.release0_smoke import release0_smoke_cases
from Tool.pipelines.common import PARSED_DIR
from Tool.retrieval.embeddings import AzureEmbeddingAdapter
from Tool.retrieval.retrievers import FullTextRetriever, HybridRetriever, RuleSectionRetriever, VectorRetriever, _chunk_embedding_text
from Tool.workflows.answer import parse_question_intent

EmbedText = Callable[[str], list[float]]
DEFAULT_ARTIFACT_PATH = Path("Design/review-artifacts/semantic-rag-smoke.md")


def semantic_rag_smoke_report(
    *,
    parsed_dir: str | Path = PARSED_DIR,
    document_alias_map: dict[str, str] | None = None,
    chunks: list[SectionChunk] | None = None,
    cases: list[dict[str, Any]] | None = None,
    embed_text: EmbedText | None = None,
    top_k: int = 8,
) -> dict[str, Any]:
    eval_cases = cases or _release0_cases(document_alias_map or RELEASE0_DOCUMENT_ALIAS_MAP)
    all_chunks = chunks if chunks is not None else _load_chunks(Path(parsed_dir), eval_cases)
    lexical_retriever = HybridRetriever([RuleSectionRetriever(), FullTextRetriever()])
    lexical_cases = [_case_diagnostic(case, all_chunks, lexical_retriever, top_k=top_k) for case in eval_cases]
    embedding_status = {"backend": "azure:text-embedding-3-small", "status": "available", "error": ""}
    vector_embed = _embedding_function(embed_text, all_chunks)
    try:
        _probe_embedding(vector_embed)
        semantic_retriever = HybridRetriever([RuleSectionRetriever(), FullTextRetriever(), VectorRetriever(embed_text=vector_embed)])
        semantic_cases = [_case_diagnostic(case, all_chunks, semantic_retriever, top_k=top_k) for case in eval_cases]
        fallback_used = False
    except Exception as exc:
        embedding_status = {**embedding_status, "status": "failed", "error": str(exc)}
        semantic_cases = lexical_cases
        fallback_used = True

    return {
        "schema_version": "semantic-rag-smoke-v0.1",
        "purpose": "Compare lexical baseline retrieval with semantic-hybrid retrieval using in-memory selected-doc chunks.",
        "embedding": embedding_status,
        "backend_reports": {
            "lexical_baseline": _backend_report(lexical_cases, fallback_used=False),
            "semantic_hybrid": _backend_report(semantic_cases, fallback_used=fallback_used),
        },
        "comparison": _comparison(lexical_cases, semantic_cases),
        "case_diagnostics": [_combined_case(lexical, semantic) for lexical, semantic in zip(lexical_cases, semantic_cases)],
    }


def write_semantic_rag_smoke_artifact(report: dict[str, Any], *, output_path: str | Path = DEFAULT_ARTIFACT_PATH) -> Path:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_semantic_rag_smoke_markdown(report), encoding="utf-8")
    return path


def render_semantic_rag_smoke_markdown(report: dict[str, Any]) -> str:
    lexical = report.get("backend_reports", {}).get("lexical_baseline", {})
    semantic = report.get("backend_reports", {}).get("semantic_hybrid", {})
    lines = [
        "# Semantic RAG Smoke",
        "",
        f"Schema: `{report.get('schema_version', '')}`",
        "",
        "## Summary",
        "",
        f"- Embedding status: `{report.get('embedding', {}).get('status', '')}`",
        f"- Lexical recall@8: {lexical.get('metrics', {}).get('recall_at_8', 0.0)}",
        f"- Semantic recall@8: {semantic.get('metrics', {}).get('recall_at_8', 0.0)}",
        f"- Citation drift cases: {report.get('comparison', {}).get('citation_drift_count', 0)}",
        f"- Improved cases: {report.get('comparison', {}).get('improved_count', 0)}",
        f"- Regressed cases: {report.get('comparison', {}).get('regressed_count', 0)}",
        "",
        "## Cases",
        "",
    ]
    for item in report.get("case_diagnostics", []):
        lines.extend(
            [
                f"### {item.get('case_id', 'unknown')}",
                "",
                f"- Route: `{item.get('actual_route_id', '')}` / expected `{item.get('expected_route_id', '')}`",
                f"- Lexical: `{item.get('lexical_status', '')}` top `{item.get('lexical_top_hit', {}).get('chunk_id', '')}`",
                f"- Semantic: `{item.get('semantic_status', '')}` top `{item.get('semantic_top_hit', {}).get('chunk_id', '')}`",
                f"- Drift: `{item.get('citation_drift', False)}`",
                f"- Question: {item.get('question', '')}",
                "",
            ]
        )
    return "\n".join(lines).rstrip() + "\n"


def _release0_cases(alias_map: dict[str, str]) -> list[dict[str, Any]]:
    cases = []
    for case in release0_smoke_cases():
        resolved = dict(case)
        scope = dict(case.get("source_scope") or {})
        aliases = list(scope.get("document_aliases", []))
        document_ids = aliases or list(scope.get("document_ids", []))
        scope["mode"] = "selected_docs" if scope.get("mode") in {"selected_docs", "multi_docs"} else scope.get("mode", "selected_docs")
        scope["document_ids"] = [alias_map.get(str(item), str(item)) for item in document_ids]
        resolved["source_scope"] = scope
        expected = case.get("expected_evidence") or {}
        resolved["expected_terms_any"] = list(expected.get("terms_any", []))
        resolved["expected_section_terms_any"] = list(expected.get("section_terms_any", []))
        cases.append(resolved)
    return cases


def _load_chunks(parsed_dir: Path, cases: list[dict[str, Any]]) -> list[SectionChunk]:
    document_ids: list[str] = []
    for case in cases:
        for document_id in (case.get("source_scope") or {}).get("document_ids", []):
            if document_id not in document_ids:
                document_ids.append(str(document_id))
    canonicals, _missing = _load_required_canonicals(parsed_dir, document_ids)
    return [chunk for canonical in canonicals for chunk in build_section_chunks(canonical)]


def _probe_embedding(embed_text: EmbedText) -> None:
    vector = embed_text("semantic rag smoke probe")
    if not vector:
        raise ValueError("embedding probe returned an empty vector")


def _embedding_function(embed_text: EmbedText | None, chunks: list[SectionChunk]) -> EmbedText:
    cache: dict[str, list[float]] = {}
    if embed_text is not None:
        def cached(text: str) -> list[float]:
            if text not in cache:
                cache[text] = embed_text(text)
            return cache[text]

        return cached

    adapter = AzureEmbeddingAdapter.from_config()
    chunk_texts = _unique_texts([_chunk_embedding_text(chunk) for chunk in chunks])
    if chunk_texts:
        vectors = adapter.embed_texts(chunk_texts)
        cache.update({text: vector for text, vector in zip(chunk_texts, vectors)})

    def cached_azure(text: str) -> list[float]:
        if text not in cache:
            cache[text] = adapter.embed_text(text)
        return cache[text]

    return cached_azure


def _unique_texts(texts: list[str]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []
    for text in texts:
        if text not in seen:
            seen.add(text)
            result.append(text)
    return result


def _case_diagnostic(case: dict[str, Any], chunks: list[SectionChunk], retriever: Any, *, top_k: int) -> dict[str, Any]:
    from App.api import _route_aware_retrieval_result, _session_query_rewrite, _session_route_plan

    question = str(case.get("question", ""))
    source_scope = case.get("source_scope") or {"mode": "selected_docs", "document_ids": []}
    intent = parse_question_intent(question)
    route_plan = _session_route_plan(question, intent)
    query_rewrite = _session_query_rewrite(question, intent, route_plan)
    route_plan = {**route_plan, "query_pack": query_rewrite.get("query_pack", {})}
    retrieval_result = retriever.retrieve(str(query_rewrite.get("rewritten_query") or question), chunks, source_scope=source_scope, top_k=top_k)
    retrieval_result = _route_aware_retrieval_result(retrieval_result, route_plan, top_k=top_k)
    failures = _case_failures(case, route_plan, retrieval_result.hits)
    return {
        "case_id": case.get("case_id", "unknown"),
        "question": question,
        "status": "fail" if failures else "pass",
        "expected_route_id": case.get("expected_route_id", ""),
        "actual_route_id": route_plan.get("route_id", ""),
        "failures": failures,
        "top_hit": _hit_summary(retrieval_result.hits[0]) if retrieval_result.hits else {},
        "top_hits": [_hit_summary(hit) for hit in retrieval_result.hits[:5]],
    }


def _case_failures(case: dict[str, Any], route_plan: dict[str, Any], hits: list[Any]) -> dict[str, Any]:
    failures: dict[str, Any] = {}
    expected_route = str(case.get("expected_route_id", ""))
    if expected_route and route_plan.get("route_id") != expected_route:
        failures["route_mismatch"] = {"expected": expected_route, "actual": route_plan.get("route_id")}
    hit_section_text = normalize_search_text("\n".join(" ".join([hit.chunk.section_title, *hit.chunk.section_path]) for hit in hits))
    hit_text = normalize_search_text("\n".join(" ".join([hit.chunk.text, hit.chunk.quote, " ".join(hit.chunk.signals)]) for hit in hits))
    section_terms = [str(item) for item in case.get("expected_section_terms_any", [])]
    evidence_terms = [str(item) for item in case.get("expected_terms_any", [])]
    if section_terms and not any(normalize_search_text(term) in hit_section_text for term in section_terms):
        failures["missing_expected_section_terms"] = section_terms
    if evidence_terms and not any(normalize_search_text(term) in hit_text for term in evidence_terms):
        failures["missing_expected_terms"] = evidence_terms
    if not hits:
        failures["no_hits"] = True
    return failures


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


def _backend_report(cases: list[dict[str, Any]], *, fallback_used: bool) -> dict[str, Any]:
    total = len(cases)
    passed = len([case for case in cases if case["status"] == "pass"])
    route_matches = len([case for case in cases if case.get("actual_route_id") == case.get("expected_route_id")])
    return {
        "fallback_used": fallback_used,
        "metrics": {
            "case_count": total,
            "recall_at_8": round(passed / total, 4) if total else 0.0,
            "route_accuracy": round(route_matches / total, 4) if total else 0.0,
        },
        "fail_count": total - passed,
    }


def _comparison(lexical_cases: list[dict[str, Any]], semantic_cases: list[dict[str, Any]]) -> dict[str, Any]:
    improved = []
    regressed = []
    drift = []
    for lexical, semantic in zip(lexical_cases, semantic_cases):
        if lexical["status"] == "fail" and semantic["status"] == "pass":
            improved.append(lexical["case_id"])
        if lexical["status"] == "pass" and semantic["status"] == "fail":
            regressed.append(lexical["case_id"])
        if (lexical.get("top_hit") or {}).get("chunk_id") != (semantic.get("top_hit") or {}).get("chunk_id"):
            drift.append(lexical["case_id"])
    return {
        "improved_cases": improved,
        "regressed_cases": regressed,
        "citation_drift_cases": drift,
        "improved_count": len(improved),
        "regressed_count": len(regressed),
        "citation_drift_count": len(drift),
    }


def _combined_case(lexical: dict[str, Any], semantic: dict[str, Any]) -> dict[str, Any]:
    return {
        "case_id": lexical["case_id"],
        "question": lexical["question"],
        "expected_route_id": lexical["expected_route_id"],
        "actual_route_id": lexical["actual_route_id"],
        "lexical_status": lexical["status"],
        "semantic_status": semantic["status"],
        "lexical_top_hit": lexical.get("top_hit", {}),
        "semantic_top_hit": semantic.get("top_hit", {}),
        "citation_drift": (lexical.get("top_hit") or {}).get("chunk_id") != (semantic.get("top_hit") or {}).get("chunk_id"),
        "lexical_failures": lexical.get("failures", {}),
        "semantic_failures": semantic.get("failures", {}),
    }