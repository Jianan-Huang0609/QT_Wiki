# Todo + Spec: QT Wiki NotebookLM 式 Session MVP

更新时间：2026-06-12
状态：Decisioned Draft；作为 Session MVP 详细规格使用
依据：[PRD-流程问答工作台.md](PRD-流程问答工作台.md)
上层执行入口：[TODO.md](TODO.md)

> 2026-06-17 同步说明：当前执行入口已收敛到 [TODO.md](TODO.md)、[Spec-Parser-RAG.md](Spec-Parser-RAG.md)、[Spec-Chat-Workflow.md](Spec-Chat-Workflow.md)、[Spec-UI-Workspace.md](Spec-UI-Workspace.md)。本文件保留 Session MVP 早期 contract 和 NotebookLM 产品判断。最新用户约束为：parser 采用 Notebook-like 自动解析，不要求每份文档先人审；Ask Workspace 左侧只展示文件级 source，不按章节展开；Chat 优先修 citation、intent、route、answer_run 和回答可信度。

## 1. 已确认产品边界

- 产品形态：类 NotebookLM，分为 Landing Page、Knowledge Base、Session Workspace。
- 本次 MVP：正式互动 Session Workspace。
- 左侧固定：Session Source Base，按当前 session 展示 Sources、真实文档 Tree、文档关系 Graph。
- 中间核心：每次新开的 session chat，采用 GPT / NotebookLM 式 transcript + 底部 composer。
- 右侧固定：当前 session 的 Note。Workflow Studio 后移到 Note 稳定之后。
- Source 选择：Selected Docs、Upload To Session、All Sources。
- Session 上传：自动解析，不做人审；显示 `parsed` / `failed` / `low confidence` 小状态标。
- 外部页：Landing Page、Knowledge Base 维护、历史 session、社区笔记进入后续；MVP 只保留入口占位。
- 技术路径：默认章节级 RAG；All Sources 强制 RAG + rerank；小范围文档/章节可 LLM 直接读局部上下文。
- 执行顺序优化：先稳定 Parser Workflow / Evals / Source Contract，再接 Retrieval API，最后接 NotebookLM Session UI，保证前端状态标、Tree、Graph 和 Reference 有真实后端字段支撑。
- v0.4 UI 打磨原则：左侧不用假 Tree/Graph；中间输入框固定在底部；右侧 MVP 只保留 Note；视觉风格参考 Jianan presentation 的公司汇报感和 Siemens Healthineers 风格。
- Tool 优先级调整：先执行 [Tool-Parser-RAG-Fusion-Spec.md](Tool-Parser-RAG-Fusion-Spec.md) 中的 QT Parser Core provider fusion、Docling provider、PDF fusion pipeline、OCR/visual provider 和 Hybrid RAG，再回到 v0.4 UI/contract、真实 Tree、Chat flow 和 Graph MVP。
- 2026-06-12 执行确认：带跳转链接的长总结和当前状态写入 [dev-memory/SESSION-WIP.md](dev-memory/SESSION-WIP.md)，[../CHANGELOG.md](../CHANGELOG.md) 只记录日期级决策与验证结果；下一步按 P0 顺序继续开发，先完成真实后端 Session Query，再拆 UI 用户操作逻辑。
- 2026-06-12 UI 重规划确认：四页目标框架固定为 `Source Intake -> Review Gate -> Ask Workspace -> Admin / JSON Lab`；当前实现优先选择 C 路线 vertical slice，先把 `Ask Workspace v1` 做成主路径，再把 Review Gate 和 Admin 从问答界面彻底拆走。
- NotebookLM 对标原则：Source 默认文件级，章节/片段只作为 drill-down；Chat 是研究与问答主界面，不展示 parser/debug 负担；Reference 必须是可读 source anchor card；Note 是记忆沉淀区；processing state 用用户能理解的 Answer Run 状态表达。
- Chatbox 六环融合原则：Ask Workspace 只保留一条统一 Chat 环路，不拆自由模式/技能模式；P0 的六环最小 contract 由 `/api/session/query` 返回 `answer_run-v0.1`，步骤为 `输入 -> 上下文装配 -> 推理规划 -> 执行 -> 生成 -> 记忆回写`。当前第 6 环先连接前端 Session Note pin-ready，后续再接持久化 session memory、tool registry 和 function calling。

