# Development Memory Changelog

## 2026-06-10

- 基于用户反馈将产品形态从 v0.2 ChatGPT 抽屉版升级为 v0.3 NotebookLM 式知识工作台：Landing / Knowledge Base / Session Workspace。
- 明确本次 MVP 最小目标为正式互动 Session Workspace：左 Sources/Tree/Graph，中 Session Chat，右 Session Note/Workflow Studio。
- 更新 PRD、Todo+Spec、dev-memory TODO 和 Session WIP，记录 Selected Docs / Upload To Session / All Sources、session 上传状态标、note publish 入口和 RAG/局部直读技术路径。
- 新增 [../MultiInput-Parser-RAG-Workflow-设计.md](../MultiInput-Parser-RAG-Workflow-设计.md)，将底层能力升级为多格式解析、章节化、Script/LLM/Evals 分工、Retrieval Strategy Matrix 和 Session RAG Workflow。
- 新增 [../Parser-Workflow-Evals-实施计划.md](../Parser-Workflow-Evals-实施计划.md)，吸收 BUs_CER / LEFA_v6 Evals 的抓取完整性、真源返回、章节正确性质量门，并定义 parser -> backend -> frontend 的 Gate 推进顺序。
- 实现 Gate 1 Parser Workflow Contract 与 Gate 2 Markdown parser MVP：canonical metadata、upload response、parse-summary/sections API 均可返回 workflow/eval/quality 字段；最终验证 `89 passed`。
- 实现 Parser Quality Eval MVP：新增 `Tool/evals/parser_quality.py`，将抓取缺口、章节漂移、章节树错误、噪音标题、复杂表格/图片风险和 LLM 输出缺证据接入 workflow summary；最终验证 `89 passed`。

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
