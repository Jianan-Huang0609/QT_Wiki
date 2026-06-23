# Spec: Chat Workflow / Agent Runtime 改造

更新时间：2026-06-23
状态：Active Spec
上层入口：[TODO.md](TODO.md)
吸收来源：[old/Gate6-Adaptive-Answer-Workflow-Plan.md](old/Gate6-Adaptive-Answer-Workflow-Plan.md)、[old/Todo+Spec-流程问答工作台.md](old/Todo+Spec-流程问答工作台.md)、[old/Tool-Parser-RAG-Fusion-Spec.md](old/Tool-Parser-RAG-Fusion-Spec.md)

## 1. 目标

把当前 session chat 从“规则检索 + 模板回答”升级为 workflow-first 的 Chat Runtime：

```text
User Question
  -> Input Normalization
  -> Intent Recognition
  -> Route / Plan
  -> Tool Execution
  -> Evidence Package
  -> Answer Composer
  -> Answer Eval
  -> Session Memory
```

目标体验：用户在 Ask Workspace 中提问时，系统能识别意图、选择工具、执行检索或表格查询、生成带引用的答案，并显示可审计 Answer Run。

当前优先级：先修 citation、source scope、intent 和 answer_run 的可信度，再扩展更复杂的 agent 工具。Chat 的“思考过程”在 UI 中表现为可审计执行摘要：intent、route、tool calls、evidence coverage、missing evidence 和 eval summary。

2026-06-17 追加体验约束：Ask Workspace 要贴近 NotebookLM 的主问答体验。默认界面让位给自然语言答案和可点击引用；Answer Run 只显示一行可审计摘要，详细 1-6 步折叠起来。回答质量以“识别用户想要的答案形态”为第一优先级：操作办法、概念解释、原文定位、多文档对比、证据缺口检查必须进入不同 route，不能都回落成 section 摘要列表。引用应尽量是 passage/block 级原文片段，支持右侧查看上下文。Runtime 不能把流程类文档默认等同于 PEP；PEP、SOP、WI、规范、规程等都只是文档类型或用户术语，route/prompt 必须使用当前文档和流程文档的通用口径。

### 1.1 Chat Runtime v0.2 八步链路

Chat Runtime 的正式目标骨架采用 8 步 workflow，作为后续 `ChatWorkflowRunner`、Tool Registry、Answer Planner 和 UI 审计摘要的共同 contract：

```text
1. Receive Input
  user_message, session_id, selected_document_ids, mode

2. Read Session State
  previous_question, selected documents, follow-up detection, source scope history

3. Intent Router
  definition, process, evidence, comparison, summary, table lookup, parse quality, tool request

4. Query Rewrite
  rewrite natural language question into retrieval-ready query and route-specific terms

5. Tool Plan
  choose section search, fulltext, vector, table lookup, direct read, reference context

6. Evidence Package
  collect quote, anchor, source_ref, supports, source_context, missing evidence

7. Answer Planner
  fill route-specific slots with evidence; mark missing slots as evidence gaps

8. Claim Verifier + UI
  verify factual support, citation coverage and missing-evidence handling; render answer, citations and process summary
```

### 1.2 当前差距矩阵

