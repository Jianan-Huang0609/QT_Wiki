# CT PEP 人审版 Markdown

源文件：`CT PEP AND 308 11.pdf`
Document id：`doc-20260611142812-f56c6cf9`
Parsed JSON：`Tool/output/parsed/doc-20260611142812-f56c6cf9.json`

> 这份文件给人审使用：先看 parser 抓取是否对，再看图像/表格/证据是否能支撑 RAG 和 LLM。RAG/LLM 部分只需要判断 quote 是否支撑答案，不需要理解算法。

## 1. 人审结论

- [ ] 抽取通过
- [ ] 抽取基本通过，需小修
- [ ] 需要修 parser
- [ ] 需要补图像/OCR review
- [ ] 需要修 RAG/answer 证据

## 2. Parse Summary

| 字段 | 值 |
| --- | --- |
| parse_status | `needs_review` |
| sections | `105` |
| fragments | `1013` |
| tables | `1` |
| figures | `2` |
| source_anchors | `1016` |
| errors | `0` |
| eval_summary | `{"pass": 3, "warn": 2, "fail": 0, "na": 0}` |
| structure_quality | `{"anchor_coverage": 1.0, "section_confidence": 0.997, "noise_rate": 0.0, "low_confidence_count": 2, "quality_issue_count": 2}` |

你看什么：
- [ ] `parse_status` 是否符合你对原文质量的判断。
- [ ] `fail/warn` 是否能解释。
- [ ] `anchor_coverage` 是否足够支撑引用。

## 3. Provider / Fusion Trace

| 字段 | 值 |
| --- | --- |
| schema_version | `parser-fusion-v0.1` |
| fusion_mode | `single_provider_passthrough` |
| providers | `["pypdf_fast_text"]` |
| provider_roles | `{"pypdf_fast_text": "fast_text"}` |
| fusion counts | `{"extraction_blocks": 0, "layout_blocks": 0, "table_blocks": 0, "visual_candidates": 0, "fusion_decisions": 0}` |

你看什么：
- [ ] PDF provider trace 存在。
- [ ] metadata 能解释抓取结果从哪里来。
- [ ] 如果有低置信 fusion decision，能进入 review。

## 4. 章节树

重点看开头、History/TOC、R2/R3、7.16 是否正确。

