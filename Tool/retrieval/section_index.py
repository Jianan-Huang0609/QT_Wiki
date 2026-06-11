from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from Tool.chunking.section_chunks import SectionChunk, normalize_search_text


@dataclass(slots=True)
class RetrievalHit:
    chunk: SectionChunk
    score: float
    matched_terms: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["chunk"] = self.chunk.to_dict()
        return payload


@dataclass(slots=True)
class RetrievalResult:
    question: str
    strategy_used: str
    source_scope: dict[str, Any]
    hits: list[RetrievalHit]
    evidence_coverage: dict[str, Any]
    trace: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "strategy_used": self.strategy_used,
            "source_scope": self.source_scope,
            "hits": [hit.to_dict() for hit in self.hits],
            "evidence_coverage": self.evidence_coverage,
            "trace": self.trace,
        }


def retrieve_sections(
    question: str,
    chunks: list[SectionChunk],
    *,
    source_scope: dict[str, Any] | None = None,
    top_k: int = 8,
) -> RetrievalResult:
    scope = source_scope or {"mode": "all_sources"}
    scoped_chunks = _filter_scope(chunks, scope)
    terms = _query_terms(question)
    hits: list[RetrievalHit] = []
    for chunk in scoped_chunks:
        score, matched_terms = _score_chunk(chunk, terms)
        if score > 0:
            hits.append(RetrievalHit(chunk=chunk, score=round(score, 4), matched_terms=matched_terms))
    hits.sort(key=lambda item: item.score, reverse=True)
    hits = hits[: max(1, top_k)]
    return RetrievalResult(
        question=question,
        strategy_used=_strategy(scope),
        source_scope=scope,
        hits=hits,
        evidence_coverage=_coverage(hits),
        trace=[
            "query normalized",
            f"source scope filtered {len(scoped_chunks)} chunks",
            "keyword and signal scoring",
            "document history downrank applied",
        ],
    )


def _filter_scope(chunks: list[SectionChunk], scope: dict[str, Any]) -> list[SectionChunk]:
    mode = scope.get("mode", "all_sources")
    if mode == "selected_docs":
        document_ids = set(scope.get("document_ids", []))
        return [chunk for chunk in chunks if chunk.document_id in document_ids]
    if mode == "selected_sections":
        section_ids = set(scope.get("section_ids", []))
        return [chunk for chunk in chunks if chunk.section_id in section_ids]
    return list(chunks)


def _strategy(scope: dict[str, Any]) -> str:
    mode = scope.get("mode", "all_sources")
    if mode == "selected_docs":
        return "scoped_section_retrieval"
    if mode == "selected_sections":
        return "direct_section_read"
    return "global_section_retrieval"


def _score_chunk(chunk: SectionChunk, terms: list[str]) -> tuple[float, list[str]]:
    title = normalize_search_text(chunk.section_title)
    text = normalize_search_text(chunk.text)
    signals = " ".join(chunk.signals).casefold()
    score = 0.0
    matched: list[str] = []
    for term in terms:
        if not term:
            continue
        term_norm = term.casefold()
        term_score = 0.0
        if _is_stage_term(term_norm):
            if _contains_term(title, term_norm):
                term_score += 8.0
            elif _contains_term(text, term_norm):
                term_score += 0.75 + min(_count_term(text, term_norm), 2) * 0.15
        else:
            if _contains_term(title, term_norm):
                term_score += 3.0
            if _contains_term(text, term_norm):
                phrase_bonus = 2.5 if " " in term_norm else 1.0
                term_score += phrase_bonus + min(_count_term(text, term_norm), 3) * 0.25
        if term_norm in signals:
            term_score += 1.5
        if term_score:
            score += term_score
            matched.append(term)
    if _is_history_chunk(chunk):
        score *= 0.35
    if chunk.chunk_type == "section":
        score += 0.25
    return score, matched


def _is_history_chunk(chunk: SectionChunk) -> bool:
    return chunk.chunk_type == "document_history" or "document_history" in chunk.signals


def _query_terms(question: str) -> list[str]:
    normalized_question = question.casefold()
    phrase_terms = [phrase for phrase in ("product owner", "project manager", "regulatory affair") if phrase in normalized_question]
    words = re.findall(r"[A-Za-z][A-Za-z0-9_\-]*|\d+(?:\.\d+)*|[\u4e00-\u9fff]{2,}", question)
    terms = []
    terms.extend(phrase_terms)
    broad_terms = {"the", "and", "what", "how", "for", "product", "process", "phase", "stage", "document", "evidence", "应该", "准备", "什么"}
    for word in words:
        cleaned = word.strip().casefold()
        if cleaned and cleaned not in broad_terms and cleaned not in terms:
            terms.append(cleaned)
    return terms


def _is_stage_term(term: str) -> bool:
    return bool(re.fullmatch(r"r\d+(?:\.\d+)?", term))


def _contains_term(text: str, term: str) -> bool:
    return _count_term(text, term) > 0


def _count_term(text: str, term: str) -> int:
    if len(term) <= 2 and re.fullmatch(r"[a-z0-9]+", term):
        return len(re.findall(rf"(?<![a-z0-9]){re.escape(term)}(?![a-z0-9])", text))
    return text.count(term)


def _coverage(hits: list[RetrievalHit]) -> dict[str, Any]:
    documents = sorted({hit.chunk.document_id for hit in hits})
    sections = sorted({hit.chunk.section_id for hit in hits if hit.chunk.section_id})
    return {"documents": documents, "sections": sections, "hit_count": len(hits)}