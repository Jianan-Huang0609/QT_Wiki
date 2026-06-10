# 旧框架去留审计 2026-06-09

目标：按当前“流程问答工作台”主线，判断已有框架哪些直接保留、哪些改造、哪些归档、哪些等待用户确认后删除。

## Keep

- `Tool/contracts/canonical.py`、`Tool/pipelines/`、`Tool/parsers/`：继续作为 Raw -> Parsed canonical 的主事实来源。当前 DOCX/PPTX 依赖标准库，PDF 依赖 `pypdf`，XLSX 依赖 `openpyxl`，适合后续接 parser/extractor adapter。
- `wiki/models/`、`wiki/store/`、`wiki/indexing/`：继续作为 Wiki 页面、Markdown/JSON 存储、机器索引和 citation/source refs 的基础。
- `App/api.py` 的 `/chat/query`、`/chat/reindex`、`/agent/upload`：继续作为 localhost MVP 的主 API。
- `App/agents/query_agent.py` 和 `App/agents/structured_knowledge.py`：继续支撑受控召回、结构化对象关系、映射矩阵和 slides 提纲。
- `App/agents/lint_agent.py`：保留为后台健康检查能力。

## Adapt

- `App/agents/ingest_agent.py`：从“审批包驱动”调整为“自动解析 + 可选校正 + 后台治理”，ReviewPackage 保留为治理对象，前端弱化为解析详情。
- `App/web/src/App.tsx`：主体验围绕右侧 Process Chat、推荐问题、引用、trace；Ingest 文案从重审批改为文档解析与可选校正。
- `README.md`、`QT-Wiki-功能文档.md`、`AGENTS.md`：逐步把历史“双关口发布”描述重写成后台治理能力，避免继续定义为普通用户主路径。
- `Tool` 层 parser/extractor：后续新增 adapter，把 QT-CER-Tool `Skill/docx-extraction-skill` 的抽取脚本映射到本 repo canonical 输出。

## Archive

- `Design/old/upload-approval/`：保留旧首次上传/审批包设计和图片，作为历史审计材料。
- `Design/old/regulation-navigator/`：保留旧 Regulation Navigator PRD、设计稿和原型 HTML，作为灵感/对照材料。

## Delete Later

- `Design/old/` 下旧稿先不删除。触发条件：用户审阅后明确哪些历史材料不再需要。
- 未被主布局调用的旧前端组件，例如 `QueryView`、`ContextPanel`，先保留到 localhost 版稳定后再做代码简化。

## Evidence

- `python -m pytest`：74 passed，1 个 FastAPI TestClient deprecation warning。
- `App/web npm run build`：TypeScript 与 Vite build 通过。
- `Design/old/` 已包含旧 Markdown、HTML 原型和图片资产。