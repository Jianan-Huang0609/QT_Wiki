# Composer Migration Risk

更新时间：2026-06-24

## 目标

在把 `_session_deterministic_answer()` 继续收敛为 AnswerPlan-driven composer 前，先保留现有 route-specific 分支的边界行为，避免迁移后丢掉已验证的人审体验。

## 风险矩阵

| Route | 当前重要行为 | 迁移风险 | 保留规则 |
| --- | --- | --- | --- |
| `process_operation` | 按流程操作主线组织，优先覆盖范围、步骤、交付和验证。 | 退回章节罗列，回答变成 section 摘要。 | filled slot 用 evidence summary；partial slot 显示可支撑部分；missing slot 写入边界提示。 |
| `stage_transition_work` | R4->R5 等阶段转换优先覆盖工作项、评审、交付物、进入/退出条件。 | 漏掉关键活动或把 CT 专用内容写死。 | 只从 bound evidence 中抽取活动；禁止无证据注入固定清单。 |
| `deliverable_detail` | QMP/PMP 等交付物问题优先找内容要求、责任、维护/批准证据。 | 内容和责任混在一起，责任主体无 citation。 | 责任主体 claim 必须绑定 citation；缺责任证据时显式提示。 |
| `tailoring_policy` | 敏捷裁剪问题区分 permission 与 constraints。 | 只回答可裁剪，漏掉不可裁剪/mandatory 边界。 | `permission` 与 `constraint` 分 slot；constraint 缺证时标记高风险缺口。 |
| `reference_lookup` | source-location follow-up 复用上一轮 citation anchors。 | 重新发散检索，引用漂移。 | source-location route 优先 previous citation；保留同文档 scope。 |
| `generic_rag` | 未知问题仍输出短结论、证据和不确定性。 | 被强行套入专业 route 或回答过度确定。 | 低置信或缺证据保留 fallback reason 和 evidence boundary。 |
| `table_lookup` | 已有 TableData 时使用 table metadata/rerank；真实 PDF 表格缺口归 parser/evidence quality。 | 把普通文本关系误写成 cell-level 事实。 | 无 table/evidence source warning 时才输出表格级结论。 |

## Slot 呈现规则

| Slot 状态 | AnswerPlan 行为 | Composer 行为 |
| --- | --- | --- |
| `filled` | 有 `citation_ids/evidence_ids/evidence_bindings`。 | 可以写成直接结论，并带 citation。 |
| `partial` | 有相关 evidence，但缺 required term 或缺 responsibility/table anchor。 | 只写已支撑部分，附边界说明。 |
| `missing` | 无可用 evidence binding。 | 不编造；写入缺口或建议缩小问题。 |

## 后续测试要求

- Composer 迁移测试至少覆盖 filled / partial / missing 三类 slot。
- `reference_lookup` 必须保留三轮 follow-up smoke。
- `table_lookup` 迁移前先检查 `evidence_sources.quality_warning`。