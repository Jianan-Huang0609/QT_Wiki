# Multi-input Parser + RAG Workflow 研究设计

更新时间：2026-06-10
状态：Research Draft
关联 PRD：[PRD-流程问答工作台.md](PRD-流程问答工作台.md)

## 1. 结论

底层能力应设计成 **workflow-first 的多输入文档解析与检索系统**。PEP PDF 是第一个验证样本，后续会持续接入 PDF、Excel、DOCX、PPTX、Markdown，以及可能的纯文本或网页导出内容。

推荐拆分为五层：

1. **Multi-input Parser Workflow**：确定性地接收文件、识别格式、抽取文本/表格/幻灯片/Markdown heading，输出 canonical document。
2. **Structure & Chapterization Layer**：按文档类型识别标题、目录、章节层级、表格区域、页码/段落/行列锚点。
3. **LLM Assist Layer**：只处理规则难以稳定覆盖的候选判断，例如标题归并、语义标签、章节摘要、低置信度结构候选。
4. **Parser / Retrieval Evals**：用样本文档和问题集持续核查解析稳定性、章节准确性、引用可追溯性、召回质量和回答 groundedness。
5. **Retrieval Strategy Matrix**：根据 source scope 选择全局 RAG、混合检索、单文档局部检索或直接读上下文。

关键产品判断：解析状态和 workflow 状态应由脚本层与 eval 规则计算，LLM 可以辅助产出候选与摘要，但不应由 agent 自行决定“解析成功/失败/可信”。这样系统更容易复现、回归测试和长期维护。

## 2. 当前代码基础

| 能力 | 当前状态 | 判断 |
| --- | --- | --- |
| 多格式入口 | `Tool/parsers/__init__.py` 支持 `.docx`、`.pdf`、`.pptx`、`.xlsx` | 可作为统一入口扩展 |
| Markdown | 当前 `SUPPORTED_SUFFIXES` 未包含 `.md` | 需要新增 markdown parser |
| Canonical contract | `Tool/contracts/canonical.py` 已有 Document / Section / Fragment / Table / Figure / anchors | 可复用并补 metadata |
| PDF | `Tool/parsers/pdf_parser.py` 使用 `pypdf`，能抽页级文本和页码 anchor | 需要增强章节化、页眉页脚清理、扫描件状态 |
| DOCX | `Tool/parsers/docx_parser.py` 能抽段落与表格 | 需要读取 heading 样式、编号标题、列表层级 |
| XLSX | `Tool/parsers/xlsx_parser.py` 按 sheet 生成 section，按行生成 fragment/table | 需要 table region/header detection 和 row/column anchors |
| PPTX | `Tool/parsers/pptx_parser.py` 按 slide 生成 section | 可作为讲义/培训材料入口，需提取备注/图表后续增强 |
| Parse pipeline | `Tool/pipelines/ingest.py`、`Tool/pipelines/parse.py` 已能入库并保存 parsed JSON | 可升级为 workflow step |
| QueryAgent | 当前基于 Wiki page index 召回 | 需要新增 section-first retrieval workflow |
| Evals | 当前有 parser 单测和 API 回归测试 | 需要建立 parser eval、retrieval eval、answer eval |

## 3. 设计原则

### 3.1 Workflow 优先

解析链路用明确步骤推进，每一步有输入、输出、状态和 evidence。

```text
Ingest
  -> Format Extract
  -> Normalize / Clean
  -> Structure Detection
  -> Optional LLM Assist
  -> Canonical Document
  -> Chunk Build
  -> Index Build
  -> Eval Report
  -> Session Retrieval / Answer
```

每一步写入 trace：

- 输入文件与 checksum。
- parser 名称和版本。
- 抽取数量：pages / sheets / slides / paragraphs / tables。
- section_count、fragment_count、table_count。
- low_confidence_items。
- eval summary。

### 3.2 LLM 作为受控辅助层

LLM 适合做：

- 低置信度标题候选归并。
- 目录项与正文 heading 对齐。
- 章节摘要。
- 角色、阶段、交付物、模板名的语义标签候选。
- 对复杂表格的表意说明。

LLM 输出进入 `candidates` 或 `metadata.assist`，由 workflow 按阈值、规则和 eval 接收。状态字段如 `parse_status`、`section_count`、`anchor coverage` 由脚本层计算。

