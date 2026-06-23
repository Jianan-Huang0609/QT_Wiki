# QT Wiki Development Memory

开发记忆入口在 [Design/dev-memory/](Design/dev-memory/)。后续继续开发时先读 [SESSION-WIP.md](Design/dev-memory/SESSION-WIP.md)，再读 [TODO.md](Design/dev-memory/TODO.md)。

## 2026-06-23

Design 文档物理归档已完成：当前根入口为 [Design/README.md](Design/README.md)、[Design/TODO.md](Design/TODO.md)、[Design/PRD-流程问答工作台.md](Design/PRD-流程问答工作台.md)、[Design/Spec-Parser-RAG.md](Design/Spec-Parser-RAG.md)、[Design/Spec-Chat-Workflow.md](Design/Spec-Chat-Workflow.md)、[Design/Spec-UI-Workspace.md](Design/Spec-UI-Workspace.md)。旧 Gate / Plan / Review / 历史 Spec 已统一进入 [Design/old/](Design/old/)。

文档分工规则更新：框架设计、策略判断、接口 contract 和解释写入对应 Spec；具体开发操作、checkbox、优先级和验证证据写入 [Design/TODO.md](Design/TODO.md)。

Chat 方向今日判断：所有问题都经过统一 Router / Planner，但不是所有问题都固化为 route；先抽薄 `RouteCatalog`，再补 `generic_rag` fallback + route evolution eval，最后接 LLM structured router。LLM 负责泛化理解和动态 slot，程序负责 source scope、citation、evidence binding、missing evidence 和 claim verifier。

TODO 口径更新：总 [Design/TODO.md](Design/TODO.md) 现在按 Release-0 可信问答闭环组织，任务统一使用 `预期功能 / 最小方案 / 验收 / 来源`，背景解释继续放在三份 Spec。

当前优先级落定：先 `BASE-01` 定 CT / MI / XP smoke 尺子，再做 Chat 的 `RouteCatalog / generic_rag / AnswerPlan / Claim Verifier`；Parser 只先做现有能力 smoke、轻量 `EvidenceSource adapter` 和质量警告，完整 DocumentBlock/artifacts/provider 评估后置。

`BASE-01` 已完成：`Tool.evals.release0_smoke` 固定 8 条 CT / MI / XP smoke case，并新增 [Design/review-artifacts/release0-smoke-failures.md](Design/review-artifacts/release0-smoke-failures.md) 作为失败记录入口；验证 `tests/test_release0_smoke_cases.py -q` 为 `2 passed`。

`CHAT-03` 已完成：新增 `Tool.workflows.route_catalog`，把高频/高风险 route 的 query terms、evidence needs、answer slots、risk level、citation policy、retrieval 扩展和 rerank 标记集中管理；`App.api` 的 route plan、query rewrite、ToolPlan `route_strategy`、top_k、rerank、AnswerPlan slots 和 answer shape 已读取 catalog。相关回归 `tests/test_route_catalog.py tests/test_app_api.py tests/test_answer_workflow.py tests/test_release0_smoke_cases.py tests/test_retriever_interface.py -q` 为 `49 passed, 1 warning`。下一步进入 `CHAT-04 generic_rag fallback + route evolution eval`。

## 0617

Design 文档已收敛为一个系统级 TODO + 三个模块级 Spec：
1. 系统级执行入口：[Design/TODO.md](Design/TODO.md)
2. Parser/RAG 当前 Spec：[Design/Spec-Parser-RAG.md](Design/Spec-Parser-RAG.md)
3. Chat Workflow 当前 Spec：[Design/Spec-Chat-Workflow.md](Design/Spec-Chat-Workflow.md)
4. UI Workspace 当前 Spec：[Design/Spec-UI-Workspace.md](Design/Spec-UI-Workspace.md)

旧文档处理策略：
- PRD 保留为产品边界。
- G9-Human-Review-Pack、Gate3-PEP-PDF-Review、Gate6、MultiInput、Parser-Evals、Pro-Input、Tool-Parser-RAG-Fusion、Todo+Spec 等旧计划/背景/证据文档已被新 Spec 吸收，并在 2026-06-23 物理归档到 [Design/old/](Design/old/)。

2026-06-17 用户进一步确认：
- Parser 体验要接近 Notebook-like 自动解析；普通文档不要求逐份人审，review 只处理低置信 block/table/visual candidate。
- Ask Workspace 左侧 Source/Tree 只展示文件级 source card，不默认展开章节子项。
- Chat 当前首要问题是 citation/source scope 不可信，以及 intent/route/Answer Run/回答质量混乱；下一步优先修 citation integrity 和 ChatWorkflowRunner。

