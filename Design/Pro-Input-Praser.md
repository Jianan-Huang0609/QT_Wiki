# Pro-Input-Praser

更新时间：2026-06-11  
状态：G9 Review Summary + Working Notes  
关联计划：[Parser-Workflow-Evals-实施计划.md](Parser-Workflow-Evals-实施计划.md)  
关联报告：[Gate3-PEP-PDF-Review.md](Gate3-PEP-PDF-Review.md)

> 文件名沿用当前命名 `Pro-Input-Praser`。本文记录 PEP parser 开发过程中的经验、难点和对应方法，并在 G9 后补充 QT Parser Core / provider fusion / eval loop 的主线总结，后续可沉淀为 Parser / OCR / Multimodal / RAG 的工程规范。

## 1. 核心目标

Pro Input Parser 的目标是把公司流程文档变成可被 RAG 和主 Chat 可信消费的结构化输入：

- 保留原文证据：每个 fragment / table / figure 都要有 page、line 或 caption anchor。
- 建出章节骨架：章节树要尽量贴近原文目录和正文层级，方便回答“R2 阶段 PO 要做什么”。
- 分离候选与事实：parser 可以生成 table / figure / multimodal 候选，人工 review 或 eval 通过后再进入高置信知识层。
- 支持多输出：Markdown、Mermaid、Reference 表、BU diff、training 交互都复用同一套 canonical document。

运行原则：固定 workflow 做骨架，规则 parser 做第一层确定性抽取，LLM / 多模态工具做补强，Evals 做免疫系统，Human Review 做最后关口。

## 2. 输入类型判断

| 输入状态 | 首选处理 | 质量风险 | Review 重点 |
| --- | --- | --- | --- |
| PDF 有可用文本层 | 文本 parser + heading detector + anchors | 断行、页眉页脚、目录污染、标题截断 | section tree、quote 是否来自正文 |
| PDF 文本表格 | table candidate extractor | 表格跨页、合并单元格、列错位 | 表头、行数、关键字段 |
| 扫描版 PDF 或图片化文字 | OCR first，再进入文本 parser | OCR 错字、漏行、页序错误 | 抽样比对原图 |
| 流程图、V-model、复杂版式 | caption/region candidate + multimodal analysis | 箭头关系、布局语义、框图层级 | 多模态输出是否有 crop/page 证据 |
| 复杂表格截图 | OCR/table extractor + multimodal double check | 跨列关系和视觉分组 | 表头层级、行列语义 |
| DOCX/PPTX/XLSX | 原生结构优先 | 样式不规范、文本框顺序 | 原生对象顺序和章节锚点 |

经验判断：OCR 解决“看不见文字”的问题；多模态解决“看不懂布局/图形关系”的问题；LLM 负责解释和候选补全，输出必须带 source evidence。

## 3. 本轮 CT PEP 暴露的问题

### 3.1 TOC 污染正文章节

现象：CT PEP 前置 Content 页的 `7.16 COUNTRY-SPECIFIC APPROVALS... / 特定国家核准（法规核准计划）` 被抽成正式 section，并且长标题在目录页跨页断成两段。

方法：

- 先做 line-level TOC dot leader 过滤，处理 `...... 41` 这类目录点线。
- 再做 page-level TOC 过滤，处理 pypdf 把点线或后半段拆掉的情况。
- 对前 10 页的 `Content / Contents / Table of contents / 目录` 标记、目录点线密度和尾部页码条目做综合判断。

当前结果：CT 前置目录不再生成 `6.4 / 7.16` rootless section；正文 `7.16` 仍保留在 page 49。

### 3.2 History 表格污染章节树

现象：`0 History / 修改历史` 下方的 `1 All 01...`、`Change content...`、续页 `7. Chapter...` 被当成 section，污染 RAG。

方法：

- 识别 `Nr. Page Version Change description CR No.` 表头。
- 把 `n All xx ...` 行抽成 `TableData`，table_type 标记为 `document_history`。
- 在 History 表格区域过滤行内容，避免它们进入 section detector。
- 对 Purpose 前的 `n. Chapter...` / `n. Appendix...` 续页行加窄规则过滤。

