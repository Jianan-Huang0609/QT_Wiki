from __future__ import annotations

from collections import Counter
from typing import Any

STATUS_KEYS = ("pass", "warn", "fail", "na")
DEFAULT_LOW_CONFIDENCE_THRESHOLD = 0.6


def evaluate_parser_fusion_metadata(
    parser_fusion: dict[str, Any],
    *,
    low_confidence_threshold: float = DEFAULT_LOW_CONFIDENCE_THRESHOLD,
) -> dict[str, Any]:
    providers = [str(provider) for provider in parser_fusion.get("providers", [])]
    visual_candidates = list(parser_fusion.get("visual_candidates", []))
    fusion_decisions = list(parser_fusion.get("fusion_decisions", []))
    low_confidence_decisions = [
        decision for decision in fusion_decisions if float(decision.get("confidence", 1.0)) < low_confidence_threshold
    ]
    anchored_visual_candidates = [candidate for candidate in visual_candidates if _has_source_anchor(candidate.get("anchors", {}))]
    findings = [
        _finding(
            "F1-01",
            "pass" if providers else "fail",
            "fusion metadata records provider contribution" if providers else "fusion metadata has no providers",
            details={"providers": providers},
        ),
        _finding(
            "F2-01",
            "warn" if low_confidence_decisions else "pass",
            "low-confidence fusion decisions need review" if low_confidence_decisions else "fusion decisions meet confidence threshold",
            details={"low_confidence_decision_ids": [str(decision.get("decision_id", "")) for decision in low_confidence_decisions]},
        ),
    ]
    metrics = {
        "provider_count": len(providers),
        "fusion_decision_count": len(fusion_decisions),
        "low_confidence_decision_count": len(low_confidence_decisions),
        "visual_candidate_count": len(visual_candidates),
        "anchored_visual_candidate_count": len(anchored_visual_candidates),
    }
    return {"eval_summary": _summary(findings), "metrics": metrics, "findings": findings}


def _has_source_anchor(anchors: dict[str, Any]) -> bool:
    return bool(anchors) and (anchors.get("page") is not None or anchors.get("line_start") is not None)


def _finding(eval_id: str, status: str, message: str, *, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "eval_id": eval_id,
        "status": status,
        "message": message,
        "reference": "REF-FUSION-EVAL",
        "details": details,
    }


def _summary(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(finding.get("status", "na")) for finding in findings)
    return {key: int(counts.get(key, 0)) for key in STATUS_KEYS}