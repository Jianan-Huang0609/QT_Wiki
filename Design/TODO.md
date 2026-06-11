\# QT Wiki Design Master TODO

更新时间：2026-06-11  
状态：Active，Design 目录唯一阶段计划入口  
使用方式：计划、方案、TODO 都在本文件按阶段展开；外部文档只作为产品定义、证据或参考附件。

## 0. 操作规则

Design 目录按“一主多附件”使用，减少 Plan / Review / Spec 混在一起的问题：

1. **本文件是唯一执行入口**  
  计划、方案、阶段任务、下一步都写在 [TODO.md](TODO.md)。如果某个 Gate 需要展开，也先在本文件对应 Phase 下面展开。

2. **外部文档只做附件**  
  PRD / Spec 负责产品定义；Review 负责证据；Notes 负责经验；旧 Plan 文档只作为详细背景，不再作为执行入口。

3. **每个阶段固定五件事**  
  `目标`、`最小方案`、`TODO`、`验收证据`、`参考附件`。这样 G3、G6、Parser 都落到同一个结构里。

4. **完成任务后回填本文件**  
  任务完成时先更新对应 Phase 的 checkbox 和证据，再同步 dev-memory/changelog。附件只有在证据或背景变化时才更新。

## 1. 当前主线

- 产品方向：NotebookLM 式 PEP 知识工作台。
- MVP：正式互动 Session Workspace。
- 技术骨架：Parser Workflow -> Section Chunk -> Retrieval -> Adaptive Answer -> Session UI。
- 回答原则：主 Chat 采用自适应模式；核心事实带 reference，输出样式按 question intent 变化。
- 当前开发焦点：**Phase 3.5 / G9 QT Parser Core 已完成 G9-01 至 G9-08**；下一步进入集中人工 review，然后回到 Phase 5 / G8 v0.4 UI/contract、真实 Tree + Chat flow 和 Graph MVP。

## 2. 阶段计划

### Phase 0: Product / Session Contract

- 目标：固定 NotebookLM 式 PEP Knowledge Workspace 的产品边界和 MVP Session Workspace。
- 最小方案：先固化 `Session`、`Source Scope`、`Session Note`、`Workflow Studio` 的 contract，再让 UI/API 对齐。
- 验收证据：[PRD-流程问答工作台.md](PRD-流程问答工作台.md)、[Todo+Spec-流程问答工作台.md](Todo+Spec-流程问答工作台.md)。
- 参考附件：PRD、Session MVP Spec。

- [ ] **G0-01 固化 Session / Source / Note contract**
  - 下一步：把当前 PRD/Spec 中的字段收敛成 schema 或前端类型。
  - 验收：前端、API、RAG scope 使用同一组 contract 名称。

### Phase 1: Parser Contract / Markdown MVP

- 目标：所有 parser 输出统一进入 canonical schema、parse workflow summary 和 eval summary。
- 最小方案：Markdown / Parser workflow 先跑通；parse summary 能暴露 status、quality、review items。
- 验收证据：G1/G2 已实现，验证 `89 passed`。
- 参考附件：[Parser-Workflow-Evals-实施计划.md](Parser-Workflow-Evals-实施计划.md) 作为历史详细背景。

- [x] **G1 Parser Workflow Contract**
  - 证据：`parse_workflow`、`structure_quality`、`eval_summary`、`review_items` 已进入 API；验证 `89 passed`。

- [x] **G2 Markdown Parser MVP**
  - 证据：Markdown heading / block / line anchors 可返回；验证 `89 passed`。

- [ ] **G1/G2 人工口径核查**
  - 下一步：核查 `parse_status`、`warn/fail/na`、Markdown Reference 粒度是否符合产品体验。

### Phase 2: PEP PDF / DOCX Chapterization

- 目标：CT / MI / XP PEP 能形成可问答的章节树、History table、figure candidates 和 source anchors。
- 最小方案：PDF/DOCX 先做到 text-layer 结构化；OCR/multimodal 进入候选队列。
- 验收证据：G3 code done，CT/MI/XP smoke；验证 `109 passed`。
- 参考附件：[Gate3-PEP-PDF-Review.md](Gate3-PEP-PDF-Review.md)、[Pro-Input-Praser.md](Pro-Input-Praser.md)。

- [x] **G3 PDF/DOCX Chapterization MVP**
  - 证据：History/TOC/figure/7.16 修复已完成；验证 `109 passed`。

