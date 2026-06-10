# Session WIP

## 2026-06-10

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

### In Progress

- 当前主线是 Gate 1/2 人工核查，然后进入 Gate 3 PEP PDF/DOCX 章节化；NotebookLM Session UI 等 parser/retrieval API 字段稳定后接入。

### To Verify

- 用户确认 PRD v0.3 是否准确表达 Landing / Knowledge Base / Session Workspace 三层产品。
- 用户确认 MVP 是否只实现正式互动 Session Workspace。
- 用户确认是否按“主 Design 只留 PRD / Todo+Spec / dev-memory / README，其余进 old”的策略继续瘦身。

### Next Up

- 核查 Gate 1 Parser Contract + eval_summary 口径。
- 核查 Gate 2 Markdown parser + line anchors 的章节树和 Reference 粒度。
- 进入 Gate 3 PEP PDF/DOCX 章节化，并继续补 Retrieval / Answer Evals。
- NotebookLM Session UI 在 parser/retrieval API 口径稳定后接入。
