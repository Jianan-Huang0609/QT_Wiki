from __future__ import annotations

import re
from typing import Any

from Tool.contracts.canonical import CanonicalDocument, Fragment, Section, TableData

NOISE_TITLE_RE = re.compile(
    r"^(?:\d{1,4}|\d{4}[/-]\d{1,2}[/-]\d{1,2}|目录|contents?|confidential|page\s+\d+|第?\s*\d+\s*页)$",
    re.IGNORECASE,
)
LLM_ASSIST_KEYS = ("llm_assist", "assist", "llm_candidates", "llm_outputs")
LLM_CONTENT_KEYS = ("label", "summary", "text", "content", "answer", "rewrite")
LLM_EVIDENCE_KEYS = ("evidence_fragment_ids", "source_refs", "source_anchors", "citations")


def evaluate_parser_quality(canonical: CanonicalDocument) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    findings.extend(_parser_error_findings(canonical))
    findings.extend(_expected_heading_findings(canonical))
    findings.extend(_section_tree_findings(canonical.sections))
    findings.extend(_fragment_section_findings(canonical.sections, canonical.fragments))
    findings.extend(_noise_findings(canonical.sections))
    findings.extend(_table_findings(canonical.tables))
    findings.extend(_figure_findings(canonical))
    findings.extend(_llm_evidence_findings(canonical))
    return {"findings": findings, "metrics": _quality_metrics(canonical, findings)}


def _parser_error_findings(canonical: CanonicalDocument) -> list[dict[str, Any]]:
    if not canonical.errors:
        return []
    has_content = bool(canonical.fragments or canonical.tables or canonical.figures)
    return [
        _finding(
            "P0-03",
            "warn" if has_content else "fail",
            "parser completed with extraction errors",
            reference="REF-PARSER",
            details={"error_count": len(canonical.errors), "error_samples": canonical.errors[:10]},
        )
    ]


def _expected_heading_findings(canonical: CanonicalDocument) -> list[dict[str, Any]]:
    expected = _expected_headings(canonical.document.metadata)
    if not expected:
        return []
    searchable = "\n".join(
        [section.title for section in canonical.sections]
        + [fragment.text for fragment in canonical.fragments]
    ).casefold()
    missing = [heading for heading in expected if heading.casefold() not in searchable]
    if not missing:
        return []
    return [
        _finding(
            "P1-01",
            "warn",
            "expected headings or key items were not captured",
            reference="REF-EVALS",
            details={"missing_expected_items": missing},
        )
    ]


def _expected_headings(metadata: dict[str, Any]) -> list[str]:
    raw = metadata.get("expected_headings")
    if raw is None:
        raw = metadata.get("quality_expectations", {}).get("expected_headings", [])
    if isinstance(raw, str):
        return [raw]
    if isinstance(raw, list):
        return [str(item).strip() for item in raw if str(item).strip()]
    return []


def _section_tree_findings(sections: list[Section]) -> list[dict[str, Any]]:
    if not sections:
        return []
    findings: list[dict[str, Any]] = []
    section_ids = [section.section_id for section in sections]
    duplicate_ids = sorted({section_id for section_id in section_ids if section_ids.count(section_id) > 1})
    if duplicate_ids:
        findings.append(
            _finding(
                "P2-01",
                "fail",
                "duplicate section ids detected",
                reference="REF-STRUCTURE",
                details={"duplicate_section_ids": duplicate_ids},
            )
        )

    seen: set[str] = set()
    section_by_id = {section.section_id: section for section in sections}
    missing_parents: list[str] = []
    late_parents: list[str] = []
    level_jumps: list[str] = []
    previous_level = sections[0].level
    for section in sections:
        if section.parent_id and section.parent_id not in section_by_id:
            missing_parents.append(section.section_id)
        if section.parent_id and section.parent_id not in seen:
            late_parents.append(section.section_id)
        parent = section_by_id.get(section.parent_id or "")
        if parent and section.level <= parent.level:
            level_jumps.append(section.section_id)
        if section.level > previous_level + 1:
            level_jumps.append(section.section_id)
        previous_level = section.level
        seen.add(section.section_id)

    if missing_parents or late_parents:
        findings.append(
            _finding(
                "P2-01",
                "fail",
                "section tree contains missing or late parent references",
                reference="REF-STRUCTURE",
                details={"missing_parent_sections": missing_parents, "late_parent_sections": late_parents},
            )
        )
    if level_jumps:
        findings.append(
            _finding(
                "P2-01",
                "warn",
                "section levels look inconsistent",
                reference="REF-STRUCTURE",
                details={"level_jump_sections": sorted(set(level_jumps))},
            )
        )
    return findings


