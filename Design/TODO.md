# QT Wiki System TODO

更新时间：2026-06-24
状态：Active，系统级 checkbox-first 执行入口

使用方式：本文件只放可勾选的系统级开发任务；模块级设计、取舍解释和接口细节写在对应 Spec；历史 Gate / Plan / Review 文档统一归档到 [old/](old/)，仅作为历史背景和证据附件。

任务字段约定：

- `预期功能`：完成后用户或系统会具备的直接能力。
- `最小方案`：当前切片只做哪些最小实现。
- `验收`：做到什么可以勾选，优先写测试、smoke、artifact 或可观察 UI 行为。
- `来源`：对应的模块 Spec。

## 0. Design 入口

当前 Design 目录采用“一份系统 TODO + 三份模块 Spec + 少量证据附件”的结构。

| 类型 | 当前文件 | 用途 |
| --- | --- | --- |
| 系统级执行板 | [TODO.md](TODO.md) | 唯一看板，能完成一项就勾掉一项。 |
| Parser/RAG 模块 Spec | [Spec-Parser-RAG.md](Spec-Parser-RAG.md) | 多文档解析、Markdown/RAG 中间格式、DocumentBlock、表格和 citation。 |
| Chat 模块 Spec | [Spec-Chat-Workflow.md](Spec-Chat-Workflow.md) | 意图识别、路由、工具执行、Answer Run、LLM composer、memory。 |
| UI 模块 Spec | [Spec-UI-Workspace.md](Spec-UI-Workspace.md) | Source Intake、Review Gate、Ask Workspace、Admin / JSON Lab。 |
| 产品定义 | [PRD-流程问答工作台.md](PRD-流程问答工作台.md) | 产品目标、MVP 边界、用户价值。 |
| 历史附件归档 | [old/](old/) | 查历史决策、人审证据、parser 经验时使用，不作为执行入口。 |

## 1. 当前主线

下一阶段主线是 Release-0 可信 NotebookLM-like 问答闭环的第二轮收敛：Router/RAG/table metadata/eval 首轮已 checkpoint，EvidenceSource 首版也已落地。现在进入 evidence quality -> Reference polish -> real smoke 的顺序；Parser 继续保持“当前够用，必要时触发式升级”，完整 provider 升级放在真实 smoke 证明结构 anchor 是瓶颈之后。

```text
已完成工作摘要

Router 2.0
  -> intent-route-v0.2 schema
  -> RouteCatalog 13 个 entry 全量无损映射
  -> rule route 输出投影到 schema
  -> LLM Router shadow 输出与规则 route diff
  -> guardrails 失败降级 generic_rag

RAG 升级
  -> VectorRetriever 接 Azure text-embedding-3-small adapter
  -> lexical-only vs semantic-hybrid smoke 对比
  -> 表格问题实测，先做 route-gated semantic retriever；只在非 role/reference route 启用，再判断 query rewrite / table-aware chunk / parser provider 哪层需要动

Parser 边界
  -> 当前 PDF pypdf、DOCX XML 主链路保持不动
  -> Docling / Marker / MinerU / OCR provider 进入 Later
  -> 触发条件是扫描件、图片型 PDF、复杂表格/版面成为 Release-0 阻塞
```

三份 Spec 到 TODO 的映射：

| Spec | 关键设计 | TODO 主线 |
| --- | --- | --- |
| [Spec-Parser-RAG.md](Spec-Parser-RAG.md) | Notebook-like 自动解析、DocumentBlock、RAG artifacts、表格/图片质量状态 | 当前只落 `PARSER-MIN-*`：评估现有 parser、补 EvidenceSource adapter；完整 artifacts/provider 后置。 |
| [Spec-Chat-Workflow.md](Spec-Chat-Workflow.md) | 8 步 runtime、RouteCatalog、generic fallback、AnswerPlan、Claim Verifier、Session Memory | `CHAT-*` 产出可审计回答链路。 |
| [Spec-UI-Workspace.md](Spec-UI-Workspace.md) | Source Intake / Review Gate / Ask Workspace / Admin | `UI-*` 产出普通用户主路径和开发调试路径分离的工作台。 |

### 1.1 当前状态板

| 状态 | 任务 | 说明 |
| --- | --- | --- |
| 已提交 | Router/RAG/table metadata/eval checkpoint | `e5bd385 Add route-gated semantic and table diagnostics`，封板 `CHAT-05C`、`RAG-03`、route-gated semantic 与 table metadata/rerank 首轮。 |
| 已提交 | EvidenceSource adapter | `cd8f324 Add EvidenceSource adapter`，完成 `CHAT-COMP-01` 与 `PARSER-MIN-02`，并同步 Spec/README/CHANGELOG/SESSION-WIP。 |
| 当前下一刀 | `PARSER-MIN-03` 轻量文档状态与质量警告 | 在 EvidenceSource 上补 `ready / limited / needs_review` 与 evidence-level `quality_warning`，供 Reference UI 和 Claim Guardrail 使用。 |
| 随后 | `UI-02` Ask Workspace v2 + Reference polish | Reference Card 消费 EvidenceSource 与 quality warning，普通问答路径继续保持干净。 |
| 再随后 | `R0-01/R0-02` 真实 smoke | 单文档可信问答与高频专业问题人审，决定是否触发 parser 表格元素抽取。 |

### 1.2 2026-06-24 后续执行节奏

| 时间 | 主线 | 交付 |
| --- | --- | --- |
| 已完成 | Router/RAG/evidence checkpoint | `CHAT-05A/B/C`、`RAG-02/03`、table metadata/rerank、`CHAT-COMP-01`、`PARSER-MIN-02`。 |
| 当前 | Quality contract | `PARSER-MIN-03`：轻量文档状态、evidence quality warning、primary evidence 可用性判断。 |
| 下一步 | Reference polish | `UI-02`：Reference Viewer 用 EvidenceSource 展示 quote/source_context/quality warning。 |
| 下一步 | Release-0 smoke | `R0-01/R0-02`：单文档 CT/MI/XP 与 R4->R5/QMP/敏捷裁剪真实人审。 |
| 触发式 | Parser 表格元素抽取 | 仅当真实 smoke 证明 table/cell/structure anchor 是核心瓶颈时启动。 |