| Step | 目标状态 | 当前实现 | 差距判断 |
| --- | --- | --- | --- |
| 1. Receive Input | 显式接收 `user_message/session_id/selected_document_ids/mode` | `/api/session/query` 接收 `question/source_scope/use_llm/model_profile/top_k`；`selected_document_ids` 包在 `source_scope.document_ids` 中 | 部分完成；缺 `session_id` 和更清晰的 `mode` 枚举。 |
| 2. Read Session State | 读取上一轮问题、已选文档、是否追问、source scope history | 前端有 chat transcript；后端每次请求 stateless，memory step 为 `deferred` | 明显缺口；需要 Session Memory Store / turn store。 |
| 3. Intent Router | LLM-first structured router + 轻量 Route Catalog，覆盖定义、流程、证据、对比、总结、表格查询等 route | `parse_question_intent()` + `_session_route_plan()` 已覆盖 `process_overview/process_operation`、`stage_transition_work`、`deliverable_detail`、`tailoring_policy` 等首批 route | 部分完成；当前仍偏规则/函数式 route，需要收敛为 LLM Router 输出结构化 JSON，再由 Route Catalog 与 verifier 守住边界。 |
| 4. Query Rewrite | 按 route 改写检索查询，避免硬编码某类文档 | `_session_retrieval_question()` 已为流程总览/操作生成 route-specific query，已去 PEP 默认假设 | 部分完成；需要输出结构化 rewrite object，并覆盖 table/comparison/reference/gap。 |
| 5. Tool Plan | 结构化决定 section search/fulltext/vector/table/direct read | 当前执行固定 `HybridRetriever([RuleSectionRetriever, FullTextRetriever])`，tool_calls 是摘要；direct reference context 已内嵌 | 部分完成；缺正式 Tool Registry、vector 持久索引、table lookup、direct read tool。 |
| 6. Evidence Package | 整理 quote、anchor、source_ref、supports、source_context | `AnswerEvidencePackage`、citation validation、passage selector、`source_context` 已可用 | 基本完成首版；缺 claim-level `supports` 矩阵和跨工具 evidence schema。 |
| 7. Answer Planner | LLM-first planner 生成 slots，Route Catalog 只提供轻量策略；slot 必须绑定 evidence，无证据标缺口 | `answer-plan-v0.1` 已为 `process_operation`、`stage_transition_work`、`deliverable_detail`、`tailoring_policy` 生成首批 slots | 部分完成；需要把 route-specific 函数式 slot map 收敛为“LLM planner + schema + verifier”的通用机制。 |
| 8. Claim Verifier + UI | 检查事实支持、citation coverage，并在 UI 展示答案/引用/过程摘要 | UI 已显示思考摘要、引用、source context；`self_check` 是启发式摘要 | 部分完成；缺真正 claim verifier / groundedness eval / unsupported claim 标记。 |

阶段判断：当前整体约 **5/8 可用**。`1/3/4/5/6/8` 已有可运行首版，`2/7` 是主要结构缺口，`3/7` 的下一步方向从“继续手写更多 route 函数”收敛为“LLM-first structured router/planner + 轻量 route catalog + evidence/citation verifier”。

### 1.3 2026-06-22 设计收敛：LLM-first Router / Planner

今天的关键判断：Chatbox 只保留一个统一 runtime，8 步 workflow 是固定骨架；变化点放在 `Intent Router`、`Query Rewrite`、`Tool Plan` 和 `Answer Planner` 的策略层。

实际设计采用三层组合：

1. **LLM-first structured router / planner**
  - LLM 读取用户问题、当前 source、上一轮问题和轻量 route catalog。
  - 输出结构化 JSON：`primary_route`、`secondary_routes`、`confidence`、`entities`、`needs_previous_context`、`evidence_needs`、`answer_slots`。
  - LLM 负责自然语言理解、多意图拆分、追问判断和未知问题的动态规划。

2. **Known Route Catalog**
  - 系统只维护少量高频/高风险 route 的轻量策略。
  - route catalog 像菜单和约束，不接管整套回答流程。
  - 每个 route 只定义：适用语义、检索提示词、证据偏好、建议 answer slots、风险等级和 citation 要求。

3. **Deterministic Guardrails / Verifier**
  - 程序负责 source scope、citation、quote、anchor、evidence support、missing evidence 和 unsupported claim。
  - 这些质量门保持稳定、可测试、可回归。
  - LLM 的 route/planner 输出必须通过 schema validation 和 route catalog 校验后才进入检索和回答。

这个设计让系统同时具备两种能力：常见流程文档问题有稳定质量边界，新问题可以由 LLM 泛化理解后进入 generic RAG fallback。

### 1.4 设计边界

Route 的目标是提升检索和证据组织质量；Route 不是一套独立 runtime。

Route 固化的内容：

- 问题属于哪类任务。
- 需要寻找哪些证据。
- 检索 query 如何扩展。
- 回答需要哪些槽位。
- 哪些 claim 必须有 citation。

Route 保持开放的内容：

