# Changelog

## 2026-06-24

- 完成 `RAG-02 Semantic Retriever Azure embedding smoke`：新增 Azure `text-embedding-3-small` adapter 与 semantic RAG smoke，对比当前 lexical baseline 和 `[RuleSection, FullText, Vector]` semantic-hybrid。真实 endpoint 可用，报告见 `Design/review-artifacts/semantic-rag-smoke.md`；lexical baseline recall@8 = `1.0`、route accuracy = `1.0`，semantic-hybrid recall@8 = `0.875`、route accuracy = `1.0`，并在 R2/PO 与 7.16 来源定位问题出现 citation drift。结论是 semantic retriever 继续保持实验开关，不替换生产默认检索；下一步用 `RAG-03` 表格问题判断是否需要 route-gated semantic retrieval。验证 `tests/test_semantic_rag_smoke.py -q` 为 `3 passed`。
- 完成 `CHAT-05B LLM Router shadow diff 分析`：新增 router shadow diff harness，支持 LLM prompt、JSON 提取、schema guardrail、`matched / llm_improved / llm_regressed / entity_missing / fallback_mismatch / source_location_risk` 分类和 Markdown artifact 输出。真实 `azure-gpt-5.4` shadow 跑 6 个目标 case，结果为 5 个 `matched`、1 个 `fallback_mismatch`；未知 fallback 问题中规则 route 保守降级 `generic_rag`，LLM 选择 `process_operation`，已记录为 route evolution eval 样本，不替换生产 route。报告见 `Design/review-artifacts/router-shadow-diff.md`。验证 `tests/test_router_shadow_diff.py tests/test_route_catalog.py tests/test_app_api.py -q` 为 `46 passed, 1 warning`。
- 完成 `CHAT-05A intent-route-v0.2 schema + RouteCatalog 全量映射`：新增 `Tool.workflows.intent_route`，将 13 个 RouteCatalog entry 无损投影到统一 route schema，包含 primary/secondary routes、route/evidence confidence、结构化 entities、previous-context 标记、guardrail 和扩展字段；`/api/session/query` 的 answer_run planning step 现在输出当前规则 route 的 shadow schema，但生产 route 决策仍保持原规则路径。Guardrail 已覆盖非法 route 与低 route_match 降级 `generic_rag`。验证 `tests/test_route_catalog.py tests/test_app_api.py -q` 为 `44 passed, 1 warning`。
- 更新下一阶段执行计划：确认 Parser 主路径当前保持稳定，PDF 继续走 pypdf 文本抽取与项目内结构规则，DOCX 继续走 XML 解析；Docling / Marker / MinerU / OCR provider 升级进入 Later，触发条件改为扫描件、图片型 PDF、anchor 不可核查或 RAG/table smoke 证明现有链路无法修复。同步更新 `Design/TODO.md` 与 `Design/dev-memory/SESSION-WIP.md`。
- 重排本周与下周主线：本周先做 Router 2.0 第一刀，包括 `CHAT-05A intent-route-v0.2 schema + RouteCatalog 全量映射`、`CHAT-05B LLM Router shadow diff` 和 `CHAT-COMP-01 composer migration risk`；同时新增 `RAG-02 Semantic Retriever Azure embedding smoke` 与 `RAG-03 表格检索诊断 smoke`。下周计划接 AnswerPlan-driven composer、slot-driven rerank extraction、`PARSER-MIN-03` 文档/evidence 质量状态和 `UI-01` Source Intake 第一刀。
- 明确 Router 2.0 设计边界：LLM 不直接替代现有规则，而是在统一 schema 下做 shadow 决策；规则 pre-router 降级为 entity extraction 与 candidate route hints，程序 guardrails 继续负责 schema 合法性、catalog route 校验、confidence 门槛、secondary routes 合法性与 source-location follow-up 兜底。Semantic RAG 先以实验开关接 Azure `text-embedding-3-small`，不建向量数据库，不改变生产默认检索，等 smoke diff 验证 recall 和 citation drift 后再决定是否推广。

## 2026-06-23

