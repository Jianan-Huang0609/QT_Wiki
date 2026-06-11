# Session WIP

## 2026-06-10

### 2026-06-11 Update

- 已新增并重写 [../Tool-Parser-RAG-Fusion-Spec.md](../Tool-Parser-RAG-Fusion-Spec.md)，把 G9 调整为 QT Parser Core provider fusion：pypdf、DOCX XML、Docling、OCR/VLM 都作为内部 extraction providers，由 fusion layer、PEP structure resolver、canonical/evidence contract 和 eval gate 产出统一结果。
- 已更新 [../TODO.md](../TODO.md)：当前焦点从直接继续 G8 UI 调整为先做 Phase 3.5 / G9 QT Parser Core，再回到 v0.4 UI/contract、真实 Tree + Chat flow 和 Graph MVP。
- 已更新 [../Todo+Spec-流程问答工作台.md](../Todo+Spec-流程问答工作台.md)：Session MVP 的 Phase 2 明确依赖 Tool Parser Core Spec，前端 Tree/Graph/Chat 需要消费真实 Tool contract。
- 本轮继续开发已完成 G9-01 Parser Fusion Core Contract：新增 `Tool/parsers/fusion.py`、`tests/test_parser_fusion_contract.py`，并让 `apply_parse_workflow_contract()` 自动写入默认 `parser_fusion` metadata；完整后端验证 `116 passed`。
- 已完成 G9-02 Docling Provider Integration：新增 lazy import + injectable converter 的 Docling provider，把 Docling-like text/layout/table/picture 信息映射为 QT fusion blocks/candidates，并生成 `docling_provider_extraction` metadata；真实 Docling 依赖待单独确认后加入 requirements；完整后端验证 `119 passed`。
- 已完成 G9-03 PDF Fusion Pipeline：新增 `Tool/parsers/pdf_fusion.py`、`tests/test_pdf_fusion_pipeline.py`，把 pypdf canonical fragments 与 Docling layout/text/table/visual output 融合为 `parser_fusion` metadata；`FusionDecision` 记录 page/text 对齐、bbox/reading_order anchor 增强和 table/visual provider contribution；现有 `parse_pdf()` 主路径保持稳定，完整后端验证 `121 passed`。
- 已完成 G9-04 DOCX Table/Layout Fusion：新增 `Tool/parsers/docx_fusion.py`、`tests/test_docx_fusion_pipeline.py`，把 DOCX XML fragments/tables 与 Docling layout/text/table output 融合为 `docx_provider_fusion` metadata；DOCX table anchors 已补 `cell_range`、`row_count`、`column_count` 并进入 source anchors，section table chunks 可引用 `tbl.1 R1C1:R2C2` 并输出 `role_table` / `deliverable_table` signals；完整后端验证 `123 passed`。
- 已完成 G9-05 OCR / Multimodal Visual Provider：新增 `Tool/parsers/providers/visual_provider.py`、`tests/test_visual_provider.py`，把 `visual_review_items` 和 Docling image candidates 转成可评审 `VisualCandidate` 队列；候选保留 source_refs、page/bbox/crop anchors、backend、confidence、review_status，primary gate 只放行 reviewed/accepted 或高置信且有 source anchors 的视觉证据；真实 OCR/VLM 依赖暂未加入 requirements；完整后端验证 `126 passed`。
- 已完成 G9-06 Retriever Interface + Hybrid RAG：新增 `Tool/retrieval/retrievers.py`、`tests/test_retriever_interface.py`，把现有 `retrieve_sections()` 包成 `RuleSectionRetriever` baseline，并新增 `FullTextRetriever`、可注入 embedding 的 `VectorRetriever`、deterministic RRF `HybridRetriever`；`evaluate_retrieval_cases()` 可接收 pluggable retriever；完整后端验证 `131 passed`。
- 已完成 G9-07 Fusion / Retrieval / Answer Eval 扩展：新增 `Tool/evals/fusion_eval.py`、`Tool/evals/answer_eval.py`、`tests/test_g9_eval_extensions.py`，并扩展 `Tool/evals/retrieval_eval.py` 的 backend comparison；当前可将 provider contribution、low-confidence fusion decisions、retrieval backend miss、missing citation、unsupported claims 和 evidence gap 未提示风险写入 findings；完整后端验证 `134 passed`。
- 已完成 G9-08 Session API Handoff：新增 `/api/session/handoff/{document_id}` 和 API contract test，基于 canonical sections/chunks/parse_workflow 输出 source summary、真实 section tree、chunk/signal graph seeds、retrieval preview、chat source_scope/request/answer contract 和 quality gates；完整后端验证 `135 passed`。

