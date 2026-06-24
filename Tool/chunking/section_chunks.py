from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from Tool.contracts.canonical import CanonicalDocument, FigureData, Fragment, Section, TableData
from Tool.normalizers import normalize_text


@dataclass(slots=True)
class SectionChunk:
    chunk_id: str
    document_id: str
    document_title: str
    file_name: str
    section_id: str | None
    section_title: str
    section_path: list[str]
    chunk_type: str
    text: str
    quote: str
    source_refs: list[dict[str, Any]] = field(default_factory=list)
    anchors: dict[str, Any] = field(default_factory=dict)
    signals: list[str] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_section_chunks(canonical: CanonicalDocument, *, max_chars: int = 1800) -> list[SectionChunk]:
    section_by_id = {section.section_id: section for section in canonical.sections}
    fragments_by_section: dict[str | None, list[Fragment]] = {}
    for fragment in canonical.fragments:
        fragments_by_section.setdefault(fragment.section_id, []).append(fragment)

    chunks: list[SectionChunk] = []
    for section in canonical.sections:
        fragments = fragments_by_section.get(section.section_id, [])
        chunks.extend(
            _section_chunks(
                canonical,
                section,
                fragments,
                section_by_id=section_by_id,
                max_chars=max_chars,
                chunk_offset=len(chunks),
            )
        )

    chunks.extend(_table_chunks(canonical, section_by_id=section_by_id, chunk_offset=len(chunks)))
    chunks.extend(_figure_chunks(canonical, section_by_id=section_by_id, chunk_offset=len(chunks)))
    return chunks


def _section_chunks(
    canonical: CanonicalDocument,
    section: Section,
    fragments: list[Fragment],
    *,
    section_by_id: dict[str, Section],
    max_chars: int,
    chunk_offset: int,
) -> list[SectionChunk]:
    if not fragments:
        return []

    section_path = _section_path(section, section_by_id)
    chunk_fragments: list[Fragment] = []
    chunks: list[SectionChunk] = []
    current_len = len(section.title)
    for fragment in fragments:
        fragment_text = normalize_text(fragment.text)
        if chunk_fragments and current_len + len(fragment_text) > max_chars:
            chunks.append(
                _make_section_chunk(
                    canonical,
                    section,
                    section_path,
                    chunk_fragments,
                    chunk_index=chunk_offset + len(chunks) + 1,
                )
            )
            chunk_fragments = []
            current_len = len(section.title)
        chunk_fragments.append(fragment)
        current_len += len(fragment_text) + 1

    if chunk_fragments:
        chunks.append(
            _make_section_chunk(
                canonical,
                section,
                section_path,
                chunk_fragments,
                chunk_index=chunk_offset + len(chunks) + 1,
            )
        )
    return chunks


def _make_section_chunk(
    canonical: CanonicalDocument,
    section: Section,
    section_path: list[str],
    fragments: list[Fragment],
    *,
    chunk_index: int,
) -> SectionChunk:
    body = "\n".join(normalize_text(fragment.text) for fragment in fragments if normalize_text(fragment.text))
    text = normalize_text(f"{section.title}\n{body}")
    source_refs = [_fragment_source_ref(canonical, section, fragment) for fragment in fragments]
    anchors = _merge_anchor_range([fragment.anchors for fragment in fragments])
    return SectionChunk(
        chunk_id=f"chunk-{canonical.document.document_id}-{chunk_index}",
        document_id=canonical.document.document_id,
        document_title=canonical.document.title,
        file_name=canonical.document.file_name,
        section_id=section.section_id,
        section_title=section.title,
        section_path=section_path,
        chunk_type="section",
        text=text,
        quote=text[:500],
        source_refs=source_refs,
        anchors=anchors,
        signals=_signals(section.title, text),
    )


