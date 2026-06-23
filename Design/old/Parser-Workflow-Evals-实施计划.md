# Parser Workflow + Evals 实施计划

更新时间：2026-06-10
状态：Execution Design Draft
关联设计：[MultiInput-Parser-RAG-Workflow-设计.md](MultiInput-Parser-RAG-Workflow-设计.md)

## 0. 当前实施进展

- [x] Gate 1 Parser Workflow Contract：canonical metadata 写入 `parse_workflow`、`structure_quality`、`eval_summary`、`review_items`。
- [x] Gate 2 Markdown Parser MVP：支持 `.md` heading、paragraph/list/code/table block 和 line anchors。
- [x] Backend B0 首版：`/agent/upload`、`/api/documents/{document_id}/parse-summary`、`/api/documents/{document_id}/sections` 返回 Gate 1 字段。
- [x] Parser Quality Evals MVP：新增 `Tool/evals/parser_quality.py`，检查抓取缺口、章节树错误、章节漂移、噪音标题、复杂表格形状、图片 caption/anchor 风险、LLM 输出缺证据。
- [x] Gate 3 PDF/DOCX Chapterization MVP：共享 heading detector 已覆盖 DOCX Heading 样式、compact 编号标题、字母子标题、PDF R 阶段标题和重复页眉清理。
- [x] Gate 3 PEP PDF smoke + 人工核查材料：自动 smoke 已跑 CT / MI / XP PEP，P2-03 已覆盖文档控制页眉和目录点线噪音，P2-01 已明示孤立深层章节；剩余章节树风险保留为 `needs_review`，等待人工确认。
- [x] Gate 4/5 Section Chunk + Retrieval Eval MVP：新增 `Tool/chunking/section_chunks.py`、`Tool/retrieval/section_index.py`、`Tool/evals/retrieval_eval.py`，并通过 `/api/documents/{document_id}/chunks` 暴露 chunk contract。
- [x] Visual OCR / Multimodal Review Queue MVP：新增 `Tool/visual_review.py`，figure 和复杂表格先进入 `visual_review_items`，作为 OCR / multimodal 候选而非可信事实。
- [ ] Gate 6 Adaptive Answer Workflow + Groundedness Eval：按自适应模式设计主 Chat 回答，把 question intent、企业关键词、retrieval evidence package 和 reference 约束组合成 AnswerPackage；详见 [Gate6-Adaptive-Answer-Workflow-Plan.md](Gate6-Adaptive-Answer-Workflow-Plan.md)。
- [ ] Gate 7 Visual OCR / Multimodal Pipeline：把 `visual_review_items` 转成 crop / OCR / multimodal 候选，并进入人工 review。

## 1. 目的

本文把 Multi-input Parser / RAG 的研究设计拆成可执行路线，并吸收 BUs_CER / LEFA_v6 Evals 的最小必要经验：

- 抓取完整性：该抓到的章节、表格、行列、标题、页码是否进入 canonical 输出。
- 真源返回：最终 section / chunk / answer 是否能回到原文 fragment、页码、行列或 line range。
- 章节正确：章节树、标题层级、section_path、chunk 边界是否稳定，避免把噪音或跨章节内容混进 RAG。

本计划只定义 workflow、功能拆分、eval 穿插点、后端接口与前端接入顺序。代码实现按后续小步推进。

## 2. 从 BUs_CER / LEFA_v6 Evals 吸收的最小模式

| LEFA 经验 | QT Wiki 吸收方式 | 暂不吸收 |
| --- | --- | --- |
| FullEvals 作为第一事实源 | Parser/Retrieval/Answer eval report 成为解析与 RAG 的质量事实源 | 暂不做复杂 dashboard |
| 专项脚本做 drilldown | parser eval、section eval、retrieval eval 分开跑，失败时给 evidence | 暂不自动修复数据 |
| registry 记录 work item / review queue | eval warning 进入 `review_items`，供 session UI 或人工确认 | 暂不自动写 whitelist |
| whitelist backflow 要人工确认 | alias、accepted-unmatched、heading 规则回流先生成 patch proposal | 暂不自动修改规则库 |
| Warning 不等于 fail | 支持 `pass / warn / fail / na`，warn 进入人工核查 | 暂不把无分母项硬判 fail |
| Source truth 是质量门 | chunk 和 answer 必须能回到 source anchor | 暂不接受无引用的生成答案 |