- [ ] **G3 PEP PDF 人工核查**
  - 下一步：核查 CT/MI/XP 的 R2/R3、7.16、History table、figure captions、P2-01 level jump。

### Phase 3: Section Chunk / Retrieval / Visual Queue

- 目标：让章节、表格、图像候选都能进入可检索证据层，并保留 source scope。
- 最小方案：section chunks + deterministic retrieval + retrieval eval 先服务 G6 AnswerEvidencePackage。
- 验收证据：G5 done，CT 146 chunks / MI 93 / XP 163，CT 7.16 检索排第一；验证 `109 passed`。
- 参考附件：[Parser-Workflow-Evals-实施计划.md](Parser-Workflow-Evals-实施计划.md)、[MultiInput-Parser-RAG-Workflow-设计.md](MultiInput-Parser-RAG-Workflow-设计.md)。

- [ ] **G4 Excel table-aware retrieval** `Later`
  - 下一步：设计 sheet/table/row/cell anchors 和 table retrieval cases。

- [x] **G5 Section Chunk + Retrieval Eval MVP**
  - 证据：source-scope retrieval、retrieval eval、chunks API、visual review queue 已完成；验证 `109 passed`。

- [ ] **G5 Retrieval 人工核查**
  - 下一步：核查 R2/PO、7.16、BU scope 的 top hits 是否符合业务直觉。

- [ ] **G7 Visual OCR / Multimodal Pipeline**
  - 下一步：基于 `visual_review_items` 做 crop / OCR / multimodal candidate pipeline。
  - 验收：OCR/multimodal 结果只作为 candidate，必须带 source image/crop 和 review status。

### Phase 3.5: QT Parser Core / Provider Fusion / Hybrid RAG

- 目标：把 pypdf、DOCX XML、Docling、OCR/VLM 和 Hybrid RAG 纳入同一个 QT Parser Core，先补底层 extraction / fusion / retrieval contract，再继续 UI v0.4。
- 最小方案：外部能力以内部 Python provider 进入 Tool core；provider 输出 extraction blocks，fusion layer 合并强项，PEP structure resolver 产出 `CanonicalDocument`，eval gate 约束 parser / retrieval / answer。
- 验收证据：当前为 planning phase，详细规格见 [Tool-Parser-RAG-Fusion-Spec.md](Tool-Parser-RAG-Fusion-Spec.md)。
- 参考附件：[Tool-Parser-RAG-Fusion-Spec.md](Tool-Parser-RAG-Fusion-Spec.md)、[MultiInput-Parser-RAG-Workflow-设计.md](MultiInput-Parser-RAG-Workflow-设计.md)、[Pro-Input-Praser.md](Pro-Input-Praser.md)。

- [x] **G9-01 Parser Fusion Core Contract**
  - 最小方案：定义 `ExtractionBlock`、`LayoutBlock`、`TableBlock`、`VisualCandidate`、`FusionDecision` 和 parser_fusion metadata。
  - 证据：新增 `Tool/parsers/fusion.py` 和 `tests/test_parser_fusion_contract.py`；`apply_parse_workflow_contract()` 已为现有 parser 写入默认 `parser_fusion` metadata，canonical top-level contract 保持稳定；窄验证 `32 passed`，完整后端验证 `116 passed`。

- [x] **G9-02 Docling Provider Integration**
  - 最小方案：把 Docling 作为内部 Python extraction provider 接入，输出 layout/table/OCR blocks 参与 fusion。
  - 证据：新增 `Tool/parsers/providers/docling_provider.py` 和 `tests/test_docling_provider.py`；provider 使用 lazy import + 可注入 converter，能把 Docling-like text/layout/table/picture 信息映射为 `ExtractionBlock`、`LayoutBlock`、`TableBlock`、`VisualCandidate`，并生成 `docling_provider_extraction` metadata；真实 Docling 依赖暂未加入 requirements，按 Spec 需单独确认安装体积、Windows 可用性和许可证；完整后端验证 `119 passed`。

- [x] **G9-03 PDF Fusion Pipeline**
  - 最小方案：把 pypdf fast text、Docling layout/table/OCR、现有 PEP cleanup 和 structure resolver 融成一个 PDF parser。
  - 证据：新增 `Tool/parsers/pdf_fusion.py` 和 `tests/test_pdf_fusion_pipeline.py`；`build_pdf_fusion_metadata()` 可把 pypdf canonical fragments 与 Docling layout/text/table/visual output 融合为 `parser_fusion` metadata，`FusionDecision` 记录 page/text 对齐、bbox/reading_order anchor 增强和 table/visual candidate 贡献；`parse_pdf_with_fusion()` 作为可选入口保留现有 `parse_pdf()` 主路径稳定；完整后端验证 `121 passed`。

