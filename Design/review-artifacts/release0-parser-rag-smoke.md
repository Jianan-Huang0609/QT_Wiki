# Release-0 Parser/RAG Smoke 诊断

日期：2026-06-23

## 结论

`PARSER-MIN-01` 的当前结论是：三份 Release-0 PEP 的 parsed canonical / section chunks / source_refs / anchors / quote 足够支撑当前 8 条 BASE-01 smoke 的大部分问答；本轮没有发现需要立刻引入新 parser provider、OCR 或完整 RAG artifacts bundle 的阻塞。

真实短板集中在 Chat/RAG 的 query rewrite、retrieval rerank 和 route-specific evidence prioritization：8 条 smoke 中 6 条通过，2 条失败都归类为 `chat_route_query_answer_gap`。失败问题的证据在 scoped chunks 中存在，且 matched chunks 均有 `source_ref / anchor / quote`，但 top hits 被较泛的 scope、definition、provisional solution、responsibility 章节抢占。

## 运行命令

```powershell
..\.venv\Scripts\python.exe -c "from Tool.evals.parser_rag_smoke import release0_parser_rag_smoke_report; import json; report=release0_parser_rag_smoke_report(); print(json.dumps({'schema_version': report['schema_version'], 'retrieval_metrics': report['retrieval_metrics'], 'failure_summary': report['failure_summary'], 'cases': [(case['case_id'], case['status'], case['failure_category']) for case in report['case_diagnostics']]}, ensure_ascii=False, indent=2))"
```

## 总览

- Schema：`release0-parser-rag-smoke-v0.1`
- Case count：8
- Recall@8：0.75
- 通过：6
- 失败：2
- 失败分类：`chat_route_query_answer_gap = 2`，`chunk_source_context_gap = 0`，`parser_structure_gap = 0`，`table_gap = 0`，`scanning_ocr_gap = 0`

## Case 结果

| Case | 状态 | 归因 |
| --- | --- | --- |
| `r0-ct-process-operation` | pass | pass |
| `r0-mi-r2-po-guidance` | pass | pass |
| `r0-ct-section-716-reference` | pass | pass |
| `r0-mi-r4-r5-transition` | pass | pass |
| `r0-mi-qmp-deliverable` | fail | `chat_route_query_answer_gap` |
| `r0-xp-agile-tailoring` | fail | `chat_route_query_answer_gap` |
| `r0-mi-unknown-fallback` | pass | pass |
| `r0-ct-mi-xp-stage-comparison` | pass | pass |

## 失败详情

### `r0-mi-qmp-deliverable`

问题：MI PEP 中 QMP 需要包含哪些内容？谁负责撰写 QMP？

- 检索失败点：top hits 缺少预期 section terms：`QMP`、`Quality Management Plan`、`responsibility`。
- scoped chunks：84
- matched chunks：30
- matched chunks source quality：无 source context 缺口；匹配 chunk 均有 source ref、anchor、quote。
- 当前 top hits：`1 Purpose and scope / 目的和适用范围`、`7 Provisional solution and backward method / 过渡措施 和补救办法`、`6.1 GM (Head) of SSME MI / SSME MI 总经理`。
- 初步判断：QMP 证据存在，但 query/rerank 更偏向泛 scope 和过渡措施；下一步应强化 `deliverable_detail` route 对 `QMP / Quality Management Plan / owner / author / responsibility` 的 section/title/path 权重，减少 `Purpose and scope` 抢占。

### `r0-xp-agile-tailoring`

问题：XP PEP 采用敏捷方法开发，可以裁剪哪些评审？哪些评审不可被裁剪？

- 检索失败点：top hits 缺少预期 section terms：`agile`、`tailoring`、`review`。
- scoped chunks：144
- matched chunks：55
- matched chunks source quality：无 source context 缺口；匹配 chunk 均有 source ref、anchor、quote。
- 当前 top hits：`7 Provisional solution and backward method/过渡措施和 补救办法`、`1 Purpose and scope/目的和适用范围`、`6.7.1 Task and responsibilities / 任务和职责`。
- 初步判断：agile/tailoring/review 证据存在，但 query/rerank 被 `XP / PEP` 和通用 responsibility/scope 章节干扰；下一步应强化 `tailoring_policy` route 对 `agile / tailoring / review / mandatory / cannot be tailored` 的证据优先级，并降低 provisional/scope 泛章节。

## 对后续工作的影响

- 当前先做 Chat/RAG 检索层修正，比更换 parser provider 更直接。
- `PARSER-MIN-02 EvidenceSource adapter` 仍有价值，但目的偏 contract 收敛和 UI/Claim Verifier 复用，不是为了补本轮两个失败。
- 完整 `DocumentBlock / RAG artifacts bundle` 和 Docling/Marker/MinerU provider 继续后置，等待出现真实 parser structure、table 或 OCR 阻塞后再启动。