### 1.3 Router 2.0 设计要点

- `primary_route` 必须来自 RouteCatalog；`secondary_routes` 也只能是已登记 route id。
- `entities` 不是 `dynamic_term_keys` 的直译，而是结构化实体实例，例如 stage 的 `from_stage / to_stage / active_stage`，deliverable 的 `query_target`，BU 的 source scope hint。
- `confidence` 拆为 `route_match` 和 `evidence_likely`：route 低置信降级 `generic_rag`，evidence 低置信提高 missing evidence 预期。
- `_extensions` 作为 schema 扩展点，后续承接 `table_needed`、`multi_hop` 等实验字段。
- Pre-router 只保留稳定事实抽取和候选 route hint，不再输出最终意图；最终 route 由 LLM Router shadow 决策，并由程序 guardrails 校验。
- Guardrails 至少包含 schema 合法、route 在 catalog、confidence 达标、secondary routes 合法；失败统一降级 `generic_rag` 并记录原因。

### 1.4 RAG 设计要点

- 当前 baseline 是 `HybridRetriever([RuleSectionRetriever, FullTextRetriever])`，属于 lexical / rule hybrid。
- `VectorRetriever` 已有注入点，本轮只接真实 Azure embedding adapter，不建向量数据库，不默认替换生产检索。
- embedding 首选 Azure `text-embedding-3-small`；不可用时再评估本地 `all-MiniLM-L6-v2` fallback。
- 三路 Hybrid 先等权 RRF，不先调权重；用 smoke 数据比较 recall@8、route accuracy、citation drift。
- RAG-02 结论：semantic-hybrid 已可运行，但在 role/reference 类问题出现 recall 回退与 citation drift；因此 RAG-03 先实现 route-gated semantic retriever，只在非 role/reference route 启用，role/reference 继续走 lexical/rule baseline 和 source guardrail。
- 表格先让 route-gated semantic embedding 尝试补召回；若仍失败，再考虑 table-aware chunk metadata 或 structured table index。

### 1.5 2026-06-24 checkpoint 后顺序

| 顺序 | 下一步 | 判断 |
| --- | --- | --- |
| 1 | 本地 checkpoint | 已提交 `e5bd385 Add route-gated semantic and table diagnostics`，封板 Router/RAG/table metadata/eval 首轮。 |
| 2 | `CHAT-COMP-01` | 先保留现有 composer 边界行为，避免 AnswerPlan-driven 迁移丢失 fallback、source-location 和 partial evidence 表达。 |
| 3 | `PARSER-MIN-02` | 先统一 evidence view，再改 Reference UI、Claim Guardrail 和 parser quality。 |
| 4 | `PARSER-MIN-03` | 给 evidence/doc 增加 ready/limited/needs_review 与 warning。 |
| 5 | `UI-02` | Reference polish 建立在 EvidenceSource 与 quality warning 上。 |
| 6 | `R0-01/R0-02` | 用单文档和高频专业问题做人审 smoke。 |
| 7 | 触发式 parser | 若人审证明表格/结构 anchor 仍是瓶颈，再进入 parser 表格元素抽取。 |

### 1.6 External Architecture References

这部分只记录外部架构参考在本项目里的落点，不做长论文综述。

| 参考 | 吸收方式 | 当前落点 |
| --- | --- | --- |
| Self-RAG | Thin Claim Guardrail + on-demand retrieval | `CHAT-07` 做薄 claim guardrail；retrieval 保持 route-gated / on-demand，不默认扩大检索。 |
| VMAO | bounded Plan/Execute/Verify/Replan | Answer Run 保持 bounded workflow；后续只允许有限、可审计的 deterministic replan。 |
| GraphRAG | later multi-doc graph summaries | 放到 `R0-04` 多文档 / BU 对比稳定后，再做轻量 domain graph summaries。 |
| DSPy | eval-driven prompt/router optimization | 先积累 eval + human-review 样本，再优化 Router、Query Rewrite、rerank 和 composer prompt。 |
| Enterprise QA lessons | evidence boundary + human review | EvidenceSource、quality warning、Reference UI 和 human review 共同守住证据边界。 |
| MEQA | tool-specific agents only when needed | 普通问答走固定 workflow；只有异构工具任务才升级为 tool-specific agents。 |

## 2. 已完成证据

- [x] **DOC-01 建立系统级 TODO + 模块级 Spec 框架**
  - 证据：本文件、[Spec-Parser-RAG.md](Spec-Parser-RAG.md)、[Spec-Chat-Workflow.md](Spec-Chat-Workflow.md)、[Spec-UI-Workspace.md](Spec-UI-Workspace.md)。

- [x] **DOC-02 物理归档历史附件**
  - 证据：2026-06-23 已把历史 plan/review/notes 从 Design 根目录移入 [old/](old/)；Design 根目录保留 [README.md](README.md)、[TODO.md](TODO.md)、[PRD-流程问答工作台.md](PRD-流程问答工作台.md)、三份 Spec 和目录型证据/记忆入口。

- [x] **DONE-CHAT-01 Citation validation 首切片**
  - 证据：`/api/session/query` 已校验 selected source scope、document identity、quote、anchor，并把 citation validation summary 写入 answer_run；相关回归测试已覆盖 scope 外证据、缺 anchor、缺 quote 和 quote-specific citation label。

