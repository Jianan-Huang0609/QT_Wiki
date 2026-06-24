# Spec: UI Workspace / 四页操作流改造

更新时间：2026-06-23
状态：Active Spec
上层入口：[TODO.md](TODO.md)
吸收来源：[old/Todo+Spec-流程问答工作台.md](old/Todo+Spec-流程问答工作台.md)、[PRD-流程问答工作台.md](PRD-流程问答工作台.md)、[old/G9-Human-Review-Pack.md](old/G9-Human-Review-Pack.md)

## 1. 目标

把当前混合工作台拆成用户能理解的四页操作流：

```text
Source Intake -> Review Gate -> Ask Workspace -> Admin / JSON Lab
```

用户主路径：

1. 上传或选择资料。
2. 系统自动解析并显示文件级状态。
3. 进入 Ask Workspace 对资料提问。
4. 在 Reference 中核查原文，并围绕同一 source 继续追问。

开发 / 调试路径进入 Admin / JSON Lab，避免普通用户被 parser/debug 细节干扰。

当前 UX 硬约束：侧边 Source / Tree 默认只展示文件本身。章节、section、block、chunk 是 drill-down 信息，放在 Review Gate / Admin / Reference 详情里，不在 Ask Workspace 左侧展开成子项。

## 2. 当前问题

- Ask Workspace v1 已能跑 selected-doc query、Answer Run 和 Reference Card；Pin / Session Note 入口已从主路径移除，避免干扰原文核查。
- Source、Tree、Graph、Review Queue、Quality、JSON、Admin、Chat 曾经混在一个界面里，用户不知道下一步做什么。
- Reference 主路径已收敛为文件、页码/锚点和 quote；block/table/cell anchors 后续作为 drill-down 或 Admin/Review 详情。
- Review Gate 和 Admin / JSON Lab 仍没有成为独立页面。
- 侧边 Tree 曾经偏章节树，会让用户把 parser/debug 结构误认为主操作路径。

## 3. 页面职责

### 3.1 Source Intake

回答“现在有哪些资料可用”。

内容：

- 上传入口。
- 最近运行 recent runs。
- 文件级 source card。
- parse status / quality summary。
- 当前 session source scope。

Source card 默认字段：file_name、source_type、selected、parse_status、quality chip、last parsed time。章节数量和 review items 只作为展开详情或 Review Gate 信息。

### 3.2 Review Gate

回答“这份资料可信不可信，哪里要人审”。

内容：

- parse status。
- quality gates。
- 文件级 document list + 可选章节 drill-down。
- review items。
- visual/table candidates。
- evidence preview。
- accept / needs review / skip review 的最小状态。

### 3.3 Ask Workspace

回答“围绕这些资料提问、追问并核查原文”。

内容：

- 文件级 source scope。
- Chat transcript。
- bottom composer。
- Answer Run timeline。
- Reference Cards：默认显示文件、页码/锚点和 quote；选中引用可展开完整返回原文、前文和后文。
- request-level follow-up context：连续提问时沿用上一轮问题、source scope 和引用摘要。

### 3.4 Admin / JSON Lab

回答“开发者如何核查系统内部状态”。

内容：

- raw handoff。
- parse workflow。
- blocks / chunks JSON。
- quality report。
- tool trace。
- eval report。
- static snapshot export。

## 4. 信息架构

```text
Top Bar
  Source scope / model / backend status

Left Navigation
  Source Intake
  Review Gate
  Ask Workspace
  Admin / JSON Lab

Main Area
  Current page content

Right Context
  Page-specific details only
```

Ask Workspace 推荐布局：

```text
Left: Resource / file-level source scope list, including upload entry and selected source state
Center: Chat transcript + Answer Run + composer
Right: Reference Viewer for end-user source inspection
```

主体验约束：左侧只回答“本轮用了哪些资源、能不能上传/切换资源、解析状态如何”，右侧只回答“这条引用来自哪个文件、页码/锚点是什么、返回原文是什么”。章节树、chunk JSON、parser debug 字段继续放在 Review Gate / Admin，不进入 Ask Workspace 主路径。

Review Gate 推荐布局：

```text
Left: Document tree
Center: Review queue + evidence preview
Right: Quality summary + table/visual candidates
```