- 修复 source-location follow-up 漂移：`在原文哪里 / 出处在哪里 / 第几页 / 原文怎么说` 这类追问现在会识别为 `reference_lookup`，优先继承上一轮 citations、页码/anchor、quote 和 source scope，并把上一轮 citation 反查到当前 chunk 后置顶；多 source_ref chunk 会按上一轮 quote/anchor 优先排序，避免 CT p.28/p.29 证据在第三问漂到 XP 或落到同 chunk 的 p.27 首引用。前端 previous_turn citations 同步传递 `document_id / fragment_id / section_id / evidence_id / source_context`，后端仍兼容旧的 file/page/quote 摘要。新增三轮回归 `R4到R5之间需要完成哪些工作？ -> 具体要交付什么文件？ -> 在原文的哪里？`，验证第三问仍定位 CT。验证 `tests/test_app_api.py tests/test_route_catalog.py tests/test_answer_workflow.py tests/test_release0_smoke_cases.py -q` 为 `54 passed, 1 warning`，`npm --prefix App/web run build` 与 `git diff --check` 通过。
- 修复阶段转换问答漏召回关键活动的问题：确认 CT PEP p.28 `Product validation (R4-M300)` 证据已在 parsed canonical 中，缺口来自 `stage_transition_work` 的 query pack / rerank、citation context 绑定和 composer 覆盖策略；增强 RouteCatalog 的阶段转换 evidence pattern 与 AnswerPlan 槽位，提升 design/system validation、reliability/stability、production documentation、software transfer、GSPR/STED、clinical/PMS 等可复用证据；修复同页多 fragment anchor 反复加分导致的 chunk 误匹配，并扩大 Reference context 窗口。按用户反馈移除 CT 专用 deterministic 活动清单，改为 AnswerPlan slot + citation/context 驱动的通用阶段转换 composer，优先覆盖不同 slot terms；新增合成 evidence 回归，验证 composer 不会自动注入 Product validation/GSPR/STED。验证 `tests/test_app_api.py tests/test_route_catalog.py tests/test_answer_workflow.py tests/test_release0_smoke_cases.py -q` 为 `53 passed, 1 warning`，Release-0 route RAG smoke 为 `8/8 pass`。
- 完成 Ask Workspace UI / follow-up 首切片：`/api/session/query` 支持 `session_id` 与 `previous_turns`，answer_run context step 输出 `session-state-v0.1`，短追问会把上一问合入检索 query；前端连续提问会传上一轮成功回答摘要、citations 和 source scope。同步精简主界面：上传后留在 Ask Workspace，左侧 source card 显示已选/已解析/待复核状态，移除 `Session PEP-R2`、`Process Chat`、`回答必须回到证据` 等可见噪音；右侧 Reference 去掉重复的当前/本轮双层结构，默认只显示文件、页码/锚点和 quote，选中项可展开完整返回原文、前文和后文并按段落渲染；Chat 正文不再展开 `原文命中` 或相邻上下文，Pin / Session Note 入口已从主路径移除。验证 `tests/test_app_api.py -k "session_query_uses_selected_pep_chunks_for_process_question or session_query_accepts_follow_up_contract or session_query_unknown_question_uses_generic_rag_fallback" -q` 为 `3 passed, 1 warning`，后续回答正文窄测 `2 passed, 1 warning`，`npm --prefix App/web run build` 通过；浏览器 smoke 确认 7 条 Reference 均有展开区且页面无 Pin 文案。
- 完成 `RAG-01 Evidence Pattern RAG` 首切片：在 RouteCatalog 中新增 `route-query-pack-v0.1` 和 domain term pack，把 query rewrite 从“原问题 + route terms”升级为 `primary_query / slot_queries / must_terms / support_terms / weak_terms / downrank_terms`；`deliverable_detail` 和 `tailoring_policy` 不再继承 overview bonus，改为按 QMP 内容/责任、敏捷裁剪/强制评审边界做 route-aware evidence scoring，并下调 `Purpose and scope`、`Provisional solution` 等泛噪音章节。新增 `Tool.evals.route_rag_smoke.release0_route_rag_smoke_report()`、`tests/test_route_rag_smoke.py` 和 `Design/review-artifacts/release0-route-rag-smoke.md`；真实 CT/MI/XP Release-0 route RAG smoke 从 `6/8` 提升到 `8/8`，`pass_rate = 1.0`、`route_accuracy = 1.0`，不涉及 parser/provider/vector DB 变更。相关回归 `tests/test_route_rag_smoke.py tests/test_route_catalog.py tests/test_parser_rag_smoke.py tests/test_release0_smoke_cases.py tests/test_app_api.py tests/test_answer_workflow.py tests/test_retriever_interface.py tests/test_parser_quality_eval.py -q` 为 `69 passed, 1 warning`。
- 完成 `PARSER-MIN-01` 当前解析能力 smoke 评估首版：新增 `Tool.evals.parser_rag_smoke.release0_parser_rag_smoke_report()` 和 `tests/test_parser_rag_smoke.py`，用 BASE-01 问题集对真实 CT/MI/XP parsed canonical 生成 chunks 并运行 HybridRetriever 诊断。真实结果为 8 条 smoke 中 6 条通过、Recall@8 = 0.75；两个失败均归类为 `chat_route_query_answer_gap`，未发现 parser 结构、source context、表格或 OCR 阻塞。报告写入 `Design/review-artifacts/release0-parser-rag-smoke.md`。
- 完成 `CHAT-06` AnswerPlan v0.2 首切片：generation step 现在输出 `answer-plan-v0.2`，每个 filled slot 保留 `citation_ids/evidence_ids` 并新增 `evidence_bindings`，可反查 document、section、anchor 和 quote preview；无证据 slot 进入 `missing_evidence`，并输出 `plan_quality` 统计 required、filled 和 missing required slots。新增/扩展 API 回归覆盖 v0.2 schema、slot 绑定和 missing evidence 合同。验证 `tests/test_app_api.py tests/test_answer_workflow.py tests/test_route_catalog.py tests/test_release0_smoke_cases.py -q` 为 `46 passed, 1 warning`。
- 完成 `CHAT-04` Generic RAG fallback 首切片：`/api/session/query` 在未命中高频流程 route 时进入 `generic_rag`，planning step 输出 `fallback_reason`，generation step 输出 `generic-rag-fallback-v0.1` report，包含 citation coverage、retrieved evidence count、missing evidence count、confidence 和 uncertainty；deterministic fallback 回答会保留证据边界。新增未知问题 API 回归 `test_session_query_unknown_question_uses_generic_rag_fallback`。同步把 UI 后续方向写入 TODO：左侧 Resource/Source 负责上传、资源列表和 source scope，右侧 Reference 负责 end-user 原文核查样式。验证 `tests/test_app_api.py tests/test_answer_workflow.py tests/test_route_catalog.py tests/test_release0_smoke_cases.py -q` 为 `45 passed, 1 warning`。
- 优化 Ask Workspace 回答可读性：LLM composer prompt 和 deterministic fallback 改为“短结论 + 自然小标题 + 可选语义字段”结构，让输出保留可扫读层次，同时让字段名随问题语义变化；前端 `RichAnswer` 支持 `依据 / 出处 / 边界 / 缺口 / 补充说明` 等语义字段行，并兼容旧式长 evidence 行的结构化渲染。本轮进一步补长回答 block 协议：LLM prompt 明确可用 `##/###` 小标题、`>` 短引用、fenced code block、分隔线、bullet/numbered list；前端新增 `blockquote / code / divider / callout` 渲染和克制样式，适合外部 GPT/DeepSeek 式流程树、监管口径短引文和分流说明。同步把 Sources 面板固定为当前 Release-0 三份 PEP（CT / MI / XP），避免 demo runs 和 parser 噪音标题污染资料列表。验证 `npm --prefix App/web run build` 通过；回答/route 窄测 `6 passed, 1 warning`，浏览器检查确认 rich quote/code/callout 样式已进入页面 bundle。
- 完成 `CHAT-03` 轻量 `RouteCatalog`：新增 `Tool.workflows.route_catalog`，集中管理 route 的 query terms、excluded terms、rewrite reason、evidence needs、answer slots、answer shape、risk level、citation policy、retrieval 扩展和 rerank 标记；`/api/session/query` 的 route plan metadata、Query Rewrite、ToolPlan `route_strategy`、retrieval top_k、route-aware rerank、AnswerPlan slots 和 answer shape 已读取 catalog。新增 `tests/test_route_catalog.py`，验证 Release-0 route 覆盖与现有 API helper 接入；相关回归 `tests/test_route_catalog.py tests/test_app_api.py tests/test_answer_workflow.py tests/test_release0_smoke_cases.py tests/test_retriever_interface.py -q` 为 `49 passed, 1 warning`，`compileall` 和 `git diff --check` 通过。
- 完成 `BASE-01` Release-0 smoke 尺子：新增 `Tool.evals.release0_smoke`，固定 8 条 CT / MI / XP smoke case，覆盖 selected-doc 流程操作、R2/PO、7.16、R4->R5、QMP、敏捷裁剪、未知问题 `generic_rag` fallback 和 CT/MI/XP 多文档对比；每条 case 记录 source scope、期望 route、最低 citation、期望证据、人工判断和失败记录位置。新增失败记录入口 `Design/review-artifacts/release0-smoke-failures.md`，验证 `tests/test_release0_smoke_cases.py -q` 为 `2 passed`。
- 落定当前 TODO 开发优先级：先用 `BASE-01` 固化 CT / MI / XP smoke 尺子，再推进 Chat 的 `RouteCatalog / generic_rag fallback / AnswerPlan v0.2 / Claim Verifier`；Parser 当前不做完整中间态重构，先用 `PARSER-MIN-01/02/03` 评估现有解析能力、补轻量 `EvidenceSource adapter` 和文档/证据质量警告；完整 `DocumentBlock / RAG artifacts bundle` 与 Docling / Marker / MinerU provider 评估后置到 Later，并以 smoke 失败类型触发。
- 重整 `Design/TODO.md` 为 Release-0 可信 NotebookLM-like 问答闭环执行板：任务统一改为 `预期功能 / 最小方案 / 验收 / 来源` 口径，减少旧计划和历史进展噪音，并把 Parser、Chat、UI 三份 Spec 的关键工作映射到 `BASE / PARSER / CHAT / UI / R0 / Later` 主线。同步修正 `Design/Spec-Chat-Workflow.md` 标题误输入。
- 收敛 Design 文档信息架构：当前 Design 根目录保留 `README.md`、`TODO.md`、`PRD-流程问答工作台.md`、`Spec-Parser-RAG.md`、`Spec-Chat-Workflow.md`、`Spec-UI-Workspace.md`；旧 Gate / Plan / Review / 历史 Spec 统一归档到 `Design/old/`。同步更新 Design README、总 TODO、根 README、功能文档、MEMORY 和 dev-memory，明确 Spec 放框架设计与策略解释，总 TODO 放具体操作和验证证据。
- 更新 Chat Workflow 设计判断：所有问题经过统一 Router / Planner，但只有高频、高风险、反复失败或合规责任强的问题进入轻量 Route Catalog；未知/低置信问题走 `generic_rag` fallback。新增对过度设计与粗糙设计风险的取舍说明，并记录企业 NotebookLM-like RAG 仍需补齐 Session State、RouteCatalog 抽象、generic fallback eval、Claim Verifier、Route Evolution Loop 和表格/结构化 block 工具。总 TODO 新增 `CHAT-02C` 和 `CHAT-02D`，作为下一步可执行切片。

