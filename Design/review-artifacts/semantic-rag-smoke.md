# Semantic RAG Smoke

Schema: `semantic-rag-smoke-v0.1`

## Summary

- Embedding status: `available`
- Lexical recall@8: 1.0
- Semantic recall@8: 0.875
- Route-gated semantic recall@8: 1.0
- Citation drift cases: 2
- Route-gated citation drift cases: 0
- Improved cases: 0
- Regressed cases: 1

## Cases

### r0-ct-process-operation

- Route: `process_operation` / expected `process_operation`
- Lexical: `pass` top `chunk-doc-20260611163219-f56c6cf9-30`
- Semantic: `pass` top `chunk-doc-20260611163219-f56c6cf9-30`
- Route-gated semantic: `pass` top `chunk-doc-20260611163219-f56c6cf9-30` enabled `True`
- Drift: `False`
- Question: CT PEP 文档的流程如何操作？

### r0-mi-r2-po-guidance

- Route: `role_action_guidance` / expected `role_action_guidance`
- Lexical: `pass` top `chunk-doc-20260611163304-4cbf18e4-2`
- Semantic: `fail` top `chunk-doc-20260611163304-4cbf18e4-17`
- Route-gated semantic: `pass` top `chunk-doc-20260611163304-4cbf18e4-2` enabled `False`
- Drift: `True`
- Question: MI PEP 里 R2 阶段作为 PO 应该做什么？

### r0-ct-section-716-reference

- Route: `reference_lookup` / expected `reference_lookup`
- Lexical: `pass` top `chunk-doc-20260611163219-f56c6cf9-117`
- Semantic: `pass` top `chunk-doc-20260611163219-f56c6cf9-110`
- Route-gated semantic: `pass` top `chunk-doc-20260611163219-f56c6cf9-117` enabled `False`
- Drift: `True`
- Question: CT PEP 的 7.16 法规核准计划在哪里？关键内容是什么？

### r0-mi-r4-r5-transition

- Route: `stage_transition_work` / expected `stage_transition_work`
- Lexical: `pass` top `chunk-doc-20260611163304-4cbf18e4-27`
- Semantic: `pass` top `chunk-doc-20260611163304-4cbf18e4-27`
- Route-gated semantic: `pass` top `chunk-doc-20260611163304-4cbf18e4-27` enabled `True`
- Drift: `False`
- Question: MI PEP 中 R4 到 R5 之间需要完成哪些工作？

### r0-mi-qmp-deliverable

- Route: `deliverable_detail` / expected `deliverable_detail`
- Lexical: `pass` top `chunk-doc-20260611163304-4cbf18e4-17`
- Semantic: `pass` top `chunk-doc-20260611163304-4cbf18e4-17`
- Route-gated semantic: `pass` top `chunk-doc-20260611163304-4cbf18e4-17` enabled `True`
- Drift: `False`
- Question: MI PEP 中 QMP 需要包含哪些内容？谁负责撰写 QMP？

### r0-xp-agile-tailoring

- Route: `tailoring_policy` / expected `tailoring_policy`
- Lexical: `pass` top `chunk-doc-20260611163330-ea3c2cc8-31`
- Semantic: `pass` top `chunk-doc-20260611163330-ea3c2cc8-31`
- Route-gated semantic: `pass` top `chunk-doc-20260611163330-ea3c2cc8-31` enabled `True`
- Drift: `False`
- Question: XP PEP 采用敏捷方法开发，可以裁剪哪些评审？哪些评审不可被裁剪？

### r0-mi-unknown-fallback

- Route: `generic_rag` / expected `generic_rag`
- Lexical: `pass` top `chunk-doc-20260611163304-4cbf18e4-2`
- Semantic: `pass` top `chunk-doc-20260611163304-4cbf18e4-2`
- Route-gated semantic: `pass` top `chunk-doc-20260611163304-4cbf18e4-2` enabled `True`
- Drift: `False`
- Question: MI PEP 里项目启动前有哪些容易被遗漏但影响后续质量门的准备事项？

### r0-ct-mi-xp-stage-comparison

- Route: `bu_comparison` / expected `bu_comparison`
- Lexical: `pass` top `chunk-doc-20260611163330-ea3c2cc8-70`
- Semantic: `pass` top `chunk-doc-20260611163330-ea3c2cc8-70`
- Route-gated semantic: `pass` top `chunk-doc-20260611163330-ea3c2cc8-70` enabled `True`
- Drift: `False`
- Question: CT、MI、XP 三份 PEP 对 R4 到 R5 阶段转换要求有什么相同点和差异？
