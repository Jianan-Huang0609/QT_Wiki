# Tool Parser Core / Provider Fusion / RAG Fusion Spec

更新时间：2026-06-11  
状态：Decisioned Draft，作为 Tool 侧下一阶段详细规格和评估计划  
上层执行入口：[TODO.md](TODO.md)  
关联附件：[MultiInput-Parser-RAG-Workflow-设计.md](MultiInput-Parser-RAG-Workflow-设计.md)、[Parser-Workflow-Evals-实施计划.md](Parser-Workflow-Evals-实施计划.md)、[Pro-Input-Praser.md](Pro-Input-Praser.md)、[Gate3-PEP-PDF-Review.md](Gate3-PEP-PDF-Review.md)

## 1. 目标与架构决策

本 Spec 将 G9 定义为 **QT Parser Core provider fusion**。pypdf、DOCX XML、Docling、OCR/VLM 等外部和内部能力都作为 QT Parser Core 的 extraction providers，在代码层面吸收各自强项，最终由同一个 fusion layer、PEP structure resolver、canonical/evidence contract 和 eval gate 产出唯一可信结果。

核心判断：

- Docling 的定位是核心 `layout/table/OCR extraction provider`。
- pypdf 的定位是 `fast text extraction provider`，保留速度、可解释性和 PEP 经验价值。
- DOCX XML parser 是 `structure-preserving provider`，继续保留段落/表格顺序和样式信息。
- OCR/VLM 是 `visual extraction provider`，先输出带 anchors 与 review status 的候选。
- RAGFlow、SurfSense、Open Notebook 的价值主要是方法借鉴：template chunking、hybrid retrieval、fusion rerank、source scope、citation UX。
- 最终对下游只暴露 QT 自己的 `CanonicalDocument`、`SectionChunk`、`RetrievalResult`、`AnswerEvidencePackage`。

新的主链路：

```text
File + Manifest
  -> Extraction Providers
       pypdf fast text blocks
       DOCX XML blocks
       Docling layout / reading order / table / OCR blocks
       OCR / VLM visual candidates
  -> Parser Fusion Layer
       block alignment
       duplicate merge
       table structure merge
       anchor enrichment
       confidence scoring
       fusion decisions
  -> PEP Structure Resolver
       heading detector
       TOC / History / Figure cleanup
       R-stage / role / deliverable / BU signals
       section tree repair
  -> CanonicalDocument
  -> Chunk / Index / Retrieval
  -> AnswerEvidencePackage
  -> Eval Gate
```

## 2. 内部基础与保留价值

| 板块 | 内部已有能力 | 必须保留的强项 |
| --- | --- | --- |
| Canonical contract | `DocumentMeta`、`Section`、`Fragment`、`TableData`、`FigureData`、`source_anchors` | 下游稳定消费 QT contract，UI/answer 与 provider backend 字段解耦。 |
| PDF fast text provider | `pypdf` text-layer、页码 anchor、PEP heading detector、History/TOC/Figure cleanup | 速度快、易测、对 CT / MI / XP PEP 噪音有经验。 |
| DOCX XML provider | XML 顺序解析、Heading 样式、compact 编号标题、字母子标题 | 保持 Office 文档真实段落/表格顺序。 |
| Parser eval | missing headings、section path、tree consistency、noise、table/figure risk、LLM evidence check | 引入新 provider 后仍能防回归。 |
| Section chunk | section/table/figure chunks、source_refs、signals、anchor_label | 已能服务 RAG 和 evidence package。 |
| Retrieval MVP | source scope filter、关键词 + signal 打分、history downrank、retrieval eval | 对 R2/PO/7.16 等精确流程问题是 baseline。 |
| Answer foundation | QuestionIntent、企业词归一、AnswerEvidencePackage | RAG 输出能进入可审回答包。 |

## 3. 外部能力如何直接融合

