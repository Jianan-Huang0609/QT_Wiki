# PRD: QT Wiki NotebookLM 式 PEP 流程知识工作台

## 0. 文档信息

| 字段 | 内容 |
| --- | --- |
| 文档状态 | Decisioned Draft |
| 当前版本 | v0.3 |
| 更新时间 | 2026-06-10 |
| 适用范围 | QT Wiki vNext 产品收敛、PEP Knowledge Base、正式互动 Session、Session Note / Workflow Studio |
| 主要读者 | 产品 owner、流程 owner、研发、质量/法规专家、后续 AI agent |

## 0.1 v0.3 已确认决策

| 决策项 | 已确认范围 |
| --- | --- |
| 产品形态 | 类 NotebookLM：左侧固定资料库与关联图，中间正式互动 Session，右侧 Session Note / Workflow Studio。 |
| 外部工作区 | 需要 Landing Page / Knowledge Base 维护页，用于更新维护知识库、新建 session、查看历史 session、查看社区笔记。 |
| 资料复用 | 生产环境的 Knowledge Base 是背景环境；每次新 session 复制或引用当前知识库快照作为 session source scope。 |
| Session MVP | 本次 MVP 最小目标是正式互动 Session 工作台。外部维护页、社区笔记和完整发布流进入后续。 |
| 左侧固定区 | 全局文档目录固定展示，并支持目录树与 Obsidian 式点线关联图切换。 |
| Source 选择 | 单个 session 可选择具体文档、上传临时文档、或 All Sources 全选。 |
| Session 隔离 | 中间 Chat 是每次新开的 session；左侧资料库稳定保留，右侧笔记跟随当前 session。 |
| Session 上传 | 允许在单个 session 内上传文档；首版自动解析，不进入人工查验，只显示解析成功/失败的小状态标。 |
| 右侧笔记 | 每个 session 有固定笔记位，可沉淀回答、快捷生成 HTML / 飞书 Markdown / 流程图 / Reference / BU diff。 |
| 笔记发布 | 用户可选择把单个 session 的笔记 publish 出来，后续进入社区笔记或共享笔记。 |
| 技术路径 | 默认章节级 RAG；All Sources 强制 RAG + rerank；小范围选中文档/章节可走 LLM 直接读局部上下文。 |
| PDF 样本 | `PEP/` 目录已有 CT、MI、XP 三份 PEP PDF，均可抽文本，适合章节级索引和 BU 对比。 |

## 1. 产品一句话定义

QT Wiki vNext 是一个面向 PEP 路径公司开发流程的 NotebookLM 式知识工作台：团队在外部 Knowledge Base 中维护 CT / MI / XP 等 PEP PDF；用户进入正式互动 Session 后选择资料范围、提问流程问题、沉淀 Session Note，并把当前 session 生成 Markdown、HTML、飞书笔记、流程图、Reference 表或 BU 差异报告。

## 2. 背景与目标

当前 v0.2 已经明确 PEP 路径、R2/PO 问答、Reference 映射和 Markdown/Mermaid/BU diff 输出。用户进一步确认：真实使用时，资料库与对话 session 应该分层。

新的产品结构应解决三类问题：

1. **资料库长期维护**：PEP PDF 是背景知识资产，需要被维护、更新、解析和索引。
2. **Session 临时研究**：每次用户的问题都是一次独立研究任务，需要新建 session、选择资料范围、保存 session 历史。
3. **笔记与产出沉淀**：每个 session 的回答可以整理成固定笔记，并可进一步生成 HTML、飞书 Markdown、流程图、Reference 表或发布为共享笔记。

因此 v0.3 的重点从“单一 Chat 页面”升级为“Knowledge Base + Session + Studio Note”的三层产品。

## 3. 用户与场景

| 用户 | 核心问题 | 典型场景 |
| --- | --- | --- |
| PO / 项目成员 | 当前阶段该做什么，产出什么，找谁确认 | 新开 `R2 PO readiness` session，选择 CT/MI/XP PEP，询问 R2 任务。 |
| 流程 owner | PEP 流程如何操作，跨 BU 有什么差异 | 全选 CT/MI/XP PEP，生成流程说明与 BU diff。 |
| 质量/法规专家 | 结论是否能追溯到文件章节 | 查看 Reference 表和左侧章节树，定位证据来源。 |
| 新员工/培训对象 | 快速理解流程和关键检查点 | 从社区笔记或历史 session 打开已发布笔记。 |
| 知识库维护者 | 如何更新知识库文件 | 进入外部 Knowledge Base 维护页，上传新 PDF，查看解析状态。 |

## 4. 产品架构

### 4.1 三层工作区