## 2026-06-22

- 执行 Chat 回答质量首个结构化切片：Intent Router 新增 `table_lookup` 和 `summary_request`；Session Query 新增 `query-rewrite-v0.1`、`tool-plan-v0.1`、`answer-plan-v0.1` 并写入 `answer_run`。ToolPlan v0.1 只基于当前真实能力输出 planned/executed/skipped/reason，明确 `vector_search` 当前因 `persistent vector index not enabled` 跳过；AnswerPlan v0.1 先覆盖 `process_operation` 的适用范围、操作顺序、交付/评审、验证/确认 slots，并要求 filled slot 绑定 citation。LLM prompt 现在消费 AnswerPlan slots，并新增 `answer-style-v0.1` 约束，让结构规划和阅读呈现分离；deterministic fallback 改为短结论 + 连续编号段落，前端 ordered list 保留原始编号起点，减少 bullet-heavy 和编号反复从 1 开始的问题。继续扩展三类高频 PEP 质量问题 route：`stage_transition_work` 覆盖“R4 到 R5 之间完成哪些工作”，`deliverable_detail` 覆盖“QMP 包含内容/撰写责任”，`tailoring_policy` 覆盖“敏捷开发可裁剪/不可裁剪评审”；对应 Query Rewrite、route-aware retrieval、AnswerPlan slots 和 AnswerStyle 均已接入。前端执行摘要改为基于 `query_rewrite/tool_plan/answer_plan` 的动态事件，不再固定五段模板；Ask Workspace 左侧 Sources 改为干净可勾选 source list，右侧 Reference 收敛为原文 quote 返回列表，不再把 Session Note/Admin 作为主阅读区。验证 `tests/test_config.py tests/test_llm_compat.py tests/test_answer_workflow.py tests/test_app_api.py tests/test_retriever_interface.py -q` 为 `64 passed, 1 warning`，后续 answer-style 窄测 `tests/test_app_api.py tests/test_answer_workflow.py -q` 为 `38 passed, 1 warning`，本轮路由/UI 回归 `tests/test_answer_workflow.py tests/test_app_api.py -q` 为 `39 passed, 1 warning`，`App/web npm run build` 通过，live `/api/session/query` 中文问题返回 `route=process_operation`、8 条 citation 和 filled AnswerPlan slots。
- 更新 Chat Runtime 下一阶段设计：确认内部保留 8 步 contract，但 Ask Workspace UI 改为动态执行摘要，不固定展示八块或五段模板；当前回答质量优先，下一步聚焦读取会话状态、LLM-first structured Router/Planner、轻量 Route Catalog、结构化 Query Rewrite、ToolPlan v0.1、Generic RAG fallback、AnswerPlan slot map 和 Claim Verifier。Route 后续作为检索/证据/slot 策略，不再继续扩成多套 runtime；ToolPlan v0.1 先基于现有 section/fulltext/hybrid retrieval、route rerank、reference context、evidence package、citation validation 和 composer 能力输出 planned/executed/skipped/reason，持久 vector DB 放到后续独立切片。
- 修复 GPT-5 系列真实调用配置：新增 `config/azure_gpt5_config.json`；`Tool.llm.config` 在 5.x config 未写入 key 时会复用默认 Azure gateway key，同时仍让 `AZURE_OPENAI_API_KEY` / `LLM_API_KEY` 环境变量优先；`Tool.llm.client` 对 `gpt-5` 和 `gpt-5.5` 自动省略 `temperature/top_p`，避免网关返回 unsupported parameter。真实 smoke：`gpt-5.4` 返回 `OK`，`gpt-5.5` 返回 `OK`，`gpt-5` 在提高 token 预算后返回 `OK`；`/api/session/query` 使用 `azure-gpt-5.4` 返回 `used_llm=True`、`confidence=high`。验证 `tests/test_config.py tests/test_llm_compat.py tests/test_answer_workflow.py tests/test_app_api.py tests/test_retriever_interface.py -q` 为 `64 passed, 1 warning`，`git diff --check` 通过。
- 收紧 Ask Workspace Chat 的回答质量与执行摘要：默认模型从 `azure-gpt-4o` 切到 `azure-gpt-5.4`，新增 `azure-gpt-5.5` 占位配置和前端选项；未知模型 profile 现在回退到 5.4 而非 4o。LLM composer prompt 改为直接回答本轮问题，不再诱导输出固定“识别与路线 / References”栏目，并把 citation 的 `source_context` 前后文一起交给模型，要求每个步骤写出具体动作、条件、交付物或评审要求。deterministic fallback 同步增加“具体做法 / 文档细节 / 可追溯位置”，减少章节级罗列，并让文档细节句贴近 citation label。前端思考摘要从长 bullet/chip 改为基于真实 answer_run 的紧凑执行 timeline。同步为 dashboard/wiki bootstrap 增加 storage permission 容错，避免 OneDrive 锁住 `wiki/output/pages/*.json` 时把 `/api/dashboard` 打成 500。验证 `tests/test_answer_workflow.py tests/test_app_api.py tests/test_retriever_interface.py -q` 为 `43 passed, 1 warning`，`App/web npm run build` 通过，`git diff --check` 通过，相关 VS Code diagnostics 无错误；浏览器 smoke 确认默认显示 `Azure GPT-5.4`、下拉含 `Azure GPT-5.5`、最新回答无旧“识别与路线 / 流程操作拆解 / References”栏目且包含具体做法/文档细节/可追溯位置。修复 GPT-5 配置前，5.4 因未拿到 key 回退到 evidence-first answer。

