# QT Wiki vNext TODO

更新时间：2026-06-10
状态：Active
Harness：`repo-dev-harness`

## 1. 当前决策快照

- 产品主线：NotebookLM 式 PEP 知识工作台，分为 Landing / Knowledge Base / Session Workspace。
- 本次 MVP：正式互动 Session Workspace。
- 左侧：固定 Sources、文档目录树、Obsidian 式关联图切换。
- 中间：每次新开的 session chat，session 独立保存历史和 source scope。
- 右侧：当前 session 的固定 note / workflow studio。
- 答案：自然语言长答案 + 文件/章节/quote Reference。
- Source 选择：Selected Docs、Upload To Session、All Sources。
- Session 上传：自动解析并显示状态小标，暂不进入人工审核。
- Workflow：HTML note、飞书 Markdown、Reference 表、Mermaid、BU diff、Publish note。
- 旧框架：隐藏为后台能力，代码先保留。
- Design 计划入口：[../TODO.md](../TODO.md) 是唯一阶段计划入口，计划、方案、TODO 都按 Phase 展开；外部 Plan / Review / Notes 只作为附件。

## 2. Now

- [x] 完成 grill-me 范围澄清。
  - 证据：MVP、文档范围、答案形态、Reference、UI、LLM、BU diff 边界已确认。

- [x] 更新 PRD 为已决策版。
  - 证据：[../PRD-流程问答工作台.md](../PRD-流程问答工作台.md) 状态更新为 Decisioned Draft。

- [x] 重写 Todo+Spec 为清晰执行板。
  - 证据：[../Todo+Spec-流程问答工作台.md](../Todo+Spec-流程问答工作台.md) 第一屏能看到 Phase 0/1/2/3 待办。

- [x] 同步 Design 入口和开发记忆。
  - 证据：[../TODO.md](../TODO.md) 成为唯一阶段计划入口，计划/方案/TODO 按 Phase 0-5 展开；[../README.md](../README.md) 改为附件导航；[PROJECT-MEMORY.md](PROJECT-MEMORY.md)、[SESSION-WIP.md](SESSION-WIP.md)、[CHANGELOG.md](CHANGELOG.md) 与当前决策一致。

- [x] 更新 PRD 为 NotebookLM 式 v0.3。
  - 证据：[../PRD-流程问答工作台.md](../PRD-流程问答工作台.md) 当前版本为 v0.3，MVP 明确为正式互动 Session。

- [x] 完成 Multi-input Parser 与 RAG Workflow 研究。
  - 证据：[../MultiInput-Parser-RAG-Workflow-设计.md](../MultiInput-Parser-RAG-Workflow-设计.md) 记录多格式解析、章节化、Script/LLM/Evals 分工和不同 RAG 策略。

- [x] 完成 Parser Workflow + Evals 实施计划。
  - 证据：[../Parser-Workflow-Evals-实施计划.md](../Parser-Workflow-Evals-实施计划.md) 吸收 BUs_CER / LEFA_v6 的抓取完整性、真源返回、章节正确性质量门，并定义人工核查 Gate。

## 3. Next Implementation

- [x] 类 ChatGPT 主 Chat UI 第一版：旧右侧 ChatbotPanel 改为主屏，文档/引用/导出改抽屉。
  - 证据：`npm run build` 通过；localhost 显示 `process-chat-app`、主 Chat、上下文/引用/输出/后台抽屉。
- [ ] NotebookLM 式正式互动 Session UI：左 Sources/Tree/Graph，中 Session Chat，右 Session Note/Workflow Studio。
- [ ] Session Contract：session、source_scope、messages、note、publish_status。
- [ ] Source Scope：Selected Docs / Upload To Session / All Sources。
- [ ] Session upload 状态标：parsed / failed / low confidence。
- [ ] Workflow Studio 占位：HTML note、飞书 Markdown、Reference 表、Mermaid、BU diff、Publish note。
- [ ] RAG/LLM 路径：Selected Docs 和 All Sources 走 RAG，小范围章节走局部 LLM 直接读。
- [ ] Multi-input Parser 增强：PDF/DOCX/XLSX/PPTX/Markdown 章节化、页眉页脚/结构清理、Markdown parser。
- [x] Parser Quality Evals：解析稳定性、抓取缺口、章节漂移、章节树错误、复杂表格/图片风险、LLM 输出缺证据。
  - 证据：`Tool/evals/parser_quality.py` 接入 workflow summary，PEP 文档控制页眉/目录点线噪音和孤立深层章节已进入 P2-03/P2-01；最终验证 `97 passed`。
- [x] Retrieval Evals：RAG 召回质量、source scope、History/template change 降权。
  - 证据：`Tool/evals/retrieval_eval.py`、`Tool/retrieval/section_index.py`；CT / MI / XP smoke 两条 retrieval cases `recall_at_k=1.0`；最终验证 `109 passed`。
- [ ] Answer Evals：citation 完整性、回答 groundedness、缺口说明、自适应格式、企业关键词归一。
- [x] Section Index / Retrieval Tool：生成 section chunks，并按 session source scope 检索。
  - 证据：`Tool/chunking/section_chunks.py`、`/api/documents/{document_id}/chunks`、`retrieve_sections()` 支持 all_sources / selected_docs / selected_sections；最终验证 `109 passed`。
- [x] Gate 1：Parser Contract + eval_summary 口径，用户核查后进入 Markdown parser。
  - 证据：`Tool/workflows/document_parse.py`、`/api/documents/{document_id}/parse-summary`、`/api/documents/{document_id}/sections`、`/agent/upload` 扩展字段；最终验证 `89 passed`。
