import {
  Activity,
  Archive,
  Bot,
  Check,
  ChevronRight,
  DatabaseZap,
  FileInput,
  FileSearch,
  Gauge,
  GitBranch,
  History,
  LayoutDashboard,
  Loader2,
  MessageSquareText,
  RefreshCw,
  Search,
  Settings,
  ShieldAlert,
  Sparkles,
  Upload,
  X
} from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import {
  ApiRequestError,
  approveCandidate,
  decideReviewPackage,
  decideReviewPackageRelations,
  getCandidates,
  getDashboard,
  getIngestRuns,
  getMappingMatrixExport,
  getReviewPackages,
  getSlidesOutlineExport,
  getWikiPages,
  queryWiki,
  rebuildIndex,
  rejectCandidate,
  runLintScan,
  uploadDocument
} from "./api";
import type {
  AgentSummary,
  CandidatePage,
  Citation,
  IndexStatus,
  IngestRunSummary,
  LintIssue,
  MappingMatrixExport,
  NavItem,
  QueryResult,
  ReviewPackage,
  SlidesOutlineExport,
  ViewKey,
  WikiPage
} from "./types";

const navItems: NavItem[] = [
  { key: "dashboard", label: "总览", caption: "运行态势", icon: LayoutDashboard },
  { key: "ingest", label: "文档解析", caption: "自动解析", icon: FileInput },
  { key: "wiki", label: "Wiki 浏览", caption: "页面与溯源", icon: FileSearch },
  { key: "query", label: "知识问答", caption: "索引召回", icon: MessageSquareText },
  { key: "lint", label: "健康中心", caption: "风险修复", icon: ShieldAlert },
  { key: "settings", label: "设置", caption: "索引与模型", icon: Settings }
];

const defaultSuggestedQuestions = [
  "PEP 文档的流程如何操作？",
  "现在在 R2 阶段，我作为 PO 应该做什么？",
  "这个流程需要输出哪些记录或模板？",
  "这条回答具体来自哪些文件章节？",
  "不同 BU 对这个流程有哪些差异？"
];

interface ChatHistoryEntry {
  id: string;
  question: string;
  result: QueryResult | null;
  createdAt: string;
  status: "success" | "error";
  errorMessage?: string;
}

type DrawerKey = "context" | "references" | "outputs" | "admin";

