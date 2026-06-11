from __future__ import annotations

import re
from dataclasses import dataclass
from math import sqrt
from typing import Any, Callable, Protocol

from Tool.chunking.section_chunks import SectionChunk, normalize_search_text
from Tool.retrieval.section_index import RetrievalHit, RetrievalResult, retrieve_sections

DEFAULT_TOP_K = 8
DEFAULT_RRF_K = 60
EmbedText = Callable[[str], list[float]]


class Retriever(Protocol):
    name: str

    def retrieve(
        self,
        question: str,
        chunks: list[SectionChunk],
        *,
        source_scope: dict[str, Any] | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> RetrievalResult: ...


@dataclass(slots=True)
class RuleSectionRetriever:
    name: str = "rule_section"

    def retrieve(
        self,
        question: str,
        chunks: list[SectionChunk],
        *,
        source_scope: dict[str, Any] | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> RetrievalResult:
        result = retrieve_sections(question, chunks, source_scope=source_scope, top_k=top_k)
        result.trace.append("rule_section_retriever wrapper")
        return result


@dataclass(slots=True)
class FullTextRetriever:
    name: str = "full_text"

    def retrieve(
        self,
        question: str,
        chunks: list[SectionChunk],
        *,
        source_scope: dict[str, Any] | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> RetrievalResult:
        scope = source_scope or {"mode": "all_sources"}
        scoped_chunks = _filter_scope(chunks, scope)
        query_terms = _query_terms(question)
        hits: list[RetrievalHit] = []
        for chunk in scoped_chunks:
            score, matched_terms = _full_text_score(chunk, query_terms)
            if score > 0:
                hits.append(RetrievalHit(chunk=chunk, score=round(score, 4), matched_terms=matched_terms))
        hits.sort(key=lambda item: (-item.score, item.chunk.chunk_id))
        hits = hits[: max(1, top_k)]
        return RetrievalResult(
            question=question,
            strategy_used="full_text_retrieval",
            source_scope=scope,
            hits=hits,
            evidence_coverage=_coverage(hits),
            trace=[
                "full_text_retriever query normalized",
                f"source scope filtered {len(scoped_chunks)} chunks",
                "full-text token overlap scoring",
            ],
        )


@dataclass(slots=True)
class VectorRetriever:
    embed_text: EmbedText | None = None
    name: str = "vector"

    def retrieve(
        self,
        question: str,
        chunks: list[SectionChunk],
        *,
        source_scope: dict[str, Any] | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> RetrievalResult:
        scope = source_scope or {"mode": "all_sources"}
        scoped_chunks = _filter_scope(chunks, scope)
        query_vector = self._embed(question)
        query_terms = _query_terms(question)
        hits: list[RetrievalHit] = []
        for chunk in scoped_chunks:
            chunk_vector = self._embed(_chunk_embedding_text(chunk))
            score = _cosine_similarity(query_vector, chunk_vector)
            if score > 0:
                hits.append(
                    RetrievalHit(
                        chunk=chunk,
                        score=round(score, 4),
                        matched_terms=_matched_terms(chunk, query_terms),
                    )
                )
        hits.sort(key=lambda item: (-item.score, item.chunk.chunk_id))
        hits = hits[: max(1, top_k)]
        return RetrievalResult(
            question=question,
            strategy_used="vector_retrieval",
            source_scope=scope,
            hits=hits,
            evidence_coverage=_coverage(hits),
            trace=[
                "vector_retriever query embedded",
                f"source scope filtered {len(scoped_chunks)} chunks",
                "vector similarity scoring",
            ],
        )

    def _embed(self, text: str) -> list[float]:
        if self.embed_text:
            return [float(value) for value in self.embed_text(text)]
        return _sparse_term_embedding(text)


@dataclass(slots=True)
class HybridRetriever:
    retrievers: list[Retriever]
    rrf_k: int = DEFAULT_RRF_K
    name: str = "hybrid"

    def retrieve(
        self,
        question: str,
        chunks: list[SectionChunk],
        *,
        source_scope: dict[str, Any] | None = None,
        top_k: int = DEFAULT_TOP_K,
    ) -> RetrievalResult:
        if not self.retrievers:
            return RetrievalResult(
                question=question,
                strategy_used="hybrid_retrieval",
                source_scope=source_scope or {"mode": "all_sources"},
                hits=[],
                evidence_coverage=_coverage([]),
                trace=["hybrid retriever fanout: none", "rrf fusion skipped because no retrievers configured"],
            )

        backend_results = [
            retriever.retrieve(question, chunks, source_scope=source_scope, top_k=top_k)
            for retriever in self.retrievers
        ]
        fused_hits = _rrf_fuse(backend_results, rrf_k=self.rrf_k, top_k=top_k)
        backend_names = ", ".join(retriever.name for retriever in self.retrievers)
        scope = source_scope or {"mode": "all_sources"}
        return RetrievalResult(
            question=question,
            strategy_used="hybrid_retrieval",
            source_scope=scope,
            hits=fused_hits,
            evidence_coverage=_coverage(fused_hits),
            trace=[
                f"hybrid retriever fanout: {backend_names}",
                *[f"{result.strategy_used}: {len(result.hits)} hits" for result in backend_results],
                f"rrf fusion combined {sum(len(result.hits) for result in backend_results)} backend hits",
            ],
        )


def _rrf_fuse(results: list[RetrievalResult], *, rrf_k: int, top_k: int) -> list[RetrievalHit]:
    score_by_chunk_id: dict[str, float] = {}
    chunk_by_id: dict[str, SectionChunk] = {}
    matched_terms_by_chunk_id: dict[str, set[str]] = {}

    for result in results:
        for rank, hit in enumerate(result.hits, start=1):
            chunk_id = hit.chunk.chunk_id
            score_by_chunk_id[chunk_id] = score_by_chunk_id.get(chunk_id, 0.0) + 1.0 / (rrf_k + rank)
            chunk_by_id[chunk_id] = hit.chunk
            matched_terms_by_chunk_id.setdefault(chunk_id, set()).update(hit.matched_terms)

    fused = [
        RetrievalHit(
            chunk=chunk_by_id[chunk_id],
            score=round(score * 100.0, 4),
            matched_terms=sorted(matched_terms_by_chunk_id.get(chunk_id, set())),
        )
        for chunk_id, score in score_by_chunk_id.items()
    ]
    fused.sort(key=lambda item: (-item.score, item.chunk.chunk_id))
    return fused[: max(1, top_k)]


def _full_text_score(chunk: SectionChunk, terms: list[str]) -> tuple[float, list[str]]:
    text = normalize_search_text(" ".join([chunk.section_title, *chunk.section_path, chunk.text, " ".join(chunk.signals)]))
    score = 0.0
    matched_terms: list[str] = []
    for term in terms:
        normalized_term = term.casefold()
        count = _count_term(text, normalized_term)
        if not count:
            continue
        score += (2.0 if _is_phrase_or_section(normalized_term) else 1.0) + min(count, 4) * 0.25
        matched_terms.append(term)
    if chunk.chunk_type == "document_history":
        score *= 0.35
    return score, matched_terms


def _matched_terms(chunk: SectionChunk, terms: list[str]) -> list[str]:
    text = normalize_search_text(_chunk_embedding_text(chunk))
    return [term for term in terms if _count_term(text, term.casefold())]


def _chunk_embedding_text(chunk: SectionChunk) -> str:
    return " ".join([chunk.section_title, *chunk.section_path, chunk.text, " ".join(chunk.signals)])


def _cosine_similarity(left: list[float], right: list[float]) -> float:
    if not left or not right or len(left) != len(right):
        return 0.0
    dot_product = sum(left_value * right_value for left_value, right_value in zip(left, right))
    left_norm = sqrt(sum(value * value for value in left))
    right_norm = sqrt(sum(value * value for value in right))
    if left_norm == 0.0 or right_norm == 0.0:
        return 0.0
    return dot_product / (left_norm * right_norm)


def _sparse_term_embedding(text: str) -> list[float]:
    normalized = normalize_search_text(text)
    vocabulary = (
        "r2",
        "r3",
        "product owner",
        "project manager",
        "qmp",
        "regulatory",
        "approval",
        "evidence",
        "deliverable",
        "responsibility",
    )
    return [float(_count_term(normalized, term)) for term in vocabulary]


def _filter_scope(chunks: list[SectionChunk], scope: dict[str, Any]) -> list[SectionChunk]:
    mode = scope.get("mode", "all_sources")
    if mode == "selected_docs":
        document_ids = set(scope.get("document_ids", []))
        return [chunk for chunk in chunks if chunk.document_id in document_ids]
    if mode == "selected_sections":
        section_ids = set(scope.get("section_ids", []))
        return [chunk for chunk in chunks if chunk.section_id in section_ids]
    return list(chunks)


def _query_terms(question: str) -> list[str]:
    words = re.findall(r"[A-Za-z][A-Za-z0-9_\-]*|\d+(?:\.\d+)*|[\u4e00-\u9fff]{2,}", question)
    terms: list[str] = []
    broad_terms = {
        "the",
        "and",
        "what",
        "how",
        "for",
        "process",
        "phase",
        "stage",
        "document",
        "应该",
        "准备",
        "什么",
    }
    for word in words:
        cleaned = word.strip().casefold()
        if cleaned and cleaned not in broad_terms and cleaned not in terms:
            terms.append(cleaned)
    return terms


def _count_term(text: str, term: str) -> int:
    if len(term) <= 2 and re.fullmatch(r"[a-z0-9]+", term):
        return len(re.findall(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text))
    return text.count(term)


def _is_phrase_or_section(term: str) -> bool:
    return " " in term or bool(re.fullmatch(r"\d+(?:\.\d+)+", term))


def _coverage(hits: list[RetrievalHit]) -> dict[str, Any]:
    documents = sorted({hit.chunk.document_id for hit in hits})
    sections = sorted({hit.chunk.section_id for hit in hits if hit.chunk.section_id})
    return {"documents": documents, "sections": sections, "hit_count": len(hits)}