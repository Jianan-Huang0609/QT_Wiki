from __future__ import annotations

from collections import Counter
from typing import Any

from Tool.contracts.canonical import CanonicalDocument, FigureData, Fragment, TableData
from Tool.evals.parser_quality import evaluate_parser_quality
from Tool.parsers.fusion import default_parser_fusion_metadata
from Tool.visual_review import build_visual_review_items

PARSER_VERSION = "multi-input-v0.1"
EVAL_STATUS_KEYS = ("pass", "warn", "fail", "na")


def apply_parse_workflow_contract(
    canonical: CanonicalDocument,
    *,
    parser_name: str,
    parser_version: str = PARSER_VERSION,
    trace: list[str] | None = None,
) -> CanonicalDocument:
    parser_fusion = canonical.document.metadata.get("parser_fusion")
    if not isinstance(parser_fusion, dict):
        parser_fusion = default_parser_fusion_metadata(canonical, parser_name=parser_name)
    summary = build_parse_workflow_summary(
        canonical,
        parser_name=parser_name,
        parser_version=parser_version,
        trace=trace,
        parser_fusion=parser_fusion,
    )
    canonical.parse_status = summary["parse_status"]
    canonical.document.metadata.update(
        {
            "parser_name": parser_name,
            "parser_version": parser_version,
            "parser_fusion": parser_fusion,
            "structure_quality": summary["structure_quality"],
            "eval_summary": summary["eval_summary"],
            "review_items": summary["review_items"],
            "parse_workflow": summary,
        }
    )
    return canonical


def build_parse_workflow_summary(
    canonical: CanonicalDocument,
    *,
    parser_name: str,
    parser_version: str = PARSER_VERSION,
    trace: list[str] | None = None,
    parser_fusion: dict[str, Any] | None = None,
) -> dict[str, Any]:
    counts = _counts(canonical)
    structure_quality = _structure_quality(canonical)
    quality_report = evaluate_parser_quality(canonical)
    visual_review_items = build_visual_review_items(canonical)
    structure_quality.update(quality_report["metrics"])
    findings = [
        *_gate1_findings(canonical, parser_name=parser_name, structure_quality=structure_quality),
        *quality_report["findings"],
    ]
    eval_summary = _eval_summary(findings)
    parse_status = _parse_status(canonical, eval_summary=eval_summary, counts=counts, parser_name=parser_name)
    review_items = [_review_item(finding) for finding in findings if finding["status"] in {"warn", "fail"}]

    return {
        "run_id": f"parse-{canonical.document.document_id}",
        "document_id": canonical.document.document_id,
        "parse_status": parse_status,
        "parser_name": parser_name,
        "parser_version": parser_version,
        "counts": counts,
        "structure_quality": structure_quality,
        "eval_summary": eval_summary,
        "review_items": review_items,
        "visual_review_items": visual_review_items,
        "parser_fusion": parser_fusion or default_parser_fusion_metadata(canonical, parser_name=parser_name),
        "trace": _trace(parser_name, trace),
    }


def _counts(canonical: CanonicalDocument) -> dict[str, int]:
    return {
        "sections": len(canonical.sections),
        "fragments": len(canonical.fragments),
        "tables": len(canonical.tables),
        "figures": len(canonical.figures),
        "source_anchors": len(canonical.source_anchors),
        "errors": len(canonical.errors),
    }


def _structure_quality(canonical: CanonicalDocument) -> dict[str, float | int]:
    evidence_items = [*canonical.fragments, *canonical.tables, *canonical.figures]
    anchor_coverage = _anchor_coverage(evidence_items)
    section_confidence = _section_confidence(canonical.fragments)
    return {
        "anchor_coverage": anchor_coverage,
        "section_confidence": section_confidence,
        "noise_rate": 0.0,
        "low_confidence_count": 0,
    }


def _anchor_coverage(items: list[Fragment | TableData | FigureData]) -> float:
    if not items:
        return 0.0
    anchored = len([item for item in items if item.anchors])
    return round(anchored / len(items), 4)


def _section_confidence(fragments: list[Fragment]) -> float:
    if not fragments:
        return 0.0
    assigned = len([fragment for fragment in fragments if fragment.section_id])
    if assigned == len(fragments):
        return 1.0
    if assigned == 0:
        return 0.0
    return round(assigned / len(fragments), 4)


def _gate1_findings(
    canonical: CanonicalDocument,
    *,
    parser_name: str,
    structure_quality: dict[str, float | int],
) -> list[dict[str, Any]]:
    has_content = bool(canonical.fragments or canonical.tables or canonical.figures)
    unsupported = parser_name == "unsupported_parser" or any("Unsupported file type" in error for error in canonical.errors)
    findings = [
        {
            "eval_id": "P0-01",
            "status": "fail" if unsupported else "pass",
            "message": "supported parser selected" if not unsupported else "unsupported file type",
            "reference": "REF-PARSER",
        },
        {
            "eval_id": "P0-02",
            "status": "pass" if has_content else "fail",
            "message": "content extracted" if has_content else "no text, table, or figure content extracted",
            "reference": "REF-PARSER",
        },
    ]

    if not has_content:
        anchor_status = "fail"
        anchor_message = "no source-backed content available"
    elif structure_quality["anchor_coverage"] == 1.0:
        anchor_status = "pass"
        anchor_message = "all extracted content has source anchors"
    else:
        anchor_status = "warn"
        anchor_message = "some extracted content is missing source anchors"

    findings.append(
        {
            "eval_id": "P3-01",
            "status": anchor_status,
            "message": anchor_message,
            "reference": "REF-EVALS",
            "anchor_coverage": structure_quality["anchor_coverage"],
        }
    )
    return findings


def _eval_summary(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(finding.get("status", "na")) for finding in findings)
    return {key: int(counts.get(key, 0)) for key in EVAL_STATUS_KEYS}


def _parse_status(
    canonical: CanonicalDocument,
    *,
    eval_summary: dict[str, int],
    counts: dict[str, int],
    parser_name: str,
) -> str:
    has_content = bool(counts["fragments"] or counts["tables"] or counts["figures"])
    source_type = canonical.document.source_type.lower()
    if parser_name == "unsupported_parser":
        return "failed"
    if not has_content and source_type == "pdf":
        return "ocr_required"
    if not has_content or eval_summary["fail"]:
        return "failed"
    if canonical.errors:
        return "partially_parsed"
    if eval_summary["warn"]:
        return "needs_review"
    return "parsed"


def _review_item(finding: dict[str, Any]) -> dict[str, Any]:
    status = str(finding.get("status", "warn"))
    return {
        "review_id": f"review-{finding.get('eval_id', 'unknown')}",
        "eval_id": finding.get("eval_id", "unknown"),
        "severity": "high" if status == "fail" else "medium",
        "status": status,
        "message": finding.get("message", ""),
        "reference": finding.get("reference", "REF-EVALS"),
        "details": finding.get("details", {}),
    }


def _trace(parser_name: str, trace: list[str] | None) -> list[str]:
    if trace:
        return trace
    return [
        "W0 context loaded",
        f"W1 format extract via {parser_name}",
        "E1 capture completeness eval",
        "E2 parser quality eval",
        "E3 source truth eval",
    ]