| # | Level | Title | Parent | Pages | Fragments |
| ---: | ---: | --- | --- | --- | ---: |
| 1 | 1 | 0 History/ 修改历史 |  | [5, 6, 7] | 3 |
| 2 | 1 | 1 Purpose and scope / 目的和适用范围 |  | [7] | 10 |
| 3 | 1 | 2 Reference document / 参考文件 |  | [7, 8, 9] | 20 |
| 4 | 1 | 3 Abbreviations and Definitions/ 缩略语与定义 |  | [9] | 1 |
| 5 | 2 | 3.1 Abbreviations/ 缩略语 | 3 Abbreviations and Definitions/ 缩略语与定义 | [9, 10] | 11 |
| 6 | 1 | R1 R5 |  | [10] | 5 |
| 7 | 1 | R5 Product successfully validated, no open |  | [10] | 6 |
| 8 | 1 | R5 产品已成功确认，文档中无未解 |  | [10, 11] | 7 |
| 9 | 2 | 3.2 Definitions / 定义 | R5 产品已成功确认，文档中无未解 | [11] | 1 |
| 10 | 3 | 3.2.1 Engineering sample/prototype / 工程样机（EM） | 3.2 Definitions / 定义 | [11] | 3 |
| 11 | 3 | 3.2.2 Drawing sample/prototype (ZM) / 图纸样机 (ZM) | 3.2 Definitions / 定义 | [11] | 4 |
| 12 | 3 | 3.2.3 Production sample/prototype/ 生产样机（FM） | 3.2 Definitions / 定义 | [11] | 5 |
| 13 | 3 | 3.2.4 Formative evaluation/ 形成性评估 | 3.2 Definitions / 定义 | [11] | 3 |
| 14 | 3 | 3.2.5 Summative evaluation/ 总结性评估 | 3.2 Definitions / 定义 | [11] | 3 |
| 15 | 3 | 3.2.6 eSW/嵌入式软件 | 3.2 Definitions / 定义 | [11, 12] | 8 |
| 16 | 3 | 3.2.7 Intended Use/ 预期用途 | 3.2 Definitions / 定义 | [12] | 4 |
| 17 | 3 | 3.2.8 Intended Purpose/ 预期目的 | 3.2 Definitions / 定义 | [12] | 4 |
| 18 | 3 | 3.2.9 Software Component/ 软件组件 | 3.2 Definitions / 定义 | [12] | 3 |
| 19 | 3 | 3.2.10 Non-Product Software/ 非产品软件 | 3.2 Definitions / 定义 | [12] | 4 |
| 20 | 3 | 3.2.11 Component/组件 | 3.2 Definitions / 定义 | [12] | 3 |
| 21 | 3 | 3.2.12 Hardware Component/硬件组件 | 3.2 Definitions / 定义 | [12, 13] | 4 |
| 22 | 1 | 4 Flow chart / 流程图 |  | [13, 14] | 3 |
| 23 | 1 | 5 Process & Requirement/ 过程和需求 |  | [14] | 1 |
| 24 | 2 | 5.1 V-model/Requirement Tracing/ V 型模式/需求跟踪 | 5 Process & Requirement/ 过程和需求 | [14, 15, 16, 17, 18, 19] | 65 |
| 25 | 2 | 5.2 Structure of the Product Engineering Process/ 产品设计过程结构 | 5 Process & Requirement/ 过程和需求 | [19, 20] | 15 |
| 26 | 2 | 5.3 System development phases and their purpose/ 系统开发阶段及其目的 | 5 Process & Requirement/ 过程和需求 | [20, 21] | 17 |
| 27 | 3 | 5.3.1 Process Phase 1: Idea Collection / 过程阶段 1：想法收集 | 5.3 System development phases and their purpose/ 系统开发阶段及其目的 | [21] | 4 |
| 28 | 3 | 5.3.2 Process Phase 2: Product Definition / 过程阶段 2：产品定义 | 5.3 System development phases and their purpose/ 系统开发阶段及其目的 | [21, 22, 23, 24, 25] | 90 |
| 29 | 3 | 5.3.3 Process Phase 3: Product Development / 过程阶段 3：产品开发 | 5.3 System development phases and their purpose/ 系统开发阶段及其目的 | [25, 26, 27, 28, 29] | 110 |
| 30 | 3 | 5.3.4 Process Phase 4: Product Support / 过程阶段 4：产品支持 | 5.3 System development phases and their purpose/ 系统开发阶段及其目的 | [29, 30, 31, 32] | 42 |
| 31 | 1 | 6 General requirements/ 通用要求 |  | [32] | 1 |
| 32 | 2 | 6.1 Design and development planning/ 设计和开发计划 | 6 General requirements/ 通用要求 | [32] | 5 |
| 33 | 2 | 6.2 Tailoring/ 裁减 | 6 General requirements/ 通用要求 | [32] | 1 |
| 34 | 3 | 6.2.1 Project Specific Tailoring/ 项目特定裁减 | 6.2 Tailoring/ 裁减 | [32] | 6 |
| 35 | 3 | 6.2.2 Software Specific Tailoring/ 软件特定裁减 | 6.2 Tailoring/ 裁减 | [32] | 3 |
| 36 | 3 | 6.2.3 Standard Tailoring for Successor Versions of Platform Release/ 平台发布后续版本的标 | 6.2 Tailoring/ 裁减 | [32] | 3 |
| 37 | 1 | R1 /R2 and M120/M150/M200 can be combined |  | [32] | 3 |
| 38 | 1 | R2 |  | [32] | 3 |
| 39 | 3 | 6.2.4 Standard Tailoring for Agile Approaches during Product Development/ 产品开发期间敏 | R2 | [32, 33] | 19 |
| 40 | 2 | 6.3 Requirements for the product/ 产品需求 | R2 | [33] | 3 |
| 41 | 2 | 6.4 Further Requirements for Development and Maintenance/开发和维护的进一步要求 | R2 | [33] | 1 |
| 42 | 3 | 6.4.2 Claims/ 声明 | 6.4 Further Requirements for Development and Maintenance/开发和维护的进一步要求 | [33] | 5 |
| 43 | 3 | 6.4.3 Product Security/ 产品网络安全 | 6.4 Further Requirements for Development and Maintenance/开发和维护的进一步要求 | [33] | 2 |
| 44 | 3 | 6.4.4 AI Systems/ 人工智能系统 | 6.4 Further Requirements for Development and Maintenance/开发和维护的进一步要求 | [33, 34] | 4 |
| 45 | 2 | 6.5 Requirement tracing/ 需求追踪 | R2 | [34] | 3 |
| 46 | 2 | 6.6 Automated processes/ 自动过程 | R2 | [34] | 4 |
| 47 | 2 | 6.7 Risk management/ 风险管理 | R2 | [34] | 6 |
| 48 | 2 | 6.8 Product Reliability/产品可靠性 | R2 | [34] | 7 |
| 49 | 2 | 6.9 Product-Related Environmental Protection | R2 | [34, 35] | 5 |
| 50 | 2 | 6.10 Standards & Laws/ 标准和法律 | R2 | [35] | 3 |
| 51 | 2 | 6.11 Patents and trademarks/ 专利和商标 | R2 | [35] | 7 |
| 52 | 2 | 6.12 Procurement and Use of Third-Party Software/ 采购和第三方软件使用 | R2 | [35] | 7 |
| 53 | 2 | 6.13 Preventive action/ 预防措施 | R2 | [35, 36] | 6 |
| 54 | 2 | 6.14 Concurrent engineering/ 并行开发 | R2 | [36] | 3 |
| 55 | 2 | 6.15 Transfer to Production/ 生产转移 | R2 | [36] | 7 |
| 56 | 3 | 6.16.1 Changes during product development/ 产品开发中的更改 | 6.15 Transfer to Production/ 生产转移 | [36] | 8 |
| 57 | 3 | 6.16.2 Changes after Release /Product enhancements/ 发布后的变更/产品增强 | 6.15 Transfer to Production/ 生产转移 | [36] | 3 |
| 58 | 2 | 6.17 Design review / Technical review/ 设计评审/技术评审 | R2 | [36] | 1 |
| 59 | 3 | 6.17.1 Design review/ 设计评审 | 6.17 Design review / Technical review/ 设计评审/技术评审 | [36, 37] | 13 |
| 60 | 3 | 6.17.2 Technical review / Content review/ 技术评审/内容评审 | 6.17 Design review / Technical review/ 设计评审/技术评审 | [37] | 4 |
| 61 | 2 | 6.18 Project phase application/ 项目阶段申请 | R2 | [37] | 7 |
| 62 | 2 | 6.19 Handling Deviations/偏差处理 | R2 | [37, 38] | 6 |
| 63 | 2 | 6.20 Design verification/ 设计验证 | R2 | [38] | 16 |
| 64 | 2 | 6.21 Design validation/ 设计确认 | R2 | [38, 39, 40] | 36 |
| 65 | 2 | 6.22 Process validation/ 过程确认 | R2 | [40] | 5 |
| 66 | 2 | 6.23 Clinical evaluation/ 临床评估 | R2 | [40] | 14 |
| 67 | 2 | 6.24 Software Development/软件开发 | R2 | [40] | 3 |
| 68 | 2 | 6.25 OTS Software/ 现成软件 | R2 | [40, 41] | 6 |
| 69 | 2 | 6.26 Unique Device Identification/ 唯一的设备识别 | R2 | [41] | 3 |
| 70 | 1 | 7 Document/ 文档 |  | [41] | 1 |
| 71 | 2 | 7.1 Document management/ 文档管理 | 7 Document/ 文档 | [41] | 9 |
| 72 | 2 | 7.2 Quality management plan (QMP)/ 质量管理计划 （QMP） | 7 Document/ 文档 | [41, 42] | 9 |
| 73 | 2 | 7.3 Project management plan (PMP) / 项目管理计划（PMP） | 7 Document/ 文档 | [42, 43] | 12 |
| 74 | 2 | 7.4 Product requirements specification level/ 产品需求规范层级 | 7 Document/ 文档 | [43] | 25 |
| 75 | 2 | 7.5 System requirements specification level/ 系统需求说明级别 | 7 Document/ 文档 | [43, 44, 45] | 41 |
| 76 | 2 | 7.6 Subsystem / component level/ 子系统/部件级别 | 7 Document/ 文档 | [45, 46] | 12 |
| 77 | 2 | 7.7 System Realization concept/ 系统实施概念 | 7 Document/ 文档 | [46] | 3 |
| 78 | 2 | 7.8 Test concept/ 测试概念 | 7 Document/ 文档 | [46] | 6 |
| 79 | 2 | 7.9 Results from risk management/ 来自于风险管理的结果 | 7 Document/ 文档 | [46] | 3 |
| 80 | 2 | 7.10 Error prevention report/错误预防报告 | 7 Document/ 文档 | [46, 47] | 4 |
| 81 | 2 | 7.11 Document plan / design history file (DHF) / 文档计划/设计历史文件（DHF） | 7 Document/ 文档 | [47, 48] | 25 |
| 82 | 2 | 7.13 Device master record (DMR)/ 产品制造性文档（DMR） | 7 Document/ 文档 | [48] | 8 |
| 83 | 2 | 7.14 Medical Device File (MDF)/ 医疗器械文档（MDF） | 7 Document/ 文档 | [48, 49] | 10 |
| 84 | 2 | 7.15 Technical documentation/ 技术文档 | 7 Document/ 文档 | [49] | 7 |
| 85 | 2 | 7.16 Country-specific approvals (regulatory approval plan) / 特定国家核准（法规核准计划） | 7 Document/ 文档 | [49] | 7 |
| 86 | 2 | 7.17 Affidavit for Service Software/ 服务软件宣誓书 | 7 Document/ 文档 | [49] | 4 |
| 87 | 2 | 7.18 Usability engineering file/ 可用性工程文件 | 7 Document/ 文档 | [49, 50] | 4 |
| 88 | 2 | 7.19 System flowchart/ 系统流程图 | 7 Document/ 文档 | [50] | 3 |
| 89 | 2 | 7.20 Accompanying documents/ 随机文档 | 7 Document/ 文档 | [50] | 6 |
| 90 | 2 | 7.21 Financial product plan (FPP) / 财务产品计划 | 7 Document/ 文档 | [50] | 4 |

