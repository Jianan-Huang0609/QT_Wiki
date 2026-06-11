from __future__ import annotations

import re
from dataclasses import dataclass

from Tool.normalizers import normalize_text

CHINESE_NUMERAL = r"[一二三四五六七八九十百零〇\d]+"
CHAPTER_RE = re.compile(rf"^(第{CHINESE_NUMERAL}章)\s*(.*?)(?=\s*第{CHINESE_NUMERAL}条|$)")
ARTICLE_RE = re.compile(rf"^(第{CHINESE_NUMERAL}条)\s*(.*)")
PEP_STAGE_RE = re.compile(r"^(R\d+(?:\.\d+)*)\s*[:：.\-]?\s*(.{0,100})$", re.IGNORECASE)
LETTERED_NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+)+)\s*([A-Za-z])[)）]\s*(.{1,100})$")
NUMBERED_HEADING_RE = re.compile(r"^(\d+(?:\.\d+){0,5})(?:[.、)]|\s+)\s*(.{2,100})$")
COMPACT_DECIMAL_HEADING_RE = re.compile(r"^(\d+\.\d+(?:\.\d+){0,4})\s*([^\d\s].{1,100})$")
BODY_SENTENCE_MARKERS = ("应当", "必须", "负责", "包括", "如下", "下列", "至少", "记录", "程序")
DOCUMENT_CONTROL_RE = re.compile(r"^\d[\d\s\-]{4,}\s*\-?\s*AND\s*\-?\s*[A-Z0-9]", re.IGNORECASE)
PAGE_OF_RE = re.compile(r"\bpage\s+\d+\s+of\s+\d+\b", re.IGNORECASE)
TOC_DOT_LEADER_RE = re.compile(r"\.{3,}\s*\d{1,4}$")


@dataclass(frozen=True, slots=True)
class DetectedHeading:
    title: str
    level: int
    kind: str


def detect_heading(text: str, *, style_level: int | None = None) -> DetectedHeading | None:
    normalized = normalize_text(text)
    if not normalized:
        return None

    if looks_like_structural_noise_heading(normalized):
        return None

    if style_level is not None:
        title = _trim_heading_title(normalized)
        if title:
            return DetectedHeading(title=title, level=style_level, kind="style")

    match = CHAPTER_RE.match(normalized)
    if match:
        title = _join_title(match.group(1), match.group(2))
        return DetectedHeading(title=title, level=1, kind="chapter")

    match = ARTICLE_RE.match(normalized)
    if match:
        title = _join_title(match.group(1), _trim_body_tail(match.group(2)))
        return DetectedHeading(title=title, level=2, kind="article")

    match = PEP_STAGE_RE.match(normalized)
    if match and _looks_like_pep_stage_heading(match.group(1), match.group(2)):
        code = match.group(1).upper()
        suffix = _trim_heading_title(match.group(2))
        title = _join_title(code, suffix)
        level = min(code.count(".") + 1, 6)
        return DetectedHeading(title=title, level=level, kind="pep_stage")

    match = LETTERED_NUMBERED_HEADING_RE.match(normalized)
    if match and _looks_like_numbered_heading(match.group(3)):
        base = match.group(1)
        letter = match.group(2).lower()
        title = _join_title(f"{base}.{letter}", _trim_heading_title(match.group(3)))
        level = min(base.count(".") + 2, 6)
        return DetectedHeading(title=title, level=level, kind="numbered_letter")

    match = COMPACT_DECIMAL_HEADING_RE.match(normalized)
    if match and _looks_like_numbered_heading(match.group(2)):
        number = match.group(1)
        title = _join_title(number, _trim_heading_title(match.group(2)))
        level = min(number.count(".") + 1, 6)
        return DetectedHeading(title=title, level=level, kind="numbered_compact")

    match = NUMBERED_HEADING_RE.match(normalized)
    if match and _looks_like_numbered_heading(match.group(2)):
        number = match.group(1)
        title = _join_title(number, _trim_heading_title(match.group(2)))
        level = min(number.count(".") + 1, 6)
        return DetectedHeading(title=title, level=level, kind="numbered")

    return None


def _join_title(prefix: str, suffix: str) -> str:
    suffix = normalize_text(suffix)
    if not suffix:
        return prefix
    if prefix.endswith(("章", "条")) and re.match(r"^[\u4e00-\u9fffA-Za-z0-9]", suffix):
        return f"{prefix} {suffix}"
    return f"{prefix} {suffix}"


def _trim_heading_title(text: str, *, limit: int = 100) -> str:
    title = normalize_text(text)
    title = re.sub(r"[：:；;。]+$", "", title).strip()
    return title[:limit].strip()


def _trim_body_tail(text: str, *, limit: int = 80) -> str:
    normalized = normalize_text(text)
    if not normalized:
        return ""
    for delimiter in ("。", "；", ";", ":", "："):
        if delimiter in normalized:
            normalized = normalized.split(delimiter, 1)[0]
            break
    return _trim_heading_title(normalized, limit=limit)


def _looks_like_pep_stage_heading(code: str, suffix: str) -> bool:
    suffix = normalize_text(suffix)
    if not suffix:
        return True
    if len(suffix) > 80:
        return False
    if suffix.endswith(("。", "；", ";")):
        return False
    return not _looks_like_body_sentence(suffix)


def _looks_like_numbered_heading(title: str) -> bool:
    normalized = normalize_text(title)
    if len(normalized) > 80:
        return False
    if normalized.endswith(("。", "；", ";")):
        return False
    return not _looks_like_body_sentence(normalized)


def _looks_like_body_sentence(text: str) -> bool:
    return any(marker in text for marker in BODY_SENTENCE_MARKERS) and len(text) > 24


def looks_like_structural_noise_heading(text: str) -> bool:
    normalized = normalize_text(text)
    return looks_like_document_control_line(normalized) or looks_like_toc_dot_leader_line(normalized)


def looks_like_document_control_line(text: str) -> bool:
    normalized = normalize_text(text)
    if not normalized:
        return False
    return bool(DOCUMENT_CONTROL_RE.match(normalized)) or (bool(PAGE_OF_RE.search(normalized)) and "AND" in normalized.upper())


def looks_like_toc_dot_leader_line(text: str) -> bool:
    return bool(TOC_DOT_LEADER_RE.search(normalize_text(text)))