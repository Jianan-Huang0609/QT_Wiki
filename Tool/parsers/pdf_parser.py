from __future__ import annotations

import re
from pathlib import Path

import pypdf

from Tool.contracts.canonical import CanonicalDocument, DocumentMeta, FigureData, Fragment, Section, TableData
from Tool.normalizers import chunk_lines, detect_doc_type, extract_terms, normalize_text
from Tool.parsers.structure import (
    DetectedHeading,
    detect_heading,
    looks_like_document_control_line,
    looks_like_structural_noise_heading,
    looks_like_toc_dot_leader_line,
)

SECTION_RE = re.compile(r"^第[一二三四五六七八九十百零〇\d]+章")
ARTICLE_RE = re.compile(r"^第[一二三四五六七八九十百零〇\d]+条")
DATE_RE = re.compile(r"^\d{4}/\d{1,2}/\d{1,2}$")
PAGE_NO_RE = re.compile(r"^\d{1,3}$")
BULLET_RE = re.compile(r"^(?:[•⚫➢■▪◆\-]|[①②③④⑤⑥⑦⑧⑨⑩]|[（(]?[一二三四五六七八九十\d]+[）).、])")
TITLE_MARKER_RE = re.compile(r"^(?:[•⚫➢■▪◆\-—–]+|[①②③④⑤⑥⑦⑧⑨⑩]+|[（(]?[一二三四五六七八九十\d]+[）).、])\s*")
SLIDE_NUMBER_PREFIX_RE = re.compile(r"^\d+(?:\.\d+){0,3}\s+")
TRAILING_TITLE_PUNCT_RE = re.compile(r"[：:？?！!；;。]+$")
ENGLISH_PAREN_SUFFIX_RE = re.compile(r"\s*[（(][A-Za-z][A-Za-z0-9/_\- ]*[）)]$")
SLIDE_MARKERS = ("分享人", "教师简介", "目录", "理解要点", "本章要点", "框架结构", "章节条款数对比")
STRUCTURAL_SLIDE_MARKERS = ("分享人", "教师简介", "目录", "框架结构", "章节条款数对比")
TITLE_NOISE_LINES = {"理解要点", "本章要点", "目", "录"}
SENTENCE_TITLE_MARKERS = ("应当", "必须", "包括", "如下", "下列", "至少", "记录", "程序", "要求")
GENERIC_SLIDE_TITLES = {"总则", "附则", "概述", "说明", "原则"}
TITLE_NOISE_MARKERS = ("下面引自", "本资料仅限于", "请勿传播", "理解和实施")
THEMATIC_TITLE_MARKERS = (
    "QMS",
    "质量",
    "风险",
    "文件",
    "设备",
    "放行",
    "采购",
    "验证",
    "设计",
    "历程",
    "修订",
    "特点",
    "关系",
    "管理",
    "控制",
    "编写",
    "保证",
    "过程",
    "标准",
    "法规",
    "体系",
    "规范",
)
HISTORY_TABLE_HEADER_RE = re.compile(r"^Nr\.\s+Page\s+Version\s+Change description\s+CR No\.?$", re.IGNORECASE)
HISTORY_TABLE_ROW_RE = re.compile(r"^(\d+)\s+(All|\d+(?:-\d+)?)\s+(\d{2})\s+(.+)$", re.IGNORECASE)
HISTORY_CONTINUATION_ROW_RE = re.compile(r"^\d+[.)]\s+(Chapter|Appendix)\b", re.IGNORECASE)
POST_HISTORY_HEADING_RE = re.compile(r"^\d+\s+(Purpose|Reference document|Abbreviations|Procedure|Process|Document)\b", re.IGNORECASE)
FIGURE_CAPTION_RE = re.compile(r"^(?:Fig\.?|Figure)\s*\d+\s*(?:/\s*图\s*\d+)?\s*[:：].+|^图\s*\d+\s*[:：].+", re.IGNORECASE)
TOC_MARKERS = {"Content", "Contents", "Table of contents", "目录"}
TRAILING_PAGE_NUMBER_RE = re.compile(r"^(?P<title>.+?)\s+\d{1,4}$")