export default function App() {
  const [activeView, setActiveView] = useState<ViewKey>("dashboard");
  const [activeDrawer, setActiveDrawer] = useState<DrawerKey>("context");
  const [agents, setAgents] = useState<AgentSummary[]>([]);
  const [indexStatus, setIndexStatus] = useState<IndexStatus | null>(null);
  const [candidates, setCandidates] = useState<CandidatePage[]>([]);
  const [reviewPackages, setReviewPackages] = useState<ReviewPackage[]>([]);
  const [ingestRuns, setIngestRuns] = useState<IngestRunSummary[]>([]);
  const [pages, setPages] = useState<WikiPage[]>([]);
  const [issues, setIssues] = useState<LintIssue[]>([]);
  const [selectedPackageId, setSelectedPackageId] = useState<string>("");
  const [selectedPageId, setSelectedPageId] = useState<string>("");
  const [queryResult, setQueryResult] = useState<QueryResult | null>(null);
  const [selectedCitationId, setSelectedCitationId] = useState<string>("");
  const [chatHistory, setChatHistory] = useState<ChatHistoryEntry[]>([]);
  const [selectedChatId, setSelectedChatId] = useState("");
  const [question, setQuestion] = useState("风险管理在质量管理体系里扮演什么角色？");
  const [useLlm, setUseLlm] = useState(true);
  const [modelProfile, setModelProfile] = useState("azure-gpt-4o");
  const [topKPages, setTopKPages] = useState(5);
  const [busy, setBusy] = useState<string>("");
  const [toast, setToast] = useState("后端已连接后会显示真实执行结果。");
  const [decisionBusinessType, setDecisionBusinessType] = useState("");
  const [decisionEffectiveLevel, setDecisionEffectiveLevel] = useState("");
  const [decisionIsBinding, setDecisionIsBinding] = useState(false);
  const [decisionNotes, setDecisionNotes] = useState("");
  const [decisionReviewedBy, setDecisionReviewedBy] = useState("");
  const [relationDecisionNotes, setRelationDecisionNotes] = useState("");
  const [relationReviewedBy, setRelationReviewedBy] = useState("");
  const [mappingMatrixExport, setMappingMatrixExport] = useState<MappingMatrixExport | null>(null);
  const [slidesOutlineExport, setSlidesOutlineExport] = useState<SlidesOutlineExport | null>(null);
  const [currentDocumentId, setCurrentDocumentId] = useState("");
  const [ingestFilter, setIngestFilter] = useState<"current" | "pending" | "all">("pending");

  useEffect(() => {
    void refreshAll();
  }, []);

  useEffect(() => {
    if (activeView === "dashboard" || activeView === "query") {
      void refreshDashboardData();
    }
  }, [activeView]);

  useEffect(() => {
    if (!selectedPackageId && reviewPackages.length) {
      setSelectedPackageId(reviewPackages[0].package_id);
    }
  }, [reviewPackages, selectedPackageId]);

  useEffect(() => {
    if (!selectedPageId && pages.length) {
      setSelectedPageId(pages[0].page_id);
    }
  }, [pages, selectedPageId]);

  const visibleReviewPackages = reviewPackages.filter((item) => matchesIngestFilter(item.document_id, item.status, currentDocumentId, ingestFilter));
  const workflowItems = navItems.filter((item) => item.key !== "query");
  const currentFlowView = activeView === "query" ? "dashboard" : activeView;
  const visibleCandidates = candidates.filter((item) => {
    const primaryDocumentId = item.document_ids[0] ?? "";
    return matchesIngestFilter(primaryDocumentId, item.status, currentDocumentId, ingestFilter);
  });
  const ingestFilterCounts = useMemo(
    () => ({
      current: reviewPackages.filter((item) => matchesIngestFilter(item.document_id, item.status, currentDocumentId, "current")).length,
      pending: reviewPackages.filter((item) => matchesIngestFilter(item.document_id, item.status, currentDocumentId, "pending")).length,
      all: reviewPackages.length,
    }),
    [reviewPackages, currentDocumentId]
  );

  const selectedReviewPackage = visibleReviewPackages.find((item) => item.package_id === selectedPackageId) ?? visibleReviewPackages[0];
  const activeChatEntry = chatHistory.find((item) => item.id === selectedChatId) ?? chatHistory[0];
  const activeChatResult = activeChatEntry?.result ?? queryResult;
  const relatedCandidates = selectedReviewPackage
    ? candidates.filter(
        (item) =>
          item.document_ids.includes(selectedReviewPackage.document_id) ||
          selectedReviewPackage.candidate_page_titles.includes(item.title)
      )
    : [];
  const selectedPage = pages.find((item) => item.page_id === selectedPageId) ?? pages[0];
  const selectedCitation =
    activeChatResult?.citations.find((item) => item.citation_id === selectedCitationId) ?? activeChatResult?.citations[0];

  useEffect(() => {
    if (!visibleReviewPackages.length) {
      if (selectedPackageId) {
        setSelectedPackageId("");
      }
      return;
    }
    if (!visibleReviewPackages.some((item) => item.package_id === selectedPackageId)) {
      setSelectedPackageId(visibleReviewPackages[0].package_id);
    }
  }, [visibleReviewPackages, selectedPackageId]);

  useEffect(() => {
    if (!selectedReviewPackage) {
      return;
    }
    setDecisionBusinessType(selectedReviewPackage.confirmed_business_type || selectedReviewPackage.business_type);
    setDecisionEffectiveLevel(selectedReviewPackage.confirmed_effective_level || selectedReviewPackage.effective_level);
    setDecisionIsBinding(selectedReviewPackage.confirmed_is_binding ?? selectedReviewPackage.is_binding);
    setDecisionNotes(selectedReviewPackage.review_notes);
    setDecisionReviewedBy(selectedReviewPackage.reviewed_by);
    setRelationDecisionNotes(selectedReviewPackage.relation_review_notes);
    setRelationReviewedBy(selectedReviewPackage.relation_reviewed_by);
  }, [selectedReviewPackage]);

  const openIssueCount = issues.filter((item) => item.status !== "resolved").length;
  const pendingCandidateCount = candidates.filter((item) => item.status === "pending").length;
  const pendingPackageCount = reviewPackages.filter((item) => item.status === "pending_review").length;

  async function refreshAll() {
    await Promise.all([refreshDashboardData(), refreshWorkspaceData()]);
  }

  async function refreshDashboardData() {
    setBusy((current) => (current === "" ? "dashboard" : current));
    try {
      const dashboard = await getDashboard();
      setAgents(dashboard.agents);
      setIndexStatus(dashboard.index);
      setIssues(dashboard.issues);
    } catch (error) {
      setToast(`dashboard: ${errorMessage(error)}`);
    } finally {
      setBusy((current) => (current === "dashboard" ? "" : current));
    }
  }

  async function refreshWorkspaceData() {
    setBusy("refresh");
    const [candidateItems, reviewPackageItems, wikiItems, runItems] = await Promise.allSettled([
      getCandidates(),
      getReviewPackages(),
      getWikiPages(),
      getIngestRuns()
    ]);
    const errors: string[] = [];

    if (candidateItems.status === "fulfilled") {
      setCandidates(candidateItems.value);
    } else {
      errors.push(`candidates: ${errorMessage(candidateItems.reason)}`);
    }
    if (reviewPackageItems.status === "fulfilled") {
      setReviewPackages(reviewPackageItems.value);
    } else {
      errors.push(`review packages: ${errorMessage(reviewPackageItems.reason)}`);
    }
    if (wikiItems.status === "fulfilled") {
      setPages(wikiItems.value);
    } else {
      errors.push(`wiki pages: ${errorMessage(wikiItems.reason)}`);
    }
    if (runItems.status === "fulfilled") {
      setIngestRuns(runItems.value);
    } else {
      errors.push(`runs: ${errorMessage(runItems.reason)}`);
    }

    setBusy("");
    if (errors.length) {
      setToast(`工作区数据加载失败：${errors.join(" | ")}`);
    }
  }

  async function handleRebuildIndex() {
    setBusy("index");
    try {
      const next = await rebuildIndex();
      setIndexStatus(next);
      setToast(`索引已重建：${next.pages} pages / ${next.sources} sources`);
    } catch (error) {
      setToast(`重建索引失败：${errorMessage(error)}`);
    } finally {
      setBusy("");
    }
  }

  async function handleQuerySubmit(questionOverride?: string) {
    const nextQuestion = (questionOverride ?? question).trim();
    if (!nextQuestion) {
      return;
    }
    const chatId = createChatId();
    setBusy("query");
    try {
      const result = await queryWiki(nextQuestion, useLlm, topKPages);
      setQueryResult(result);
      setSelectedCitationId(result.citations[0]?.citation_id ?? "");
      setChatHistory((current) => [
        {
          id: chatId,
          question: nextQuestion,
          result,
          createdAt: new Date().toISOString(),
          status: "success",
        },
        ...current,
      ]);
      setSelectedChatId(chatId);
      setQuestion("");
      setToast(result.used_llm ? "Query used LLM." : "Query completed without LLM.");
    } catch (error) {
      setChatHistory((current) => [
        {
          id: chatId,
          question: nextQuestion,
          result: null,
          createdAt: new Date().toISOString(),
          status: "error",
          errorMessage: errorMessage(error),
        },
        ...current,
      ]);
      setSelectedChatId(chatId);
      setToast(`query failed: ${errorMessage(error)}`);
    } finally {
      setBusy("");
    }
  }

  function handleSuggestedQuestion(nextQuestion: string) {
    setQuestion(nextQuestion);
    void handleQuerySubmit(nextQuestion);
  }

  async function handleCandidateDecision(candidateId: string, decision: "approve" | "reject") {
    setBusy(candidateId);
    try {
      if (decision === "approve") {
        await approveCandidate(candidateId);
      } else {
        await rejectCandidate(candidateId);
      }
      await refreshWorkspaceData();
      setToast(decision === "approve" ? "候选页已批准并发布到 Wiki。" : "候选页已拒绝。");
    } catch (error) {
      setToast(`候选页操作失败：${errorMessage(error)}`);
    } finally {
      setBusy("");
    }
  }

  async function handleReviewDecision(identityDecision: "confirmed" | "needs_revision") {
    if (!selectedReviewPackage) {
      return;
    }
    setBusy(selectedReviewPackage.package_id);
    try {
      await decideReviewPackage(selectedReviewPackage.package_id, {
        identity_decision: identityDecision,
        confirmed_business_type: decisionBusinessType,
        confirmed_effective_level: decisionEffectiveLevel,
        confirmed_is_binding: decisionIsBinding,
        review_notes: decisionNotes,
        reviewed_by: decisionReviewedBy
      });
      await refreshWorkspaceData();
      setToast(identityDecision === "confirmed" ? "文档身份已确认。" : "审批包已退回重判。");
    } catch (error) {
      setToast(`文档身份确认失败：${errorMessage(error)}`);
    } finally {
      setBusy("");
    }
  }

  async function handleRelationReviewDecision(relationDecision: "confirmed" | "needs_revision") {
    if (!selectedReviewPackage) {
      return;
    }
    setBusy(`${selectedReviewPackage.package_id}:relations`);
    try {
      await decideReviewPackageRelations(selectedReviewPackage.package_id, {
        relation_decision: relationDecision,
        relation_review_notes: relationDecisionNotes,
        relation_reviewed_by: relationReviewedBy
      });
      await refreshWorkspaceData();
      setToast(relationDecision === "confirmed" ? "关键关系已确认。" : "关系判断已退回重判。");
    } catch (error) {
      setToast(`关键关系确认失败：${errorMessage(error)}`);
    } finally {
      setBusy("");
    }
  }

  async function handleLoadMappingMatrix() {
    setBusy("mapping-export");
    try {
      const result = await getMappingMatrixExport();
      setMappingMatrixExport(result);
      setToast(`已生成映射矩阵：${result.row_count} 行`);
    } catch (error) {
      setToast(`映射矩阵导出失败：${errorMessage(error)}`);
    } finally {
      setBusy("");
    }
  }

  async function handleLoadSlidesOutline() {
    setBusy("slides-export");
    try {
      const result = await getSlidesOutlineExport();
      setSlidesOutlineExport(result);
      setToast(`已生成 slides 提纲：${result.slide_count} 页`);
    } catch (error) {
      setToast(`slides 提纲导出失败：${errorMessage(error)}`);
    } finally {
      setBusy("");
    }
  }

  async function handleUpload(file: File | null) {
    if (!file) {
      setToast("请选择 .docx / .pdf / .pptx / .xlsx 文档。");
      return;
    }
    setBusy("upload");
    try {
      const result = await uploadDocument(file, useLlm);
      setCurrentDocumentId(result.document_id ?? "");
      setIngestFilter("current");
      if (result.review_package_id) {
        setSelectedPackageId(result.review_package_id);
      }
      setToast(`文档已解析：${result.section_count} 个章节 / ${result.fragment_count} 个片段。低置信度内容可在解析详情中校正，LLM ${useLlm ? "已开启" : "未开启"}。`);
      await refreshWorkspaceData();
      setActiveView("ingest");
      setActiveDrawer("context");
    } catch (error) {
      setToast(`上传失败：${errorMessage(error)}`);
    } finally {
      setBusy("");
    }
  }

  async function handleLintScan() {
    setBusy("lint");
    try {
      const next = await runLintScan();
      setIssues(next);
      setToast(`健康扫描完成：${next.length} 个问题。`);
    } catch (error) {
      setToast(`健康扫描失败：${errorMessage(error)}`);
    } finally {
      setBusy("");
    }
  }

  function handleSelectRun(run: IngestRunSummary) {
    setCurrentDocumentId(run.document_id);
    setIngestFilter("current");
    setSelectedPackageId(run.review_package_id || "");
    setActiveView("ingest");
    setToast(`已切换到运行 ${run.run_id}，当前聚焦文档 ${run.file_name || run.document_id}。`);
  }

  function handleClearCurrentSession() {
    setCurrentDocumentId("");
    setIngestFilter("pending");
    setSelectedPackageId("");
    setToast("已退出当前上传聚焦，工作台恢复为仅看待审核。");
  }

  function handleSelectChat(chatId: string) {
    const entry = chatHistory.find((item) => item.id === chatId);
    setSelectedChatId(chatId);
    if (!entry) {
      return;
    }
    setQuestion(entry.question);
    setQueryResult(entry.result);
    setSelectedCitationId(entry.result?.citations[0]?.citation_id ?? "");
  }

  return (
    <div className="app process-chat-app">
      <header className="process-header">
        <div className="process-brand">
          <div className="brand-mark">
            <DatabaseZap size={22} />
          </div>
          <div>
            <p className="eyebrow">QT Wiki vNext</p>
            <h1>PEP 流程问答</h1>
          </div>
        </div>
        <div className="process-status-strip" aria-label="当前上下文">
          <span>文档 {currentDocumentId || selectedReviewPackage?.document_id || "未选择"}</span>
          <span>BU 待识别</span>
          <span>阶段 R2</span>
          <span>角色 PO</span>
        </div>
        <div className="process-header-actions">
          <label className="model-select">
            <span>模型</span>
            <select value={modelProfile} onChange={(event) => setModelProfile(event.target.value)}>
              <option value="azure-gpt-4o">Azure GPT-4o</option>
              <option value="azure-gpt-5">Azure GPT-5</option>
              <option value="azure-gpt-5-multimodal">GPT-5 Multimodal</option>
            </select>
          </label>
          <label className="switch-line process-switch">
            <input type="checkbox" checked={useLlm} onChange={(event) => setUseLlm(event.target.checked)} />
            <span>LLM</span>
          </label>
          <label className="upload-button process-upload">
            <Upload size={16} />
            上传 PEP
            <input type="file" accept=".docx,.pdf,.pptx,.xlsx,.txt,.md" onChange={(event) => void handleUpload(event.target.files?.[0] ?? null)} />
          </label>
        </div>
      </header>

      <main className="process-shell">
        <section className="process-chat-column">
          <div className="process-chat-intro">
            <div>
              <p className="eyebrow">Process Chat</p>
              <h2>问 PEP 流程、R2 阶段动作、PO 交付物和引用来源</h2>
            </div>
            <div className="process-metrics">
              <Metric label="索引来源" value={String(indexStatus?.sources ?? 0)} />
              <Metric label="已解析" value={String(reviewPackages.length)} />
              <Metric label="低置信度" value={String(pendingPackageCount)} />
            </div>
          </div>
          <ChatbotPanel
            question={question}
            setQuestion={setQuestion}
            activeChatEntry={activeChatEntry}
            activeView={currentFlowView}
            busy={busy}
            selectedCitation={selectedCitation}
            selectedReviewPackage={selectedReviewPackage}
            selectedPage={selectedPage}
            issues={issues}
            onSubmit={() => void handleQuerySubmit()}
            onAskSuggested={handleSuggestedQuestion}
            onSelectCitation={setSelectedCitationId}
          />
        </section>

        <ProcessDrawer
          activeDrawer={activeDrawer}
          setActiveDrawer={setActiveDrawer}
          activeChatResult={activeChatResult}
          selectedCitation={selectedCitation}
          selectedReviewPackage={selectedReviewPackage}
          selectedPage={selectedPage}
          selectedCitationId={selectedCitationId}
          currentDocumentId={currentDocumentId}
          ingestRuns={ingestRuns}
          issues={issues}
          indexStatus={indexStatus}
          activeView={currentFlowView}
          workflowItems={workflowItems}
          setActiveView={setActiveView}
          onSelectCitation={setSelectedCitationId}
          onSelectRun={handleSelectRun}
          onRebuildIndex={() => void handleRebuildIndex()}
          busy={busy}
        />
      </main>

      <div className="toast" role="status">
        <Activity size={15} />
        {toast}
      </div>
    </div>
  );
}

