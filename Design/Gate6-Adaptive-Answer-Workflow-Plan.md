# Gate 6 Adaptive Answer Workflow Plan

更新时间：2026-06-10  
状态：Planning Accepted  
关联计划：[Parser-Workflow-Evals-实施计划.md](Parser-Workflow-Evals-实施计划.md)  
前置基础：[Gate3-PEP-PDF-Review.md](Gate3-PEP-PDF-Review.md)、[Pro-Input-Praser.md](Pro-Input-Praser.md)

## 1. 设计结论

Gate 6 采用 **自适应主 Chat Answer Workflow**：核心事实必须带 reference，输出格式按问题意图变化。Prompt 只执行已经解析好的 `intent + enterprise keywords + evidence package + style policy`，不承担全部业务理解。

目标是让用户在主 chat 里问“R2 阶段我作为 PO 应该做什么”时，系统能先识别这是流程合规型角色任务问题，再用企业关键词归一和 retrieval evidence 生成答案，而不是每次套同一个报告模板。

## 2. 核心原则

- Reference 强制：涉及流程、角色、交付物、章节、BU 差异、合规判断的关键事实都要有 citation。
- 版式自适应：不固定每次都输出“结论/步骤/Reference”三段式；只有问题需要时才使用 checklist、表格或分节标题。
- 企业关键词共享：R2、M150、PO、Product Owner、QMP、PMP、regulatory approval plan 等词先进入统一归一层，再参与 retrieval 和 answer。
- Evidence first：答案只基于 `source_refs.quote`、section/title/page/table/figure anchors 和 retrieval trace。
- 缺口可见：证据不足时说明缺哪些文档、章节或角色信息。
- History 降权：History/template change 只作为版本背景，不作为正式流程步骤依据。

## 3. Workflow

```text
User question
  -> Question Intent Parser
  -> Enterprise Keyword Normalizer
  -> Source Scope / Retrieval Strategy
  -> Retrieval Result
  -> Answer Evidence Package
  -> Adaptive Answer Composer
  -> Answer Groundedness Eval
  -> AnswerPackage for UI
```

LLM 可以参与 answer composition，但不决定 evidence 是否可信。可信度、citation 完整性和缺口状态由 workflow / eval 计算。

## 4. Question Intent Contract

首版 `QuestionIntent` 建议字段：

```json
{
  "intent_type": "role_action_guidance",
  "question_terms": ["R2", "PO", "evidence"],
  "normalized_terms": {
    "stage": ["R2"],
    "role": ["Product Owner"],
    "deliverable": ["QMP"]
  },
  "source_scope_hint": "selected_docs_or_all_sources",
  "answer_shape": "adaptive_guidance",
  "reference_density": "high",
  "risk_level": "process_compliance",
  "requires_abstention_check": true
}
```

首版 intent types：

| intent_type | 典型问题 | 默认输出倾向 | Reference 密度 |
| --- | --- | --- | --- |
| `role_action_guidance` | R2 阶段我作为 PO 应该做什么 | 简短结论 + 行动 checklist + evidence | high |
| `process_explanation` | PEP 的流程如何操作 | 顺序解释 + 关键节点 | medium/high |
| `reference_lookup` | 7.16 在哪个文件哪个章节 | 文件/章节/page/quote 列表 | high |
| `bu_comparison` | CT 和 XP 的 R2 有什么差异 | 差异表 + 分 BU 引用 | high |
| `definition_lookup` | QMP 是什么 | 短解释 + 原文引用 | medium |
| `training_generation` | 做成培训材料 | 教学步骤 / quiz / note | medium |
| `gap_check` | 现在证据够不够 | 已有证据 + 缺口 | high |

## 5. Enterprise Keyword Lexicon

企业关键词不是静态硬编码词表，而是从 parser / chunk / retrieval 产物中积累：

- `signals`：来自 chunk，例如 `stage_r2`、`role_product_owner`、`deliverable_qmp`。
- `aliases`：来自原文和人工确认，例如 `PO -> Product Owner`。
- `source_refs`：每个关键词应尽量保留来源 document / section / quote。
- `review_status`：未确认 alias 先作为 candidate，不能直接改写正式术语。