- [x] **DONE-CHAT-02 Reference source context 首切片**
  - 证据：citation payload 已带 `source_context`，Reference Viewer 可展开引用前文、命中上下文和引用后文；后端相关测试和 `App/web npm run build` 已通过。

- [x] **DONE-CHAT-03 Query Rewrite / ToolPlan / AnswerPlan v0.1 首切片**
  - 证据：`/api/session/query` 已写入 `query-rewrite-v0.1`、`tool-plan-v0.1`、`answer-plan-v0.1`；`process_operation/stage_transition_work/deliverable_detail/tailoring_policy` 已有首批 route 和 slot map。

- [x] **DONE-CHAT-04 Answer readability 首切片**
  - 证据：LLM composer prompt 和 deterministic fallback 已改为“短结论 + 自然小标题 + 可选语义字段”结构；Ask Workspace `RichAnswer` 支持 `依据 / 出处 / 边界 / 缺口 / 补充说明` 等语义字段行，并兼容旧式长 evidence 行的结构化渲染。前端已把编号步骤标题与补充小标题分层：编号标题为 `level-3`，普通 `####`/紧凑补充标题降为 `level-4`。验证 `tests/test_app_api.py -k "session_query_uses_selected_pep_chunks_for_process_question or process_overview_fallback_uses_evidence_details_without_fixed_framework" -q` 为 `2 passed, 1 warning`，`npm --prefix App/web run build` 通过；浏览器 smoke 确认补充标题字体小于编号标题。

- [x] **DONE-CHAT-05 Session State / follow-up contract 首切片**
  - 证据：`SessionQueryRequest` 已接收 `session_id` 与 `previous_turns`；`/api/session/query` 的 context step 输出 `session-state-v0.1`，包含 `is_follow_up`、`follow_up_reason`、上一问摘要、上一轮引用数、source scope 是否一致和 contextual query。前端连续提问时会把上一轮成功回答的摘要、citations 和 source scope 传入后端；短追问会把上一问合入检索 query。验证 `tests/test_app_api.py -k "session_query_uses_selected_pep_chunks_for_process_question or session_query_accepts_follow_up_contract or session_query_unknown_question_uses_generic_rag_fallback" -q` 为 `3 passed, 1 warning`。

- [x] **DONE-UI-02A Ask Workspace 主路径减噪 + Reference 简化**
  - 证据：上传成功后停留在 Ask Workspace；左侧 source card 显示已选/已解析/待复核状态，顶部移除 `Session PEP-R2`、eval/model 等小标堆叠；中间移除 `围绕当前 source 提问...`、`Process Chat`、`回答必须回到证据` 等说明性标题；右侧 Reference 去掉“当前原文 + 本轮返回”的重复结构，默认只显示 resource 文件、页码/锚点和返回 quote。验证 `npm --prefix App/web run build` 通过。

## 3. 当前执行计划

### Phase 0: Release-0 验收基线

- [x] **BASE-01 固化 CT / MI / XP smoke 问题集** `Highest`
  - 预期功能：项目有一组固定问题可以反复验证 selected-doc 问答、引用、route、fallback 和 UI 展示是否可信。
  - 最小方案：固定 CT / MI / XP 的问题样例：流程如何操作、R2/PO、7.16、R4->R5、QMP、敏捷裁剪、证据缺口和未知问题。
  - 验收：每个问题记录期望 source scope、route、最低 citation 要求、人工可读判断和失败记录位置。
  - 证据：已新增 `Tool.evals.release0_smoke`，包含 8 条 `release0-smoke-cases-v0.1` case，覆盖 CT / MI / XP 单文档、未知 fallback 和多文档对比；失败记录入口为 [review-artifacts/release0-smoke-failures.md](review-artifacts/release0-smoke-failures.md)。验证 `..\.venv\Scripts\python.exe -m pytest tests/test_release0_smoke_cases.py -q` 为 `2 passed`。

### Phase 1: Chat Runtime 可信回答骨架

- [x] **CHAT-03 抽出轻量 RouteCatalog** `Highest`
  - 预期功能：系统用统一 catalog 管理高频/高风险问题策略，包括 query terms、evidence needs、answer slots、risk level 和 citation policy。
  - 最小方案：先迁移现有 `process_operation/stage_transition_work/deliverable_detail/tailoring_policy/reference_lookup/table_lookup/bu_comparison/gap_check/summary_request/generic_rag` 的策略字段。
  - 验收：现有 route 行为和测试不回退；Query Rewrite、ToolPlan、AnswerPlan 可从 catalog 读取策略。
  - 证据：已新增 `Tool.workflows.route_catalog`，并让 `/api/session/query` 的 route plan metadata、query rewrite、ToolPlan `route_strategy`、retrieval top_k、route rerank、AnswerPlan slots 和 answer shape 读取 catalog；新增 `tests/test_route_catalog.py` 覆盖 Release-0 route 覆盖率和 API helper 接入。验证 `tests/test_route_catalog.py tests/test_app_api.py tests/test_answer_workflow.py tests/test_release0_smoke_cases.py tests/test_retriever_interface.py -q` 为 `49 passed, 1 warning`，`compileall` 和 `git diff --check` 通过。
  - 来源：[Spec-Chat-Workflow.md](Spec-Chat-Workflow.md)。