当前结果：CT / MI / XP 都生成至少一个 History table candidate；CT 开头从 `0 History` 直接进入 `1 Purpose`，History 行不再冒充流程章节。

### 3.3 Figure 只能看到 caption

现象：CT page 15 的 V-model 在文本层只有 `Figure 1/图 1: V-model/V 字型模式`，图内框、箭头和阶段关系没有文本结构。

方法：

- 先抽 `FigureData` caption candidate，保留 page、caption、source。
- 后续增加 page crop / figure region crop，把图像区域交给 multimodal model 生成候选描述。
- 多模态结果只作为 candidate，必须带 page/crop/figure_id evidence，并进入 P1-03 / L1-01 / human review。

当前结果：CT page 15 生成 `fig-1`，CT page 20 生成 `fig-2`；MI / XP 也能生成 figure caption candidates。

### 3.4 正文标题存在续行断裂

现象：CT 正文 page 49 的 `7.16 Country-specific approvals... / 特定国家核准（法规核准计划）` 在 pypdf 文本层被拆成两行，heading 行只到 `法规核准`，下一行单独出现 `计划）`。

方法：

- 在行预处理阶段识别 heading 行括号未闭合、下一行是短闭合续行的情况。
- 将短续行拼回 heading，再进入 section detector。
- 如果目标文字完全不存在于文本层，再进入 OCR 或 multimodal crop 补证。

当前结果：CT 正文 `7.16 Country-specific approvals (regulatory approval plan) / 特定国家核准（法规核准计划）` 已能完整进入 section title。

## 4. Parser 工作流方法

1. Raw input intake  
记录文件名、checksum、页数、格式、文本层可用性。

2. Deterministic extraction  
先跑格式专属 parser：PDF text、DOCX XML、Markdown heading/table、XLSX sheets、PPTX slides。

3. Structural cleanup  
清理页眉页脚、页码、目录点线、Content 前置页、History 表格噪音。

4. Canonical mapping  
统一输出 `sections`、`fragments`、`tables`、`figures`、`source_anchors`、`parse_status`。

5. Parser evals  
P1 检查抓取完整性，P2 检查章节树和噪音，P3 检查 source anchors，L1 检查 LLM 证据。

6. Review artifact  
生成 section tree / key section / table / figure / review_items 报告，让人工快速判断是否进入 Retrieval。

7. Section chunk / retrieval gate  
通过后生成 section-first chunks，按 source scope 做 deterministic retrieval，并用 retrieval cases 检查 expected docs / sections / terms。

8. Answer-ready gate  
Retrieval 只交付 evidence package；进入用户回答前还要做 answer groundedness eval，确认每个关键事实有 citation，证据不足时能明确说明缺口。

## 5. Evals 映射

| Eval | 当前关注 | 典型触发 |
| --- | --- | --- |
| P1-02 Table | 表格候选完整性 | empty rows、missing anchors、irregular rows |
| P1-03 Figure | 图片/图注候选完整性 | figure 无 caption 或无 page anchor |
| P2-01 Section Tree | 层级跳转、孤立子章节 | 目录残留、parent 错层 |
| P2-02 Fragment Drift | fragment 和 section path 不一致 | heading_path 漂移 |
| P2-03 Noise Title | 页眉页脚/TOC/文控噪音 | document control、page of、dot leader |
| P3-01 Anchors | source evidence 覆盖率 | fragment/table/figure 缺 anchor |
| L1-01 LLM Evidence | LLM 输出证据约束 | LLM 生成内容缺 source_refs |
| C1-01 Chunk Boundary | chunk 不跨无关章节 | section chunk 混入其他章节 |
| C1-02 Chunk Citation | chunk 保留 file / section / anchor / quote | source_refs 缺失 |
| R1-01 Retrieval | retrieval 命中 expected doc / section / terms | R2 问题命中 History/template change |

建议新增：

- P1-04 Expected Section Path：指定关键章节必须命中，例如 Purpose、Reference、Process、R2、7.16。
- P1-05 Visual Completeness：figure caption 存在但图像区域未分析时提示 multimodal review。当前已实现 review queue MVP。
- A1-01 Answer Groundedness：回答中的关键事实必须能回到 retrieval evidence。

## 6. Human Review 清单