2026-06-17 已完成首个 citation integrity hotfix 切片：
- `/api/session/query` citation 输出前会校验 selected source scope、document_id/file_name、quote、anchor，并把 validation summary 写入 answer_run execution step。
- deterministic answer 只消费 validated citation 对应的 evidence；citation key 包含 quote，避免同一 anchor 下不同证据句共用标签；前端 Citation 类型补充 `section_id/evidence_id/anchors`。
- 新增回归测试覆盖 out-of-scope、missing anchor、missing quote 证据被过滤，以及 quote-specific citation labels；验证全量后端 `pytest -q` 为 `138 passed`。
- Parser-to-Markdown Spec 已扩展 open-source provider 融合矩阵和 CT/MI/XP 样例验收；下一步做真实 PEP smoke 后再勾 R0-02 / CHAT-00。

2026-06-17 Session Query LLM composer 已接入：
- 之前 `/api/session/query` 的 Answer Run 是真实检索/证据/citation 校验，但 generation 固定 deterministic，未调 4o。
- 现在 `use_llm=true` 会基于 validated citations 调用 LLM composer，默认 `model_profile` 已改为 `azure-gpt-5.4`；前端模型下拉会传到后端，并保留 `azure-gpt-4o` 作为可选项。
- 新增 `config/azure_gpt5_4_config.json` 作为 5.4 占位配置，未写入新密钥；真实调用需环境变量或本地安全配置提供 key 和确认 deployment 名。
- LLM 回答未带 citation label 或调用失败时回退 evidence-first 答案；下一步需做真实 5.4 smoke 和 answer eval。

2026-06-22 Chat answer quality quick slice：
- 用户反馈思考摘要像预设框架、默认调用 4o、回答仍偏章节级。已把默认 profile/schema/frontend 改为 `azure-gpt-5.4`，并新增 `azure-gpt-5.5` 占位配置和选项；未知 profile 回退到 5.4。
- LLM prompt 现在消费 citation quote + `source_context` 前后文，要求直接回答本轮问题，不再输出固定“识别与路线 / References”栏目，并要求每步写具体动作、条件、交付物或评审依据。
- deterministic fallback 已增加“文档细节 / 可追溯位置”，前端思考摘要改为真实 answer_run timeline；下一步仍需正式 Answer Planner slot map 和 Claim Verifier。

2026-06-22 GPT-5 调用层修复：
- 5.4 之前 401 的根因是 `config/azure_gpt5_4_config.json` 未拿到 key；`azure-gpt-5` 之前还缺 `config/azure_gpt5_config.json`。
- 已新增 `config/azure_gpt5_config.json`；空 key 的 5.x config 会复用默认 Azure gateway key，环境变量仍优先。
- `Tool.llm.client` 对 `gpt-5` / `gpt-5.5` 省略 `temperature/top_p`；真实 smoke 中 `gpt-5`、`gpt-5.4`、`gpt-5.5` 均可返回 `OK`。

2026-06-22 Chat Runtime quality slice：
- 已新增 `query-rewrite-v0.1`、`tool-plan-v0.1`、`answer-plan-v0.1` 到 `/api/session/query` 的 `answer_run`。
- Intent Router 新增 `table_lookup` / `summary_request`；前端执行摘要改为读取 `query_rewrite/tool_plan/answer_plan` 的动态事件。
- `process_operation` AnswerPlan 首批 slots：`scope_applicability`、`operation_sequence`、`deliverables_reviews`、`verification_validation`，filled slot 必须绑定 citation。
- 输出格式经验：`AnswerPlan` 负责证据和 slot 顺序，`AnswerStyle` 负责 chatbox 阅读形态；已新增 `answer-style-v0.1`，要求短结论、少量小标题、必要时连续编号，并避免编号项里嵌套 bullet。
- 继续新增三类专业问题 route：`stage_transition_work` 处理 R4->R5 转换工作，`deliverable_detail` 处理 QMP 内容/责任，`tailoring_policy` 处理敏捷裁剪与不可裁剪评审边界；三者都接入 Query Rewrite、route rerank、AnswerPlan slots 和 fallback/LLM prompt。
- Ask Workspace UI 当前方向：左侧 Sources 是干净的可选 source list，用 checkbox 决定本轮 query scope；右侧 Reference 只作为原文 quote 返回列表和定位展开区，Session Note/Admin 不再放在主右栏。
- 设计方向已收敛为 LLM-first structured Router/Planner：LLM 输出 route/planner JSON，Route Catalog 只保存高频/高风险问题的轻量策略，Generic RAG fallback 承接未知问题，程序负责 source scope、citation、evidence binding、missing evidence 和 claim verifier。

