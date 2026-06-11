# G9 Human Review Pack

更新时间：2026-06-11  
状态：Review Draft  
关联总结：[Pro-Input-Praser.md](Pro-Input-Praser.md)  
关联规格：[Tool-Parser-RAG-Fusion-Spec.md](Tool-Parser-RAG-Fusion-Spec.md)  
上层执行入口：[TODO.md](TODO.md)

## 1. 推荐人审路线

建议先生成一版人审内容集合，再做 UI。

原因：G9 的核心成果是 parser / OCR / multimodal / retrieval / eval / LLM evidence 的底层 contract。当前最需要人判断的是“抽取是否忠实原文、JSON contract 是否够用、eval findings 是否能指导下一轮修正”。这些判断适合先用静态 review pack 集中完成，再把确认过的字段接进 G8 UI。

推荐顺序：

1. 人审内容集合：用 Markdown + JSON snapshots 集中看一轮。
2. G9 hardening pass：修复人审和机器预审发现的阻塞项。
3. G8 UI v0.4：消费已经确认过的 `session-handoff-v0.1`、tree、graph、retrieval preview、answer contract。
4. UI 手测：检查三栏工作台是否好用，字段是否展示清楚。

## 2. 这轮人审要回答什么

本轮人审不是逐行 code review，而是做五类判断：

- Parser 语义：章节树、History / TOC 清理、R2/R3、7.16、Reference 是否贴近原文。
- Provider fusion：pypdf / DOCX XML / Docling / OCR/VLM 的贡献是否可解释，低置信融合是否进入 review。
- Visual candidate：figure、流程图、复杂表格是否只作为候选，是否有 page/bbox/crop/source_refs。
- Retrieval / Answer：检索命中的 section/quote 是否支撑问题，LLM answer 是否引用 primary evidence。
- Handoff contract：G8 UI 是否能用 `session-handoff-v0.1` 一次拿到 Source、Tree、Graph、Retrieval、Chat、Quality。

通过标准：

- [ ] 可以用当前 JSON contract 支撑 G8 UI，不需要再大改字段形状。
- [ ] 人能从 review pack 判断 parser 是否可信进入 retrieval。
- [ ] 复杂视觉和低置信融合能被识别并留在人审队列。
- [ ] Retrieval / Answer 的证据链足够解释“答案为什么这么说”。
- [ ] 已知工程 hardening 项有明确修复计划。

## 3. 人审材料包应该包含什么

### 3.0 你实际要输出什么

先不用做 UI。第一版人审只需要输出一个文件夹，里面放 Markdown 总表和几个 JSON snapshot。

建议文件夹：

```text
Design/review-artifacts/g9/
  REVIEW-INDEX.md
  ct-pep/
    parse-summary.json
    sections.json
    chunks-preview.json
    session-handoff.json
    query-r2-po.json
    query-716.json
  mi-pep/
    parse-summary.json
    sections.json
    chunks-preview.json
    session-handoff.json
    query-r2-po.json
  xp-pep/
    parse-summary.json
    sections.json
    chunks-preview.json
    session-handoff.json
    query-r2-po.json
```

第一轮人审优先看这 6 类输出：

| 输出文件 | 怎么来 | 你看什么 | 判断结果 |
| --- | --- | --- | --- |
| `REVIEW-INDEX.md` | 手工汇总或从下面 JSON 摘要整理 | 哪些文档 parsed / needs_review / failed，fail/warn 数量 | 决定先审哪份文档。 |
| `parse-summary.json` | `GET /api/documents/{document_id}/parse-summary` | `parse_status`、counts、`eval_summary`、`review_items`、`visual_review_items`、`parse_workflow.parser_fusion` | 判断 parser 是否可信进入 RAG。 |
| `sections.json` | `GET /api/documents/{document_id}/sections` | 前 20 个 section、R2/R3、7.16、Purpose/Reference、parent/level/page_range | 判断章节树是否贴近原文。 |
| `chunks-preview.json` | `GET /api/documents/{document_id}/chunks` 后取前几十个或关键词附近 chunks | `section_title`、`chunk_type`、`quote`、`source_refs`、`signals` | 判断 RAG chunk 是否可引用。 |
| `session-handoff.json` | `GET /api/session/handoff/{document_id}` | `source`、`tree`、`graph`、`retrieval.preview_chunks`、`chat.answer_contract`、`quality` | 判断 G8 UI 能不能直接消费。 |
| `query-*.json` | `POST /chat/query` | answer、citations、source refs、retrieval trace | 判断答案是否被证据支撑。 |

### 3.0.1 最小输出命令

从 repo 根目录 `QT-wiki` 执行。

1. 如果文档还没有入库，先 ingest：

```powershell
..\.venv\Scripts\python.exe -m Tool.pipelines.ingest --input Raw
```

命令会输出：