人工 review 时优先看这些点：

- 章节树第一屏：是否从 History / Purpose / Reference 合理开始，Content 页是否混入。
- 关键章节：Purpose、Reference、Definitions、Process & Requirement、System phases、R2/R3、Country-specific approvals。
- Reference 样例：quote 是否来自正文，heading_path 是否和 section 匹配，page 是否正确。
- History table：版本行是否进入 `tables`，是否还污染 sections。
- Figures：V-model / process structure 是否只有 caption，是否需要 crop + multimodal。
- 双语标题：中文是否缺字或错位，尤其括号内说明和法规术语。
- BU diff：比较前先确认 CT / MI / XP 的章节粒度一致，否则 diff 会比较到 History 或模板变更。

## 7. 下一步实现建议（G9 后）

- 进入 G9 集中 review：核查 provider fusion metadata、visual candidate gate、retriever backend comparison、answer grounding findings 和 `/api/session/handoff/{document_id}` payload。
- 回到 G8 v0.4 UI/contract：左侧 Tree / Graph / Source Base 消费真实 handoff JSON，中间 Chat 消费 retrieval + answer evidence，右侧 Note 引用 citation excerpts。
- 增加 PDF figure crop pipeline：按 caption page 生成截图候选，关联 `figure_id`、page、bbox、crop_ref。
- 接入真实 OCR/VLM backend：沿用 G9-05 `VisualCandidate` schema，把扫描页、图片化表格、流程图说明作为 pending / reviewed / accepted 候选。
- 增加 table extractor 扩展：覆盖职责矩阵、deliverable 表、checklist 和跨页表，并继续输出 table/cell anchors。
- 增加 BU 对齐层：先做章节 path mapping，再做 CT / MI / XP 差异展示。

## 8. 当前 CT/MI/XP Smoke 结论

本轮 parser + chunk/retrieval 修复后：

- CT：`tables=1`，`figures=2`，`chunks=146`，`visual_review_items=2`；Content / History 污染已明显降低，7.16 双语标题已拼回完整；仍有 P2-01 level jump warning。
- MI：`tables=1`，`figures=1`，`chunks=93`，`visual_review_items=1`；主体从 History 后进入 Purpose / Reference；仍有 process phase parent warning。
- XP：`tables=1`，`figures=5`，`chunks=163`，`visual_review_items=5`；前置 History 污染已降低；仍有多处 level jump warning。

真实 retrieval smoke 结果：R2 查询已优先命中 R2 正文/裁剪规则，CT 7.16 regulatory approval plan 在 `selected_docs=ct-pep` scope 中排第一；两条 retrieval eval cases 当前 `recall_at_k=1.0`。

这说明 Gate 4/5 已经有可验证 MVP。G9 之后，底座已经具备 Answer Evidence Package、groundedness eval 和 session handoff contract；下一步重点是把真实 crop/OCR/VLM 执行、UI review 面板和 G8 三栏工作台接到这套 contract 上。

## 9. G9 主线总结：能力、输出与闭环设计

G9 的核心成果是把 QT Wiki parser 从“单一路径解析器”升级为“provider fusion + eval-gated workflow”。它现在能接收不同 extraction provider 的中间结果，用统一 JSON 记录每个 provider 的贡献、冲突、置信度和证据 anchor，再让 evals 把这些核查点变成 findings，供人工 review、LLM 二轮修正或下一次 workflow 决策使用。

一句话总结：G9 让系统从“解析完得到一份文档”升级为“解析时保留可审过程，检索和回答时继续带着证据链前进”。

### 9.1 G9 已完成的能力板块

