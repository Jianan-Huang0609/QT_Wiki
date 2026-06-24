# Spec: Parser / RAG 中间格式改造

更新时间：2026-06-23
状态：Active Spec
上层入口：[TODO.md](TODO.md)
吸收来源：[old/MultiInput-Parser-RAG-Workflow-设计.md](old/MultiInput-Parser-RAG-Workflow-设计.md)、[old/Parser-Workflow-Evals-实施计划.md](old/Parser-Workflow-Evals-实施计划.md)、[old/Tool-Parser-RAG-Fusion-Spec.md](old/Tool-Parser-RAG-Fusion-Spec.md)、[old/Pro-Input-Praser.md](old/Pro-Input-Praser.md)

## 1. 目标

把 PDF、Office、图片等资料转成适合 RAG / Agent 使用的结构化中间格式，而不是只做纯文本抽取。

产品体验目标是 Notebook-like：资料上传后自动解析、自动生成可检索 artifact，并用状态提示可信度。人审只处理低置信 block、复杂视觉、复杂表格和缺 anchor 风险，不作为每份文档进入问答前的强制步骤。

必须解决：

- 文本：阅读顺序、标题层级、页码、段落边界。
- 表格：行列结构、合并单元格、跨页表格、标题和脚注。
- 表中表：外表保留上下文，内表拆为 CSV/JSON，并建立 parent-child。
- 可溯源：page、bbox、section、block_id 必须保留。
- Markdown：每份资料都要生成可读、可审、可直接喂给 LLM 的 `document.md`，并和 block/chunk/source_ref 一一对应。
- RAG 友好：每份文档都能产出 `document.md`、`blocks.json`、`chunks.json` 和质量报告。

## 2. 当前问题

代码里已有 `CanonicalDocument`、`parser_fusion`、Docling provider、section chunks 和 eval，但主链路仍有明显断点：

- `parse_document()` 仍按后缀直接调用旧 parser，fusion provider 还不是主入口。
- `ProcessedDocument.content` 仍是 fragments/tables 的纯文本拼接，不是稳定 Markdown artifact。
- Canonical schema 只有 `sections/fragments/tables/figures`，没有统一的 `DocumentBlock[]`。
- `parser_fusion` 更像 trace/summary，不是下游 RAG 的事实源。
- 表格、复杂表格、表中表、bbox、cell range、parent-child 没成为统一 citation contract。
- `needs_review` 当前容易被 UI 解读为整份文档不可用；需要拆成 document-level status 和 block/evidence-level review queue。

## 3. 目标架构

```text
File + Manifest
  -> Parser Router
       clean digital -> MarkItDown / existing fast parser
       enterprise structured -> Docling
       complex Chinese/table/formula/scanned -> Marker or MinerU optional provider
       low quality -> OCR/VLM review candidate
  -> Provider Outputs
       ExtractionBlock / LayoutBlock / TableBlock / VisualCandidate
  -> Fusion / Structure Resolver
       reading order / heading / table / anchor merge
  -> DocumentBlock[]
  -> RAG Artifacts
       document.md
       blocks.json
       chunks.json
       quality_report.json
       tables/*.csv
  -> Auto Source Status
       ready / limited / needs_review / failed / ocr_required
  -> Retrieval / Evidence / Chat
```

### 3.1 Notebook-like 自动解析策略

- 每份上传文档默认自动 parse、artifact、index，并出现在 Source Intake。
- 文档状态表达整体可用性：`ready`、`limited`、`needs_review`、`failed`、`ocr_required`。
- Review queue 精确到 block/table/visual candidate/source anchor，不把整份文档默认推给人审。
- `ready` 和 `limited` 文档可进入 Ask Workspace；低置信 block 从 primary evidence 中排除或降权。
- `needs_review` 表示存在值得核查的局部风险，仍允许用户基于高置信文本块提问。

### 3.2 Parser-to-Markdown 产品契约

`document.md` 是用户和 LLM 都能阅读的稳定视图，但事实来源仍以 `blocks.json` 为准。Markdown renderer 必须把每个内容块的锚点写成机器可读注释，保证 UI、RAG、citation 可以从 Markdown 回跳到 block。

首版 Markdown 结构：