## 2. 当前执行板

### P0：2026-06-12 继续开发切片

- [x] **P0-01 Session Query API 真实闭环** `Highest`
  - 用户认可的下一步：先让后端基于当前 selected PEP 真正回答，再继续拆 UI。
  - 最小设计：新增或完成 `/api/session/query`，请求包含 `question`、`source_scope.mode`、`source_scope.document_ids`、`use_llm`、`top_k`、`top_k_citations`；后端加载 selected docs 的 canonical sections/chunks，走 section retrieval + `AnswerEvidencePackage`，返回兼容现有 Chat 的 answer/citations/trace。
  - 当前状态：后端 endpoint、request schema、targeted API test 已通过；真实 CT/MI/XP TestClient smoke 已确认 citation document_id/file_name 跟随 selected docs；全量后端 `136 passed`。
  - 验收：选中 MI PEP 后问“PEP 文档的流程如何操作？”，citation 来自 MI document_id 或 MI file_name；切换 CT/XP 后 citation 随 source scope 切换；证据不足时明确提示缺 evidence。

- [x] **P0-02 Frontend Chat 接入 Session Query** `High`
  - 最小设计：前端新增 `querySession()`，`handleQuerySubmit` 在有当前 `sessionHandoff.chat.source_scope` 或 selected document 时调用 `/api/session/query`；旧 `/chat/query` 只作为 All Wiki fallback 并在 UI 中标注。
  - 当前状态：`App/web/src/api.ts` 已新增 `querySession()`；`App.tsx` 的 Chat submit 已优先走当前 PEP source scope；`structured_matches` 已兼容旧 review package summary 和新 `AnswerEvidencePackage`；`App/web npm run build` 通过。
  - 验收：Chat transcript、evidence panel 和 citation chips 显示当前 PEP source scope；切换 PEP 后不会沿用旧 handoff/evidence。浏览器 smoke 作为 P0-04 继续记录。

- [ ] **P0-03 UI 用户操作逻辑拆页** `High`
  - 目标框架：把当前混合工作台拆成 `Source Intake -> Review Gate -> Ask Workspace -> Admin / JSON Lab`。Review Gate 先处理 parse/review/quality，Ask Workspace 只处理问答、citation 和 Note。
  - 当前优先路线：用户确认先做 C 路线 vertical slice，即 `Ask Workspace v1`。该切片先解决最不满意的 Chat、Source、Reference 和 Note 主路径，再继续完整四页重构。
  - [x] **P0-03A Source 文件级收敛**：左侧默认只展示 CT / MI / XP 三份原始 PEP 文件名、selected 状态、parse 状态和 quality 摘要；Tree/section/chunk 从 Ask Workspace 主路径移出。
  - [x] **P0-03B Chat / Review 分离**：Ask Workspace 中间区只保留 Chat transcript、回答状态和底部 composer；Review Queue、Evidence/Trace 侧栏、Quality Gate、JSON inspector、Admin controls 从普通问答主路径迁出或折叠。
  - [x] **P0-03C Answer Run 六步状态**：每次提问形成可读 Answer Run：`输入 -> 上下文装配 -> 推理规划 -> 执行 -> 生成 -> 记忆回写`，前端显示后端返回的每步状态和简短说明；没有后端 `answer_run` 的旧路径保留前端 fallback。
  - [x] **P0-03D Reference Card**：引用从 `[c1]/[c2]` 改为可读 inline label 和右侧 Reference Card，展示文件名、页码/章节和 quote；后端推荐问题也改为文件名级 source label，避免 `0 History` 噪音。
  - [x] **P0-03E Note pin 最小闭环**：右侧保留 Session Note，可把当前回答或引用 pin 到 note；publish/export 后移。
  - 验收：普通用户在 Ask Workspace 首屏能看到当前选择了哪几份 PEP、问答正在执行到哪一步、答案依据了哪段原文；JSON/raw handoff 不进入主操作路径。当前 C 路线首版已通过 build、targeted API test、diff check 和 localhost browser smoke；完整四页拆分仍在 P0-03 后续。

