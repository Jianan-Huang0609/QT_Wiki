from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Any


@dataclass(frozen=True, slots=True)
class AnswerSlotDefinition:
    slot_id: str
    label: str
    required: bool
    terms: tuple[str, ...] = ()
    missing_reason: str = "缺少可支撑该回答槽位的证据。"

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["terms"] = list(self.terms)
        return payload


@dataclass(frozen=True, slots=True)
class RouteCatalogEntry:
    route_id: str
    summary: str
    query_terms: tuple[str, ...]
    evidence_needs: tuple[str, ...]
    answer_slots: tuple[AnswerSlotDefinition, ...]
    answer_shape: str
    rewrite_reason: str
    risk_level: str
    citation_policy: str
    excluded_terms: tuple[str, ...] = ()
    dynamic_term_keys: tuple[str, ...] = ()
    needs_overview_evidence: bool = False
    expands_retrieval: bool = False
    rerank_enabled: bool = False
    route_label: str = "证据检索问答"
    top_k_multiplier: int = 4

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["query_terms"] = list(self.query_terms)
        payload["evidence_needs"] = list(self.evidence_needs)
        payload["answer_slots"] = [slot.to_dict() for slot in self.answer_slots]
        payload["excluded_terms"] = list(self.excluded_terms)
        payload["dynamic_term_keys"] = list(self.dynamic_term_keys)
        return payload


@dataclass(frozen=True, slots=True)
class RouteQueryPack:
    route_id: str
    primary_query: str
    route_terms: tuple[str, ...]
    slot_queries: tuple[dict[str, Any], ...]
    must_terms: tuple[str, ...]
    support_terms: tuple[str, ...]
    weak_terms: tuple[str, ...]
    downrank_terms: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        payload = asdict(self)
        payload["schema_version"] = "route-query-pack-v0.1"
        payload["route_terms"] = list(self.route_terms)
        payload["slot_queries"] = [dict(item) for item in self.slot_queries]
        payload["must_terms"] = list(self.must_terms)
        payload["support_terms"] = list(self.support_terms)
        payload["weak_terms"] = list(self.weak_terms)
        payload["downrank_terms"] = list(self.downrank_terms)
        return payload


def get_route_catalog() -> dict[str, RouteCatalogEntry]:
    return dict(_ROUTE_CATALOG)


def get_route_entry(route_id: str) -> RouteCatalogEntry | None:
    return _ROUTE_CATALOG.get(str(route_id or ""))


def route_query_terms(route_id: str, normalized_terms: dict[str, list[str]] | None = None) -> list[str]:
    entry = get_route_entry(route_id)
    if entry is None:
        return []
    dynamic_terms: list[str] = []
    terms = normalized_terms or {}
    for key in entry.dynamic_term_keys:
        values = list(terms.get(key, []))
        if key == "stage":
            values = values[:2]
        dynamic_terms.extend(values)
    term_pack = route_domain_term_pack(route_id, normalized_terms)
    return _unique([*dynamic_terms, *term_pack["must_terms"], *entry.query_terms, *term_pack["support_terms"]])


def route_query_pack(route_id: str, question: str, normalized_terms: dict[str, list[str]] | None = None) -> dict[str, Any]:
    entry = get_route_entry(route_id)
    if entry is None:
        return RouteQueryPack(route_id=route_id, primary_query=question, route_terms=(), slot_queries=(), must_terms=(), support_terms=(), weak_terms=(), downrank_terms=()).to_dict()

    route_terms = tuple(route_query_terms(route_id, normalized_terms))
    term_pack = route_domain_term_pack(route_id, normalized_terms)
    slot_queries = tuple(_slot_query_payload(question, slot, term_pack) for slot in entry.answer_slots)
    return RouteQueryPack(
        route_id=route_id,
        primary_query=" ".join([question, *route_terms]).strip(),
        route_terms=route_terms,
        slot_queries=slot_queries,
        must_terms=tuple(term_pack["must_terms"]),
        support_terms=tuple(term_pack["support_terms"]),
        weak_terms=tuple(term_pack["weak_terms"]),
        downrank_terms=tuple(term_pack["downrank_terms"]),
    ).to_dict()