```markdown
---
document_id: "ct-pep"
file_name: "20260611163219-CT PEP AND 308 11.pdf"
source_type: "pdf"
parse_status: "limited"
primary_provider: "docling"
provider_trace:
  - "pypdf_fast_text"
  - "docling"
quality:
  text_order_score: 0.91
  heading_score: 0.86
  table_structure_score: 0.74
---

<!-- qt:block_id=sec_007 type=heading page=12 bbox="72,130,510,155" section_id="r2-planning" -->
## R2 Planning

<!-- qt:block_id=txt_044 type=text page=12 bbox="72,180,510,238" section_id="r2-planning" -->
R2 Planning defines the preparation activities...

<!-- qt:block_id=tbl_003 type=table page=14 bbox="64,220,530,470" section_id="r2-planning" csv="tables/tbl_003.csv" json="tables/tbl_003.json" -->
| Role | Deliverable |
| --- | --- |
| PO | QMP |
```

Markdown renderer 规则：

- frontmatter 记录 document-level metadata、provider trace 和质量摘要。
- 每个可引用 block 前都有 `qt:block_id` 注释；`block_id` 与 `blocks.json` 完全一致。
- 标题层级由 QT PEP structure resolver 决定；provider 的 layout header 作为证据参与融合。
- 表格既渲染 Markdown table，也输出 CSV/JSON/HTML 资产路径；复杂表格可用摘要 + asset link。
- 图片、扫描区域、公式以可读占位符进入 Markdown，并保留 crop/ocr anchors。
- Markdown 中的 quote 必须能在 `blocks.json.source_refs[].quote` 找到对应摘录。

### 3.3 Artifact 边界

`document.md`、`blocks.json`、`chunks.json` 和 `quality_report.json` 分工如下：

| Artifact | 主要消费者 | 职责 |
| --- | --- | --- |
| `document.md` | 人、LLM direct context、Review Gate | 可读文档、标题层级、引用锚点、表格/图片占位。 |
| `blocks.json` | RAG、citation、eval、Admin / JSON Lab | 稳定事实源，记录 block content、anchors、provider trace、confidence。 |
| `chunks.json` | retriever、answer workflow | 面向召回的 section/table/figure chunk，继承 block_id/source_refs。 |
| `quality_report.json` | UI 状态、review queue、eval gate | 文档状态、可用 evidence、低置信原因、provider fallback。 |
| `tables/*`、`crops/*` | Review Gate、精确引用、表格 QA | 复杂表格、表中表、图片/扫描区域的可审资产。 |

## 4. DocumentBlock Contract

首版 contract：

```json
{
  "doc_id": "doc-...",
  "block_id": "b_001",
  "type": "text|table|inner_table|image|formula",
  "content_md": "...",
  "content_text": "...",
  "content_json": {},
  "content_csv_path": "tables/t_003.csv",
  "page": 3,
  "bbox": [0, 0, 0, 0],
  "section_id": "sec-...",
  "heading_path": ["H1", "H2"],
  "parent_id": null,
  "children_ids": [],
  "source_refs": [
    {
      "document_id": "doc-...",
      "block_id": "b_001",
      "anchor_label": "p.3",
      "quote": "...",
      "anchors": { "page": 3, "bbox": [0, 0, 0, 0] }
    }
  ],
  "confidence": 0.92,
  "provider_trace": ["pypdf_fast_text", "docling"]
}
```

Contract 规则：

- `block_id` 是 RAG、citation、UI reference 的稳定最小单位。
- `content_md` 给 LLM 和 Markdown preview 使用。
- `content_json` 给表格、结构化对象、精确引用和 eval 使用。
- `content_text` 给 embedding / full-text retrieval 使用。
- `source_refs` 必须保留 document、block、anchor 和 quote。
- `page/bbox` 不可用时保留缺口状态，质量报告必须说明原因。

## 5. RAG Artifacts

每份文档解析后输出：

```text
Tool/output/rag/{document_id}/document.md
Tool/output/rag/{document_id}/blocks.json
Tool/output/rag/{document_id}/chunks.json
Tool/output/rag/{document_id}/quality_report.json
Tool/output/rag/{document_id}/tables/*.csv
Tool/output/rag/{document_id}/tables/*.json
Tool/output/rag/{document_id}/crops/*.png
```