def _fragment_section_findings(sections: list[Section], fragments: list[Fragment]) -> list[dict[str, Any]]:
    if not fragments:
        return []
    section_by_id = {section.section_id: section for section in sections}
    missing_refs = [fragment.fragment_id for fragment in fragments if fragment.section_id and fragment.section_id not in section_by_id]
    findings: list[dict[str, Any]] = []
    if missing_refs:
        findings.append(
            _finding(
                "P2-02",
                "fail",
                "fragments reference missing sections",
                reference="REF-STRUCTURE",
                details={"fragment_ids": missing_refs},
            )
        )

    if sections:
        unassigned = [fragment.fragment_id for fragment in fragments if fragment.section_id is None]
        unassigned_ratio = len(unassigned) / len(fragments)
        if unassigned_ratio > 0.35:
            findings.append(
                _finding(
                    "P2-02",
                    "warn",
                    "many fragments are not assigned to a section",
                    reference="REF-STRUCTURE",
                    details={"unassigned_fragment_ratio": round(unassigned_ratio, 4), "fragment_ids": unassigned[:20]},
                )
            )

    drift_fragments: list[str] = []
    for fragment in fragments:
        if not fragment.section_id or fragment.section_id not in section_by_id:
            continue
        heading_path = fragment.anchors.get("heading_path")
        if isinstance(heading_path, list) and heading_path:
            section_title = section_by_id[fragment.section_id].title
            if section_title not in [str(item) for item in heading_path]:
                drift_fragments.append(fragment.fragment_id)
    if drift_fragments:
        findings.append(
            _finding(
                "P2-02",
                "warn",
                "fragment heading_path does not match assigned section",
                reference="REF-STRUCTURE",
                details={"fragment_ids": drift_fragments[:20]},
            )
        )
    return findings


def _noise_findings(sections: list[Section]) -> list[dict[str, Any]]:
    if not sections:
        return []
    noisy = [section.title for section in sections if _looks_like_noise_title(section.title)]
    if not noisy:
        return []
    return [
        _finding(
            "P2-03",
            "warn",
            "section titles contain likely header, footer, catalog, or page-number noise",
            reference="REF-STRUCTURE",
            details={"noise_samples": noisy[:20], "noise_rate": round(len(noisy) / len(sections), 4)},
        )
    ]


def _looks_like_noise_title(title: str) -> bool:
    normalized = re.sub(r"\s+", " ", title.strip())
    return bool(NOISE_TITLE_RE.match(normalized))