- 用户自然语言表达。
- 多意图组合。
- 最终回答措辞。
- 新问题的动态 answer slots。

新增 route 的触发条件：高频问题、高风险合规/责任问题、或真实 eval/smoke 中反复失败的问题。普通新问题进入 `generic_rag`，由 LLM planner 动态生成 slot，并由 verifier 限制 unsupported claim。

### 1.5 2026-06-23 辩证判断：薄 RouteCatalog + 泛化 Router

今天的设计判断进一步收敛为：**所有问题都经过统一 Router / Planner 步骤，但不是所有问题都固化为固定 route**。

企业内部文档问答和普通聊天不同，关键目标不是“生成一段像答案的文字”，而是：回答只基于当前 source scope；citation 能定位到文件、页码/章节、quote；证据不足时能说明缺口；多轮追问能继承上下文；反复失败的问题能进入 eval 和 route evolution，而不是每次临场发挥。因此 Chat Runtime 需要比普通 `question -> retrieve -> prompt -> answer` 多一层可审计规划：

```text
question
  -> intent / route
  -> query rewrite
  -> tool plan
  -> evidence package
  -> answer plan
  -> claim verifier
  -> answer + citations
```

这个方向本身合理，但有两类风险需要持续约束：

- **过度设计风险**：每来一种问法就新增 route、query rewrite、rerank bonus、answer slots 和 fallback composer，系统会滑向难维护的专家规则库。Route Catalog 只吸收高频、高风险、反复失败或合规责任强的问题。
- **粗糙设计风险**：把理解、规划、引用、证据充足性都交给 LLM 自由发挥，会形成好看的 NotebookLM 仿品，但 citation、source scope、missing evidence 和 unsupported claim 缺少稳定质量门。LLM 输出必须经过 schema validation、catalog 校验和 evidence/citation/claim verifier。

最小可持续框架是：

```text
固定 8 步可信链路
  + LLM 泛化理解和动态 slot 规划
  + 少量 Known Route Catalog
  + deterministic source / citation / evidence / claim guardrails
  + generic_rag fallback
  + 失败样本驱动 route evolution eval
```

`RouteCatalog` 的定位是“薄约束层”，而不是新 runtime。它只保存 route 的适用语义、证据需求、query terms、slot 建议、风险级别和 citation 要求。LLM Router / Planner 负责自然语言泛化、多意图组合和动态 slot；程序负责校验 route、source scope、evidence binding、citation、missing evidence 和 claim support。

`generic_rag` 不是随便兜底。它的固定输出目标是：短结论、支撑证据、不确定性/缺口、可追溯引用。低置信 route、未知问题、LLM 输出 schema 不合法或 catalog 不包含的问题，都进入 `generic_rag`，并把失败样本写入 eval。反复失败的问题再沉淀为 Route Catalog entry。

### 1.6 企业 NotebookLM-like RAG 的剩余能力缺口

为了让 QT Wiki 成为可信的企业内部文档 NotebookLM-like 工作台，而不是只做 selected-doc chat，还需要补齐以下能力：

- **Session State / Follow-up**：后端需要读取上一轮 question、answer 摘要、citations 和 source scope history，支持“那 QMP 呢？”这类追问。
- **RouteCatalog 抽象**：当前 route 信息散在 `parse_question_intent()`、`_session_route_plan()`、query rewrite、rerank bonus 和 AnswerPlan slot map 中，需要先做减法式抽取。
- **Generic RAG fallback eval**：未知问题必须也能返回有引用、有边界、有不确定性提示的回答；fallback 质量需要 eval 固定。
- **Claim Verifier**：citation validation 只能证明引用字段可信，还需要 claim-level 检查，验证回答中的责任、必须、不可裁剪、评审结论是否被 quote/source_context 支持。
- **Route Evolution Loop**：把用户反复追问、LLM 答偏、多轮不准的问题记录为 eval case，再判断该修 catalog、query rewrite、retrieval、answer planner、parser artifact 还是 source selection。
- **Table / Figure / Structured Block tools**：企业流程答案常在表格、矩阵、责任表和交付物清单中；后续需要 block-aware retrieval、table lookup、cell-level citation 和 parse quality tool。