- [x] **G9-04 DOCX Table/Layout Fusion**
  - 最小方案：融合 DOCX XML 顺序与 Docling table/layout 信息，补 table/cell anchors、list level metadata、role/deliverable signals。
  - 证据：新增 `Tool/parsers/docx_fusion.py` 和 `tests/test_docx_fusion_pipeline.py`；`build_docx_fusion_metadata()` 可把 DOCX XML fragments/tables 与 Docling layout/text/table output 融合为 `docx_provider_fusion` metadata，DOCX table anchors 已补 `cell_range`、`row_count`、`column_count` 并进入 source anchors；section chunk table refs 支持 `tbl.1 R1C1:R2C2`，table chunks 可输出 `role_table` / `deliverable_table` signals；完整后端验证 `123 passed`。

- [x] **G9-05 OCR / Multimodal Visual Provider**
  - 最小方案：把 visual_review_items 和 Docling image blocks 转成 page/crop -> OCR/VLM -> VisualCandidate -> eval/review 的队列。
  - 证据：新增 `Tool/parsers/providers/visual_provider.py` 和 `tests/test_visual_provider.py`；`build_visual_candidate_queue()` 可把 `visual_review_items` 经注入式 OCR/VLM extractor 转成 `VisualCandidate`，也可并入 Docling image candidates；候选保留 page/bbox/crop anchors、backend、confidence、review_status 和 source_refs，`primary_visual_candidates()` 只放行 reviewed/accepted 或高置信且有 source anchors 的候选；真实 OCR/VLM 依赖暂未加入 requirements；完整后端验证 `126 passed`。

- [x] **G9-06 Retriever Interface + Hybrid RAG**
  - 最小方案：定义统一 retriever interface，把现有 `retrieve_sections()` 包成 RuleSectionRetriever baseline，再做 full-text、vector、hybrid fusion / deterministic rerank。
  - 证据：新增 `Tool/retrieval/retrievers.py` 和 `tests/test_retriever_interface.py`；`RuleSectionRetriever` 保留现有 `retrieve_sections()` / `RetrievalResult` contract，`FullTextRetriever` 提供无依赖关键词 overlap baseline，`VectorRetriever` 支持注入 embedding 函数并提供 sparse fallback，`HybridRetriever` 用 deterministic RRF 融合多 backend；`evaluate_retrieval_cases()` 已可接收 pluggable retriever；完整后端验证 `131 passed`。

- [x] **G9-07 Fusion / Retrieval / Answer Eval 扩展**
  - 最小方案：新增 provider contribution eval、fusion decision eval、retrieval backend comparison eval、answer groundedness/citation completeness eval。
  - 证据：新增 `Tool/evals/fusion_eval.py`、`Tool/evals/answer_eval.py` 和 `tests/test_g9_eval_extensions.py`；`evaluate_parser_fusion_metadata()` 可报告 provider contribution 与 low-confidence fusion decision，`compare_retrieval_backends()` 可对多个 pluggable retriever 跑同一组 cases 并选择 best backend，`evaluate_answer_grounding()` 可标记 missing citation、unsupported claims 和 evidence gap 未提示风险；完整后端验证 `134 passed`。

- [x] **G9-08 Session API Handoff**
  - 最小方案：把真实 Tree、Graph、Chat flow 所需 contract 从 Tool 层交给 G8 UI。
  - 证据：新增 `/api/session/handoff/{document_id}` 和 API contract test；handoff payload 输出 `session-handoff-v0.1`，包含 source summary、真实 section tree、chunk/signal graph seeds、retrieval preview、chat source_scope/request/answer contract 和 quality gates，数据来自 canonical sections/chunks/parse_workflow；完整后端验证 `135 passed`。

### Phase 4: Adaptive Answer Workflow

