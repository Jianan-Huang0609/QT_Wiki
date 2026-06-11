from __future__ import annotations

from collections import Counter
from typing import Any

STATUS_KEYS = ("pass", "warn", "fail", "na")


def evaluate_answer_grounding(answer_text: str, evidence_package: Any) -> dict[str, Any]:
    package = evidence_package.to_dict() if hasattr(evidence_package, "to_dict") else dict(evidence_package or {})
    evidence_items = list(package.get("evidence_items", []))
    findings: list[dict[str, Any]] = []

    if answer_text.strip() and not evidence_items:
        findings.append(
            _finding(
                "A2-01",
                "fail",
                "answer makes claims without primary evidence",
                details={"answer_preview": answer_text[:200]},
            )
        )
    elif evidence_items:
        cited_items = _cited_evidence_items(answer_text, evidence_items)
        findings.append(
            _finding(
                "A1-01",
                "pass" if cited_items else "fail",
                "answer cites primary evidence" if cited_items else "answer is missing citations to primary evidence",
                details={
                    "cited_evidence_ids": [str(item.get("evidence_id", "")) for item in cited_items],
                    "available_evidence_ids": [str(item.get("evidence_id", "")) for item in evidence_items],
                },
            )
        )

    missing_evidence = list(package.get("missing_evidence", []))
    if missing_evidence and not _contains_abstention(answer_text):
        findings.append(
            _finding(
                "A3-01",
                "warn",
                "answer package has missing evidence but answer does not signal uncertainty",
                details={"missing_evidence": missing_evidence},
            )
        )

    return {
        "eval_summary": _summary(findings),
        "metrics": {
            "evidence_count": len(evidence_items),
            "missing_evidence_count": len(missing_evidence),
            "cited_evidence_count": len(_cited_evidence_items(answer_text, evidence_items)),
        },
        "findings": findings,
    }


def _cited_evidence_items(answer_text: str, evidence_items: list[dict[str, Any]]) -> list[dict[str, Any]]:
    answer = answer_text.casefold()
    cited: list[dict[str, Any]] = []
    for item in evidence_items:
        evidence_id = str(item.get("evidence_id", "")).casefold()
        anchor_label = str(item.get("anchor_label", "")).casefold()
        if evidence_id and evidence_id in answer:
            cited.append(item)
            continue
        if anchor_label and anchor_label in answer:
            cited.append(item)
    return cited


def _contains_abstention(answer_text: str) -> bool:
    answer = answer_text.casefold()
    return any(marker in answer for marker in ("缺", "不足", "无法确认", "missing", "insufficient", "not enough"))


def _finding(eval_id: str, status: str, message: str, *, details: dict[str, Any]) -> dict[str, Any]:
    return {
        "eval_id": eval_id,
        "status": status,
        "message": message,
        "reference": "REF-ANSWER-EVAL",
        "details": details,
    }


def _summary(findings: list[dict[str, Any]]) -> dict[str, int]:
    counts = Counter(str(finding.get("status", "na")) for finding in findings)
    return {key: int(counts.get(key, 0)) for key in STATUS_KEYS}