# Todo + Spec: QT Wiki NotebookLM 式 Session MVP

更新时间：2026-06-10
状态：Decisioned Draft
依据：[PRD-流程问答工作台.md](PRD-流程问答工作台.md)

## 1. 已确认产品边界

- 产品形态：类 NotebookLM，分为 Landing Page、Knowledge Base、Session Workspace。
- 本次 MVP：正式互动 Session Workspace。
- 左侧固定：Sources 资料库、文档目录树、Obsidian 式关联图切换。
- 中间核心：每次新开的 session chat，约占主要纵向与横向注意力。
- 右侧固定：当前 session 的 note / workflow studio。
- Source 选择：Selected Docs、Upload To Session、All Sources。
- Session 上传：自动解析，不做人审；显示 `parsed` / `failed` / `low confidence` 小状态标。
- 外部页：Landing Page、Knowledge Base 维护、历史 session、社区笔记进入后续；MVP 只保留入口占位。
- 技术路径：默认章节级 RAG；All Sources 强制 RAG + rerank；小范围文档/章节可 LLM 直接读局部上下文。
- 执行顺序优化：先稳定 Parser Workflow / Evals / Source Contract，再接 Retrieval API，最后接 NotebookLM Session UI，保证前端状态标和 Reference 有真实后端字段支撑。

## 2. 当前执行板

### Phase 0：规格重定版

- [x] 将 PRD 从 v0.2 ChatGPT 抽屉版升级为 v0.3 NotebookLM 式产品。
  - 证据：[PRD-流程问答工作台.md](PRD-流程问答工作台.md) 当前版本为 v0.3。

- [x] 明确本次 MVP 最小目标为正式互动 Session Workspace。
  - 证据：PRD `5. MVP 范围` 与本文件 `Phase 1`。

- [ ] 固化 Session Contract：session_id、title、source_scope、messages、note、publish_status。
- [ ] 固化 Source Contract：Knowledge Base source、session-only source、parse_status、BU、page_count、section/fragment stats。
- [ ] 固化 Source Scope Contract：selected_docs、all_sources、session_upload、selected_section。
- [ ] 固化 Note Contract：markdown、pinned_answer_ids、workflow_outputs、publish_status。
- [x] 完成 Multi-input Parser 与 RAG Workflow 研究。
  - 证据：[MultiInput-Parser-RAG-Workflow-设计.md](MultiInput-Parser-RAG-Workflow-设计.md) 记录 PDF/DOCX/XLSX/PPTX/Markdown 解析、章节化、Script/LLM/Evals 分工和不同 RAG 策略。

- [x] 完成 Parser Workflow + Evals 实施计划。
  - 证据：[Parser-Workflow-Evals-实施计划.md](Parser-Workflow-Evals-实施计划.md) 将 BUs_CER / LEFA_v6 的抓取完整性、真源返回、章节正确性质量门吸收到 QT Wiki parser/RAG 路线。

验收证据：contracts 写入 schema 或前端类型，并有最小 fixture。

### Phase 1：正式互动 Session MVP

- [ ] 左侧 Sources 固定栏。
  - 最小设计：展示 CT / MI / XP PEP，支持勾选、All Sources、Upload To Session。
  - 验收：用户能看到资料选择状态和解析状态小标。

- [ ] 左侧 Tree / Graph 切换。
  - 最小设计：Tree 展示 BU -> Document -> Chapter 占位结构；Graph 展示 Document / Stage / Role / Deliverable 点线图。
  - 验收：切换不影响当前 session。

- [ ] 中间 Session Chat。
  - 最小设计：New Session、session 列表、当前 session 独立消息、当前 source scope 展示。
  - 验收：新开 session 后中间 chat 清空，左侧资料库保持不变。

- [ ] 当前 session source scope。
  - 最小设计：Selected Docs / All Sources / session upload 三种模式写入当前 session。
  - 验收：提问请求能带上当前 scope，或前端至少明确展示 scope。

- [ ] Session 上传状态。
  - 最小设计：上传后显示 `parsed` 勾选状态或 `failed` 状态，不进入人工审核页。
  - 验收：上传成功后该文档进入当前 session source list。

- [ ] 右侧 Session Note。
  - 最小设计：当前 session 的固定 markdown 草稿、Pinned answers、Publish note 状态。
  - 验收：切换 session 后右侧 note 随 session 切换。

- [ ] Workflow Studio 入口。
  - 最小设计：HTML note、飞书 Markdown、Reference 表、Mermaid、BU diff 五个操作入口。
  - 验收：按钮进入占位状态或生成静态预览，不阻断 chat。