- 目标：主 Chat 回答基于公司流程证据，自适应输出解释、行动建议、Reference 和缺口提示。
- 最小方案：先做 deterministic `QuestionIntent`、企业关键词归一和 `AnswerEvidencePackage`，再接 prompt / LLM。
- 验收证据：当前为 next implementation phase；完成后需要 answer eval 和人工核查。
- 参考附件：[Gate6-Adaptive-Answer-Workflow-Plan.md](Gate6-Adaptive-Answer-Workflow-Plan.md) 作为历史详细背景，执行内容以本 Phase 为准。

- [x] **G6-01 QuestionIntent 规则解析 MVP**
  - 最小方案：识别 `role_action_guidance / process_explanation / reference_lookup / bu_comparison / definition_lookup / gap_check`。
  - 证据：`Tool/workflows/answer.py` 已实现 `parse_question_intent()`；`R2阶段我作为PO应该做什么` -> `role_action_guidance`，`PO` -> `Product Owner`，reference density 为 high；验证 `114 passed`。

- [x] **G6-02 企业关键词归一 MVP**
  - 最小方案：规则词典 + chunk signals 归一 R 阶段、M milestone、角色、交付物、BU、章节号。
  - 证据：`normalize_enterprise_terms()` 已覆盖 `PO / Product Owner`、`R2/R3`、`M150`、`QMP`、`7.16`、`CT`，并可合并 chunk signals；验证 `114 passed`。

- [x] **G6-03 AnswerEvidencePackage MVP**
  - 最小方案：把 `RetrievalResult` 转成可回答证据包，每条 evidence 都有 document / section / anchor / quote。
  - 证据：`build_answer_evidence_package()` 已把 retrieval hits 转为带 document / section / anchor / quote / supports 的 evidence items；History/template change 和缺 source_refs hit 不作为 primary evidence，证据不足写入 `missing_evidence`；验证 `114 passed`。

- [ ] **G6-04 Adaptive Prompt Builder**
  - 最小方案：prompt 只消费 `intent + enterprise keywords + evidence package + style policy`。
  - 验收：核心事实有 citation；短问题短答，复杂问题才展开；输出不过度模板化。

- [ ] **G6-05 Answer Evals MVP**
  - 最小方案：检查 groundedness、citation completeness、abstention correctness、adaptive format、keyword normalization。
  - 验收：unsupported claim / missing citation 能进入 eval findings。

- [ ] **G6 Answer 人工核查**
  - 下一步：核查自适应格式是否自然；reference 是否足够支撑公司流程依据。

### Phase 5: NotebookLM Session UI / API

- 目标：把 parser / retrieval / answer package 接到正式互动 Session Workspace。
- 最小方案：等待 G9 Tool Fusion 提供真实 source/tree/graph/evidence contract 后，再做 Session Source Base、真实 Tree/Graph、GPT/NotebookLM 式 Chat transcript 和右侧 Note-only。
- 验收证据：v0.2 主 Chat 原型已验证；v0.3 三栏 Session Workspace skeleton 已本地构建并通过 localhost `/chat/query` smoke；v0.4 PRD/Spec 已记录反馈修订方向。
- 参考附件：[Todo+Spec-流程问答工作台.md](Todo+Spec-流程问答工作台.md)。

- [ ] **G8-01 Session Query API**
  - 下一步：输入 question + source scope，返回 answer package + citations + retrieval trace。

- [x] **G8-02 NotebookLM 三栏 Session UI skeleton**
  - 最小方案：左 Sources/Tree/Graph，中 Session Chat，右 Session Note/Workflow Studio；复用现有上传、模型选择、LLM 开关、推荐问题、citation 和后台入口。
  - 证据：`App/web/src/App.tsx`、`App/web/src/styles.css` 已切到 Session Workspace shell；`npm run build` 通过；localhost 关 LLM 后推荐问题真实调用 `/chat/query`，Reference 面板回填引用，浏览器 console 无 error。
  - 后续：把 Tree/Graph/Note 从静态预览接入真实 Session contract、AnswerEvidencePackage 和 section graph。

- [x] **G8-03 UI v0.4 PRD/TODO 打磨**
  - 最小方案：吸收 UI 评审反馈，修订 PRD 与 Session Spec，明确左侧 Base、真实 Tree/Graph、Chat transcript、Note-only、企业视觉系统和开源参考取舍。
  - 证据：[PRD-流程问答工作台.md](PRD-流程问答工作台.md) 已更新到 v0.4；[Todo+Spec-流程问答工作台.md](Todo+Spec-流程问答工作台.md) 已补 G8-03 到 G8-09 任务和 Tree/Graph/Note contract。