- [x] **P0-04 Real PEP Smoke Evidence** `High`
  - 最小设计：用当前 CT / MI / XP 三份真实 PEP 各跑 handoff + session query + 浏览器 Chat smoke。
  - 当前状态：CT / MI / XP 均已完成 localhost browser smoke；点击或选择当前 PEP 后会请求对应 handoff，再由 Chat 调用 `/api/session/query`，evidence panel 显示当前 PEP citation 和 selected-doc trace。
  - 验收：记录三份 PEP 的 document_id、问题、citation 来源、trace 和结果状态；验证通过后同步 [TODO.md](TODO.md)、[dev-memory/SESSION-WIP.md](dev-memory/SESSION-WIP.md) 与 [../CHANGELOG.md](../CHANGELOG.md)。

- [x] **P0-05 Chat 六环后端最小框架 + 多轮提问修复** `Highest`
  - 用户核心问题：UI 端要能连续问新问题；后端要真正给出六环步骤，而不是只在前端模拟。
  - 最小设计：`ChatQueryResponse.answer_run` 返回 `schema_version/run_id/loop/steps`；每个 step 包含 `step_id`、`label`、`status`、`summary`、`inputs`、`outputs`。P0 只覆盖 selected-doc session RAG 主路径：input 接收文本；context 装配 source scope/canonicals/chunks；planning 输出 intent/strategy/retrieval question；execution 输出 retrieval/evidence/citation counts；generation 输出 composer/confidence；memory 输出 pin-ready 与 durable memory 状态。
  - 当前状态：后端 schema、session query 组装函数、API 回归测试和运行态 smoke 已完成；前端 `QueryResult` 接收 `answer_run`，Answer Run 优先显示后端 steps；Chat transcript 改为多轮追加；窄屏/VS Code 嵌入浏览器下 Chat 面板固定为视口高，composer 保持在面板底部，推荐问题横向滚动，提交按钮增加 pointer fallback。
  - 验收：连续提交两次问题都命中 `/api/session/query`，页面显示两轮 user/assistant 消息；Answer Run 六步来自后端 `answer-run-v0.1`；第 6 环显示 `deferred`，表达当前已支持 Pin 到 Session Note，持久化 session memory 后续接入。

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

- [ ] **G8-03 Session Source Base 重构**
  - 最小设计：左侧 Sources 按当前 session 展示，区分 Knowledge Base source、session-only upload、selected、excluded、parsed、failed、low confidence。
  - 验收：切换 session 或 source scope 后，Sources 列表、顶部 scope、query request 使用同一组 source ids；没有真实 source 时显示空状态。

- [ ] **G8-04 真实 Document Tree**
  - 最小设计：Tree 从 parse summary / sections / chunks 构建 BU -> Document -> Chapter -> Section，不再写死 R2 / PO / 7.16 等假节点。
  - 验收：Tree 节点带 document_id、section_id、anchor、页码或 fragment count；缺少真实章节数据时显示“等待解析 / 重建索引”状态。

- [ ] **G8-05 文档关系 Graph MVP**
  - 最小设计：Graph 使用真实关系数据：contains、mentions、requires、produces、responsible_for、differs_from、supports_citation；节点类型为 Document、Chapter、Stage、Role、Deliverable、Reference。
  - 验收：点击 Graph 节点或边能联动 Tree 节点、citation 或 source chip；无关系数据时展示关系表和构建状态，而不是装饰性点线图。