## 3. QT Wiki Evals Reference 标签

后续每个 eval 都要标明来源，避免测试项变成散乱脚本。

Evals 分两条线推进：

- 静态开发质量门：代码诊断、类型/语法、测试、diff whitespace、五轴代码审阅，捕捉实现过程中的代码问题、契约漂移和安全/性能风险。
- 动态内容质量门：基于解析产物和后续 RAG/Answer 产物，捕捉章节漂移、信息抓不全、LLM 改写无证据、RAG 召回差、章节拆分错误、复杂表格/图片内容风险。

| Reference 标签 | 来源 | 含义 |
| --- | --- | --- |
| REF-PARSER | `Tool/parsers/*`、`Tool/workflows/document_parse.py` | 格式抽取、canonical document 输出 |
| REF-STRUCTURE | `Tool/structure/*` | heading、section、table、cleanup、signals |
| REF-CHUNK | `Tool/chunking/section_chunks.py` | section chunk 生成与边界检查 |
| REF-RETRIEVAL | `Tool/retrieval/*` | source scope、keyword/vector/rerank、coverage |
| REF-ANSWER | `Tool/workflows/session_rag.py`、`App/api.py` | evidence package 到 answer package |
| REF-EVALS | `Tool/evals/*`、`tests/fixtures/evals/*` | parser/retrieval/answer eval 事实源 |
| REF-HITL | review items、人工确认记录 | low confidence / alias / accepted unmatched 的人工决策 |
| REF-BACKFLOW | 后续 patch proposal | 人工确认后的规则或 whitelist 回流草案 |

## 4. Workflow 总体路线

```text
Input files
  -> W0 Context / Manifest
  -> W1 Format Extract
  -> E1 Capture Completeness Eval
  -> W2 Structure / Chapterization
  -> E2 Section Correctness Eval
  -> W3 Canonical Document Save
  -> E3 Source Truth Eval
  -> W4 Section Chunk Build
  -> E4 Chunk Boundary Eval
  -> W5 Retrieval Index Build
  -> E5 Retrieval Eval
  -> W6 Session Answer Workflow
  -> E6 Answer Groundedness Eval
  -> Review Queue / Backflow Proposal
```

状态由 workflow 计算：

- `parsed`：抽取成功，关键 eval 通过。
- `partially_parsed`：有内容和 anchors，但章节、表格或结构质量不足。
- `needs_review`：核心内容可用，但存在低置信度 heading、未确认 alias 或 eval warning。
- `failed`：无可用文本/表格/锚点，或文件不可读。
- `ocr_required`：PDF 无文本层，需 OCR。

LLM 只产候选，不决定状态。

## 5. 必要 Evals 主表

### 5.1 Parser / Structure Evals

