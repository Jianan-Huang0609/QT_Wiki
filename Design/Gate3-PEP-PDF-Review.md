# Gate 3 PEP PDF Review

更新时间：2026-06-10  
状态：Parser fixes + Gate 4/5 smoke applied; Ready for Human Review  
来源：CT / MI / XP PEP PDF parser smoke  
关联计划：[Parser-Workflow-Evals-实施计划.md](Parser-Workflow-Evals-实施计划.md)

## 1. 如何使用

当前没有可直接查看章节树的 localhost UI。本文件是 Gate 3 的人工核查报告，先用于你在 VS Code 里完成 review。

建议先核查每份 PEP 的三类内容：

- [ ] 章节树：关键章节是否挂对 parent，History / TOC 是否混入正式章节。
- [ ] 关键路径：Purpose、Reference、Definitions、Process / Requirement、system phases、R1-R5 是否能找到。
- [ ] Reference：关键 fragment 的 `heading_path`、page anchor 和原文 quote 是否能支撑 R2/PO 问答。

Review 结论建议直接写在本文件第 6 节。

## 2. 总览

| BU | 文件 | parse_status | sections | fragments | tables | figures | anchors | eval | 当前结论 |
| --- | --- | --- | ---: | ---: | ---: | ---: | ---: | --- | --- |
| CT | `CT PEP AND 308 11.pdf` | `needs_review` | 105 | 1013 | 1 | 2 | 1016 | pass 3 / warn 2 / fail 0 | Content / History 污染已清理到可审状态；7.16 正文标题已拼回完整；P2-01 level jump 和 P1-05 visual review 需要人工确认。 |
| MI | `MI PEP AND 308 11.pdf` | `needs_review` | 75 | 555 | 1 | 1 | 557 | pass 3 / warn 2 / fail 0 | 主体从 History 后进入 Purpose / Reference；部分 process phase parent 错层，P2-01 和 P1-05 需要人工确认。 |
| XP | `XP PEP AND 308 11.pdf` | `needs_review` | 114 | 946 | 1 | 5 | 952 | pass 3 / warn 2 / fail 0 | 前置 History 污染已明显降低；仍有多处 level jump 和 5 个 figure visual review item。 |

共同观察：

- 文档控制页眉、目录点线页码和前置 Content 页已进入 PDF 清理，当前 smoke 没有 P2-03 warning。
- 三份 PEP 都生成了 History `TableData` candidate，History 行不再大面积进入正式 section。
- 三份 PEP 都生成了 figure caption candidate；图内框、箭头和复杂布局仍需要后续 crop + multimodal review。
- 三份 PEP 都有完整 source anchors，因此可以继续进入 Section Chunk / Retrieval 设计；进入问答前需要确认 P2-01 层级 warning。
- Gate 4/5 smoke 已生成 section chunks：CT 146、MI 93、XP 163；figure visual review queue：CT 2、MI 1、XP 5。
- Retrieval smoke 当前结果：R2 查询优先回到 R2 正文/裁剪规则，CT 7.16 regulatory approval plan 在 CT selected-docs scope 排第一。

## 3. CT PEP Review

### 3.1 Workflow Summary

- `parse_status`: `needs_review`
- `counts`: sections 105, fragments 1013, tables 1, figures 2, source_anchors 1016, errors 0
- `structure_quality`: anchor_coverage 1.0, section_confidence 0.997, noise_rate 0.0
- `review_items`: P2-01 warn, `level_jump_sections = [sec-39]`, `rootless_child_sections = []`

### 3.2 前置 Section 样例

| id | level | page | parent | title |
| --- | ---: | --- | --- | --- |
| sec-1 | 1 | 5-7 | - | 0 History / 修改历史 |
| sec-2 | 1 | 7 | - | 1 Purpose and scope / 目的和适用范围 |
| sec-3 | 1 | 7-9 | - | 2 Reference document / 参考文件 |
| sec-4 | 1 | 9 | - | 3 Abbreviations and Definitions / 缩略语与定义 |
| sec-5 | 2 | 9-10 | sec-4 | 3.1 Abbreviations / 缩略语 |
| sec-6 | 1 | 10 | - | R1 R5 |

人工判断点：

- [ ] `0 History` 作为文档历史章节保留是否可接受。
- [ ] History table 已进入 `tbl-1`，版本行不再污染正式章节。
- [ ] 前置 Content / TOC section 已过滤，`rootless_child_sections` 清零。
- [ ] `level_jump_sections = [sec-39]` 仍需要确认是否影响 Retrieval。

### 3.3 关键路径命中