## 2026-06-18

- 固化 Chat Runtime v0.2 八步链路文档：在 `Design/Spec-Chat-Workflow.md` 写入 `Receive Input -> Read Session State -> Intent Router -> Query Rewrite -> Tool Plan -> Evidence Package -> Answer Planner -> Claim Verifier + UI`，并新增当前差距矩阵；`Design/TODO.md` 增补 `CHAT-01B/02A/03D/05A/05B` 等可执行项。当前判断约 5/8 可用，主要缺 session state/follow-up、正式 ToolPlan、AnswerPlanner slot map 和 Claim Verifier report。
- 完成 Reference Viewer 前后文切片：session query 的 citation payload 新增 `source_context`，从当前 selected-doc chunk window 装配引用前文、命中上下文、引用后文、chunk/section/anchor 元数据；前端 Reference Card 展开区现在显示“引用前文 / 命中上下文 / 引用后文”。验证 `tests/test_app_api.py -k "session_query_uses_selected_pep_chunks_for_process_question" -q` 为 `1 passed`，`tests/test_answer_workflow.py tests/test_app_api.py tests/test_retriever_interface.py -q` 为 `40 passed, 1 warning`，`App/web npm run build` 通过；重启本地后端后浏览器 smoke 确认 MI PEP 7 条 citation 均带 source_context 且 DOM 正常渲染前后文。
- 继续细化 Ask Workspace Chat 体验：后端 `answer_run` 新增 `evidence_preview` 与 `self_check`，前端思考摘要改为“问题界定 / source scope / 意图路线 / 检索改写 / 候选证据 / 引用校验 / 完整性自检”的审计链路；正文 citation 从文件名长按钮改成 `c1/c2` 小标，点击后右侧 Reference Card 展开 quote 与定位；Reference Card 标题改成 `cN · 页码/锚点 · 章节`，文件名下沉到 metadata。`process_operation` deterministic answer 移除正文 References 文件列表，最多使用 7 条已过滤操作证据提升完整性。验证 `tests/test_answer_workflow.py tests/test_app_api.py tests/test_retriever_interface.py -q` 为 `40 passed`，`App/web npm run build` 通过；浏览器 smoke 确认 inline 无长文件名、无 References heading、思考摘要含自检和 evidence preview、Reference 标题不是文件名。
- 调整 Ask Workspace Chat 思考展示：移除固定 Answer Run / 1-6 步全局面板，改为每条 assistant 消息内的可展开“思考摘要”；提问时先插入“正在思考”气泡，回答完成后默认收起摘要，正文继续显示结构化答案和可定位引用。修复 Vite dev 启动方式，`npm run dev` 已在 `http://127.0.0.1:5173/` 正常运行；验证 `App/web npm run build` 通过，浏览器 smoke 显示固定 Answer Run DOM 为 0、可见文案无 `Answer Run`、完成态思考默认收起、Reference Card 返回 8 条。

## 2026-06-17