- [x] **CHAT-04 Generic RAG fallback + route evolution eval** `Highest`
  - 预期功能：未知问题也能得到有引用、有边界、有不确定性说明的回答；反复失败的问题可以沉淀为 eval case 和后续 RouteCatalog entry。
  - 最小方案：低置信、未知 route、LLM schema 校验失败时进入 `generic_rag`，输出 fallback reason、retrieved evidence、uncertainty 和 citation coverage。
  - 验收：fallback 返回短结论、支撑证据、不确定性提示和 citation coverage；新增 route 前先补 eval case。
  - 证据：`/api/session/query` 已在未命中高频流程 route 时进入 `generic_rag`，planning step 输出 `fallback_reason`，generation step 输出 `generic-rag-fallback-v0.1` report，包含 citation coverage、retrieved evidence count、missing evidence count、confidence 和 uncertainty；deterministic fallback 回答会保留“证据边界”。新增 `tests/test_app_api.py::test_session_query_unknown_question_uses_generic_rag_fallback`，验证未知问题有 citation、有 fallback report、有证据边界。验证 `tests/test_app_api.py -k "unknown_question_uses_generic_rag_fallback or session_query_uses_selected_pep_chunks_for_process_question" -q` 为 `2 passed, 1 warning`。
  - 来源：[Spec-Chat-Workflow.md](Spec-Chat-Workflow.md)。

- [x] **CHAT-06 AnswerPlan v0.2 + evidence-bound slots 首版** `Highest`
  - 预期功能：回答先形成结构化 slots，filled slot 必须绑定 evidence/citation；无证据的 slot 明确进入 missing evidence。
  - 最小方案：Planner 基于 `RouteCatalog + EvidencePackage` 生成 `answer-plan-v0.2`；LLM composer 接收 AnswerPlan、citations、source_context 和 AnswerStyle；deterministic fallback 后续收敛为 plan-only。
  - 验收：`process_operation/stage_transition_work/deliverable_detail/tailoring_policy/generic_rag` 均能生成 slots；slot 绑定的 citation_ids/evidence_ids 可反查；缺证 slot 写入 `missing_evidence`。
  - 证据：`/api/session/query` 的 generation step 已输出 `answer-plan-v0.2`，slot 保留 `citation_ids/evidence_ids` 并新增 `evidence_bindings`，可反查 document、section、anchor 和 quote preview；未填充 slot 进入 `missing_evidence`，并输出 `plan_quality` 统计 required、filled 和 missing required slots。新增 `tests/test_app_api.py::test_answer_plan_v02_records_missing_evidence_for_unfilled_required_slots`，并扩展 session query 回归验证 slot binding。验证 `tests/test_app_api.py tests/test_answer_workflow.py tests/test_route_catalog.py tests/test_release0_smoke_cases.py -q` 为 `46 passed, 1 warning`，VS Code diagnostics 与 `git diff --check` 通过。
  - 来源：[Spec-Chat-Workflow.md](Spec-Chat-Workflow.md)。

- [ ] **CHAT-07 Thin Claim Guardrail** `Later`
  - 预期功能：系统可以对高风险事实句做轻量 groundedness 检查，并标记 unsupported 或 weakly-supported claim。
  - 最小方案：只检查责任主体、必须/不可裁剪、阶段门、交付物结论等高风险 claim；复用本轮 citations/source_context，不新增厚同步二次 RAG。
  - 验收：人为构造 unsupported 高风险 claim 的测试能被标记；answer_run 写入薄 guardrail 摘要；普通 UI 只展示警告状态，不展示调试细节。
  - 来源：[Spec-Chat-Workflow.md](Spec-Chat-Workflow.md)。

- [ ] **CHAT-01 伴随式抽取 ChatWorkflowRunner**
  - 预期功能：`/api/session/query` 的核心步骤逐步从 API 函数中抽出，形成可测试的 runner，但不为重构而打断回答质量主线。
  - 最小方案：在实现 RouteCatalog、generic fallback、AnswerPlan、Claim Verifier 时，把对应 intent、retrieval、evidence、answer_run 组装逻辑迁到 runner 或独立 helper。
  - 验收：API 仍返回兼容 `ChatQueryResponse`；新增/迁移逻辑都有窄测试；answer_run 每一步来自真实中间状态。
  - 来源：[Spec-Chat-Workflow.md](Spec-Chat-Workflow.md)。

- [x] **CHAT-05A intent-route-v0.2 schema + RouteCatalog 全量映射** `Highest`
  - 预期功能：系统有一个可承载当前 RouteCatalog 策略和未来 LLM Router 输出的统一 route schema，且不会丢失现有 13 个 route 的策略字段。
  - 最小方案：定义 `intent-route-v0.2`，把 `RouteCatalogEntry.route_id / summary / query_terms / excluded_terms / dynamic_term_keys / evidence_needs / answer_slots / answer_shape / risk_level / citation_policy / rewrite_reason / rerank_enabled / expands_retrieval / top_k_multiplier` 全量映射；新增 `primary_route / secondary_routes / confidence.route_match / confidence.evidence_likely / entities / question_type / needs_previous_context / guardrail / _extensions`。
  - 验收：每个 catalog entry round-trip 后字段不丢；非法 route、非法 secondary route、低 route_match 都能降级 `generic_rag`；`/api/session/query` 可在 answer_run 中 shadow 输出 schema，但不改变当前生产 route 行为。
  - 证据：新增 `Tool.workflows.intent_route`，提供 `intent-route-v0.2` catalog projection、结构化 entities 和 guardrail fallback；当前规则 route 通过 `_session_intent_route_shadow()` 投影到 `/api/session/query` 的 answer_run planning 输出，不改变生产 route。新增 `tests/test_route_catalog.py` 覆盖 13 个 RouteCatalog entry 无损映射、非法 primary route 和低 `route_match` 降级 `generic_rag`、阶段/BU entity 投影；扩展 session query API 回归验证 answer_run shadow schema。验证 `tests/test_route_catalog.py tests/test_app_api.py -q` 为 `44 passed, 1 warning`。
  - 来源：[Spec-Chat-Workflow.md](Spec-Chat-Workflow.md)。