## 5. UI Contract

前端只消费后端 contract，不解析 raw internals：

- `SessionHandoff.source`
- `SessionHandoff.tree`
- `SessionHandoff.quality`
- `SessionHandoff.retrieval.preview_chunks`
- `ChatQueryResponse.answer_run`
- `ChatQueryResponse.citations`
- `ChatQueryResponse.structured_matches[AnswerEvidencePackage]`
- 后续 `RagDocument.blocks/chunks/quality_report`

Ask Workspace 的 source list 只消费文件级 source contract；`tree.items` 默认不在左侧展开。Review Gate 可以读取 tree/items 做局部 drill-down。

Reference Card 默认字段：

```json
{
  "file_name": "MI PEP AND 308 11.pdf",
  "section_title": "4 Procedure and Requirement",
  "anchor_label": "p.12",
  "quote": "...",
  "citation_id": "c1"
}
```

Reference 展开 / Admin 字段：

```json
{
  "document_id": "doc-...",
  "block_id": "b_...",
  "table_id": "tbl-...",
  "cell_range": "R1C1:R2C2"
}
```

Reference 主路径的展开内容来自 `source_context`，按 `返回原文 / 前文 / 原文段落 / 后文` 渲染为可读段落；Chat 正文只保留结论、动作、边界和 citation label，不在正文重复展开原文命中或相邻上下文。

2026-06-24 后续 UI 顺序：Reference polish 先消费 `EvidenceSource`，再做视觉层优化。右侧 Reference Card 应优先使用 `evidence_sources[*].usable_as_primary_evidence` 和 `quality_warning` 显示轻量质量提示；table/cell/visual anchors 作为 drill-down 信息进入 Review Gate / Admin，不进入普通 Ask Workspace 主路径。

## 6. 实施步骤

- [ ] **U0 文件级 Source / Tree baseline**
  - 验收：Ask Workspace 左侧只显示文件卡片；章节树入口移动到 Review Gate / Admin drill-down。

- [ ] **U1 页面路由 / view state 收敛**
  - 验收：四个主页面能切换；默认入口清晰。

- [ ] **U2 Source Intake 页面**
  - 验收：上传、recent runs、source cards、parse status 在同一页；上传后的资源能进入文件级 Resource/Source list，并可作为下一轮 Ask Workspace source scope。

- [ ] **U3 Review Gate 页面**
  - 验收：quality、review queue、table/visual candidates 和章节 drill-down 可独立核查；普通文档无需逐份人审即可进入 Ask Workspace。

- [ ] **U4 Ask Workspace v2**
  - 验收：Chat 页面只保留问答、Answer Run 和 Reference；左侧 Resource/Source 不展开 parser 章节树，右侧 Reference 默认以文件、页码/锚点和 quote 为主要查看样式，并可展开完整原文与前后文。

- [ ] **U5 Admin / JSON Lab**
  - 验收：raw handoff、blocks/chunks、eval、trace 在开发页。

- [ ] **U6 Responsive / embedded browser QA**
  - 验收：VS Code 嵌入浏览器、窄屏、desktop 都无内容重叠，composer 可见。

## 7. 视觉原则

- 工作台优先，信息密度适中，避免营销式 landing hero。
- Source 默认文件级；章节、block、chunk 是 drill-down。
- Reference 必须可读：文件、章节、页码、quote 优先。
- Review 和 Chat 分离，用户先判断可信，再开始问答。
- Admin 信息完整保留，但默认不进入普通用户路径。
- 按 Siemens Healthineers / 公司汇报风格：克制、清晰、低噪音、状态语义稳定。

## 8. 验收

- `cd App/web; npm run build` 通过。
- 浏览器 smoke：上传/选择 PEP -> 自动解析状态 -> Ask Workspace 连续两问 -> Reference 可展开原文；低置信项可进入 Review Gate。
- Reference Card 默认显示文件、页码/锚点、quote，选中项默认展开完整原文和前后文。
- Answer Run 六步来自后端。
- Review Gate 显示 parser quality 和 review items。
- Admin / JSON Lab 能查看 handoff / blocks / chunks / eval。
- 窄屏无文字重叠，composer 不被遮挡。