| 层级 | 定位 | 首版处理 |
| --- | --- | --- |
| Landing Page | 功能开始页，提供新建 session、维护知识库、查看历史 session、查看社区笔记入口 | 后续实现，MVP 可用轻量入口占位 |
| Knowledge Base | 背景知识库，维护 PEP PDF、解析结果、章节索引、关联图 | 后续强化；MVP 使用现有 PEP 样本和已解析数据 |
| Session Workspace | 正式互动工作台，左 sources / 中 chat / 右 note studio | 本次 MVP 主体 |

### 4.2 Session Workspace 信息架构

```text
┌────────────────────────────────────────────────────────────────────┐
│ QT Wiki Notebook | Session title | Source scope | Model | New Session │
├──────────────────┬──────────────────────────────────┬──────────────┤
│ Sources / Graph  │ Session Chat                     │ Studio Note  │
│                  │                                  │              │
│ [x] CT PEP       │ Current session conversation      │ Pinned facts │
│ [x] MI PEP       │ Answer + References               │ Draft note   │
│ [x] XP PEP       │                                  │ Workflows    │
│                  │                                  │ - HTML note  │
│ Upload to session│                                  │ - Feishu MD  │
│ All Sources      │                                  │ - Mermaid    │
│                  │                                  │ - BU Diff    │
│ Tree | Graph     │ Input box                         │ Publish note │
└──────────────────┴──────────────────────────────────┴──────────────┘
```

## 5. MVP 范围

本次 MVP 最小交付是正式互动 Session 工作台。

### 5.1 MVP 必须包含

1. 左侧固定 Sources 区：
   - 展示 CT / MI / XP PEP 文档。
   - 支持勾选具体文档。
   - 支持 All Sources。
   - 支持 Tree / Graph 视觉切换。
   - 支持 session 内上传临时文档，并显示解析状态小标。

2. 中间 Session Chat：
   - 支持新建 session。
   - 每个 session 拥有独立聊天记录。
   - 每个 session 记录 source scope。
   - 提问时按当前 source scope 选择 RAG 或局部 LLM 直接读路径。
   - 回答保留 Reference 映射。

3. 右侧 Session Note / Studio：
   - 每个 session 有固定笔记位。
   - 支持把回答 pin 到 note。
   - 显示快捷 workflow：HTML note、飞书 Markdown、Reference 表、Mermaid、BU diff。
   - 支持 publish note 的入口占位。

4. Session 状态：
   - 显示当前 session 名称、创建时间、source scope、模型、解析状态。
   - 历史 session 可在 session 列表中切换。

### 5.2 MVP 暂缓

- 完整 Landing Page。
- 完整 Knowledge Base 维护后台。
- 社区笔记列表与权限。
- 人工审核章节拆分与对象抽取。
- 完整 HTML / 飞书发布 API。
- 图谱物理布局算法和复杂编辑能力。

## 6. 功能需求

### FR1 Landing Page / 外部入口

Landing Page 是产品开始页，服务于工作区入口选择。

入口包括：

- 更新维护知识库。
- 新建 Session。
- 查看历史 Session。
- 查看社区笔记。

首版策略：MVP 中只保留轻量入口或顶部导航占位，正式实现排在 Session Workspace 之后。

### FR2 Knowledge Base 维护

Knowledge Base 维护 PEP PDF、解析状态、章节索引和关联图。

能力包括：

- 上传或替换知识库文档。
- 查看解析成功/失败状态。
- 查看章节树。
- 查看跨文档关联图。
- 将当前知识库快照提供给新 session。

首版策略：CT / MI / XP PEP 可作为初始知识库样本；完整维护页后续实现。

### FR3 Session Source 选择

每个 session 必须有自己的 source scope。

选择方式：

| 模式 | 用户场景 | 技术路径 |
| --- | --- | --- |
| Selected Docs | 用户明确知道要问 CT / MI / XP 哪些文档 | 章节级 RAG，按选中文档过滤召回 |
| Upload To Session | 用户临时补充一个 PDF 或文档 | 先解析成 session-only source，成功后加入当前 session scope |
| All Sources | 用户不知道问题覆盖哪些文件 | 全库 RAG + rerank + evidence coverage |
| Selected Section | 用户只问某一章节 | LLM 直接读局部章节 + Reference |

验收标准：

- 当前 session 清晰显示 source scope。
- 上传到 session 的文档显示 `parsed` / `failed` 小状态标。
- All Sources 查询会在回答中说明命中的文档范围。

### FR4 左侧 Tree / Graph

左侧固定展示资料结构，支持两种视图。

Tree 视图：

- BU -> Document -> Chapter -> Section。
- 显示页码、章节标题、解析状态。
- 支持勾选文档或章节进入当前 session。

Graph 视图：

- Obsidian 式点线图。
- 节点类型：Document、Chapter、Stage、Role、Deliverable、Template、Reference。
- 边类型：contains、mentions、requires、produces、responsible_for、differs_from。