| Gate | 能力板块 | 核心输出 | 当前效果 |
| --- | --- | --- | --- |
| G9-01 | Parser Fusion Core Contract | `ExtractionBlock`、`LayoutBlock`、`TableBlock`、`VisualCandidate`、`FusionDecision`、`parser_fusion` metadata | 所有 parser 都能在 metadata 中记录 provider/fusion trace，旧 canonical schema 保持稳定。 |
| G9-02 | Docling Provider Integration | `docling_provider_extraction` metadata、Docling-like text/layout/table/picture blocks | Docling 作为可选 provider 接入，采用 lazy import + injectable converter，暂不增加 requirements。 |
| G9-03 | PDF Fusion Pipeline | `pdf_provider_fusion` metadata | pypdf fast text 继续保留 PEP cleanup 经验，Docling layout/table/OCR 输出可补 bbox、reading_order 和 table candidate。 |
| G9-04 | DOCX Table/Layout Fusion | `docx_provider_fusion` metadata、table/cell anchors | DOCX XML 顺序与 Docling table/layout 合并；table chunk 可引用 `tbl.1 R1C1:R2C2`，并输出 role/deliverable signals。 |
| G9-05 | OCR / Multimodal Visual Provider | `VisualCandidate` queue、primary visual candidate gate | figure/table/image 候选保留 page/bbox/crop/source_refs；reviewed/accepted 或高置信且有 anchor 的候选才能成为 primary evidence。 |
| G9-06 | Retriever Interface + Hybrid RAG | `RuleSectionRetriever`、`FullTextRetriever`、`VectorRetriever`、`HybridRetriever`、统一 `RetrievalResult` | 检索 backend 可插拔，rule/full-text/vector/hybrid 统一输出 evidence coverage、hits、trace；hybrid 使用 deterministic RRF。 |
| G9-07 | Fusion / Retrieval / Answer Eval Extensions | `evaluate_parser_fusion_metadata()`、`compare_retrieval_backends()`、`evaluate_answer_grounding()` | Eval 可以报告 provider contribution、low-confidence fusion、backend miss、missing citation、unsupported claims 和 missing evidence 未提示。 |
| G9-08 | Session API Handoff | `session-handoff-v0.1` payload | UI 一次拿到 source summary、真实 tree、chunk/signal graph seeds、retrieval preview、chat contract 和 quality gates。 |

最终验证结果：`compileall` 通过，`pytest` 为 `135 passed, 1 warning`，`git diff --check` 通过。唯一 warning 是 FastAPI TestClient / Starlette 的既有 deprecation warning。

### 9.2 当前系统已经具备的能力

- 多 provider 抽取：pypdf fast text、DOCX XML、Docling-like layout/table/OCR、OCR/VLM visual candidate 都有统一中间表示。
- 稳定 canonical 输出：下游继续消费 `CanonicalDocument`、`SectionChunk`、`RetrievalResult`、`AnswerEvidencePackage`，provider backend 字段不会直接泄漏到 UI 和 Chat 主路径。
- 可审 parser 过程：`parser_fusion` 记录 providers、provider roles、block counts、sample blocks、visual candidates 和 fusion decisions。
- 表格可引用：DOCX table anchors 已包含 table index、cell range、row count、column count，chunk anchor 可定位到 `tbl.1 R1C1:R2C2`。
- 视觉候选可控：图像/流程图/截图表格先作为 `VisualCandidate`，带 page/bbox/crop_ref/review_status/confidence，再通过 gate 进入 primary evidence。
- 检索 backend 可替换：同一个 retrieval eval case 可以跑 rule、full-text、vector、hybrid，比较 Recall@K 和 miss details。
- 回答前证据包：retrieval hits 会进入 `AnswerEvidencePackage`，过滤 History/template change 与缺 source_refs hit，并保留 evidence_id、section、anchor、quote。
- UI handoff 可用：G8 三栏 UI 可以直接从 `/api/session/handoff/{document_id}` 读取 Tree、Graph seeds、retrieval preview、chat request/answer contract 和 quality gates。

### 9.3 抓取生成时拿到的核心 JSON

G9 之后，解析不是只看最终文本，而是看一串 contract。最重要的 JSON 有四类。

#### 9.3.1 `parser_fusion`

`parser_fusion` 放在 canonical metadata / parse workflow 里，回答“这份文档是哪些 provider 一起抓的、各自贡献了什么、融合时做过哪些决定”。

