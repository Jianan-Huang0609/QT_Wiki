from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field
from typing import Any

from Tool.chunking.section_chunks import normalize_search_text
from Tool.retrieval.section_index import RetrievalHit, RetrievalResult

TERM_KEYS = ("stage", "milestone", "role", "deliverable", "bu", "section")
ROLE_ALIASES = (
    (re.compile(r"(?<![a-z0-9])po(?![a-z0-9])", re.IGNORECASE), "Product Owner"),
    (re.compile(r"\bproduct\s+owner\b", re.IGNORECASE), "Product Owner"),
    (re.compile(r"(?<![a-z0-9])pm(?![a-z0-9])", re.IGNORECASE), "Project Manager"),
    (re.compile(r"\bproject\s+manager\b", re.IGNORECASE), "Project Manager"),
    (re.compile(r"\bregulatory\s+affairs?\b", re.IGNORECASE), "Regulatory Affairs"),
)
DELIVERABLE_ALIASES = {
    "QMP": "QMP",
    "PMP": "PMP",
    "DHF": "DHF",
    "DMR": "DMR",
}
BU_ALIASES = {"CT": "CT", "MI": "MI", "XP": "XP"}
SIGNAL_TERMS = {
    "role_po": ("role", "Product Owner"),
    "role_product_owner": ("role", "Product Owner"),
    "role_project_manager": ("role", "Project Manager"),
    "role_regulatory_affairs": ("role", "Regulatory Affairs"),
    "deliverable_qmp": ("deliverable", "QMP"),
    "deliverable_pmp": ("deliverable", "PMP"),
    "deliverable_dhf": ("deliverable", "DHF"),
    "deliverable_dmr": ("deliverable", "DMR"),
    "bu_ct": ("bu", "CT"),
    "bu_mi": ("bu", "MI"),
    "bu_xp": ("bu", "XP"),
}


@dataclass(slots=True)
class QuestionIntent:
    intent_type: str
    question_terms: list[str]
    normalized_terms: dict[str, list[str]]
    source_scope_hint: str
    answer_shape: str
    reference_density: str
    risk_level: str
    requires_abstention_check: bool

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class EvidenceItem:
    evidence_id: str
    document_id: str
    file_name: str
    section_id: str | None
    section_title: str
    section_path: list[str]
    anchor_label: str
    quote: str
    source_refs: list[dict[str, Any]]
    score: float
    matched_terms: list[str]
    signals: list[str]
    supports: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class AnswerEvidencePackage:
    question: str
    intent: dict[str, Any]
    source_scope: dict[str, Any]
    strategy_used: str
    evidence_items: list[EvidenceItem]
    coverage: dict[str, Any]
    missing_evidence: list[dict[str, Any]] = field(default_factory=list)
    trace: list[str] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "question": self.question,
            "intent": self.intent,
            "source_scope": self.source_scope,
            "strategy_used": self.strategy_used,
            "evidence_items": [item.to_dict() for item in self.evidence_items],
            "coverage": self.coverage,
            "missing_evidence": self.missing_evidence,
            "trace": self.trace,
        }


def parse_question_intent(question: str) -> QuestionIntent:
    normalized_terms = normalize_enterprise_terms(question)
    intent_type = _intent_type(question, normalized_terms)
    policy = _intent_policy(intent_type)
    return QuestionIntent(
        intent_type=intent_type,
        question_terms=_question_terms(normalized_terms),
        normalized_terms=normalized_terms,
        source_scope_hint=policy["source_scope_hint"],
        answer_shape=policy["answer_shape"],
        reference_density=policy["reference_density"],
        risk_level=policy["risk_level"],
        requires_abstention_check=bool(policy["requires_abstention_check"]),
    )


def normalize_enterprise_terms(question: str, *, chunk_signals: list[str] | None = None) -> dict[str, list[str]]:
    terms = _empty_terms()
    for stage in re.findall(r"(?<![A-Za-z0-9])R\d+(?:\.\d+)?(?![A-Za-z0-9])", question, flags=re.IGNORECASE):
        _add_term(terms, "stage", stage.upper())
    for milestone in re.findall(r"(?<![A-Za-z0-9])M\d+(?![A-Za-z0-9])", question, flags=re.IGNORECASE):
        _add_term(terms, "milestone", milestone.upper())
    for section in re.findall(r"(?<![A-Za-z0-9])\d+\.\d+(?:\.\d+)*(?![A-Za-z0-9])", question):
        _add_term(terms, "section", section)

    for pattern, canonical in ROLE_ALIASES:
        if pattern.search(question):
            _add_term(terms, "role", canonical)
    for alias, canonical in DELIVERABLE_ALIASES.items():
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", question, flags=re.IGNORECASE):
            _add_term(terms, "deliverable", canonical)
    for alias, canonical in BU_ALIASES.items():
        if re.search(rf"(?<![A-Za-z0-9]){re.escape(alias)}(?![A-Za-z0-9])", question, flags=re.IGNORECASE):
            _add_term(terms, "bu", canonical)

    for signal in chunk_signals or []:
        key_value = _term_from_signal(signal)
        if key_value:
            _add_term(terms, key_value[0], key_value[1])
    return terms