def _table_chunks(
    canonical: CanonicalDocument,
    *,
    section_by_id: dict[str, Section],
    chunk_offset: int,
) -> list[SectionChunk]:
    chunks: list[SectionChunk] = []
    for table in canonical.tables:
        section = section_by_id.get(table.section_id or "")
        section_title = section.title if section else ""
        chunk_type = "document_history" if table.anchors.get("table_type") == "document_history" else "table"
        table_text = "\n".join(" | ".join(cell for cell in row) for row in table.rows)
        text = normalize_text(f"{section_title}\n{table_text}")
        chunks.append(
            SectionChunk(
                chunk_id=f"chunk-{canonical.document.document_id}-{chunk_offset + len(chunks) + 1}",
                document_id=canonical.document.document_id,
                document_title=canonical.document.title,
                file_name=canonical.document.file_name,
                section_id=table.section_id,
                section_title=section_title,
                section_path=_section_path(section, section_by_id) if section else [],
                chunk_type=chunk_type,
                text=text,
                quote=text[:500],
                source_refs=[_table_source_ref(canonical, section, table)],
                anchors=dict(table.anchors),
                signals=_signals(section_title, text) + _table_signals(table.rows) + [chunk_type],
                metadata={
                    "row_count": len(table.rows),
                    "column_count": _column_count(table.rows),
                    **_table_metadata(table.rows, chunk_type),
                },
            )
        )
    return chunks


def _figure_chunks(
    canonical: CanonicalDocument,
    *,
    section_by_id: dict[str, Section],
    chunk_offset: int,
) -> list[SectionChunk]:
    chunks: list[SectionChunk] = []
    for figure in canonical.figures:
        section = section_by_id.get(figure.section_id or "")
        section_title = section.title if section else ""
        text = normalize_text(f"{section_title}\n{figure.caption}")
        chunks.append(
            SectionChunk(
                chunk_id=f"chunk-{canonical.document.document_id}-{chunk_offset + len(chunks) + 1}",
                document_id=canonical.document.document_id,
                document_title=canonical.document.title,
                file_name=canonical.document.file_name,
                section_id=figure.section_id,
                section_title=section_title,
                section_path=_section_path(section, section_by_id) if section else [],
                chunk_type="figure",
                text=text,
                quote=text[:500],
                source_refs=[_figure_source_ref(canonical, section, figure)],
                anchors=dict(figure.anchors),
                signals=_signals(section_title, text) + ["figure", "visual_review_required"],
            )
        )
    return chunks


def _section_path(section: Section | None, section_by_id: dict[str, Section]) -> list[str]:
    if section is None:
        return []
    path = [section.title]
    current = section
    seen = {section.section_id}
    while current.parent_id:
        parent = section_by_id.get(current.parent_id)
        if parent is None or parent.section_id in seen:
            break
        path.append(parent.title)
        seen.add(parent.section_id)
        current = parent
    return list(reversed(path))


def _fragment_source_ref(canonical: CanonicalDocument, section: Section, fragment: Fragment) -> dict[str, Any]:
    return {
        "document_id": canonical.document.document_id,
        "fragment_id": fragment.fragment_id,
        "file_name": canonical.document.file_name,
        "section_id": section.section_id,
        "section_title": section.title,
        "anchor_label": _anchor_label(fragment.anchors),
        "anchors": dict(fragment.anchors),
        "quote": normalize_text(fragment.text)[:500],
    }


def _table_source_ref(canonical: CanonicalDocument, section: Section | None, table: TableData) -> dict[str, Any]:
    return {
        "document_id": canonical.document.document_id,
        "table_id": table.table_id,
        "file_name": canonical.document.file_name,
        "section_id": table.section_id,
        "section_title": section.title if section else "",
        "anchor_label": _anchor_label(table.anchors),
        "anchors": dict(table.anchors),
        "quote": "\n".join(" | ".join(row) for row in table.rows[:3])[:500],
    }