```text
INGESTED doc-xxxx -> Raw/xxx.pdf
```

2. 对每个 `document_id` 生成 parsed canonical JSON：

```powershell
..\.venv\Scripts\python.exe -m Tool.pipelines.parse --document-id doc-xxxx
```

输出位置：

```text
Tool/output/parsed/doc-xxxx.json
```

这个文件是最底层原始人审材料。里面重点看：

- `document.metadata.parse_workflow`
- `document.metadata.parse_workflow.parser_fusion`
- `sections`
- `fragments`
- `tables`
- `figures`
- `source_anchors`
- `parse_status`

3. 启动 API：

```powershell
..\.venv\Scripts\python.exe App/api.py
```

默认地址：

```text
http://127.0.0.1:8000
```

4. 导出单文档 review snapshots：

```powershell
$doc = "doc-xxxx"
$out = "Design/review-artifacts/g9/$doc"
New-Item -ItemType Directory -Force -Path $out | Out-Null
Invoke-RestMethod "http://127.0.0.1:8000/api/documents/$doc/parse-summary" | ConvertTo-Json -Depth 20 | Set-Content "$out/parse-summary.json" -Encoding UTF8
Invoke-RestMethod "http://127.0.0.1:8000/api/documents/$doc/sections" | ConvertTo-Json -Depth 20 | Set-Content "$out/sections.json" -Encoding UTF8
Invoke-RestMethod "http://127.0.0.1:8000/api/documents/$doc/chunks" | ConvertTo-Json -Depth 20 | Set-Content "$out/chunks-preview.json" -Encoding UTF8
Invoke-RestMethod "http://127.0.0.1:8000/api/session/handoff/$doc" | ConvertTo-Json -Depth 30 | Set-Content "$out/session-handoff.json" -Encoding UTF8
```

5. 导出问题测试结果：

```powershell
$body = @{
  question = "R2 阶段 PO 要准备什么？"
  use_llm = $false
  selected_docs = @($doc)
} | ConvertTo-Json -Depth 10

Invoke-RestMethod "http://127.0.0.1:8000/chat/query" -Method Post -ContentType "application/json" -Body $body |
  ConvertTo-Json -Depth 30 |
  Set-Content "$out/query-r2-po.json" -Encoding UTF8
```

如果当前 `/chat/query` 仍走旧 selected docs 参数，以上 body 需要按实际 API contract 调整；第一轮人审的必需项仍是 `parse-summary.json`、`sections.json`、`chunks-preview.json`、`session-handoff.json`。

### 3.0.2 打开后先看哪里

建议打开顺序：

1. `parse-summary.json`
   - 先看 `parse_status`。
   - 再看 `eval_summary.fail` 和 `eval_summary.warn`。
   - 然后看 `review_items` / `visual_review_items`。
   - 最后看 `parse_workflow.parser_fusion.providers` 和 `fusion_decisions`。

2. `sections.json`
   - 先看开头 20 个 section，确认 Content / TOC / History 没污染正文。
   - 搜索 `R2`、`R3`、`7.16`、`Purpose`、`Reference`。
   - 看 `level`、`parent_id`、`page_range` 是否合理。

3. `chunks-preview.json`
   - 搜索 `R2`、`Product Owner`、`QMP`、`7.16`。
   - 看 `chunk_type` 是否是正文 section/table，而不是 `document_history`。
   - 看 `quote` 和 `source_refs.anchor_label` 是否能回原文。

4. `session-handoff.json`
   - 看 `source.parse_status` 和 counts。
   - 看 `tree.items` 是否足够 UI 展示。
   - 看 `graph.edges` 是否以 `contains` / `mentions` 为主，不是装饰性乱连。
   - 看 `chat.answer_contract.requires_citations` 是否为 true。
   - 看 `quality.parser_fusion` 是否存在。

5. `query-*.json`
   - 看 top citations 是否来自正确文档和章节。
   - 看 quote 是否真的支撑 answer。
   - 看证据不足时是否有明确缺口说明。

最小通过标准：

- `parse-summary.json` 没有无法解释的 fail。
- `sections.json` 的关键章节能命中正文。
- `chunks-preview.json` 的关键 quote 能回到 source_refs。
- `session-handoff.json` 能直接支撑 G8 UI 的 Source / Tree / Graph / Chat。
- `query-*.json` 的答案不是只“有 citation”，而是 citation 真的支撑断言。

### 3.1 Review Index

每个文档一行，先看总体状态。

| 文档 | parse_status | sections | fragments | tables | figures | chunks | eval fail/warn | 人审结论 |
| --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| CT PEP | parsed / needs_review | 待刷新 | 待刷新 | 待刷新 | 待刷新 | 待刷新 | 待刷新 | [ ] 通过 [ ] 需修 |
| MI PEP | parsed / needs_review | 待刷新 | 待刷新 | 待刷新 | 待刷新 | 待刷新 | 待刷新 | [ ] 通过 [ ] 需修 |
| XP PEP | parsed / needs_review | 待刷新 | 待刷新 | 待刷新 | 待刷新 | 待刷新 | 待刷新 | [ ] 通过 [ ] 需修 |