def route_domain_term_pack(route_id: str, normalized_terms: dict[str, list[str]] | None = None) -> dict[str, list[str]]:
    terms = normalized_terms or {}
    route_pack = _ROUTE_TERM_PACKS.get(route_id, {})
    must_terms = _entity_terms(route_id, terms)
    return {
        "must_terms": must_terms,
        "support_terms": list(route_pack.get("support_terms", ())),
        "weak_terms": list(route_pack.get("weak_terms", ())),
        "downrank_terms": list(route_pack.get("downrank_terms", ())),
    }


def route_answer_slot_dicts(route_id: str) -> list[dict[str, Any]]:
    entry = get_route_entry(route_id)
    if entry is None:
        return []
    return [slot.to_dict() for slot in entry.answer_slots]


def _slot_query_payload(question: str, slot: AnswerSlotDefinition, term_pack: dict[str, list[str]]) -> dict[str, Any]:
    terms = _unique([*term_pack["must_terms"], *slot.terms])
    return {
        "slot_id": slot.slot_id,
        "label": slot.label,
        "required": slot.required,
        "query": " ".join([question, *terms]).strip(),
        "terms": terms,
    }


def _entity_terms(route_id: str, normalized_terms: dict[str, list[str]]) -> list[str]:
    if route_id == "deliverable_detail":
        aliases: list[str] = []
        for term in normalized_terms.get("deliverable", []):
            aliases.extend(_DELIVERABLE_TERM_ALIASES.get(term.upper(), (term,)))
        return _unique(aliases)
    if route_id == "tailoring_policy":
        return list(_TAILORING_ENTITY_TERMS)
    return []


def _unique(values: list[str] | tuple[str, ...]) -> list[str]:
    seen: set[str] = set()
    items: list[str] = []
    for value in values:
        text = str(value).strip()
        key = text.casefold()
        if text and key not in seen:
            seen.add(key)
            items.append(text)
    return items


COMMON_EXCLUDED = ("history", "template change", "local labeling compliance noise")
DOCUMENT_IDENTITY_WEAK_TERMS = ("CT", "MI", "XP", "PEP", "document", "procedure", "process document")
_DELIVERABLE_TERM_ALIASES = {
    "QMP": ("QMP", "quality management plan", "质量管理计划"),
    "PMP": ("PMP", "project management plan", "项目管理计划"),
    "DHF": ("DHF", "design history file"),
    "DMR": ("DMR", "device master record"),
}
_TAILORING_ENTITY_TERMS = ("agile", "敏捷", "tailoring", "tailor", "裁剪", "review", "评审")
_ROUTE_TERM_PACKS: dict[str, dict[str, tuple[str, ...]]] = {
    "stage_transition_work": {
        "support_terms": (
            "product validation",
            "R4 M300",
            "design validation",
            "system validation test report",
            "risk management report",
            "usability evaluation",
            "reliability engineering report",
            "system stability test summary",
            "GSPR",
            "general safety and performance requirements",
            "STED",
            "summary technical documentation",
            "clinical evaluation report",
            "post-market surveillance",
            "production documentation",
            "series production samples",
            "software transfer",
            "embedded software",
            "transfer protocol",
            "process validation",
            "country specific approvals",
            "CE declaration",
        ),
        "weak_terms": DOCUMENT_IDENTITY_WEAK_TERMS,
        "downrank_terms": ("purpose and scope", "provisional solution", "standard tailoring", "product steering group"),
    },
    "deliverable_detail": {
        "support_terms": ("required contents", "shall contain", "owner", "author", "responsibility", "review approval"),
        "weak_terms": DOCUMENT_IDENTITY_WEAK_TERMS,
        "downrank_terms": ("purpose and scope", "provisional solution", "history", "template change", "general requirements"),
    },
    "tailoring_policy": {
        "support_terms": ("mandatory review", "cannot be tailored", "tailorable review", "approval evidence", "rationale record"),
        "weak_terms": DOCUMENT_IDENTITY_WEAK_TERMS,
        "downrank_terms": ("purpose and scope", "provisional solution", "task and responsibilities", "history", "template change"),
    },
}


