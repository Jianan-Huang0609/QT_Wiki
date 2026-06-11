# QT Wiki Design Index

## Start Here

- [TODO.md](TODO.md): Design 目录唯一阶段计划入口，计划、方案、TODO 都在这里按 Phase 展开。
- [PRD-流程问答工作台.md](PRD-流程问答工作台.md): 产品定义，主线为 NotebookLM 式 PEP Knowledge Base、正式互动 Session、Session Note / Workflow Studio。
- [Todo+Spec-流程问答工作台.md](Todo+Spec-流程问答工作台.md): Session MVP 详细规格，用于下钻 Session contract、source scope、三栏 UI 和 workflow studio。
- [Tool-Parser-RAG-Fusion-Spec.md](Tool-Parser-RAG-Fusion-Spec.md): Tool 侧融合规格，用于 QT Parser Core provider fusion、Docling provider、PDF fusion、OCR/visual provider 和 Hybrid RAG。
- [G9-Human-Review-Pack.md](G9-Human-Review-Pack.md): G9 人审内容集合，先用 Markdown + JSON snapshots 集中核查 parser、fusion、visual、retrieval、answer 和 handoff contract，再进入 G8 UI。

## How To Operate

1. 每次开始先打开 [TODO.md](TODO.md)，按 Phase 找当前任务和方案。
2. 计划和方案优先写回 [TODO.md](TODO.md)，外部文档只做附件。
3. 如果要核查某个 Gate 的事实，进入 Gate review 报告。
4. 如果要理解历史技术路线，进入设计/计划附件。
5. 如果要恢复会话或看历史证据，进入 [dev-memory/](dev-memory/)。

当前不做大规模改名，先通过 [TODO.md](TODO.md) 固定“阶段计划 + 附件证据 + 开发记忆”的操作方式。

## Reference And Evidence Attachments

- [Parser-Workflow-Evals-实施计划.md](Parser-Workflow-Evals-实施计划.md): Parser / Retrieval / Answer gates 与 eval 的历史详细计划附件；执行以 [TODO.md](TODO.md) 的 Phase 为准。
- [MultiInput-Parser-RAG-Workflow-设计.md](MultiInput-Parser-RAG-Workflow-设计.md): 多格式解析、章节化、Script/LLM/Evals 分工、Retrieval Strategy Matrix 和 Session RAG Workflow 研究设计。
- [Tool-Parser-RAG-Fusion-Spec.md](Tool-Parser-RAG-Fusion-Spec.md): G9 QT Parser Core 详细规格，记录 provider fusion、Docling provider、PDF fusion、OCR/visual provider、Hybrid RAG 和 eval gate 计划。
- [G9-Human-Review-Pack.md](G9-Human-Review-Pack.md): G9 review 执行包，记录人审路线、材料结构、checklist、review record 模板和后续 hardening 项。
- [Gate3-PEP-PDF-Review.md](Gate3-PEP-PDF-Review.md): G3 证据附件，记录 CT / MI / XP PEP PDF 自动 smoke 和人工 review 样例。
- [Gate6-Adaptive-Answer-Workflow-Plan.md](Gate6-Adaptive-Answer-Workflow-Plan.md): G6 历史详细方案附件；执行以 [TODO.md](TODO.md) 的 Phase 4 为准。
- [Pro-Input-Praser.md](Pro-Input-Praser.md): PEP parser 开发经验、难点和方法，覆盖 TOC/History/Figure/标题续行、OCR 与 multimodal 决策边界。

## Development Memory

- [dev-memory/TODO.md](dev-memory/TODO.md): 开发记忆层 TODO，保留 Now / Next / Done / Later 和证据摘要。
- [dev-memory/SESSION-WIP.md](dev-memory/SESSION-WIP.md): 当前会话状态和下一步。
- [dev-memory/PROJECT-MEMORY.md](dev-memory/PROJECT-MEMORY.md): 稳定项目记忆和边界。
- [dev-memory/CHANGELOG.md](dev-memory/CHANGELOG.md): 本开发线变更记录。

## Archived Old Frameworks

- [old/upload-approval/](old/upload-approval/): 旧“首次上传 / 审批包 / Wiki 发布”框架与 gap 分析。
- [old/regulation-navigator/](old/regulation-navigator/): 旧“Regulation Navigator / 法规导航型知识平台”框架、原型 HTML 和原始需求草稿。

当前整理策略是先归档，审阅后再决定是否删除旧框架。日常开发入口固定为 [TODO.md](TODO.md)，README 只承担导航职责。
