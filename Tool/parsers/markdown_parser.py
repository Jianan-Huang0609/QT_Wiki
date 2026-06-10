from __future__ import annotations

import re
from pathlib import Path

from Tool.contracts.canonical import CanonicalDocument, DocumentMeta, Fragment, Section, TableData
from Tool.normalizers import detect_doc_type, extract_terms, normalize_text

HEADING_RE = re.compile(r"^(#{1,6})\s+(.+?)\s*$")
LIST_RE = re.compile(r"^\s*(?:[-*+]\s+|\d+[.)]\s+)")


def parse_markdown(file_path: Path, manifest: dict) -> CanonicalDocument:
    text = file_path.read_text(encoding="utf-8-sig")
    lines = text.splitlines()
    sections: list[Section] = []
    fragments: list[Fragment] = []
    tables: list[TableData] = []
    section_stack: dict[int, str] = {}
    current_section_id: str | None = None
    current_heading_path: list[str] = []
    block: list[tuple[int, str]] = []
    section_index = 0
    fragment_index = 0
    table_index = 0
    in_code_block = False

    def flush_block() -> None:
        nonlocal block, fragment_index, table_index
        if not block:
            return
        content_lines = [line for _, line in block]
        raw_text = "\n".join(content_lines).strip()
        if not raw_text:
            block = []
            return
        fragment_index += 1
        fragment_type = _fragment_type(content_lines)
        anchors = {
            "line_start": block[0][0],
            "line_end": block[-1][0],
            "heading_path": list(current_heading_path),
        }
        fragments.append(
            Fragment(
                fragment_id=f"frag-{fragment_index}",
                section_id=current_section_id,
                fragment_type=fragment_type,
                text=_fragment_text(content_lines),
                anchors=anchors,
            )
        )
        if fragment_type == "table":
            table_index += 1
            tables.append(
                TableData(
                    table_id=f"tbl-{table_index}",
                    section_id=current_section_id,
                    page=None,
                    rows=_table_rows(content_lines),
                    anchors=anchors,
                )
            )
        block = []

    for line_number, line in enumerate(lines, start=1):
        stripped = line.strip()
        if stripped.startswith("```"):
            block.append((line_number, line.rstrip()))
            in_code_block = not in_code_block
            if not in_code_block:
                flush_block()
            continue

        if in_code_block:
            block.append((line_number, line.rstrip()))
            continue

        heading_match = HEADING_RE.match(stripped)
        if heading_match:
            flush_block()
            section_index += 1
            level = len(heading_match.group(1))
            title = normalize_text(heading_match.group(2))
            section_id = f"sec-{section_index}"
            parent_id = _parent_id(section_stack, level)
            sections.append(Section(section_id=section_id, title=title, level=level, parent_id=parent_id))
            section_stack = {key: value for key, value in section_stack.items() if key < level}
            section_stack[level] = section_id
            current_section_id = section_id
            current_heading_path = [section.title for section in sections if section.section_id in section_stack.values()]
            continue

        if not stripped:
            flush_block()
            continue

        block.append((line_number, line.rstrip()))

    flush_block()

    title = sections[0].title if sections else file_path.stem
    meta = DocumentMeta(
        document_id=manifest["document_id"],
        title=title,
        source_path=manifest["stored_path"],
        file_name=file_path.name,
        source_type="md",
        doc_type=detect_doc_type(title, file_path.name),
        checksum=manifest.get("checksum", ""),
        metadata={"manifest_path": manifest.get("manifest_path", ""), "line_count": len(lines)},
    )

    return CanonicalDocument(
        document=meta,
        sections=sections,
        fragments=fragments,
        tables=tables,
        figures=[],
        terms=extract_terms([fragment.text for fragment in fragments]),
        entities=[],
        parse_status="parsed" if fragments else "failed",
        source_anchors=[{"fragment_id": fragment.fragment_id, "anchors": fragment.anchors} for fragment in fragments],
        errors=[] if fragments else ["No text fragments extracted from Markdown."],
    )


def _parent_id(section_stack: dict[int, str], level: int) -> str | None:
    for parent_level in range(level - 1, 0, -1):
        if parent_level in section_stack:
            return section_stack[parent_level]
    return None


def _fragment_type(lines: list[str]) -> str:
    stripped = [line.strip() for line in lines if line.strip()]
    if not stripped:
        return "paragraph"
    if stripped[0].startswith("```"):
        return "code"
    if all(line.startswith("|") and line.endswith("|") for line in stripped):
        return "table"
    if all(LIST_RE.match(line) for line in stripped):
        return "list"
    return "paragraph"


def _fragment_text(lines: list[str]) -> str:
    if lines and lines[0].strip().startswith("```"):
        return "\n".join(line.rstrip() for line in lines).strip()
    return normalize_text(" ".join(line.strip() for line in lines if line.strip()))


def _table_rows(lines: list[str]) -> list[list[str]]:
    rows: list[list[str]] = []
    for line in lines:
        stripped = line.strip()
        if not stripped.startswith("|") or not stripped.endswith("|"):
            continue
        cells = [normalize_text(cell) for cell in stripped.strip("|").split("|")]
        rows.append(cells)
    return rows