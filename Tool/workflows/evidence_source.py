from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any

from Tool.workflows.answer import AnswerEvidencePackage, EvidenceItem


@dataclass(slots=True)
class EvidenceSource:
    evidence_id: str
    citation_id: str
    document_id: str
    file_name: str
    chunk_id: str
    section_id: str | None
    section_title: str
    heading_path: list[str]
    anchor_label: str
    quote: str
    source_context: dict[str, Any] = field(default_factory=dict)
    quality_warning: list[str] = field(default_factory=list)
    usable_as_primary_evidence: bool = True

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_evidence_sources(evidence_package: AnswerEvidencePackage, citations: list[dict[str, Any]]) -> list[EvidenceSource]:
    citation_by_evidence_id = {
        str(citation.get("evidence_id") or ""): citation
        for citation in citations
        if citation.get("evidence_id")
    }
    sources: list[EvidenceSource] = []
    for evidence in evidence_package.evidence_items:
        citation = citation_by_evidence_id.get(evidence.evidence_id)
        if citation is None:
            continue
        sources.append(evidence_source_from(evidence, citation))
    return sources


def evidence_source_from(evidence: EvidenceItem, citation: dict[str, Any]) -> EvidenceSource:
    source_context = citation.get("source_context") if isinstance(citation.get("source_context"), dict) else {}
    warnings = _quality_warnings(evidence, citation, source_context)
    return EvidenceSource(
        evidence_id=evidence.evidence_id,
        citation_id=str(citation.get("citation_id") or ""),
        document_id=str(citation.get("document_id") or evidence.document_id),
        file_name=str(citation.get("file_name") or evidence.file_name),
        chunk_id=str(source_context.get("chunk_id") or ""),
        section_id=str(citation.get("section_id") or evidence.section_id or source_context.get("section_id") or "") or None,
        section_title=str(evidence.section_title or source_context.get("section_title") or ""),
        heading_path=list(evidence.section_path),
        anchor_label=str(citation.get("anchor_label") or evidence.anchor_label or source_context.get("anchor_label") or ""),
        quote=str(citation.get("quote") or evidence.quote or source_context.get("context_text") or ""),
        source_context=dict(source_context),
        quality_warning=warnings,
        usable_as_primary_evidence=not warnings,
    )


def _quality_warnings(evidence: EvidenceItem, citation: dict[str, Any], source_context: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    if not str(citation.get("quote") or evidence.quote or "").strip():
        warnings.append("missing_quote")
    if not str(citation.get("anchor_label") or evidence.anchor_label or "").strip():
        warnings.append("missing_anchor")
    if not source_context.get("context_text"):
        warnings.append("missing_source_context")
    if "document_history" in evidence.signals:
        warnings.append("document_history_not_primary_evidence")
    if "visual_review_required" in evidence.signals:
        warnings.append("visual_review_required")
    return warnings