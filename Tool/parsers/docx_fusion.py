from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from Tool.contracts.canonical import CanonicalDocument, Fragment, TableData
from Tool.parsers.fusion import ExtractionBlock, FusionDecision, LayoutBlock, TableBlock, build_parser_fusion_metadata
from Tool.parsers.providers.docling_provider import DoclingProviderOutput


def parse_docx_with_fusion(
    file_path: str | Path,
    manifest: dict[str, Any],
    *,
    docling_output: DoclingProviderOutput | None = None,
    enable_docling: bool = False,
    docling_converter: Any | None = None,
) -> CanonicalDocument:
    from Tool.parsers.docx_parser import parse_docx
    from Tool.parsers.providers.docling_provider import extract_docling_blocks

    canonical = parse_docx(Path(file_path), manifest)
    active_docling_output = docling_output
    if active_docling_output is None and enable_docling:
        active_docling_output = extract_docling_blocks(file_path, converter=docling_converter)
    canonical.document.metadata["parser_fusion"] = build_docx_fusion_metadata(
        canonical,
        docling_output=active_docling_output,
    )
    return canonical


def build_docx_fusion_metadata(
    canonical: CanonicalDocument,
    *,
    docling_output: DoclingProviderOutput | None = None,
) -> dict[str, Any]:
    docx_blocks = [_docx_fragment_block(fragment) for fragment in canonical.fragments]
    docx_table_blocks = [_docx_table_block(table) for table in canonical.tables]
    docling_extraction_blocks = list(docling_output.extraction_blocks) if docling_output else []
    docling_layout_blocks = list(docling_output.layout_blocks) if docling_output else []
    docling_table_blocks = list(docling_output.table_blocks) if docling_output else []
    docling_visual_candidates = list(docling_output.visual_candidates) if docling_output else []
    fusion_decisions = [
        *_block_fusion_decisions(docx_blocks, docling_layout_blocks, docling_extraction_blocks),
        *_table_fusion_decisions(docx_table_blocks, docling_table_blocks),
    ]

    providers = ["docx_xml"]
    if docling_output:
        providers.append(docling_output.provider)
        providers.extend(block.provider for block in docling_extraction_blocks)
        providers.extend(block.provider for block in docling_layout_blocks)
        providers.extend(block.provider for block in docling_table_blocks)
        providers.extend(candidate.provider for candidate in docling_visual_candidates)

    return build_parser_fusion_metadata(
        providers=providers,
        extraction_blocks=[*docx_blocks, *docling_extraction_blocks],
        layout_blocks=docling_layout_blocks,
        table_blocks=[*docx_table_blocks, *docling_table_blocks],
        visual_candidates=docling_visual_candidates,
        fusion_decisions=fusion_decisions,
        canonical_output={
            "sections": len(canonical.sections),
            "fragments": len(canonical.fragments),
            "tables": len(canonical.tables),
            "figures": len(canonical.figures),
            "source_anchors": len(canonical.source_anchors),
        },
        fusion_mode="docx_provider_fusion",
    )


def _docx_fragment_block(fragment: Fragment) -> ExtractionBlock:
    return ExtractionBlock(
        block_id=f"docx-{fragment.fragment_id}",
        provider="docx_xml",
        block_type=fragment.fragment_type or "text",
        text=fragment.text,
        anchors=dict(fragment.anchors),
        confidence=1.0,
        metadata={
            "canonical_fragment_id": fragment.fragment_id,
            "section_id": fragment.section_id,
        },
    )


def _docx_table_block(table: TableData) -> TableBlock:
    return TableBlock(
        block_id=f"docx-{table.table_id}",
        provider="docx_xml",
        rows=[list(row) for row in table.rows],
        anchors=dict(table.anchors),
        confidence=1.0,
        metadata={
            "canonical_table_id": table.table_id,
            "section_id": table.section_id,
        },
    )


