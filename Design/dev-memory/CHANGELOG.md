# Development Memory Changelog

## 2026-06-11

- 新增并重写 [../Tool-Parser-RAG-Fusion-Spec.md](../Tool-Parser-RAG-Fusion-Spec.md)，将 G9 调整为 QT Parser Core provider fusion：pypdf、DOCX XML、Docling、OCR/VLM 都作为内部 extraction providers，由 fusion layer、PEP structure resolver、canonical/evidence contract 和 eval gate 产出统一结果。
- 实现 G9-01 Parser Fusion Core Contract：新增 `Tool/parsers/fusion.py`，定义 provider fusion block/decision dataclasses 和 `parser_fusion` metadata builder；现有 parser workflow 已自动记录默认 single-provider trace，完整后端验证 `116 passed`。
- 实现 G9-02 Docling Provider Integration：新增 `Tool/parsers/providers/docling_provider.py`，采用 lazy import + injectable converter，将 Docling-like text/layout/table/picture 信息映射为 QT fusion blocks/candidates，并生成 `docling_provider_extraction` metadata；真实 Docling 依赖待单独确认后加入 requirements，完整后端验证 `119 passed`。
- 实现 G9-03 PDF Fusion Pipeline：新增 `Tool/parsers/pdf_fusion.py` 和 `tests/test_pdf_fusion_pipeline.py`，把 pypdf canonical fragments 与 Docling layout/text/table/visual output 融成 `parser_fusion` metadata；现有 `parse_pdf()` 主路径保持稳定，完整后端验证 `121 passed`。
- 实现 G9-04 DOCX Table/Layout Fusion：新增 `Tool/parsers/docx_fusion.py` 和 `tests/test_docx_fusion_pipeline.py`，把 DOCX XML fragments/tables 与 Docling layout/text/table output 融成 `docx_provider_fusion` metadata；DOCX table anchors 已补 cell range、row count、column count，section table chunks 支持 table/cell anchor label 和 role/deliverable signals；完整后端验证 `123 passed`。
- 实现 G9-05 OCR / Multimodal Visual Provider：新增 `Tool/parsers/providers/visual_provider.py` 和 `tests/test_visual_provider.py`，把 visual_review_items 与 Docling image candidates 转为可评审 `VisualCandidate` 队列；候选保留 source_refs、page/bbox/crop anchors、backend、confidence 和 review_status，primary gate 只放行 reviewed/accepted 或高置信且有 source anchors 的视觉证据；完整后端验证 `126 passed`。
- 实现 G9-06 Retriever Interface + Hybrid RAG：新增 `Tool/retrieval/retrievers.py` 和 `tests/test_retriever_interface.py`，把现有 `retrieve_sections()` 包装为 `RuleSectionRetriever` baseline，并新增 `FullTextRetriever`、可注入 embedding 的 `VectorRetriever`、RRF `HybridRetriever`；retrieval eval 可接收 pluggable retriever，完整后端验证 `131 passed`。
- 实现 G9-07 Fusion / Retrieval / Answer Eval 扩展：新增 `Tool/evals/fusion_eval.py`、`Tool/evals/answer_eval.py` 和 `tests/test_g9_eval_extensions.py`，扩展 retrieval backend comparison，并让 low-confidence fusion、backend miss、missing citation、unsupported claims 和 evidence gap 未提示进入 findings；完整后端验证 `134 passed`。
- 实现 G9-08 Session API Handoff：新增 `/api/session/handoff/{document_id}` 和 API contract test，基于 canonical sections/chunks/parse_workflow 输出真实 Tree、Graph seeds、retrieval preview、chat contract 和 quality gates；完整后端验证 `135 passed`。
- 更新 [../TODO.md](../TODO.md) 与 [../Todo+Spec-流程问答工作台.md](../Todo+Spec-流程问答工作台.md)，把当前主线调整为 Tool 先行：先补真实 parser/RAG/evidence contract，再继续 G8 v0.4 UI、真实 Tree、Chat transcript 和 Graph MVP。

## 2026-06-10