`document.md` 用于人读和 LLM direct context。
`blocks.json` 用于 RAG 事实源。
`chunks.json` 用于检索和 answer evidence。
`quality_report.json` 用于 Review Gate 和 Admin / JSON Lab。

质量报告必须区分：document status、可用 primary evidence 数量、review queue 数量、被排除的 block/candidate 数量。

Artifact 生成原则：

- `blocks.json` 是 `document.md` 的 source of truth；Markdown 可以重渲染。
- `chunks.json` 从 blocks 生成，保留 `source_refs`、`block_ids`、`section_id`、`heading_path`。
- 任何进入 Chat citation 的 evidence 都必须来自带 quote 和 anchor 的 block/chunk。
- `quality_report.json` 记录 provider choice、fallback reason、缺失 page/bbox 的原因和人工 review item。

## 6. Parser Router

Parser Router 做两层判断：先判定输入形态，再选择 provider 组合。默认输出永远进入 QT 自己的 `DocumentBlock[]` 和 artifact bundle。

### 6.1 开源能力融合矩阵

| 技术 / 仓库能力 | 本项目角色 | 适用输入 | 融合方式 | 质量门 |
| --- | --- | --- | --- | --- |
| MarkItDown | Markdown-first provider | clean Office、HTML、轻量 PDF、可直接转 Markdown 的资料 | 作为 `MarkdownExtractionProvider`，快速产出 `content_md`，再切成 blocks | page/bbox 弱时标记 `limited`，进入 secondary evidence 或 direct context。 |
| 现有 pypdf / DOCX XML parser | fast / structure-preserving provider | CT/MI/XP PEP PDF、DOCX 工作流文档 | 保留 PEP heading detector、History/TOC/Figure cleanup、DOCX 顺序解析 | 继续跑已有 parser eval，提供可解释 baseline。 |
| Docling | 主 layout/table/OCR provider | 企业 PDF、表格型 PDF、多栏/复杂 layout | 已有 lazy provider；输出 layout/text/table/visual blocks，补 page/bbox/reading_order | Windows/安装体积/许可证确认后进入 parser extra；结构分数达标时默认主用。 |
| Marker | PDF-to-Markdown / complex layout optional provider | 论文式 PDF、公式、复杂中文排版、Docling/pypdf 质量不足的 PDF | 作为 `MarkerMarkdownProvider`，产出 Markdown + metadata，再映射为 blocks | 与 Docling/pypdf 对齐；低一致性时进入 review queue。 |
| MinerU | OCR/layout/table optional provider | 扫描件、图片型 PDF、复杂图表、中文文档 | 作为 `MinerUVisualProvider`，输出 OCR text、table、figure crop anchors | 只有高置信且有 page/crop/bbox 的候选进入 primary evidence。 |
| OCR/VLM visual provider | 视觉候选层 | 扫描区域、图片、图注、低质量表格 | 输出 `VisualCandidate` 和 crop；Review Gate 精确到 block/crop | reviewed/accepted 或高置信有锚点后进入 chunks。 |
| RAGFlow / DeepDoc | chunk/retrieval/eval 方法库 | 多文档问答、table chunking、hybrid recall | 借鉴 template chunking、multi-recall、fusion rerank、citation visualization | 保持 QT `RetrievalResult` / `AnswerEvidencePackage` contract。 |
| SurfSense | Search Space / hybrid retrieval 参考 | Selected Docs、All Sources、跨 BU 对比 | 借鉴 source scope、hybrid semantic + full-text、RRF、cited answer UI | 先在 `Tool/retrieval` 内实现策略，连接器和自动化后续接入。 |
| Open Notebook | Notebook-like 信息架构参考 | Source / Note / Chat / Reference 工作台 | 借鉴 source readiness、fine-grained context control、note pinning | QT UI 保持文件级 Source Tree，block 细节进入 Review/Reference。 |

### 6.2 路由策略