MVP 图谱可以先用静态/规则布局展示关系，不要求复杂拖拽编辑。

### FR5 中间 Session Chat

Session Chat 是正式互动区，占页面主要宽度。

能力包括：

- 新建 session。
- 切换历史 session。
- 提问 PEP 流程、R2/PO 任务、Reference、BU diff。
- 回答根据 source scope 自动选择技术路径。
- 回答包含 Reference 映射。
- 支持把回答 pin 到右侧 note。

回答结构建议：

```text
结论
适用范围 / Source scope
步骤与职责
交付物 / 记录
BU 差异或缺口
Reference
可继续追问
```

### FR6 右侧 Session Note / Workflow Studio

右侧是当前 session 的固定笔记位，而不是全局设置。

能力包括：

- Session Note 草稿。
- Pin answer to note。
- Workflow shortcuts：
  - 生成 HTML note。
  - 生成飞书 Markdown。
  - 生成 Reference 表。
  - 生成 Mermaid 流程图。
  - 生成 BU diff。
- Publish note 入口。

首版策略：先做 UI 和本地草稿状态；导出 API 后续接入。

### FR7 笔记发布与社区笔记

用户可以选择是否 publish 当前 session 笔记。

发布对象：

- 当前 session note。
- 关联 source scope。
- 生成资产：HTML / Markdown / Mermaid / Reference / BU diff。

首版策略：MVP 中保留 publish 入口和状态字段；社区笔记列表、权限和审核后续实现。

## 7. 技术路径

### 7.1 默认路径：章节级 RAG

适用：Selected Docs、All Sources、多文档 BU 对比。

流程：

1. PDF 解析为 Document / Chapter / Section / Fragment。
2. 构建章节级索引。
3. 按 session source scope 过滤候选。
4. 召回相关章节和 fragment。
5. rerank 并覆盖不同 BU。
6. LLM 基于证据生成答案。
7. 输出 Reference。

### 7.2 局部直接读路径

适用：用户只选一个文档的小章节，或上传很小的 session-only 文档。

流程：

1. 将选中章节或小文档作为上下文。
2. LLM 直接读取该局部上下文。
3. 输出答案和章节级 Reference。

### 7.3 Session 上传路径

适用：用户在 session 中临时补充资料。

流程：

1. 上传文件。
2. 自动解析和章节拆分。
3. 显示小状态标：`parsed`、`failed`、`low confidence`。
4. 成功后加入当前 session source scope。
5. 不进入人工审核主路径。

## 8. 数据模型草案

### 8.1 Session

```json
{
  "session_id": "session-r2-po-001",
  "title": "R2 PO Readiness",
  "source_scope": {
    "mode": "selected_docs",
    "document_ids": ["ct-pep", "mi-pep", "xp-pep"],
    "session_upload_ids": []
  },
  "messages": [],
  "note": {
    "markdown": "",
    "pinned_answer_ids": [],
    "publish_status": "draft"
  },
  "created_at": "2026-06-10T00:00:00Z"
}
```

### 8.2 Source

```json
{
  "document_id": "ct-pep",
  "file_name": "CT PEP AND 308 11.pdf",
  "bu": "CT",
  "source_type": "knowledge_base",
  "parse_status": "parsed",
  "page_count": 55,
  "section_count": 0,
  "fragment_count": 0
}
```

### 8.3 Graph Node

```json
{
  "node_id": "stage-r2",
  "node_type": "stage",
  "label": "R2",
  "source_refs": ["ref-1"]
}
```

## 9. MVP Definition of Done

- 页面呈现 NotebookLM 式三栏：左 Sources / Tree / Graph，中 Session Chat，右 Session Note / Workflow Studio。
- 左侧默认展示 CT / MI / XP 三份 PEP PDF 样本和解析状态。
- 用户能选择 Selected Docs、All Sources 或 session upload 作为当前 session source scope。
- 用户能新建 session；新 session 拥有独立聊天记录和独立 note。
- 用户能在 session 中提问，回答使用当前 source scope 并保留 Reference。
- 用户能把回答 pin 到右侧 session note。
- 右侧能展示 HTML note、飞书 Markdown、Reference 表、Mermaid、BU diff、Publish note 的 workflow 入口。
- `npm run build` 通过，localhost 能展示正式互动 Session 工作台。

## 10. 开放问题

1. Landing Page 是否在 MVP 后第一优先级实现，还是先补齐 RAG / export 后再做。
2. Publish note 的目标是本地社区列表、Markdown 文件、GitHub Pages 页面，还是飞书文档。
3. Graph 首版使用静态布局、规则布局，还是引入图谱/力导向库。
4. Session 历史保存在浏览器本地、后端 JSON，还是 GitHub Pages 静态产物。
5. Knowledge Base 更新是否需要人工审核，还是只在后台显示低置信度提示。