def _figure_source_ref(canonical: CanonicalDocument, section: Section | None, figure: FigureData) -> dict[str, Any]:
    return {
        "document_id": canonical.document.document_id,
        "figure_id": figure.figure_id,
        "file_name": canonical.document.file_name,
        "section_id": figure.section_id,
        "section_title": section.title if section else "",
        "anchor_label": _anchor_label(figure.anchors),
        "anchors": dict(figure.anchors),
        "quote": figure.caption,
    }


def _anchor_label(anchors: dict[str, Any]) -> str:
    if "page" in anchors:
        return f"p.{anchors['page']}"
    if "line_start" in anchors and "line_end" in anchors:
        return f"L{anchors['line_start']}-L{anchors['line_end']}"
    if "sheet" in anchors and "row_index" in anchors:
        return f"{anchors['sheet']} row {anchors['row_index']}"
    if "table_index" in anchors:
        label = f"tbl.{anchors['table_index']}"
        if anchors.get("cell_range"):
            return f"{label} {anchors['cell_range']}"
        return label
    return ""


def _merge_anchor_range(anchors_list: list[dict[str, Any]]) -> dict[str, Any]:
    pages = [anchors.get("page") for anchors in anchors_list if anchors.get("page") is not None]
    line_starts = [anchors.get("line_start") for anchors in anchors_list if anchors.get("line_start") is not None]
    line_ends = [anchors.get("line_end") for anchors in anchors_list if anchors.get("line_end") is not None]
    merged: dict[str, Any] = {}
    if pages:
        merged["pages"] = sorted(set(pages))
    if line_starts and line_ends:
        merged["line_start"] = min(line_starts)
        merged["line_end"] = max(line_ends)
    return merged


def _signals(title: str, text: str) -> list[str]:
    normalized = f"{title} {text}".casefold()
    signals: list[str] = []
    for marker, signal in (
        ("history", "document_history"),
        ("修改历史", "document_history"),
        ("r2", "stage_r2"),
        ("r3", "stage_r3"),
        ("product owner", "role_product_owner"),
        ("po", "role_po"),
        ("qmp", "deliverable_qmp"),
        ("figure", "figure"),
        ("图", "figure"),
    ):
        if _contains_signal_marker(normalized, marker) and signal not in signals:
            signals.append(signal)
    return signals


def _table_signals(rows: list[list[str]]) -> list[str]:
    header_text = " ".join(rows[0]).casefold() if rows else ""
    signals: list[str] = []
    if "role" in header_text or "responsib" in header_text or "owner" in header_text or "approver" in header_text or "职责" in header_text or "角色" in header_text or "责任" in header_text:
        signals.append("role_table")
    if "deliverable" in header_text or "evidence" in header_text or "output" in header_text or "交付" in header_text or "证据" in header_text:
        signals.append("deliverable_table")
    return signals


def _table_metadata(rows: list[list[str]], chunk_type: str) -> dict[str, Any]:
    headers = [normalize_text(cell) for cell in rows[0]] if rows else []
    row_labels = [normalize_text(row[0]) for row in rows[1:] if row and normalize_text(row[0])]
    signals = set(_table_signals(rows))
    if chunk_type == "document_history":
        table_type = "document_history"
    elif {"role_table", "deliverable_table"}.issubset(signals):
        table_type = "role_deliverable"
    elif "role_table" in signals:
        table_type = "role"
    elif "deliverable_table" in signals:
        table_type = "deliverable"
    else:
        table_type = "generic"
    return {"table_type": table_type, "row_labels": row_labels, "column_headers": headers}


def _column_count(rows: list[list[str]]) -> int:
    return max((len(row) for row in rows), default=0)


def _contains_signal_marker(normalized_text: str, marker: str) -> bool:
    if marker in {"po", "r2", "r3"}:
        return bool(re.search(rf"(?<![a-z0-9]){re.escape(marker)}(?![a-z0-9])", normalized_text))
    return marker in normalized_text


def normalize_search_text(text: str) -> str:
    return re.sub(r"\s+", " ", normalize_text(text)).casefold()