| 文档特征 | Provider 组合 | 说明 |
| --- | --- | --- |
| clean digital PDF | pypdf + Docling lightweight | pypdf 提供快路径，Docling 补 layout/bbox/table。 |
| enterprise structured PDF | Docling + pypdf + PEP resolver | Docling 主供 layout/table，QT resolver 主供业务章节和噪音清理。 |
| Office document | DOCX XML / native parser + MarkItDown + Docling optional | 保留真实段落/表格顺序，同时快速生成 Markdown 草稿。 |
| scanned / image PDF | MinerU or OCR/VLM + Docling OCR | 先生成 visual candidates 和 review queue，高置信部分进入 primary evidence。 |
| table-heavy / nested table | Docling + Marker/MinerU fallback | 表格结构、cell anchors、跨页合并作为重点质量门。 |
| parser disagreement | Provider fusion + eval gate | 通过 text overlap、page anchor、bbox、heading path、table schema 对齐决策。 |

依赖策略：

- Docling 继续作为核心 layout/table provider，因为代码中已有 lazy provider 和 provider fusion metadata。
- MarkItDown 作为轻量 Markdown-first provider，适合 Office/HTML/clean input 的快路径。
- Marker / MinerU 作为 optional provider，通过 CT/MI/XP 和 demo PDF eval 决定启用条件。
- 新依赖加入 requirements 前确认 Windows、安装体积、许可证、离线可用性和运行成本。

## 7. Parser-to-Markdown Pipeline

### 7.1 Stage 0: File Profiling

输入：Raw file + manifest。

输出：`FileProfile`。

字段建议：

```json
{
  "document_id": "ct-pep",
  "file_name": "20260611163219-CT PEP AND 308 11.pdf",
  "mime_type": "application/pdf",
  "page_count": 42,
  "has_text_layer": true,
  "scan_ratio": 0.08,
  "office_family": null,
  "language_hints": ["en", "zh"],
  "risk_hints": ["table_heavy", "pep_document"]
}
```

### 7.2 Stage 1: Provider Collection

Router 根据 profile 选择 provider collection，而不是只选一个 parser。每个 provider 只负责生成证据块：

- pypdf：text blocks、page anchor、fast heading candidates。
- DOCX XML：段落/表格顺序、Heading style、cell range。
- MarkItDown：Markdown draft、Office/HTML clean conversion。
- Docling：layout blocks、reading order、tables、bbox、OCR/image candidates。
- Marker/MinerU：optional Markdown/OCR/table/figure candidates。

### 7.3 Stage 2: Normalize to Extraction Blocks

所有 provider 统一映射到四类临时对象：

- `ExtractionBlock`：普通文本和 heading candidate。
- `LayoutBlock`：带 bbox/reading_order 的文本或区域。
- `TableBlock`：表格结构、HTML/CSV/JSON、cell anchors。
- `VisualCandidate`：图片、扫描区域、OCR/VLM 候选。

### 7.4 Stage 3: Fusion / Structure Resolver

Fusion layer 对齐 provider 结果：

- page + normalized text overlap 对齐文本。
- bbox + reading_order 修正阅读顺序。
- provider agreement 提升 confidence。
- table schema / row count / header similarity 合并表格。
- OCR/VLM 候选以 review status 控制进入 primary evidence。

PEP structure resolver 负责企业流程语义：

- R-stage、PO/PL/SM 等角色信号。
- History/TOC/Figure caption 噪音清理。
- section tree repair。
- deliverable / record / responsibility table 语义标记。

### 7.5 Stage 4: Build DocumentBlock[]

融合结果转成稳定 blocks：

- text/heading block：`content_md` 和 `content_text` 同步生成。
- table block：保留 `content_md`、`content_json`、`content_csv_path`、`cell_range`。
- inner_table block：建立 `parent_id` / `children_ids`。
- image/formula block：保留可读描述、crop path、review status。
- 每个 block 必须生成 `source_refs`，包含 document_id、block_id、anchor_label、quote、anchors。

### 7.6 Stage 5: Render document.md

Renderer 从 `DocumentBlock[]` 生成 Markdown：

- frontmatter 写入 document metadata 和 quality summary。
- block comment 写入 block_id/type/page/bbox/section/provider。
- heading_path 控制 Markdown heading level。
- table block 渲染 Markdown table；复杂表格增加 CSV/JSON link。
- visual block 渲染为 `![caption](crops/...)` 或文字占位，并带 review status。
- renderer 可重复运行，避免人工编辑成为事实源。

### 7.6A EvidenceSource Adapter