- [x] **CHAT-05B LLM Router shadow diff 分析** `Highest`
  - 预期功能：真实 LLM Router 输出可以和当前规则 route 做逐案对比，明确哪些规则可退役、哪些规则应保留为 pre-router entity extraction 或 safety guardrail。
  - 最小方案：对 R4->R5、QMP、敏捷裁剪、source-location follow-up、未知 fallback、多 BU 对比运行 LLM Router shadow；比较 route id、entities、confidence、query_pack/evidence_needs/answer_slots、needs_previous_context 和 fallback reason。
  - 验收：生成 diff artifact，至少分类 `matched / llm_improved / llm_regressed / entity_missing / fallback_mismatch / source_location_risk`；source-location follow-up 仍由程序 guardrail 兜底；LLM route 不直接替换生产 route。
  - 证据：新增 `Tool.workflows.router_shadow` 和 `Tool.evals.router_shadow`，支持 LLM router prompt、JSON 提取、guardrail 后 diff 分类、可注入 router 测试和 Azure GPT-5.4 真实 shadow callable。已生成 [review-artifacts/router-shadow-diff.md](review-artifacts/router-shadow-diff.md)：6 个目标 case 中 5 个 `matched`，1 个 `fallback_mismatch`；`r0-mi-unknown-fallback` 中规则 route 保守降级 `generic_rag`，LLM shadow 选择 `process_operation`，暂作为 route evolution eval 样本，不替换生产 route。Source-location follow-up 本轮 matched，但继续保留程序级 citation/source-scope guardrail。验证 `tests/test_router_shadow_diff.py tests/test_route_catalog.py tests/test_app_api.py -q` 为 `46 passed, 1 warning`。
  - 来源：[Spec-Chat-Workflow.md](Spec-Chat-Workflow.md)。

- [x] **CHAT-05C route evolution eval：容易遗漏/准备事项问题** `Highest`
  - 预期功能：把 router shadow diff 中的 `fallback_mismatch` 沉淀为 route evolution eval，判断“容易遗漏 / 准备事项 / 注意事项 / 开始前需要什么”这类问题应扩展 `process_operation`，还是继续由 `generic_rag` 保守承接。
  - 最小方案：新增 3-5 条真实/合成问题，覆盖 `容易遗漏什么`、`需要提前准备什么`、`有哪些注意事项`；对比规则 route、LLM shadow route、evidence 命中和 fallback answer 质量。
  - 验收：输出 route evolution report，明确是否新增 RouteCatalog terms 或新 route；只有当该 eval 能稳定校准 `route_match/evidence_likely` 后，`_session_intent_route_shadow()` 中硬编码 confidence 才退役。
  - 证据：新增 `Tool.evals.route_evolution.route_evolution_eval_report()`、`tests/test_route_evolution_eval.py` 和 [review-artifacts/route-evolution-prep-readiness.md](review-artifacts/route-evolution-prep-readiness.md)。4 条“容易遗漏 / 准备事项 / 注意事项 / R2 前准备”问题当前规则 route 分布为 `generic_rag: 3`、`process_overview: 1`，结论为 `needs_route_decision`；候选收敛方向是 `process_operation` vs `generic_rag`，生产 route 暂不改。验证 `tests/test_route_evolution_eval.py -q` 通过。
  - 来源：[review-artifacts/router-shadow-diff.md](review-artifacts/router-shadow-diff.md)、[Spec-Chat-Workflow.md](Spec-Chat-Workflow.md)。

- [x] **CHAT-COMP-01 Composer 迁移风险评估** `Highest`
  - 预期功能：在把 `_session_deterministic_answer()` 收敛为 AnswerPlan-driven 前，先确认现有 route-specific 分支在证据不完美时的补救行为不会丢。
  - 最小方案：新增 [dev-memory/composer_migration_risk.md](dev-memory/composer_migration_risk.md)，盘点 `process_operation / process_overview / reference_lookup / stage_transition_work / generic_rag` 等分支的边界行为：无 citation、partial evidence、missing slot、missing quote/context、fallback 输出。
  - 验收：文档明确 `filled / partial / missing` slot 的呈现规则；后续 composer 迁移测试至少覆盖 filled、partial、missing 三类 slot。
  - 证据：新增 [dev-memory/composer_migration_risk.md](dev-memory/composer_migration_risk.md)，按 `process_operation/stage_transition_work/deliverable_detail/tailoring_policy/reference_lookup/generic_rag/table_lookup` 盘点当前行为、迁移风险和保留规则。
  - 来源：[Spec-Chat-Workflow.md](Spec-Chat-Workflow.md)。

- [x] **CHAT-02 Session State / follow-up contract**
  - 预期功能：用户连续追问时，系统能读取上一轮问题、答案摘要、citations 和 source scope history，并判断本轮是否是 follow-up。
  - 最小方案：在 request contract 接收 `session_id/previous_turns`；在 context step 记录 previous question、previous answer summary、selected docs history 和 `is_follow_up`。
  - 验收：连续两问时后端能区分新问题和追问；answer_run context step 展示上一轮摘要、当前 source scope 和 contextual query。
  - 证据：`tests/test_app_api.py::test_session_query_accepts_follow_up_contract` 已覆盖同 source scope 下短追问，前端 `querySession()` 已传入上一轮成功回答摘要和 citations。
  - 来源：[Spec-Chat-Workflow.md](Spec-Chat-Workflow.md)。

- [ ] **CHAT-08 Session Memory Store** `Later`
  - 预期功能：系统可以持久化 session turns、confirmed references、confirmed terms、tool runs 和 source scope history。
  - 最小方案：先把 request-level follow-up context 升级为可写入的最小 turn store。
  - 验收：刷新页面后仍可恢复本 session 的 turns、confirmed references 和 source scope history。
  - 来源：[Spec-Chat-Workflow.md](Spec-Chat-Workflow.md)。

### Phase 2: Parser / RAG 最小必要底座

