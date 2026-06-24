# Router Shadow Diff

Schema: `router-shadow-diff-v0.1`

## Summary

- Cases: 6
- Matched: 5
- Findings: 1
- Match rate: 0.8333

## Decision Notes

- `stage_transition_work`、`deliverable_detail`、`tailoring_policy`、`bu_comparison` 和 source-location follow-up 在本轮 GPT-5.4 shadow 中与规则 route 一致，可继续用当前规则作为稳定 pre-router / regression oracle。
- `r0-mi-unknown-fallback` 出现 `fallback_mismatch`：规则 route 保守降级 `generic_rag`，LLM shadow 选择 `process_operation`。该类开放式“容易遗漏/准备事项/质量门影响”问题适合进入 `route evolution eval`，暂时不退役 `generic_rag` guardrail。
- Source-location follow-up 本轮 matched，但仍保留程序级 source-location guardrail：该类问题直接关系上一轮 citation 继承和 source scope，LLM route 不应单独接管。

## Cases

### r0-mi-r4-r5-transition

- Classification: `matched`
- Expected: `stage_transition_work`
- Rule route: `stage_transition_work`
- LLM route: `stage_transition_work`
- Question: MI PEP 中 R4 到 R5 之间需要完成哪些工作？

### r0-mi-qmp-deliverable

- Classification: `matched`
- Expected: `deliverable_detail`
- Rule route: `deliverable_detail`
- LLM route: `deliverable_detail`
- Question: MI PEP 中 QMP 需要包含哪些内容？谁负责撰写 QMP？

### r0-xp-agile-tailoring

- Classification: `matched`
- Expected: `tailoring_policy`
- Rule route: `tailoring_policy`
- LLM route: `tailoring_policy`
- Question: XP PEP 采用敏捷方法开发，可以裁剪哪些评审？哪些评审不可被裁剪？

### r0-mi-unknown-fallback

- Classification: `fallback_mismatch`
- Expected: `generic_rag`
- Rule route: `generic_rag`
- LLM route: `process_operation`
- Question: MI PEP 里项目启动前有哪些容易被遗漏但影响后续质量门的准备事项？

### r0-ct-mi-xp-stage-comparison

- Classification: `matched`
- Expected: `bu_comparison`
- Rule route: `bu_comparison`
- LLM route: `bu_comparison`
- Question: CT、MI、XP 三份 PEP 对 R4 到 R5 阶段转换要求有什么相同点和差异？

### r0-source-location-follow-up

- Classification: `matched`
- Expected: `reference_lookup`
- Rule route: `reference_lookup`
- LLM route: `reference_lookup`
- Question: 在原文的哪里？