- [ ] **G8-06 Session Chat Transcript 重构**
  - 最小设计：中间区域改为上方 message transcript、底部 sticky composer；user / assistant 消息按时间追加；推荐问题从主区域移到底部 quick prompt 或空会话起始态。
  - 验收：完成一次提问后，回答显示在输入框上方；输入框仍固定底部；citation chips、copy、pin to note、show citations 可用或有明确占位。

- [ ] **G8-07 右侧 Note-only MVP**
  - 最小设计：右侧只展示当前 session note：markdown 草稿、Pinned answers、citation excerpts、publish/draft 状态。
  - 验收：右侧不再出现 Admin、Reference tab、Workflow tab；Reference 通过 Chat message 或 Note 引用摘录呈现。

- [ ] **G8-08 企业视觉系统打磨**
  - 最小设计：参考 Jianan presentation 的公司汇报感，采用深青绿主色、医疗蓝辅助、低饱和灰白背景、琥珀警示；控件更像流程工作台而不是通用 AI demo。
  - 验收：桌面首屏可截图汇报；信息密度稳定，按钮/标签/状态色语义一致，移动端无文字溢出或交互重叠。

- [ ] **G8-09 开源 NotebookLM 能力融合 spike**
  - 最小设计：基于 SurfSense、KnowNote、InsightsLM、Local-NotebookLM 整理可复用模式，不直接引入代码依赖。
  - 验收：形成 integration decision：本轮吸收 search space / cited answer / three-column note pattern；audio / connector / report generator / workflow automation 放入 Later。

验收证据：`cd App/web; npm run build` 通过；localhost 显示 NotebookLM 式三栏 session workspace；关 LLM 后真实 `/chat/query` smoke 通过；浏览器 console 无 error；桌面和窄屏截图无布局重叠。

### Phase 2：RAG 与 LLM 路径接入

本 Phase 的底层实施以 [Tool-Parser-RAG-Fusion-Spec.md](Tool-Parser-RAG-Fusion-Spec.md) 为详细计划：先完成 G9 QT Parser Core / Provider Fusion，再让 G8 UI 消费真实 Tree / Graph / Retrieval / AnswerEvidencePackage。

- [x] Gate 1 Parser Contract：统一 `.pdf/.docx/.xlsx/.pptx/.md` 的 parse workflow、structure_quality、eval_summary、trace 和 review_items。
  - 证据：`Tool/workflows/document_parse.py`、`/api/documents/{document_id}/parse-summary`、`/api/documents/{document_id}/sections`、`/agent/upload` Gate 1 字段；最终验证 `89 passed`。
- [x] Gate 2 Markdown Parser MVP：先用 Markdown heading + line anchors 打通 section tree、parse summary 和 eval summary。
  - 证据：`Tool/parsers/markdown_parser.py` 支持 `.md` heading、paragraph/list/code/table block 和 line anchors；最终验证 `89 passed`。
- [ ] Gate 1/2 人工核查：确认 `parse_status`、`warn/fail/na`、Markdown 章节树和 Reference 粒度是否符合产品体验。
- [x] Gate 3 PDF/DOCX Chapterization MVP：PDF 编号标题/R 阶段标题/页眉清理、DOCX heading style、compact 编号标题、字母子标题。
  - 证据：`Tool/parsers/structure.py`、`Tool/parsers/pdf_parser.py`、`Tool/parsers/docx_parser.py` 已接入共享 heading detector 和 `heading_path` anchors；最终验证 `92 passed`。