因此，下一步的 `CHAT-02B` 不应直接上完整 agent 平台，而应按三步落地：先抽薄 RouteCatalog；再补 `generic_rag` fallback contract + eval；最后接 LLM structured router / planner schema 和真实模型。

## 2. 当前问题

- `/api/session/query` 已有 selected-doc source scope，但实现仍集中在 API 函数里，难以测试和扩展。
- runtime input contract 缺少显式 `session_id`、`selected_document_ids` 和 `mode` 字段，当前靠 `source_scope` 和前端状态隐式表达。
- 后端没有读取上一轮 question / answer / source history，无法真正判断 follow-up。
- `QuestionIntent` 已有规则 baseline，但没有 route / plan contract。
- session query 已接入 `HybridRetriever([RuleSectionRetriever, FullTextRetriever])` 首切片；当前是 parsed canonical JSON -> runtime `SectionChunk[]` -> lexical hybrid RAG，不是持久化向量数据库。下一步需要补 direct source context、retriever config / Tool Registry，并补 R2/PO、7.16、BU diff eval。
- `use_llm` 在 session query 主链路里没有真正决定 answer composer。
- `answer_run` 已有六步结构，但 execution/tool calls 仍是静态摘要。
- memory step 仍是 `deferred`，前端 pin-ready 没有 durable store。
- citation 当前是最高风险点：可能出现旧 handoff/source scope 串线、quote 缺失、History/template change 误入 primary evidence、回答事实和引用不匹配。
- Reference Viewer 当前只展开 quote 和定位字段，还缺同文档相邻 chunk / section excerpt 前后文，用户难以判断引用是否完整支撑答案。
- Answer Planner 还没有独立结构；目前流程操作答案由 deterministic composer 直接组织，缺少 slot -> evidence -> missing gap 的中间产物。
- Claim Verifier 还停留在 `self_check` / answer eval 方向，尚未按事实句生成 claim support report。

## 3. ChatWorkflowRunner

新增独立 runtime：

```python
run_chat(
    question: str,
    source_scope: dict,
    session_id: str | None,
    use_llm: bool,
    top_k: int,
) -> ChatRunResult
```

`ChatRunResult` 输出：

- `answer_text`
- `confidence`
- `citations`
- `matched_sections`
- `evidence_package`
- `answer_run`
- `suggested_questions`
- `trace`
- `memory_write`

`ChatRunInput` 首版建议显式化为：

```json
{
  "user_message": "PEP 文档的流程如何操作？",
  "session_id": "session-...",
  "selected_document_ids": ["doc-..."],
  "mode": "selected_docs|all_sources|follow_up|table_lookup|compare",
  "use_llm": false,
  "model_profile": "azure-gpt-4o",
  "top_k": 8
}
```

API 仍返回兼容 `ChatQueryResponse`。

### 3.1 Citation Integrity Rules

- retrieval hit 进入 answer 前必须生成 `AnswerEvidencePackage`。
- citation 只能从 evidence package 派生，不能由 answer composer 临时拼接。
- citation 必须校验 `document_id/file_name/source_scope/quote/anchor_label/block_id or section_id`。
- citation 的 `quote` 优先来自与问题命中词最相关的 passage，而不是 section 开头或标题 fragment。
- passage selector 需要过滤短标题、表格碎片和重复章节标题前缀，避免 Reference Card 展示不可读的 parser 噪音。
- selected docs 模式下，citation 的 document_id 必须属于 request source scope。
- History/template change 可以作为版本背景，不作为 primary evidence。
- citation 校验失败时，answer_run generation step 返回 `failed` 或 `warning`，并说明缺失字段。

## 4. Intent / Route Contract

### 4.1 Router 分层

Router 采用四层串联：

```text
Entity Pre-router
  -> Known Route Catalog Matcher
  -> LLM Semantic Router
  -> Generic RAG Fallback
```