最小可先用规则词典实现：R 阶段、M milestone、常见角色、常见交付物、BU 名称和章节号。后续再接人工 review backflow。

## 6. Adaptive Prompt Policy

Prompt 分两层。

Always-on 约束：

- 只基于 evidence package 回答。
- 每个关键事实必须有 citation。
- 没有证据时说明缺口。
- 保留公司流程原始术语，避免随意改写。
- History/template change 只可作为版本背景。

Conditional 约束：

- `role_action_guidance`：回答“要做什么、产出什么 evidence、谁参与、何时进入下一节点”。
- `process_explanation`：回答流程顺序、阶段关系和关键门禁。
- `bu_comparison`：按 BU 对齐差异，并标明每个差异的来源。
- `reference_lookup`：优先输出文件、章节、page/line/table、quote。
- `gap_check`：区分“已有证据”和“缺失证据”。
- `training_generation`：允许更教学化，但关键流程事实仍要带 reference。

防套路规则：

- 不强制每次使用同一组标题。
- 不强制每次输出表格。
- 短问题可以短答，复杂问题再展开。
- Reference 可以自然嵌入正文，也可以在末尾集中列出；UI 层可再折叠展示。

## 7. Answer Evidence Package

Gate 6 第一段实现应先固定 evidence package，而不是直接写 prompt。

建议结构：

```json
{
  "question": "R2阶段我作为PO应该做什么",
  "intent": {},
  "source_scope": {},
  "strategy_used": "scoped_section_retrieval",
  "evidence_items": [
    {
      "evidence_id": "ev-1",
      "document_id": "ct-pep",
      "file_name": "CT PEP AND 308 11.pdf",
      "section_id": "sec-...",
      "section_title": "...",
      "anchor_label": "p.21",
      "quote": "...",
      "signals": ["stage_r2", "role_product_owner"],
      "supports": ["stage", "role", "deliverable"]
    }
  ],
  "coverage": {
    "documents": ["ct-pep"],
    "sections": ["sec-..."],
    "missing": []
  }
}
```

## 8. AnswerPackage

前端消费统一 `AnswerPackage`：

```json
{
  "answer_text": "...",
  "answer_shape": "adaptive_guidance",
  "citations": [],
  "intent": {},
  "source_scope": {},
  "evidence_coverage": {},
  "missing_evidence": [],
  "eval_summary": {},
  "trace": []
}
```

其中 `answer_shape` 只是渲染提示，不是固定模板。

## 9. Answer Evals

Gate 6 eval 先覆盖四类：

| ID | 目标 | 检查点 |
| --- | --- | --- |
| A1-01 | Groundedness | 答案关键事实是否能匹配 evidence quote 或 source ref |
| A1-02 | Citation completeness | 流程、角色、交付物、BU 差异是否有 citation |
| A1-03 | Abstention correctness | 证据不足时是否说明缺口，而不是编造 |
| A1-04 | Adaptive format | 输出是否匹配 intent，且没有机械套模板 |
| A1-05 | Keyword normalization | PO/R2/QMP 等企业关键词是否正确归一 |

## 10. 最小实现顺序

- [ ] G6-01：实现 `QuestionIntent` 规则解析 MVP，覆盖 R 阶段、角色、交付物、BU diff、reference lookup。
- [ ] G6-02：实现企业关键词归一 MVP，先用规则词典 + chunk signals。
- [ ] G6-03：把 `RetrievalResult` 转成 `AnswerEvidencePackage`。
- [ ] G6-04：实现 adaptive prompt builder，只接收 intent + evidence package。
- [ ] G6-05：实现 `AnswerPackage` 和 answer eval MVP。
- [ ] G6-06：补最小 Session Query API，返回 answer、citations、intent、trace、eval_summary。

## 11. 下一步建议

最适合马上做的是 **G6-01 + G6-03**：先不接真实 LLM，把问题意图解析和 evidence package 固定下来。这样可以继续用 deterministic tests 验证：

- R2/PO 问题被识别为 `role_action_guidance`。
- `PO` 归一为 `Product Owner`。
- Evidence package 只包含带 source refs 的 retrieval hits。
- History/template change 不成为 primary evidence。

这一步完成后，再接 adaptive prompt builder 会更稳，因为 prompt 只是消费结构化上下文。