当前 smoke 经验值：CT `tables=1`、`figures=2`、`chunks=146`；MI `tables=1`、`figures=1`、`chunks=93`；XP `tables=1`、`figures=5`、`chunks=163`。正式人审前建议重新生成最新 parsed JSON 后刷新本表。

### 3.2 Parser Summary Snapshot

目标：确认 parser 输出的基础质量。

需要展示：

- `document_id`、`file_name`、`parse_status`
- `section_count`、`fragment_count`、`table_count`、`figure_count`
- `structure_quality.anchor_coverage`
- `eval_summary`
- `review_items`
- `visual_review_items`

人审问题：

- [ ] parse_status 是否符合实际文档质量。
- [ ] warning/fail 是否能让人理解下一步该看哪里。
- [ ] `review_items` 是否覆盖 TOC、History、section tree、anchor、table、figure 风险。
- [ ] `visual_review_items` 是否覆盖 V-model、流程图、复杂表格。

### 3.3 Section Tree Snapshot

目标：确认章节树可进入 RAG。

每个文档至少抽查：

- 前 20 个 section：确认 History / Content / document control 是否污染正文。
- Purpose / Reference / Definitions / Process & Requirement。
- R2 / R3 / System phases。
- Country-specific approvals / 7.16。
- 所有 level jump / rootless child warning 对应的节点。

人审问题：

- [ ] 章节从 History 后合理进入 Purpose / Reference / 正文流程。
- [ ] Content / TOC 页没有变成正文 root section。
- [ ] R2/R3 命中正文，而不是模板历史或目录页。
- [ ] 双语标题没有明显缺字，尤其括号内法规术语。
- [ ] section page range 与原文页码大体一致。

### 3.4 Table / Figure / Visual Snapshot

目标：确认表格、图、OCR/VLM 候选没有过早变成事实。

需要展示：

- History table：rows、table_type、page、anchor_label。
- Table chunks：`tbl.N R1C1:R2C2`、row_count、column_count、signals。
- Figure candidates：figure_id、caption、page、source。
- Visual candidates：candidate_id、provider、candidate_type、page、bbox/crop_ref、confidence、review_status、source_refs。

人审问题：

- [ ] History 表格进入 `tables`，没有污染 sections。
- [ ] 表格行列没有明显错位。
- [ ] role / deliverable table signals 合理。
- [ ] Figure caption 与原文一致。
- [ ] V-model / process structure 当前如果只有 caption，标记为需要 crop + multimodal。
- [ ] `review_status=pending_review` 的视觉候选没有被当成 primary evidence。

### 3.5 Parser Fusion Snapshot

目标：确认 provider fusion 过程可解释。