1. **Entity Pre-router**
   - 用轻量规则抽取稳定实体：`R1/R2/R3/R4/R5`、`QMP/PMP/PEP/RA`、`review/tailoring/agile/validation/design transfer`、`owner/responsible/author/content/shall/must`。
   - 输出实体和提示信号，供 LLM Router 与 Query Rewrite 使用。

2. **Known Route Catalog Matcher**
   - 根据实体、动词、问法和 source 类型给出候选 route。
   - catalog 只保存少量高频/高风险 route，避免 route registry 膨胀。

3. **LLM Semantic Router**
   - 读取用户问题、session state、上一轮引用摘要、候选 route catalog。
   - 输出结构化 JSON；系统只接受 schema 合法且 route 存在的结果。
   - 支持多 route：例如同一问题同时命中 `deliverable_detail` 和 `tailoring_policy`。

4. **Generic RAG Fallback**
   - route 置信度低、问题新、或 LLM 输出无法通过 schema 校验时使用。
   - 通用流程：识别问题对象 -> broad query rewrite -> hybrid retrieval -> evidence package -> conclusion / evidence / uncertainty。

### 4.2 LLM Router 输出 schema

```json
{
  "schema_version": "intent-route-v0.2",
  "primary_route": "stage_transition_work",
  "secondary_routes": ["gap_check"],
  "confidence": 0.82,
  "entities": ["R4", "R5"],
  "question_type": "stage transition work",
  "needs_previous_context": false,
  "evidence_needs": ["entry criteria", "exit criteria", "deliverables", "review readiness"],
  "answer_slots": ["transition_scope", "work_items", "reviews_deliverables", "exit_readiness"],
  "fallback_reason": ""
}
```

Schema 规则：

- `primary_route` 必须来自 Route Catalog；未知 route 降级为 `generic_rag`。
- `confidence < 0.62` 时进入 `generic_rag` 或请求澄清。
- `needs_previous_context=true` 时，Read Session State 必须附带上一轮问题、答案摘要和上一轮 citations。
- `answer_slots` 可以来自 catalog，也可以由 LLM planner 动态补充；动态 slot 必须经过 AnswerPlan schema 校验。

### 4.3 Route Catalog 首版

| route_id | 适用问题 | 默认 evidence needs | 默认 answer slots |
| --- | --- | --- | --- |
| `process_operation` | 流程如何操作、怎么做、步骤是什么 | scope、operation sequence、deliverables、reviews、verification | `scope_applicability`、`operation_sequence`、`deliverables_reviews`、`verification_validation` |
| `stage_transition_work` | R4 到 R5、阶段转换、进入下一阶段前要完成什么 | entry/exit criteria、work items、deliverables、review readiness | `transition_scope`、`entry_inputs`、`work_items`、`reviews_deliverables`、`exit_readiness` |
| `deliverable_detail` | QMP/PMP/计划/报告包含什么、谁写、谁批准 | deliverable definition、content requirements、owner/author、review/approval | `deliverable_scope`、`required_contents`、`owner_author`、`review_approval` |
| `tailoring_policy` | 敏捷裁剪、哪些评审可裁剪、哪些不可裁剪 | tailoring condition、mandatory review、approval evidence、non-tailorable boundary | `agile_applicability`、`tailorable_reviews`、`non_tailorable_reviews`、`approval_evidence` |
| `reference_lookup` | 找原文、定位某条要求 | exact quote、anchor、section/page、source context | `reference_target`、`source_location`、`original_quote` |
| `table_lookup` | 查表、矩阵、角色表、交付物表 | table block、row/column/cell、nearby heading | `table_scope`、`matched_rows`、`cell_evidence` |
| `bu_comparison` | 多 BU/多文档差异 | aligned evidence rows、per-doc citations、difference type | `comparison_scope`、`same_points`、`differences`、`open_gaps` |
| `gap_check` | 缺什么、是否满足、还没准备什么 | expected requirements、available evidence、missing evidence | `expected_items`、`available_evidence`、`missing_gaps`、`risk_note` |
| `summary_request` | 总结文档/章节/主题 | representative sections、source coverage、limitations | `summary_scope`、`key_points`、`source_coverage` |
| `generic_rag` | 新问题、低置信 route、未知意图 | broad retrieved evidence、best citations、uncertainty | `short_answer`、`supporting_evidence`、`uncertainty` |