### Done

- 新增 vNext PRD: [../PRD-流程问答工作台.md](../PRD-流程问答工作台.md)。
- 新增 Todo + Spec: [../Todo+Spec-流程问答工作台.md](../Todo+Spec-流程问答工作台.md)。
- 在 [../../QT-Wiki-功能文档.md](../../QT-Wiki-功能文档.md) 顶部补充 vNext 产品收敛说明。
- 在 [../../CHANGELOG.md](../../CHANGELOG.md) 记录 vNext PRD 与计划文档更新。
- 旧设计内容已归档到 [../old/](../old/)，当前没有删除旧稿。
- 已建立开发记忆目录 [./](./)，并新增根目录指针 [../../MEMORY.md](../../MEMORY.md)。
- 已确认 `repo-dev-harness` 适合本 repo，并将 [TODO.md](TODO.md) 规范化为 checkbox-first 执行清单。
- 已确认 QT-CER-Tool `BUs_CER` 分支可访问，`Skill/docx-extraction-skill` 可作为 parser/extractor adapter 参考。
- 已完成早期 grill-me 范围澄清：PEP 路径、自然语言长答案、文件/章节/quote Reference、模型下拉、BU diff 首版可用；其中 UI 形态已由 v0.3 NotebookLM 式 Session Workspace 承接。
- 已将 PRD、Todo+Spec、dev-memory TODO 更新为当前决策版。
- 已完成第一版 v0.2 UI 原型：顶部上下文与模型选择、中间主 Chat、右侧 Context/Reference/Outputs/Admin 抽屉；该原型作为已验证探索版本保留，下一步由 v0.3 Session Workspace 替换。
- 已验证 v0.2 前端构建通过，并在 localhost 浏览器确认新壳层与抽屉渲染。
- 已根据用户确认将产品形态升级为 NotebookLM 式：Landing / Knowledge Base / Session Workspace。
- 已更新 PRD 到 v0.3，明确本次 MVP 最小目标是正式互动 Session Workspace。
- 已确认 `PEP/` 目录下 CT / MI / XP 三份 PEP PDF 可抽文本，适合章节级 RAG。
- 已完成 Multi-input Parser + RAG Workflow 研究：现有 parser 覆盖 PDF/DOCX/XLSX/PPTX，Markdown 待接入；下一步以章节化、Script/LLM/Evals 分工和 section-first retrieval 为底座。
- 已新增 Parser Workflow + Evals 实施计划：吸收 BUs_CER / LEFA_v6 的抓取完整性、真源返回、章节正确性三类质量门，并定义 Gate 1-7 人工核查节点。
- 已实现 Gate 1 Parser Workflow Contract 与 Gate 2 Markdown parser MVP，最终验证 `89 passed`。
- 已实现 Parser Quality Eval MVP：开发过程中的静态质量用诊断/测试/审查守门，动态内容质量已覆盖抓取缺口、章节漂移、复杂表格/图片风险和 LLM 输出缺证据；最终验证 `89 passed`。
- 已实现 Gate 3 PDF/DOCX Chapterization MVP：DOCX 按 XML 元素顺序解析并吸收 Heading 样式、compact 编号标题和字母子标题；PDF 支持 R 阶段标题、重复页眉清理和 `heading_path` anchors；最终验证 `92 passed`。
- 已完成 Gate 3 PEP smoke 检查机制补强：CT / MI / XP PEP 自动 smoke 已跑，文档控制页眉和目录点线噪音进入 P2-03 + PDF 清理，孤立深层章节进入 P2-01 details；最终验证 `97 passed`。
- 已新增 [../Gate3-PEP-PDF-Review.md](../Gate3-PEP-PDF-Review.md)，把 CT / MI / XP PEP smoke 结果整理为人工核查报告。
- 已根据 CT 人工反馈补强 PDF parser：Content/TOC 页过滤、History table candidate、History 续页行过滤、figure caption candidate、短标题续行拼接；CT 7.16 已完整保留“法规核准计划”。
- 已新增 [../Pro-Input-Praser.md](../Pro-Input-Praser.md)，沉淀 parser 经验、难点、OCR/multimodal 决策边界和人工 review 清单。
- 已刷新 [../Gate3-PEP-PDF-Review.md](../Gate3-PEP-PDF-Review.md) 的 CT / MI / XP smoke 数字：三份 PEP 均有 History table 和 figure caption candidate，rootless child sections 清零，剩余 P2-01 level jump warning。
- 已完成 Gate 4/5 Section Chunk + Retrieval Eval MVP：新增 section chunk builder、deterministic retrieval、retrieval eval cases、`/api/documents/{document_id}/chunks`，并补 `visual_review_items` 作为 OCR / multimodal review queue。
- 已跑真实 CT / MI / XP smoke：CT 146 chunks / visual 2，MI 93 chunks / visual 1，XP 163 chunks / visual 5；CT 7.16 selected-docs 检索排第一，R2 查询回到 R2 正文/裁剪规则。
- 已完成全量验证：`compileall`、`pytest`、`git diff --check` 通过，当前 `109 passed`，仅保留 StarletteDeprecationWarning。
- 已根据用户确认新增 Gate 6 自适应主 Chat 回答计划：[../Gate6-Adaptive-Answer-Workflow-Plan.md](../Gate6-Adaptive-Answer-Workflow-Plan.md)，明确 question intent、企业关键词归一、AnswerEvidencePackage、adaptive prompt policy 和 answer eval。
- 已整理 Design 目录入口：新增 [../TODO.md](../TODO.md) 作为唯一阶段计划入口；计划、方案、TODO 都在该文件按 Phase 0-5 展开；外部 Plan / Review / Notes 文档降级为附件证据或历史背景；[../README.md](../README.md) 只做附件导航。
- 已实现 Gate 6 Answer Foundation：新增 `Tool/workflows/answer.py`，覆盖 `QuestionIntent`、企业关键词归一和 `RetrievalResult -> AnswerEvidencePackage`；History/template change 和缺 source_refs hit 不作为 primary evidence；验证 `compileall`、`pytest`、`git diff --check`、diagnostics 通过，当前 `114 passed`。
- 已实现 v0.3 NotebookLM 三栏 Session Workspace skeleton：左 Sources/Tree/Graph，中 Session Chat，右 Session Note/Reference/Workflow/Admin；复用现有上传、模型选择、LLM 开关、推荐问题、citation 和后台入口。
- 已完成 UI 本地验证：`App/web` 的 `npm run build` 通过；localhost 浏览器关 LLM 后点击“现在在 R2 阶段，我作为 PO 应该做什么？”真实调用 `/chat/query`，Reference 面板回填 citations，console 无 error。