def _block_fusion_decisions(
    docx_blocks: list[ExtractionBlock],
    docling_layout_blocks: list[LayoutBlock],
    docling_extraction_blocks: list[ExtractionBlock],
) -> list[FusionDecision]:
    decisions: list[FusionDecision] = []
    used_docling_block_ids: set[str] = set()
    docling_candidates: list[LayoutBlock | ExtractionBlock] = [*docling_layout_blocks, *docling_extraction_blocks]

    for docx_block in docx_blocks:
        docling_block = _best_text_match(docx_block, docling_candidates, used_docling_block_ids)
        if docling_block is None:
            continue
        used_docling_block_ids.add(docling_block.block_id)
        merged_anchors = {**docx_block.anchors, **docling_block.anchors}
        decisions.append(
            FusionDecision(
                decision_id=f"fusion-{docx_block.block_id}-{docling_block.block_id}",
                decision_type="merge_blocks",
                selected_block_ids=[docx_block.block_id, docling_block.block_id],
                reason="Docling layout/text block matched DOCX XML text; layout metadata enriches the canonical DOCX anchor.",
                confidence=round(min(docx_block.confidence, docling_block.confidence), 4),
                output_target="parser_fusion_anchor_enrichment",
                metadata={
                    "canonical_fragment_id": docx_block.metadata.get("canonical_fragment_id", ""),
                    "docling_block_id": docling_block.block_id,
                    "merged_anchors": merged_anchors,
                },
            )
        )
    return decisions


def _table_fusion_decisions(
    docx_table_blocks: list[TableBlock],
    docling_table_blocks: list[TableBlock],
) -> list[FusionDecision]:
    decisions: list[FusionDecision] = []
    used_docling_block_ids: set[str] = set()
    for docx_table in docx_table_blocks:
        docling_table = _best_table_match(docx_table, docling_table_blocks, used_docling_block_ids)
        if docling_table is None:
            continue
        used_docling_block_ids.add(docling_table.block_id)
        merged_anchors = {**docx_table.anchors, **docling_table.anchors}
        decisions.append(
            FusionDecision(
                decision_id=f"fusion-{docx_table.block_id}-{docling_table.block_id}",
                decision_type="merge_tables",
                selected_block_ids=[docx_table.block_id, docling_table.block_id],
                reason="Docling table matched DOCX XML table rows; layout metadata enriches table/cell anchors.",
                confidence=round(min(docx_table.confidence, docling_table.confidence), 4),
                output_target="table_candidate",
                metadata={
                    "canonical_table_id": docx_table.metadata.get("canonical_table_id", ""),
                    "docling_block_id": docling_table.block_id,
                    "merged_anchors": merged_anchors,
                },
            )
        )
    return decisions


def _best_text_match(
    docx_block: ExtractionBlock,
    docling_candidates: list[LayoutBlock | ExtractionBlock],
    used_docling_block_ids: set[str],
) -> LayoutBlock | ExtractionBlock | None:
    docx_text = _normalized_text(docx_block.text)
    if not docx_text:
        return None
    for candidate in docling_candidates:
        if candidate.block_id in used_docling_block_ids:
            continue
        if docx_text == _normalized_text(candidate.text):
            return candidate
    return None


def _best_table_match(
    docx_table: TableBlock,
    docling_tables: list[TableBlock],
    used_docling_block_ids: set[str],
) -> TableBlock | None:
    docx_signature = _table_signature(docx_table.rows)
    if not docx_signature:
        return None
    for candidate in docling_tables:
        if candidate.block_id in used_docling_block_ids:
            continue
        if docx_signature == _table_signature(candidate.rows):
            return candidate
    return None


def _table_signature(rows: list[list[str]]) -> tuple[tuple[str, ...], ...]:
    return tuple(tuple(_normalized_text(cell) for cell in row) for row in rows if any(_normalized_text(cell) for cell in row))


def _normalized_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()