### 4.4 Route Catalog entry shape

```json
{
  "route_id": "deliverable_detail",
  "description": "Ask what a deliverable contains and who owns it.",
  "entity_hints": ["QMP", "PMP", "plan", "report", "deliverable"],
  "query_terms": ["content", "owner", "responsible", "author", "review", "approval"],
  "answer_slots": ["deliverable_scope", "required_contents", "owner_author", "review_approval"],
  "evidence_policy": "high_citation_density",
  "risk_level": "process_compliance",
  "requires_citation": true,
  "requires_missing_evidence_note": true
}
```

Route Catalog 的职责：提供约束、提示和验收维度。最终问题理解和 slot 组合由 LLM Router / Planner 生成。

### 4.5 Route 演化规则

新增 route 的来源：

- 高频真实用户问题。
- 高风险合规、责任、评审、裁剪、交付物问题。
- `generic_rag` 或现有 route 在 eval/smoke 中反复失败。
- LLM Router 经常输出相似 `evidence_needs` 和 `answer_slots` 的问题簇。

新增 route 前先写一条 eval case：用户问题、source scope、期望 route、期望 evidence needs、最低 citation 要求。Route 进入 catalog 后，仍然复用统一 8 步 runtime。

## 5. Tool Registry

首版工具：

| 工具 | 输入 | 输出 |
| --- | --- | --- |
| `hybrid_retrieve_blocks` | question, source_scope, top_k | RetrievalResult |
| `direct_section_read` | document_id, section_id | blocks / chunks |
| `table_lookup` | question, source_scope | table blocks / cell refs |
| `compare_documents` | question, document_ids | aligned evidence rows |
| `get_parse_quality` | document_ids | parse status / quality gates |
| `get_reference_context` | citation ids / block ids | source snippets |
| `build_answer_evidence_package` | RetrievalResult, intent | AnswerEvidencePackage |
| `validate_citations` | evidence_package, source_scope | citation validation report |
| `normalize_enterprise_terms` | question, chunks/signals | normalized stages / roles / deliverables |
| `memory_pin` | session_id, answer/ref | memory write result |

`get_reference_context` 首切片可以先在 `/api/session/query` 内实现为 citation enrichment：从本轮已构建的 chunks 中找到命中 chunk，返回 bounded `source_context`，包含 `context_before`、`context_text`、`context_after`、`chunk_id`、`section_id` 和 anchor 摘要。后续抽成正式 Tool Registry，再替换为 persisted chunk index / block store。

Tool 执行规则：

- 工具输出必须结构化。
- 每个 tool call 写入 answer_run execution step。
- 失败不静默吞掉，进入 `status=warning` 和 trace。
- 外部数据都按不可信输入处理，进入 schema validation。

## 6. Answer Run Contract

当前六步保留，但改为真实 runner 状态：

```text
input -> context -> planning -> execution -> generation -> memory
```

每步字段：

```json
{
  "step_id": "execution",
  "label": "执行",
  "status": "done|warning|failed|deferred",
  "summary": "已完成 hybrid retrieval 和 evidence package 构建。",
  "inputs": {},
  "outputs": {
    "intent_type": "role_action_guidance",
    "route_type": "rag_guidance",
    "tool_calls": ["hybrid_retrieve_blocks", "build_answer_evidence_package"],
    "evidence_count": 5,
    "citation_count": 5,
    "missing_evidence_count": 1
  }
}
```

UI 展示的是可审计过程摘要，不展示逐字内部思维链。

## 7. Answer Planner / Composer

Answer 生成分三层：

```text
LLM Answer Planner
  -> Evidence-bound AnswerPlan
  -> LLM or deterministic Composer
```

### 7.1 LLM Answer Planner

Planner 读取 `IntentRoute`、`Route Catalog entry`、`EvidencePackage` 和 `source_context`，输出结构化 `AnswerPlan`。