- 改进 Ask Workspace 的 Chat 展示体验：Answer Run 从折叠卡片升级为渐进式可审计链路摘要，展示输入、上下文、route、tool calls、citation validation、生成和 memory 的细节；回答正文改为结构化渲染标题/列表/inline citation，避免裸露 Markdown；Reference Card 支持展开原文 quote、文件、章节、fragment 和 anchor 字段。同步强化 `process_operation` 答案颗粒度，拆分操作要点与原文依据，并下调 Labeling / China RoHS / Product Scope 等局部合规噪音、跳过标题式 evidence。验证 `tests/test_answer_workflow.py tests/test_app_api.py tests/test_retriever_interface.py -q` 为 `40 passed`，`App/web npm run build` 通过；localhost MI PEP 浏览器 smoke 返回 `hybrid_retrieve_sections` 链路、8 个可展开 Reference、无裸露 `**...**` Markdown 和无 Labeling/RoHS 噪音。
- 继续强化 Session Chat 的 RAG 质量：`/api/session/query` 实际执行已切到 `HybridRetriever([RuleSectionRetriever, FullTextRetriever])`，Answer Run tool_calls 返回 `hybrid_retrieve_sections`；`process_operation` rerank 下调泛流程问题中的 country-specific approval 局部专题，passage selector 增加表格碎片惩罚和重复章节标题清洗。验证 `tests/test_answer_workflow.py tests/test_app_api.py tests/test_retriever_interface.py -q` 为 `38 passed`，`App/web npm run build` 通过；XP PEP 真实 smoke 返回 `process_operation`，引用前 5 为 p.6/p.9/p.16/p.49/p.50，quote 已清掉标题重复和表格碎片。
- 泛化 Session Chat 的流程文档 route/prompt：`App/api.py` 不再在 route summary、retrieval expansion、LLM prompt、fallback answer 和 source label 中默认假设所有内容都是 PEP；系统扩展词改为 `process document / workflow / procedure / lifecycle / traceability` 等通用口径，用户问题或文件名里出现 PEP 时才自然保留。新增 SOP 泛化回归测试，验证 `SOP 文档的流程如何操作？` 不会被硬塞 PEP；相关验证 `tests/test_answer_workflow.py tests/test_app_api.py -q` 为 `30 passed`，`App/web npm run build` 通过。
- 根据 NotebookLM-like 反馈收窄 Chat 主体验：前端 Answer Run 改为默认一行摘要，详细 1-6 步折叠展示；后端新增 `process_operation` route，把“PEP 文档的流程如何操作？”这类问题从泛流程总览中拆出来，回答按操作主线组织；`AnswerEvidencePackage` 新增无依赖 passage selector，优先返回与 matched terms / intent terms 相关的原文片段。验证 `tests/test_answer_workflow.py tests/test_app_api.py -q` 为 `29 passed`，`App/web npm run build` 通过，XP PEP 真实 smoke 返回 `process_operation` 和 p.6/p.9/p.16/p.49/p.58 passage 级引用。
- 强化 Session Chat 的真实流程感和 reference 质量：泛流程问题现在进入 `process_overview` route，检索会优先 PEP 适用范围、V-model、全流程通用要求和阶段主干，Answer Run execution 输出真实 tool_calls；`AnswerEvidencePackage` 改为优先使用 chunk-level 正文 quote，避免 Reference Card 只显示章节标题；前端 Answer Run 卡片补充 route、retrieval query、tools、citation validation 和 model profile 元信息。验证 `tests/test_answer_workflow.py tests/test_app_api.py -q` 为 `27 passed`，`App/web npm run build` 通过，XP PEP 真实 smoke 已返回 p.6/p.9/p.16 正文级引用。
- 接入 Session Query 的真实 LLM composer 与模型选择：`/api/session/query` 支持 `model_profile`，在 `use_llm=true` 时基于已校验 evidence 调用 LLM，并要求输出保留 validated citation label；前端模型下拉现在会传入 `/api/session/query` 和 `/chat/query`，新增 `Azure GPT-5.4` 选项及 `config/azure_gpt5_4_config.json` 占位配置。验证 `tests/test_app_api.py -k "session_query_can_use_selected_llm_model_profile or session_query_uses_selected or session_citations_filter or quote_specific" -q`、`tests/test_app_api.py tests/test_llm_compat.py -q`、`App/web npm run build` 通过。
- 完成 Chat citation integrity hotfix 的后端切片：`/api/session/query` 现在会在输出 citation 前校验 selected source scope、document_id/file_name、quote 和 anchor，并让 deterministic answer 只消费可引用 evidence；citation 匹配已细化到 quote 级，避免同一 source anchor 下不同证据句共用引用标签。同步前端 Citation 类型并扩展 Parser-to-Markdown Spec，补齐 MarkItDown / Docling / Marker / MinerU / RAGFlow / SurfSense / Open Notebook 融合矩阵、artifact contract 和 CT/MI/XP 样例验收。验证 `tests/test_app_api.py -k "session_citations_filter or quote_specific or session_query_uses_selected" -q`、全量后端 `pytest -q` 通过。
- 根据 reviewer 讨论和用户新反馈优化 Design TODO/Spec：新增 Release-0 可信问答纵向闭环，明确 parser 采用 Notebook-like 自动解析和状态提示，不要求每份文档先人审；Ask Workspace 左侧只展示文件级 Source/Tree；Chat 优先修复 citation/source scope 串线、intent/route、Answer Run 可审计摘要和回答可信度。
- 收敛 Design 开发文档：重写 `Design/TODO.md` 为系统级 checkbox-first 执行入口，新增 `Design/Spec-Parser-RAG.md`、`Design/Spec-Chat-Workflow.md`、`Design/Spec-UI-Workspace.md` 三份模块级当前 Spec，分别承接解析/RAG、Chat Runtime 和 UI 四页工作台改造路线。
- 更新 `Design/README.md`，明确旧文档处理策略：PRD 继续作为产品定义；G9/Gate3 保留为证据包；Gate6/MultiInput/Parser-Evals/Pro-Input/Tool-Parser-RAG-Fusion 等旧计划或背景文档降级为历史附件，执行入口统一回到新 TODO 和三份 Spec。
- 同步开发记忆：`MEMORY.md` 和 `Design/dev-memory/SESSION-WIP.md` 已记录新的文档框架、旧文档软整理策略和下一步 Parser / Chat / UI 优先级。当前未物理移动旧文档，避免链接断裂；后续可单独执行归档任务。

## 2026-06-12

- 融合 Chatbox 六环架构到 Ask Workspace 主链路：`/api/session/query` 新增 `answer_run-v0.1` 后端六步 contract，前端 Answer Run 优先显示后端步骤；同时修复 Chat 连续提问路径，支持多轮 transcript、窄屏固定 Chat 面板、composer pointer/Enter 提交和推荐问题横向滚动。验证 `tests/test_app_api.py -k session_query -q`、`App/web npm run build`、运行态 API smoke 与 localhost 5173 窄屏连续两问 smoke 通过。
- 根据最新 UI 审阅反馈重排 G8/P0-03：四页目标框架固定为 `Source Intake -> Review Gate -> Ask Workspace -> Admin / JSON Lab`，当前实现优先走 C 路线 `Ask Workspace v1`，聚焦文件级 Source、Chat/Review 分离、六步 Answer Run、可读 Reference Card 和 Note pin。
- 完成 `Ask Workspace v1` 首版：左侧收敛为 CT/MI/XP 文件级 Source；中间 Chat 移除 Review Queue 和旧 Evidence/Trace 侧栏，新增六步 Answer Run；右侧改为 Reference Viewer + Session Note，并支持 Pin answer / Pin ref；同时修复 Session Query 推荐问题使用 `0 History` 等 parser 噪音标题的问题。验证 `App/web npm run build`、`tests/test_app_api.py -k session_query -q`、`git diff --check` 和 localhost browser smoke 通过。
- 确认记录策略：带跳转链接的详细阶段总结进入 `Design/dev-memory/SESSION-WIP.md`，`CHANGELOG.md` 只保留日期级决策、验证结果和用户可回顾的关键变化。
- 更新 Session MVP Spec 的 P0 继续开发切片：按 `Session Query API 真实闭环 -> Frontend Chat 接入 -> UI 用户操作逻辑拆页 -> Real PEP Smoke Evidence` 推进；用户已认可先完成真实后端 selected-doc 问答，再拆 UI。
- 完成 P0-A/P0-02 首个实现切片：新增前端 `querySession()` 并让主 Chat 在存在当前 PEP/handoff 时调用 `/api/session/query`；`structured_matches` 兼容 `AnswerEvidencePackage`；验证 `tests/test_app_api.py -k session_query`、真实 CT/MI/XP session query smoke、`App/web npm run build`、全量 `pytest -q` 均通过。
- 完成 localhost 浏览器 smoke：FastAPI `127.0.0.1:8000` 与 Vite `127.0.0.1:5173` 同时运行时，MI/XP/CT 三份 PEP 均可加载 handoff 并通过主 Chat 调用 `/api/session/query`；evidence panel 显示当前 PEP 的 document_id/file_name/citation/trace。顺手将左侧 Source card 改为可点击选择当前 PEP，解决三份 PEP 本地切换入口不顺的问题。