_ROUTE_CATALOG: dict[str, RouteCatalogEntry] = {
    "process_operation": RouteCatalogEntry(
        route_id="process_operation",
        summary="识别为流程操作办法问题，优先检索流程主干、操作顺序、阶段关系、交付/评审依据和总览证据。",
        query_terms=(
            "process document",
            "operation steps",
            "how to operate",
            "workflow procedure",
            "phase sequence",
            "purpose scope applicability",
            "process model lifecycle traceability",
            "general requirements",
            "deliverables review evidence",
        ),
        excluded_terms=COMMON_EXCLUDED,
        rewrite_reason="用户询问流程如何操作，需要提升流程主干、阶段关系、交付物和评审证据。",
        evidence_needs=("scope", "operation_sequence", "deliverables_reviews", "verification_validation"),
        answer_slots=(
            AnswerSlotDefinition("scope_applicability", "适用范围", True, ("purpose", "scope", "适用范围", "applicability", "applies"), "未召回足够的流程适用范围或边界证据。"),
            AnswerSlotDefinition("operation_sequence", "操作顺序", True, ("operate", "operation", "workflow", "procedure", "phase", "sequence", "流程", "步骤"), "未召回足够的流程操作顺序或阶段主线证据。"),
            AnswerSlotDefinition("deliverables_reviews", "交付/评审依据", True, ("deliverable", "review", "qmp", "evidence", "record", "交付", "评审", "记录"), "未召回足够的交付物、评审或留证证据。"),
            AnswerSlotDefinition("verification_validation", "验证/确认", False, ("verification", "validation", "verify", "validate", "验证", "确认"), "本轮未召回验证/确认相关证据。"),
        ),
        answer_shape="scope -> operation sequence -> deliverables/reviews -> gaps",
        risk_level="high",
        citation_policy="high_density",
        needs_overview_evidence=True,
        expands_retrieval=True,
        rerank_enabled=True,
        route_label="流程操作办法",
    ),
    "process_overview": RouteCatalogEntry(
        route_id="process_overview",
        summary="识别为流程概念/适用范围问题，优先检索当前文档的目的、适用范围、流程主线和通用要求。",
        query_terms=(
            "process document",
            "workflow procedure",
            "purpose scope applicability objective",
            "procedure requirement",
            "process model lifecycle traceability",
            "general requirements",
        ),
        excluded_terms=COMMON_EXCLUDED,
        rewrite_reason="用户询问流程目的、范围或概览，需要提升文档总览、适用边界和流程模型证据。",
        evidence_needs=("purpose_scope", "process_model", "general_requirements"),
        answer_slots=(
            AnswerSlotDefinition("purpose_scope", "目的/范围", True, ("purpose", "scope", "目的", "适用范围"), "缺少目的或适用范围证据。"),
            AnswerSlotDefinition("process_model", "流程模型", True, ("v-model", "workflow", "process model", "lifecycle", "流程"), "缺少流程模型或主线证据。"),
            AnswerSlotDefinition("general_requirements", "通用要求", False, ("general requirements", "all process phases", "requirement", "通用"), "缺少通用要求证据。"),
        ),
        answer_shape="purpose/scope -> process model -> general requirements",
        risk_level="medium",
        citation_policy="required",
        needs_overview_evidence=True,
        expands_retrieval=True,
        rerank_enabled=True,
        route_label="流程总览解释",
    ),
    "role_action_guidance": RouteCatalogEntry(
        route_id="role_action_guidance",
        summary="识别为角色阶段动作问题，优先检索职责、交付物、阶段动作和留证证据。",
        query_terms=("responsibility", "deliverable", "qmp evidence", "phase", "role action"),
        rewrite_reason="用户询问角色在阶段中的动作，需要提升职责、交付物和留证证据。",
        evidence_needs=("role", "stage", "deliverable", "evidence"),
        answer_slots=(
            AnswerSlotDefinition("role_scope", "角色范围", True, ("role", "responsibility", "职责", "角色"), "缺少角色或职责范围证据。"),
            AnswerSlotDefinition("stage_action", "阶段动作", True, ("phase", "stage", "action", "activity", "阶段", "动作"), "缺少该阶段需要执行的动作证据。"),
            AnswerSlotDefinition("deliverable_evidence", "交付/留证", True, ("deliverable", "evidence", "record", "qmp", "交付", "证据", "记录"), "缺少交付物或留证要求证据。"),
        ),
        answer_shape="direct answer -> supporting citations -> gaps",
        risk_level="high",
        citation_policy="high_density",
    ),
    "reference_lookup": RouteCatalogEntry(
        route_id="reference_lookup",
        summary="识别为来源定位问题，优先检索章节、anchor、页码和原文 quote。",
        query_terms=("section", "anchor", "source reference", "quote", "location"),
        rewrite_reason="用户询问来源位置，需要提升章节、anchor 和原文 quote。",
        evidence_needs=("source_location", "source_quote"),
        answer_slots=(
            AnswerSlotDefinition("source_location", "来源定位", True, ("section", "anchor", "page", "chapter", "章节", "页"), "缺少可定位章节或页码证据。"),
            AnswerSlotDefinition("source_quote", "原文片段", True, ("quote", "reference", "原文", "引用"), "缺少可直接引用的原文片段。"),
        ),
        answer_shape="location -> quote -> context",
        risk_level="medium",
        citation_policy="required",
    ),
    "table_lookup": RouteCatalogEntry(
        route_id="table_lookup",
        summary="识别为表格查询问题，优先检索 table/matrix/cell 证据。",
        query_terms=("table", "matrix", "row", "column", "cell", "deliverable"),
        rewrite_reason="用户询问表格内容，需要提升 table/matrix/cell 相关证据。",
        evidence_needs=("table_or_matrix", "cell_or_row", "source_quote"),
        answer_slots=(
            AnswerSlotDefinition("table_or_matrix", "表格/矩阵", True, ("table", "matrix", "表", "矩阵"), "缺少表格或矩阵证据。"),
            AnswerSlotDefinition("cell_or_row", "行列/单元格", True, ("row", "column", "cell", "行", "列", "单元格"), "缺少可定位行列或单元格证据。"),
            AnswerSlotDefinition("source_quote", "原文片段", True, ("quote", "reference", "原文", "引用"), "缺少表格来源原文片段。"),
        ),
        answer_shape="table/cell evidence -> direct answer -> gaps",
        risk_level="high",
        citation_policy="required",
    ),
    "bu_comparison": RouteCatalogEntry(
        route_id="bu_comparison",
        summary="识别为多文档对比问题，优先检索可对齐的 CT/MI/XP 证据。",
        query_terms=("comparison", "difference", "aligned evidence", "BU", "CT MI XP"),
        rewrite_reason="用户询问多文档差异，需要提升可对齐的比较证据。",
        evidence_needs=("per_document_evidence", "same_points", "differences", "gaps"),
        answer_slots=(
            AnswerSlotDefinition("per_document_evidence", "逐文档证据", True, ("CT", "MI", "XP", "document", "source", "文档", "来源"), "缺少逐文档可对齐证据。"),
            AnswerSlotDefinition("same_points", "共同点", False, ("same", "common", "aligned", "共同", "一致"), "本轮未召回共同点证据。"),
            AnswerSlotDefinition("differences", "差异点", True, ("difference", "different", "gap", "差异", "不同"), "缺少差异点证据。"),
            AnswerSlotDefinition("gaps", "证据缺口", False, ("missing", "insufficient", "gap", "缺", "不足"), "本轮未召回明确缺口证据。"),
        ),
        answer_shape="aligned evidence rows -> differences -> gaps",
        risk_level="high",
        citation_policy="per_document_required",
    ),
    "gap_check": RouteCatalogEntry(
        route_id="gap_check",
        summary="识别为证据缺口检查问题，优先检索要求、缺口和支持关系。",
        query_terms=("required evidence", "missing evidence", "coverage", "gap", "support"),
        rewrite_reason="用户询问证据是否足够，需要提升要求、缺口和支持关系。",
        evidence_needs=("required_evidence", "available_evidence", "missing_evidence"),
        answer_slots=(
            AnswerSlotDefinition("required_evidence", "要求证据", True, ("required", "shall", "must", "要求", "必须"), "缺少要求侧证据。"),
            AnswerSlotDefinition("available_evidence", "已有证据", True, ("available", "evidence", "record", "已有", "证据", "记录"), "缺少已有证据。"),
            AnswerSlotDefinition("missing_evidence", "缺口", True, ("missing", "gap", "insufficient", "缺", "不足"), "缺少证据缺口判断。"),
        ),
        answer_shape="available evidence -> missing evidence -> next check",
        risk_level="high",
        citation_policy="required",
    ),
    "summary_request": RouteCatalogEntry(
        route_id="summary_request",
        summary="识别为总结问题，优先检索文档主线、范围、要求和交付评审证据。",
        query_terms=("main points", "scope", "process", "requirements", "deliverables", "review"),
        rewrite_reason="用户要求总结，需要提升文档主线、范围、要求和交付评审证据。",
        evidence_needs=("main_points", "supporting_citations", "boundaries"),
        answer_slots=(
            AnswerSlotDefinition("main_points", "要点", True, ("main", "point", "summary", "requirement", "要点", "总结"), "缺少可总结的主线证据。"),
            AnswerSlotDefinition("supporting_citations", "引用支撑", True, ("source", "quote", "citation", "来源", "引用"), "缺少引用支撑。"),
            AnswerSlotDefinition("boundaries", "边界", False, ("scope", "boundary", "limit", "范围", "边界"), "本轮未召回边界证据。"),
        ),
        answer_shape="main points -> supporting citations -> boundaries",
        risk_level="medium",
        citation_policy="required",
    ),
    "definition_lookup": RouteCatalogEntry(
        route_id="definition_lookup",
        summary="识别为定义解释问题，优先检索术语解释和定义位置。",
        query_terms=("definition", "meaning", "scope", "term"),
        rewrite_reason="用户询问定义，需要提升术语解释和定义位置。",
        evidence_needs=("definition", "scope", "source_quote"),
        answer_slots=(
            AnswerSlotDefinition("definition", "定义", True, ("definition", "meaning", "定义", "含义"), "缺少定义证据。"),
            AnswerSlotDefinition("scope", "适用范围", False, ("scope", "applicability", "范围", "适用"), "本轮未召回定义适用范围证据。"),
            AnswerSlotDefinition("source_quote", "原文片段", True, ("quote", "reference", "source", "原文", "引用"), "缺少定义原文片段。"),
        ),
        answer_shape="direct answer -> supporting citations -> gaps",
        risk_level="medium",
        citation_policy="required",
    ),
    "stage_transition_work": RouteCatalogEntry(
        route_id="stage_transition_work",
        summary="识别为阶段转换工作问题，优先检索两个阶段之间的输入、工作项、评审交付和退出/进入条件。",
        query_terms=("stage transition", "work items", "entry exit criteria", "phase deliverables", "review outputs", "readiness"),
        dynamic_term_keys=("stage",),
        excluded_terms=COMMON_EXCLUDED,
        rewrite_reason="用户询问两个阶段之间要完成哪些工作，需要提升阶段转换、工作项、交付评审和退出/进入条件证据。",
        evidence_needs=("transition_scope", "work_items", "reviews_deliverables", "exit_readiness"),
        answer_slots=(
            AnswerSlotDefinition("transition_scope", "阶段范围", True, ("r4", "r5", "transition", "between", "phase", "阶段"), "缺少 R4/R5 或阶段转换边界证据。"),
            AnswerSlotDefinition("entry_inputs", "输入/前置条件", False, ("input", "entry", "precondition", "readiness", "product validation", "after design review r4", "输入", "前置"), "本轮未召回阶段进入条件或输入证据。"),
            AnswerSlotDefinition("work_items", "需完成工作", True, ("work", "activity", "task", "complete", "product validation", "design validation", "system validation", "system validation test report", "reliability", "reliability engineering report", "stability", "system stability test summary", "production documentation", "series production samples", "software transfer", "process validation", "gspr", "sted", "technical documentation", "clinical evaluation", "post-market surveillance", "完成", "工作", "活动"), "缺少阶段之间需完成工作项证据。"),
            AnswerSlotDefinition("reviews_deliverables", "评审/交付物", True, ("review", "deliverable", "record", "output", "system validation test report", "risk management report", "reliability engineering report", "system stability test summary", "technical documentation", "summary technical documentation", "gspr", "sted", "clinical evaluation report", "post-market surveillance", "评审", "交付", "记录"), "缺少评审、交付物或记录证据。"),
            AnswerSlotDefinition("exit_readiness", "退出/进入 R5 条件", False, ("exit", "readiness", "approval", "r5", "m300", "delivery release", "ce declaration", "post-market surveillance", "country specific approvals", "退出", "准备", "批准"), "本轮未召回进入 R5 的 readiness 或批准条件证据。"),
        ),
        answer_shape="transition scope -> work items -> reviews/deliverables -> exit readiness",
        risk_level="high",
        citation_policy="high_density",
        needs_overview_evidence=True,
        expands_retrieval=True,
        rerank_enabled=True,
        route_label="阶段转换工作",
    ),
    "deliverable_detail": RouteCatalogEntry(
        route_id="deliverable_detail",
        summary="识别为交付物内容和责任问题，优先检索内容要求、责任人、撰写/维护和评审批准证据。",
        query_terms=("quality management plan", "content", "owner", "responsible", "author", "review approval"),
        dynamic_term_keys=("deliverable",),
        excluded_terms=("history", "template change"),
        rewrite_reason="用户询问交付物内容和责任，需要提升内容要求、责任人、撰写维护和评审批准证据。",
        evidence_needs=("deliverable_scope", "required_contents", "owner_author", "review_approval"),
        answer_slots=(
            AnswerSlotDefinition("deliverable_scope", "交付物范围", True, ("qmp", "quality management plan", "deliverable", "交付"), "缺少 QMP 或交付物范围证据。"),
            AnswerSlotDefinition("required_contents", "应包含内容", True, ("content", "include", "contains", "shall contain", "内容", "包含"), "缺少 QMP 应包含内容证据。"),
            AnswerSlotDefinition("owner_author", "责任人/撰写人", True, ("owner", "responsible", "author", "write", "prepare", "responsibility", "负责", "撰写", "编写"), "缺少 QMP 责任人或撰写人证据。"),
            AnswerSlotDefinition("review_approval", "评审/批准", False, ("review", "approval", "maintain", "update", "评审", "批准", "维护"), "本轮未召回 QMP 评审、批准或维护证据。"),
        ),
        answer_shape="deliverable scope -> required contents -> owner/author -> review approval",
        risk_level="high",
        citation_policy="high_density",
        expands_retrieval=True,
        rerank_enabled=True,
        route_label="交付物内容与责任",
    ),
    "tailoring_policy": RouteCatalogEntry(
        route_id="tailoring_policy",
        summary="识别为敏捷/裁剪评审问题，优先检索 tailoring 条件、可裁剪评审、不可裁剪评审和批准/留证要求。",
        query_terms=("agile", "tailoring", "review", "cannot be tailored", "mandatory review", "tailorable review", "approval evidence"),
        excluded_terms=("history", "template change"),
        rewrite_reason="用户询问敏捷开发下评审裁剪边界，需要提升可裁剪、不可裁剪、强制评审和批准留证证据。",
        evidence_needs=("agile_applicability", "tailorable_reviews", "non_tailorable_reviews", "approval_evidence"),
        answer_slots=(
            AnswerSlotDefinition("agile_applicability", "敏捷适用边界", True, ("agile", "敏捷", "iterative", "scrum"), "缺少敏捷方法适用边界证据。"),
            AnswerSlotDefinition("tailorable_reviews", "可裁剪评审", True, ("tailor", "tailorable", "can be tailored", "optional", "裁剪", "可裁剪"), "缺少可裁剪评审证据。"),
            AnswerSlotDefinition("non_tailorable_reviews", "不可裁剪评审", True, ("cannot be tailored", "mandatory", "shall", "must", "不可", "不能", "强制"), "缺少不可裁剪或强制评审证据。"),
            AnswerSlotDefinition("approval_evidence", "批准/留证", False, ("approval", "evidence", "record", "rationale", "批准", "证据", "记录", "理由"), "本轮未召回裁剪批准、理由或留证要求。"),
        ),
        answer_shape="agile boundary -> tailorable reviews -> non-tailorable reviews -> approval evidence",
        risk_level="high",
        citation_policy="high_density",
        expands_retrieval=True,
        rerank_enabled=True,
        route_label="裁剪与评审边界",
    ),
    "generic_rag": RouteCatalogEntry(
        route_id="generic_rag",
        summary="识别为未知或低置信问题，使用通用 RAG fallback 并显式说明证据边界。",
        query_terms=("supporting evidence", "relevant section", "source quote", "uncertainty"),
        rewrite_reason="未知问题进入通用 RAG fallback，需要保留短结论、支撑证据、不确定性和引用边界。",
        evidence_needs=("supporting_evidence", "source_quote", "uncertainty"),
        answer_slots=(
            AnswerSlotDefinition("direct_answer", "直接回答", True, (), "缺少可支撑直接回答的证据。"),
            AnswerSlotDefinition("source_support", "引用支撑", True, (), "缺少可校验引用。"),
            AnswerSlotDefinition("uncertainty", "不确定性/缺口", False, ("missing", "uncertain", "insufficient", "缺", "不足"), "本轮没有显式证据缺口。"),
        ),
        answer_shape="short answer -> supporting citations -> uncertainty/gaps",
        risk_level="medium",
        citation_policy="required",
    ),
}