| 检查项 | 命中 section | 初步判断 |
| --- | --- | --- |
| Purpose | `sec-2` L1 p.7 `1 Purpose and scope / 目的和适用范围` | 可用 |
| Reference | `sec-3` L1 p.7-9 `2 Reference document / 参考文件` | 可用 |
| Definitions | `sec-4` L1 p.9 `3 Abbreviations and Definitions / 缩略语与定义` | 可用 |
| Process / Requirement | `sec-23` L1 p.14 `5 Process & Requirement / 过程和需求` | 可用 |
| System phases | `sec-26` L2 p.20-21 `5.3 System development phases and their purpose / 系统开发阶段及其目的` | 可用 |
| Process Phase 1 | `sec-27` L3 p.21 `5.3.1 Process Phase 1: Idea Collection / 过程阶段 1：想法收集` | 可用，编号是 CT 5.3.1 |
| R stages | `sec-6` L1 p.10 `R1 R5` 等 | 命中，仍需确认正文证据粒度 |
| Country-specific approvals | `sec-85` L2 p.49 `7.16 Country-specific approvals (regulatory approval plan) / 特定国家核准（法规核准计划）` | 可用，标题续行已拼回 |

### 3.4 Reference 样例

| fragment | section | page | heading_path | quote |
| --- | --- | --- | --- | --- |
| frag-23 | sec-3 | 7 | 2 Reference document / 参考文件 | `[13] 8596541-AND-008 Milestone Review Checklist 项目结点确认表` |
| frag-24 | sec-3 | 8 | 2 Reference document / 参考文件 | `[14] 8596541-AND-1RD Reference Data for CT-Documents CT 文档参考表` |
| frag-880 | sec-85 | 49 | 7 Document / 文档 > 7.16 Country-specific approvals... | `7.16 Country-specific approvals (regulatory approval plan) / 特定国家核准（法规核准计划）` |

CT 人工结论：

- [ ] 章节树可接受，进入 Retrieval。
- [ ] 需要继续修 parser：原因：
- [ ] 需要补 expected section path eval：原因：

## 4. MI PEP Review

### 4.1 Workflow Summary

- `parse_status`: `needs_review`
- `counts`: sections 75, fragments 555, tables 1, figures 1, source_anchors 557, errors 0
- `structure_quality`: anchor_coverage 1.0, section_confidence 0.9964, noise_rate 0.0
- `review_items`: P2-01 warn, `level_jump_sections = [sec-17, sec-28, sec-44, sec-61]`, `rootless_child_sections = []`

### 4.2 前置 Section 样例

| id | level | page | parent | title |
| --- | ---: | --- | --- | --- |
| sec-1 | 1 | 4 | - | 0 History / 修改历史 |
| sec-2 | 1 | 5 | - | 1 Purpose and scope / 目的和适用范围 |
| sec-3 | 1 | 6 | - | 2 Reference document / 参考文件 |
| sec-4 | 1 | 7 | - | 3 Abbreviations and Definitions / 缩略语与定义 |
| sec-5 | 1 | 7 | - | R1 R5 Design Reviews 设计评审 |
| sec-6 | 1 | 9 | - | 4 Procedure& Requirement / 过程和需求 |

人工判断点：

- [ ] `History` 作为文档历史章节保留是否可接受。
- [ ] 主体章节从 `sec-2` 开始结构较清晰。
- [ ] `sec-17`, `sec-28` 等 process phase parent 错层需要确认是否影响 RAG。

### 4.3 关键路径命中

| 检查项 | 命中 section | 初步判断 |
| --- | --- | --- |
| Purpose | `sec-2` L1 p.5 `1 Purpose and scope / 目的和适用范围` | 可用 |
| Reference | `sec-3` L1 p.6 `2 Reference document / 参考文件` | 可用 |
| Definitions | `sec-4` L1 p.7 `3 Abbreviations and Definitions / 缩略语与定义` | 可用 |
| Procedure | `sec-6` L1 p.9 `4 Procedure& Requirement / 过程和需求` | 可用 |
| 4.3 System phases | `sec-9` L2 p.12 parent `sec-6` | 可用 |
| 4.3.1 Phase 1 | `sec-10` L3 p.12-13 parent `sec-9` | 可用 |
| 4.3.2 Phase 2 | `sec-17` L3 p.15-16 parent `sec-16` | parent 可疑 |
| 4.3.3 Phase 3 | `sec-28` L3 p.18 parent `sec-27` | parent 可疑 |
| R2 | `sec-34` L1 p.20 `R2 To confirm that the system is adequately...` | 命中，需确认正文证据 |

### 4.4 Reference 样例

| fragment | section | page | heading_path | quote |
| --- | --- | --- | --- | --- |
| frag-58 | sec-12 | 10 | 4 Procedure& Requirement > 4.1 V-model | `plans shall identify and describe the interfaces...` |
| frag-63 | sec-12 | 11 | 4 Procedure& Requirement > 4.1 V-model | `The design input requirements shall be documented and shall be reviewed and approved...` |
| frag-64 | sec-12 | 11 | 4 Procedure& Requirement > 4.1 V-model | `The approval, including the date and signature... shall be documented.` |
| frag-134 | sec-19 | 14 | 2 规划项目（负责人：项目经理） | `Quality controls specified in the QMP include participation in selected reviews...` |