| ID | 目标 | 输入 | 输出 | 状态口径 | 人工核查点 |
| --- | --- | --- | --- | --- | --- |
| P0-01 | 支持格式文件能进入 parse workflow | input file、manifest | parse_status、parser_name、errors | 无 parser 或文件不可读为 fail | 新格式接入前核查 |
| P0-02 | 抽取结果非空 | canonical fragments/tables | fragment_count、table_count | 文本/表格全空为 fail；扫描 PDF 为 ocr_required | OCR 样本核查 |
| P1-01 | 抓取完整性：关键 heading / sheet / slide / markdown heading 被抓到 | parser cases、expected headings | missing_expected_items | 高价值 expected 缺失为 fail/warn | 新 BU 样本进入时核查 |
| P1-02 | 表格/行列抓取完整性 | XLSX/DOCX/PDF table cases | table_count、row/column coverage | 关键表格缺失为 warn/fail | Excel 输入首版核查 |
| P1-03 | 图片/图示抓取风险 | figures、captions、anchors | missing_caption_figures、missing_anchor_figures | 图示缺 caption 或 anchor 为 warn | 图片密集文档首版核查 |
| P1-05 | Visual completeness：图像/复杂表格是否进入 OCR 或 multimodal review queue | figures、tables、visual_review_items | visual_review_count、recommended_tools | 有图像候选但未视觉分析为 warn | crop / OCR / multimodal 接入前核查 |
| P2-01 | 章节正确：section 层级与 parent_id 合理 | section candidates、canonical sections | section_tree_errors | 目录错层、重复根节点过多为 warn/fail | 章节树 UI 前核查 |
| P2-02 | 章节边界正确：fragment 归属不跨章节污染 | sections、fragments | orphan_fragments、cross_section_suspects | 大量 null section 或跨章节为 warn | RAG chunk 前核查 |
| P2-03 | 噪音清理：页眉页脚、目录点线、模板残留不进入标题 | sections、fragments | noise_rate、noise_samples | 噪音标题超过阈值为 warn/fail | PDF/DOCX 批量导入前核查 |
| P3-01 | 真源返回：section / fragment anchors 完整 | canonical source_anchors | anchor_coverage | anchor 缺失为 fail；低覆盖为 warn | Reference UI 前核查 |
| P3-02 | 真源还原：chunk 去处理后能回到原文片段 | chunks、canonical fragments | unsupported_chunk_text | 无法由 source 支撑为 fail | LLM assist 接入前核查 |
| L1-01 | LLM Assist 保真：LLM 生成/改写内容必须有 evidence | metadata.llm_assist、llm fragments | missing_evidence_items | LLM 输出无证据为 fail | LLM assist 接入前核查 |

### 5.2 Chunk / Retrieval / Answer Evals

| ID | 目标 | 输入 | 输出 | 状态口径 | 人工核查点 |
| --- | --- | --- | --- | --- | --- |
| C1-01 | Chunk 边界：chunk 不跨无关章节 | sections、chunks | boundary_violations | 跨章节污染为 warn/fail | 建索引前核查 |
| C1-02 | Chunk 引用完整：file、section、anchor、quote 都存在 | chunks | missing_citation_fields | 缺任一核心字段为 fail | Reference 输出前核查 |
| R1-01 | 全局检索召回：All Sources 能命中 expected docs / sections | retrieval cases | Recall@K、coverage | 低于阈值为 warn/fail | 全局知识库扩容后核查 |
| R1-02 | 局部检索/直读策略选择正确 | source_scope、strategy trace | strategy_used、reason | 策略与 scope 不一致为 fail | Session query 接口前核查 |
| R1-03 | Excel table-aware retrieval 能引用行列 | table chunks、queries | sheet/row/cell citation | 无行列引用为 warn/fail | Excel 进入 MVP 时核查 |
| A1-01 | Answer groundedness：答案每个关键事实有 citation | answer package、evidence | unsupported_claims | unsupported claim 为 fail | LLM 答案上线前核查 |
| A1-02 | 缺口说明：证据不足时不编造 | no-answer cases | abstention correctness | 证据不足仍编造为 fail | LLM prompt 固化前核查 |
| A1-03 | 格式合规：结论、source scope、steps、references 完整 | answer package | format_errors | 缺 Reference 为 fail | 前端渲染前核查 |
| A1-04 | 自适应格式：输出样式匹配问题意图且不过度模板化 | question intent、answer package | shape_mismatch、over_template_signals | 主 Chat 体验僵硬为 warn | 主 Chat 接入前核查 |
| A1-05 | 企业关键词归一：PO/R2/QMP 等术语正确映射并保留原文依据 | question intent、keyword lexicon、evidence | normalization_errors | 核心术语错配为 fail | Answer Workflow 前核查 |

## 6. Parser Workflow 功能拆分

### Step P0：Contract 与 Workflow 壳层

目标：先把状态、trace、eval summary 结构固定。

输出：

```json
{
  "run_id": "parse-20260610-001",
  "document_id": "doc-...",
  "parse_status": "partially_parsed",
  "parser_name": "pdf_parser",
  "parser_version": "multi-input-v0.1",
  "counts": {"sections": 12, "fragments": 320, "tables": 2},
  "structure_quality": {"anchor_coverage": 1.0, "section_confidence": 0.82, "noise_rate": 0.03},
  "eval_summary": {"pass": 6, "warn": 2, "fail": 0, "na": 1},
  "review_items": []
}
```