def parse_pdf(file_path: Path, manifest: dict) -> CanonicalDocument:
    reader = pypdf.PdfReader(str(file_path))
    extracted_pages: list[tuple[int, str]] = []
    errors: list[str] = []

    for page_number, page in enumerate(reader.pages, start=1):
        try:
            extracted_pages.append((page_number, page.extract_text() or ""))
        except Exception as exc:
            errors.append(f"page {page_number}: {exc}")

    if _looks_like_slide_pdf(extracted_pages, title_hint=manifest.get("title", file_path.stem), file_name=file_path.name):
        return _parse_slide_pdf(
            file_path=file_path,
            manifest=manifest,
            extracted_pages=extracted_pages,
            page_count=len(reader.pages),
            errors=errors,
        )

    sections: list[Section] = []
    fragments: list[Fragment] = []
    tables: list[TableData] = []
    figures: list[FigureData] = []
    current_section_id: str | None = None
    section_stack: list[Section] = []
    fragment_index = 0

    repeated_noise = _repeated_pdf_noise_lines(extracted_pages)
    for page_number, text in extracted_pages:
        page_lines = [normalize_text(line) for line in text.splitlines()]
        page_lines = [line for line in page_lines if line]
        tables.extend(_extract_history_tables(page_lines, page_number=page_number, table_offset=len(tables)))
        figures.extend(_extract_figure_candidates(page_lines, page_number=page_number, figure_offset=len(figures)))
        prepared_lines = _prepare_text_page_lines(text, repeated_noise=repeated_noise, page_number=page_number)
        for paragraph_index, chunk in enumerate(_chunk_text_page_lines(prepared_lines), start=1):
            if not chunk:
                continue
            heading = detect_heading(chunk)
            if heading:
                current_section_id = _append_section(sections, section_stack, heading, page_number)

            if current_section_id:
                _touch_section_page(sections, current_section_id, page_number)

            fragment_index += 1
            fragments.append(
                Fragment(
                    fragment_id=f"frag-{fragment_index}",
                    section_id=current_section_id,
                    fragment_type="paragraph",
                    text=normalize_text(chunk),
                    anchors={
                        "page": page_number,
                        "paragraph_index": paragraph_index,
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
        source_type="pdf",
        doc_type=detect_doc_type(title, file_path.name),
        checksum=manifest.get("checksum", ""),
        metadata={"manifest_path": manifest.get("manifest_path", ""), "page_count": len(reader.pages)},
    )

    parse_status = "parsed" if fragments and not errors else "partially_parsed" if fragments else "failed"
    if not fragments and not errors:
        errors.append("No text fragments extracted from PDF.")

    return CanonicalDocument(
        document=meta,
        sections=sections,
        fragments=fragments,
        tables=tables,
        figures=figures,
        terms=extract_terms([fragment.text for fragment in fragments]),
        entities=[],
        parse_status=parse_status,
        source_anchors=[
            {"fragment_id": fragment.fragment_id, "anchors": fragment.anchors}
            for fragment in fragments
        ] + [
            {"table_id": table.table_id, "anchors": table.anchors}
            for table in tables
        ] + [
            {"figure_id": figure.figure_id, "anchors": figure.anchors}
            for figure in figures
        ],
        errors=errors,
    )


def _parse_slide_pdf(
    *,
    file_path: Path,
    manifest: dict,
    extracted_pages: list[tuple[int, str]],
    page_count: int,
    errors: list[str],
) -> CanonicalDocument:
    sections: list[Section] = []
    fragments: list[Fragment] = []
    skipped_pages: list[int] = []

    for page_number, text in extracted_pages:
        lines = _prepare_slide_lines(text)
        if not lines:
            continue
        if _is_structural_slide(lines):
            skipped_pages.append(page_number)
            continue

        title, title_source = _pick_slide_page_title(lines, fallback=f"第{page_number}页")
        body_lines = _drop_first_occurrence(lines, title_source)
        merged_lines = _merge_slide_lines(body_lines)
        if not merged_lines:
            skipped_pages.append(page_number)
            continue

        section_id = f"slide-{page_number}"
        sections.append(
            Section(
                section_id=section_id,
                title=title,
                level=1,
                page_range=[page_number, page_number],
            )
        )
        for paragraph_index, chunk in enumerate(merged_lines, start=1):
            fragments.append(
                Fragment(
                    fragment_id=f"frag-{page_number}-{paragraph_index}",
                    section_id=section_id,
                    fragment_type="paragraph",
                    text=chunk,
                    anchors={"page": page_number, "paragraph_index": paragraph_index},
                )
            )

    title = _pick_slide_document_title(sections, fragments, fallback=file_path.stem)
    meta = DocumentMeta(
        document_id=manifest["document_id"],
        title=title,
        source_path=manifest["stored_path"],
        file_name=file_path.name,
        source_type="pdf",
        doc_type="presentation",
        checksum=manifest.get("checksum", ""),
        metadata={
            "manifest_path": manifest.get("manifest_path", ""),
            "page_count": page_count,
            "pdf_layout": "slides",
            "skipped_pages": skipped_pages,
        },
    )

    parse_status = "parsed" if fragments and not errors else "partially_parsed" if fragments else "failed"
    if not fragments and not errors:
        errors.append("No text fragments extracted from slide-like PDF.")

    return CanonicalDocument(
        document=meta,
        sections=sections,
        fragments=fragments,
        tables=[],
        figures=[],
        terms=extract_terms([fragment.text for fragment in fragments]),
        entities=[],
        parse_status=parse_status,
        source_anchors=[
            {"fragment_id": fragment.fragment_id, "anchors": fragment.anchors}
            for fragment in fragments
        ],
        errors=errors,
    )


def _looks_like_slide_pdf(extracted_pages: list[tuple[int, str]], *, title_hint: str, file_name: str) -> bool:
    if not extracted_pages:
        return False

    sample_pages = extracted_pages[: min(12, len(extracted_pages))]
    marker_pages = 0
    short_line_pages = 0
    article_pages = 0

    for _, text in sample_pages:
        lines = _prepare_slide_lines(text)
        if not lines:
            continue
        if any(marker in " ".join(lines[:10]) for marker in SLIDE_MARKERS):
            marker_pages += 1
        if len(lines) >= 6:
            short_ratio = sum(1 for line in lines if len(line) <= 30) / len(lines)
            if short_ratio >= 0.6:
                short_line_pages += 1
        if sum(1 for line in lines if ARTICLE_RE.match(line)) >= 2:
            article_pages += 1

    title_source = f"{title_hint} {file_name}"
    title_bias = any(keyword in title_source for keyword in ("理解和实施", "培训", "讲义", "课件"))
    return (
        marker_pages >= 2 and short_line_pages >= 2 and article_pages <= max(2, len(sample_pages) // 4)
    ) or (
        title_bias and marker_pages >= 1 and short_line_pages >= 1
    )


def _prepare_slide_lines(text: str) -> list[str]:
    lines = [normalize_text(line) for line in text.splitlines()]
    lines = [line for line in lines if line]
    if lines and DATE_RE.match(lines[0]):
        lines = lines[1:]
    if lines and PAGE_NO_RE.match(lines[0]):
        lines = lines[1:]
    return [line for line in lines if not PAGE_NO_RE.match(line)]


def _prepare_text_page_lines(text: str, *, repeated_noise: set[str], page_number: int) -> list[str]:
    lines = [normalize_text(line) for line in text.splitlines()]
    lines = _join_split_heading_lines(lines)
    if _looks_like_toc_page(lines, page_number=page_number):
        return []
    history_noise_indexes = _history_table_noise_line_indexes(lines)
    history_noise_indexes.update(_history_continuation_noise_line_indexes(lines))
    return [
        line
        for index, line in enumerate(lines)
        if line and index not in history_noise_indexes and not _is_pdf_text_noise_line(line, repeated_noise=repeated_noise)
    ]


def _chunk_text_page_lines(lines: list[str], *, max_chunk_chars: int = 220) -> list[str]:
    chunks: list[str] = []
    bucket: list[str] = []

    def flush_bucket() -> None:
        if bucket:
            chunks.append(" ".join(bucket))
            bucket.clear()

    for line in lines:
        for piece in chunk_lines(line, max_chunk_chars=max_chunk_chars):
            if detect_heading(piece):
                flush_bucket()
                chunks.append(piece)
                continue

            next_length = len(" ".join(bucket + [piece]))
            if bucket and (_ends_sentence(bucket[-1]) or next_length > max_chunk_chars):
                flush_bucket()
            bucket.append(piece)

    flush_bucket()
    return chunks


def _repeated_pdf_noise_lines(extracted_pages: list[tuple[int, str]]) -> set[str]:
    counts: dict[str, int] = {}
    for _, text in extracted_pages:
        seen_on_page: set[str] = set()
        for raw_line in text.splitlines():
            line = normalize_text(raw_line)
            if not line or len(line) > 80 or looks_like_structural_noise_heading(line) or detect_heading(line):
                continue
            seen_on_page.add(line)
        for line in seen_on_page:
            counts[line] = counts.get(line, 0) + 1
    return {line for line, count in counts.items() if count >= 2}


def _is_pdf_text_noise_line(line: str, *, repeated_noise: set[str]) -> bool:
    if DATE_RE.match(line) or PAGE_NO_RE.match(line):
        return True
    return line in repeated_noise or looks_like_structural_noise_heading(line)


def _join_split_heading_lines(lines: list[str]) -> list[str]:
    joined_lines: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index]
        next_line = lines[index + 1] if index + 1 < len(lines) else ""
        if line and next_line and _heading_needs_short_continuation(line, next_line):
            joined_lines.append(_merge_heading_continuation(line, next_line))
            index += 2
            continue
        joined_lines.append(line)
        index += 1
    return joined_lines


def _heading_needs_short_continuation(line: str, next_line: str) -> bool:
    if detect_heading(line) is None:
        return False
    has_open_bracket = line.count("（") > line.count("）") or line.count("(") > line.count(")")
    if not has_open_bracket:
        return False
    return _looks_like_short_heading_continuation(next_line)


def _looks_like_short_heading_continuation(line: str) -> bool:
    normalized = normalize_text(line)
    if not normalized or len(normalized) > 30:
        return False
    return bool(re.match(r"^[\w\u4e00-\u9fff\s/\-]+[）)]$", normalized))


def _merge_heading_continuation(line: str, next_line: str) -> str:
    left = normalize_text(line).rstrip()
    right = normalize_text(next_line).lstrip()
    separator = ""
    if not re.search(r"[\u4e00-\u9fff（(]$", left) or not re.match(r"^[\u4e00-\u9fff]", right):
        separator = " "
    merged = f"{left}{separator}{right}"
    merged = re.sub(r"([（(])\s+", r"\1", merged)
    merged = re.sub(r"\s+([）)])", r"\1", merged)
    merged = re.sub(r"(?<=[\u4e00-\u9fff])\s+(?=[\u4e00-\u9fff])", "", merged)
    return merged


def _looks_like_toc_page(lines: list[str], *, page_number: int) -> bool:
    if page_number > 10:
        return False

    useful_lines = [line for line in lines if line and not _looks_like_pdf_control_line(line)]
    if not useful_lines:
        return False

    marker_seen = any(line in TOC_MARKERS for line in useful_lines[:8])
    dot_leader_count = sum(1 for line in useful_lines if looks_like_toc_dot_leader_line(line))
    trailing_page_entry_count = sum(1 for line in useful_lines if _looks_like_toc_page_number_entry(line))

    if marker_seen and trailing_page_entry_count:
        return True
    if dot_leader_count >= 2:
        return True
    return False


def _looks_like_pdf_control_line(line: str) -> bool:
    normalized = normalize_text(line)
    if not normalized:
        return True
    return DATE_RE.match(normalized) is not None or PAGE_NO_RE.match(normalized) is not None or looks_like_document_control_line(normalized)


def _looks_like_toc_page_number_entry(line: str) -> bool:
    normalized = normalize_text(line)
    if looks_like_toc_dot_leader_line(normalized):
        return True
    match = TRAILING_PAGE_NUMBER_RE.match(normalized)
    if not match:
        return False
    return detect_heading(match.group("title")) is not None


def _extract_history_tables(lines: list[str], *, page_number: int, table_offset: int) -> list[TableData]:
    header_index = next((index for index, line in enumerate(lines) if HISTORY_TABLE_HEADER_RE.match(line)), None)
    if header_index is None:
        return []

    rows = [["Nr", "Page", "Version", "Change description", "CR No."]]
    current_row: list[str] | None = None

    for line in lines[header_index + 1:]:
        if POST_HISTORY_HEADING_RE.match(line):
            break
        row_match = HISTORY_TABLE_ROW_RE.match(line)
        if row_match:
            if current_row:
                rows.append(current_row)
            current_row = [row_match.group(1), row_match.group(2), row_match.group(3), row_match.group(4).strip(), ""]
            continue
        if current_row and line:
            if line.upper() in {"N.A.", "NA"} or re.match(r"^P\d+", line, re.IGNORECASE):
                current_row[4] = line if not current_row[4] else f"{current_row[4]} {line}"
            else:
                current_row[3] = f"{current_row[3]} {line}".strip()

    if current_row:
        rows.append(current_row)
    if len(rows) == 1:
        return []

    return [
        TableData(
            table_id=f"tbl-{table_offset + 1}",
            section_id=None,
            page=page_number,
            rows=rows,
            anchors={"page": page_number, "table_type": "document_history", "line_start": header_index + 1},
        )
    ]


def _extract_figure_candidates(lines: list[str], *, page_number: int, figure_offset: int) -> list[FigureData]:
    figures: list[FigureData] = []
    for line in lines:
        if FIGURE_CAPTION_RE.match(line):
            figures.append(
                FigureData(
                    figure_id=f"fig-{figure_offset + len(figures) + 1}",
                    section_id=None,
                    page=page_number,
                    caption=line,
                    anchors={"page": page_number, "caption": line, "source": "pdf_text_caption"},
                )
            )
    return figures


def _history_table_noise_line_indexes(lines: list[str]) -> set[int]:
    header_index = next((index for index, line in enumerate(lines) if HISTORY_TABLE_HEADER_RE.match(line)), None)
    first_row_index = next((index for index, line in enumerate(lines) if HISTORY_TABLE_ROW_RE.match(line)), None)
    start_index = header_index if header_index is not None else first_row_index
    if start_index is None:
        return set()

    noise_indexes: set[int] = set()
    for index in range(start_index, len(lines)):
        line = lines[index]
        if index > start_index and POST_HISTORY_HEADING_RE.match(line):
            break
        noise_indexes.add(index)
    return noise_indexes


def _history_continuation_noise_line_indexes(lines: list[str]) -> set[int]:
    noise_indexes: set[int] = set()
    for index, line in enumerate(lines):
        if POST_HISTORY_HEADING_RE.match(line):
            break
        if HISTORY_CONTINUATION_ROW_RE.match(line):
            noise_indexes.add(index)
    return noise_indexes


def _append_section(
    sections: list[Section],
    section_stack: list[Section],
    heading: DetectedHeading,
    page_number: int,
) -> str:
    while section_stack and section_stack[-1].level >= heading.level:
        section_stack.pop()

    parent_id = section_stack[-1].section_id if section_stack else None
    section = Section(
        section_id=f"sec-{len(sections) + 1}",
        title=heading.title,
        level=heading.level,
        page_range=[page_number],
        parent_id=parent_id,
    )
    sections.append(section)
    section_stack.append(section)
    return section.section_id


def _touch_section_page(sections: list[Section], section_id: str, page_number: int) -> None:
    for section in sections:
        if section.section_id == section_id and page_number not in section.page_range:
            section.page_range.append(page_number)
            return


def _is_structural_slide(lines: list[str]) -> bool:
    preview = " ".join(lines[:12])
    return any(marker in preview for marker in STRUCTURAL_SLIDE_MARKERS)


def _pick_slide_page_title(lines: list[str], *, fallback: str) -> tuple[str, str]:
    candidates = [line for line in lines[:12] if line]
    if not candidates:
        return fallback, fallback

    scored_candidates: list[tuple[int, int, str, str]] = []
    for index, raw_line in enumerate(candidates):
        cleaned_line = _normalize_slide_title_candidate(raw_line)
        score = _slide_title_score(raw_line, cleaned_line, index=index)
        scored_candidates.append((score, -index, cleaned_line, raw_line))

    best_score, _, cleaned_line, raw_line = max(scored_candidates)
    if best_score > 0 and cleaned_line:
        return cleaned_line, raw_line
    return fallback, fallback


def _normalize_slide_title_candidate(line: str) -> str:
    cleaned = TITLE_MARKER_RE.sub("", line).strip()
    cleaned = SLIDE_NUMBER_PREFIX_RE.sub("", cleaned).strip()
    cleaned = ENGLISH_PAREN_SUFFIX_RE.sub("", cleaned).strip()
    cleaned = TRAILING_TITLE_PUNCT_RE.sub("", cleaned).strip()
    cleaned = re.sub(r"\s+", " ", cleaned)
    return cleaned


def _slide_title_score(raw_line: str, cleaned_line: str, *, index: int) -> int:
    if not cleaned_line or cleaned_line in TITLE_NOISE_LINES:
        return -10

    score = 0
    if 4 <= len(cleaned_line) <= 28:
        score += 5
    elif len(cleaned_line) <= 45:
        score += 3
    elif len(cleaned_line) <= 60:
        score += 1
    else:
        score -= 2

    score += max(0, 5 - index)

    if raw_line != cleaned_line and len(cleaned_line) <= 24:
        score += 1
    if TITLE_MARKER_RE.match(raw_line):
        score -= 1
    if raw_line.startswith(("—", "——", "–")):
        score -= 2
    if re.match(r"^[A-Za-z][).、]\s*", raw_line):
        score -= 5
    if any(marker in cleaned_line for marker in TITLE_NOISE_MARKERS):
        score -= 6
    if ARTICLE_RE.match(cleaned_line) or SECTION_RE.match(cleaned_line):
        score += 2
    if re.match(r"^\d+(?:\.\d+)*[.、]?", raw_line):
        score += 2
    if cleaned_line.startswith(tuple(str(year) for year in range(1990, 2036))):
        score -= 3
    if any(marker in cleaned_line for marker in SENTENCE_TITLE_MARKERS):
        score -= 3
    if cleaned_line in GENERIC_SLIDE_TITLES:
        score -= 4
    if re.match(r"^(新版|最新)[“\"《]?(规范|制度|标准)[”\"》]?$", cleaned_line):
        score -= 4
    if any(keyword in cleaned_line for keyword in THEMATIC_TITLE_MARKERS):
        score += 2
    if "发展历程" in cleaned_line:
        score += 4
    if re.search(r"(历程|特点|编写|管理|控制|保证|关系|要求|确认)$", cleaned_line):
        score += 2
    return score


def _drop_first_occurrence(lines: list[str], target: str) -> list[str]:
    dropped = False
    result: list[str] = []
    for line in lines:
        if not dropped and line == target:
            dropped = True
            continue
        result.append(line)
    return result


def _merge_slide_lines(lines: list[str], *, max_chunk_chars: int = 260) -> list[str]:
    chunks: list[str] = []
    bucket: list[str] = []

    for line in lines:
        if _is_slide_noise_line(line):
            if bucket:
                chunks.append(" ".join(bucket))
                bucket = []
            continue

        starts_new = bool(bucket) and (
            BULLET_RE.match(line)
            or ARTICLE_RE.match(line)
            or SECTION_RE.match(line)
        )
        next_length = len(" ".join(bucket + [line]))
        if starts_new or (bucket and (_ends_sentence(bucket[-1]) or next_length > max_chunk_chars)):
            chunks.append(" ".join(bucket))
            bucket = [line]
            continue
        bucket.append(line)

    if bucket:
        chunks.append(" ".join(bucket))
    return [chunk for chunk in chunks if len(chunk) >= 8]


def _is_slide_noise_line(line: str) -> bool:
    if not line:
        return True
    if line in {"理解要点", "本章要点", "目", "录", "——", "……"}:
        return True
    return False


def _ends_sentence(text: str) -> bool:
    return text.endswith(("。", "；", "？", "！", ".", ";", ":", "："))


def _pick_slide_document_title(sections: list[Section], fragments: list[Fragment], *, fallback: str) -> str:
    if sections:
        first_title = sections[0].title
        if 6 <= len(first_title) <= 60:
            return first_title
    return _pick_title(fragments, fallback)


def _pick_title(fragments: list[Fragment], fallback: str) -> str:
    for fragment in fragments[:12]:
        text = fragment.text
        if (
            text
            and len(text) >= 6
            and len(text) <= 40
            and not re.match(r"^\d{4}/\d{1,2}/\d{1,2}$", text)
            and not re.match(r"^\d{4}/\d{1,2}/\d{1,2}\s+\d+\s+", text)
            and "分享人" not in text
            and "目录" not in text
            and "本章要点" not in text
            and "章节条款数对比" not in text
            and "变化率" not in text
        ):
            return text
    return fallback
