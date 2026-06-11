from __future__ import annotations

from dataclasses import dataclass, field
from importlib import import_module as default_import_module
from pathlib import Path
from typing import Any, Callable, Iterable

from Tool.parsers.fusion import (
    ExtractionBlock,
    LayoutBlock,
    TableBlock,
    VisualCandidate,
    build_parser_fusion_metadata,
)

DOC_CONTAINER_ATTRIBUTES = ("document", "doc")
TEXT_COLLECTION_ATTRIBUTES = ("texts", "text_items", "paragraphs", "sections")
TABLE_COLLECTION_ATTRIBUTES = ("tables", "table_items")
PICTURE_COLLECTION_ATTRIBUTES = ("pictures", "images", "figures")


@dataclass(slots=True)
class DoclingProviderOutput:
    provider: str = "docling"
    extraction_blocks: list[ExtractionBlock] = field(default_factory=list)
    layout_blocks: list[LayoutBlock] = field(default_factory=list)
    table_blocks: list[TableBlock] = field(default_factory=list)
    visual_candidates: list[VisualCandidate] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


ImportModule = Callable[[str], Any]


def load_docling_converter_class(*, import_module: ImportModule = default_import_module) -> type[Any]:
    try:
        module = import_module("docling.document_converter")
    except ImportError as exc:
        raise RuntimeError("Docling is required for Docling provider extraction. Install it with: pip install docling") from exc
    return module.DocumentConverter


def extract_docling_blocks(file_path: str | Path, *, converter: Any | None = None) -> DoclingProviderOutput:
    path = Path(file_path)
    active_converter = converter or load_docling_converter_class()()
    result = active_converter.convert(str(path))
    document = _docling_document(result)
    output = DoclingProviderOutput()

    for index, item in enumerate(_iter_collection(document, TEXT_COLLECTION_ATTRIBUTES), start=1):
        text = _item_text(item)
        if not text:
            continue
        anchors = _anchors(item, index=index)
        block_id = _block_id(item, prefix="docling-text", index=index)
        confidence = _confidence(item)
        output.extraction_blocks.append(
            ExtractionBlock(
                block_id=block_id,
                provider="docling",
                block_type="text",
                text=text,
                anchors=anchors,
                confidence=confidence,
                metadata=_metadata(item),
            )
        )
        output.layout_blocks.append(
            LayoutBlock(
                block_id=_block_id(item, prefix="docling-layout", index=index),
                provider="docling",
                text=text,
                layout_type=_label(item),
                anchors=anchors,
                confidence=confidence,
                metadata=_metadata(item),
            )
        )

    for index, item in enumerate(_iter_collection(document, TABLE_COLLECTION_ATTRIBUTES), start=1):
        rows = _table_rows(item)
        output.table_blocks.append(
            TableBlock(
                block_id=_block_id(item, prefix="docling-table", index=index),
                provider="docling",
                rows=rows,
                anchors=_anchors(item, index=index),
                confidence=_confidence(item),
                metadata={**_metadata(item), "label": _label(item)},
            )
        )

    for index, item in enumerate(_iter_collection(document, PICTURE_COLLECTION_ATTRIBUTES), start=1):
        output.visual_candidates.append(
            VisualCandidate(
                candidate_id=_block_id(item, prefix="docling-visual", index=index),
                provider="docling_ocr",
                candidate_type=_label(item),
                text=_item_text(item),
                anchors=_anchors(item, index=index),
                confidence=_confidence(item),
                review_status=_review_status(item),
                metadata=_metadata(item),
            )
        )

    return output


def build_docling_parser_fusion_metadata(
    output: DoclingProviderOutput,
    *,
    canonical_output: dict[str, int] | None = None,
) -> dict[str, Any]:
    providers = [output.provider]
    providers.extend(candidate.provider for candidate in output.visual_candidates)
    return build_parser_fusion_metadata(
        providers=providers,
        extraction_blocks=output.extraction_blocks,
        layout_blocks=output.layout_blocks,
        table_blocks=output.table_blocks,
        visual_candidates=output.visual_candidates,
        canonical_output=canonical_output,
        fusion_mode="docling_provider_extraction",
    )


def _docling_document(result: Any) -> Any:
    for attribute in DOC_CONTAINER_ATTRIBUTES:
        document = getattr(result, attribute, None)
        if document is not None:
            return document
    return result


def _iter_collection(document: Any, attribute_names: Iterable[str]) -> list[Any]:
    for attribute in attribute_names:
        value = getattr(document, attribute, None)
        if value is None:
            continue
        if callable(value):
            value = value()
        if isinstance(value, dict):
            return list(value.values())
        return list(value)
    return []