MI 人工结论：

- [ ] 章节树可接受，进入 Retrieval。
- [ ] 需要继续修 parser：原因：
- [ ] 需要补 expected section path eval：原因：

## 5. XP PEP Review

### 5.1 Workflow Summary

- `parse_status`: `needs_review`
- `counts`: sections 114, fragments 946, tables 1, figures 5, source_anchors 952, errors 0
- `structure_quality`: anchor_coverage 1.0, section_confidence 0.9926, noise_rate 0.0
- `review_items`: P2-01 warn, `level_jump_sections = [sec-29, sec-51, sec-57, sec-60, sec-69]`, `rootless_child_sections = []`

### 5.2 前置 Section 样例

| id | level | page | parent | title |
| --- | ---: | --- | --- | --- |
| sec-1 | 1 | 6 | - | 1 Purpose and scope / 目的和适用范围 |
| sec-2 | 1 | 6-7 | - | 2 Reference document / 参考文件 |
| sec-3 | 1 | 7 | - | 3 Abbreviations and Definitions / 缩略语与定义 |
| sec-4 | 2 | 7-8 | sec-3 | 3.1 Abbreviations / 缩略语 |
| sec-5 | 1 | 8 | - | R1 R5 Main Reviews 主要评审 |
| sec-6 | 2 | 8 | sec-5 | 3.2 Definitions / 定义 |

人工判断点：

- [ ] 前置目录和 History 行已明显减少，主体从 Purpose 开始。
- [ ] `R1 R5 Main Reviews` 与 `3.2 Definitions` 的 parent 关系需要确认。
- [ ] R2 相关正文证据仍需要继续下钻，避免后续 Retrieval 命中模板变更语境。

### 5.3 关键路径命中

| 检查项 | 命中 section | 初步判断 |
| --- | --- | --- |
| Purpose | `sec-1` L1 p.6 `1 Purpose and scope / 目的和适用范围` | 可用 |
| Reference | `sec-2` L1 p.6-7 `2 Reference document / 参考文件` | 可用 |
| Definitions | `sec-3` L1 p.7 `3 Abbreviations and Definitions / 缩略语与定义` | 可用 |
| Process / Requirement | `sec-11` L1 p.9 `5 Process & Requirement / 过程和需求` | 可用 |
| 5.3 Structure | `sec-26` L2 p.13 parent `sec-24` | 可用但 parent 可疑 |
| R stages | `sec-5` `R1 R5 Main Reviews`, `sec-16` R2 | 命中，需确认正文证据 |

### 5.4 Reference 样例

| fragment | section | page | heading_path | quote |
| --- | --- | --- | --- | --- |
| frag-69 | sec-16 | 9 | R2 | `R2` |
| frag-136 | sec-30 | 14 | 5.3.2 Review items & milestones in PLM | `5.3.2 Review items & milestones in PLM...` |
| frag-185 | sec-41 | 17 | R2 closer to R3, below procedures must be followed | `additional main review R2'... DHF and DMR are checked for consistency and completeness` |
| frag-188 | sec-41 | 17 | R2 closer to R3, below procedures must be followed | `after the main review R2... a M230 decision... before the main review R3` |

XP 人工结论：

- [ ] 章节树可接受，进入 Retrieval。
- [ ] 需要继续修 parser：原因：
- [ ] 需要补 expected section path eval：原因：

## 6. 你的 Review 结论

请在这里写你的判断，或直接勾选。

### 6.1 Gate 3 是否可进入下一步

- [ ] 可以进入 Section Chunk / Retrieval MVP，保留 P2-01 warning 作为人工风险。
- [ ] 继续修 PEP parser，重点是 4.3.x / 5.3.x parent 错层和复杂表格/图片结构。
- [ ] 先补 expected section path eval，再决定是否进入 Retrieval。

### 6.2 必须修的 parser 问题

- [x] History table 行误入正式 section：本轮已修，需抽样复核 CT / MI / XP。
- [x] TOC / 前置目录项误入正式 section：本轮已修，需抽样复核前 10 页。
- [x] 双语标题续行截断影响理解：CT 7.16 已拼回完整，需继续观察其他 PDF。
- [ ] 4.3.x / 5.3.x process phase parent 错层。
- [x] R2/PO retrieval MVP 已降权 History/template change，并修正 `PO` 子串误命中；仍需 Answer Eval 判断最终回答是否有足够角色证据。

备注：

```text

```

### 6.3 下一步建议

推荐下一步是补 Answer Evidence Package 和 groundedness eval：先把 retrieval hits 变成带 citation 的回答输入，再做最小 Session Query API。Review UI 可并行读取 section tree、chunks、review_items 和 visual_review_items。