```json
{
	"schema_version": "parser-fusion-v0.1",
	"fusion_mode": "pdf_provider_fusion",
	"providers": ["pypdf_fast_text", "docling"],
	"provider_roles": {
		"pypdf_fast_text": "fast_text",
		"docling": "layout_table_ocr"
	},
	"counts": {
		"extraction_blocks": 146,
		"layout_blocks": 32,
		"table_blocks": 1,
		"visual_candidates": 2,
		"fusion_decisions": 18
	},
	"canonical_output": {
		"sections": 128,
		"fragments": 146,
		"tables": 1,
		"figures": 2,
		"source_anchors": 149
	},
	"samples": {
		"extraction_blocks": [],
		"layout_blocks": [],
		"table_blocks": []
	},
	"visual_candidates": [],
	"fusion_decisions": [
		{
			"decision_id": "fusion-p12-heading-r2",
			"decision_type": "merge_blocks",
			"selected_block_ids": ["pdf-pypdf-p12-b03", "docling-p12-layout-07"],
			"reason": "pypdf text matched normalized heading; docling supplied bbox and reading_order",
			"confidence": 0.93,
			"output_target": "section_candidate"
		}
	]
}
```

阅读顺序：先看 `schema_version` 和 `fusion_mode`，确认输出属于哪条融合路径；再看 `providers` / `provider_roles`，确认 pypdf、DOCX XML、Docling、OCR/VLM 是否参与；接着看 `counts` 和 `canonical_output`，确认 provider block 是否真正转成 canonical sections/tables/figures；最后看 `fusion_decisions`，核查低置信或冲突的合并决策。

#### 9.3.2 `VisualCandidate`

`VisualCandidate` 是“图像/截图/流程图/扫描页的候选事实”。它的设计重点是先保留证据，不急着把视觉描述当成事实。

```json
{
	"candidate_id": "visual-ct-p15-fig-1",
	"provider": "vlm",
	"candidate_type": "figure_description",
	"text": "The figure describes the V-model flow and phase relationship.",
	"anchors": {
		"page": 15,
		"bbox": [80, 180, 500, 430],
		"crop_ref": "output/crops/ct-p15-fig-1.png"
	},
	"confidence": 0.76,
	"review_status": "pending_review",
	"metadata": {
		"source_refs": [
			{"document_id": "ct-pep", "figure_id": "fig-1", "anchor_label": "p.15"}
		]
	}
}
```

Primary gate 的规则是：候选需要有 page，并且有 bbox 或 crop_ref；同时需要 `review_status` 为 reviewed/accepted/auto_accepted，或者 confidence 达到高置信阈值。这样可以让 OCR/VLM 帮忙看复杂图，又保留“视觉内容需要证据和 review”的边界。

#### 9.3.3 `RetrievalResult` 与 `AnswerEvidencePackage`

Retrieval 的职责是找证据，AnswerEvidencePackage 的职责是把证据整理成 LLM 可以安全消费的包。

```json
{
	"question": "R2 阶段 PO 要准备什么？",
	"strategy_used": "hybrid_retrieval",
	"source_scope": {
		"mode": "selected_docs",
		"document_ids": ["ct-pep"]
	},
	"hits": [
		{
			"chunk": {
				"chunk_id": "chunk-ct-r2-001",
				"document_id": "ct-pep",
				"section_id": "sec-r2",
				"section_title": "R2 Planning",
				"chunk_type": "section",
				"quote": "...",
				"source_refs": [
					{"document_id": "ct-pep", "section_id": "sec-r2", "anchor_label": "p.18", "quote": "..."}
				]
			},
			"score": 98.25,
			"matched_terms": ["R2", "Product Owner"]
		}
	],
	"evidence_coverage": {"hit_count": 1},
	"trace": ["hybrid retriever fanout: rule_section, full_text, vector", "rrf fusion combined backend hits"]
}
```

```json
{
	"question": "R2 阶段 PO 要准备什么？",
	"intent": {
		"intent_type": "role_action_guidance",
		"normalized_terms": {
			"stage": ["R2"],
			"role": ["Product Owner"],
			"deliverable": [],
			"bu": [],
			"section": []
		},
		"requires_abstention_check": true
	},
	"source_scope": {"mode": "selected_docs", "document_ids": ["ct-pep"]},
	"strategy_used": "hybrid_retrieval",
	"evidence_items": [
		{
			"evidence_id": "ev-1",
			"document_id": "ct-pep",
			"section_id": "sec-r2",
			"section_title": "R2 Planning",
			"anchor_label": "p.18",
			"quote": "...",
			"supports": ["stage:R2", "role:Product Owner"]
		}
	],
	"missing_evidence": [],
	"trace": ["answer evidence package built"]
}
```