### Session Output Summary

- 本轮核心产出：从产品愿景推进到 parser / retrieval / visual review / answer workflow 的阶段化实施底座，并启动 v0.3 NotebookLM Session Workspace UI skeleton。
- 文档产出：PRD v0.3、Session MVP Spec、Parser/RAG workflow 设计、Parser/Evals 历史实施计划、G3 review、Parser notes、G6 历史方案、Design master TODO 与 README 导航。
- 组织产出：Design 目录采用轻量“一主多附件”规则，[../TODO.md](../TODO.md) 是唯一阶段计划入口；外部 plan/review/notes 只作为附件。
- 验证产出：最近完整后端测试验证为 `135 passed`；本轮 UI 验证为 `npm run build` 通过，localhost `/chat/query` smoke 通过，console 无 error。

### In Progress

- 当前主线以 [../TODO.md](../TODO.md) 为准：Phase 3.5 / G9 QT Parser Core 的 G9-01 至 G9-08 已完成；下一步建议进行集中人工 review，然后回到 G8 v0.4 UI/contract 修订、真实 Tree + Chat flow、Graph MVP。

### To Verify

- 用户确认 PRD v0.3 是否准确表达 Landing / Knowledge Base / Session Workspace 三层产品。
- 用户确认 MVP 是否只实现正式互动 Session Workspace。
- 用户抽查 [../TODO.md](../TODO.md) 的 Phase 0-5 结构是否顺手，尤其是 G3 证据和 G6 方案是否已经不再混乱。
- 用户确认是否先进入 Phase 4 / G6 实现，还是先做一次 G1/G2/G3/G5 人工核查。

### Next Up

- 推荐首选：G9 集中人工 review，核查 parser fusion metadata、visual candidate gate、retriever backend comparison、answer eval 和 `/api/session/handoff/{document_id}` payload。
- 第二步：回到 G8 v0.4 UI/contract 修订、真实 Tree + Chat flow、Graph MVP。
- 第三步：阶段确认后再本地 commit / 远端 push。
- 后续回到 G8：v0.4 UI/contract 修订、真实 Tree + Chat flow、Graph MVP。
