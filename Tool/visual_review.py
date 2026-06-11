from __future__ import annotations

from typing import Any

from Tool.contracts.canonical import CanonicalDocument, TableData


def build_visual_review_items(canonical: CanonicalDocument) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    if canonical.parse_status == "ocr_required":
        items.append(
            {
                "review_id": f"visual-{canonical.document.document_id}-ocr",
                "eval_id": "P1-05",
                "source_type": "document",
                "source_id": canonical.document.document_id,
                "page": None,
                "recommended_tool": "ocr",
                "reason": "document has no usable text layer",
                "status": "needs_review",
                "anchors": {},
            }
        )

    for figure in canonical.figures:
        if figure.anchors.get("visual_analysis") or figure.anchors.get("crop_path"):
            continue
        items.append(
            {
                "review_id": f"visual-{canonical.document.document_id}-{figure.figure_id}",
                "eval_id": "P1-05",
                "source_type": "figure",
                "source_id": figure.figure_id,
                "page": figure.page,
                "recommended_tool": "multimodal",
                "reason": "figure caption exists but diagram content has not been visually analyzed",
                "status": "needs_review",
                "caption": figure.caption,
                "anchors": dict(figure.anchors),
            }
        )

    for table in canonical.tables:
        if _requires_table_visual_review(table, canonical):
            items.append(
                {
                    "review_id": f"visual-{canonical.document.document_id}-{table.table_id}",
                    "eval_id": "P1-05",
                    "source_type": "table",
                    "source_id": table.table_id,
                    "page": table.page,
                    "recommended_tool": "ocr_or_multimodal",
                    "reason": "table shape or source PDF layout needs visual verification",
                    "status": "needs_review",
                    "anchors": dict(table.anchors),
                    "row_count": len(table.rows),
                }
            )
    return items


def _requires_table_visual_review(table: TableData, canonical: CanonicalDocument) -> bool:
    if table.anchors.get("visual_analysis") or table.anchors.get("table_type") == "document_history":
        return False
    if table.anchors.get("requires_visual_review") is True:
        return True
    row_lengths = {len(row) for row in table.rows if row}
    if len(row_lengths) > 1:
        return True
    return canonical.document.source_type.lower() == "pdf" and len(table.rows) >= 20