```json
{
  "schema_version": "answer-plan-v0.2",
  "route_id": "deliverable_detail",
  "answer_style": "concise_numbered",
  "slots": [
    {
      "slot_id": "required_contents",
      "label": "QMP 需要包含哪些内容",
      "status": "filled",
      "evidence_ids": ["e1", "e2"],
      "citation_ids": ["c1", "c2"],
      "draft_points": ["..."],
      "missing_reason": ""
    }
  ],
  "missing_evidence": [],
  "must_cite_claims": ["QMP content", "QMP owner"],
  "style_constraints": ["short conclusion", "no debug trace in answer body"]
}
```

Planner 规则：

- slot 可以来自 route catalog，也可以由 LLM 动态补充。
- filled slot 必须绑定 `evidence_ids` 和 `citation_ids`。
- 缺证 slot 保留在 `missing_evidence`，composer 必须在答案中温和提示。
- `must_cite_claims` 进入 Claim Verifier，确保责任、必须、不可裁剪、评审结论有原文支持。

### 7.2 Composer

两层 composer：

- LLM composer：只消费 `AnswerPlan + citations + source_context + AnswerStyle`。
- deterministic fallback：根据同一 `AnswerPlan` 输出短结论、证据摘要、缺口说明和引用。

LLM prompt 常驻约束：

- 基于 evidence package 和 AnswerPlan 回答。
- 关键事实带 citation。
- 证据不足时说明缺口。
- 保留公司流程原始术语。
- History/template change 只作为版本背景。
- 回答正文聚焦用户问题，过程摘要交给 UI disclosure。

### 7.3 AnswerStyle

AnswerPlan 决定“证据如何组织”，AnswerStyle 决定“chatbox 如何阅读”。

首版 style：

| style | 使用场景 | 展示口径 |
| --- | --- | --- |
| `concise_numbered` | 操作步骤、阶段转换、交付物责任 | 短结论 + 连续编号 + 每项 citation |
| `compact_comparison` | 可裁剪/不可裁剪、BU 对比 | 两组或多组对照，避免长嵌套列表 |
| `quote_first` | 原文定位、reference lookup | 先给 quote，再给位置和解释 |
| `evidence_gap` | 缺口检查、低置信问题 | 先列已有证据，再列缺口和风险 |
| `summary` | 总结类问题 | 主题分段 + coverage note |

### 7.4 当前首批 route 的 AnswerPlan 方向

- `stage_transition_work`：`transition_scope`、`entry_inputs`、`work_items`、`reviews_deliverables`、`exit_readiness`。
- `deliverable_detail`：`deliverable_scope`、`required_contents`、`owner_author`、`review_approval`。
- `tailoring_policy`：`agile_applicability`、`tailorable_reviews`、`non_tailorable_reviews`、`approval_evidence`。
- `process_operation`：`scope_applicability`、`operation_sequence`、`deliverables_reviews`、`verification_validation`。

后续 route 优先从真实失败样本和 eval case 中扩展，而不是预先穷举所有业务问题。

## 8. Answer Eval

每次生成后跑最小 eval：

- `groundedness`：关键事实是否匹配 evidence quote。
- `citation_completeness`：流程、角色、交付物、BU 差异是否有 citation。
- `abstention_correctness`：证据不足是否说明缺口。
- `adaptive_format`：输出是否符合 intent。
- `keyword_normalization`：PO/R2/QMP 等企业关键词是否正确归一。

Eval 结果进入 `answer_run.generation.outputs.eval_summary` 和 Admin / JSON Lab。

## 9. Session Memory

首版 store：

```json
{
  "session_id": "session-...",
  "turns": [],
  "pinned_answers": [],
  "pinned_references": [],
  "confirmed_terms": [],
  "tool_runs": [],
  "source_scope_history": []
}
```

Memory step 状态：

- P0：`deferred`，仅前端 pin-ready。
- P1：写入 local JSON store。
- P2：支持 session reopen / search / export。

## 10. 实施步骤

- [ ] **C0 Citation integrity hotfix**
  - 验收：CT/MI/XP selected-doc 切换后 citation 不串线；无 quote/anchor 的 hit 不生成 citation；answer eval 能标出 unsupported citation。