### 3.3 Chapter-first / Section-first

所有格式尽量先重建结构，再做 chunk：

- PDF：TOC + numbered heading + page anchors。
- DOCX：heading style + numbering + paragraph/table order。
- Markdown：`#` heading 层级天然作为 section tree。
- PPTX：slide 作为一级 section，标题/备注/要点作为 fragments。
- XLSX：sheet/table region 作为 section，row/column/cell 作为 anchors。

Chunk 构建以 section 为边界，补充 overlap 和相邻片段，避免把跨章节内容混进同一 chunk。

## 4. Multi-input Parser 细分设计

### 4.1 Format Extractors

| 格式 | 第一层抽取 | 结构锚点 | 首版增强点 |
| --- | --- | --- | --- |
| PDF | 页级文本、段落、基础表格候选 | page、paragraph_index | heading detector、页眉页脚清理、扫描件检测 |
| DOCX | 段落、表格、样式、列表编号 | paragraph_index、table_index | heading style、编号层级、表格归属 section |
| XLSX | sheet、行、表格区域 | sheet、row_index、column、cell_range | 表头识别、区域切分、合并单元格说明 |
| PPTX | slide 文本、标题、要点 | slide/page、shape_index | speaker notes、图表 caption、slide type |
| Markdown | heading、paragraph、list、code/table block | heading_path、line_start、line_end | 新增 parser，天然 section tree |

### 4.2 Structure Detection

新增通用结构检测层，而不是把所有规则塞进各 parser。

建议模块：

```text
Tool/
  structure/
    __init__.py
    headings.py        # 编号标题、Markdown heading、DOCX heading style 统一归一
    cleanup.py         # 页眉页脚、重复噪音、目录点线清理
    tables.py          # xlsx/docx/pdf 表格区域与表头识别
    signals.py         # stage/role/deliverable/BU/keyword signals
```

`headings.py` 输出统一 `SectionCandidate`：

```json
{
  "candidate_id": "heading-001",
  "title": "5.3.2 Process Phase 2: Product Realization / 过程阶段 2：产品实现",
  "level": 3,
  "source": "body",
  "anchors": {"page": 15, "paragraph_index": 2},
  "confidence": 0.86,
  "reason": "numbered_heading_pattern"
}
```

### 4.3 Canonical Document 扩展建议

保持现有 contract 兼容，优先通过 `metadata` 增加信息：

```json
{
  "metadata": {
    "parser_version": "multi-input-v0.1",
    "structure_quality": {
      "section_confidence": 0.82,
      "anchor_coverage": 1.0,
      "table_coverage": 0.7,
      "low_confidence_count": 3
    },
    "document_signals": {
      "stages": ["R2", "M200"],
      "roles": ["Project Manager", "Product Manager"],
      "deliverables": ["QMP", "PMP"]
    }
  }
}
```

需要改变 contract 时再新增字段，先用兼容方式降低改造成本。

## 5. Script / LLM / Evals 分工

### 5.1 Script Layer

脚本层负责可复现和可测试的事实：

- 文件格式识别。
- checksum、manifest、source path。
- 文本、表格、行列、slide 抽取。
- heading / section candidate 规则识别。
- parse_status 计算。
- section/chunk/index 产物保存。
- eval report 生成。

### 5.2 LLM Assist Layer

LLM 层只处理可被验证的增强：

- 章节候选归并：把 TOC heading 和正文 heading 对齐。
- 语义标签：阶段、角色、交付物、流程活动。
- 章节摘要：给 retrieval rerank 和 UI 预览使用。
- 表格解释：把复杂表格变成可检索的自然语言说明。

LLM 输出必须包含 evidence：

```json
{
  "label": "R2 readiness",
  "evidence_fragment_ids": ["frag-120", "frag-121"],
  "confidence": 0.78,
  "needs_review": false
}
```

### 5.3 Eval Layer

Evals 分三类：

| Eval 类型 | 目标 | 指标 |
| --- | --- | --- |
| Parser Eval | 文档是否稳定解析成章节/片段/表格 | section recall、anchor coverage、table coverage、noise rate、parse_status accuracy |
| Retrieval Eval | 问题是否命中正确章节和证据 | Recall@K、MRR、BU coverage、citation hit rate |
| Answer Eval | 回答是否基于证据、引用完整、知道缺口 | groundedness、citation completeness、abstention correctness、format compliance |

