# Release-0 Route RAG Smoke 诊断

日期：2026-06-23

## 结论

`RAG-01 Evidence Pattern Generalization` 已把 Release-0 的 route runtime RAG smoke 从 `6/8` 提升到 `8/8`。本轮没有改 parser/provider，也没有引入向量库；修复集中在 Chat/RAG runtime 的 route priority、query pack、domain term pack、route-aware evidence scoring 和泛噪音降权。

本报告和 `release0-parser-rag-smoke.md` 的分工：

- `release0-parser-rag-smoke.md`：判断 parsed canonical / SectionChunk / source_refs / anchors / quote 是否足够。
- 本报告：验证真实 session runtime 的 route plan、query pack、HybridRetriever、route-aware rerank 是否能把正确证据排进 top hits。

## 运行命令

```powershell
..\.venv\Scripts\python.exe -c "from Tool.evals.route_rag_smoke import release0_route_rag_smoke_report; import json; report=release0_route_rag_smoke_report(top_k=8); print(json.dumps({'schema_version': report['schema_version'], 'metrics': report['metrics'], 'failure_summary': report['failure_summary'], 'cases': [(case['case_id'], case['status'], case['failure_category'], case['actual_route_id']) for case in report['case_diagnostics']]}, ensure_ascii=False, indent=2))"
```

## 总览

- Schema：`release0-route-rag-smoke-v0.1`
- Case count：8
- Pass count：8
- Pass rate：1.0
- Route accuracy：1.0
- Failure summary：`route_gap = 0`，`route_rerank_gap = 0`，`retrieval_gap = 0`，`document_load_gap = 0`

## Case 结果

| Case | 状态 | Route |
| --- | --- | --- |
| `r0-ct-process-operation` | pass | `process_operation` |
| `r0-mi-r2-po-guidance` | pass | `role_action_guidance` |
| `r0-ct-section-716-reference` | pass | `reference_lookup` |
| `r0-mi-r4-r5-transition` | pass | `stage_transition_work` |
| `r0-mi-qmp-deliverable` | pass | `deliverable_detail` |
| `r0-xp-agile-tailoring` | pass | `tailoring_policy` |
| `r0-mi-unknown-fallback` | pass | `generic_rag` |
| `r0-ct-mi-xp-stage-comparison` | pass | `bu_comparison` |

## 本轮修复点

### 1. Query Pack

`query-rewrite-v0.1` 保持兼容，同时新增 `route-query-pack-v0.1`：

- `primary_query`
- `slot_queries`
- `must_terms`
- `support_terms`
- `weak_terms`
- `downrank_terms`

这让 RAG 从“原问题 + route terms”升级为“按证据模式组织查询”。

### 2. Domain Term Pack

QMP、Quality Management Plan、质量管理计划、owner、author、responsible、agile、tailoring、mandatory、cannot be tailored 等术语进入 route domain pack。新增术语时优先扩展词包，主流程保持稳定。

### 3. Route Evidence Scoring

`deliverable_detail` 和 `tailoring_policy` 不再继承 overview bonus。现在按 route evidence pattern 加权：

- `deliverable_detail`：提升 `QMP + required contents`、`QMP + owner/author/responsible`、`QMP + review/approval`。
- `tailoring_policy`：提升 `agile + tailoring + review`、`review + mandatory/cannot be tailored`。
- detail/policy route 下调 `Purpose and scope`、`Provisional solution`、泛 responsibility 等噪音章节。

### 4. Route Priority

- 多 BU 对比意图优先于阶段转换意图，避免 `CT/MI/XP + R4/R5 + 差异` 被误判为单纯 `stage_transition_work`。
- 开放式发现类问题进入 `generic_rag`，例如“容易被遗漏但影响后续质量门的准备事项”。

## 设计 takeaway

RAG 的稳定方向不是为每个垂直术语写一套流程，而是：

```text
Route 按证据需求分类
Term 按领域词包扩展
Slot 按答案结构绑定
Eval 按真实 runtime 验证
```

大白话：

- Route 是“我要找哪类证据”。
- Term 是“这类证据里有哪些专业叫法”。
- Slot 是“答案需要填哪几个格子”。
- Rerank 是“把更像正确证据的段落排到前面”。
- Eval 是“用真实问题反复证明这条链路没跑偏”。

## 后续影响

- `PARSER-MIN-02 EvidenceSource adapter` 仍然有价值，但目标是 contract 收敛和 UI/Claim Verifier 复用，本轮失败不需要通过换 parser 解决。
- 下一步可继续 `CHAT-07 Claim Verifier report`，用当前更稳的 evidence/citation/slot 结果检查 unsupported claim。
