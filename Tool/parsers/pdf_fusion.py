from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from Tool.contracts.canonical import CanonicalDocument, Fragment
from Tool.parsers.fusion import ExtractionBlock, FusionDecision, LayoutBlock, build_parser_fusion_metadata
from Tool.parsers.providers.docling_provider import DoclingProviderOutput


def parse_pdf_with_fusion(
    file_path: str | Path,
    manifest: dict[str, Any],
    *,
    docling_output: DoclingProviderOutput | None = None,
    enable_docling: bool = False,
    docling_converter: Any | None = None,
) -> CanonicalDocument:
    from Tool.parsers.pdf_parser import parse_pdf
    from Tool.parsers.providers.docling_provider import extract_docling_blocks

    canonical = parse_pdf(Path(file_path), manifest)
    active_docling_output = docling_output
    if active_docling_output is None and enable_docling:
        active_docling_output = extract_docling_blocks(file_path, converter=docling_converter)
    canonical.document.metadata["parser_fusion"] = build_pdf_fusion_metadata(
        canonical,
        docling_output=active_docling_output,
    )
    return canonical


def build_pdf_fusion_metadata(
    canonical: CanonicalDocument,
    *,
    docling_output: DoclingProviderOutput | None = None,
) -> dict[str, Any]:
    pypdf_blocks = [_pypdf_fragment_block(fragment) for fragment in canonical.fragments]
    docling_extraction_blocks = list(docling_output.extraction_blocks) if docling_output else []
    docling_layout_blocks = list(docling_output.layout_blocks) if docling_output else []
    docling_table_blocks = list(docling_output.table_blocks) if docling_output else []
    docling_visual_candidates = list(docling_output.visual_candidates) if docling_output else []
    fusion_decisions = _fusion_decisions(pypdf_blocks, docling_layout_blocks, docling_extraction_blocks)

    providers = ["pypdf_fast_text"]
    if docling_output:
        providers.append(docling_output.provider)
        providers.extend(block.provider for block in docling_extraction_blocks)
        providers.extend(block.provider for block in docling_layout_blocks)
        providers.extend(block.provider for block in docling_table_blocks)
        providers.extend(candidate.provider for candidate in docling_visual_candidates)

    return build_parser_fusion_metadata(
        providers=providers,
        extraction_blocks=[*pypdf_blocks, *docling_extraction_blocks],
        layout_blocks=docling_layout_blocks,
        table_blocks=docling_table_blocks,
        visual_candidates=docling_visual_candidates,
        fusion_decisions=fusion_decisions,
        canonical_output={
            "sections": len(canonical.sections),
            "fragments": len(canonical.fragments),
            "tables": len(canonical.tables),
            "figures": len(canonical.figures),
            "source_anchors": len(canonical.source_anchors),
        },
        fusion_mode="pdf_provider_fusion",
    )


def _pypdf_fragment_block(fragment: Fragment) -> ExtractionBlock:
    return ExtractionBlock(
        block_id=f"pypdf-{fragment.fragment_id}",
        provider="pypdf_fast_text",
        block_type=fragment.fragment_type or "text",
        text=fragment.text,
        anchors=dict(fragment.anchors),
        confidence=1.0,
        metadata={
            "canonical_fragment_id": fragment.fragment_id,
            "section_id": fragment.section_id,
        },
    )


def _fusion_decisions(
    pypdf_blocks: list[ExtractionBlock],
    docling_layout_blocks: list[LayoutBlock],
    docling_extraction_blocks: list[ExtractionBlock],
) -> list[FusionDecision]:
    decisions: list[FusionDecision] = []
    used_docling_block_ids: set[str] = set()
    docling_candidates: list[LayoutBlock | ExtractionBlock] = [*docling_layout_blocks, *docling_extraction_blocks]

    for pypdf_block in pypdf_blocks:
        docling_block = _best_docling_match(pypdf_block, docling_candidates, used_docling_block_ids)
        if docling_block is None:
            continue
        used_docling_block_ids.add(docling_block.block_id)
        merged_anchors = {**pypdf_block.anchors, **docling_block.anchors}
        decisions.append(
            FusionDecision(
                decision_id=f"fusion-{pypdf_block.block_id}-{docling_block.block_id}",
                decision_type="merge_blocks",
                selected_block_ids=[pypdf_block.block_id, docling_block.block_id],
                reason="Docling layout/text block matched pypdf page and normalized text; bbox/reading_order enrich the canonical PDF anchor.",
                confidence=round(min(pypdf_block.confidence, docling_block.confidence), 4),
                output_target="parser_fusion_anchor_enrichment",
                metadata={
                    "canonical_fragment_id": pypdf_block.metadata.get("canonical_fragment_id", ""),
                    "docling_block_id": docling_block.block_id,
                    "merged_anchors": merged_anchors,
                },
            )
        )
    return decisions


def _best_docling_match(
    pypdf_block: ExtractionBlock,
    docling_candidates: list[LayoutBlock | ExtractionBlock],
    used_docling_block_ids: set[str],
) -> LayoutBlock | ExtractionBlock | None:
    pypdf_text = _normalized_text(pypdf_block.text)
    if not pypdf_text:
        return None
    pypdf_page = pypdf_block.anchors.get("page")

    for candidate in docling_candidates:
        if candidate.block_id in used_docling_block_ids:
            continue
        if pypdf_page is not None and candidate.anchors.get("page") != pypdf_page:
            continue
        candidate_text = _normalized_text(candidate.text)
        if not candidate_text:
            continue
        if pypdf_text == candidate_text:
            return candidate
    return None


def _normalized_text(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip().casefold()