重点看 `parser_fusion`：

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
    "extraction_blocks": 0,
    "layout_blocks": 0,
    "table_blocks": 0,
    "visual_candidates": 0,
    "fusion_decisions": 0
  },
  "canonical_output": {
    "sections": 0,
    "fragments": 0,
    "tables": 0,
    "figures": 0,
    "source_anchors": 0
  },
  "fusion_decisions": []
}
```

人审问题：

- [ ] providers 与文档类型匹配：PDF 应至少有 pypdf fast text；DOCX 应有 docx_xml；Docling/OCR/VLM 是可选增强。
- [ ] provider roles 能解释各自贡献。
- [ ] `canonical_output` 与 parser summary 数量一致。
- [ ] low-confidence fusion decision 有 reason、selected_block_ids、output_target。
- [ ] table / visual provider 输出没有绕过 canonical/eval gate。

### 3.6 Retrieval / Answer Snapshot

目标：确认 RAG 和 LLM 只基于证据作答。

建议至少跑这些 review questions：

| 问题 | source_scope | 期望命中 | 人审重点 |
| --- | --- | --- | --- |
| R2 阶段 PO 要准备什么？ | selected_docs: CT | R2 正文 / Product Owner / deliverable | 命中是否来自 R2 正文，quote 是否支撑职责。 |
| CT 7.16 regulatory approval plan 在哪里？ | selected_docs: CT | 7.16 Country-specific approvals | 是否命中正文 page 49，而不是目录页。 |
| CT / MI / XP 的 R2 职责有什么差异？ | selected_docs: CT, MI, XP | 三个 BU 的 R2/R-stage 章节 | 是否先对齐章节 path，再比较差异。 |
| 这个问题证据不足时怎么回答？ | selected_docs 或 all_sources | missing_evidence | 是否明确说明缺口，而不是编答案。 |

人审问题：

- [ ] top hit 的 document_id 和 section_title 与问题一致。
- [ ] quote 能支撑回答中的关键事实。
- [ ] History/template change 没有成为 primary evidence。
- [ ] AnswerEvidencePackage 有 `evidence_id`、`anchor_label`、`quote`。
- [ ] LLM answer 使用 citation，并在证据不足时提示缺口。

### 3.7 Session Handoff Snapshot

目标：确认 G8 UI 可以基于一个 payload 起步。

重点看 `/api/session/handoff/{document_id}`：

- `source`：Source list / status chip。
- `tree.items`：左侧 Document Tree。
- `graph.nodes/edges`：Graph MVP seeds。
- `retrieval.available_retrievers`、`preview_chunks`：检索面板和 debug。
- `chat.request_contract`：composer 请求字段。
- `chat.answer_contract`：citation / evidence package 要求。
- `quality`：parse/eval/review/fusion 状态。

人审问题：

- [ ] Tree 节点足够 UI 展示：node_id、node_type、parent_id、title、section_id、page_range、fragment_count、chunk_count。
- [ ] Graph 边关系能解释：contains / mentions。
- [ ] Retrieval preview 不会把 History/template change 放在首要位置。
- [ ] Chat contract 清楚说明 requires_citations 和 quality gates。
- [ ] Quality 区能让用户知道是否需要 review。

## 4. 建议执行节奏

### 4.1 第一轮：静态内容集合 review

时间：60 到 90 分钟。

执行：

1. 先看 Review Index，决定哪些文档需要重点看。
2. 每个文档看 Section Tree Snapshot，优先检查 History / TOC / R2 / 7.16。
3. 看 Table / Figure / Visual Snapshot，确认复杂视觉仍在候选层。
4. 看 Retrieval / Answer Snapshot，确认 citation 是否真的支撑答案。
5. 看 Session Handoff Snapshot，确认 G8 UI contract 是否够用。

产出：

- [ ] `Approved for G8 UI integration`
- [ ] `Approved with hardening items`
- [ ] `Request G9 repair before UI`

### 4.2 第二轮：工程 hardening

机器预审已指出几个建议先修的点：

- [ ] chunk builder 增加 no-section fallback，避免有 fragments 但无 sections 时丢正文。
- [ ] retrieval eval 收紧为同一 hit 满足 expected doc/section/term，降低假阳性。
- [ ] answer eval 明确当前是 citation presence gate，并增加 claim support 的后续 eval 设计。
- [ ] fusion eval 并入 parse workflow quality gate。
- [ ] visual primary gate 区分 `reviewed` 与 `accepted`。
- [ ] API `document_id` 增加白名单校验。
- [ ] chunks/handoff 增加 limit/truncated 或分页策略。

### 4.3 第三轮：UI 接入 review

G8 UI 开始后，人审重点从“内容可信不可信”转为“用户能不能看懂并操作”：

- Source 状态是否清楚。
- Tree 是否真实，能定位章节。
- Graph 是否解释关系，而不是装饰图。
- Chat answer 是否自然展示 citation。
- Note 是否能 pin answer 和 citation excerpts。

## 5. 临时生成 review snapshots 的接口清单

启动后端并确保文档已 parsed 后，用这些接口拉材料：

```text
GET /api/documents/{document_id}/parse-summary
GET /api/documents/{document_id}/sections
GET /api/documents/{document_id}/chunks
GET /api/session/handoff/{document_id}
POST /chat/query
```

建议保存的文件结构同 `3.0`。如果只想先看最小包，保存这四个即可：

```text
Design/review-artifacts/g9/
  ct-pep/
    parse-summary.json
    sections.json
    chunks-preview.json
    session-handoff.json
```

当前仓库未跟踪真实 `Tool/output/parsed/*.json`，因此这份 pack 先定义人审结构和判断口径。重新上传或重新 parse CT / MI / XP 后，再把真实 JSON snapshots 放到 `Design/review-artifacts/g9/` 或保持本地不入库。

## 6. 人审记录模板

复制下面模板给每个文档填一次。

```markdown
## Review Record: <document_id>

### Verdict

- [ ] Pass
- [ ] Pass with hardening
- [ ] Needs parser repair
- [ ] Needs visual/OCR review
- [ ] Needs retrieval/answer repair

### Parser / Section Tree

- History / TOC cleanup:
- R2 / R3 section quality:
- 7.16 / country-specific approvals:
- Reference quality:
- Page / anchor quality:

### Tables / Figures / Visual

- History table:
- Responsibility / deliverable table:
- Figures and captions:
- OCR/VLM candidates:

### Retrieval / Answer

- R2 PO query:
- 7.16 query:
- BU comparison query:
- Missing evidence behavior:

### Blocking Issues

1.

### Follow-up Actions

1.
```