## 2026-06-11

- 根据用户反馈重排 Phase 5 P0 优先级：先完成真实后端 Session Query selected-doc 闭环，再拆 UI 用户操作逻辑为 Source Intake / Review Gate / Ask Workspace / Admin JSON Lab；当前 TODO 已明确 `/chat/query` wiki-first 是主 Chat 不可信的核心缺口。
- 使用当前 CT / MI / XP 三份 PEP PDF 真实跑通 `/agent/upload`：三份文档均进入 `needs_review` 而非失败，CT/MI/XP 分别生成 105/75/114 sections、134/84/144 chunks、2/1/5 visual candidates，session handoff 均可返回 tree / graph / review queue / retrieval preview；同时确认当前 `/chat/query` 仍是 wiki-first，后续需要补 Session Query API 的 selected-doc source scope。
- 修复 Chat evidence 串线：切换当前 PEP 时先清空旧 handoff，并在有当前 handoff 时优先显示当前 PEP retrieval preview chunks，避免回落到旧 Wiki page source refs。
- 改造 Session Chat 为 NotebookLM 式工作区：中间区域分为上方消息流、右侧 evidence/context/trace 面板和底部 composer；citation、handoff preview chunks 与当前 tree/source scope 能在 Chat 侧直接核查；`App/web npm run build`、前端代理 `/api/dashboard`、`/chat/query` 和 handoff smoke 均通过。
- 更新 `Design/TODO.md` 的 Phase 5：确认下一阶段 UI 按 NotebookLM 三栏框架接入 G9 Evidence Review Workspace，优先实现真实 Source/Tree、Review Queue、Evidence Card、Quality/JSON/Notes，并明确 CT PEP 人审验收口径。
- 实现 G8-08A-C Evidence Review Workspace 首批 UI 接入：前端新增 `session-handoff-v0.1` 类型和 API client，左侧 Source/Tree/Graph 消费真实 handoff，中间新增 Review Queue，右侧收敛出 Quality / JSON / Notes 最小面板；`App/web npm run build` 通过。
- 新增并重写 `Design/Tool-Parser-RAG-Fusion-Spec.md`，把 G9 定义为 QT Parser Core provider fusion：pypdf、DOCX XML、Docling、OCR/VLM 都作为内部 extraction providers，由 fusion layer、PEP structure resolver、canonical/evidence contract 和 eval gate 产出统一结果。
- 更新 `Design/TODO.md` 和 `Design/Todo+Spec-流程问答工作台.md`：当前执行顺序调整为先做 Parser Fusion Core Contract、Docling Provider Integration、PDF Fusion Pipeline 和 Hybrid RAG，再回到 G8 v0.4 UI/contract、真实 Tree + Chat flow 和 Graph MVP。
- 实现 G9-01 Parser Fusion Core Contract：新增 `Tool/parsers/fusion.py`，定义 `ExtractionBlock`、`LayoutBlock`、`TableBlock`、`VisualCandidate`、`FusionDecision` 和 `parser_fusion` metadata builder；`apply_parse_workflow_contract()` 已为现有 parser 自动写入默认 single-provider fusion trace，完整后端验证 `116 passed`。
- 实现 G9-02 Docling Provider Integration：新增 `Tool/parsers/providers/docling_provider.py` 和 provider package，采用 lazy import + injectable converter，将 Docling-like text/layout/table/picture 信息映射为 QT fusion blocks/candidates，并生成 `docling_provider_extraction` metadata；真实 Docling 依赖仍待单独确认后加入 requirements，完整后端验证 `119 passed`。
- 实现 G9-03 PDF Fusion Pipeline：新增 `Tool/parsers/pdf_fusion.py` 和 `tests/test_pdf_fusion_pipeline.py`，将 pypdf canonical fragments 与 Docling layout/text/table/visual output 融合为 `parser_fusion` metadata；`FusionDecision` 记录 bbox / reading_order anchor 增强和 provider contribution；现有 `parse_pdf()` 主路径保持稳定，完整后端验证 `121 passed`。
- 实现 G9-04 DOCX Table/Layout Fusion：新增 `Tool/parsers/docx_fusion.py` 和 `tests/test_docx_fusion_pipeline.py`，将 DOCX XML fragments/tables 与 Docling layout/text/table output 融合为 `docx_provider_fusion` metadata；DOCX table anchors 已补 cell range、row count、column count 并进入 source anchors，section table chunks 支持 `tbl.1 R1C1:R2C2` 引用和 role/deliverable signals，完整后端验证 `123 passed`。
- 实现 G9-05 OCR / Multimodal Visual Provider：新增 `Tool/parsers/providers/visual_provider.py` 和 `tests/test_visual_provider.py`，把 visual_review_items 与 Docling image candidates 规范化为 `VisualCandidate` 队列；候选保留 source_refs、page/bbox/crop anchors、backend、confidence 和 review_status，primary gate 只放行 reviewed/accepted 或高置信且有 source anchors 的视觉证据，真实 OCR/VLM 依赖仍未加入 requirements，完整后端验证 `126 passed`。
- 实现 G9-06 Retriever Interface + Hybrid RAG：新增 `Tool/retrieval/retrievers.py` 和 `tests/test_retriever_interface.py`，将现有规则检索包装为 `RuleSectionRetriever`，并新增无依赖 `FullTextRetriever`、可注入 embedding 的 `VectorRetriever`、deterministic RRF `HybridRetriever`；`evaluate_retrieval_cases()` 可接收 pluggable retriever，完整后端验证 `131 passed`。
- 实现 G9-07 Fusion / Retrieval / Answer Eval 扩展：新增 `Tool/evals/fusion_eval.py`、`Tool/evals/answer_eval.py` 和 `tests/test_g9_eval_extensions.py`，并扩展 `Tool/evals/retrieval_eval.py` 的 backend comparison；当前 eval 可报告 provider contribution、low-confidence fusion decisions、retrieval backend miss、missing citation、unsupported claims 和 evidence gap 未提示风险，完整后端验证 `134 passed`。
- 实现 G9-08 Session API Handoff：新增 `/api/session/handoff/{document_id}` 和 API contract test，基于 canonical sections/chunks/parse_workflow 输出 `session-handoff-v0.1` payload，包含 source summary、真实 tree、chunk/signal graph seeds、retrieval preview、chat contract 和 quality gates；完整后端验证 `135 passed`。
- 完善 `Design/Pro-Input-Praser.md` 的 G9 主线总结：补充 PDF/DOCX parser、Docling/OCR/VLM provider、fusion metadata、retriever backend、answer evidence、eval findings、LLM 二轮修正和 session handoff 的能力地图与 JSON 闭环说明。
- 新增 `Design/G9-Human-Review-Pack.md`，将 G9 人审路线固定为先生成 Markdown + JSON snapshots 的内容集合，集中核查 parser、provider fusion、visual candidates、retrieval/answer evidence 和 session handoff；已补充 `ingest/parse`、API snapshot 导出命令、最小必看 JSON 和字段查看顺序，再进入 G8 UI 接入。

