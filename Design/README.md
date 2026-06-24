# QT Wiki Design Index

更新时间：2026-06-24
状态：当前设计导航

## Start Here

- [TODO.md](TODO.md)：系统级执行入口，所有可勾选开发任务从这里开始。
- [Spec-Parser-RAG.md](Spec-Parser-RAG.md)：Parser / RAG 中间格式改造，覆盖 DocumentBlock、Markdown artifacts、Parser Router、表格和 eval。
- [Spec-Chat-Workflow.md](Spec-Chat-Workflow.md)：Chat workflow 改造，覆盖 intent、route、tool registry、Answer Run、LLM composer 和 memory。
- [Spec-UI-Workspace.md](Spec-UI-Workspace.md)：UI 四页操作流，覆盖 Source Intake、Review Gate、Ask Workspace、Admin / JSON Lab。
- [PRD-流程问答工作台.md](PRD-流程问答工作台.md)：产品定义和 MVP 边界。

## How To Operate

1. 开发前先看 [TODO.md](TODO.md)，只从系统级 checkbox 领取任务。
2. 需要理解模块设计时进入对应 Spec。
3. 完成任务后在 [TODO.md](TODO.md) 勾选并写证据。
4. 较长的设计变化写回对应 Spec。
5. 历史 Gate / Review / Plan 文档统一在 [old/](old/) 中，只作为证据或背景，不再作为执行入口。

## Current Layout

Design 根目录只保留当前入口和模块 Spec：

```text
Design/
  README.md
  TODO.md
  PRD-流程问答工作台.md
  Spec-Parser-RAG.md
  Spec-Chat-Workflow.md
  Spec-UI-Workspace.md
  dev-memory/
  old/
  review-artifacts/
```

## Current Technical Frame

当前项目按四个板块推进：

| 板块 | 当前 contract | 下一步 |
| --- | --- | --- |
| Chat Runtime | `intent-route-v0.2`、RouteCatalog、Answer Run、AnswerPlan v0.2 | Thin Claim Guardrail、bounded replan。 |
| Retrieval / Evidence | HybridRetriever、AnswerEvidencePackage、EvidenceSource | Quality warning、Reference polish。 |
| Parser / Blocks | CanonicalDocument、SectionChunk、TableData/FigureData | 触发式表格元素抽取，完整 provider 评估保持 Later。 |
| UI Workspace | Source cards、Ask Workspace、Reference Viewer | Source Intake / Review Gate / Ask Workspace v2 / Admin 拆页。 |

外部框架吸收采用“先 contract/eval，后 agent”的原则：Self-RAG 吸收到 verifier，VMAO 吸收到 bounded Answer Run，GraphRAG 放到多文档对比，DSPy 放到 eval-driven tuning，多 agent 只用于异构工具任务。

设计和执行分工：

- `Spec-*`：放框架设计、策略判断、接口 contract、验收口径和取舍解释。
- `TODO.md`：放具体操作、checkbox、优先级、验证证据和完成状态。
- `PRD-流程问答工作台.md`：放产品目标、MVP 边界和用户价值。
- `dev-memory/`：放持续开发记忆、会话 WIP 和稳定项目事实。
- `old/`：放已被当前 Spec 吸收的历史计划、旧规格、证据包和背景研究。

## Archive Map

以下文档已归档到 [old/](old/)，查历史时再进入：

| 文件 | 当前角色 | 当前入口 |
| --- | --- | --- |
| [old/G9-Human-Review-Pack.md](old/G9-Human-Review-Pack.md) | G9 parser / retrieval / answer 人审证据包 | [Spec-Parser-RAG.md](Spec-Parser-RAG.md)、[Spec-Chat-Workflow.md](Spec-Chat-Workflow.md) |
| [old/Gate3-PEP-PDF-Review.md](old/Gate3-PEP-PDF-Review.md) | CT / MI / XP PEP parser 人审证据包 | [Spec-Parser-RAG.md](Spec-Parser-RAG.md) |
| [old/Gate6-Adaptive-Answer-Workflow-Plan.md](old/Gate6-Adaptive-Answer-Workflow-Plan.md) | Chat 历史方案 | [Spec-Chat-Workflow.md](Spec-Chat-Workflow.md) |
| [old/MultiInput-Parser-RAG-Workflow-设计.md](old/MultiInput-Parser-RAG-Workflow-设计.md) | Parser/RAG 背景研究 | [Spec-Parser-RAG.md](Spec-Parser-RAG.md) |
| [old/Parser-Workflow-Evals-实施计划.md](old/Parser-Workflow-Evals-实施计划.md) | Parser/evals 历史实施计划 | [Spec-Parser-RAG.md](Spec-Parser-RAG.md) |
| [old/Pro-Input-Praser.md](old/Pro-Input-Praser.md) | Parser 经验笔记 | [Spec-Parser-RAG.md](Spec-Parser-RAG.md) |
| [old/Tool-Parser-RAG-Fusion-Spec.md](old/Tool-Parser-RAG-Fusion-Spec.md) | G9 provider fusion 历史详细规格 | [Spec-Parser-RAG.md](Spec-Parser-RAG.md) |
| [old/Todo+Spec-流程问答工作台.md](old/Todo+Spec-流程问答工作台.md) | Session MVP 历史详细规格 | [TODO.md](TODO.md)、[Spec-UI-Workspace.md](Spec-UI-Workspace.md)、[Spec-Chat-Workflow.md](Spec-Chat-Workflow.md) |

## Development Memory

- [dev-memory/SESSION-WIP.md](dev-memory/SESSION-WIP.md)：当前会话状态、最新决策和下一步。
- [dev-memory/TODO.md](dev-memory/TODO.md)：开发记忆层 TODO，后续可逐步简化。
- [dev-memory/PROJECT-MEMORY.md](dev-memory/PROJECT-MEMORY.md)：稳定项目记忆和边界。
- [dev-memory/CHANGELOG.md](dev-memory/CHANGELOG.md)：开发线变更记录。

## Archived Old Frameworks

- [old/upload-approval/](old/upload-approval/)：旧上传审批框架。
- [old/regulation-navigator/](old/regulation-navigator/)：旧 Regulation Navigator 框架。