- [ ] **G8-04 Session Source Base 实现**
  - 最小方案：Sources 按当前 session scope 展示 selected/excluded/session-only/parsed/failed/low confidence 状态。
  - 验收：切换 session 或 source scope 后，左侧 Sources、顶部 scope 和 query request 使用同一组 source ids。

- [ ] **G8-05 真实 Tree / Graph 实现**
  - 最小方案：Tree 从 parser/sections/chunks 数据生成；Graph 从 document relation / extracted relation / answer evidence 生成。
  - 验收：没有真实数据时显示空状态；点击节点或边能联动 Tree、citation 或 source chip。

- [ ] **G8-06 Chat transcript + bottom composer**
  - 最小方案：中间区域改为上方消息流、底部固定输入；回答追加到 transcript，支持 citation chips 和 pin to note。
  - 验收：提问后输入框仍在底部，回答在上方消息流，推荐问题不挤占主流程。

- [ ] **G8-07 Note-only right panel + visual system**
  - 最小方案：右侧只保留 Session Note；移除 Admin/Reference/Workflow tabs；按 Jianan presentation / Siemens Healthineers 风格打磨颜色、密度和控件状态。
  - 验收：桌面首屏可截图汇报，移动端无重叠；右侧 note 随 session 切换。

## 3. 阶段状态速览

| Gate | 所属阶段 | 状态 | 当前证据 | 下一步 |
| --- | --- | --- | --- | --- |
| G0 | Phase 0 | In progress | PRD / Spec 已存在 | 固化 session/source/note contract |
| G1 | Phase 1 | Done | API 已返回 workflow/eval/review 字段；验证 `89 passed` | 人工核查状态口径 |
| G2 | Phase 1 | Done | Markdown heading / block / line anchors；验证 `89 passed` | 人工核查 Reference 粒度 |
| G3 | Phase 2 | Code done, review pending | CT/MI/XP PEP smoke；验证 `109 passed` | 人工核查 P2-01 level jump 和关键章节树 |
| G4 | Phase 3 | Later | XLSX parser 基础存在 | 设计 table anchors 和 retrieval cases |
| G5 | Phase 3 | Done | CT 146 chunks / MI 93 / XP 163；验证 `109 passed` | 接入 G6 EvidencePackage |
| G6 | Phase 4 | In progress | G6-01/02/03 已实现；`compileall`、`pytest`、`git diff --check`、diagnostics 通过，当前 `114 passed` | 实现 G6-04 + G6-05 |
| G7 | Phase 3 | Queue MVP done | `visual_review_items` 已返回 CT 2 / MI 1 / XP 5 | 做 crop / OCR / multimodal candidate pipeline |
| G8 | Phase 5 | In progress | v0.4 PRD/Spec 已吸收 UI 评审反馈；v0.3 skeleton 已通过 build 与 localhost smoke | 实现 Session Source Base、真实 Tree/Graph、Chat transcript 和 Note-only 右栏 |
| G9 | Phase 3.5 | In progress | G9-01 Parser Fusion Core Contract、G9-02 Docling Provider Integration 和 G9-03 PDF Fusion Pipeline 已完成；[Tool-Parser-RAG-Fusion-Spec.md](Tool-Parser-RAG-Fusion-Spec.md) 定义后续 DOCX table/layout fusion、OCR/visual provider 和 Hybrid RAG 计划 | 进入 G9-04 DOCX Table/Layout Fusion，或按产品优先级切到 G9-06 Retriever Interface + Hybrid RAG |

## 4. 附件地图

计划和方案以第 2 节阶段计划为准；下表只说明外部文档作为附件时的用途。