def _item_text(item: Any) -> str:
    for attribute in ("text", "orig", "content", "caption", "caption_text"):
        value = getattr(item, attribute, None)
        if value:
            return str(value).strip()
    exporter = getattr(item, "export_to_markdown", None)
    if callable(exporter):
        exported = exporter()
        if exported:
            return str(exported).strip()
    return ""


def _table_rows(item: Any) -> list[list[str]]:
    rows = _maybe_rows(getattr(item, "rows", None))
    if rows:
        return rows
    data = getattr(item, "data", None)
    if data is not None:
        rows = _maybe_rows(getattr(data, "rows", None))
        if rows:
            return rows
    dataframe_exporter = getattr(item, "export_to_dataframe", None)
    if callable(dataframe_exporter):
        dataframe = dataframe_exporter()
        rows = _dataframe_rows(dataframe)
        if rows:
            return rows
    return []


def _maybe_rows(value: Any) -> list[list[str]]:
    if value is None:
        return []
    rows: list[list[str]] = []
    for row in list(value):
        if isinstance(row, dict):
            rows.append([str(cell) for cell in row.values()])
        elif isinstance(row, (list, tuple)):
            rows.append([str(cell) for cell in row])
        else:
            rows.append([str(row)])
    return rows


def _dataframe_rows(dataframe: Any) -> list[list[str]]:
    rows: list[list[str]] = []
    columns = getattr(dataframe, "columns", None)
    if columns is not None:
        rows.append([str(column) for column in list(columns)])
    values = getattr(dataframe, "values", None)
    tolist = getattr(values, "tolist", None)
    if callable(tolist):
        rows.extend([[str(cell) for cell in row] for row in tolist()])
    return rows


def _anchors(item: Any, *, index: int) -> dict[str, Any]:
    anchors: dict[str, Any] = {"provider_index": index}
    provenance = _first_provenance(item)
    page = _first_attr(provenance, item, names=("page_no", "page", "page_number"))
    if page is not None:
        anchors["page"] = int(page)
    bbox = _first_attr(provenance, item, names=("bbox", "bounding_box"))
    if bbox is not None:
        anchors["bbox"] = _bbox_values(bbox)
    reading_order = _first_attr(item, provenance, names=("reading_order", "reading_order_index", "order"))
    if reading_order is not None:
        anchors["reading_order"] = int(reading_order)
    return anchors


def _first_provenance(item: Any) -> Any | None:
    value = getattr(item, "prov", None) or getattr(item, "provenance", None)
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        return value[0] if value else None
    return value


def _first_attr(*objects: Any, names: tuple[str, ...]) -> Any | None:
    for current_object in objects:
        if current_object is None:
            continue
        for name in names:
            value = getattr(current_object, name, None)
            if value is not None:
                return value
    return None


def _bbox_values(bbox: Any) -> list[float | int]:
    if isinstance(bbox, (list, tuple)):
        return [float(value) if isinstance(value, float) else int(value) for value in bbox]
    values = []
    for name in ("l", "t", "r", "b"):
        value = getattr(bbox, name, None)
        if value is not None:
            values.append(value)
    if len(values) == 4:
        return [float(value) if isinstance(value, float) else int(value) for value in values]
    values = []
    for name in ("left", "top", "right", "bottom"):
        value = getattr(bbox, name, None)
        if value is not None:
            values.append(value)
    return [float(value) if isinstance(value, float) else int(value) for value in values]


def _confidence(item: Any) -> float:
    value = getattr(item, "confidence", None)
    if value is None:
        return 1.0
    return float(value)


def _label(item: Any) -> str:
    value = getattr(item, "label", None) or getattr(item, "type", None) or "text"
    return str(getattr(value, "value", value)).strip() or "text"


def _metadata(item: Any) -> dict[str, Any]:
    metadata = getattr(item, "metadata", None)
    if isinstance(metadata, dict):
        return dict(metadata)
    self_ref = getattr(item, "self_ref", None)
    return {"self_ref": str(self_ref)} if self_ref else {}


def _review_status(item: Any) -> str:
    value = getattr(item, "review_status", None)
    return str(value) if value else "pending_review"


def _block_id(item: Any, *, prefix: str, index: int) -> str:
    self_ref = getattr(item, "self_ref", None)
    if self_ref:
        normalized = str(self_ref).strip("#/").replace("/", "-")
        if normalized:
            return f"{prefix}-{normalized}"
    return f"{prefix}-{index}"