def _table_findings(tables: list[TableData]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    empty_tables = [table.table_id for table in tables if not table.rows]
    missing_anchors = [table.table_id for table in tables if not table.anchors]
    irregular_tables = [table.table_id for table in tables if _has_irregular_rows(table)]
    if empty_tables or missing_anchors or irregular_tables:
        findings.append(
            _finding(
                "P1-02",
                "warn",
                "table extraction needs review for empty rows, anchors, or irregular shape",
                reference="REF-STRUCTURE",
                details={
                    "empty_tables": empty_tables,
                    "missing_anchor_tables": missing_anchors,
                    "irregular_shape_tables": irregular_tables,
                },
            )
        )
    return findings


def _has_irregular_rows(table: TableData) -> bool:
    row_lengths = {len(row) for row in table.rows if row}
    return len(row_lengths) > 1


def _figure_findings(canonical: CanonicalDocument) -> list[dict[str, Any]]:
    if not canonical.figures:
        return []
    missing_caption = [figure.figure_id for figure in canonical.figures if not figure.caption.strip()]
    missing_anchors = [figure.figure_id for figure in canonical.figures if not figure.anchors]
    if not missing_caption and not missing_anchors:
        return []
    return [
        _finding(
            "P1-03",
            "warn",
            "figure extraction needs review for missing caption or source anchors",
            reference="REF-STRUCTURE",
            details={"missing_caption_figures": missing_caption, "missing_anchor_figures": missing_anchors},
        )
    ]


def _llm_evidence_findings(canonical: CanonicalDocument) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for key in LLM_ASSIST_KEYS:
        for index, item in enumerate(_as_items(canonical.document.metadata.get(key))):
            if _has_llm_content(item) and not _has_valid_evidence(item, canonical):
                findings.append(
                    _finding(
                        "L1-01",
                        "fail",
                        "LLM assist output lacks source evidence and may have altered content",
                        reference="REF-EVALS",
                        details={"metadata_key": key, "item_index": index},
                    )
                )
    for fragment in canonical.fragments:
        if fragment.anchors.get("llm_generated") is True and not _has_valid_evidence(fragment.anchors, canonical):
            findings.append(
                _finding(
                    "L1-01",
                    "fail",
                    "LLM-generated fragment lacks source evidence",
                    reference="REF-EVALS",
                    details={"fragment_id": fragment.fragment_id},
                )
            )
    return findings


def _as_items(value: Any) -> list[Any]:
    if value is None:
        return []
    if isinstance(value, list):
        return value
    return [value]


def _has_llm_content(item: Any) -> bool:
    if isinstance(item, str):
        return bool(item.strip())
    if isinstance(item, dict):
        return any(str(item.get(key, "")).strip() for key in LLM_CONTENT_KEYS)
    return bool(item)


def _has_valid_evidence(item: Any, canonical: CanonicalDocument) -> bool:
    if not isinstance(item, dict):
        return False
    fragment_ids = {fragment.fragment_id for fragment in canonical.fragments}
    document_id = canonical.document.document_id
    evidence_fragment_ids = item.get("evidence_fragment_ids")
    if isinstance(evidence_fragment_ids, list) and any(str(fragment_id) in fragment_ids for fragment_id in evidence_fragment_ids):
        return True
    for key in ("source_refs", "citations", "source_anchors"):
        refs = item.get(key)
        for ref in _as_items(refs):
            if not isinstance(ref, dict):
                continue
            ref_fragment_id = str(ref.get("fragment_id", "")).strip()
            ref_document_id = str(ref.get("document_id", document_id)).strip()
            if ref_fragment_id and ref_fragment_id in fragment_ids and ref_document_id == document_id:
                return True
    return False


def _quality_metrics(canonical: CanonicalDocument, findings: list[dict[str, Any]]) -> dict[str, float | int]:
    noisy_count = len([section for section in canonical.sections if _looks_like_noise_title(section.title)])
    section_count = len(canonical.sections)
    return {
        "noise_rate": round(noisy_count / section_count, 4) if section_count else 0.0,
        "quality_issue_count": len([finding for finding in findings if finding["status"] in {"warn", "fail"}]),
        "low_confidence_count": len([finding for finding in findings if finding["status"] == "warn"]),
    }


def _finding(
    eval_id: str,
    status: str,
    message: str,
    *,
    reference: str,
    details: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "eval_id": eval_id,
        "status": status,
        "message": message,
        "reference": reference,
        "details": details or {},
    }