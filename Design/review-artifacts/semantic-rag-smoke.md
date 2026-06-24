# Semantic RAG Smoke

Schema: `semantic-rag-smoke-v0.1`

## Summary

- Embedding status: `available`
- Lexical recall@8: 1.0
- Semantic recall@8: 0.875
- Citation drift cases: 2
- Improved cases: 0
- Regressed cases: 1

## Decision Notes

- Azure `text-embedding-3-small` endpoint is available and can be injected into `VectorRetriever` through the experimental semantic smoke path.
- Current semantic-hybrid should stay experimental: lexical baseline recall@8 is `1.0`, semantic-hybrid recall@8 is `0.875`, with one regression on `r0-mi-r2-po-guidance` and citation drift on `r0-mi-r2-po-guidance` / `r0-ct-section-716-reference`.
- Production session retrieval should remain `HybridRetriever([RuleSectionRetriever, FullTextRetriever])` for now. Before enabling semantic retrieval, investigate slot-aware weighting or route-specific vector gating, especially for role/action and source-location questions.
- `RAG-03` should use a real table question next. If semantic helps table recall without worsening role/reference questions, keep it as a route-gated retriever rather than a global default.

## Cases

### r0-ct-process-operation

- Route: `process_operation` / expected `process_operation`
- Lexical: `pass` top `chunk-doc-20260611163219-f56c6cf9-30`
- Semantic: `pass` top `chunk-doc-20260611163219-f56c6cf9-30`
- Drift: `False`
- Question: CT PEP 文档的流程如何操作？

### r0-mi-r2-po-guidance

- Route: `role_action_guidance` / expected `role_action_guidance`
- Lexical: `pass` top `chunk-doc-20260611163304-4cbf18e4-2`
- Semantic: `fail` top `chunk-doc-20260611163304-4cbf18e4-17`
- Drift: `True`
- Question: MI PEP 里 R2 阶段作为 PO 应该做什么？

### r0-ct-section-716-reference

- Route: `reference_lookup` / expected `reference_lookup`
- Lexical: `pass` top `chunk-doc-20260611163219-f56c6cf9-117`
- Semantic: `pass` top `chunk-doc-20260611163219-f56c6cf9-110`
- Drift: `True`
- Question: CT PEP 的 7.16 法规核准计划在哪里？关键内容是什么？

### r0-mi-r4-r5-transition

- Route: `stage_transition_work` / expected `stage_transition_work`
- Lexical: `pass` top `chunk-doc-20260611163304-4cbf18e4-27`
- Semantic: `pass` top `chunk-doc-20260611163304-4cbf18e4-27`
- Drift: `False`
- Question: MI PEP 中 R4 到 R5 之间需要完成哪些工作？

### r0-mi-qmp-deliverable

- Route: `deliverable_detail` / expected `deliverable_detail`
- Lexical: `pass` top `chunk-doc-20260611163304-4cbf18e4-17`
- Semantic: `pass` top `chunk-doc-20260611163304-4cbf18e4-17`
- Drift: `False`
- Question: MI PEP 中 QMP 需要包含哪些内容？谁负责撰写 QMP？

### r0-xp-agile-tailoring

- Route: `tailoring_policy` / expected `tailoring_policy`
- Lexical: `pass` top `chunk-doc-20260611163330-ea3c2cc8-31`
- Semantic: `pass` top `chunk-doc-20260611163330-ea3c2cc8-31`
- Drift: `False`
- Question: XP PEP 采用敏捷方法开发，可以裁剪哪些评审？哪些评审不可被裁剪？

### r0-mi-unknown-fallback

- Route: `generic_rag` / expected `generic_rag`
- Lexical: `pass` top `chunk-doc-20260611163304-4cbf18e4-2`
- Semantic: `pass` top `chunk-doc-20260611163304-4cbf18e4-2`
- Drift: `False`
- Question: MI PEP 里项目启动前有哪些容易被遗漏但影响后续质量门的准备事项？

### r0-ct-mi-xp-stage-comparison

- Route: `bu_comparison` / expected `bu_comparison`
- Lexical: `pass` top `chunk-doc-20260611163330-ea3c2cc8-70`
- Semantic: `pass` top `chunk-doc-20260611163330-ea3c2cc8-70`
- Drift: `False`
- Question: CT、MI、XP 三份 PEP 对 R4 到 R5 阶段转换要求有什么相同点和差异？
