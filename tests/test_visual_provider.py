from __future__ import annotations

from Tool.parsers.fusion import VisualCandidate
from Tool.parsers.providers.visual_provider import (
    build_visual_candidate_queue,
    build_visual_provider_fusion_metadata,
    primary_visual_candidates,
)


def test_visual_provider_turns_review_items_into_candidates_with_source_refs():
    review_items = [
        {
            "review_id": "visual-ct-pep-fig-1",
            "source_type": "figure",
            "source_id": "fig-1",
            "page": 18,
            "recommended_tool": "multimodal",
            "reason": "figure caption exists but diagram content has not been visually analyzed",
            "caption": "R2 review flow",
            "anchors": {
                "page": 18,
                "bbox": [80, 180, 500, 430],
                "crop_path": "output/crops/ct-p18-figure-01.png",
            },
        }
    ]
    extractor_requests: list[dict] = []

    def fake_extractor(request: dict):
        extractor_requests.append(request)
        return {
            "text": "The diagram shows PO review and QMP handoff during R2.",
            "confidence": 0.93,
            "backend": "gpt-4o-vision",
            "candidate_type": "figure_description",
        }

    output = build_visual_candidate_queue(review_items, extractor=fake_extractor)

    assert extractor_requests[0]["source_id"] == "fig-1"
    assert extractor_requests[0]["anchors"]["crop_ref"] == "output/crops/ct-p18-figure-01.png"
    assert len(output.visual_candidates) == 1
    candidate = output.visual_candidates[0]
    assert candidate.provider == "vlm"
    assert candidate.candidate_type == "figure_description"
    assert candidate.text.startswith("The diagram shows PO review")
    assert candidate.anchors["page"] == 18
    assert candidate.anchors["bbox"] == [80, 180, 500, 430]
    assert candidate.anchors["crop_ref"] == "output/crops/ct-p18-figure-01.png"
    assert candidate.confidence == 0.93
    assert candidate.review_status == "auto_accepted"
    assert candidate.metadata["backend"] == "gpt-4o-vision"
    assert candidate.metadata["source_review_id"] == "visual-ct-pep-fig-1"
    assert candidate.metadata["source_refs"] == [
        {
            "source_type": "figure",
            "source_id": "fig-1",
            "page": 18,
            "anchors": {
                "page": 18,
                "bbox": [80, 180, 500, 430],
                "crop_ref": "output/crops/ct-p18-figure-01.png",
            },
        }
    ]
    assert output.primary_candidates == [candidate]


def test_visual_provider_requires_confidence_and_source_anchors_for_primary_candidates():
    anchored_low_confidence = VisualCandidate(
        candidate_id="visual-low-confidence",
        provider="vlm",
        candidate_type="figure_description",
        text="Possible workflow diagram.",
        anchors={"page": 3, "bbox": [1, 2, 3, 4]},
        confidence=0.72,
        review_status="pending_review",
    )
    high_confidence_without_anchor = VisualCandidate(
        candidate_id="visual-no-anchor",
        provider="vlm",
        candidate_type="figure_description",
        text="High confidence but no source anchor.",
        anchors={},
        confidence=0.97,
        review_status="auto_accepted",
    )
    reviewed_with_anchor = VisualCandidate(
        candidate_id="visual-reviewed",
        provider="docling_ocr",
        candidate_type="ocr_text",
        text="Reviewed OCR text.",
        anchors={"page": 4, "crop_ref": "output/crops/p4.png"},
        confidence=0.65,
        review_status="reviewed",
    )

    assert primary_visual_candidates(
        [anchored_low_confidence, high_confidence_without_anchor, reviewed_with_anchor]
    ) == [reviewed_with_anchor]


def test_visual_provider_merges_docling_image_candidates_and_builds_fusion_metadata():
    docling_pending = VisualCandidate(
        candidate_id="docling-visual-pending",
        provider="docling_ocr",
        candidate_type="picture",
        text="R2 flow diagram candidate.",
        anchors={"page": 5, "bbox": [10, 20, 200, 220]},
        confidence=0.76,
        review_status="pending_review",
    )
    docling_reviewed = VisualCandidate(
        candidate_id="docling-visual-reviewed",
        provider="docling_ocr",
        candidate_type="picture",
        text="Reviewed diagram text.",
        anchors={"page": 6, "bbox": [10, 20, 200, 220]},
        confidence=0.8,
        review_status="reviewed",
    )

    output = build_visual_candidate_queue(
        [],
        docling_candidates=[docling_pending, docling_reviewed],
    )
    metadata = build_visual_provider_fusion_metadata(
        output,
        canonical_output={"sections": 0, "fragments": 0, "tables": 0, "figures": 2},
    )

    assert output.visual_candidates == [docling_pending, docling_reviewed]
    assert output.primary_candidates == [docling_reviewed]
    assert metadata["schema_version"] == "parser-fusion-v0.1"
    assert metadata["fusion_mode"] == "visual_provider_extraction"
    assert metadata["providers"] == ["docling_ocr"]
    assert metadata["provider_roles"]["docling_ocr"] == "visual_ocr"
    assert metadata["counts"]["visual_candidates"] == 2
    assert metadata["canonical_output"]["figures"] == 2