- [ ] **C1 ChatWorkflowRunner skeleton**
  - 验收：`/api/session/query` 逻辑迁入 runner，API 响应不变。

- [ ] **C1A Runtime input + session state contract**
  - 验收：请求层显式支持 `session_id`、`selected_document_ids` 和 `mode`；runner 能读取上一轮问题、上一轮 answer、source scope history，并输出 `is_follow_up`。

- [ ] **C2 LLM-first Intent Router + Route Catalog**
  - 最小方案：建立轻量 `RouteCatalog`，让 LLM Router 输出结构化 `intent-route-v0.2` JSON；规则 pre-router 只抽实体和候选 route。
  - 验收：R4/R5、QMP、敏捷裁剪、流程操作、表格、引用定位和未知问题都能输出 `primary_route/confidence/entities/evidence_needs/answer_slots`；未知 route 降级到 `generic_rag`。

- [ ] **C2B Generic RAG fallback + route evolution eval**
  - 最小方案：为低置信或未知问题提供通用 RAG fallback，并记录 fallback reason、retrieved evidence、uncertainty；新增 route 前先补 eval case。
  - 验收：新问题不会阻断问答；反复失败的问题可从 eval case 沉淀为 Route Catalog entry。

- [ ] **C2A Query rewrite object**
  - 验收：query rewrite 不只返回字符串，还输出 `rewritten_query`、`route_terms`、`excluded_terms`、`reason`；覆盖 process、definition、reference、table、comparison、gap。

- [ ] **C3 Tool registry**
  - 验收：answer_run execution step 记录真实 tool calls。

- [ ] **C3A Tool plan contract**
  - 验收：runner 在执行前输出 `ToolPlan`，明确是否调用 section search、fulltext、vector、table lookup、direct read、reference context；未启用工具要写明原因。

- [ ] **C4 HybridRetriever 接入 session query**
  - 进展：2026-06-17 `/api/session/query` 已使用 `HybridRetriever([RuleSectionRetriever, FullTextRetriever])`，Answer Run tool_calls 返回 `hybrid_retrieve_sections`。
  - 验收：trace 包含 hybrid fanout / RRF；R2/PO eval 不劣于旧路径。

- [x] **C4A Direct reference context**
  - 验收：session query 的 citation payload 带 bounded `source_context`；Reference Viewer 能展示引用前文、命中上下文和引用后文，且不跨 source scope。
  - 证据：2026-06-18 已在 citation payload 增加 `source_context`，来源为本轮 selected-doc chunks；后端主线测试 `40 passed, 1 warning`，前端 build 通过，浏览器 smoke 看到 7/7 citations 带 context。

- [ ] **C5 LLM composer**
  - 验收：`use_llm=True` 真正走 LLM composer；失败时回退 deterministic。

- [ ] **C6 Answer eval 集成**
  - 验收：missing citation / unsupported claim / missing evidence 被返回到 answer_run。

- [ ] **C6A LLM-first Answer Planner + evidence-bound slots**
  - 最小方案：LLM Planner 基于 `RouteCatalog + EvidencePackage` 生成 `answer-plan-v0.2`；程序校验 filled slot 的 evidence/citation 绑定。
  - 验收：`process_operation/stage_transition_work/deliverable_detail/tailoring_policy/generic_rag` 均能生成 slots；slot 无证据时写入 `missing_evidence`，composer 只消费 plan。

- [ ] **C6B Claim Verifier report**
  - 验收：生成后抽取事实 claim，校验每个 claim 是否由 citation quote/source_context 支持；unsupported / weakly-supported claim 写入 answer_run 和 UI 摘要。

- [ ] **C7 Session memory store**
  - 验收：pin answer/ref 可持久化，memory step 从 deferred 变为 done 或 warning。

## 11. 测试和验证

- API test：selected-doc source scope、all_sources、invalid scope。
- Intent test：R2/PO、reference lookup、BU comparison、table lookup、parse quality。
- Tool test：hybrid retrieval、table lookup、quality lookup。
- Answer eval test：missing citation、unsupported claim、evidence gap。
- Browser smoke：连续两问、Answer Run 六步、citation card、pin note。