只展示前 90 个 section，完整列表见 `sections.json`。

你看什么：
- [ ] `Content` / TOC 没有污染正文。
- [ ] `History` 行没有冒充流程章节。
- [ ] R2/R3 是正文，不是目录或模板历史。
- [ ] 7.16 标题完整，中文法规术语没有明显缺字。

## 5. 关键章节摘录

### Purpose
- Section `sec-2`: 1 Purpose and scope / 目的和适用范围 pages=[7]
  - p.7：1 Purpose and scope / 目的和适用范围
  - p.7：This CT QR shall be effective for SSME CT where the QMM [6] is applicable.
  - p.7：本程序适用于在质量管理手册 [6]适用范围内的 SSME CT。
- Section `sec-17`: 3.2.8 Intended Purpose/ 预期目的 pages=[12]
  - p.12：3.2.8 Intended Purpose/ 预期目的
  - p.12：Intended purpose means the use for which a device is intended according to the data supplied by the manufacturer on the label, in the instructions for use or in promotional or sales materials or statements
  - p.12：and as specified by the manufacturer in the clinical evaluation.
- Section `sec-26`: 5.3 System development phases and their purpose/ 系统开发阶段及其目的 pages=[20, 21]
  - p.20：5.3 System development phases and their purpose/ 系统开发阶段及其目的
  - p.20：The details below describe the sections of the development process and their purpose in chronological order. The end-of-phase output required for the design reviews is described in [13] or [14].
  - p.20：[13] is dedicated used for SOMARIS 5 project.

