# Project Memory: QT Wiki vNext

## Stable Product Direction

- vNext 主线是 NotebookLM 式 PEP 知识工作台：Landing / Knowledge Base / Session Workspace 三层产品。
- 本次 MVP 最小目标是正式互动 Session Workspace：左侧固定 Sources/Tree/Graph，中间 Session Chat，右侧 Session Note / Workflow Studio。
- Knowledge Base 是背景环境，维护 CT / MI / XP 等 PEP PDF、章节索引和关联图；每次新 session 复用或复制当前知识库快照作为 source scope。
- Session 是一次独立研究任务，拥有独立聊天记录、source scope、session-only uploads 和 note。
- 右侧 note 跟随当前 session，支持 pin answer、生成 HTML note、飞书 Markdown、Reference 表、Mermaid、BU diff，并保留 publish note 入口。
- 典型用户问题包括：“PEP 文档的流程如何操作？”、“现在在 R2 阶段，我作为 PO 应该做什么？”、“这条回答来自哪个文件哪个章节？”
- 回答必须基于本次上传、预置公司流程库、历史解析文档或用户问题上下文，并返回文件、章节/标题和 quote。
- Source 选择模式包括 Selected Docs、Upload To Session、All Sources；默认技术路径是章节级 RAG，All Sources 使用 RAG + rerank，小范围章节可走局部 LLM 直接读。
- `PEP/` 目录中 CT、MI、XP 三份 PEP PDF 可抽文本，适合作为首批知识库和 BU diff 样本。
- 解析底座按 Multi-input workflow 设计：现有 parser 已覆盖 PDF/DOCX/XLSX/PPTX，Markdown 需要新增；下一步优先做章节化、structure_quality、parser eval 和 section-first index。
- Evals 借鉴 BUs_CER / LEFA_v6 的最小质量门：抓取完整性、真源返回、章节正确性。后续实现按 Gate 推进，关键节点需要用户核查后再进入下一层。
- 2026-06-10 已实现 Gate 1 Parser Workflow Contract 和 Gate 2 Markdown parser MVP：canonical metadata 写入 `parse_workflow`、`structure_quality`、`eval_summary`、`review_items`，upload 和 parse-summary API 可返回这些字段。
- 2026-06-10 Evals 范围扩展为静态开发质量门 + 动态内容质量门。Parser Quality Eval MVP 已覆盖抓取缺口、章节漂移、章节树错误、噪音标题、复杂表格/图片风险、LLM 输出缺证据。
- 2026-06-10 已实现 Gate 3 PDF/DOCX Chapterization MVP：共享 heading detector 覆盖 R 阶段、中文章/条、数字编号、compact 编号、字母子标题和 DOCX Heading 样式；真实 CT / MI / XP PEP 自动 smoke 已补强 P2-03 文档控制/目录噪音和 P2-01 孤立深层章节检查，人工核查仍是下一步。
- 2026-06-10 已实现 Gate 4/5 Section Chunk + Retrieval Eval MVP：section chunks、source-scope retrieval、retrieval eval、chunks API 和 visual review queue 已进入代码；CT/MI/XP smoke 当前为 146 / 93 / 163 chunks，最近完整验证 `109 passed`。
- 2026-06-10 Gate 6 已收敛为下一阶段：先做 deterministic QuestionIntent、企业关键词归一和 AnswerEvidencePackage，再接 adaptive prompt builder、answer eval 和 Session Query API。
- 2026-06-10 已实现 Gate 6 Answer Foundation：`Tool/workflows/answer.py` 提供 deterministic QuestionIntent、企业关键词归一和 AnswerEvidencePackage；History/template change 与缺 source_refs hit 不作为 primary evidence。
- Design 目录当前采用“一主多附件”：计划、方案、TODO 都以 [../TODO.md](../TODO.md) Phase 0-5 为准；外部 Plan / Review / Notes 文档只作为证据附件或历史背景。
- GitHub Pages 作为静态前端、静态索引和导出产物托管目标；上传和 AI 解析先由本地 FastAPI、CLI/build script 或后续轻量服务生成 JSON/Markdown。

## Current Source Of Truth

- PRD: [../PRD-流程问答工作台.md](../PRD-流程问答工作台.md)
- Design master stage plan: [../TODO.md](../TODO.md)
- Todo + Spec: [../Todo+Spec-流程问答工作台.md](../Todo+Spec-流程问答工作台.md)
- 功能文档入口: [../../QT-Wiki-功能文档.md](../../QT-Wiki-功能文档.md)
- 根变更记录: [../../CHANGELOG.md](../../CHANGELOG.md)

## Architecture Boundaries

- 复用现有解析层：`Tool/parsers`, `Tool/pipelines`, canonical document / fragment / section 结构。
- Query 层需要逐步从 wiki-first 演进到 session-source-scope-first。
- 旧审批包和 Wiki 页面能力保留为背景和治理能力，不作为 vNext 用户主路径。
- 复杂审批不进入首版主体验；首版只显示低置信度提示，并保留可选人工校正入口。

## Review Rules

- 当前轻量开发框架采用 `repo-dev-harness`：TODO 用 checkbox-first，dev memory 只记录稳定事实，changelog 只记录已确认动作和验证证据。
- Design 阶段计划以 [../TODO.md](../TODO.md) 为唯一入口；新计划优先写回对应 Phase，长背景才新增附件。
- 修改文档后同步更新 [CHANGELOG.md](../../CHANGELOG.md)。
- 长线开发状态写入 [SESSION-WIP.md](SESSION-WIP.md)。
- 用户原始要求和待审任务写入 [TODO.md](TODO.md)。
- 旧设计稿优先归档到 [../old/](../old/)，审阅后再决定是否删除。