## 2026-06-10

- 基于用户反馈将 PRD 升级为 v0.3 NotebookLM 式产品：外部 Landing / Knowledge Base 负责知识库维护和入口，正式互动 Session 作为本次 MVP，右侧 Session Note / Workflow Studio 承接 HTML、飞书 Markdown、Reference、Mermaid、BU diff 和 publish note 入口。
- 实现 v0.3 NotebookLM 三栏 Session Workspace UI skeleton：左 Sources/Tree/Graph，中 Session Chat，右 Session Note/Reference/Workflow/Admin；复用现有上传、模型选择、LLM 开关、推荐问题、citation 和后台入口；`npm run build` 与 localhost 关 LLM `/chat/query` smoke 通过，浏览器 console 无 error。
- 新增 `Design/MultiInput-Parser-RAG-Workflow-设计.md`，将底层能力收敛为多格式解析、章节化、Script/LLM/Evals 分工、Retrieval Strategy Matrix 与 Session RAG Workflow。
- 新增 `Design/Parser-Workflow-Evals-实施计划.md`，将 BUs_CER / LEFA_v6 的 Evals 经验收敛为抓取完整性、真源返回、章节正确性三类质量门，并明确 parser、后端接口、前端 UI 的人工核查 Gate。
- 实现 Gate 1 Parser Workflow Contract 与 Gate 2 Markdown parser MVP：新增 parse workflow/eval summary 生成、Markdown 解析、parse-summary/sections API，并扩展上传响应返回结构质量与 review items；最终验证 `89 passed`。
- 实现 Parser Quality Eval MVP：新增 `Tool/evals/parser_quality.py`，动态检查抓取缺口、章节漂移、章节树错误、噪音标题、复杂表格/图片风险和 LLM 输出缺证据，并接入 workflow summary；最终验证 `89 passed`。
- 实现 Gate 3 PDF/DOCX Chapterization MVP：新增共享 heading detector，DOCX 继续按 XML 元素顺序解析并吸收 Heading 样式、compact 编号标题和字母子标题，PDF 支持 R 阶段标题、重复页眉清理和 `heading_path` anchors；最终验证 `92 passed`。
- 增强 Gate 3 PEP PDF smoke 检查机制：将文档控制页眉、目录点线页码纳入 P2-03 噪音 eval 和 PDF 清理，并扩展 P2-01 明示孤立深层章节；CT / MI / XP PEP smoke 当前全部保留 source anchors，剩余章节树风险进入 `needs_review`；最终验证 `97 passed`。
- 新增 `Design/Gate3-PEP-PDF-Review.md`，将 CT / MI / XP PEP smoke 输出整理成人工 review 报告，便于核查章节树、History/TOC 噪音、关键章节命中和 Reference 样例。
- 基于 CT 人工反馈补强 PDF parser：新增前置 Content/TOC 页过滤、History 表格候选抽取、History 续页行过滤、figure caption candidate 和短标题续行拼接；CT 7.16 正文标题已完整保留为“法规核准计划”，CT / MI / XP 均生成 History table 与 figure caption 候选。
- 新增 `Design/Pro-Input-Praser.md` 并刷新 `Design/Gate3-PEP-PDF-Review.md`，沉淀 Pro Input Parser 的经验、难点、OCR/multimodal 决策边界和人工 review 清单。
- 实现 Gate 4/5 Section Chunk + Retrieval Eval MVP：新增 section chunk builder、deterministic source-scope retrieval、retrieval eval cases、`/api/documents/{document_id}/chunks` 和 visual OCR / multimodal review queue；CT / MI / XP smoke 当前生成 146 / 93 / 163 chunks，最终验证 `109 passed`。
- 规划 Gate 6 Adaptive Answer Workflow：主 Chat 采用自适应模式，核心事实带 reference，输出格式按 question intent 变化；新增 `Design/Gate6-Adaptive-Answer-Workflow-Plan.md`，覆盖企业关键词归一、AnswerEvidencePackage、adaptive prompt policy 和 Answer Evals。
- 实现 Gate 6 Answer Foundation：新增 `Tool/workflows/answer.py`，提供 `QuestionIntent`、企业关键词归一和 `AnswerEvidencePackage`，把 retrieval hits 转为带 document / section / anchor / quote 的 answer evidence，并将 History/template change 与缺 source_refs hit 排除出 primary evidence；当前验证 `compileall`、`pytest`、`git diff --check`、diagnostics 通过，`114 passed`。
- 整理 `Design/` 信息架构：新增 `Design/TODO.md` 作为唯一阶段计划入口，计划、方案、TODO 都按 Phase 0-5 展开；`Design/README.md` 改为附件导航，外部 Plan / Review / Notes 文档降级为证据附件或历史背景；采用软整理策略，暂不大规模改名。

## 2026-06-09

- 新增 `Design/PRD-流程问答工作台.md`，将 vNext 产品方向收敛为“上传文档 -> AI 解析 -> 主 Chat 流程问答 -> Reference 映射 -> 导出/训练/差异”的工作台主线。
- 新增 `Design/Todo+Spec-流程问答工作台.md`，按 Phase 0-5 拆解 Chat Answer Contract、Process Index、PEP/R2/PO 问答闭环、多模态导出、BU 差异和治理回流任务。
- 基于 grill-me 范围澄清将 PRD 更新为 v0.2 决策版：首版聚焦 PEP 路径、R2/PO 问答、类 ChatGPT 主界面、自然语言长答案、文件/章节/quote Reference、GPT-4o/GPT-5 类模型下拉和 BU 差异首版可用。
- 重写 `Design/Todo+Spec-流程问答工作台.md` 和 `Design/dev-memory/TODO.md`，从长 phase 表改为更清晰的 checkbox 执行板。
- 前端完成一版 v0.2 UI 原型：旧右侧 ChatbotPanel 升级为主 Chat，顶部展示文档/阶段/角色和模型选择，右侧抽屉承载上下文、引用、输出和后台入口。
- 在 `QT-Wiki-功能文档.md` 顶部补充 2026-06-09 vNext 产品收敛说明，明确 GitHub Pages 作为静态前端/静态索引/导出产物托管目标，上传和 AI 解析先由本地或后续轻量服务生成数据。
- 新增根目录 `MEMORY.md` 与 `Design/dev-memory/`，集中保存项目记忆、会话 WIP、用户待审 TODO 和开发记忆 changelog。
- 新增 `Design/README.md` 作为当前设计入口，并将旧首次上传/审批包框架、旧 Regulation Navigator 框架和原型资产归档到 `Design/old/`。
- 更新 `README.md` 与 `QT-Wiki-功能文档.md` 中的设计文档路径，避免继续指向已归档的 root `Design.md`。