### Reference
- Section `sec-3`: 2 Reference document / 参考文件 pages=[7, 8, 9]
  - p.7：2 Reference document / 参考文件
  - p.7：[1] 5521906-AND-305 Change Control Procedure 修改控制程序 [2] 4791600-QMS-700 Standard Operating Procedure Supplier Quality Management 供应商质量管理 标准操作 程序 [3] 8596541-AND-107 Design Transfer Guidance 设计转移指导书
  - p.7：[4] 5521906-AND-319 Process Validation and Verification Procedure 过程确认与验证程序 [5] 5521906-AND-348 Customer Complaint Handling Procedure 用户抱怨处理程序 [6] 5521906-AND-300 Quality Management Manual (QMM) 质量管理手册

### R2
- Section `sec-37`: R1 /R2 and M120/M150/M200 can be combined pages=[32]
  - p.32：R1/R2 and M120/M150/M200 can be combined
  - p.32：to one R and one M milestone: R2/M200.
  - p.32：Required milestone inputs are the sum of R1 and
- Section `sec-38`: R2 pages=[32]
  - p.32：R2.
  - p.32：平台的第一个版本开发经历所有主评审 （M120， R1，M150，R2，M200）。
  - p.32：标准裁减： 对于后续项目R1 / R2和 M120 / M150 / M200 可以组合为一个 R 和一个 M 主评审：R2 / M200。 所需的评审输入是 R1 和 R2 的总和。