def build_answer_evidence_package(
    retrieval_result: RetrievalResult,
    *,
    intent: QuestionIntent | None = None,
) -> AnswerEvidencePackage:
    question_intent = intent or parse_question_intent(retrieval_result.question)
    evidence_items: list[EvidenceItem] = []
    skipped: list[dict[str, Any]] = []
    for hit in retrieval_result.hits:
        if _is_history_hit(hit):
            skipped.append({"chunk_id": hit.chunk.chunk_id, "reason": "document_history_not_primary_evidence"})
            continue
        if not hit.chunk.source_refs:
            skipped.append({"chunk_id": hit.chunk.chunk_id, "reason": "missing_source_refs"})
            continue
        evidence_items.append(_evidence_item(hit, len(evidence_items) + 1, question_intent.normalized_terms))

    missing_evidence = _missing_evidence(question_intent, evidence_items)
    if not evidence_items:
        missing_evidence.append(
            {
                "term_type": "primary_evidence",
                "terms": [],
                "reason": "no retrieval hit with source refs is available as primary evidence",
            }
        )
    coverage = _coverage(evidence_items, missing_evidence)
    return AnswerEvidencePackage(
        question=retrieval_result.question,
        intent=question_intent.to_dict(),
        source_scope=retrieval_result.source_scope,
        strategy_used=retrieval_result.strategy_used,
        evidence_items=evidence_items,
        coverage=coverage,
        missing_evidence=missing_evidence,
        trace=[*retrieval_result.trace, *_skip_trace(skipped), "answer evidence package built"],
    )


def _intent_type(question: str, normalized_terms: dict[str, list[str]]) -> str:
    text = question.casefold()
    if _has_any(text, ("差异", "比较", "对比", "difference", "compare")) and len(normalized_terms["bu"]) >= 2:
        return "bu_comparison"
    if _has_any(text, ("够不够", "缺什么", "缺口", "是否足够", "missing", "gap", "enough")):
        return "gap_check"
    if _has_any(text, ("哪个文件", "哪个章节", "哪一章", "来自哪里", "引用", "reference", "where")):
        return "reference_lookup"
    if normalized_terms["section"] and _has_any(text, ("在哪", "哪个", "where")):
        return "reference_lookup"
    if _has_any(text, ("是什么", "定义", "what is", "meaning", "stand for")):
        return "definition_lookup"
    if normalized_terms["stage"] and normalized_terms["role"] and _has_any(
        text,
        ("作为", "应该", "做什么", "准备", "负责", "职责", "should", "responsibility", "responsibilities"),
    ):
        return "role_action_guidance"
    if _has_any(text, ("流程", "如何操作", "怎么做", "步骤", "process", "procedure", "how")):
        return "process_explanation"
    return "process_explanation"


def _intent_policy(intent_type: str) -> dict[str, str | bool]:
    policies: dict[str, dict[str, str | bool]] = {
        "role_action_guidance": {
            "source_scope_hint": "selected_docs_or_all_sources",
            "answer_shape": "adaptive_guidance",
            "reference_density": "high",
            "risk_level": "process_compliance",
            "requires_abstention_check": True,
        },
        "process_explanation": {
            "source_scope_hint": "selected_docs_or_all_sources",
            "answer_shape": "process_steps",
            "reference_density": "medium_high",
            "risk_level": "process_compliance",
            "requires_abstention_check": True,
        },
        "reference_lookup": {
            "source_scope_hint": "selected_docs_or_all_sources",
            "answer_shape": "reference_list",
            "reference_density": "high",
            "risk_level": "source_trace",
            "requires_abstention_check": True,
        },
        "bu_comparison": {
            "source_scope_hint": "all_sources_or_selected_docs",
            "answer_shape": "bu_comparison_table",
            "reference_density": "high",
            "risk_level": "process_compliance",
            "requires_abstention_check": True,
        },
        "definition_lookup": {
            "source_scope_hint": "selected_docs_or_all_sources",
            "answer_shape": "short_definition",
            "reference_density": "medium",
            "risk_level": "term_definition",
            "requires_abstention_check": True,
        },
        "gap_check": {
            "source_scope_hint": "selected_docs_or_all_sources",
            "answer_shape": "evidence_gap_check",
            "reference_density": "high",
            "risk_level": "process_compliance",
            "requires_abstention_check": True,
        },
    }
    return policies[intent_type]