验收证据：`cd App/web; npm run build` 通过；localhost 显示 NotebookLM 式三栏 session workspace。

### Phase 2：RAG 与 LLM 路径接入

- [x] Gate 1 Parser Contract：统一 `.pdf/.docx/.xlsx/.pptx/.md` 的 parse workflow、structure_quality、eval_summary、trace 和 review_items。
  - 证据：`Tool/workflows/document_parse.py`、`/api/documents/{document_id}/parse-summary`、`/api/documents/{document_id}/sections`、`/agent/upload` Gate 1 字段；最终验证 `89 passed`。
- [x] Gate 2 Markdown Parser MVP：先用 Markdown heading + line anchors 打通 section tree、parse summary 和 eval summary。
  - 证据：`Tool/parsers/markdown_parser.py` 支持 `.md` heading、paragraph/list/code/table block 和 line anchors；最终验证 `89 passed`。
- [ ] Gate 1/2 人工核查：确认 `parse_status`、`warn/fail/na`、Markdown 章节树和 Reference 粒度是否符合产品体验。
- [ ] Gate 3 PDF/DOCX Chapterization：PDF 编号标题/页眉清理、DOCX heading style、PEP PDF smoke cases。
- [ ] Gate 4 XLSX Table-aware Structure：sheet/table/row/cell anchors 和表格引用。
- [x] Parser Quality Eval MVP：P0-01 / P0-02 / P3-01 / P1-01 / P1-02 / P1-03 / P2-01 / P2-02 / P2-03 / L1-01 已接入 workflow summary。
  - 证据：`Tool/evals/parser_quality.py` 检查抓取缺口、章节漂移、章节树错误、噪音标题、复杂表格/图片风险、LLM 输出缺证据；最终验证 `89 passed`。
- [ ] Retrieval / Answer Eval MVP：RAG 召回差、citation 不完整、unsupported claims、缺口说明错误。
- [ ] Semantic signals：抽取 stage、role、deliverable、BU、关键词，写入 chunk metadata。
- [ ] Section Index Tool：从 canonical documents 生成 section chunks，并保存本地 `sections.jsonl`。
- [ ] Session Retrieval Tool：按 source_scope 检索 Selected Docs / All Sources / session upload。
- [ ] Selected Docs 查询走章节级 RAG。
- [ ] All Sources 查询走全库 RAG + rerank。
- [ ] Selected Section 查询可走局部 LLM 直接读。
- [ ] Session upload 成功后参与当前 session RAG。
- [ ] 回答返回 source scope、evidence coverage、Reference。

验收证据：R2/PO 问答可基于 CT / MI / XP source scope 返回不同证据；All Sources 能提示命中文档范围。

人工核查点：Gate 1 口径、Gate 2 Markdown 引用粒度、Gate 3 PEP PDF 章节树、Gate 4 Excel 表格引用、Gate 6 Retrieval 策略、Gate 7 Answer Reference 完整性。

### Phase 3：外部页与知识库维护

- [ ] Landing Page：更新知识库、新建 session、历史 session、社区笔记入口。
- [ ] Knowledge Base 维护页：上传/替换 PEP，查看解析状态、章节树、关联图。
- [ ] 历史 Session：列出已保存 session 和 note。
- [ ] Community Notes：展示已 publish 笔记。

验收证据：外部入口可导航；不影响 Session MVP 主链路。

## 3. Later Backlog

- [ ] Publish note 到 GitHub Pages / 飞书 / 社区笔记。
- [ ] 图谱拖拽、过滤、关系编辑。
- [ ] Knowledge Base 人工校正队列。
- [ ] 多用户权限与 SharePoint/Blob 接入。

## 4. 关键 Contracts 草案

### 4.1 Session Contract

```json
{
  "session_id": "session-r2-po-001",
  "title": "R2 PO Readiness",
  "source_scope": {
    "mode": "selected_docs",
    "document_ids": ["ct-pep", "mi-pep", "xp-pep"],
    "session_upload_ids": []
  },
  "messages": [],
  "note": {
    "markdown": "",
    "pinned_answer_ids": [],
    "publish_status": "draft"
  }
}
```

### 4.2 Source Contract

```json
{
  "document_id": "ct-pep",
  "file_name": "CT PEP AND 308 11.pdf",
  "bu": "CT",
  "source_type": "knowledge_base",
  "parse_status": "parsed",
  "page_count": 55,
  "section_count": 0,
  "fragment_count": 0
}
```

### 4.3 Workflow Output Contract

```json
{
  "output_id": "output-html-note-001",
  "session_id": "session-r2-po-001",
  "output_type": "html_note",
  "status": "draft",
  "source_answer_ids": [],
  "content_ref": ""
}
```