function DashboardView({
  agents,
  indexStatus,
  pages,
  pendingPackageCount,
  pendingCandidateCount,
  openIssueCount,
  onNavigate
}: {
  agents: AgentSummary[];
  indexStatus: IndexStatus | null;
  pages: WikiPage[];
  pendingPackageCount: number;
  pendingCandidateCount: number;
  openIssueCount: number;
  onNavigate: (view: ViewKey) => void;
}) {
  return (
    <div className="view-stack">
      <section className="hero-panel">
        <div>
          <p className="eyebrow">Operational Console</p>
          <h2>把文档解析、证据索引和流程问答串起来</h2>
          <p>
            上传文档后先形成章节、片段、对象和关系，主 Chat 负责基于索引召回答案，抽屉面板持续展示来源、检索链路和风险提示。
          </p>
        </div>
        <div className="hero-metrics">
          <Metric label="Wiki 页面" value={String(pages.length)} />
          <Metric label="待校正" value={String(pendingPackageCount)} />
          <Metric label="待审核" value={String(pendingCandidateCount)} />
          <Metric label="健康问题" value={String(openIssueCount)} />
          <Metric label="来源索引" value={String(indexStatus?.sources ?? 0)} />
        </div>
      </section>

      <section className="agent-grid">
        {agents.map((agent) => (
          <button className={`agent-tile ${agent.accent}`} key={agent.key} type="button" onClick={() => onNavigate(agent.key === "ingest" ? "ingest" : agent.key === "query" ? "query" : "lint")}>
            <div className="tile-head">
              <Bot size={18} />
              <span className={`status-dot ${agent.status}`} />
            </div>
            <h3>{agent.name}</h3>
            <p>{agent.headline}</p>
            <footer>
              <span>队列 {agent.queue}</span>
              <span>{agent.lastRun}</span>
            </footer>
          </button>
        ))}
      </section>

      <section className="timeline-panel">
        <div className="section-title">
          <GitBranch size={18} />
          <h3>标准链路</h3>
        </div>
        {["Raw 文档入库", "Parsed fragments 生成", "解析结果可选校正", "Wiki 页面发布", "Index 自动重建", "Query 受控回答"].map((item, index) => (
          <div className="pipeline-step" key={item}>
            <span>{index + 1}</span>
            <strong>{item}</strong>
            {index < 5 && <ChevronRight size={16} />}
          </div>
        ))}
      </section>
    </div>
  );
}

