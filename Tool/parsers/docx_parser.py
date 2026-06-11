from __future__ import annotations

import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

from Tool.contracts.canonical import CanonicalDocument, DocumentMeta, Fragment, Section, TableData
from Tool.normalizers import detect_doc_type, extract_terms, normalize_text
from Tool.parsers.structure import DetectedHeading, detect_heading

NS = {"w": "http://schemas.openxmlformats.org/wordprocessingml/2006/main"}
SECTION_RE = re.compile(r"^第[一二三四五六七八九十百零〇\d]+章")


def parse_docx(file_path: Path, manifest: dict) -> CanonicalDocument:
    with zipfile.ZipFile(file_path) as archive:
        root = ET.fromstring(archive.read("word/document.xml"))

    sections: list[Section] = []
    fragments: list[Fragment] = []
    tables: list[TableData] = []
    current_section_id: str | None = None
    section_stack: list[Section] = []
    paragraph_index = 0
    table_index = 0

    body = root.find("w:body", NS)
    if body is None:
        raise ValueError("DOCX body not found")

    for child in body:
        if child.tag.endswith("}p"):
            text = _paragraph_text(child)
            if not text:
                continue
            paragraph_index += 1
            heading = detect_heading(text, style_level=_paragraph_heading_level(child))
            if heading:
                current_section_id = _append_section(sections, section_stack, heading)
            fragments.append(
                Fragment(
                    fragment_id=f"frag-{paragraph_index}",
                    section_id=current_section_id,
                    fragment_type="paragraph",
                    text=text,
                    anchors={
                        "paragraph_index": paragraph_index,
                        **({"heading_path": [section.title for section in section_stack]} if section_stack else {}),
                    },
                )
            )
        elif child.tag.endswith("}tbl"):
            rows = _table_rows(child)
            if not rows:
                continue
            table_index += 1
            tables.append(
                TableData(
                    table_id=f"tbl-{table_index}",
                    section_id=current_section_id,
                    page=None,
                    rows=rows,
                    anchors={
                        "table_index": table_index,
                        "cell_range": _cell_range(rows),
                        "row_count": len(rows),
                        "column_count": _column_count(rows),
                        **({"heading_path": [section.title for section in section_stack]} if section_stack else {}),
                    },
                )
            )

    title = _pick_title(fragments, file_path.stem)
    meta = DocumentMeta(
        document_id=manifest["document_id"],
        title=title,
        source_path=manifest["stored_path"],
        file_name=file_path.name,
        source_type="docx",
        doc_type=detect_doc_type(title, file_path.name),
        checksum=manifest.get("checksum", ""),
        metadata={"manifest_path": manifest.get("manifest_path", "")},
    )

    source_anchors = [
        {"fragment_id": fragment.fragment_id, "anchors": fragment.anchors}
        for fragment in fragments
    ] + [
        {"table_id": table.table_id, "anchors": table.anchors}
        for table in tables
    ]

    parse_status = "parsed" if fragments else "failed"
    errors = [] if fragments else ["No text fragments extracted from DOCX."]
    return CanonicalDocument(
        document=meta,
        sections=sections,
        fragments=fragments,
        tables=tables,
        figures=[],
        terms=extract_terms([fragment.text for fragment in fragments]),
        entities=[],
        parse_status=parse_status,
        source_anchors=source_anchors,
        errors=errors,
    )


def _paragraph_text(paragraph: ET.Element) -> str:
    texts = [
        normalize_text(node.text or "")
        for node in paragraph.findall(".//w:t", NS)
        if normalize_text(node.text or "")
    ]
    return normalize_text("".join(texts))


def _paragraph_heading_level(paragraph: ET.Element) -> int | None:
    style = paragraph.find("w:pPr/w:pStyle", NS)
    if style is None:
        return None
    value = style.get(f"{{{NS['w']}}}val", "")
    match = re.search(r"(?:heading|标题)\s*([1-6])", value, re.IGNORECASE)
    if match:
        return int(match.group(1))
    if value in {str(level) for level in range(1, 7)}:
        return int(value)
    return None


def _append_section(sections: list[Section], section_stack: list[Section], heading: DetectedHeading) -> str:
    while section_stack and section_stack[-1].level >= heading.level:
        section_stack.pop()

    parent_id = section_stack[-1].section_id if section_stack else None
    section = Section(
        section_id=f"sec-{len(sections) + 1}",
        title=heading.title,
        level=heading.level,
        page_range=[],
        parent_id=parent_id,
    )
    sections.append(section)
    section_stack.append(section)
    return section.section_id


def _table_rows(table: ET.Element) -> list[list[str]]:
    rows: list[list[str]] = []
    for row in table.findall("w:tr", NS):
        cells = []
        for cell in row.findall("w:tc", NS):
            text = normalize_text(" ".join(_paragraph_text(p) for p in cell.findall(".//w:p", NS)))
            cells.append(text)
        if any(cells):
            rows.append(cells)
    return rows


def _cell_range(rows: list[list[str]]) -> str:
    if not rows:
        return ""
    return f"R1C1:R{len(rows)}C{_column_count(rows)}"


def _column_count(rows: list[list[str]]) -> int:
    return max((len(row) for row in rows), default=0)


def _pick_title(fragments: list[Fragment], fallback: str) -> str:
    for fragment in fragments[:8]:
        text = fragment.text
        if text and len(text) >= 6 and text != "附件":
            return text
    return fallback