| 外部能力 | 外部好的地方 | 代码层融合方式 | 边界 |
| --- | --- | --- | --- |
| Docling | advanced PDF understanding、reading order、layout blocks、table structure、OCR、lossless JSON/Markdown | 作为 `DoclingExtractionProvider` 直接 Python import；输出 extraction blocks，参与 fusion | QT canonical contract 仍是下游主 contract。 |
| RAGFlow / DeepDoc | template chunking、multiple recall、fused rerank、citation visualization、GraphRAG、Docling/MinerU 支持 | 借鉴 chunking / recall / rerank 策略，在 `Tool/retrieval` 内实现自己的 retrievers | QT 自己维护 retrieval contract 与持久化模型。 |
| MinerU / VLM OCR | 扫描件、图片表格、复杂论文/报告 OCR 更强 | 作为后续 `VisualExtractionProvider`，输出候选 + crop anchors + confidence | reviewed 或高置信候选才能进入 primary evidence。 |
| SurfSense | Search Space、hybrid semantic + full-text、hierarchical index、RRF、cited answer | 借鉴 source scope / hybrid retrieval / RRF；实现内部 HybridRetriever | connectors、协作、自动化后置。 |
| Open Notebook | notebook/source/note/chat 信息架构、fine-grained context control、full-text + vector search | 借鉴 session/source/note contract 和 context control | QT UI/API 继续消费本项目 contract。 |

## 4. Provider Fusion Model

Provider 产出中间 extraction blocks。Fusion layer 统一对齐、去重、补 anchors、评分，再交给 PEP structure resolver 产出 `CanonicalDocument`。

### 4.1 ExtractionBlock

```json
{
  "block_id": "pdf-pypdf-p12-b03",
  "provider": "pypdf_fast_text",
  "block_type": "text",
  "text": "R2 Planning",
  "anchors": {
    "page": 12,
    "paragraph_index": 3
  },
  "confidence": 0.82,
  "metadata": {
    "raw_order": 42
  }
}
```

### 4.2 LayoutBlock

```json
{
  "block_id": "docling-p12-layout-07",
  "provider": "docling",
  "block_type": "layout_text",
  "text": "R2 Planning",
  "anchors": {
    "page": 12,
    "bbox": [72, 130, 510, 155],
    "reading_order": 18
  },
  "layout_type": "section_header",
  "confidence": 0.91
}
```

### 4.3 TableBlock

```json
{
  "block_id": "docling-p14-table-01",
  "provider": "docling",
  "block_type": "table",
  "rows": [["Role", "Deliverable"], ["PO", "QMP"]],
  "anchors": {
    "page": 14,
    "bbox": [64, 220, 530, 470]
  },
  "confidence": 0.87
}
```

### 4.4 VisualCandidate

```json
{
  "candidate_id": "visual-ct-p18-figure-01",
  "provider": "docling_ocr|mineru|vlm",
  "candidate_type": "figure_description",
  "text": "The figure shows the R2 review flow...",
  "anchors": {
    "page": 18,
    "bbox": [80, 180, 500, 430],
    "crop_ref": "output/crops/ct-p18-figure-01.png"
  },
  "confidence": 0.76,
  "review_status": "pending_review"
}
```

### 4.5 FusionDecision

```json
{
  "decision_id": "fusion-p12-heading-r2",
  "decision_type": "merge_blocks",
  "selected_block_ids": ["docling-p12-layout-07", "pdf-pypdf-p12-b03"],
  "reason": "docling reading order supplied bbox; pypdf text matched normalized heading",
  "confidence": 0.93,
  "output_target": "section_candidate"
}
```

## 5. PDF Parser Fusion Pipeline

PDF parser 采用并行或可配置的 provider evidence collection，然后由 fusion layer 统一融合。

```text
PDF Parser Fusion
  1. pypdf fast text extraction
  2. Docling layout/table/OCR extraction
  3. optional visual OCR/VLM candidate extraction
  4. block alignment by page/text/bbox/reading_order
  5. table merge and semantic classification
  6. PEP structure resolver
  7. CanonicalDocument + fusion metadata
```

融合规则草案：