function IngestView({
  reviewPackages,
  candidates,
  selected,
  selectedId,
  relatedCandidates,
  busy,
  ingestRuns,
  currentDocumentId,
  ingestFilter,
  ingestFilterCounts,
  decisionBusinessType,
  decisionEffectiveLevel,
  decisionIsBinding,
  decisionNotes,
  decisionReviewedBy,
  useLlm,
  setUseLlm,
  relationDecisionNotes,
  relationReviewedBy,
  onSelect,
  onIngestFilterChange,
  onSelectRun,
  onClearCurrentSession,
  onDecisionBusinessType,
  onDecisionEffectiveLevel,
  onDecisionIsBinding,
  onDecisionNotes,
  onDecisionReviewedBy,
  onRelationDecisionNotes,
  onRelationReviewedBy,
  onDecision,
  onReviewDecision,
  onRelationReviewDecision,
  onUpload
}: {
  reviewPackages: ReviewPackage[];
  candidates: CandidatePage[];
  selected?: ReviewPackage;
  selectedId: string;
  relatedCandidates: CandidatePage[];
  busy: string;
  ingestRuns: IngestRunSummary[];
  currentDocumentId: string;
  ingestFilter: "current" | "pending" | "all";
  ingestFilterCounts: {
    current: number;
    pending: number;
    all: number;
  };
  decisionBusinessType: string;
  decisionEffectiveLevel: string;
  decisionIsBinding: boolean;
  decisionNotes: string;
  decisionReviewedBy: string;
  useLlm: boolean;
  setUseLlm: (value: boolean) => void;
  relationDecisionNotes: string;
  relationReviewedBy: string;
  onSelect: (id: string) => void;
  onIngestFilterChange: (value: "current" | "pending" | "all") => void;
  onSelectRun: (run: IngestRunSummary) => void;
  onClearCurrentSession: () => void;
  onDecisionBusinessType: (value: string) => void;
  onDecisionEffectiveLevel: (value: string) => void;
  onDecisionIsBinding: (value: boolean) => void;
  onDecisionNotes: (value: string) => void;
  onDecisionReviewedBy: (value: string) => void;
  onRelationDecisionNotes: (value: string) => void;
  onRelationReviewedBy: (value: string) => void;
  onDecision: (id: string, decision: "approve" | "reject") => void;
  onReviewDecision: (decision: "confirmed" | "needs_revision") => void;
  onRelationReviewDecision: (decision: "confirmed" | "needs_revision") => void;
  onUpload: (file: File | null) => void;
}) {
  const [file, setFile] = useState<File | null>(null);
  const relationReviewRequired = Boolean(selected?.extracted_relations?.length);
  const relationReady = !relationReviewRequired || selected?.relation_decision === "confirmed" || selected?.relation_decision === "not_applicable";
  const canPublish = selected?.identity_decision === "confirmed" && relationReady;
  return (
    <div className="split-view">
      <section className="list-pane">
        <div className="pane-toolbar">
          <div>
            <p className="eyebrow">IngestAgent</p>
            <h2>文档解析与可选校正</h2>
          </div>
          <label className="upload-button">
            <Upload size={16} />
            选择文档
            <input
              type="file"
              accept=".docx,.pdf,.pptx,.xlsx"
              onChange={(event) => setFile(event.target.files?.[0] ?? null)}
            />
          </label>
        </div>
        <div className="upload-row">
          <span>{file?.name ?? "尚未选择文档"}</span>
          <div className="action-pair">
            <label className="switch-line">
              <input type="checkbox" checked={useLlm} onChange={(event) => setUseLlm(event.target.checked)} />
              <span>LLM 辅助摄入</span>
            </label>
            <button className="secondary-action" type="button" onClick={() => onUpload(file)}>
              {busy === "upload" ? <Loader2 className="spin" size={16} /> : <Archive size={16} />}
              提交处理
            </button>
          </div>
        </div>
        <div className="filter-toolbar">
          <div className="segmented-control">
            <button className={ingestFilter === "current" ? "active" : ""} type="button" onClick={() => onIngestFilterChange("current")} disabled={!currentDocumentId}>
              当前上传
            </button>
            <button className={ingestFilter === "pending" ? "active" : ""} type="button" onClick={() => onIngestFilterChange("pending")}>
              仅待审核
            </button>
            <button className={ingestFilter === "all" ? "active" : ""} type="button" onClick={() => onIngestFilterChange("all")}>
              全部历史
            </button>
          </div>
          <span className="filter-caption">
            {ingestFilter === "current"
              ? currentDocumentId || "当前还没有本次上传文档"
              : ingestFilter === "pending"
                ? "查看需要校正的解析结果"
                : "展示历史解析结果"}
          </span>
        </div>
        <div className="workspace-summary">
          <span className="count-pill">当前 {ingestFilterCounts.current}</span>
          <span className="count-pill">待审 {ingestFilterCounts.pending}</span>
          {currentDocumentId ? (
            <button className="mini-action" type="button" onClick={onClearCurrentSession}>
              清除当前聚焦
            </button>
          ) : null}
        </div>
        <div className="recent-runs">
          <div className="section-title compact">
            <div className="section-title-label">
              <History size={16} />
              <h3>最近上传</h3>
            </div>
          </div>
          <div className="run-list">
            {ingestRuns.length ? (
              ingestRuns.map((run) => (
                <button
                  className={`run-card ${run.document_id === currentDocumentId ? "active" : ""}`}
                  key={run.run_id}
                  type="button"
                  onClick={() => onSelectRun(run)}
                >
                  <div className="run-card-top">
                    <strong>{run.file_name || run.document_id}</strong>
                    <span className={`status-badge ${run.pending_review_count > 0 ? "pending_review" : "published"}`}>
                      {run.pending_review_count > 0 ? `${run.pending_review_count} 待审` : "已完成"}
                    </span>
                  </div>
                  <span>{formatRunTimestamp(run.created_at)}</span>
                  <span>
                    {run.use_llm ? "LLM" : "Rule"} · {run.proposals_created} proposals
                  </span>
                </button>
              ))
            ) : (
              <EmptyState title="暂无上传运行" text="上传文档后，这里会显示最近的处理记录。" />
            )}
          </div>
        </div>
        <div className="candidate-list">
          {reviewPackages.length ? (
            reviewPackages.map((reviewPackage) => (
              <button
                className={`candidate-row ${reviewPackage.package_id === selectedId ? "active" : ""}`}
                key={reviewPackage.package_id}
                type="button"
                onClick={() => onSelect(reviewPackage.package_id)}
              >
                <div>
                  <strong>{reviewPackage.title}</strong>
                  <span>{reviewPackage.business_type} · {Math.round(reviewPackage.confidence * 100)}%</span>
                </div>
                <StatusBadge status={reviewPackage.status} />
              </button>
            ))
          ) : (
            <EmptyState title="当前过滤器下没有解析结果" text="切换到“仅待校正”或“全部历史”，或先上传新文档。" />
          )}
        </div>
      </section>

      <section className="detail-pane">
        {selected ? (
          <>
            <div className="detail-head">
              <div>
                <p className="eyebrow">{selected.package_id}</p>
                <h2>{selected.title}</h2>
              </div>
              <StatusBadge status={selected.status} />
            </div>
            <div className="review-package-layout">
              <section className="review-card">
                <p className="eyebrow">Document Identity</p>
                <h3>文档身份</h3>
                <div className="identity-grid">
                  <Metric label="业务类型" value={selected.business_type} />
                  <Metric label="效力层级" value={selected.effective_level || "待确认"} />
                  <Metric label="强约束" value={selected.is_binding ? "是" : "否"} />
                  <Metric label="置信度" value={`${Math.round(selected.confidence * 100)}%`} />
                </div>
                {selected.notes.length ? (
                  <div className="note-stack">
                    {selected.notes.map((note) => (
                      <p key={note}>{note}</p>
                    ))}
                  </div>
                ) : null}
                <div className="decision-form">
                  <label>
                    <span>确认业务类型</span>
                    <select value={decisionBusinessType} onChange={(event) => onDecisionBusinessType(event.target.value)}>
                      <option value="external_mandatory">external_mandatory</option>
                      <option value="external_reference">external_reference</option>
                      <option value="internal_controlled">internal_controlled</option>
                      <option value="operational_evidence">operational_evidence</option>
                      <option value="feedback">feedback</option>
                      <option value="unknown">unknown</option>
                    </select>
                  </label>
                  <label>
                    <span>确认效力层级</span>
                    <input value={decisionEffectiveLevel} onChange={(event) => onDecisionEffectiveLevel(event.target.value)} />
                  </label>
                  <label className="switch-line wide">
                    <input type="checkbox" checked={decisionIsBinding} onChange={(event) => onDecisionIsBinding(event.target.checked)} />
                    <span>确认可作为强约束</span>
                  </label>
                  <label>
                    <span>审核人</span>
                    <input value={decisionReviewedBy} onChange={(event) => onDecisionReviewedBy(event.target.value)} placeholder="姓名或账号" />
                  </label>
                  <label>
                    <span>审核备注</span>
                    <textarea value={decisionNotes} onChange={(event) => onDecisionNotes(event.target.value)} rows={4} />
                  </label>
                  <div className="action-pair">
                    <button className="secondary-action danger" type="button" onClick={() => onReviewDecision("needs_revision")}>
                      {busy === selected.package_id ? <Loader2 className="spin" size={16} /> : <X size={16} />}
                      退回重判
                    </button>
                    <button className="primary-action" type="button" onClick={() => onReviewDecision("confirmed")}>
                      {busy === selected.package_id ? <Loader2 className="spin" size={16} /> : <Check size={16} />}
                      确认文档身份
                    </button>
                  </div>
                </div>
              </section>

              <section className="review-card">
                <p className="eyebrow">Human Gate</p>
                <h3>待人工确认</h3>
                <div className="review-list">
                  {selected.human_questions.map((item) => (
                    <article key={item.question_id} className="review-row">
                      <strong>{item.question}</strong>
                      <p>{item.rationale}</p>
                    </article>
                  ))}
                </div>
              </section>

              <section className="review-card">
                <p className="eyebrow">Risk</p>
                <h3>风险与缺口</h3>
                <div className="review-list">
                  {selected.issues.length ? (
                    selected.issues.map((item) => (
                      <article key={item.issue_id} className="review-row">
                        <strong>{item.detail}</strong>
                        <RiskBadge risk={item.severity} />
                      </article>
                    ))
                  ) : (
                    <EmptyState title="暂无风险" text="当前审批包没有自动标出的高风险问题。" />
                  )}
                </div>
              </section>

              <section className="review-card">
                <p className="eyebrow">Objects</p>
                <h3>抽取对象</h3>
                <div className="review-list">
                  {selected.extracted_objects.length ? (
                    selected.extracted_objects.map((item) => (
                      <article key={item.object_id} className="review-row">
                        <div className="object-top">
                          <strong>{item.name}</strong>
                          <RiskBadge risk={item.review_risk} />
                        </div>
                        <p>{item.object_type} · {Math.round(item.confidence * 100)}%</p>
                        {item.evidence_refs[0] ? <p>{item.evidence_refs[0].anchor_label}: {item.evidence_refs[0].quote}</p> : null}
                      </article>
                    ))
                  ) : (
                    <EmptyState title="暂无对象" text="当前审批包还没有抽取出可审阅对象。" />
                  )}
                </div>
              </section>

              <section className="review-card">
                <p className="eyebrow">Relations</p>
                <h3>对象关系</h3>
                <div className="review-list">
                  {selected.extracted_relations?.length ? (
                    selected.extracted_relations.map((item) => (
                      <article key={item.relation_id} className="review-row">
                        <div className="object-top">
                          <strong>{item.from_object_id} → {item.to_object_id}</strong>
                          <span className={`badge ${item.human_required ? "high" : "low"}`}>{item.human_required ? "需确认" : "自动"}</span>
                        </div>
                        <p>{item.relation_type} · {item.claim_type} · {Math.round(item.confidence * 100)}%</p>
                        {item.evidence_refs[0] ? <p>{item.evidence_refs[0].anchor_label}: {item.evidence_refs[0].quote}</p> : null}
                      </article>
                    ))
                  ) : (
                    <EmptyState title="暂无关系" text="当前审批包还没有抽取出对象间关系。" />
                  )}
                </div>
              </section>

              <section className="review-card">
                <p className="eyebrow">Human Gate 2</p>
                <h3>关键关系确认</h3>
                {!relationReviewRequired ? (
                  <EmptyState title="无需二次确认" text="当前审批包没有抽取出需要发布前确认的对象关系。" />
                ) : (
                  <div className="review-form">
                    <div className="review-inline-status">
                      <StatusBadge status={selected.relation_decision === "confirmed" ? "ready_to_publish" : "pending_review"} />
                      <span>当前状态：{humanStatus(selected.relation_decision)}</span>
                    </div>
                    <label>
                      <span>关系审核人</span>
                      <input value={relationReviewedBy} onChange={(event) => onRelationReviewedBy(event.target.value)} placeholder="姓名或账号" />
                    </label>
                    <label>
                      <span>关系审核备注</span>
                      <textarea value={relationDecisionNotes} onChange={(event) => onRelationDecisionNotes(event.target.value)} rows={4} />
                    </label>
                    <div className="action-pair">
                      <button className="secondary-action danger" type="button" onClick={() => onRelationReviewDecision("needs_revision")} disabled={selected.identity_decision !== "confirmed"}>
                        {busy === `${selected.package_id}:relations` ? <Loader2 className="spin" size={16} /> : <X size={16} />}
                        退回重判
                      </button>
                      <button className="primary-action" type="button" onClick={() => onRelationReviewDecision("confirmed")} disabled={selected.identity_decision !== "confirmed"}>
                        {busy === `${selected.package_id}:relations` ? <Loader2 className="spin" size={16} /> : <Check size={16} />}
                        确认关键关系
                      </button>
                    </div>
                  </div>
                )}
              </section>

              <section className="review-card">
                <div className="detail-head compact">
                  <div>
                    <p className="eyebrow">Publish Candidates</p>
                    <h3>关联候选页</h3>
                  </div>
                </div>
                <div className="review-list">
                  {!canPublish ? (
                    <EmptyState
                      title="发布已锁定"
                      text={
                        selected.identity_decision !== "confirmed"
                          ? "先确认文档身份，再批准关联候选页发布。"
                          : "当前审批包还缺少关键关系确认，发布仍保持锁定。"
                      }
                    />
                  ) : null}
                  {relatedCandidates.length ? (
                    relatedCandidates.map((candidate) => (
                      <article key={candidate.candidate_id} className="candidate-review-row">
                        <div>
                          <strong>{candidate.title}</strong>
                          <p>{candidate.page_type} · {Math.round(candidate.confidence * 100)}%</p>
                        </div>
                        <div className="action-pair">
                          <button className="secondary-action danger" type="button" onClick={() => onDecision(candidate.candidate_id, "reject")} disabled={!canPublish}>
                            <X size={16} />
                            拒绝
                          </button>
                          <button className="primary-action" type="button" onClick={() => onDecision(candidate.candidate_id, "approve")} disabled={!canPublish}>
                            {busy === candidate.candidate_id ? <Loader2 className="spin" size={16} /> : <Check size={16} />}
                            批准发布
                          </button>
                        </div>
                      </article>
                    ))
                  ) : (
                    <EmptyState title="暂无候选页" text="该审批包尚未关联可发布页面。" />
                  )}
                </div>
              </section>
            </div>
          </>
        ) : (
          <EmptyState title="暂无解析结果" text="上传文档或运行 IngestAgent 后，这里会出现文档解析详情。" />
        )}
      </section>
    </div>
  );
}