你需要核查：`parse_status` 和 `warn/fail/na` 口径是否符合产品体验。

### Step P1：Markdown Parser

目标：先接入最稳定的章节化格式，用 heading + line anchors 打样 workflow。

范围：

- `.md` 加入 `SUPPORTED_SUFFIXES`。
- `# / ## / ###` 生成 sections。
- paragraph/list/code/table block 生成 fragments。
- anchors 使用 `line_start / line_end / heading_path`。

你需要核查：Markdown 的章节树和引用粒度是否满足右侧 Reference UI。

### Step P2：PDF / DOCX 章节化增强

目标：让 PDF/DOCX 都从“段落堆叠”进入“章节树 + fragment 归属”。

范围：

- PDF：编号 heading、TOC 点线、页眉页脚清理、扫描件检测。
- DOCX：heading style、编号标题、列表层级、表格归属 section。
- PEP PDF 作为第一批 smoke cases。

你需要核查：三份 PEP PDF 的章节树、标题清理和 R2 相关章节是否可用。

### Step P3：XLSX / Table-aware 结构化

目标：Excel 不作为普通文本处理，而是 table-first。

范围：

- sheet 作为一级 section。
- 连续非空区域识别为 table region。
- 表头、row_index、column、cell_range 写入 anchors。
- 行文本可检索，表格引用能定位到 sheet + row/cell。

你需要核查：Excel 输出的引用是否能让用户回到原表格。

### Step P4：Section Chunk 与 Index

目标：所有格式统一生成 section chunks。

范围：

- chunk 保留 section_path、source anchors、quote、signals。
- 长章节按 token 预算切分，保留 overlap 和相邻 fragment。
- 输出 `sections.jsonl` 或等价本地 index。

你需要核查：chunk 粒度是否适合 LLM 读，是否太碎或太大。

当前实现：

- `build_section_chunks()` 已生成 section / table / figure chunks。
- 每个 chunk 保留 `document_id`、`section_path`、`source_refs`、`anchors`、`quote` 和 `signals`。
- History table 被标记为 `document_history`，后续 retrieval scoring 会降权。
- `/api/documents/{document_id}/chunks` 已返回稳定 chunk contract。

### Step P5：Session Retrieval Workflow

目标：查询层按 source scope 自动选择策略。

范围：

- All Sources：全局 hybrid retrieval。
- Selected Docs：scoped retrieval。
- Selected Section / short doc：direct read。
- Excel：table-aware retrieval。
- 返回 `strategy_used` 和 trace。

你需要核查：策略选择是否符合使用直觉。

当前实现：

- `retrieve_sections()` 支持 `all_sources`、`selected_docs`、`selected_sections`。
- `RetrievalResult` 返回 `strategy_used`、`source_scope`、`evidence_coverage`、`hits` 和 trace。
- `evaluate_retrieval_cases()` 支持 expected docs / section terms / text terms / forbidden primary section terms。
- CT / MI / XP smoke：R2 查询已回到 R2 正文/裁剪规则，CT 7.16 regulatory approval plan 在 selected_docs scope 排第一。

## 7. 后端功能设计顺序

### Backend B0：Parse Workflow API

先增强现有 upload 返回，不急着做复杂 session API。

候选接口：

```text
POST /agent/upload
GET  /api/documents/{document_id}/parse-summary
GET  /api/documents/{document_id}/sections
```

新增字段：

- `parse_status`
- `structure_quality`
- `eval_summary`
- `review_items`
- `sections_preview`

### Backend B1：Eval API

候选接口：

```text
POST /api/evals/parser/run
GET  /api/evals/runs/{run_id}
GET  /api/evals/review-items
```

首版也可以只通过 CLI 跑 eval，再由前端读取 parse summary。

当前实现：parser eval 通过 workflow metadata 返回；retrieval eval 先以 Python module / test / smoke script 方式运行。

### Backend B2：Retrieval / Query API

扩展 `/chat/query` 或新增 `/api/session-query`。

当前已补充：

```text
GET /api/documents/{document_id}/chunks
```

