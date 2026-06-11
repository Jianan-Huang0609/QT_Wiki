# Changelog

## 2026-06-11

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