首版 eval 不需要复杂平台，先用 repo-local fixture：

```text
tests/fixtures/evals/
  parser_cases.json
  retrieval_cases.json
  answer_cases.json
Tool/evals/
  parser_eval.py
  retrieval_eval.py
  answer_eval.py
```

Eval case 示例：

```json
{
  "case_id": "pep-r2-ct-mi-xp",
  "question": "R2阶段我作为PO应该准备什么？",
  "source_scope": {"mode": "all_sources"},
  "expected_terms": ["R2", "M200", "Project Manager", "Product Manager", "QMP"],
  "expected_documents_any": ["CT PEP AND 308 11.pdf", "MI PEP AND 308 11.pdf", "XP PEP AND 308 11.pdf"],
  "min_citation_count": 3
}
```

## 6. Retrieval Strategy Matrix

### 6.1 检索模式

| 场景 | 推荐策略 | 说明 |
| --- | --- | --- |
| 全局很多文档 | Hybrid RAG：metadata filter + keyword + vector + rerank | 适合用户不知道答案在哪，重点做覆盖度和去噪 |
| 多文档 Selected Docs | Scoped hybrid retrieval | 只在选中文档内召回，减少跨 BU 混淆 |
| 单个长文档 | In-document section retrieval | 先用目录/章节树定位，再取局部上下文 |
| 单个短文档 | Direct read | 文档或选中章节足够短时，LLM 直接读完整上下文 |
| Selected Section | Direct section read | 直接读取该章节和相邻片段，保留引用 |
| Excel 表格 | Table-aware retrieval | 按 sheet/table/row/column 检索，引用到行列或 cell range |
| Markdown | Heading-path retrieval | 按 heading path 和段落块检索，引用到 line range |

### 6.2 全局 RAG

适合 Knowledge Base 文档很多的情况。

```text
Question
  -> query normalization
  -> metadata filter: source_type / BU / doc_type / date / selected libraries
  -> lexical retrieval: keyword, heading, aliases, stage/role/deliverable signals
  -> vector retrieval: semantic chunks
  -> rerank: reranker or LLM-assisted scoring
  -> evidence coverage: doc/BU/source coverage
  -> answer package
```

### 6.3 局部直读

适合单文档或已选章节。

判断条件：

- 选中内容低于 context budget。
- section_count 清楚，用户明确选择范围。
- 问题需要顺序理解，而不是跨库召回。

输出仍然走同一个 AnswerPackage，Reference 不降级。

### 6.4 混合策略选择器

workflow 根据 scope 选择策略：

```text
if selected_section:
  direct_section_read
elif single_doc and content_tokens <= budget:
  direct_doc_read
elif source_scope.mode == "selected_docs":
  scoped_hybrid_retrieval
elif source_scope.mode == "all_sources":
  global_hybrid_retrieval
else:
  session_upload_retrieval
```

策略选择由 workflow 规则决定，并写入 trace；LLM 可以解释 trace，但不负责选择状态。

## 7. Workflow / Tool 包装建议

### 7.1 Repo-local 模块

建议先按现有 `Tool` 风格扩展：

```text
Tool/
  parsers/
    markdown_parser.py
  structure/
    headings.py
    cleanup.py
    tables.py
    signals.py
  chunking/
    section_chunks.py
  retrieval/
    section_index.py
    hybrid_search.py
    strategy.py
  evals/
    parser_eval.py
    retrieval_eval.py
    answer_eval.py
  workflows/
    document_parse.py
    session_rag.py
```

### 7.2 Public Tool Functions

```python
parse_document_workflow(input_path, *, use_llm_assist=False) -> ParseWorkflowResult
build_section_chunks(document_ids=None, *, scope="knowledge_base") -> ChunkBuildResult
build_or_update_retrieval_index(chunks, *, index_dir=None) -> IndexBuildResult
retrieve_for_session(question, source_scope, *, strategy="auto") -> RetrievalResult
answer_with_evidence(question, retrieval_result, *, use_llm=True) -> AnswerPackage
run_parser_eval(case_file) -> EvalReport
run_retrieval_eval(case_file) -> EvalReport
```

### 7.3 CLI