def _evidence_item(hit: RetrievalHit, index: int, normalized_terms: dict[str, list[str]]) -> EvidenceItem:
    first_ref = hit.chunk.source_refs[0]
    quote = str(first_ref.get("quote") or hit.chunk.quote).strip()
    return EvidenceItem(
        evidence_id=f"ev-{index}",
        document_id=hit.chunk.document_id,
        file_name=hit.chunk.file_name,
        section_id=hit.chunk.section_id,
        section_title=hit.chunk.section_title,
        section_path=list(hit.chunk.section_path),
        anchor_label=str(first_ref.get("anchor_label") or _anchor_label(hit.chunk.anchors)),
        quote=quote,
        source_refs=[dict(ref) for ref in hit.chunk.source_refs],
        score=hit.score,
        matched_terms=list(hit.matched_terms),
        signals=list(hit.chunk.signals),
        supports=_supports(hit, normalized_terms),
    )


def _supports(hit: RetrievalHit, normalized_terms: dict[str, list[str]]) -> list[str]:
    searchable = normalize_search_text(" ".join([hit.chunk.section_title, hit.chunk.text, hit.chunk.document_title, hit.chunk.file_name]))
    signal_terms = normalize_enterprise_terms("", chunk_signals=hit.chunk.signals)
    supports: list[str] = []
    for key in TERM_KEYS:
        if signal_terms.get(key):
            supports.append(key)
            continue
        if normalized_terms.get(key) and any(
            normalize_search_text(term) in searchable for term in normalized_terms[key]
        ):
            supports.append(key)
    return supports


def _missing_evidence(intent: QuestionIntent, evidence_items: list[EvidenceItem]) -> list[dict[str, Any]]:
    supported = {support for item in evidence_items for support in item.supports}
    missing: list[dict[str, Any]] = []
    for key in _required_term_keys(intent.intent_type):
        terms = intent.normalized_terms.get(key, [])
        if terms and key not in supported:
            missing.append(
                {
                    "term_type": key,
                    "terms": terms,
                    "reason": "no primary evidence supports normalized terms",
                }
            )
    return missing


def _required_term_keys(intent_type: str) -> tuple[str, ...]:
    if intent_type == "role_action_guidance":
        return ("stage", "role", "deliverable")
    if intent_type == "reference_lookup":
        return ("section", "stage", "deliverable")
    if intent_type == "bu_comparison":
        return ("bu", "stage", "role", "deliverable")
    if intent_type == "definition_lookup":
        return ("deliverable", "role", "stage")
    if intent_type == "gap_check":
        return TERM_KEYS
    return ("stage", "role", "deliverable", "milestone")


def _coverage(evidence_items: list[EvidenceItem], missing_evidence: list[dict[str, Any]]) -> dict[str, Any]:
    documents = sorted({item.document_id for item in evidence_items})
    sections = sorted({item.section_id for item in evidence_items if item.section_id})
    return {
        "documents": documents,
        "sections": sections,
        "evidence_count": len(evidence_items),
        "missing": missing_evidence,
    }


def _term_from_signal(signal: str) -> tuple[str, str] | None:
    normalized = signal.strip().casefold()
    if normalized in SIGNAL_TERMS:
        return SIGNAL_TERMS[normalized]
    if normalized.startswith("stage_r"):
        return "stage", normalized.removeprefix("stage_").upper()
    if normalized.startswith("milestone_m"):
        return "milestone", normalized.removeprefix("milestone_").upper()
    if normalized.startswith("bu_"):
        return "bu", normalized.removeprefix("bu_").upper()
    if normalized.startswith("deliverable_"):
        return "deliverable", normalized.removeprefix("deliverable_").upper()
    return None


def _empty_terms() -> dict[str, list[str]]:
    return {key: [] for key in TERM_KEYS}


def _add_term(terms: dict[str, list[str]], key: str, value: str) -> None:
    if value and value not in terms[key]:
        terms[key].append(value)


def _question_terms(normalized_terms: dict[str, list[str]]) -> list[str]:
    terms: list[str] = []
    for key in TERM_KEYS:
        for term in normalized_terms[key]:
            if term not in terms:
                terms.append(term)
    return terms


def _has_any(text: str, markers: tuple[str, ...]) -> bool:
    return any(marker.casefold() in text for marker in markers)


def _is_history_hit(hit: RetrievalHit) -> bool:
    return hit.chunk.chunk_type == "document_history" or "document_history" in hit.chunk.signals


def _anchor_label(anchors: dict[str, Any]) -> str:
    if "page" in anchors:
        return f"p.{anchors['page']}"
    pages = anchors.get("pages")
    if isinstance(pages, list) and pages:
        return f"p.{pages[0]}" if len(pages) == 1 else f"p.{pages[0]}-{pages[-1]}"
    if "line_start" in anchors and "line_end" in anchors:
        return f"L{anchors['line_start']}-L{anchors['line_end']}"
    return ""


def _skip_trace(skipped: list[dict[str, Any]]) -> list[str]:
    return [f"skipped {item['chunk_id']}: {item['reason']}" for item in skipped]