## 2026-04-29

- 前端主工作台重排为三列：左侧为对话历史与快捷设置，中间为流程切换与流程内容，右侧为固定 chatbot，不再把 Query 当成单独页面切换。
- 新增前端查询历史状态，右侧发起的问题会沉淀到左栏历史，可回看并重新聚焦已有问答结果。
- 中间流程区改为固定流程切换条，流程操作与聊天问答解耦，切换 Ingest / Wiki / Lint / Settings 时不会打断 chatbot。
- 收缩三列视觉噪音：压缩左右栏宽度、合并 chatbot 底部上下文卡片、移除 Ingest 冗余统计与左栏重复计数，整体改为更紧凑的工作台排布。

## 2026-04-29

- Ingest 工作台新增“最近上传”运行列表，可在前端显式切换当前上传上下文，不再被历史候选页和历史审批包持续干扰。
- `/api/ingest/runs` 已接入前端工作区刷新链路，上传后、审批后只刷新 Ingest 工作区数据，不再每次都拉全量 dashboard 状态。
- Ingest 前端补充当前聚焦清理入口和 workspace 摘要计数，便于回到“仅待审核”工作模式。
- 新增 `/api/ingest/runs` 回归测试，固定最近运行按时间倒序返回的行为。

## 2026-04-29

- 新增根目录 `CHANGELOG.md`，用于按日期记录后续变更。
- 为 Wiki 模型层新增最小审批包结构：`DocumentIdentity`、`ReviewObject`、`ReviewRelation`、`ReviewIssue`、`HumanReviewQuestion`、`ReviewPackage`。
- 为存储层新增审批包 JSON 和 Obsidian Markdown 输出目录与读写接口。
- Ingest 流程现在会在生成候选页面的同时生成一个最小审批包，先覆盖文档身份、证据摘要、风险提示和待人工确认问题。
- 新增审批包相关测试，覆盖保存/加载和 Ingest 构建审批包的基础行为。
- 新增 `/api/ingest/review-packages` 接口，后端可返回审批包列表供前端审阅。
- 前端 Ingest 视图改为以审批包为主视图，展示文档身份、人工关口、风险问题和关联候选页。
- 候选页批准/拒绝动作暂时保留原逻辑，审批包先承担“确认关键判断”的工作台角色。
- 为审批包新增关口 1 决策字段：`identity_decision`、确认后的业务类型/效力/强约束、审核备注、审核人、审核时间。
- 新增审批包决策写回能力和 `/api/ingest/review-packages/{package_id}/decision` 接口，文档身份确认不再只是只读展示。
- 前端 Ingest 页面新增文档身份确认表单，支持确认或退回重判，并展示已确认结果。
- 候选页发布新增前置约束：对应审批包的文档身份未确认时，前端禁用发布按钮，后端 API 也会返回 `409` 拒绝发布。
- 为审批包补齐最小对象抽取，当前会规则提取 `requirement`、`process_step`、`record`、`role` 四类对象，并绑定来源片段。
- `/api/ingest/review-packages` 现在会返回 `extracted_objects`，前端 Ingest 页面新增“抽取对象”区块用于审阅。
- 新增对象抽取和 API 兼容性测试，确认最小对象层已进入可审状态。
- 为审批包补齐最小关系抽取，当前会规则生成 `requires`、`produces`、`responsible_for` 三类关系，并绑定来源片段。
- 新增关系决策关口和 `/api/ingest/review-packages/{package_id}/relations/decision` 接口，关键关系现在可以正式确认或退回重判。
- 候选页发布条件升级为“双关口”通过：文档身份已确认，且关键关系已确认或无关系需要确认。
- 前端 Ingest 页面新增“抽取关系”与关系审核区块，支持在发布前完成人工映射确认。
- QueryAgent 现在会直接消费已批准审批包中的结构化对象与关系；`/chat/query` 返回 `structured_matches`，并把审批包证据补进 citations。
- 新增 `App/agents/structured_knowledge.py`，统一承载已批准审批包筛选、关系展开、问题上下文构建、映射矩阵和 slides 提纲生成逻辑。
- 新增导出接口 `/api/exports/mapping-matrix` 与 `/api/exports/slides-outline`，导出源只使用已批准审批包，可直接复用为法规-流程映射和汇报提纲底稿。
- 前端 Ingest 页补齐关口 2：支持关键关系审核、显示关系决策状态，并把候选页发布按钮切换为“文档身份 + 关系确认”双关口控制。
- 前端 Query / Settings 页补齐结构化消费与导出预览：查询结果展示命中的审批包，设置页可直接拉取映射矩阵和 slides 提纲。
- 新增回归测试，覆盖关系关口发布约束、结构化 Query 返回、映射矩阵导出和 slides 提纲导出；当前验证结果为 `15 passed`，`npx tsc --noEmit` 通过。
- 修复前端“看起来没用到 LLM / 反馈不真实”的问题：默认开启 LLM、Ingest 页显式展示 LLM 开关、Query 结果按实际 `used_llm` 显示，不再把请求开关误当成真实执行结果。
- 修复前端静默吞错并回退 mock 的问题：API 失败现在直接返回真实错误信息，控制台会明确提示后端错误而不是假装成功。
- 修复 `dashboard` 被空 JSON / 损坏 JSON 页面文件打崩的问题：`wiki.store.files.load_all_pages()` 与 `list_review_packages()` 现在会跳过无效文件并打印告警。
- 新增回归测试覆盖无效页面 JSON 跳过逻辑；当前验证结果升级为 `16 passed`，`npx tsc --noEmit` 通过。
- 新增“当前上传会话”上下文：上传接口现在返回 `document_id`、`review_package_id` 和 `candidate_ids`，供前端在上传后直接聚焦本次文档。
- Ingest 前端新增过滤工作台：`当前上传 / 仅待审核 / 全部历史`，上传成功后会自动切换到“当前上传”并定位到本次审批包，显著降低历史候选和历史审批包干扰。
- 将工作区刷新与 dashboard 全量刷新拆开：审批、关系确认、上传后只刷新 Ingest 工作区数据，不再每次都把全量 dashboard / lint 状态拉进主操作链。
- 新增上传返回运行上下文的回归测试；当前验证结果升级为 `17 passed`，`npx tsc --noEmit` 通过。