function WikiView({
  pages,
  selected,
  selectedId,
  onSelect
}: {
  pages: WikiPage[];
  selected?: WikiPage;
  selectedId: string;
  onSelect: (id: string) => void;
}) {
  return (
    <div className="split-view">
      <section className="list-pane">
        <div className="pane-toolbar">
          <div>
            <p className="eyebrow">Wiki Layer</p>
            <h2>页面浏览</h2>
          </div>
          <span className="count-pill">{pages.length} pages</span>
        </div>
        <div className="page-list">
          {pages.map((page) => (
            <button
              className={`wiki-row ${page.page_id === selectedId ? "active" : ""}`}
              key={page.page_id}
              type="button"
              onClick={() => onSelect(page.page_id)}
            >
              <strong>{page.title}</strong>
              <span>{page.page_type} · {page.source_refs.length} sources</span>
            </button>
          ))}
        </div>
      </section>
      <section className="detail-pane">
        {selected ? (
          <>
            <div className="detail-head">
              <div>
                <p className="eyebrow">{selected.page_type}</p>
                <h2>{selected.title}</h2>
              </div>
              <StatusBadge status={selected.review_status} />
            </div>
            <MarkdownPreview content={selected.markdown} />
          </>
        ) : (
          <EmptyState title="没有页面" text="发布 Wiki 页面后即可浏览 Markdown 和来源。" />
        )}
      </section>
    </div>
  );
}

