# QT Wiki System TODO

更新时间：2026-06-23
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

下一阶段主线是 Release-0 可信 NotebookLM-like 问答闭环。当前执行顺序明确为：先用 `BASE-01` 定尺子，再推进 Chat 的 RouteCatalog / generic fallback / AnswerPlan / Session State；Parser 先评估现有解析能力是否够用，只补轻量 EvidenceSource adapter；UI 围绕稳定 contract 做普通用户主路径减噪。Claim Verifier 先作为后续薄 guardrail，不作为当前主路径阻塞项。

```text
BASE-01 smoke 问题集
  -> Chat 用 RouteCatalog / generic fallback 规划回答
  -> evidence / citation / session state 守住事实边界和追问上下文
  -> 现有解析结果通过 EvidenceSource adapter 供 Chat 稳定消费
  -> UI 展示回答、引用、质量摘要
  -> CT / MI / XP smoke 证明可用
```

三份 Spec 到 TODO 的映射：

| Spec | 关键设计 | TODO 主线 |
| --- | --- | --- |
| [Spec-Parser-RAG.md](Spec-Parser-RAG.md) | Notebook-like 自动解析、DocumentBlock、RAG artifacts、表格/图片质量状态 | 当前只落 `PARSER-MIN-*`：评估现有 parser、补 EvidenceSource adapter；完整 artifacts/provider 后置。 |
| [Spec-Chat-Workflow.md](Spec-Chat-Workflow.md) | 8 步 runtime、RouteCatalog、generic fallback、AnswerPlan、Claim Verifier、Session Memory | `CHAT-*` 产出可审计回答链路。 |
| [Spec-UI-Workspace.md](Spec-UI-Workspace.md) | Source Intake / Review Gate / Ask Workspace / Admin | `UI-*` 产出普通用户主路径和开发调试路径分离的工作台。 |

### 1.1 当前最高优先级

| 顺序 | 任务 | 优先级判断 |
| --- | --- | --- |
| 1 | `PARSER-MIN-02` | 把 Chat、citation、AnswerPlan、Reference 统一到轻量 EvidenceSource view，减少字段散拼。 |
| 2 | `PARSER-MIN-03` | 输出文件级/evidence-level 质量状态，让 UI 能稳定表达已解析、待复核、不可作为 primary evidence。 |
| 3 | `UI-01` / `UI-02` | 继续把上传、资源选择、连续提问、Reference 和 Note 做成普通用户主路径；debug/admin 进入后续页面。 |
| 4 | `R0-01` / `R0-02` / `R0-03` / `R0-04` | 用真实 CT / MI / XP smoke 证明单文档、高频问题、未知 fallback 和多文档对比可用。 |
| 5 | `CHAT-07` | 后续薄 Claim Guardrail，只检查高风险事实句和引用覆盖，不做厚同步二次 RAG。 |

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

- [ ] **CHAT-05 LLM structured Router schema harness**
  - 预期功能：真实 LLM 接入前，系统可以用 fixture/mock 验证 `intent-route-v0.2` 的结构化输出、校验规则和降级路径。
  - 最小方案：校验 route 是否存在、confidence、entities、evidence_needs、answer_slots 和 fallback_reason。
  - 验收：R4/R5、QMP、敏捷裁剪和未知问题 fixture 通过 schema；非法 route 或低置信输出降级到 `generic_rag`。
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

- [ ] **PARSER-MIN-02 EvidenceSource adapter** `Highest`
  - 预期功能：Chat、citation、AnswerPlan、Claim Verifier 和 Reference UI 使用同一条轻量 evidence view，不再各自拼 parser 零散字段。
  - 最小方案：从当前 `SectionChunk + source_refs + parse quality` 适配出 `evidence_id/document_id/file_name/chunk_id/section_id/heading_path/anchor_label/quote/source_context/quality_warning/usable_as_primary_evidence`。
  - 验收：AnswerPlan slot、citation、claim verifier 和 Reference Card 可通过同一个 `evidence_id` 反查同一段 quote/source_context。
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
  - 预期功能：当现有 parser 不够用时，可以按失败类型评估结构化 provider，而不是直接把重依赖纳入主链路。
  - 触发条件：`PARSER-MIN-01` 发现 reading order、layout、表格、中文复杂 PDF、扫描件或公式/图片是 Release-0 阻塞；评估前确认 Windows、芯片/本地部署、安装体积、许可证、离线可用性和运行成本。

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