- 文本内容：pypdf 与 Docling 文本一致时合并，保留 pypdf page anchor + Docling bbox/reading_order。
- 阅读顺序：Docling reading order 优先修正多栏/复杂版面；pypdf raw order 保留在 metadata 作为对照。
- 标题识别：Docling layout header 只作为候选，最终 section tree 仍由 QT heading detector / PEP resolver 决定。
- 表格：Docling table structure 优先进入 `TableData`，再由 PEP rules 标记 History、职责矩阵、deliverable 表等语义类型。
- 图像/图注：现有 figure caption 规则保留；Docling image/layout 信息补 bbox 和 crop anchor。
- OCR：OCR/VLM 输出先进入 `VisualCandidate`；被接受后再进入 fragments/tables/figures。

## 6. Docling Provider 融合办法

Docling 作为核心依赖进入 parser 能力栈时，调用方式是内部 Python import。UI 继续消费 QT canonical / retrieval / answer contract。

目标模块：

```text
Tool/parsers/providers/
  pypdf_provider.py
  docx_xml_provider.py
  docling_provider.py
  visual_provider.py
Tool/parsers/fusion.py
Tool/parsers/pdf_fusion.py
```

Docling provider 负责：

- 调用 `DocumentConverter().convert(path)`。
- 从 DoclingDocument 中抽取 text/layout/table/image/OCR blocks。
- 尽量保留 page、bbox、reading_order、label、confidence。
- 输出 QT 自己的 `ExtractionBlock / LayoutBlock / TableBlock / VisualCandidate`。

Docling provider 的职责边界：

- Section tree 由 PEP structure resolver 决定。
- Final `CanonicalDocument` 由 fusion layer + resolver 产出。
- Parser eval gate 覆盖 Docling 增强后的最终结果。
- OCR/VLM 结果按 candidate + review gate 进入 evidence。

依赖策略：Docling 属于核心 parser 能力，计划纳入 requirements 或明确的 parser extra；真正执行前需要单独确认安装体积、Python 版本、Windows 可用性和许可证。

## 7. PEP Structure Resolver

PEP resolver 是 QT Wiki 的核心优势，负责把融合后的通用 extraction blocks 变成企业流程知识结构。

职责：

- heading detector：R 阶段、编号标题、中英混排标题、compact 编号标题。
- section tree repair：父子层级、late parent、level jump、rootless child。
- cleanup：TOC、document control header、页脚页码、History continuation row、title noise。
- semantic signals：stage、milestone、role、deliverable、BU、section number、template。
- table semantics：History table、responsibility matrix、deliverable table、template/output table。
- figure semantics：figure caption、workflow diagram candidate、visual review item。

输出：

- `Section` / `Fragment` / `TableData` / `FigureData`。
- `source_anchors`，包含 page、paragraph、line、bbox、table/cell、crop 等可用 anchors。
- `document.metadata.parser_fusion`，记录 provider contributions 和 fusion decisions。
- `document.metadata.structure_quality` 和 eval findings。

## 8. DOCX Fusion Plan

DOCX 采用 XML provider + Docling provider 的融合路线。

内部已有强项：XML 顺序稳定、Heading 样式可读、表格和段落能按文档顺序混合处理。

需要吸收的外部强项：Docling 的统一文档模型、table structure、layout label、可能的图表/图片理解。

准备做到：

- XML provider 保留段落、Heading style、numbering、table order。
- Docling provider 补 table layout、image/chart、可能的 reading order metadata。
- Fusion layer 统一 table/cell anchors：`table_id`、`row_index`、`column_index`、`cell_range`。
- PEP resolver 为职责矩阵、deliverable 表、template 表打 signals。
- Table chunks 可进入 RAG，引用能定位到表格/行/cell range。

## 9. OCR / Multimodal Visual Provider

OCR/multimodal 定位为 visual extraction provider，用于补足 text-layer 与 layout provider 难以覆盖的信息。

数据流：

```text
visual_review_items or Docling image blocks
  -> page/crop anchors
  -> OCR/VLM extraction
  -> VisualCandidate
  -> eval + human review gate
  -> accepted candidate enters canonical evidence
```

验收口径：

- 每个 visual candidate 都带 page/crop/bbox/backend/confidence。
- reviewed 或高置信且有 anchors 的 candidate 才进入 primary evidence。
- accepted candidate 必须保留 source_refs。
- answer package 只能消费 reviewed 或高置信且有 anchors 的 visual evidence。