- [x] **PARSER-MIN-01 当前解析能力 smoke 评估** `Highest`
  - 预期功能：团队可以判断现有 parser 输出是否足够支撑 Release-0 Chat 问答，避免先引入新重依赖。
  - 最小方案：用 `BASE-01` 问题集检查当前 `CanonicalDocument / SectionChunk / source_refs / source_context / quality` 信息是否足够回答普通流程、R2/PO、7.16、R4->R5、QMP、敏捷裁剪和证据缺口问题。
  - 验收：形成失败分类：Chat route/query/answer 可修、chunk/source_context 可修、parser 结构缺口、表格缺口、扫描/OCR 缺口。
  - 证据：新增 `Tool.evals.parser_rag_smoke.release0_parser_rag_smoke_report()` 和 `tests/test_parser_rag_smoke.py`，使用 BASE-01 retrieval cases 对真实 CT/MI/XP parsed canonical 构建 `SectionChunk` 后运行 HybridRetriever 诊断。真实运行结果为 8 条 smoke 中 6 条通过、Recall@8 = 0.75；两个失败 `r0-mi-qmp-deliverable` 与 `r0-xp-agile-tailoring` 均归类为 `chat_route_query_answer_gap`，未发现 `chunk_source_context_gap/parser_structure_gap/table_gap/scanning_ocr_gap`。报告见 [review-artifacts/release0-parser-rag-smoke.md](review-artifacts/release0-parser-rag-smoke.md)。
  - 来源：[Spec-Parser-RAG.md](Spec-Parser-RAG.md)。

- [x] **RAG-01 Evidence Pattern RAG 首切片** `Highest`
  - 预期功能：系统用少量证据模式处理高频专业问答，不为每个垂直术语新增一套流程；QMP、敏捷裁剪等问题能把正确证据排进 top hits。
  - 最小方案：在 RouteCatalog 增加 `route-query-pack-v0.1` 和 domain term pack；强化 `deliverable_detail/tailoring_policy` 的 route-aware evidence scoring；补 `release0-route-rag-smoke-v0.1` runtime smoke。
  - 验收：Release-0 route RAG smoke 的 8 条 BASE-01 case 全部通过，route accuracy 为 1.0；QMP 和 agile tailoring 两个原失败 case 通过；不引入 parser/provider/vector DB 变更。
  - 证据：新增 `Tool.evals.route_rag_smoke.release0_route_rag_smoke_report()`、`tests/test_route_rag_smoke.py` 和 [review-artifacts/release0-route-rag-smoke.md](review-artifacts/release0-route-rag-smoke.md)。真实运行 `release0_route_rag_smoke_report(top_k=8)` 为 `8/8 pass`，`pass_rate = 1.0`，`route_accuracy = 1.0`；相关回归 `tests/test_route_rag_smoke.py tests/test_route_catalog.py tests/test_parser_rag_smoke.py tests/test_release0_smoke_cases.py tests/test_app_api.py tests/test_answer_workflow.py tests/test_retriever_interface.py tests/test_parser_quality_eval.py -q` 为 `69 passed, 1 warning`。
  - 来源：[Spec-Chat-Workflow.md](Spec-Chat-Workflow.md)、[Spec-Parser-RAG.md](Spec-Parser-RAG.md)。

- [x] **RAG-02 Semantic Retriever Azure embedding smoke** `Highest`
  - 预期功能：系统可以用真实 embedding 检查 semantic retrieval 是否补足 lexical retrieval 的中英文混写、缩写和同义表达漏召回问题。
  - 最小方案：给 `VectorRetriever` 注入 Azure `text-embedding-3-small` adapter；先不建向量数据库，按本轮 selected-doc chunks 内存计算 cosine；在 smoke 中比较 `[RuleSection, FullText]` baseline 与 `[RuleSection, FullText, Vector]` semantic-hybrid。
  - 验收：输出 lexical-only vs semantic-hybrid 对比 artifact，至少记录 recall@8、route accuracy、citation drift、embedding endpoint 失败时的 fallback；默认生产检索不因 embedding 不可用失败。
  - 证据：新增 `Tool.retrieval.embeddings.AzureEmbeddingAdapter` 和 `config/azure_embedding_3_small_config.json` 占位配置，真实接入 Azure `text-embedding-3-small`；新增 `Tool.evals.semantic_rag_smoke`，对比 lexical baseline、`[RuleSection, FullText, Vector]` semantic-hybrid 和 route-gated semantic，并用 batch + memory cache 避免重复 chunk embedding 请求。真实报告见 [review-artifacts/semantic-rag-smoke.md](review-artifacts/semantic-rag-smoke.md)：embedding endpoint 可用；lexical baseline recall@8 = `1.0`、route accuracy = `1.0`；semantic-hybrid recall@8 = `0.875`、route accuracy = `1.0`，`r0-mi-r2-po-guidance` 回退，`r0-mi-r2-po-guidance` 和 `r0-ct-section-716-reference` 发生 citation drift；route-gated semantic recall@8 回到 `1.0`，citation drift 降到 `0`。结论：semantic retriever 保持实验开关，不替换生产默认检索；后续只在非 role/reference route 试点。验证 `tests/test_semantic_rag_smoke.py -q` 为 `4 passed`。
  - 来源：[Spec-Parser-RAG.md](Spec-Parser-RAG.md)、[Spec-Chat-Workflow.md](Spec-Chat-Workflow.md)。