LLM 写答案时应使用 `evidence_items` 里的 `evidence_id` 或 `anchor_label` 做 citation；如果 `missing_evidence` 有内容，答案要明确提示证据缺口。

#### 9.3.4 `session-handoff-v0.1`

`/api/session/handoff/{document_id}` 是 G9 给 G8 UI 的聚合 contract。它把解析、章节、chunk、检索、chat 和质量门整理成一次可消费 payload。

```json
{
	"schema_version": "session-handoff-v0.1",
	"document_id": "ct-pep",
	"source": {
		"document_id": "ct-pep",
		"parse_status": "parsed",
		"section_count": 128,
		"fragment_count": 146,
		"table_count": 1,
		"figure_count": 2,
		"chunk_count": 146
	},
	"tree": {
		"root_id": "doc-ct-pep",
		"items": []
	},
	"graph": {
		"nodes": [],
		"edges": []
	},
	"retrieval": {
		"available_retrievers": ["rule_section", "full_text", "vector", "hybrid"],
		"default_retriever": "hybrid",
		"preview_chunks": []
	},
	"chat": {
		"request_contract": {
			"question": "string",
			"source_scope": {"mode": "selected_docs", "document_ids": ["ct-pep"]},
			"retriever": "hybrid",
			"top_k": 8
		},
		"answer_contract": {
			"requires_citations": true,
			"evidence_package": "AnswerEvidencePackage",
			"citation_fields": ["document_id", "section_id", "anchor_label", "quote"],
			"quality_gates": ["missing_citation", "unsupported_claim", "missing_evidence"]
		}
	},
	"quality": {
		"parse_status": "parsed",
		"eval_summary": {"pass": 0, "warn": 0, "fail": 0, "na": 0},
		"review_items": [],
		"visual_review_items": [],
		"parser_fusion": {}
	}
}
```

UI 接入时，左侧 Tree 消费 `tree.items`，Graph 消费 `graph.nodes/edges`，Source 状态消费 `source` 和 `quality.parse_status`，Chat composer 使用 `chat.request_contract`，answer/citation 渲染遵守 `chat.answer_contract`。

### 9.4 Eval 如何把 JSON 变成核查点

G9 的 eval 不是单纯给一个总分，而是把 JSON 中的风险转成可操作 findings。

| JSON 来源 | Eval | 核查点 | Finding | 下一轮动作 |
| --- | --- | --- | --- | --- |
| `parser_fusion.providers` / `fusion_decisions` | `evaluate_parser_fusion_metadata()` | provider 是否记录、低置信 fusion decision 是否出现、visual candidate 是否有 anchor | `F1-01`、`F2-01` | 调整 provider 输出、收紧 block matching、把低置信候选送 human review。 |
| `CanonicalDocument` / `parse_workflow` | parser quality eval | expected heading、section tree、noise title、anchor coverage、table/figure risk、LLM source_refs | `P1/P2/P3/L1` | 修 parser cleanup、补 source anchor、把复杂 table/figure 送 visual review。 |
| `RetrievalResult` | `evaluate_retrieval_cases()` | expected document、expected section、expected term、forbidden primary section | `R1-01` | 调整 chunk signals、source scope、rerank、history downrank。 |
| 多个 retrieval backend report | `compare_retrieval_backends()` | rule/full-text/vector/hybrid 的 Recall@K 和 fail count | `R2-01` | 选择默认 backend、调整 hybrid RRF、补 full-text/vector 特征。 |
| `AnswerEvidencePackage` + answer text | `evaluate_answer_grounding()` | answer 是否引用 primary evidence、是否无证据作答、缺 evidence 时是否提示不确定 | `A1-01`、`A2-01`、`A3-01` | 让 LLM 带 citation 重写答案、触发补检索、输出证据缺口。 |

这套设计的关键是：eval 读取结构化 JSON，而不是只读 LLM 的自然语言解释。这样每个 warning/fail 都能定位到 provider、block、chunk、evidence 或 answer contract。

