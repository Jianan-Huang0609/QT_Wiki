from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any, Iterable

from Tool.contracts.canonical import CanonicalDocument

PARSER_FUSION_SCHEMA_VERSION = "parser-fusion-v0.1"
SAMPLE_LIMIT = 20

PROVIDER_ROLE_HINTS = {
    "pypdf_fast_text": "fast_text",
    "docx_xml": "structure_preserving",
    "markdown_text": "structure_preserving",
    "pptx_text": "structure_preserving",
    "xlsx_openpyxl": "structure_preserving",
    "docling": "layout_table_ocr",
    "docling_ocr": "visual_ocr",
    "mineru": "visual_ocr",
    "vlm": "visual_candidate",
    "unsupported": "unsupported",
}

DEFAULT_PROVIDER_BY_PARSER = {
    "pdf_parser": "pypdf_fast_text",
    "docx_parser": "docx_xml",
    "markdown_parser": "markdown_text",
    "pptx_parser": "pptx_text",
    "xlsx_parser": "xlsx_openpyxl",
    "unsupported_parser": "unsupported",
}


@dataclass(slots=True, frozen=True)
class ExtractionBlock:
    block_id: str
    provider: str
    block_type: str
    text: str = ""
    anchors: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _with_normalized_confidence(asdict(self))


@dataclass(slots=True, frozen=True)
class LayoutBlock:
    block_id: str
    provider: str
    text: str
    layout_type: str = "text"
    anchors: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    block_type: str = "layout_text"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _with_normalized_confidence(asdict(self))


@dataclass(slots=True, frozen=True)
class TableBlock:
    block_id: str
    provider: str
    rows: list[list[str]] = field(default_factory=list)
    anchors: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    block_type: str = "table"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _with_normalized_confidence(asdict(self))


@dataclass(slots=True, frozen=True)
class VisualCandidate:
    candidate_id: str
    provider: str
    candidate_type: str
    text: str = ""
    anchors: dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0
    review_status: str = "pending_review"
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _with_normalized_confidence(asdict(self))


@dataclass(slots=True, frozen=True)
class FusionDecision:
    decision_id: str
    decision_type: str
    selected_block_ids: list[str] = field(default_factory=list)
    reason: str = ""
    confidence: float = 1.0
    output_target: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return _with_normalized_confidence(asdict(self))


def build_parser_fusion_metadata(
    *,
    providers: Iterable[str],
    extraction_blocks: Iterable[ExtractionBlock] = (),
    layout_blocks: Iterable[LayoutBlock] = (),
    table_blocks: Iterable[TableBlock] = (),
    visual_candidates: Iterable[VisualCandidate] = (),
    fusion_decisions: Iterable[FusionDecision] = (),
    canonical_output: dict[str, int] | None = None,
    fusion_mode: str = "provider_fusion",
) -> dict[str, Any]:
    provider_list = _dedupe(providers)
    extraction_list = list(extraction_blocks)
    layout_list = list(layout_blocks)
    table_list = list(table_blocks)
    visual_list = list(visual_candidates)
    decision_list = list(fusion_decisions)

    return {
        "schema_version": PARSER_FUSION_SCHEMA_VERSION,
        "fusion_mode": fusion_mode,
        "providers": provider_list,
        "provider_roles": {provider: _provider_role(provider) for provider in provider_list},
        "counts": {
            "extraction_blocks": len(extraction_list),
            "layout_blocks": len(layout_list),
            "table_blocks": len(table_list),
            "visual_candidates": len(visual_list),
            "fusion_decisions": len(decision_list),
        },
        "canonical_output": dict(canonical_output or {}),
        "samples": {
            "extraction_blocks": _sample_dicts(extraction_list),
            "layout_blocks": _sample_dicts(layout_list),
            "table_blocks": _sample_dicts(table_list),
        },
        "visual_candidates": _sample_dicts(visual_list),
        "fusion_decisions": _sample_dicts(decision_list),
    }


def default_parser_fusion_metadata(canonical: CanonicalDocument, *, parser_name: str) -> dict[str, Any]:
    provider = DEFAULT_PROVIDER_BY_PARSER.get(parser_name, parser_name.replace("_parser", "") or "unknown")
    return build_parser_fusion_metadata(
        providers=[provider],
        canonical_output={
            "sections": len(canonical.sections),
            "fragments": len(canonical.fragments),
            "tables": len(canonical.tables),
            "figures": len(canonical.figures),
            "source_anchors": len(canonical.source_anchors),
        },
        fusion_mode="single_provider_passthrough",
    )


def _sample_dicts(items: Iterable[Any]) -> list[dict[str, Any]]:
    return [item.to_dict() for item in list(items)[:SAMPLE_LIMIT]]


def _dedupe(items: Iterable[str]) -> list[str]:
    deduped: list[str] = []
    for item in items:
        provider = str(item).strip()
        if provider and provider not in deduped:
            deduped.append(provider)
    return deduped


def _provider_role(provider: str) -> str:
    if provider in PROVIDER_ROLE_HINTS:
        return PROVIDER_ROLE_HINTS[provider]
    if provider.endswith("_ocr") or "ocr" in provider:
        return "visual_ocr"
    if "layout" in provider or "docling" in provider:
        return "layout_table_ocr"
    if "text" in provider:
        return "fast_text"
    return "extraction_provider"


def _with_normalized_confidence(data: dict[str, Any]) -> dict[str, Any]:
    if "confidence" in data:
        data["confidence"] = round(float(data["confidence"]), 4)
    return data