- [x] **RAG-03 表格检索诊断 + route-gated semantic retriever** `Highest`
  - 预期功能：团队知道当前 PEP 表格问题的短板在 query rewrite、table chunk、composer 还是 parser/provider，并把 RAG-02 结论落成受 route 保护的 semantic retriever 实验开关。
  - 最小方案：选择 1 个真实 PEP 表格问题，例如交付物责任、owner/approver、行列值查询；分别跑 lexical baseline 与 route-gated semantic-hybrid。Semantic 先只在非 role/reference route 启用，role/reference route 继续使用 lexical/rule baseline，避免 R2/PO 与 7.16 来源定位类问题的 citation drift 进入生产路径。
  - 验收：输出失败分类：`query_rewrite_gap / table_chunk_flattening_gap / table_anchor_gap / composer_table_answer_gap / parser_provider_gap`；记录 route gate 对 recall@8、route accuracy 和 citation drift 的影响；若 semantic 已能召回表格，structured table index 保持 Later。
  - 证据：新增 `Tool.evals.table_retrieval_diagnostic.table_retrieval_diagnostic_report()` 和 [review-artifacts/table-retrieval-diagnostic.md](review-artifacts/table-retrieval-diagnostic.md)。真实 MI PEP 表格问题 `MI PEP 这个表格里 QMP 的交付物责任是什么？` 已命中 `table_lookup`，route-gated semantic 启用，但 selected doc 中 `scoped_table_chunk_count = 0`、table-hit rate = `0.0`，失败分类为 `parser_provider_gap`。同时在 `_table_chunks()` 保持 `SectionChunk.text` 不变的前提下新增 `metadata.table_type / row_labels / column_headers`，并在 `_route_evidence_bonus()` 为 `table_lookup` 增加 row label / table metadata bonus；该路径不改 parser、不改 retriever、不改 embedding。结论：Router/Planner 已能进入表格意图层；已有 TableData 时可以到 table metadata level。后续提醒：当前先不写厚的 PDF pseudo-table detector；等 parser 内容整理干净且真实表格问题仍卡住时，再在 parser 层直接抽取能识别为表格元素的内容，例如 responsibility matrix、deliverable-owner/approver 表和 checklist。验证 `tests/test_table_retrieval_diagnostic.py tests/test_semantic_rag_smoke.py tests/test_section_chunk_retrieval.py tests/test_app_api.py -q` 通过。
  - 来源：[Spec-Parser-RAG.md](Spec-Parser-RAG.md)、[Spec-Chat-Workflow.md](Spec-Chat-Workflow.md)。

- [x] **PARSER-MIN-02 EvidenceSource adapter** `Highest`
  - 预期功能：Chat、citation、AnswerPlan、Claim Verifier 和 Reference UI 使用同一条轻量 evidence view，不再各自拼 parser 零散字段。
  - 最小方案：从当前 `SectionChunk + source_refs + parse quality` 适配出 `evidence_id/document_id/file_name/chunk_id/section_id/heading_path/anchor_label/quote/source_context/quality_warning/usable_as_primary_evidence`。
  - 验收：AnswerPlan slot、citation、claim verifier 和 Reference Card 可通过同一个 `evidence_id` 反查同一段 quote/source_context。
  - 证据：新增 `Tool.workflows.evidence_source.EvidenceSource` 与 `build_evidence_sources()`，`/api/session/query` 现在在 `structured_matches[0].evidence_sources` 和 answer_run execution 输出统一 evidence view，包含 `chunk_id/heading_path/quality_warning/usable_as_primary_evidence`。验证 `tests/test_answer_workflow.py::test_evidence_source_adapter_exposes_stable_reference_view tests/test_app_api.py::test_session_query_exposes_evidence_sources_for_reference_ui -q` 为 `2 passed, 1 warning`。
  - 来源：[Spec-Parser-RAG.md](Spec-Parser-RAG.md)。

- [ ] **PARSER-MIN-03 轻量文档状态与质量警告**
  - 预期功能：系统可以区分整份文档是否可问，以及某些证据是否适合作为 primary evidence。
  - 最小方案：先复用现有 parse summary/review items，输出 `ready / limited / needs_review / ocr_required / failed` 和 evidence-level warning；暂不实现完整 Review Gate 状态机。
  - 验收：`needs_review` 不再等同于整份文档不可问；低置信表格/视觉/OCR 内容不会混入 primary evidence。
  - 来源：[Spec-Parser-RAG.md](Spec-Parser-RAG.md)。

### Phase 3: UI Workspace 主体验

- [ ] **UI-01 Source Intake 基线**
  - 预期功能：用户进入 Source Intake 后，可以看到所有可用资料、当前选中的资料、解析状态和质量提示，并能切换本轮问答的 source scope。
  - 最小方案：左侧 Resource/Source 区提供上传入口、recent runs、文件级 source cards、parse status、quality chip 和本轮勾选 scope。
  - 验收：Source 默认文件级；用户能清楚看到哪些资料可问、哪些资料已选、哪些资料有解析风险；上传后的资源能自然进入左侧资源列表并用于下一轮 Chat。
  - 来源：[Spec-UI-Workspace.md](Spec-UI-Workspace.md)。

- [ ] **UI-02 Ask Workspace v2** `Highest`
  - 预期功能：用户可以在一个干净的问答工作区中选择资料、连续提问、查看引用，并展开可读原文上下文。
  - 最小方案：左侧 resource/source scope，中间 transcript + composer，右侧 Reference 查看区；debug/admin 信息移出普通主路径。
  - 验收：连续两问、citation 点击、右侧 Reference 默认显示文件/页码/quote，选中引用可展开完整原文、前文和后文；普通问答路径不展示 JSON/debug/admin。
  - 来源：[Spec-UI-Workspace.md](Spec-UI-Workspace.md)。

- [ ] **UI-03 Review Gate 页面**
  - 预期功能：用户或开发者可以集中查看低置信 block、table、visual candidate、quality gates 和 evidence preview，并决定哪些内容需要修复或排除。
  - 最小方案：展示 parse status、quality gates、Review Queue、Visual/Table candidates、Evidence preview。
  - 验收：普通文档可先进入 Ask Workspace；风险项可进入 review；review/debug 信息不打断普通问答。
  - 来源：[Spec-UI-Workspace.md](Spec-UI-Workspace.md)。