- [ ] Gate 3 PEP PDF smoke + 人工核查：自动 smoke 已跑 CT / MI / XP PEP，页眉和目录点线噪音已接入 P2-03 + PDF 清理，孤立深层章节已接入 P2-01 details；剩余章节树风险进入 `needs_review`，待人工核查 R2/R3 关键章节树和 Reference 粒度。
- [ ] Gate 4 XLSX Table-aware Structure：sheet/table/row/cell anchors 和表格引用。
- [x] Parser Quality Eval MVP：P0-01 / P0-02 / P3-01 / P1-01 / P1-02 / P1-03 / P2-01 / P2-02 / P2-03 / L1-01 已接入 workflow summary。
  - 证据：`Tool/evals/parser_quality.py` 检查抓取缺口、章节漂移、章节树错误、噪音标题、复杂表格/图片风险、LLM 输出缺证据；PEP smoke 噪音与孤立深层章节检查已补充；最终验证 `97 passed`。
- [x] Retrieval / Answer Eval MVP：已新增 fusion / retrieval / answer eval 扩展，覆盖 provider contribution、low-confidence fusion decisions、retrieval backend comparison、missing citation、unsupported claims 和 evidence gap 未提示风险；完整后端验证 `134 passed`。
- [x] Parser Fusion Core Contract：已定义 ExtractionBlock、LayoutBlock、TableBlock、VisualCandidate、FusionDecision 和 parser_fusion metadata；现有 parser workflow 自动写入默认 single-provider fusion trace，完整后端验证 `116 passed`。
- [x] Docling Provider Integration：已新增 lazy import + injectable converter 的内部 provider，输出 layout/table/OCR blocks 参与 fusion；真实 Docling 依赖暂未加入 requirements，后续单独确认安装体积、Windows 可用性和许可证。
- [x] PDF Fusion Pipeline：新增 `Tool/parsers/pdf_fusion.py`，把 pypdf fast text canonical fragments 与 Docling layout/table/OCR provider output 融成 `parser_fusion` metadata；先以可选 `parse_pdf_with_fusion()` 保持现有 `parse_pdf()` 主路径稳定，完整后端验证 `121 passed`。
- [x] DOCX Table/Layout Fusion：新增 `Tool/parsers/docx_fusion.py`，把 DOCX XML fragments/tables 与 Docling layout/table output 融成 `docx_provider_fusion` metadata；DOCX table anchors 已补 cell range / row count / column count，section table chunks 可引用 `tbl.1 R1C1:R2C2` 并输出 role/deliverable signals，完整后端验证 `123 passed`。
- [x] OCR / Multimodal Visual Provider：新增 `Tool/parsers/providers/visual_provider.py`，把 visual_review_items 和 Docling image blocks 转成可评审 `VisualCandidate` 队列；候选保留 source_refs、page/bbox/crop anchors、backend、confidence 和 review_status，primary gate 只放行 reviewed/accepted 或高置信且有 source anchors 的视觉证据，完整后端验证 `126 passed`。
- [x] Retriever Interface + Hybrid RAG：新增 `Tool/retrieval/retrievers.py`，把现有规则检索包装为 `RuleSectionRetriever` baseline，并提供 `FullTextRetriever`、可注入 embedding 的 `VectorRetriever`、RRF `HybridRetriever`；`evaluate_retrieval_cases()` 可比较不同 backend 的统一 `RetrievalResult`，完整后端验证 `131 passed`。
- [x] Fusion / Retrieval / Answer Eval 扩展：新增 `Tool/evals/fusion_eval.py`、`Tool/evals/answer_eval.py`，并扩展 `Tool/evals/retrieval_eval.py` 支持 backend comparison；当前可将 low-confidence fusion、retrieval backend miss、missing citation、unsupported claims 和缺 evidence 未提示写入 findings，完整后端验证 `134 passed`。
- [x] Session API Handoff：新增 `/api/session/handoff/{document_id}`，一次返回 source summary、真实 section tree、chunk/signal graph seeds、retrieval preview、chat source_scope/request/answer contract 和 quality gates；G8 UI 可基于该 contract 接入真实 Tool 输出，完整后端验证 `135 passed`。
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
    "session_upload_ids": [],
    "section_ids": []
  },
  "messages": [],
  "note": {
    "markdown": "",
    "pinned_answer_ids": [],
    "pinned_citation_ids": [],
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
  "scope_state": "selected",
  "page_count": 55,
  "section_count": 128,
  "fragment_count": 146,
  "last_indexed_at": "2026-06-11T00:00:00Z"
}
```

### 4.3 Tree Node Contract

Tree 节点只从真实 parser / section index 生成。

```json
{
  "node_id": "section-ct-r2-001",
  "node_type": "section",
  "document_id": "ct-pep",
  "parent_id": "chapter-ct-r2",
  "title": "R2 Responsibilities",
  "heading_path": ["5 Process", "5.3 R2 Responsibilities"],
  "anchor_label": "5.3",
  "page_start": 18,
  "fragment_count": 7,
  "parse_status": "parsed"
}
```

### 4.4 Graph Relation Contract

Graph 关系只从真实文档信号、结构化抽取或 answer evidence 生成。

```json
{
  "relation_id": "rel-r2-po-qmp",
  "relation_type": "responsible_for",
  "from": {
    "node_id": "role-product-owner",
    "node_type": "role",
    "label": "Product Owner"
  },
  "to": {
    "node_id": "deliverable-qmp",
    "node_type": "deliverable",
    "label": "QMP"
  },
  "source_refs": [
    {
      "document_id": "ct-pep",
      "section_id": "section-ct-r2-001",
      "anchor_label": "5.3"
    }
  ],
  "confidence": 0.82
}
```

### 4.5 Chat Message Contract

```json
{
  "message_id": "msg-001",
  "session_id": "session-r2-po-001",
  "role": "assistant",
  "content": "R2 阶段 PO 需要...",
  "citations": [],
  "intent": "role_action_guidance",
  "created_at": "2026-06-11T00:00:00Z",
  "actions": {
    "can_pin_to_note": true,
    "can_show_citations": true,
    "can_regenerate": true
  }
}
```

### 4.6 Note Contract

```json
{
  "note_id": "note-session-r2-po-001",
  "session_id": "session-r2-po-001",
  "markdown": "# R2 PO Readiness\n",
  "pinned_answer_ids": ["msg-001"],
  "pinned_citation_ids": ["c1", "c2"],
  "publish_status": "draft",
  "updated_at": "2026-06-11T00:00:00Z"
}
```

### 4.7 Future Workflow Output Contract

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

## 5. 开源 NotebookLM 类能力调研结论

调研方式：用 GitHub Search 搜索 `notebooklm open source`、`local notebooklm`、`document chat notebooklm`，并阅读代表项目 README。

| 项目 | 价值 | 当前取舍 |
| --- | --- | --- |
| SurfSense | Search space、hybrid search、cited answers、connectors、report/podcast/presentation outputs、多人协作 | 吸收 search space / cited answer / output studio 信息架构；connectors、协作、自动化后置。 |
| KnowNote | Electron 本地三栏 Knowledge Library / AI Q&A / Note Output，SQLite + sqlite-vec，mind map | 吸收三栏职责边界和 Note Output；GPL 代码只作设计参考。 |
| InsightsLM | React + self-hosted RAG，verifiable citations，Supabase + n8n workflows，podcast generation | 吸收 citation-first 和 workflow webhook 思路；当前继续使用 FastAPI + workflow-first 架构。 |
| Local-NotebookLM | PDF -> transcript/audio，多语言、多 provider，FastAPI/Gradio | audio overview、executive brief、Q&A script 放入 Later。 |
| NotebookLlama | LlamaCloud-backed extraction / index pipeline，Streamlit app，MCP server | 可参考 extraction/index setup 思路；当前避免引入 LlamaCloud 依赖。 |

本轮融合原则：先把 Session Source Base、真实 Tree/Graph、Chat transcript 和 Note 做扎实，再吸收输出型能力。当前不新增重依赖，不引入 license 风险较高的代码。