当前 Release-0 先不等待完整 `DocumentBlock[]`，而是从 `SectionChunk + AnswerEvidencePackage + CitationPayload` 适配出轻量 `EvidenceSource`：

- `evidence_id / citation_id`
- `document_id / file_name`
- `chunk_id / section_id / heading_path`
- `anchor_label / quote / source_context`
- `quality_warning / usable_as_primary_evidence`

这个 adapter 是 Reference UI、Claim Guardrail、quality warning 和后续 parser 表格元素抽取之间的稳定桥。Parser 后续只需要把更强的 table/cell/visual anchors 供给 EvidenceSource，不直接泄漏 provider backend 字段到 Chat/UI 主路径。

### 7.6B External Architecture References

Parser/RAG 层只吸收这些外部架构的证据与检索落点：

- Self-RAG -> Thin Claim Guardrail + on-demand retrieval。
- GraphRAG -> later multi-doc graph summaries。
- DSPy -> eval-driven prompt/router optimization。
- Enterprise QA lessons -> evidence boundary + human review。

VMAO 和 MEQA 主要落在 Chat Runtime / tool orchestration；Parser/RAG 的职责是稳定输出 EvidenceSource、quality warning、table/cell/visual anchors 和 eval evidence。

### 7.7 Stage 6: Blocks -> Chunks -> Retrieval

Chunk builder 以 blocks 为输入：

- section chunk 聚合同 section 的 text/table/figure blocks。
- table chunk 单独记录 semantic summary、key rows、source refs。
- figure/OCR chunk 只有在 review gate 接受或高置信时进入 primary evidence。
- chunk 继承 `block_ids`，让 Chat citation 可以回到 block 和 Markdown anchor。

### 7.8 Stage 7: Quality Gate / Review Queue

质量门给出文档状态和 block 级 queue：

- `ready`：primary evidence 足够，关键 block 均有 anchor。
- `limited`：主体文本可用，部分表格/图片/bbox 缺口进入 review queue。
- `needs_review`：关键章节或高价值表格存在低置信风险，Ask Workspace 降权使用。
- `ocr_required`：文本层不足，需要 OCR/MinerU/VLM provider。
- `failed`：无可用 primary evidence。

## 8. 表格和表中表策略

### 简单表格

- 输出 Markdown table。
- 同时保留 JSON rows 和 source anchors。
- chunk text 使用表格摘要 + 关键行列。

### 复杂表格

- 不只转 Markdown。
- 输出 table block：`content_md + content_json/html + bbox + cell_range`。
- 为每张表生成 table summary，用于 embedding。

### 表中表

- 外层表保留 Markdown/HTML，用于阅读结构。
- 内层表拆成独立 CSV/JSON block。
- 外层单元格中使用占位符：`[inner_table:block_id]`。
- metadata 建立 parent-child：`inner_table.parent_id = outer_table.block_id`。

## 9. 样例文件融合策略

### 9.1 CT / MI / XP PEP PDF

当前 Raw 样例：

- `Raw/20260611163219-CT PEP AND 308 11.pdf`
- `Raw/20260611163304-MI PEP AND 308 11.pdf`
- `Raw/20260611163330-XP PEP AND 308 11.pdf`

融合策略：

- pypdf 保留已有 PEP heading、TOC/History/Figure cleanup 经验。
- Docling 补 page bbox、reading order、table structure 和 figure/image anchors。
- PEP resolver 统一决定 R2/R3/7.16 等业务章节树。
- 表格重点验证 History 表、职责矩阵、deliverable / record / approval plan 相关表。
- Chat 验收问题优先覆盖 Selected Docs：MI-only、CT-only、CT+MI+XP 对比。

验收输出：

- 每份 PEP 至少生成 `document.md`、`blocks.json`、`chunks.json`、`quality_report.json`。
- R2/R3/7.16 等章节的 Markdown heading 与 section chunks 一致。
- 引用能回到 file + page + section + block_id；有 bbox 时 Reference 卡可显示 bbox anchors。
- History/TOC 噪音低权重或排除，避免污染流程问答。

### 9.2 demo PDF

当前 demo PDF 用来验证常规 PDF 解析稳定性：

- `Raw/20260612090900-demo.pdf`
- `Raw/20260612091024-demo.pdf`