### 9.5 LLM 如何凭核查点进入下一轮

G9 形成的是一个“小循环”：每轮 workflow 都产出 JSON，每个 JSON 都被 eval 检查，LLM 或规则节点只围绕 findings 做下一步。

```text
1. Parse / Extract
	 文件进入 parser，生成 canonical document、parser_fusion、review_items、visual_review_items。

2. Eval / Gate
	 parser quality、fusion eval、retrieval eval、answer eval 读取 JSON，输出 findings。

3. Classify Findings
	 workflow 把 findings 分成 structure、anchor、visual、retrieval、answer 五类。

4. Targeted Repair
	 规则节点修可确定问题，例如 TOC、History、heading continuation、source_scope filter。
	 LLM 节点处理解释性问题，例如把 low-confidence visual candidate 总结成人审问题，或按 evidence_id 重写答案。

5. Re-run Narrow Slice
	 只重跑受影响的 parser/retriever/answer eval，确认 findings 从 fail/warn 变成 pass 或进入 human review。

6. Human Review
	 对视觉内容、复杂表格、低置信 fusion、流程合规答案进行最终确认。
```

典型例子：

- `P2-03 noise title`：说明目录/页眉/History 噪音进入 section tree。下一轮优先修 deterministic cleanup，再重跑 parser eval。
- `F2-01 low-confidence fusion decision`：说明 pypdf 和 Docling block 对齐置信度低。下一轮检查 selected_block_ids、page/bbox/text match，必要时把候选送 review。
- `R2-01 backend miss`：说明某个检索 backend 没命中 expected section。下一轮比较 rule/full-text/vector/hybrid 的 top hits，调整 signals、rerank 或默认 backend。
- `A1-01 missing citation`：说明答案没有引用 primary evidence。下一轮要求 LLM 使用 `ev-1` / `anchor_label` 重写，并保持所有关键事实有 citation。
- `A3-01 missing evidence without uncertainty`：说明证据包已经标记缺口，但答案没有提醒。下一轮答案要把“证据不足 / 缺少哪个 source scope”写清楚。

### 9.6 这套框架的设计原则

- Stable contract first：下游只依赖 QT 自己的 `CanonicalDocument`、`SectionChunk`、`RetrievalResult`、`AnswerEvidencePackage` 和 `session-handoff-v0.1`。
- Provider as capability layer：pypdf、DOCX XML、Docling、OCR/VLM 都是 provider，负责贡献证据；最终事实由 fusion + resolver + eval gate 共同确认。
- Candidate before fact：table、figure、visual、LLM 解释先进入 candidate/review 队列，通过 gate 后再成为 primary evidence。
- Anchor first：每个 fragment/table/figure/chunk/evidence 都尽量带 page、line、table/cell、bbox 或 crop anchor。
- Eval as immune system：eval 不替代 parser，而是持续指出抓取缺口、结构漂移、检索 miss 和回答无证据风险。
- Human review as trust gate：复杂视觉、低置信 fusion、合规答案保留人审入口，系统负责把 review payload 做得足够清楚。

### 9.7 后续复用这套操作框架

以后新增一个 parser provider、retriever backend 或 answer workflow，都按同一个小模板推进：

1. 先定义中间 JSON：provider 输出 block/candidate/backend result，字段必须有 id、source anchor、confidence、metadata。
2. 再写最小 failing test：用小 fixture 固定 schema、关键字段和风险场景。
3. 实现最小 provider / backend：先 injectable、lazy import、无新增重依赖，保证主路径稳定。
4. 接入 fusion / canonical / handoff：让新能力进入稳定 contract，而不是让 UI 或 Chat 直接依赖 provider 私有字段。
5. 增加 eval finding：每个新风险都要有 eval_id、status、message、details，方便下一轮 workflow 精准修正。
6. 跑窄验证再跑全量验证：先跑对应 test，再跑 `compileall`、`pytest`、`git diff --check`。
7. 同步 review 文档：把能力、输出 JSON、eval 核查点、剩余边界写进 Design 文档和 changelog。

这就是 G9 沉淀下来的主线方法：工具化 provider，workflow 化流程，JSON 化证据，eval 化核查，LLM 只在明确边界内做二轮解释、修正和生成。