```bash
python -m Tool.workflows.document_parse --input ../PEP --eval
python -m Tool.retrieval.section_index build --scope knowledge-base
python -m Tool.workflows.session_rag query --question "R2阶段我作为PO应该做什么" --scope all
python -m Tool.evals.parser_eval --cases tests/fixtures/evals/parser_cases.json
python -m Tool.evals.retrieval_eval --cases tests/fixtures/evals/retrieval_cases.json
```

### 7.4 FastAPI

Session MVP 可以先扩展现有 `/chat/query`，后续再拆专用 endpoints。

建议请求：

```json
{
  "question": "R2阶段我作为PO应该做什么",
  "source_scope": {
    "mode": "selected_docs",
    "document_ids": ["ct-pep", "mi-pep", "xp-pep"],
    "session_upload_ids": []
  },
  "retrieval_strategy": "auto",
  "use_llm": true,
  "top_k_chunks": 8
}
```

建议响应：

```json
{
  "answer": "...",
  "strategy_used": "scoped_hybrid_retrieval",
  "source_scope": {},
  "evidence_coverage": {"documents": 3, "bus": ["CT", "MI", "XP"]},
  "citations": [],
  "trace": []
}
```

## 8. 实施顺序

### Step 1：Multi-input Parser Contract

- 扩展 `SUPPORTED_SUFFIXES` 支持 Markdown。
- 设计 `ParseWorkflowResult`、`StructureQuality`、`SectionCandidate`。
- 将 parser 输出统一走 structure layer。
- 保持现有 canonical JSON 兼容。

### Step 2：Chapterization MVP

- PDF：编号 heading、目录点线、页眉页脚清理。
- DOCX：heading style 与编号标题。
- Markdown：`#` heading 到 section tree。
- XLSX：sheet/table region 到 section。
- PPTX：slide title 到 section。

### Step 3：Parser Eval MVP

- 建立 parser cases。
- 核查 section_count、expected headings、anchor coverage、noise rate。
- 将三份 PEP PDF 作为第一批真实样本。

### Step 4：Section Chunk + Retrieval MVP

- 从 canonical sections/fragments 生成 chunks。
- 建立 keyword + signal retrieval。
- 支持 source_scope filter。

### Step 5：Strategy Matrix 接入 Session

- Selected Docs -> scoped retrieval。
- All Sources -> global hybrid retrieval。
- Selected Section / short doc -> direct read。
- Excel -> table-aware retrieval。

### Step 6：Answer + Eval

- 输出统一 AnswerPackage。
- 建立 retrieval eval 和 answer eval。
- 将 eval report 写入 workflow trace。

## 9. 风险与防护

| 风险 | 防护 |
| --- | --- |
| 不同格式章节结构差异大 | 先抽象 SectionCandidate，再按格式映射到 CanonicalDocument。 |
| PDF 可抽文本但章节识别弱 | TOC/body 双源 heading detector + 页眉页脚清理 + parser eval。 |
| Excel 被当成普通文本导致引用弱 | table-aware chunk，引用 sheet/row/column/cell_range。 |
| Markdown 还未接入 | 新增 markdown_parser，直接使用 heading 和 line anchors。 |
| LLM 输出不稳定 | LLM 只产候选与摘要，workflow 用阈值、evidence 和 eval 接收。 |
| 全局 RAG 召回噪音大 | metadata filter + hybrid retrieval + rerank + evidence coverage。 |
| 单文档直接读超上下文 | workflow 先估算 token，超出后切换 in-document retrieval。 |
| 引用不可追溯 | 每个 chunk 必须保留 document_id、section_id、anchor、quote。 |

## 10. 建议验收标准

- `.pdf/.docx/.xlsx/.pptx/.md` 都能进入统一 parse workflow。
- 每个 parsed document 都输出 sections、fragments、anchors 和 structure_quality。
- 三份 PEP PDF 的 section_count 从 0 提升到可用章节树。
- Markdown 文档按 heading 输出 section tree 和 line anchors。
- Excel 能引用到 sheet + row 或 cell range。
- Parser eval 能报告 expected headings、anchor coverage、noise rate。
- Retrieval eval 覆盖全局多文档、selected docs、单文档、selected section、Excel table 五类问题。
- Session RAG trace 明确记录 strategy_used，前端只消费稳定 AnswerPackage。