正式 query API 等 Answer Contract 固定后再接入。

Gate 6 Answer Contract 当前计划：

- `QuestionIntent`：问题意图、关键词、答案形态、reference 密度。
- `EnterpriseKeywordLexicon`：R 阶段、角色、交付物、BU、章节号、alias。
- `AnswerEvidencePackage`：retrieval hits 到可引用 evidence items。
- `AnswerPackage`：answer_text、citations、intent、coverage、missing_evidence、eval_summary、trace。
- Adaptive prompt builder：只消费 intent + evidence package，不直接自由检索。

请求：

```json
{
  "question": "R2阶段我作为PO应该做什么",
  "source_scope": {"mode": "selected_docs", "document_ids": ["ct-pep"]},
  "retrieval_strategy": "auto",
  "use_llm": true,
  "top_k_chunks": 8
}
```

响应：

```json
{
  "answer": "...",
  "strategy_used": "scoped_hybrid_retrieval",
  "source_scope": {},
  "evidence_coverage": {},
  "citations": [],
  "trace": [],
  "eval_summary": {}
}
```

## 8. 前端 UI / 接口设计顺序

### Frontend F0：Parser 状态露出

左侧 Sources 每个文档显示：

- `parsed / partially_parsed / needs_review / failed / ocr_required`。
- section_count、fragment_count、anchor coverage。
- warning 数量。

你需要核查：状态文案和小图标是否让非技术用户能理解。

### Frontend F1：章节树预览

左侧 Tree 展示：

- Document -> Section -> Fragment preview。
- PDF 显示 page。
- Markdown 显示 line range。
- Excel 显示 sheet/table/row。

你需要核查：章节树是否像 NotebookLM Sources 一样能建立信任感。

### Frontend F2：Eval Review Queue

右侧或后台入口展示 warning：

- 缺失 heading。
- 低置信度标题。
- 无 anchor chunk。
- 需要人工确认的 alias / accepted unmatched。

首版只读，不自动回流。

### Frontend F3：Query Trace / Reference

回答区展示：

- strategy_used。
- source scope。
- evidence coverage。
- citations：file + section + page/row/line + quote。

你需要核查：Reference 是否足够清楚，能否支撑“公司流程依据”。

## 9. 关键人工核查节点

| 节点 | 你核查什么 | 通过后进入 |
| --- | --- | --- |
| Gate 1 Contract | parse_status、structure_quality、eval_summary 口径 | Markdown parser |
| Gate 2 Markdown | heading tree、line anchors、Reference 粒度 | PDF/DOCX 章节化 |
| Gate 3 PEP PDF | PEP 章节树、R2/R3 等关键章节、页眉清理 | Section Chunk |
| Gate 4 Excel | sheet/table/row/cell 引用是否可读 | Table-aware retrieval |
| Gate 5 Chunk | chunk 粒度和引用完整性 | Retrieval API / Answer Contract |
| Gate 6 Adaptive Answer | question intent、企业关键词归一、evidence package、adaptive format、Reference 完整性 | Session Query API / 主 Chat |
| Gate 7 Visual OCR / Multimodal | crop/OCR/multimodal 候选是否有 evidence 并进入 review | Workflow Studio 输出 |

## 10. 当前推荐下一步

最小实现顺序：

1. 实现 `QuestionIntent` 规则解析 MVP，覆盖 R 阶段、角色、交付物、BU diff、reference lookup。
2. 实现企业关键词归一 MVP，先用规则词典 + chunk signals。
3. 把 `RetrievalResult` 固化成 `AnswerEvidencePackage`：每个事实只来自 `source_refs.quote`。
4. 实现 adaptive prompt builder 和 AnswerPackage，但保持输出格式按 intent 自适应。
5. 实现 Answer Groundedness Eval：unsupported claim、missing citation、evidence insufficient abstention、format over-template warning。
6. 给 Session Query API 接 `selected_docs / all_sources / selected_sections`。

当前底座已经从 Parser Gate 推进到 Retrieval Gate。下一步重点是 Gate 6 的 `QuestionIntent + AnswerEvidencePackage`，先把“用户问题要什么”和“证据包能证明什么”固定下来，再接 LLM 自适应生成。