| 文件 | 角色 | 何时看 |
| --- | --- | --- |
| [TODO.md](TODO.md) | 唯一阶段计划入口 | 每次开始开发先看 |
| [README.md](README.md) | 附件导航 | 找文件时看 |
| [PRD-流程问答工作台.md](PRD-流程问答工作台.md) | 产品定义 | 产品边界不清时看 |
| [Todo+Spec-流程问答工作台.md](Todo+Spec-流程问答工作台.md) | Session MVP 详细规格 | 前端/Session contract 下钻时看 |
| [Tool-Parser-RAG-Fusion-Spec.md](Tool-Parser-RAG-Fusion-Spec.md) | Tool 融合详细规格 | 做 QT Parser Core、provider fusion、Docling provider、PDF fusion、OCR/visual provider、Hybrid RAG 时看 |
| [MultiInput-Parser-RAG-Workflow-设计.md](MultiInput-Parser-RAG-Workflow-设计.md) | Parser/RAG 架构背景 | 需要理解技术路线时看 |
| [Parser-Workflow-Evals-实施计划.md](Parser-Workflow-Evals-实施计划.md) | 历史详细计划附件 | 查 parser/evals 细节时看；执行以本 TODO 为准 |
| [Gate3-PEP-PDF-Review.md](Gate3-PEP-PDF-Review.md) | G3 证据附件 | 核查 CT/MI/XP 章节树时看 |
| [Gate6-Adaptive-Answer-Workflow-Plan.md](Gate6-Adaptive-Answer-Workflow-Plan.md) | G6 历史详细方案附件 | 查 G6 背景时看；执行以本 TODO Phase 4 为准 |
| [Pro-Input-Praser.md](Pro-Input-Praser.md) | Parser 经验沉淀 | 处理 OCR/multimodal/parser 边界时看 |
| [dev-memory/](dev-memory/) | 开发记忆和会话交接 | 长会话恢复时看 |
| [old/](old/) | 旧框架归档 | 查旧 upload-approval / regulation navigator 思路时看 |

## 4.1 当前文件角色与命名判断

当前先采用“软整理”，保留现有文件名，避免一次性改名导致链接碎掉。后续优先把计划和方案写回本文件；只有证据、经验、产品定义或很长的技术背景才新增外部文档。

| 类型 | 命名规则 | 当前对应文件 | 用途 |
| --- | --- | --- | --- |
| 总入口 | `TODO.md` | [TODO.md](TODO.md) | 唯一阶段计划入口 |
| 产品定义 | `PRD-<主题>.md` | [PRD-流程问答工作台.md](PRD-流程问答工作台.md) | 产品边界和用户价值 |
| 详细规格 | `Spec-<主题>.md` 或保留当前 `Todo+Spec-<主题>.md` | [Todo+Spec-流程问答工作台.md](Todo+Spec-流程问答工作台.md) | Session MVP 详细规格 |
| 架构研究 | `<领域>-Workflow-设计.md` | [MultiInput-Parser-RAG-Workflow-设计.md](MultiInput-Parser-RAG-Workflow-设计.md) | 技术路线和架构原则 |
| 分支实施计划 | 优先写入本文件 Phase；必要时才用 `Gate<N>-<主题>-Plan.md` 做附件 | [Parser-Workflow-Evals-实施计划.md](Parser-Workflow-Evals-实施计划.md)、[Gate6-Adaptive-Answer-Workflow-Plan.md](Gate6-Adaptive-Answer-Workflow-Plan.md) | 历史详细背景，执行以本 TODO 为准 |
| Gate 证据报告 | `Gate<N>-<主题>-Review.md` | [Gate3-PEP-PDF-Review.md](Gate3-PEP-PDF-Review.md) | 人工核查、smoke、样例证据 |
| 经验方法 | `<主题>-Notes.md` 或当前经验名 | [Pro-Input-Praser.md](Pro-Input-Praser.md) | 经验、难点、方法沉淀 |
| 归档 | `old/<主题>/` | [old/](old/) | 旧路线，只查阅不维护 |

后续如果要正式改名，建议单独做一次“Design 文件迁移”任务：先改文件名，再批量更新链接，再跑 `git diff --check`。当前阶段先不改名。

## 5. 人工核查队列

人工核查任务已经放回第 2 节对应 Phase；这里仅保留跨阶段提醒。

- [ ] 核查完成后，把结论写回对应 Phase 的 `验收证据` 或 checkbox 说明。
- [ ] 证据较长时，追加到对应 Review / Notes 附件，并在本文件保留一句证据摘要。

## 6. Later / Backlog

- [ ] Feishu CLI adapter。
- [ ] Teachany 类训练交互。
- [ ] Slides / PPT outline。
- [ ] 多用户权限与 SharePoint / Blob 接入。

## 7. 收尾规则

- [ ] 完成代码或文档变更后，同步 [dev-memory/SESSION-WIP.md](dev-memory/SESSION-WIP.md)。
- [ ] 重大或已验证变化同步 [CHANGELOG.md](../CHANGELOG.md)。
- [ ] Gate 状态变化同步本文件第 3 节。
- [ ] 可验证任务必须记录测试、诊断或人工核查证据。