- 基于用户反馈将产品形态从 v0.2 ChatGPT 抽屉版升级为 v0.3 NotebookLM 式知识工作台：Landing / Knowledge Base / Session Workspace。
- 明确本次 MVP 最小目标为正式互动 Session Workspace：左 Sources/Tree/Graph，中 Session Chat，右 Session Note/Workflow Studio。
- 实现 v0.3 NotebookLM 三栏 Session Workspace UI skeleton：左 Sources/Tree/Graph，中 Session Chat，右 Session Note/Reference/Workflow/Admin；复用现有上传、模型选择、LLM 开关、推荐问题、citation 和后台入口；`npm run build` 与 localhost 关 LLM `/chat/query` smoke 通过，浏览器 console 无 error。
- 更新 PRD、Todo+Spec、dev-memory TODO 和 Session WIP，记录 Selected Docs / Upload To Session / All Sources、session 上传状态标、note publish 入口和 RAG/局部直读技术路径。
- 新增 [../MultiInput-Parser-RAG-Workflow-设计.md](../MultiInput-Parser-RAG-Workflow-设计.md)，将底层能力升级为多格式解析、章节化、Script/LLM/Evals 分工、Retrieval Strategy Matrix 和 Session RAG Workflow。
- 新增 [../Parser-Workflow-Evals-实施计划.md](../Parser-Workflow-Evals-实施计划.md)，吸收 BUs_CER / LEFA_v6 Evals 的抓取完整性、真源返回、章节正确性质量门，并定义 parser -> backend -> frontend 的 Gate 推进顺序。
- 实现 Gate 1 Parser Workflow Contract 与 Gate 2 Markdown parser MVP：canonical metadata、upload response、parse-summary/sections API 均可返回 workflow/eval/quality 字段；最终验证 `89 passed`。
- 实现 Parser Quality Eval MVP：新增 `Tool/evals/parser_quality.py`，将抓取缺口、章节漂移、章节树错误、噪音标题、复杂表格/图片风险和 LLM 输出缺证据接入 workflow summary；最终验证 `89 passed`。
- 基于 CT PEP 人工 review 修复 PDF parser：Content/TOC 页不再进入 section，History 表格进入 `TableData`，History 续页行不再污染正文，figure caption 进入 `FigureData`，CT 7.16 标题续行已拼回完整。
- 新增 [../Pro-Input-Praser.md](../Pro-Input-Praser.md)，记录 parser 难点、处理方法、OCR 与 multimodal 边界，并刷新 [../Gate3-PEP-PDF-Review.md](../Gate3-PEP-PDF-Review.md) 的 CT / MI / XP smoke 数字。
- 完成 Gate 4/5 Section Chunk + Retrieval Eval MVP：新增 section chunk builder、source-scope retrieval、retrieval eval cases、`/api/documents/{document_id}/chunks` 和 `visual_review_items`；CT / MI / XP smoke 当前生成 146 / 93 / 163 chunks，retrieval eval `recall_at_k=1.0`，最终验证 `109 passed`。
- 规划 Gate 6 Adaptive Answer Workflow：用户确认主 Chat 采用自适应模式，核心事实带 reference，输出格式按问题意图变化；新增计划文档覆盖 QuestionIntent、企业关键词归一、AnswerEvidencePackage、adaptive prompt policy 和 answer eval。
- 实现 Gate 6 Answer Foundation：新增 `Tool/workflows/answer.py`，固化 QuestionIntent、企业关键词归一和 RetrievalResult -> AnswerEvidencePackage；History/template change 与缺 source_refs hit 不作为 primary evidence；当前验证 `compileall`、`pytest`、`git diff --check`、diagnostics 通过，`114 passed`。
- 整理 Design 目录信息架构：新增 [../TODO.md](../TODO.md) 作为唯一阶段计划入口，计划、方案、TODO 都按 Phase 0-5 展开；[../README.md](../README.md) 改为附件导航；外部 Plan / Review / Notes 文档降级为证据附件或历史背景，暂不大规模改名。

## 2026-06-09

- 建立 `Design/dev-memory/`，用于跨会话保存项目稳定记忆、当前会话状态、可审阅 TODO 和本开发线变更记录。
- 新增根目录 `MEMORY.md` 指向开发记忆入口。
- 记录 vNext 主线为“上传文档 -> AI 解析 -> 主 Chat 流程问答 -> Reference 映射 -> Markdown/Mermaid/训练/BU diff 输出”。
- 记录旧设计稿已经归档到 `Design/old/`，当前未删除旧内容。
- 新增 `Design/README.md` 作为设计目录入口，区分当前 vNext 框架、开发记忆和 archived old frameworks。
- 修复 README 与功能文档里的旧 `Design.md` 路径说明。
- 采用 `repo-dev-harness` 作为本 repo 的轻量开发框架，并将 `TODO.md` 规范化为 checkbox-first：原始目标、已完成证据、当前主线、Later/backlog、收尾规则。
- 记录 QT-CER-Tool `BUs_CER` 分支和 `Skill/docx-extraction-skill` 已可访问，后续作为 parser/extractor API adapter 参考。
- 基于 grill-me 结果更新 PRD 为 v0.2 决策版：MVP 聚焦 PEP 路径、类 ChatGPT 主 Chat、自然语言长答案、文件/章节/quote Reference、模型下拉和 BU diff 首版可用。
- 重写 `Todo+Spec-流程问答工作台.md` 与 `dev-memory/TODO.md`，改为清晰 checkbox 执行板。
- 完成第一版 UI 原型：主界面改为顶部上下文与模型选择、中间主 Chat、右侧 Context/Reference/Outputs/Admin 抽屉；前端 build 与 localhost 渲染已验证。