## 10. Hybrid RAG Fusion Plan

RAG 采用内部 retriever fusion，吸收 RAGFlow、SurfSense、Open Notebook 的强策略并保留 QT retrieval contract。

```text
Retriever interface
  retrieve(question, chunks, source_scope, top_k) -> RetrievalResult

Retrievers
  RuleSectionRetriever      当前关键词 + signal baseline
  FullTextRetriever         BM25 / SQLite FTS / Tantivy 类
  VectorRetriever           Chroma / FAISS / Qdrant
  HybridRetriever           keyword + vector + RRF / weighted fusion
  RerankRetriever           stage/role/deliverable/source scope/BU coverage rerank
  GraphRetriever            后续基于真实 relation graph
```

外部吸收点：

- SurfSense：search space、hybrid semantic + full-text、hierarchical index、RRF、cited answer。
- RAGFlow：multiple recall、fused rerank、template chunking、citation visualization。
- Open Notebook：fine-grained context control、notebook source scope、chat/note 联动。

内部保留点：

- `RetrievalResult` 统一 contract。
- `AnswerEvidencePackage` 统一 evidence gate。
- `QuestionIntent` 和企业关键词归一。
- source scope 与 Session Source Base 对齐。

准备做到：

- 先抽象 retriever interface，当前 `retrieve_sections()` 变成 RuleSectionRetriever baseline。
- 增加 full-text index，用于章节号、模板名、角色、R/M 阶段、法规术语。
- 增加 vector index，用于自然语言语义问法。
- 增加 hybrid fusion，至少支持 RRF 或 deterministic weighted fusion。
- 增加 rerank policy，先规则 rerank，再评估模型 reranker。
- RetrievalResult 继续输出 strategy、source_scope、hits、coverage、trace。

## 11. Eval Gate

新能力必须被 eval gate 约束。Eval 不只比较谁赢，还要解释每个 provider 对最终结果贡献了什么。

新增 eval 类型：

| Eval | 目标 | 示例指标 |
| --- | --- | --- |
| Provider Contribution Eval | 评估 pypdf/docling/OCR 各自贡献 | matched_blocks、table_recovered、bbox_coverage、reading_order_improvement |
| Fusion Decision Eval | 检查 fusion 是否过度合并或错选 | duplicate_rate、conflict_count、low_confidence_decisions |
| Parser Quality Eval | 延续现有 parser quality | expected heading recall、section tree、noise、anchor coverage |
| Retrieval Backend Eval | 比较 rule/fulltext/vector/hybrid | Recall@K、MRR、citation hit、BU coverage |
| Answer Eval | 检查 groundedness | unsupported claim、missing citation、abstention correctness |

## 12. G9 Gate 计划

### G9-01 Parser Fusion Core Contract

- 目标：定义 ExtractionBlock、LayoutBlock、TableBlock、VisualCandidate、FusionDecision 和 parser_fusion metadata。
- 最小设计：先用纯 Python dataclass / dict contract，保持 canonical top-level schema 稳定。
- 验收：现有 parser 可在 metadata 中记录 provider/fusion trace，旧测试保持通过。

### G9-02 Docling Provider Integration

- 目标：把 Docling 作为内部 Python extraction provider 融入 Tool/parsers。
- 最小设计：docling provider 输出 blocks；fusion layer 将 Docling layout/table 信息合并进 PDF/DOCX parser。
- 验收：测试证明 Docling blocks 可为 TableData、bbox anchors、reading_order metadata 提供信息；canonical 仍由 fusion layer 统一产出。

### G9-03 PDF Fusion Pipeline

- 目标：把 pypdf fast text + Docling layout/table/OCR + PEP resolver 融成一个 PDF parser。
- 最小设计：保持 pypdf 和 PEP cleanup，吸收 Docling bbox/table/reading_order。
- 验收：CT / MI / XP PEP smoke 不退化；复杂表格和 layout metadata 增强可见。

### G9-04 DOCX Table/Layout Fusion