2026-06-17 route-aware Chat / reference 修复：
- 泛流程问题进入 `process_overview` route，不再把 R2/R3/QMP/PMP 等阶段词硬塞进通用流程检索。
- Answer Run planning/execution 已写入 route_id、expanded retrieval question、真实 tool_calls 和 citation validation summary；前端 timeline 现在显示这些元信息。
- `AnswerEvidencePackage` 优先使用 chunk-level 正文 quote，修复 Reference Card 只显示首个 source_ref 章节标题的问题；XP PEP smoke 已返回 p.6/p.9/p.16 正文级引用。
- 相关验证：`tests/test_answer_workflow.py tests/test_app_api.py -q` 为 `27 passed`，`App/web npm run build` 通过。

2026-06-17 NotebookLM-like Chat 反馈落地：
- UI 上 Answer Run 默认收成一行摘要，1-6 步详细执行信息折叠展示，主 Chat 空间让给回答。
- 新增 `process_operation` route：问“流程如何操作/怎么做/步骤”时与“目的/适用范围是什么”的概念总览分开处理。
- deterministic fallback 已按操作主线组织答案，不再只是列 section；passage selector 会从 chunk 正文中挑与 matched terms / intent terms 最相关的片段。
- 最新验证：`tests/test_answer_workflow.py tests/test_app_api.py -q` 为 `29 passed`，`App/web npm run build` 通过；XP PEP smoke 返回 `process_operation`。

2026-06-17 Chat prompt 泛化修正：
- `App/api.py` 不再默认把流程类文档等同于 PEP；route summary、retrieval expansion、LLM prompt、fallback answer、source label 和 suggested questions 都改为“当前文档/流程文档”口径。
- PEP 只作为用户问题、文件名或文档内容中的自然术语保留；SOP/WI/规范/规程类问题也能进入 `process_operation`。
- 最新验证：SOP 泛化 smoke 的 retrieval question 不含 `pep`；`tests/test_answer_workflow.py tests/test_app_api.py -q` 为 `30 passed`，`App/web npm run build` 通过。

2026-06-17 RAG quality hardening：
- `/api/session/query` 已从直接规则检索切到 `HybridRetriever([RuleSectionRetriever, FullTextRetriever])`，Answer Run execution tool_calls 记录 `hybrid_retrieve_sections`。
- `process_operation` route 对泛流程操作问题下调 country-specific approval / market access 局部专题，避免回答“流程如何操作”时被局部审批章节抢占。
- `AnswerEvidencePackage` passage selector 增加短标题、表格碎片和重复章节标题清洗；XP PEP smoke 的 p.9 V-model quote 现在返回正文句子而非表格碎片，p.6/p.16 quote 也不再重复标题。
- 最新验证：`tests/test_answer_workflow.py tests/test_app_api.py tests/test_retriever_interface.py -q` 为 `38 passed`，`App/web npm run build` 通过；XP PEP smoke 返回 `route_id=process_operation`，tool_calls 包含 `hybrid_retrieve_sections`。

2026-06-18 Chat thinking UI：
- Ask Workspace 已移除固定 Answer Run / 1-6 步全局面板；思考摘要现在挂在每条 assistant message 内，运行中展开、完成后默认收起。
- 用户可见文案不再出现 `Answer Run`；折叠摘要使用“流程操作路线 · N 条引用已校验 · 证据链已装配”这类自然语言。
- `npm run dev` 需直接运行 package script，避免额外 `-- --host ...` 参数被 npm 追加成 Vite root 导致 5173 返回 404。
- 继续细化：后端 answer_run 增加 `evidence_preview` 和 `self_check`，前端思考摘要按问题界定/source/route/query rewrite/evidence/citation validation/self-check 重排。
- 正文引用必须用 `c1/c2` 小标，点击后让右侧 Reference 展开；Reference Card 标题用 `cN · page/anchor · section`，文件名进入 metadata。