- [x] Gate 2：Markdown parser + line anchors，用户核查章节树和 Reference 粒度。
  - 证据：`Tool/parsers/markdown_parser.py` 已支持 `.md` heading、paragraph/list/code/table block 和 line anchors；最终验证 `89 passed`。
- [ ] Gate 1/2 人工核查：确认 parse_status、eval_summary、review_items 和 Markdown Reference 粒度。
- [x] Gate 3 PDF/DOCX Chapterization MVP：共享 heading detector 覆盖 DOCX Heading 样式、compact 编号标题、字母子标题、PDF R 阶段标题和重复页眉清理。
  - 证据：`Tool/parsers/structure.py`、`Tool/parsers/pdf_parser.py`、`Tool/parsers/docx_parser.py`；最终验证 `92 passed`。
- [ ] Gate 3 PEP PDF smoke + 人工核查：自动 smoke 已跑 CT / MI / XP PEP，页眉和目录点线噪音已接入 P2-03 + PDF 清理，剩余章节树风险进入 `needs_review`；用户核查 R2/R3 关键章节树和 Reference 粒度。
  - 最新进展：CT 反馈驱动的 Content/TOC、History table、figure caption、标题续行修复已完成；三份 PEP 均生成 History table 和 figure caption candidate，rootless child sections 清零。
  - 待核查：P2-01 level jump、4.3.x / 5.3.x parent 错层、R2/PO evidence 是否命中正文流程。
- [x] Gate 4/5 Section Chunk + Retrieval Eval MVP：section chunks、source refs、retrieval strategy trace、retrieval eval cases。
  - 证据：CT 146 chunks / MI 93 chunks / XP 163 chunks；CT 7.16 selected-docs 检索排第一；R2 查询回到 R2 正文/裁剪规则；最终验证 `109 passed`。
- [ ] Gate 6 Adaptive Answer Workflow：自适应主 Chat 回答，先解析 question intent 和企业关键词，再把 retrieval hits 转成 AnswerEvidencePackage，固定 citation、abstention 和非模板化输出 contract。
  - 执行入口：[../TODO.md](../TODO.md) Phase 4；历史方案附件：[../Gate6-Adaptive-Answer-Workflow-Plan.md](../Gate6-Adaptive-Answer-Workflow-Plan.md)。
  - 最新进展：G6-01/02/03 已完成，`Tool/workflows/answer.py` 固化 `QuestionIntent`、企业关键词归一和 `AnswerEvidencePackage`；验证 `compileall`、`pytest`、`git diff --check`、diagnostics 通过，当前 `114 passed`。
- [ ] Gate 7 Visual OCR / Multimodal pipeline：基于 `visual_review_items` 做 crop、OCR 或 multimodal 候选，并进入人工 review。

## 4. Done

- [x] 建立 vNext PRD 和 Todo+Spec 初稿。
- [x] 建立 `Design/dev-memory/` 和根目录 [../../MEMORY.md](../../MEMORY.md)。
- [x] 将旧 upload-approval 和 regulation-navigator 框架归档到 [../old/](../old/)。
- [x] 采用 `repo-dev-harness` 轻量开发记忆方式。
- [x] 确认 QT-CER-Tool `BUs_CER` 分支可作为 parser/extractor adapter 参考。
- [x] 完成一次 localhost 快速原型验证：后端测试、前端 build、推荐问题点击路径可用。
- [x] 完成一版 v0.2 UI 原型：顶部上下文 + 模型选择，中间主 Chat，右侧抽屉承载 Context/Reference/Outputs/Admin。
- [x] 确认 PEP 目录包含 CT / MI / XP 三份可抽文本 PDF，适合章节级 RAG 与 BU diff。
- [x] 确认现有 parser 已覆盖 PDF/DOCX/XLSX/PPTX 基础抽取，Markdown 仍需新增；章节化和 eval 是下一步底座。
- [x] 确认 parser/RAG 实施顺序：先 Markdown 打通 contract/workflow/eval/API，再逐步接入 PDF/DOCX/XLSX 和 Retrieval。
- [x] 完成 Gate 1 Parser Workflow Contract 与 Markdown parser MVP。
- [x] 完成 Parser Quality Eval MVP，动态捕捉章节漂移、抓取缺口、章节树错误、复杂表格/图片风险和 LLM 输出缺证据。
- [x] 完成 Gate 3 PEP smoke 检查机制补强：文档控制页眉、目录点线噪音和孤立深层章节进入 workflow eval/review items。
- [x] 完成 CT 反馈驱动的 PDF parser 修复，并新增 [../Pro-Input-Praser.md](../Pro-Input-Praser.md) 经验文档。
- [x] 完成 Section Chunk / Retrieval Eval / Visual Review Queue MVP。
- [x] 整理 Design 目录上层入口和阶段计划。
  - 证据：[../TODO.md](../TODO.md) 成为 Design 唯一阶段计划入口；[../README.md](../README.md) 改为附件导航；[../Todo+Spec-流程问答工作台.md](../Todo+Spec-流程问答工作台.md) 标注为 Session MVP 详细规格。

## 5. Later

- [ ] Feishu CLI adapter。
- [ ] Teachany 类训练交互。
- [ ] Slides/PPT outline。
- [ ] 多用户权限与 SharePoint/Blob 接入。
- [ ] 用户审阅后删除不再需要的 old 框架文档。