### R3
- 未命中，需要人工看原文确认。

### 7.16 country approvals
- Section `sec-85`: 7.16 Country-specific approvals (regulatory approval plan) / 特定国家核准（法规核准计划） pages=[49]
  - p.49：7.16 Country-specific approvals (regulatory approval plan) / 特定国家核准（法规核准计划）
  - p.49：Following M150, the project manager and the regulatory affair team define the work packages, evidence, and documentation required in order to obtain the country-specific approval and
  - p.49：summarize these requirements in a regulatory Applications for approval are submitted by quality management department.

## 6. 表格

### Table 1 `tbl-1`
- Section:
- Anchor: p.5
- Rows: 9

| Row | Content |
| ---: | --- |
| 1 | Nr \| Page \| Version \| Change description \| CR No. |
| 2 | 1 \| All \| 01 \| Initial creation, the content transferred from 55 21 906 – AND – 008 – 007 due to SSME QMS restructuring. \| N.A. |
| 3 | 2 \| All \| 02 \| Change content: Alignment w/ process manual 4791500-AND-105 to cover both Emotion and aCTivate product development. \| P10222 |
| 4 | 3 \| All \| 03 \| Main changes: combine system and software projects milestones; shift R3 befor e product verification; other adaptions like renamings MEP→CUT, V&V descriptions and requirement levels rework, etc. \| P10351 |
| 5 | 4 \| All \| 04 \| Change content: Adapt MEDDEV 2.7.1 Revision 4; Adapt ISO 13485: 2016; Reference document name update. Add UDI requirement Add software development requirement. Update the requirement for CT QR4 4791500-AND-105-17. \| P10371, P10380, P10414, P10440, |
| 6 | 5 \| All \| 05 \| E-QMS Project P10626 \|  |
| 7 | 6 \| All \| 06 \| Update due to QR28-Product Reliability Management PCR10803 \|  |
| 8 | 7 \| All \| 07 \| Chang Reason: 1. supplier management procedure change. and QR28 was integrated into QR0 2. CT20210014-for wrong reference of “the supplier Quality management procedure”. Chang Content: 1.Change the reference from 5521906-AND-304 to 4791600-QMS-700 “SOP - DI Supplier Quality Management 2.Change reference from 11106079-AND-02S QR28-Product Reliability Management to 11106101-AND-02S QR0-Basic Quality Requirements for Business Areas/Lines and Technology Excellence Units Appendix 2 roles updated, reference doc. updated 5521906-AND-269 change to 5521906-AND-376 5521906-AND-285 change to 5521906-AND-378 PCR 10872 \|  |

你看什么：
- [ ] History table 是否进入 table，而不是污染 section。
- [ ] 职责/交付物表格是否列对齐。
- [ ] 表格有 page/line/table anchor 可引用。

## 7. 图像 / Figure / Visual Review

- `fig-1` page=15 section=None caption=Figure 1/图 1: V-model/V 字型模式
- `fig-2` page=20 section=None caption=Figure 2/图 2： Structure of the product engineering process/ 产品设计过程结构