- 目标：把 DOCX XML 顺序和 Docling table/layout 信息融合。
- 最小设计：table/cell anchors、list level metadata、deliverable/role signals。
- 验收：DOCX 表格可以作为 table chunk 被检索，引用能定位到表格/行/cell range。

### G9-05 OCR / Multimodal Visual Provider

- 目标：把 visual_review_items 和 Docling image blocks 转成 OCR/VLM candidate 队列。
- 最小设计：page/crop anchors、candidate schema、review status、confidence gate。
- 验收：扫描件或 figure/table candidate 能生成 pending candidate，reviewed 或高置信且有 anchors 的候选才能进入 primary evidence。

### G9-06 Retriever Interface + Hybrid RAG

- 目标：让 retrieval backend 可插拔，同时保留统一 RetrievalResult。
- 最小设计：RuleSectionRetriever baseline、FullTextRetriever spike、VectorRetriever spike、Hybrid fusion。
- 验收：R2/PO、7.16、BU comparison、reference lookup 的 eval case 可比较 Recall@K / MRR / citation hit。

### G9-07 Fusion / Retrieval / Answer Eval 扩展

- 目标：让 provider fusion 和 hybrid RAG 均受 eval 约束。
- 最小设计：provider contribution eval、fusion decision eval、retrieval backend comparison eval、answer groundedness eval。
- 验收：unsupported claim、missing citation、wrong source scope、forbidden primary section、low-confidence fusion 都能进入 findings。

### G9-08 Session API Handoff

- 目标：为 v0.4 UI 提供真实 Tree、Graph、Chat flow 所需 API contract。
- 最小设计：Tree 来自 canonical sections/chunks，Graph 来自 structured relations / evidence relations，Chat 消费 AnswerEvidencePackage。
- 验收：G8 UI 不再需要静态 Tree/Graph mock。

## 13. 推荐执行顺序

1. G9-01 Parser Fusion Core Contract。
2. G9-02 Docling Provider Integration。
3. G9-03 PDF Fusion Pipeline。
4. G9-06 Retriever Interface + Hybrid RAG。
5. G9-05 OCR / Multimodal Visual Provider。
6. G9-04 DOCX Table/Layout Fusion。
7. G9-07 Fusion / Retrieval / Answer Eval 扩展。
8. G9-08 Session API Handoff。
9. 回到 G8：v0.4 UI/contract 修订、真实 Tree + Chat flow、Graph MVP。

排序理由：先统一 parser fusion contract，再把 Docling 能力直接吸收进 PDF/DOCX parser；等真实 extraction、layout、table 和 retrieval contract 稳定后，再打磨 UI，避免继续做静态占位。

## 14. 边界

Always：

- 外部能力以 provider 进入 QT Parser Core，不让 UI 或 answer 依赖外部 backend 字段。
- provider 输出必须记录 provider、anchors、confidence、metadata。
- fusion decisions 必须可解释。
- primary evidence 必须可追溯。
- 新 provider 或 retriever 必须有 eval case 或 comparison report。

Ask first：

- 新增重量级依赖，例如 Docling、Chroma、Qdrant、MinerU、VLM OCR 模型。
- 引入 Docker 服务、GPU/OCR 模型或大型本地模型。
- 改 canonical top-level schema 或持久化格式。

Guardrails：

- QT 主 contract 保持为 `CanonicalDocument` / `RetrievalResult` / `AnswerEvidencePackage`。
- OCR/VLM 输出以 candidate + review gate 管理。
- UI 通过 QT contract 使用 provider 增强结果。
- Eval finding 和质量门保留完整。

## 15. 验证命令

现有验证基线：

```powershell
Set-Location "QT-wiki"
..\.venv\Scripts\python.exe -m pytest
..\.venv\Scripts\python.exe -m compileall App Tool wiki tests
git diff --check
```

前端联动验证仍使用：

```powershell
Set-Location "QT-wiki\App\web"
npm run build
```

后续新增 provider fusion 后，需要补充专项命令，例如：

```powershell
..\.venv\Scripts\python.exe -m pytest tests/test_parser_fusion_contract.py tests/test_docling_provider.py tests/test_pdf_fusion_pipeline.py tests/test_hybrid_retrieval.py
```