function HistoryRail({
  indexStatus,
  useLlm,
  setUseLlm,
  topKPages,
  setTopKPages,
  chatHistory,
  selectedChatId,
  onSelectChat,
  onRebuildIndex,
  busy,
}: {
  indexStatus: IndexStatus | null;
  useLlm: boolean;
  setUseLlm: (value: boolean) => void;
  topKPages: number;
  setTopKPages: (value: number) => void;
  chatHistory: ChatHistoryEntry[];
  selectedChatId: string;
  onSelectChat: (chatId: string) => void;
  onRebuildIndex: () => void;
  busy: string;
}) {
  return (
    <div className="rail-stack">
      <div className="brand">
        <div className="brand-mark">
          <DatabaseZap size={22} />
        </div>
        <div>
          <strong>QT Wiki</strong>
          <span>工作台</span>
        </div>
      </div>

      <section className="rail-card">
        <div className="section-title compact">
          <div className="section-title-label">
            <Settings size={16} />
            <h3>快捷设置</h3>
          </div>
        </div>
        <div className={`index-chip ${indexStatus?.state ?? "missing"}`}>
          <span />
          <div>
            <strong>{formatIndexState(indexStatus?.state)}</strong>
            <small>{indexStatus?.lastBuilt ?? "not built"}</small>
          </div>
        </div>
        <label className="switch-line wide">
          <input type="checkbox" checked={useLlm} onChange={(event) => setUseLlm(event.target.checked)} />
          <span>启用 LLM</span>
        </label>
        <label className="rail-range">
          <span>召回页面数</span>
          <div>
            <input type="range" min={1} max={10} value={topKPages} onChange={(event) => setTopKPages(Number(event.target.value))} />
            <strong>{topKPages}</strong>
          </div>
        </label>
        <button className="icon-text-button" type="button" onClick={onRebuildIndex}>
          {busy === "index" ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
          重建索引
        </button>
      </section>

      <section className="rail-card rail-fill">
        <div className="section-title compact">
          <div className="section-title-label">
            <History size={16} />
            <h3>对话历史</h3>
          </div>
        </div>
        <div className="history-list">
          {chatHistory.length ? (
            chatHistory.map((item) => (
              <button
                className={`history-item ${selectedChatId === item.id ? "active" : ""}`}
                key={item.id}
                type="button"
                onClick={() => onSelectChat(item.id)}
              >
                <strong>{item.question}</strong>
                <span>{formatRunTimestamp(item.createdAt)}</span>
                <span>{item.status === "success" ? "已完成" : item.errorMessage || "失败"}</span>
              </button>
            ))
          ) : (
            <EmptyState title="暂无对话" text="在主 Chat 提问后，这里会保留历史记录。" />
          )}
        </div>
      </section>
    </div>
  );
}

function ChatbotPanel({
  question,
  setQuestion,
  activeChatEntry,
  activeView,
  busy,
  selectedCitation,
  selectedReviewPackage,
  selectedPage,
  issues,
  onSubmit,
  onAskSuggested,
  onSelectCitation,
}: {
  question: string;
  setQuestion: (value: string) => void;
  activeChatEntry?: ChatHistoryEntry;
  activeView: ViewKey;
  busy: string;
  selectedCitation?: Citation;
  selectedReviewPackage?: ReviewPackage;
  selectedPage?: WikiPage;
  issues: LintIssue[];
  onSubmit: () => void;
  onAskSuggested: (question: string) => void;
  onSelectCitation: (id: string) => void;
}) {
  const refs = activeView === "ingest" ? selectedReviewPackage?.source_refs : selectedPage?.source_refs;
  const result = activeChatEntry?.result ?? null;
  const trace = result?.trace?.length
    ? result.trace
    : activeView === "ingest" && selectedReviewPackage?.tool_trace.length
      ? selectedReviewPackage.tool_trace
      : ["load index", "rank pages", "load source refs"];
  const suggestedQuestions = result?.suggested_questions?.length ? result.suggested_questions : defaultSuggestedQuestions;

  return (
    <div className="chatbot-shell">
      <section className="chatbot-card chatbot-composer">
        <div className="composer-head">
          <div>
            <p className="eyebrow">Process Chat</p>
            <h2>流程问答</h2>
          </div>
          {activeChatEntry ? <span className="chatbot-mode">{result?.used_llm ? "LLM" : activeChatEntry.status === "error" ? "失败" : "规则"}</span> : null}
        </div>
        <label className="chat-input-shell">
          <Search size={16} />
          <textarea
            value={question}
            onChange={(event) => setQuestion(event.target.value)}
            placeholder="问公司流程怎么做、当前阶段要交付什么、引用来自哪里"
          />
        </label>
        <div className="suggestion-row" aria-label="推荐问题">
          {suggestedQuestions.slice(0, 5).map((item) => (
            <button key={item} type="button" onClick={() => onAskSuggested(item)} disabled={busy === "query"}>
              <Sparkles size={14} />
              <span>{item}</span>
            </button>
          ))}
        </div>
        <button className="primary-action" type="button" onClick={onSubmit}>
          {busy === "query" ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
          提问
        </button>
      </section>

      <section className="chatbot-card chatbot-answer">
        {activeChatEntry ? (
          activeChatEntry.status === "error" ? (
            <EmptyState title="查询失败" text={activeChatEntry.errorMessage || "未知错误"} />
          ) : result ? (
            <>
              <div className="answer-head">
                <strong>{activeChatEntry.question}</strong>
                <span>{result.used_llm ? "LLM" : "规则"}</span>
              </div>
              <RichAnswer text={result.answer} citations={result.citations} onSelectCitation={onSelectCitation} />
              {result.structured_matches?.length ? (
                <div className="review-list compact-list query-structured-list">
                  {result.structured_matches.map((item) => (
                    <article key={item.package_id} className="review-row">
                      <strong>{item.title}</strong>
                      <p>{item.business_type} · {item.object_count} objects · {item.relation_count} relations</p>
                    </article>
                  ))}
                </div>
              ) : null}
            </>
          ) : (
            <EmptyState title="暂无答案" text="当前对话还没有可展示的回答。" />
          )
        ) : (
          <EmptyState title="开始提问" text="主 Chat 会保留当前对话，文档、引用和输出可在抽屉中查看。" />
        )}
      </section>

      <section className="chatbot-card chatbot-context">
        <div className="chatbot-context-block">
          <p className="eyebrow">Evidence</p>
          <h3>来源</h3>
          {selectedCitation ? (
            <SourceBlock
              refItem={{
                document_id: selectedCitation.document_id ?? "",
                fragment_id: selectedCitation.fragment_id,
                file_name: selectedCitation.file_name,
                anchor_label: selectedCitation.anchor_label,
                quote: selectedCitation.quote,
              }}
            />
          ) : refs?.length ? (
            refs.slice(0, 2).map((ref) => <SourceBlock key={`${ref.document_id}-${ref.fragment_id ?? ref.anchor_label}`} refItem={ref} />)
          ) : (
            <EmptyState title="暂无来源" text="点击回答里的引用，或在中间选择页面/审批包。" />
          )}
        </div>
        <div className="chatbot-context-block">
          <p className="eyebrow">Trace</p>
          <h3>检索链路与风险</h3>
          <div className="trace-list">
            {trace.map((item) => (
              <span key={item}>{item}</span>
            ))}
          </div>
          <div className="risk-stack chat-risk-stack">
            {issues.slice(0, 2).map((issue) => (
              <div className="risk-row" key={issue.issue_id}>
                <RiskBadge risk={issue.severity} />
                <span>{issue.title}</span>
              </div>
            ))}
          </div>
        </div>
      </section>
    </div>
  );
}

function ProcessDrawer({
  activeDrawer,
  setActiveDrawer,
  activeChatResult,
  selectedCitation,
  selectedReviewPackage,
  selectedPage,
  selectedCitationId,
  currentDocumentId,
  ingestRuns,
  issues,
  indexStatus,
  activeView,
  workflowItems,
  setActiveView,
  onSelectCitation,
  onSelectRun,
  onRebuildIndex,
  busy,
}: {
  activeDrawer: DrawerKey;
  setActiveDrawer: (value: DrawerKey) => void;
  activeChatResult: QueryResult | null;
  selectedCitation?: Citation;
  selectedReviewPackage?: ReviewPackage;
  selectedPage?: WikiPage;
  selectedCitationId: string;
  currentDocumentId: string;
  ingestRuns: IngestRunSummary[];
  issues: LintIssue[];
  indexStatus: IndexStatus | null;
  activeView: ViewKey;
  workflowItems: NavItem[];
  setActiveView: (value: ViewKey) => void;
  onSelectCitation: (id: string) => void;
  onSelectRun: (run: IngestRunSummary) => void;
  onRebuildIndex: () => void;
  busy: string;
}) {
  const refs = selectedReviewPackage?.source_refs?.length ? selectedReviewPackage.source_refs : selectedPage?.source_refs ?? [];
  const trace = activeChatResult?.trace?.length ? activeChatResult.trace : selectedReviewPackage?.tool_trace ?? [];
  const drawerTabs: { key: DrawerKey; label: string }[] = [
    { key: "context", label: "上下文" },
    { key: "references", label: "引用" },
    { key: "outputs", label: "输出" },
    { key: "admin", label: "后台" },
  ];

  return (
    <aside className="process-drawer" aria-label="流程问答抽屉">
      <div className="drawer-tabs" role="tablist" aria-label="抽屉面板">
        {drawerTabs.map((tab) => (
          <button
            className={activeDrawer === tab.key ? "active" : ""}
            key={tab.key}
            type="button"
            role="tab"
            aria-selected={activeDrawer === tab.key}
            onClick={() => setActiveDrawer(tab.key)}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {activeDrawer === "context" && (
        <div className="drawer-body">
          <section className="drawer-card">
            <p className="eyebrow">Current Scope</p>
            <h2>文档上下文</h2>
            <div className="context-facts">
              <span>当前文档</span>
              <strong>{currentDocumentId || selectedReviewPackage?.document_id || "未选择"}</strong>
              <span>标题</span>
              <strong>{selectedReviewPackage?.title || selectedPage?.title || "PEP 流程文档"}</strong>
              <span>状态</span>
              <strong>{selectedReviewPackage ? humanStatus(selectedReviewPackage.identity_decision) : "待选择"}</strong>
            </div>
          </section>

          <section className="drawer-card metric-strip-card">
            <Metric label="索引来源" value={String(indexStatus?.sources ?? 0)} />
            <Metric label="Wiki 页面" value={String(indexStatus?.pages ?? 0)} />
            <Metric label="低置信度" value={String(issues.filter((issue) => issue.severity !== "low").length)} />
          </section>

          <section className="drawer-card">
            <div className="section-title compact">
              <div className="section-title-label">
                <History size={16} />
                <h3>最近上传</h3>
              </div>
            </div>
            <div className="drawer-run-list">
              {ingestRuns.slice(0, 4).map((run) => (
                <button className="run-card" key={run.run_id} type="button" onClick={() => onSelectRun(run)}>
                  <strong>{run.file_name || run.document_id}</strong>
                  <span>{formatRunTimestamp(run.created_at)}</span>
                  <span>{run.use_llm ? "LLM" : "Rule"} · {run.proposals_created} proposals</span>
                </button>
              ))}
              {!ingestRuns.length ? <EmptyState title="暂无上传" text="上传 PEP 后会在这里显示处理记录。" /> : null}
            </div>
          </section>
        </div>
      )}

      {activeDrawer === "references" && (
        <div className="drawer-body">
          <section className="drawer-card">
            <p className="eyebrow">Selected Evidence</p>
            <h2>Reference</h2>
            {selectedCitation ? (
              <SourceBlock
                refItem={{
                  document_id: selectedCitation.document_id ?? "",
                  fragment_id: selectedCitation.fragment_id,
                  file_name: selectedCitation.file_name,
                  anchor_label: selectedCitation.anchor_label,
                  quote: selectedCitation.quote,
                }}
              />
            ) : refs.length ? (
              refs.slice(0, 3).map((ref) => <SourceBlock key={`${ref.document_id}-${ref.fragment_id ?? ref.anchor_label}`} refItem={ref} />)
            ) : (
              <EmptyState title="暂无引用" text="提问后会显示命中的文件、章节和 quote。" />
            )}
          </section>

          <section className="drawer-card">
            <h3>回答引用</h3>
            <div className="citation-list">
              {activeChatResult?.citations.length ? (
                activeChatResult.citations.map((citation) => (
                  <button
                    className={selectedCitationId === citation.citation_id ? "active" : ""}
                    key={citation.citation_id}
                    type="button"
                    onClick={() => onSelectCitation(citation.citation_id)}
                  >
                    <strong>{citation.page_title || citation.file_name}</strong>
                    <span>{citation.anchor_label || citation.fragment_id || "章节待定位"}</span>
                  </button>
                ))
              ) : (
                <EmptyState title="等待答案" text="完成一次问答后，这里会列出全部引用。" />
              )}
            </div>
          </section>

          <section className="drawer-card">
            <h3>Trace</h3>
            <div className="trace-list drawer-trace-list">
              {trace.length ? trace.map((item) => <span key={item}>{item}</span>) : <span>ready</span>}
            </div>
          </section>
        </div>
      )}

      {activeDrawer === "outputs" && (
        <div className="drawer-body">
          <section className="drawer-card">
            <p className="eyebrow">Assets</p>
            <h2>输出资产</h2>
            <div className="output-grid">
              <article className="output-tile ready">
                <Archive size={18} />
                <strong>Markdown</strong>
                <span>answer.md</span>
              </article>
              <article className="output-tile ready">
                <FileSearch size={18} />
                <strong>Reference 表</strong>
                <span>references.md</span>
              </article>
              <article className="output-tile draft">
                <GitBranch size={18} />
                <strong>Mermaid</strong>
                <span>flow.mmd</span>
              </article>
              <article className="output-tile draft">
                <Activity size={18} />
                <strong>BU Diff</strong>
                <span>bu-diff.md</span>
              </article>
            </div>
          </section>
          <section className="drawer-card">
            <h3>当前答案</h3>
            {activeChatResult ? (
              <div className="export-preview compact-export-preview">
                <strong>{activeChatResult.used_llm ? "LLM" : "Rule"} · {activeChatResult.confidence}</strong>
                <p>{activeChatResult.answer.slice(0, 240)}</p>
              </div>
            ) : (
              <EmptyState title="暂无答案" text="完成问答后可生成 Markdown、Reference 和流程图资产。" />
            )}
          </section>
        </div>
      )}

      {activeDrawer === "admin" && (
        <div className="drawer-body">
          <section className="drawer-card">
            <p className="eyebrow">Background Console</p>
            <h2>{titleForView(activeView)}</h2>
            <div className="admin-nav-grid">
              {workflowItems.map((item) => {
                const Icon = item.icon;
                return (
                  <button className={activeView === item.key ? "active" : ""} key={item.key} type="button" onClick={() => setActiveView(item.key)}>
                    <Icon size={16} />
                    <span>{item.label}</span>
                  </button>
                );
              })}
            </div>
          </section>
          <section className="drawer-card">
            <div className={`index-chip ${indexStatus?.state ?? "missing"}`}>
              <span />
              <div>
                <strong>{formatIndexState(indexStatus?.state)}</strong>
                <small>{indexStatus?.lastBuilt ?? "not built"}</small>
              </div>
            </div>
            <button className="icon-text-button" type="button" onClick={onRebuildIndex}>
              {busy === "index" ? <Loader2 className="spin" size={16} /> : <RefreshCw size={16} />}
              重建索引
            </button>
          </section>
        </div>
      )}
    </aside>
  );
}

function QueryView({
  question,
  setQuestion,
  useLlm,
  setUseLlm,
  topKPages,
  setTopKPages,
  result,
  busy,
  onSubmit,
  onSelectCitation
}: {
  question: string;
  setQuestion: (value: string) => void;
  useLlm: boolean;
  setUseLlm: (value: boolean) => void;
  topKPages: number;
  setTopKPages: (value: number) => void;
  result: QueryResult | null;
  busy: string;
  onSubmit: () => void;
  onSelectCitation: (id: string) => void;
}) {
  return (
    <div className="query-view">
      <section className="query-composer">
        <div className="composer-head">
          <div>
            <p className="eyebrow">QueryAgent</p>
            <h2>索引召回问答</h2>
          </div>
          <label className="switch-line">
            <input type="checkbox" checked={useLlm} onChange={(event) => setUseLlm(event.target.checked)} />
            <span>LLM 生成</span>
          </label>
        </div>
        <textarea value={question} onChange={(event) => setQuestion(event.target.value)} />
        <div className="composer-foot">
          <label>
            召回页面
            <input
              type="range"
              min={1}
              max={10}
              value={topKPages}
              onChange={(event) => setTopKPages(Number(event.target.value))}
            />
            <span>{topKPages}</span>
          </label>
          <button className="primary-action" type="button" onClick={onSubmit}>
            {busy === "query" ? <Loader2 className="spin" size={16} /> : <Search size={16} />}
            执行查询
          </button>
        </div>
      </section>

      <section className="answer-panel">
        {result ? (
          <>
            <div className="answer-head">
              <StatusBadge status={result.confidence === "high" ? "published" : "pending_review"} />
              <span>{result.used_llm ? "LLM 已参与" : "规则式回答"}</span>
            </div>
            <RichAnswer text={result.answer} citations={result.citations} onSelectCitation={onSelectCitation} />
            <div className="trace-strip">
              {result.trace.map((item) => (
                <span key={item}>{item}</span>
              ))}
            </div>
            {result.structured_matches?.length ? (
              <div className="review-list compact-list">
                {result.structured_matches.map((item) => (
                  <article key={item.package_id} className="review-row">
                    <strong>{item.title}</strong>
                    <p>{item.business_type} · {item.relation_count} relations · {item.object_count} objects</p>
                  </article>
                ))}
              </div>
            ) : null}
          </>
        ) : (
          <EmptyState title="等待提问" text="QueryAgent 会先查机器索引，再加载少量 Wiki 页面和 source_refs。" />
        )}
      </section>
    </div>
  );
}

function LintView({ issues, busy, onScan }: { issues: LintIssue[]; busy: string; onScan: () => void }) {
  return (
    <div className="view-stack">
      <section className="pane-toolbar lint-toolbar">
        <div>
          <p className="eyebrow">LintAgent</p>
          <h2>健康问题</h2>
        </div>
        <button className="primary-action" type="button" onClick={onScan}>
          {busy === "lint" ? <Loader2 className="spin" size={16} /> : <Gauge size={16} />}
          运行扫描
        </button>
      </section>
      <section className="issue-board">
        {issues.map((issue) => (
          <article className={`issue-card ${issue.severity}`} key={issue.issue_id}>
            <div className="issue-top">
              <strong>{issue.title}</strong>
              <RiskBadge risk={issue.severity} />
            </div>
            <span>{issue.target}</span>
            <p>{issue.detail}</p>
            <footer>{issue.suggestion}</footer>
          </article>
        ))}
      </section>
    </div>
  );
}

function SettingsView({
  indexStatus,
  useLlm,
  setUseLlm,
  onRebuild,
  onLoadMappingMatrix,
  onLoadSlidesOutline,
  mappingMatrixExport,
  slidesOutlineExport,
  busy
}: {
  indexStatus: IndexStatus | null;
  useLlm: boolean;
  setUseLlm: (value: boolean) => void;
  onRebuild: () => Promise<void>;
  onLoadMappingMatrix: () => Promise<void>;
  onLoadSlidesOutline: () => Promise<void>;
  mappingMatrixExport: MappingMatrixExport | null;
  slidesOutlineExport: SlidesOutlineExport | null;
  busy: string;
}) {
  return (
    <div className="settings-grid">
      <section className="settings-section">
        <h2>索引策略</h2>
        <p>Index 层只由程序生成，QueryAgent 默认只读取索引和命中页面。</p>
        <Metric label="页面" value={String(indexStatus?.pages ?? 0)} />
        <Metric label="术语" value={String(indexStatus?.terms ?? 0)} />
        <Metric label="来源" value={String(indexStatus?.sources ?? 0)} />
        <button className="primary-action" type="button" onClick={() => void onRebuild()}>
          <RefreshCw size={16} />
          重建 Index
        </button>
      </section>
      <section className="settings-section">
        <h2>模型边界</h2>
        <p>LLM 只能基于召回页面和来源引用生成回答，不能默认读取全量 Wiki。</p>
        <label className="switch-line wide">
          <input type="checkbox" checked={useLlm} onChange={(event) => setUseLlm(event.target.checked)} />
          <span>默认启用 LLM 生成</span>
        </label>
      </section>
      <section className="settings-section">
        <h2>结构化导出</h2>
        <p>导出只消费已批准审批包，不直接重新读取 Raw。</p>
        <div className="action-pair">
          <button className="secondary-action" type="button" onClick={() => void onLoadMappingMatrix()}>
            {busy === "mapping-export" ? <Loader2 className="spin" size={16} /> : <Archive size={16} />}
            映射矩阵
          </button>
          <button className="secondary-action" type="button" onClick={() => void onLoadSlidesOutline()}>
            {busy === "slides-export" ? <Loader2 className="spin" size={16} /> : <Archive size={16} />}
            Slides 提纲
          </button>
        </div>
        {mappingMatrixExport ? (
          <div className="export-preview">
            <strong>映射矩阵</strong>
            <p>{mappingMatrixExport.package_count} 个审批包，{mappingMatrixExport.row_count} 行要求映射</p>
            <p>{mappingMatrixExport.rows[0] ? `${mappingMatrixExport.rows[0].requirement_name} -> ${mappingMatrixExport.rows[0].mapped_process_steps.map((item) => item.name).join("、") || "暂无步骤"}` : "暂无映射行"}</p>
          </div>
        ) : null}
        {slidesOutlineExport ? (
          <div className="export-preview">
            <strong>Slides 提纲</strong>
            <p>{slidesOutlineExport.slide_count} 页</p>
            <pre>{slidesOutlineExport.markdown}</pre>
          </div>
        ) : null}
      </section>
    </div>
  );
}

function ContextPanel({
  activeView,
  selectedReviewPackage,
  selectedPage,
  selectedCitation,
  queryResult,
  issues
}: {
  activeView: ViewKey;
  selectedReviewPackage?: ReviewPackage;
  selectedPage?: WikiPage;
  selectedCitation?: Citation;
  queryResult: QueryResult | null;
  issues: LintIssue[];
}) {
  const refs = activeView === "ingest" ? selectedReviewPackage?.source_refs : selectedPage?.source_refs;
  return (
    <>
      <section className="context-section">
        <p className="eyebrow">Evidence</p>
        <h2>来源面板</h2>
        {selectedCitation ? (
          <SourceBlock
            refItem={{
              document_id: selectedCitation.document_id ?? "",
              fragment_id: selectedCitation.fragment_id,
              file_name: selectedCitation.file_name,
              anchor_label: selectedCitation.anchor_label,
              quote: selectedCitation.quote
            }}
          />
        ) : refs?.length ? (
          refs.map((ref) => <SourceBlock key={`${ref.document_id}-${ref.fragment_id ?? ref.anchor_label}`} refItem={ref} />)
        ) : (
          <EmptyState title="暂无来源" text="选择候选页、Wiki 页面或查询引用后展示证据。" />
        )}
      </section>

      <section className="context-section">
        <p className="eyebrow">Agent Trace</p>
        <h2>运行轨迹</h2>
        <div className="trace-list">
          {(
            activeView === "ingest" && selectedReviewPackage?.tool_trace.length
              ? selectedReviewPackage.tool_trace
              : queryResult?.trace.length
                ? queryResult.trace
                : ["load index", "rank pages", "load source_refs", "human review gate"]
          ).map((item) => (
            <span key={item}>{item}</span>
          ))}
        </div>
      </section>

      <section className="context-section">
        <p className="eyebrow">Risk</p>
        <h2>健康摘要</h2>
        <div className="risk-stack">
          {issues.slice(0, 3).map((issue) => (
            <div className="risk-row" key={issue.issue_id}>
              <RiskBadge risk={issue.severity} />
              <span>{issue.title}</span>
            </div>
          ))}
        </div>
      </section>
    </>
  );
}

function Metric({ label, value }: { label: string; value: string }) {
  return (
    <div className="metric">
      <span>{label}</span>
      <strong>{value}</strong>
    </div>
  );
}

function StatusBadge({ status }: { status: string }) {
  return <span className={`status-badge ${status}`}>{humanStatus(status)}</span>;
}

function RiskBadge({ risk }: { risk: string }) {
  return <span className={`risk-badge ${risk}`}>{risk === "high" ? "高" : risk === "medium" ? "中" : "低"}</span>;
}

function SourceBlock({ refItem }: { refItem: { document_id: string; fragment_id?: string; file_name?: string; anchor_label?: string; quote?: string } }) {
  return (
    <article className="source-block">
      <strong>{refItem.file_name || refItem.document_id}</strong>
      <span>{[refItem.document_id, refItem.fragment_id, refItem.anchor_label].filter(Boolean).join(" / ")}</span>
      <p>{refItem.quote || "暂无摘录。"}</p>
    </article>
  );
}

function MarkdownPreview({ content }: { content: string }) {
  const html = useMemo(() => markdownToHtml(content), [content]);
  return <div className="markdown-preview" dangerouslySetInnerHTML={{ __html: html }} />;
}

function RichAnswer({
  text,
  citations,
  onSelectCitation
}: {
  text: string;
  citations: Citation[];
  onSelectCitation: (id: string) => void;
}) {
  const citationIds = new Set(citations.map((item) => item.citation_id));
  return (
    <div className="rich-answer">
      {text.split(/\n{2,}/).map((paragraph) => (
        <p key={paragraph}>
          {paragraph.split(/(\[c\d+\])/g).map((part) => {
            const id = part.replace("[", "").replace("]", "");
            if (citationIds.has(id)) {
              return (
                <button className="citation-button" key={part} type="button" onClick={() => onSelectCitation(id)}>
                  {part}
                </button>
              );
            }
            return <span key={part}>{part}</span>;
          })}
        </p>
      ))}
    </div>
  );
}

function EmptyState({ title, text }: { title: string; text: string }) {
  return (
    <div className="empty-state">
      <strong>{title}</strong>
      <span>{text}</span>
    </div>
  );
}

function markdownToHtml(markdown: string) {
  return markdown
    .replace(/&/g, "&amp;")
    .replace(/</g, "&lt;")
    .replace(/>/g, "&gt;")
    .split("\n")
    .map((line) => {
      if (line.startsWith("# ")) return `<h1>${line.slice(2)}</h1>`;
      if (line.startsWith("## ")) return `<h2>${line.slice(3)}</h2>`;
      if (line.startsWith("- ")) return `<li>${line.slice(2)}</li>`;
      if (!line.trim()) return "";
      return `<p>${line}</p>`;
    })
    .join("");
}

function titleForView(view: ViewKey) {
  return navItems.find((item) => item.key === view)?.label ?? "QT Wiki";
}

function createChatId() {
  return `chat-${Date.now()}-${Math.random().toString(16).slice(2, 8)}`;
}

function formatRunTimestamp(value: string) {
  return value.replace("T", " ").slice(0, 16);
}

function formatIndexState(state?: string) {
  if (state === "fresh") return "索引正常";
  if (state === "stale") return "索引过期";
  return "索引缺失";
}

function matchesIngestFilter(
  documentId: string,
  status: string,
  currentDocumentId: string,
  filter: "current" | "pending" | "all"
) {
  if (filter === "current") {
    return Boolean(currentDocumentId) && documentId === currentDocumentId;
  }
  if (filter === "pending") {
    return status === "pending" || status === "pending_review" || status === "identity_confirmed" || status === "pending_revision";
  }
  return true;
}

function errorMessage(error: unknown) {
  if (error instanceof ApiRequestError) {
    return error.message;
  }
  if (error instanceof Error) {
    return error.message;
  }
  return "未知错误";
}

function humanStatus(status: string) {
  const map: Record<string, string> = {
    pending: "待审核",
    pending_review: "待审核",
    identity_confirmed: "身份已确认",
    pending_revision: "待重判",
    ready_to_publish: "可发布",
    confirmed: "已确认",
    not_applicable: "不适用",
    approved: "已批准",
    published: "已发布",
    generated: "已生成",
    rejected: "已拒绝",
    high: "高置信"
  };
  return map[status] ?? status;
}