2026-06-17 Chat UX hardening：
- Answer Run UI 已改成渐进式可审计链路摘要，展示 route、工具目的、证据数量、citation validation 和 composer，不展示逐字内部思维链。
- `RichAnswer` 支持标题、列表和 inline citation 渲染；Reference Card 可展开 quote、file/section/fragment/anchor 定位字段。
- `process_operation` fallback answer 拆成步骤、操作要点、原文依据；rerank 进一步下调 Labeling / China RoHS / Product Scope 等局部合规噪音，并跳过标题式 evidence。
- 最新验证：`tests/test_answer_workflow.py tests/test_app_api.py tests/test_retriever_interface.py -q` 为 `40 passed`，`App/web npm run build` 通过；MI PEP 浏览器 smoke 无裸露 Markdown、无 Labeling/RoHS 噪音，Reference 可展开。

2026-06-18 RAG backend boundary：
- 当前 Ask Workspace `/api/session/query` 已经是 selected-doc RAG：从 `Tool/output/parsed/{document_id}.json` 读取 canonical document，运行时生成 `SectionChunk[]`，再通过 `HybridRetriever([RuleSectionRetriever, FullTextRetriever])`、route-aware rerank、evidence package 和 citation validation 生成回答。
- 当前还不是持久化向量数据库 RAG：`VectorRetriever` 已存在但未接入 session query，也没有落盘 embedding index；文件数据库以 Raw/manifest、parsed canonical JSON、wiki output/index JSONL 为主。
- Direct source/reference context 首切片已完成：citation card 现在带同 chunk/相邻 chunk 的 bounded 前后文，前端 Reference Viewer 可展开“引用前文 / 命中上下文 / 引用后文”；验证后端主线 `40 passed, 1 warning`、前端 build 通过、浏览器 smoke 确认 7/7 citations 带 context。

2026-06-18 Chat Runtime v0.2 八步链路：
- 正式目标写入 [Design/Spec-Chat-Workflow.md](Design/Spec-Chat-Workflow.md)：Receive Input、Read Session State、Intent Router、Query Rewrite、Tool Plan、Evidence Package、Answer Planner、Claim Verifier + UI。
- 当前约 5/8 可用；主要缺口是 session state/follow-up、正式 ToolPlan、AnswerPlanner slot map、Claim Verifier report。下一步应优先做 `CHAT-01B Runtime input + session state contract`，再做 `ToolPlan` 和 `AnswerPlan`。

下一步优先级：
1. Chat：`CHAT-01B Runtime input + session state contract`，让后端能读上一轮并识别追问。
2. Chat：继续扩展 ToolPlan + AnswerPlan + AnswerStyle + Claim Verifier，把 8 步链路从隐式函数升级成显式中间产物，并让输出既可证据校验也可读。
3. Release-0：完成 CT/MI/XP selected-doc 可信问答 smoke，并把失败项写入 eval/hardening 清单。
4. Chat/RAG：persistent chunk index + retrieval eval baseline，为真实 vector store 做准备。
5. Parser/UI：Notebook-like artifacts 和四页工作台继续推进。

## 0615
继续 QT Wiki 项目，沿用当前仓库状态，不要重开方向。

当前已完成：
1. Ask Workspace 已接入 selected-doc `/api/session/query`
2. 后端已返回 `answer_run-v0.1` 六环：input/context/planning/execution/generation/memory
3. 前端 Chat 已改为多轮 transcript，composer 支持连续提问
4. 文档与开发记忆已更新到 Design/TODO.md、Design/old/Todo+Spec-流程问答工作台.md、Design/dev-memory/SESSION-WIP.md、CHANGELOG.md

当前下一步优先级：
1. 把第 6 环 memory 从 front-end pin-ready 升级为真实 session memory store
2. 强化第 3/4 环 planning/execution，让 R2/PO/RA 类问题有更好的 semantic rerank 和 role-aware retrieval
3. 继续把 UI 从 Ask Workspace v1 推进到四页框架：Source Intake -> Review Gate -> Ask Workspace -> Admin / JSON Lab
4. 优先保持 workflow-first 架构，不另起一套 chat 系统

续做前先检查：
- `pytest tests/test_app_api.py -k session_query -q`
- `cd App/web; npm run build`
- 前端 `http://127.0.0.1:5173`
- 后端 `http://127.0.0.1:8000`

保护约束：
- 不要动 Raw/ 下现有删除态和未跟踪生成物
- 不要处理 USAGE.md 删除态
- 文档有变化时继续同步 CHANGELOG 和 dev-memory