### visual_review_items
- eval=P1-05 status=needs_review item={'review_id': 'visual-doc-20260611142812-f56c6cf9-fig-1', 'eval_id': 'P1-05', 'source_type': 'figure', 'source_id': 'fig-1', 'page': 15, 'recommended_tool': 'multimodal', 'reason': 'figure caption exists but diagram content has not been visually analyzed', 'status': 'needs_review', 'caption': 'Figure 1/图 1: V-model/V 字型模式', 'anchors': {'page': 15, 'caption': ...
- eval=P1-05 status=needs_review item={'review_id': 'visual-doc-20260611142812-f56c6cf9-fig-2', 'eval_id': 'P1-05', 'source_type': 'figure', 'source_id': 'fig-2', 'page': 20, 'recommended_tool': 'multimodal', 'reason': 'figure caption exists but diagram content has not been visually analyzed', 'status': 'needs_review', 'caption': 'Figure 2/图 2： Structure of the product engineering process/ 产品设计过 ...

你看什么：
- [ ] Figure caption 是否和原 PDF 一致。
- [ ] V-model / process diagram 是否被标记为需要 crop + multimodal。
- [ ] 未 accepted 的视觉候选没有进入 primary evidence。

## 8. Source Anchors 样例

- {'fragment_id': 'frag-1', 'anchors': {'page': 1, 'paragraph_index': 1}}
- {'fragment_id': 'frag-2', 'anchors': {'page': 1, 'paragraph_index': 2}}
- {'fragment_id': 'frag-3', 'anchors': {'page': 5, 'paragraph_index': 1}}
- {'fragment_id': 'frag-4', 'anchors': {'page': 5, 'paragraph_index': 2, 'heading_path': ['0 History/ 修改历史']}}
- {'fragment_id': 'frag-5', 'anchors': {'page': 6, 'paragraph_index': 1, 'heading_path': ['0 History/ 修改历史']}}
- {'fragment_id': 'frag-6', 'anchors': {'page': 7, 'paragraph_index': 1, 'heading_path': ['0 History/ 修改历史']}}
- {'fragment_id': 'frag-7', 'anchors': {'page': 7, 'paragraph_index': 2, 'heading_path': ['1 Purpose and scope / 目的和适用范围']}}
- {'fragment_id': 'frag-8', 'anchors': {'page': 7, 'paragraph_index': 3, 'heading_path': ['1 Purpose and scope / 目的和适用范围']}}
- {'fragment_id': 'frag-9', 'anchors': {'page': 7, 'paragraph_index': 4, 'heading_path': ['1 Purpose and scope / 目的和适用范围']}}
- {'fragment_id': 'frag-10', 'anchors': {'page': 7, 'paragraph_index': 5, 'heading_path': ['1 Purpose and scope / 目的和适用范围']}}
- {'fragment_id': 'frag-11', 'anchors': {'page': 7, 'paragraph_index': 6, 'heading_path': ['1 Purpose and scope / 目的和适用范围']}}
- {'fragment_id': 'frag-12', 'anchors': {'page': 7, 'paragraph_index': 7, 'heading_path': ['1 Purpose and scope / 目的和适用范围']}}
- {'fragment_id': 'frag-13', 'anchors': {'page': 7, 'paragraph_index': 8, 'heading_path': ['1 Purpose and scope / 目的和适用范围']}}
- {'fragment_id': 'frag-14', 'anchors': {'page': 7, 'paragraph_index': 9, 'heading_path': ['1 Purpose and scope / 目的和适用范围']}}
- {'fragment_id': 'frag-15', 'anchors': {'page': 7, 'paragraph_index': 10, 'heading_path': ['1 Purpose and scope / 目的和适用范围']}}
- {'fragment_id': 'frag-16', 'anchors': {'page': 7, 'paragraph_index': 11, 'heading_path': ['1 Purpose and scope / 目的和适用范围']}}
- {'fragment_id': 'frag-17', 'anchors': {'page': 7, 'paragraph_index': 12, 'heading_path': ['2 Reference document / 参考文件']}}
- {'fragment_id': 'frag-18', 'anchors': {'page': 7, 'paragraph_index': 13, 'heading_path': ['2 Reference document / 参考文件']}}
- {'fragment_id': 'frag-19', 'anchors': {'page': 7, 'paragraph_index': 14, 'heading_path': ['2 Reference document / 参考文件']}}
- {'fragment_id': 'frag-20', 'anchors': {'page': 7, 'paragraph_index': 15, 'heading_path': ['2 Reference document / 参考文件']}}
- {'fragment_id': 'frag-21', 'anchors': {'page': 7, 'paragraph_index': 16, 'heading_path': ['2 Reference document / 参考文件']}}
- {'fragment_id': 'frag-22', 'anchors': {'page': 7, 'paragraph_index': 17, 'heading_path': ['2 Reference document / 参考文件']}}
- {'fragment_id': 'frag-23', 'anchors': {'page': 7, 'paragraph_index': 18, 'heading_path': ['2 Reference document / 参考文件']}}
- {'fragment_id': 'frag-24', 'anchors': {'page': 8, 'paragraph_index': 1, 'heading_path': ['2 Reference document / 参考文件']}}
- {'fragment_id': 'frag-25', 'anchors': {'page': 8, 'paragraph_index': 2, 'heading_path': ['2 Reference document / 参考文件']}}
- {'fragment_id': 'frag-26', 'anchors': {'page': 8, 'paragraph_index': 3, 'heading_path': ['2 Reference document / 参考文件']}}
- {'fragment_id': 'frag-27', 'anchors': {'page': 8, 'paragraph_index': 4, 'heading_path': ['2 Reference document / 参考文件']}}
- {'fragment_id': 'frag-28', 'anchors': {'page': 8, 'paragraph_index': 5, 'heading_path': ['2 Reference document / 参考文件']}}
- {'fragment_id': 'frag-29', 'anchors': {'page': 8, 'paragraph_index': 6, 'heading_path': ['2 Reference document / 参考文件']}}
- {'fragment_id': 'frag-30', 'anchors': {'page': 8, 'paragraph_index': 7, 'heading_path': ['2 Reference document / 参考文件']}}
- 更多 anchors 见 parsed JSON。

## 9. RAG / LLM 人审附录

这里不用判断算法，只判断：top evidence quote 是否真的支撑这个问题的答案。

### Query: What should the Product Owner prepare during R2?
- Eval summary: `{"pass": 1, "warn": 0, "fail": 0, "na": 0}`
- Strategy: `hybrid_retrieval`
- 你看什么：
  - [ ] Top hit 是正确章节/文档。
  - [ ] Quote 能支撑答案。
  - [ ] History/template change 没有成为 primary evidence。

Top evidence:
- `ev-1` 6.2.4 Standard Tailoring for Agile Approaches during Product Development/ 产品开发期间敏 p.32
  - Quote: 6.2.4 Standard Tailoring for Agile Approaches during Product Development/ 产品开发期间敏
  - Supports: `["stage"]`
- `ev-2` R1 /R2 and M120/M150/M200 can be combined p.32
  - Quote: R1/R2 and M120/M150/M200 can be combined
  - Supports: `["stage"]`
- `ev-3` R2 p.32
  - Quote: R2.
  - Supports: `["stage"]`
- `ev-4` 6.16.1 Changes during product development/ 产品开发中的更改 p.36
  - Quote: 6.16.1 Changes during product development/ 产品开发中的更改
  - Supports: `["deliverable"]`
Missing evidence:
- {'term_type': 'role', 'terms': ['Product Owner'], 'reason': 'no primary evidence supports normalized terms'}

### Query: Where is the country-specific approvals regulatory approval plan section?
- Eval summary: `{"pass": 1, "warn": 0, "fail": 0, "na": 0}`
- Strategy: `hybrid_retrieval`
- 你看什么：
  - [ ] Top hit 是正确章节/文档。
  - [ ] Quote 能支撑答案。
  - [ ] History/template change 没有成为 primary evidence。

Top evidence:
- `ev-1` 7.16 Country-specific approvals (regulatory approval plan) / 特定国家核准（法规核准计划） p.49
  - Quote: 7.16 Country-specific approvals (regulatory approval plan) / 特定国家核准（法规核准计划）
  - Supports: `[]`
- `ev-2` 5.3.3 Process Phase 3: Product Development / 过程阶段 3：产品开发 p.27
  - Quote: • Perform final verification (system verification): Verification test reports (depending on test concept: reports for subsystem/system level; including reports for safety tests and reliability tests) • 执行最终验证（系统验证）：验证测试报
  - Supports: `[]`
- `ev-3` 7.2 Quality management plan (QMP)/ 质量管理计划 （QMP） p.41
  - Quote: 7.2 Quality management plan (QMP)/ 质量管理计划 （QMP）
  - Supports: `["deliverable"]`
- `ev-4` 5.3.2 Process Phase 2: Product Definition / 过程阶段 2：产品定义 p.22
  - Quote: • A project-specific quality management plan (QMP) is created and maintained for each project. Approval / termination criteria for individual project phases are defined.
  - Supports: `["deliverable"]`

## 10. 人审记录

- Parser 问题：
- 图像/OCR 问题：
- Evidence/RAG 问题：
- UI handoff 问题：