- [ ] **UI-04 Admin / JSON Lab 页面**
  - 预期功能：开发者可以查看 raw handoff、parse workflow、blocks/chunks JSON、tool traces、eval reports 和 static snapshot export。
  - 最小方案：把 handoff、parse artifacts、answer_run/tool trace、eval report 集中到 Admin / JSON Lab。
  - 验收：开发调试能力保留；普通 Ask Workspace 不被内部 JSON 和 skipped tool reason 污染。
  - 来源：[Spec-UI-Workspace.md](Spec-UI-Workspace.md)。

### Phase 4: Release-0 真实闭环 Smoke

- [ ] **R0-01 单文档可信问答 smoke** `Highest`
  - 预期功能：选中单个 PEP 后，用户能得到只基于该文档的可信回答和可展开引用。
  - 最小方案：对 CT / MI / XP 分别测试流程如何操作、R2/PO、7.16。
  - 验收：route、tool plan、citations、answer plan、self/claim check 都写入 answer_run；Reference 不串文档。

- [ ] **R0-02 高频专业问题 smoke** `Highest`
  - 预期功能：R4->R5、QMP、敏捷裁剪这三类高频专业问题可以走 catalog route，并输出按问题形态组织的答案。
  - 最小方案：覆盖 `stage_transition_work/deliverable_detail/tailoring_policy` 三类 route。
  - 验收：引用来自当前选中文档；缺证据时明确提示；slot map 不退回章节罗列。

- [ ] **R0-03 未知问题 fallback smoke**
  - 预期功能：不在 catalog 的真实业务问法也能走 `generic_rag`，给出有引用、有边界的回答。
  - 最小方案：选择 1-2 个未知问题，记录 fallback reason、retrieved evidence、uncertainty 和 citation coverage。
  - 验收：fallback 输出可读短结论、引用和不确定性；失败样本进入 route evolution eval。

- [ ] **R0-04 多文档 / BU 对比 smoke**
  - 预期功能：用户选择多份资料时，系统能按文档分组引用，并区分相同点、差异点和证据缺口。
  - 最小方案：对 CT / MI / XP 询问同一阶段、交付物或评审要求的差异。
  - 验收：回答按文档分组 citation；source scope 不串线；unsupported comparison 被标记为证据缺口。

## 4. 验收节奏

- 每完成 1 个模块切片，先跑对应窄测试。
- 每完成 2-3 个相关任务，跑一次 `pytest` 相关子集和 `App/web npm run build`。
- Parser/Chat 涉及真实质量时，补一条 eval 或 smoke case。
- UI 涉及主流程时，补浏览器 smoke 和截图检查。
- 文档或状态变化后，同步 [dev-memory/SESSION-WIP.md](dev-memory/SESSION-WIP.md) 与 [../CHANGELOG.md](../CHANGELOG.md)。

## 5. Later / Backlog

- [ ] **LATER-00 完整 DocumentBlock / RAG artifacts bundle** `Later`
  - 预期功能：每份解析后的文档都有稳定 `document.md / blocks.json / chunks.json / quality_report.json`，供 Review Gate、Admin、多 provider 对比和长期 RAG 复用。
  - 触发条件：`PARSER-MIN-01` 证明当前 parsed canonical/chunks/source_refs 难以稳定支撑引用回跳、表格定位、多 provider 对比或 UI 文档审阅。

- [ ] **LATER-01 Persistent vector DB / embedding cache** `Later`
  - 预期功能：系统可以复用持久 chunk index 和 embedding cache 提升多文档检索能力。
  - 触发条件：Release-0 selected-doc lexical/hybrid smoke 稳定后再启动。

- [ ] **LATER-02 Docling / Marker / MinerU provider 评估** `Later`
  - 预期功能：当现有 pypdf / DOCX XML 主路径被真实数据证明不够用时，可以按失败类型评估结构化 provider，而不是直接把重依赖纳入主链路。
  - 当前判断：2026-06-24 起完整 parser 升级保持 Later；本周不改 parser 主路径，优先做 Router 2.0、Semantic RAG 和表格检索诊断。
  - 触发条件：扫描件或图片型 PDF 进入主数据源；pypdf/DOCX XML 无法提供可核查 anchor；表格/reading order/layout 问题经 `RAG-03` 证明无法靠 query rewrite、semantic retrieval 或 table-aware chunk metadata 修复；评估前确认 Windows、芯片/本地部署、安装体积、许可证、离线可用性和运行成本。

- [ ] **LATER-03 OCR/VLM crop pipeline 真实依赖评估** `Later`
  - 预期功能：图片、图表和扫描内容可以进入 visual candidate review，再决定是否进入 evidence。
  - 触发条件：Review Gate 有稳定 visual candidate UI 后再接真实依赖。

- [ ] **LATER-04 Graph / 关系抽取 contract** `Later`
  - 预期功能：从真实 chunk signals / relations 生成可解释图谱。
  - 触发条件：block/chunk/citation contract 稳定后启动。

- [ ] **LATER-05 导出与集成能力** `Later`
  - 预期功能：支持 GitHub Pages static snapshot、Feishu、HTML、Mermaid、PPT 导出，以及 SharePoint / Blob / 权限接入。
  - 触发条件：Release-0 问答闭环和 artifact contract 稳定后拆分独立任务。

## 6. 收尾规则

- [ ] 系统级任务完成后，在本文件勾选并写一句证据。
- [ ] 模块级设计变化写回对应 Spec。
- [ ] 真实验证结果写入 changelog，计划性想法留在 TODO/Spec。
- [ ] 跨会话状态变化写入 [dev-memory/SESSION-WIP.md](dev-memory/SESSION-WIP.md)。
- [ ] 历史文档如果被新 Spec 完整吸收，先在 README 标注 superseded，再按用户确认移动归档。