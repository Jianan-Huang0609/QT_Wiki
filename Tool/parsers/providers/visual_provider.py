from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Iterable

from Tool.parsers.fusion import VisualCandidate, build_parser_fusion_metadata

PRIMARY_CONFIDENCE_THRESHOLD = 0.9
PRIMARY_REVIEW_STATUSES = {"accepted", "auto_accepted", "reviewed"}

VisualExtractor = Callable[[dict[str, Any]], dict[str, Any] | VisualCandidate | None]


@dataclass(slots=True)
class VisualProviderOutput:
    provider: str = "visual_provider"
    visual_candidates: list[VisualCandidate] = field(default_factory=list)
    primary_candidates: list[VisualCandidate] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def build_visual_candidate_queue(
    review_items: Iterable[dict[str, Any]],
    *,
    extractor: VisualExtractor | None = None,
    docling_candidates: Iterable[VisualCandidate] = (),
    min_primary_confidence: float = PRIMARY_CONFIDENCE_THRESHOLD,
) -> VisualProviderOutput:
    candidates = list(docling_candidates)
    errors: list[str] = []

    for index, item in enumerate(review_items, start=1):
        request = _review_item_request(item, index=index)
        try:
            extracted = extractor(request) if extractor else None
        except Exception as exc:  # pragma: no cover - defensive boundary for injected providers
            errors.append(f"{request['review_id']}: {exc}")
            extracted = {"confidence": 0.0, "metadata": {"error": str(exc)}}
        candidates.append(
            _candidate_from_extraction(
                request,
                extracted,
                min_primary_confidence=min_primary_confidence,
            )
        )

    return VisualProviderOutput(
        visual_candidates=candidates,
        primary_candidates=primary_visual_candidates(candidates, min_confidence=min_primary_confidence),
        errors=errors,
    )


def primary_visual_candidates(
    candidates: Iterable[VisualCandidate],
    *,
    min_confidence: float = PRIMARY_CONFIDENCE_THRESHOLD,
) -> list[VisualCandidate]:
    primary: list[VisualCandidate] = []
    for candidate in candidates:
        if not _has_primary_source_anchor(candidate.anchors):
            continue
        if candidate.review_status in PRIMARY_REVIEW_STATUSES or candidate.confidence >= min_confidence:
            primary.append(candidate)
    return primary


def build_visual_provider_fusion_metadata(
    output: VisualProviderOutput,
    *,
    canonical_output: dict[str, int] | None = None,
) -> dict[str, Any]:
    providers = [candidate.provider for candidate in output.visual_candidates] or [output.provider]
    return build_parser_fusion_metadata(
        providers=providers,
        visual_candidates=output.visual_candidates,
        canonical_output=canonical_output,
        fusion_mode="visual_provider_extraction",
    )


def _review_item_request(item: dict[str, Any], *, index: int) -> dict[str, Any]:
    anchors = _normalized_anchors(item)
    review_id = str(item.get("review_id") or f"visual-review-{index}")
    return {
        "review_id": review_id,
        "source_type": str(item.get("source_type") or "visual"),
        "source_id": str(item.get("source_id") or review_id),
        "page": anchors.get("page", item.get("page")),
        "recommended_tool": str(item.get("recommended_tool") or "multimodal"),
        "reason": str(item.get("reason") or ""),
        "caption": str(item.get("caption") or ""),
        "anchors": anchors,
    }


def _candidate_from_extraction(
    request: dict[str, Any],
    extracted: dict[str, Any] | VisualCandidate | None,
    *,
    min_primary_confidence: float,
) -> VisualCandidate:
    if isinstance(extracted, VisualCandidate):
        return extracted

    result = dict(extracted or {})
    anchors = {**request["anchors"], **_normalized_anchors(result)}
    provider = str(result.get("provider") or _provider_for_tool(request["recommended_tool"]))
    confidence = float(result.get("confidence", 0.0))
    review_status = str(result.get("review_status") or _review_status(anchors, confidence, min_primary_confidence))
    metadata = _candidate_metadata(request, result)
    return VisualCandidate(
        candidate_id=str(result.get("candidate_id") or f"visual-{request['review_id']}"),
        provider=provider,
        candidate_type=str(result.get("candidate_type") or _candidate_type(provider)),
        text=str(result.get("text") or ""),
        anchors=anchors,
        confidence=confidence,
        review_status=review_status,
        metadata=metadata,
    )


def _candidate_metadata(request: dict[str, Any], result: dict[str, Any]) -> dict[str, Any]:
    metadata = {
        "source_review_id": request["review_id"],
        "source_type": request["source_type"],
        "source_id": request["source_id"],
        "recommended_tool": request["recommended_tool"],
        "reason": request["reason"],
        "source_refs": [_source_ref(request)],
    }
    if result.get("backend"):
        metadata["backend"] = str(result["backend"])
    if isinstance(result.get("metadata"), dict):
        metadata.update(result["metadata"])
    return metadata


def _source_ref(request: dict[str, Any]) -> dict[str, Any]:
    return {
        "source_type": request["source_type"],
        "source_id": request["source_id"],
        "page": request["page"],
        "anchors": dict(request["anchors"]),
    }


def _normalized_anchors(item: dict[str, Any]) -> dict[str, Any]:
    anchors = dict(item.get("anchors") or {})
    if item.get("page") is not None and "page" not in anchors:
        anchors["page"] = item["page"]
    crop_ref = item.get("crop_ref") or item.get("crop_path") or anchors.get("crop_ref") or anchors.get("crop_path")
    if crop_ref:
        anchors["crop_ref"] = str(crop_ref)
        anchors.pop("crop_path", None)
    return anchors


def _provider_for_tool(recommended_tool: str) -> str:
    tool = recommended_tool.casefold()
    if "multimodal" in tool or "vlm" in tool:
        return "vlm"
    if "ocr" in tool:
        return "ocr"
    return "vlm"


def _candidate_type(provider: str) -> str:
    return "ocr_text" if provider.endswith("ocr") or provider == "ocr" else "figure_description"


def _review_status(anchors: dict[str, Any], confidence: float, min_primary_confidence: float) -> str:
    if _has_primary_source_anchor(anchors) and confidence >= min_primary_confidence:
        return "auto_accepted"
    return "pending_review"


def _has_primary_source_anchor(anchors: dict[str, Any]) -> bool:
    if not anchors:
        return False
    has_page = anchors.get("page") is not None
    has_visual_locator = bool(anchors.get("bbox") or anchors.get("crop_ref"))
    return has_page and has_visual_locator