融合策略：

- 用 MarkItDown / pypdf 快路径验证 Markdown 可读性。
- 用 Docling 验证 layout/table anchors 是否优于快路径。
- 若 provider 输出差异明显，进入 fusion decision 和 quality report。

### 9.3 Office / 图片输入

Office 文件目标路线：

- DOCX：DOCX XML parser 保留段落和表格顺序；MarkItDown 产出 Markdown draft；Docling optional 补 layout。
- PPTX：按 slide/page 生成 block，保留 slide number、shape bbox、speaker note。
- XLSX：每个 sheet/range 生成 table block，保留 sheet、range、merged cell、formula/value。
- 图片：MinerU/OCR/VLM 生成 visual candidates；高置信或人工接受后进入 chunks。

## 10. 实施步骤

- [ ] **P0 Auto parse status policy**
  - 文件候选：`Tool/workflows/rag_artifacts.py`、`App/schemas.py`、`tests/test_rag_auto_status.py`。
  - 验收：sample document 可以同时表达 document status 和 block-level review queue；`needs_review` 不阻断高置信文本 retrieval。

- [ ] **P0.5 FileProfile + Provider capability matrix**
  - 文件候选：`Tool/parsers/router.py`、`tests/test_parser_router.py`。
  - 验收：CT/MI/XP PEP、demo PDF、DOCX、XLSX、图片都能得到明确 provider plan 和 fallback reason。

- [ ] **P1 DocumentBlock dataclass / schema**
  - 文件候选：`Tool/contracts/rag.py`、`tests/test_rag_document_contract.py`。
  - 验收：sample canonical 可转为 blocks，block source_refs 可序列化。

- [ ] **P2 Canonical -> DocumentBlock adapter**
  - 文件候选：`Tool/workflows/rag_artifacts.py`。
  - 验收：fragments、tables、figures 都能转 block；heading_path 和 anchors 不丢。

- [ ] **P3 Markdown renderer**
  - 文件候选：`Tool/workflows/rag_artifacts.py`、`tests/test_rag_markdown_renderer.py`。
  - 验收：`document.md` 包含 frontmatter、标题、章节、段落、表格、图片候选和 `qt:block_id` source anchors。

- [ ] **P4 Blocks -> chunks**
  - 验收：chunk builder 可优先消费 blocks，并保留 block_id citation。

- [ ] **P5 Parser Router 主路径**
  - 验收：parse workflow trace 包含 provider choice、fallback、quality gate。

- [ ] **P5.5 MarkItDown / Marker / MinerU optional adapters**
  - 文件候选：`Tool/parsers/providers/markitdown_provider.py`、`marker_provider.py`、`mineru_provider.py`。
  - 验收：依赖关闭时不影响主流程；依赖开启时 provider output 能进入 fusion metadata。

- [ ] **P6 Table / nested table eval**
  - 验收：至少覆盖普通表、合并/跨页表、表中表三个样例。

## 11. Eval 指标

- `text_order_score`：阅读顺序正确率。
- `heading_score`：标题层级保留。
- `table_structure_score`：行列、合并单元格、跨页保真。
- `nested_table_score`：表中表 parent-child 是否正确。
- `citation_score`：page / bbox / block_id 是否可回溯。
- `markdown_anchor_score`：`document.md` 中 block comment 与 `blocks.json` 是否一一对应。
- `provider_selection_score`：Router 是否选择了合适 provider 组合。
- `rag_answer_score`：进入 RAG 后答案准确率。
- `latency_cost`：单页耗时与成本。

## 12. 验收样例集

- [ ] CT PEP PDF：R2/R3/7.16 heading、History/TOC cleanup、引用 page/block 回跳。
- [ ] MI PEP PDF：Selected Docs 问答、职责/交付物表格、source scope citation。
- [ ] XP PEP PDF：跨 BU 对比、section chunk consistency。
- [ ] demo PDF：clean PDF Markdown 可读性和 provider fallback。
- [ ] 普通表格 PDF。
- [ ] 合并单元格 / 跨页表格 PDF。
- [ ] 表中表 PDF。
- [ ] 扫描件 PDF。
- [ ] 中文业务文档。
- [ ] Office 文件：DOCX / PPTX / XLSX。