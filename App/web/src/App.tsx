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
import { type ReactNode, useEffect, useMemo, useState } from "react";
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
  getSessionHandoff,
  getSlidesOutlineExport,
  getWikiPages,
  querySession,
  queryWiki,
  rebuildIndex,
  rejectCandidate,
  runLintScan,
  uploadDocument
} from "./api";
import type {
  AgentSummary,
  AnswerRunStepPayload,
  CandidatePage,
  Citation,
  IndexStatus,
  IngestRunSummary,
  LintIssue,
  MappingMatrixExport,
  NavItem,
  QueryResult,
  ReviewPackage,
  SessionHandoff,
  StructuredMatch,
  SessionTreeNode,
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

const DEFAULT_MODEL_PROFILE = "azure-gpt-5.4";

interface ChatHistoryEntry {
  id: string;
  question: string;
  result: QueryResult | null;
  createdAt: string;
  status: "running" | "success" | "error";
  errorMessage?: string;
}

type DrawerKey = "context" | "references" | "outputs" | "admin";
type SourcePanelMode = "sources" | "tree" | "graph";

interface ReviewQueueItem {
  id: string;
  group: string;
  title: string;
  detail: string;
  status: string;
  severity: string;
  target?: string;
}

interface SessionSourceCard {
  document_id: string;
  file_name: string;
  title: string;
  status: string;
  section_count?: number;
  review_count?: number;
  created_at?: string;
}

type AnswerRunStatus = "waiting" | "running" | "done" | "warning" | "deferred";

interface AnswerRunStep {
  id: string;
  label: string;
  detail: string;
  status: AnswerRunStatus;
  meta?: string[];
  thoughts?: string[];
  rawOutputs?: Record<string, unknown>;
}

type RichAnswerBlock =
  | { type: "heading"; text: string; level: 2 | 3 }
  | { type: "paragraph"; text: string }
  | { type: "ul"; items: string[] }
  | { type: "ol"; items: string[]; start?: number };

interface AnswerRunTraceItem {
  label: string;
  detail: string;
  meta?: string;
  status: AnswerRunStatus;
}

interface PinnedNoteItem {
  id: string;
  kind: "answer" | "reference";
  title: string;
  text: string;
  meta: string;
  createdAt: string;
}

export default function App() {
  const [activeView, setActiveView] = useState<ViewKey>("dashboard");
  const [sourcePanelMode, setSourcePanelMode] = useState<SourcePanelMode>("sources");
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
  const [modelProfile, setModelProfile] = useState(DEFAULT_MODEL_PROFILE);
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
  const [selectedSourceIds, setSelectedSourceIds] = useState<string[]>([]);
  const [ingestFilter, setIngestFilter] = useState<"current" | "pending" | "all">("pending");
  const [sessionHandoff, setSessionHandoff] = useState<SessionHandoff | null>(null);
  const [handoffBusy, setHandoffBusy] = useState(false);
  const [handoffError, setHandoffError] = useState("");
  const [selectedTreeNodeId, setSelectedTreeNodeId] = useState("");
  const [pinnedNotes, setPinnedNotes] = useState<PinnedNoteItem[]>([]);

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
  const activeChatResult = activeChatEntry ? activeChatEntry.result : queryResult;
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
  const activeSessionDocumentId = currentDocumentId || selectedReviewPackage?.document_id || "";
  const selectedTreeNode = sessionHandoff?.tree.items.find((item) => item.node_id === selectedTreeNodeId);
  const activeSourceName = sessionHandoff?.source.file_name || sourceNameForDocument(activeSessionDocumentId, reviewPackages, ingestRuns) || "All Sources";
  const sessionSourceCards = useMemo(() => buildSessionSourceCards(reviewPackages, ingestRuns), [reviewPackages, ingestRuns]);
  const selectedSessionDocumentIds = useMemo(
    () => selectedSourceIds.filter((documentId) => sessionSourceCards.some((card) => card.document_id === documentId)),
    [selectedSourceIds, sessionSourceCards]
  );
  const effectiveSessionDocumentIds = selectedSessionDocumentIds.length
    ? selectedSessionDocumentIds
    : activeSessionDocumentId
      ? [activeSessionDocumentId]
      : [];

  useEffect(() => {
    setSelectedSourceIds((current) => {
      const availableIds = sessionSourceCards.map((card) => card.document_id);
      const validIds = current.filter((documentId) => availableIds.includes(documentId));
      const fallbackIds = activeSessionDocumentId && availableIds.includes(activeSessionDocumentId)
        ? [activeSessionDocumentId]
        : availableIds.slice(0, 1);
      const nextIds = validIds.length ? validIds : fallbackIds;
      return sameStringArray(current, nextIds) ? current : nextIds;
    });
  }, [sessionSourceCards, activeSessionDocumentId]);

  useEffect(() => {
    setSourcePanelMode("sources");
  }, [activeSessionDocumentId]);

  useEffect(() => {
    let cancelled = false;
    if (!activeSessionDocumentId) {
      setSessionHandoff(null);
      setHandoffError("");
      setSelectedTreeNodeId("");
      return () => {
        cancelled = true;
      };
    }

    setHandoffBusy(true);
    setHandoffError("");
    setSessionHandoff(null);
    setSelectedTreeNodeId("");
    getSessionHandoff(activeSessionDocumentId)
      .then((payload) => {
        if (cancelled) {
          return;
        }
        setSessionHandoff(payload);
        setSelectedTreeNodeId((current) => {
          if (payload.tree.items.some((item) => item.node_id === current)) {
            return current;
          }
          return payload.tree.items[0]?.node_id ?? "";
        });
      })
      .catch((error) => {
        if (cancelled) {
          return;
        }
        setSessionHandoff(null);
        setHandoffError(errorMessage(error));
        setSelectedTreeNodeId("");
      })
      .finally(() => {
        if (!cancelled) {
          setHandoffBusy(false);
        }
      });

    return () => {
      cancelled = true;
    };
  }, [activeSessionDocumentId]);

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
    if (busy === "query") {
      return;
    }
    const nextQuestion = (questionOverride ?? question).trim();
    if (!nextQuestion) {
      return;
    }
    const chatId = createChatId();
    setBusy("query");
    setChatHistory((current) => [
      {
        id: chatId,
        question: nextQuestion,
        result: null,
        createdAt: new Date().toISOString(),
        status: "running",
      },
      ...current,
    ]);
    setSelectedChatId(chatId);
    setQuestion("");
    try {
      const sessionSourceScope = effectiveSessionDocumentIds.length ? { mode: "selected_docs", document_ids: effectiveSessionDocumentIds } : null;
      const result = sessionSourceScope
        ? await querySession(nextQuestion, sessionSourceScope, useLlm, Math.max(8, Math.min(topKPages, 30)), modelProfile)
        : await queryWiki(nextQuestion, useLlm, topKPages, modelProfile);
      setQueryResult(result);
      setSelectedCitationId(result.citations[0]?.citation_id ?? "");
      setChatHistory((current) => current.map((item) => (
        item.id === chatId ? { ...item, result, status: "success" } : item
      )));
      setToast(result.used_llm ? `Query used ${modelProfileLabel(modelProfile)}.` : "Query completed with evidence-first answer.");
    } catch (error) {
      setChatHistory((current) => current.map((item) => (
        item.id === chatId ? { ...item, status: "error", errorMessage: errorMessage(error) } : item
      )));
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
      if (result.document_id) {
        setSelectedSourceIds([result.document_id]);
      }
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
    setSelectedSourceIds((current) => current.includes(run.document_id) ? current : [run.document_id, ...current]);
    setIngestFilter("current");
    setSelectedPackageId(run.review_package_id || "");
    setActiveView("ingest");
    setToast(`已切换到运行 ${run.run_id}，当前聚焦文档 ${run.file_name || run.document_id}。`);
  }

  function handleSelectDocument(documentId: string) {
    const nextPackage = reviewPackages.find((item) => item.document_id === documentId);
    setCurrentDocumentId(documentId);
    setSelectedSourceIds((current) => current.includes(documentId) ? current : [documentId, ...current]);
    setIngestFilter("current");
    setSelectedPackageId(nextPackage?.package_id || "");
    setActiveView("query");
    setToast(`已切换 Ask Workspace source：${sourceNameForDocument(documentId, reviewPackages, ingestRuns) || nextPackage?.title || documentId}。`);
  }

  function handleClearCurrentSession() {
    setCurrentDocumentId("");
    setSelectedSourceIds([]);
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

  function handleToggleSource(documentId: string) {
    setSelectedSourceIds((current) => {
      if (current.includes(documentId)) {
        return current.length > 1 ? current.filter((item) => item !== documentId) : current;
      }
      return [documentId, ...current];
    });
    if (!currentDocumentId) {
      setCurrentDocumentId(documentId);
    }
  }

  function handlePinAnswer() {
    const result = activeChatEntry?.result ?? queryResult;
    if (!result) {
      setToast("先完成一次问答，再 pin 到 Note。");
      return;
    }
    setPinnedNotes((current) => [
      {
        id: `pin-answer-${Date.now()}`,
        kind: "answer",
        title: activeChatEntry?.question || "Pinned answer",
        text: result.answer.slice(0, 520),
        meta: `${result.used_llm ? "LLM" : "Rule"} · ${result.confidence} · ${result.citations.length} refs`,
        createdAt: new Date().toISOString(),
      },
      ...current,
    ]);
    setToast("已将当前回答 pin 到 Session Note。");
  }

  function handlePinCitation(citation?: Citation) {
    if (!citation) {
      setToast("先选择一个 reference，再 pin 到 Note。");
      return;
    }
    setPinnedNotes((current) => [
      {
        id: `pin-reference-${Date.now()}`,
        kind: "reference",
        title: citationTitle(citation),
        text: citation.quote || "暂无摘录。",
        meta: citationMeta(citation),
        createdAt: new Date().toISOString(),
      },
      ...current,
    ]);
    setToast("已将当前 reference pin 到 Session Note。");
  }

  return (
    <div className="app session-workspace-app">
      <header className="session-topbar">
        <div className="session-brand">
          <div className="brand-mark">
            <DatabaseZap size={22} />
          </div>
          <div>
            <p className="eyebrow">QT Wiki vNext</p>
            <h1>PEP Knowledge Session</h1>
          </div>
        </div>
        <div className="session-scope-strip" aria-label="当前 session scope">
          <span>Session PEP-R2</span>
          <span>{activeSourceName}</span>
          <span>{sessionHandoff?.source.parse_status || (handoffBusy ? "loading handoff" : "handoff idle")}</span>
          <span>{formatEvalSummary(sessionHandoff?.quality.eval_summary) || `${indexStatus?.sources ?? 0} sources indexed`}</span>
          <span>{useLlm ? modelProfileLabel(modelProfile) : "Rule mode"}</span>
        </div>
        <div className="session-actions">
          <label className="model-select">
            <span>模型</span>
            <select value={modelProfile} onChange={(event) => setModelProfile(event.target.value)}>
              <option value="azure-gpt-5">Azure GPT-5</option>
              <option value="azure-gpt-5.5">Azure GPT-5.5</option>
              <option value="azure-gpt-5.4">Azure GPT-5.4</option>
              <option value="azure-gpt-5-multimodal">GPT-5 Multimodal</option>
              <option value="azure-gpt-4o">Azure GPT-4o</option>
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

      <main className="session-grid">
        <SessionSourcePanel
          mode="sources"
          setMode={() => setSourcePanelMode("sources")}
          indexStatus={indexStatus}
          reviewPackages={reviewPackages}
          pages={pages}
          ingestRuns={ingestRuns}
          sourceCards={sessionSourceCards}
          selectedSourceIds={selectedSessionDocumentIds}
          currentDocumentId={currentDocumentId}
          sessionHandoff={sessionHandoff}
          handoffBusy={handoffBusy}
          handoffError={handoffError}
          selectedTreeNodeId={selectedTreeNodeId}
          selectedReviewPackage={selectedReviewPackage}
          selectedPage={selectedPage}
          onSelectRun={handleSelectRun}
          onSelectDocument={handleSelectDocument}
          onToggleSource={handleToggleSource}
          onSelectTreeNode={setSelectedTreeNodeId}
        />

        <section className="session-chat-stage" aria-label="Session chat">
          <div className="session-chat-titlebar">
            <div>
              <p className="eyebrow">Ask Workspace</p>
              <h2>围绕当前 source 提问，回答内可展开思考摘要和可定位引用</h2>
            </div>
            <div className="session-metrics">
              <Metric label="当前来源" value={sessionHandoff ? "Selected" : "All"} />
              <Metric label="引用" value={String(activeChatResult?.citations.length ?? 0)} />
              <Metric label="Note" value={String(pinnedNotes.length)} />
            </div>
          </div>
          <ChatbotPanel
            question={question}
            setQuestion={setQuestion}
            activeChatEntry={activeChatEntry}
            chatHistory={chatHistory}
            activeView={currentFlowView}
            busy={busy}
            selectedCitation={selectedCitation}
            selectedReviewPackage={selectedReviewPackage}
            selectedPage={selectedPage}
            sessionHandoff={sessionHandoff}
            selectedTreeNode={selectedTreeNode}
            issues={issues}
            onSubmit={() => void handleQuerySubmit()}
            onAskSuggested={handleSuggestedQuestion}
            onSelectCitation={setSelectedCitationId}
            onPinAnswer={handlePinAnswer}
          />
        </section>

        <SessionRightPanel
          activeChatResult={activeChatResult}
          selectedCitation={selectedCitation}
          selectedCitationId={selectedCitationId}
          handoffBusy={handoffBusy}
          handoffError={handoffError}
          onSelectCitation={setSelectedCitationId}
          onPinCitation={handlePinCitation}
        />
      </main>

      <div className="toast" role="status">
        <Activity size={15} />
        {toast}
      </div>
    </div>
  );
}

function SessionSourcePanel({
  mode,
  setMode,
  indexStatus,
  reviewPackages,
  pages,
  ingestRuns,
  sourceCards,
  selectedSourceIds,
  currentDocumentId,
  sessionHandoff,
  handoffBusy,
  handoffError,
  selectedTreeNodeId,
  selectedReviewPackage,
  selectedPage,
  onSelectRun,
  onSelectDocument,
  onToggleSource,
  onSelectTreeNode,
}: {
  mode: SourcePanelMode;
  setMode: (mode: SourcePanelMode) => void;
  indexStatus: IndexStatus | null;
  reviewPackages: ReviewPackage[];
  pages: WikiPage[];
  ingestRuns: IngestRunSummary[];
  sourceCards: SessionSourceCard[];
  selectedSourceIds: string[];
  currentDocumentId: string;
  sessionHandoff: SessionHandoff | null;
  handoffBusy: boolean;
  handoffError: string;
  selectedTreeNodeId: string;
  selectedReviewPackage?: ReviewPackage;
  selectedPage?: WikiPage;
  onSelectRun: (run: IngestRunSummary) => void;
  onSelectDocument: (documentId: string) => void;
  onToggleSource: (documentId: string) => void;
  onSelectTreeNode: (nodeId: string) => void;
}) {
  const warningSectionIds = useMemo(() => collectWarningSectionIds(sessionHandoff), [sessionHandoff]);
  const graphNodes = sessionHandoff?.graph.nodes.slice(0, 5).map((node) => node.label) ?? [
    selectedReviewPackage?.title || selectedPage?.title || "PEP Session",
    "R2",
    "PO",
    "QMP",
    "Reference",
  ];
  const treeItems = sessionHandoff?.tree.items ?? [];

  return (
    <aside className="session-source-panel" aria-label="Session sources">
      <div className="panel-topline">
        <div>
          <p className="eyebrow">Knowledge Base</p>
          <h2>Sources</h2>
        </div>
        <span className="count-pill">{selectedSourceIds.length}/{sourceCards.length || indexStatus?.sources || 0}</span>
      </div>

      {mode === "sources" && (
        <div className="source-panel-body">
          {handoffError ? <EmptyState title="当前 source 暂不可预览" text={handoffError} /> : null}
          <section className="source-scope-card source-selection-summary">
            <span>Source scope</span>
            <strong>{selectedSourceIds.length ? `${selectedSourceIds.length} selected` : "No source selected"}</strong>
            <small>勾选进入本轮 Chat；点击文件名只切换当前预览 source。</small>
          </section>
          <div className="source-list clean-source-list">
            {sourceCards.length ? (
              sourceCards.map((item) => (
                <article
                  className={`source-doc-card clean-source-card ${currentDocumentId === item.document_id ? "active" : ""} ${selectedSourceIds.includes(item.document_id) ? "selected" : ""}`}
                  key={item.document_id}
                >
                  <label className="source-select-check">
                    <input
                      type="checkbox"
                      checked={selectedSourceIds.includes(item.document_id)}
                      onChange={() => onToggleSource(item.document_id)}
                    />
                    <span>{selectedSourceIds.includes(item.document_id) ? "Selected" : "Use"}</span>
                  </label>
                  <button className="source-focus-button" type="button" onClick={() => onSelectDocument(item.document_id)}>
                    <strong>{item.file_name || item.title}</strong>
                    <span>{sourceReadableMeta(item)}</span>
                  </button>
                  <StatusBadge status={item.status} />
                </article>
              ))
            ) : (
              <EmptyState title="暂无 Sources" text="上传或解析 PEP 后，这里会显示 session 可用来源。" />
            )}
          </div>
        </div>
      )}

      {mode === "tree" && (
        <div className="source-panel-body">
          {handoffBusy ? <EmptyState title="正在加载章节树" text="等待 session handoff 返回真实 tree items。" /> : null}
          {handoffError ? <EmptyState title="章节树暂不可用" text={handoffError} /> : null}
          {treeItems.length ? (
            <section className="source-tree" aria-label="真实章节树">
              {treeItems.map((item) => {
                const level = item.node_type === "document" ? 0 : Math.min(item.level ?? 1, 3);
                const hasWarning = Boolean(item.section_id && warningSectionIds.has(item.section_id));
                return (
                  <button
                    className={`tree-node level-${level} ${selectedTreeNodeId === item.node_id ? "active" : ""} ${hasWarning ? "warn" : ""}`}
                    key={item.node_id}
                    type="button"
                    onClick={() => onSelectTreeNode(item.node_id)}
                  >
                    {item.node_type === "document" ? <Archive size={16} /> : <span />}
                    <div>
                      <strong>{item.title}</strong>
                      <small>{treeNodeMeta(item)}</small>
                    </div>
                    {hasWarning ? <ShieldAlert size={14} /> : null}
                  </button>
                );
              })}
            </section>
          ) : !handoffBusy && !handoffError ? (
            <EmptyState title="暂无真实 Tree" text="选择已 parse 的文档后，这里会显示 handoff tree。" />
          ) : null}
        </div>
      )}

      {mode === "graph" && (
        <div className="source-panel-body">
          <section className="source-graph" aria-label="Source relationship graph preview">
            {graphNodes.map((node, index) => (
              <div className={`graph-node node-${index}`} key={node}>
                {node}
              </div>
            ))}
          </section>
          <p className="graph-caption">
            {sessionHandoff
              ? `${sessionHandoff.graph.nodes.length} nodes · ${sessionHandoff.graph.edges.length} edges，当前只展示 contains / mentions seeds。`
              : "当前为本地关系预览，选择 parsed 文档后会从 handoff graph seeds 生成。"}
          </p>
        </div>
      )}
    </aside>
  );
}

function SessionRightPanel({
  activeChatResult,
  selectedCitation,
  selectedCitationId,
  handoffBusy,
  handoffError,
  onSelectCitation,
  onPinCitation,
}: {
  activeChatResult: QueryResult | null;
  selectedCitation?: Citation;
  selectedCitationId: string;
  handoffBusy: boolean;
  handoffError: string;
  onSelectCitation: (id: string) => void;
  onPinCitation: (citation?: Citation) => void;
}) {
  const citations = activeChatResult?.citations ?? [];
  const activeReference = selectedCitation ?? citations[0];
  return (
    <aside className="session-right-panel ask-reference-panel" aria-label="Reference viewer">
      <div className="ask-side-heading">
        <div>
          <p className="eyebrow">Reference</p>
          <h2>原文返回</h2>
        </div>
        <span className="count-pill">{citations.length} refs</span>
      </div>

      <div className="right-panel-body ask-side-body">
        <section className="session-note-card reference-viewer-card">
          <div className="reference-card-head">
            <h3>当前原文</h3>
            <button className="mini-action" type="button" onClick={() => onPinCitation(activeReference)} disabled={!activeReference}>
              Pin
            </button>
          </div>
          {handoffBusy ? <EmptyState title="正在加载 source" text="回答完成后会显示命中的原文 quote。" /> : null}
          {handoffError ? <EmptyState title="Reference 暂不可用" text={handoffError} /> : null}
          {!handoffBusy && !handoffError ? (
            activeReference ? (
              <ReferenceCard citation={activeReference} active={true} onSelect={onSelectCitation} onPin={onPinCitation} />
            ) : (
              <EmptyState title="等待原文返回" text="完成一次提问后，这里会显示文件、章节和 quote。" />
            )
          ) : null}
        </section>

        <section className="session-note-card citation-stack-card">
          <h3>本轮返回</h3>
          <div className="citation-stack readable-citation-stack">
            {citations.length ? (
              citations.map((citation) => (
                <ReferenceCard
                  citation={citation}
                  key={citation.citation_id}
                  active={selectedCitationId === citation.citation_id}
                  onSelect={onSelectCitation}
                  onPin={onPinCitation}
                />
              ))
            ) : (
              <EmptyState title="暂无原文" text="Ask Workspace 会把下一次回答命中的原文整理到这里。" />
            )}
          </div>
        </section>
      </div>
    </aside>
  );
}

function ReviewQueuePanel({
  sessionHandoff,
  handoffBusy,
  handoffError,
  selectedTreeNode,
}: {
  sessionHandoff: SessionHandoff | null;
  handoffBusy: boolean;
  handoffError: string;
  selectedTreeNode?: SessionTreeNode;
}) {
  const items = reviewQueueItems(sessionHandoff);
  return (
    <section className="review-queue-panel" aria-label="G9 review queue">
      <div className="review-queue-head">
        <div>
          <p className="eyebrow">G9 Review Queue</p>
          <h3>先审解析、视觉候选和证据质量</h3>
        </div>
        <span className="count-pill">{items.length}</span>
      </div>
      {selectedTreeNode ? (
        <div className="selected-tree-summary">
          <strong>{selectedTreeNode.title}</strong>
          <span>{treeNodeMeta(selectedTreeNode)}</span>
        </div>
      ) : null}
      {handoffBusy ? <EmptyState title="正在读取 handoff" text="Review queue 会汇总 parser、visual 和 answer quality findings。" /> : null}
      {handoffError ? <EmptyState title="Review queue 暂不可用" text={handoffError} /> : null}
      {!handoffBusy && !handoffError ? (
        items.length ? (
          <div className="review-queue-list">
            {items.slice(0, 5).map((item) => (
              <article className="review-queue-item" key={item.id}>
                <div>
                  <strong>{item.title}</strong>
                  <span>{item.group} · {item.status}{item.target ? ` · ${item.target}` : ""}</span>
                </div>
                <RiskBadge risk={item.severity} />
                <p>{item.detail}</p>
              </article>
            ))}
          </div>
        ) : (
          <EmptyState title="当前没有集中待审项" text="仍建议抽查 Tree、Table、Visual 和 Answer evidence 后再给结论。" />
        )
      ) : null}
    </section>
  );
}

function QualityPanel({
  sessionHandoff,
  handoffBusy,
  handoffError,
}: {
  sessionHandoff: SessionHandoff | null;
  handoffBusy: boolean;
  handoffError: string;
}) {
  const fusion = sessionHandoff?.quality.parser_fusion;
  const items = reviewQueueItems(sessionHandoff);
  return (
    <>
      <section className="session-note-card quality-card">
        <p className="eyebrow">Quality Gates</p>
        <h2>{sessionHandoff ? humanStatus(sessionHandoff.quality.parse_status) : "等待 handoff"}</h2>
        {handoffBusy ? <EmptyState title="正在读取质量门" text="加载 parser workflow、eval summary 和 fusion trace。" /> : null}
        {handoffError ? <EmptyState title="质量门暂不可用" text={handoffError} /> : null}
        {sessionHandoff ? (
          <div className="quality-grid">
            <Metric label="Eval" value={formatEvalSummary(sessionHandoff.quality.eval_summary) || "n/a"} />
            <Metric label="Review" value={String(items.length)} />
            <Metric label="Visual" value={String(sessionHandoff.quality.visual_review_items?.length ?? 0)} />
            <Metric label="Chunks" value={String(sessionHandoff.retrieval.chunk_count)} />
          </div>
        ) : null}
      </section>
      {sessionHandoff ? (
        <section className="session-note-card quality-card">
          <h3>Parser Fusion</h3>
          <div className="context-facts">
            <span>mode</span>
            <strong>{fusion?.fusion_mode || "unknown"}</strong>
            <span>providers</span>
            <strong>{fusion?.providers?.join(" / ") || "n/a"}</strong>
            <span>canonical</span>
            <strong>{formatRecordCounts(fusion?.canonical_output)}</strong>
          </div>
        </section>
      ) : null}
      {items.length ? (
        <section className="session-note-card quality-card">
          <h3>Findings</h3>
          <div className="quality-finding-list">
            {items.map((item) => (
              <article className="quality-finding" key={item.id}>
                <RiskBadge risk={item.severity} />
                <div>
                  <strong>{item.title}</strong>
                  <span>{item.detail}</span>
                </div>
              </article>
            ))}
          </div>
        </section>
      ) : null}
    </>
  );
}

function JsonInspector({ sessionHandoff, activeChatResult }: { sessionHandoff: SessionHandoff | null; activeChatResult: QueryResult | null }) {
  const payload = sessionHandoff ? compactHandoffForInspector(sessionHandoff, activeChatResult) : null;
  return (
    <section className="session-note-card json-inspector-card">
      <p className="eyebrow">Contract Inspector</p>
      <h2>Handoff JSON</h2>
      {payload ? (
        <pre>{JSON.stringify(payload, null, 2)}</pre>
      ) : (
        <EmptyState title="暂无 JSON" text="选择已有 parsed JSON 的文档后，这里显示 handoff 摘要和当前 answer trace。" />
      )}
    </section>
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
                <span>{chatHistoryStatusLabel(item)}</span>
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
  chatHistory,
  activeView,
  busy,
  selectedCitation,
  selectedReviewPackage,
  selectedPage,
  sessionHandoff,
  selectedTreeNode,
  issues,
  onSubmit,
  onAskSuggested,
  onSelectCitation,
  onPinAnswer,
}: {
  question: string;
  setQuestion: (value: string) => void;
  activeChatEntry?: ChatHistoryEntry;
  chatHistory: ChatHistoryEntry[];
  activeView: ViewKey;
  busy: string;
  selectedCitation?: Citation;
  selectedReviewPackage?: ReviewPackage;
  selectedPage?: WikiPage;
  sessionHandoff: SessionHandoff | null;
  selectedTreeNode?: SessionTreeNode;
  issues: LintIssue[];
  onSubmit: () => void;
  onAskSuggested: (question: string) => void;
  onSelectCitation: (id: string) => void;
  onPinAnswer: () => void;
}) {
  const result = activeChatEntry?.result ?? null;
  const suggestedQuestions = result?.suggested_questions?.length ? result.suggested_questions : defaultSuggestedQuestions;
  const transcriptEntries = chatHistory.slice(0, 8).reverse();

  return (
    <div className="session-chatbot-shell">
      <section className="chat-transcript-panel" aria-label="Session chat transcript">
        <div className="chat-transcript-head">
          <div>
            <p className="eyebrow">Process Chat</p>
            <h3>回答必须回到证据</h3>
          </div>
          <span className="chatbot-mode">{result?.used_llm ? "LLM" : activeChatEntry?.status === "error" ? "失败" : "Evidence first"}</span>
        </div>
        <div className="chat-message-list">
          {transcriptEntries.length ? (
            transcriptEntries.map((entry) => (
              <ChatExchange
                entry={entry}
                isActive={entry.id === activeChatEntry?.id}
                key={entry.id}
                onPinAnswer={onPinAnswer}
                onSelectCitation={onSelectCitation}
                sessionHandoff={sessionHandoff}
              />
            ))
          ) : (
            <EmptyState title="开始提问" text="底部输入问题，答案会在这里形成消息流，并把 citation 和 evidence 放到右侧核查。" />
          )}
        </div>
      </section>

      <section className="chat-composer-dock" aria-label="Chat composer">
        <div className="suggestion-row" aria-label="推荐问题">
          {suggestedQuestions.slice(0, 5).map((item) => (
            <button key={item} type="button" onClick={() => onAskSuggested(item)} disabled={busy === "query"}>
              <Sparkles size={14} />
              <span>{item}</span>
            </button>
          ))}
        </div>
        <form className="chat-dock-row" onSubmit={(event) => {
          event.preventDefault();
          onSubmit();
        }}>
          <label className="chat-input-shell">
            <Search size={16} />
            <textarea
              value={question}
              onChange={(event) => setQuestion(event.target.value)}
              onKeyDown={(event) => {
                if (event.key === "Enter" && !event.shiftKey) {
                  event.preventDefault();
                  onSubmit();
                }
              }}
              placeholder="问 R2 阶段、PO 动作、交付物或引用来源"
            />
          </label>
          <button
            className="primary-action"
            type="submit"
            disabled={busy === "query" || !question.trim()}
            onPointerDown={(event) => {
              if (busy === "query" || !question.trim()) {
                return;
              }
              event.preventDefault();
              onSubmit();
            }}
          >
            {busy === "query" ? <Loader2 className="spin" size={16} /> : <Sparkles size={16} />}
            提问
          </button>
        </form>
      </section>
    </div>
  );
}

function ChatExchange({
  entry,
  isActive,
  onPinAnswer,
  onSelectCitation,
  sessionHandoff,
}: {
  entry: ChatHistoryEntry;
  isActive: boolean;
  onPinAnswer: () => void;
  onSelectCitation: (id: string) => void;
  sessionHandoff: SessionHandoff | null;
}) {
  const result = entry.result;
  const thoughtSteps = buildAnswerRunSteps(entry, result, entry.status === "running", sessionHandoff);
  return (
    <>
      <article className={`chat-message user ${isActive ? "active" : ""}`}>
        <span>你 · {formatRunTimestamp(entry.createdAt)}</span>
        <p>{entry.question}</p>
      </article>
      {entry.status === "error" ? (
        <article className={`chat-message assistant error ${isActive ? "active" : ""}`}>
          <span>QT Wiki</span>
          <EmptyState title="查询失败" text={entry.errorMessage || "未知错误"} />
        </article>
      ) : result ? (
        <article className={`chat-message assistant ${isActive ? "active" : ""}`}>
          <span>QT Wiki · {result.used_llm ? "LLM" : "规则"} · {result.confidence}</span>
          <ChatThoughtDisclosure steps={thoughtSteps} isRunning={false} />
          <RichAnswer text={result.answer} citations={result.citations} onSelectCitation={onSelectCitation} />
          <div className="message-action-row">
            {isActive ? (
              <button className="mini-action" type="button" onClick={onPinAnswer}>
                Pin answer
              </button>
            ) : null}
            <span>{result.citations.length} readable references</span>
          </div>
          {result.structured_matches?.length ? (
            <div className="structured-chip-row">
              {result.structured_matches.slice(0, 3).map((item) => (
                <span key={structuredMatchKey(item)}>{structuredMatchTitle(item)} · {structuredMatchMeta(item)}</span>
              ))}
            </div>
          ) : null}
        </article>
      ) : (
        <article className={`chat-message assistant thinking ${isActive ? "active" : ""}`}>
          <span>QT Wiki · 思考中</span>
          <ChatThoughtDisclosure steps={thoughtSteps} isRunning={entry.status === "running"} />
        </article>
      )}
    </>
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
                  <article key={structuredMatchKey(item)} className="review-row">
                    <strong>{structuredMatchTitle(item)}</strong>
                    <p>{structuredMatchMeta(item)}</p>
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

function ReferenceCard({
  citation,
  active = false,
  onSelect,
  onPin,
}: {
  citation: Citation;
  active?: boolean;
  onSelect: (id: string) => void;
  onPin?: (citation?: Citation) => void;
}) {
  const detailRows = citationDetailRows(citation);
  const contextSegments = citationContextSegments(citation);
  return (
    <article className={`reference-card ${active ? "active" : ""}`}>
      <div className="reference-card-main">
        <button className="reference-select-button" type="button" onClick={() => onSelect(citation.citation_id)}>
          <strong>{citationTitle(citation)}</strong>
          <span>{citationMeta(citation)}</span>
          <p>{citation.quote || "暂无摘录。"}</p>
        </button>
        {onPin ? (
          <button className="mini-action" type="button" onClick={() => onPin(citation)}>
            Pin
          </button>
        ) : null}
      </div>
      <details className="reference-expand" open={active || undefined}>
        <summary>
          <ChevronRight size={14} />
          原文与定位
        </summary>
        <blockquote>{citation.quote || "暂无摘录。"}</blockquote>
        {contextSegments.length ? (
          <div className="reference-context-window" aria-label="引用前后文">
            {contextSegments.map((segment) => (
              <section className={`reference-context-segment ${segment.kind}`} key={segment.label}>
                <span>{segment.label}</span>
                <p>{segment.text}</p>
              </section>
            ))}
          </div>
        ) : null}
        <dl>
          {detailRows.map(([label, value]) => (
            <div key={label}>
              <dt>{label}</dt>
              <dd>{value}</dd>
            </div>
          ))}
        </dl>
      </details>
    </article>
  );
}

function ChatThoughtDisclosure({ steps, isRunning }: { steps: AnswerRunStep[]; isRunning: boolean }) {
  const summary = answerRunSummary(steps);
  const traceItems = answerRunTraceItems(steps, isRunning);
  const factItems = answerRunFactItems(steps);
  return (
    <details className="chat-thought-disclosure" open={isRunning || undefined}>
      <summary>
        {isRunning ? <Loader2 className="spin" size={14} /> : <Sparkles size={14} />}
        <strong>{isRunning ? "执行中" : "执行摘要"}</strong>
        <small>{summary.text}</small>
        <ChevronRight className="thought-chevron" size={14} />
      </summary>
      <div className="chat-thought-body">
        <ol className="chat-run-timeline">
          {traceItems.map((item) => (
            <li key={item.label} data-status={item.status}>
              <span>{item.label}</span>
              <p>{item.detail}</p>
              {item.meta ? <small>{item.meta}</small> : null}
            </li>
          ))}
        </ol>
        {factItems.length ? (
          <ul className="chat-thought-meta">
            {factItems.map((item) => (
              <li key={item}>{item}</li>
            ))}
          </ul>
        ) : null}
      </div>
    </details>
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
  const citationById = new Map(citations.map((item) => [item.citation_id, item]));
  const blocks = useMemo(() => parseRichAnswerBlocks(text), [text]);
  return (
    <div className="rich-answer">
      {blocks.map((block, index) => renderRichAnswerBlock(block, index, citationById, onSelectCitation))}
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

function chatHistoryStatusLabel(entry: ChatHistoryEntry) {
  if (entry.status === "running") {
    return "思考中";
  }
  if (entry.status === "success") {
    return "已完成";
  }
  return entry.errorMessage || "失败";
}

function modelProfileLabel(profile: string) {
  if (profile === "azure-gpt-5.5") {
    return "Azure GPT-5.5";
  }
  if (profile === "azure-gpt-5.4") {
    return "Azure GPT-5.4";
  }
  if (profile === "azure-gpt-5") {
    return "Azure GPT-5";
  }
  if (profile === "azure-gpt-5-multimodal") {
    return "GPT-5 Multimodal";
  }
  if (profile === "azure-gpt-4o") {
    return "Azure GPT-4o";
  }
  return profile || "Azure GPT-5.4";
}

function formatIndexState(state?: string) {
  if (state === "fresh") return "索引正常";
  if (state === "stale") return "索引过期";
  return "索引缺失";
}

function formatEvalSummary(summary?: Record<string, number>) {
  if (!summary) {
    return "";
  }
  const parts = ["fail", "warn", "pass"]
    .map((key) => (summary[key] ? `${key} ${summary[key]}` : ""))
    .filter(Boolean);
  return parts.join(" · ");
}

function formatRecordCounts(record?: Record<string, number>) {
  if (!record) {
    return "n/a";
  }
  const entries = Object.entries(record).filter(([, value]) => typeof value === "number");
  if (!entries.length) {
    return "n/a";
  }
  return entries.map(([key, value]) => `${key}:${value}`).join(" · ");
}

function buildSessionSourceCards(reviewPackages: ReviewPackage[], ingestRuns: IngestRunSummary[]): SessionSourceCard[] {
  const byDocument = new Map<string, SessionSourceCard>();
  ingestRuns.forEach((run) => {
    byDocument.set(run.document_id, {
      document_id: run.document_id,
      file_name: run.file_name || run.document_id,
      title: run.file_name || run.document_id,
      status: run.pending_review_count > 0 ? "pending_review" : "ready_to_publish",
      review_count: run.pending_review_count,
      created_at: run.created_at,
    });
  });
  reviewPackages.forEach((reviewPackage) => {
    const existing = byDocument.get(reviewPackage.document_id);
    byDocument.set(reviewPackage.document_id, {
      document_id: reviewPackage.document_id,
      file_name: existing?.file_name || reviewPackage.title || reviewPackage.document_id,
      title: reviewPackage.title || existing?.title || reviewPackage.document_id,
      status: reviewPackage.status,
      section_count: existing?.section_count,
      review_count: reviewPackage.issues.length + reviewPackage.human_questions.length,
      created_at: existing?.created_at,
    });
  });
  const cards = Array.from(byDocument.values()).sort((left, right) => {
    const leftPep = isPreferredPepSource(left) ? 1 : 0;
    const rightPep = isPreferredPepSource(right) ? 1 : 0;
    if (leftPep !== rightPep) {
      return rightPep - leftPep;
    }
    return (right.created_at || "").localeCompare(left.created_at || "");
  });
  const preferred = cards.filter(isPreferredPepSource);
  return (preferred.length >= 3 ? preferred : cards).slice(0, 6);
}

function isPreferredPepSource(card: SessionSourceCard) {
  return /\b(CT|MI|XP)\b.*PEP|PEP.*\b(CT|MI|XP)\b|AND 308/i.test(`${card.file_name} ${card.title}`);
}

function sourceNameForDocument(documentId: string, reviewPackages: ReviewPackage[], ingestRuns: IngestRunSummary[]) {
  if (!documentId) {
    return "";
  }
  const run = ingestRuns.find((item) => item.document_id === documentId);
  if (run?.file_name) {
    return run.file_name;
  }
  const reviewPackage = reviewPackages.find((item) => item.document_id === documentId);
  return reviewPackage?.title || documentId;
}

function sourceReadableMeta(card: SessionSourceCard) {
  return [
    card.section_count !== undefined ? `${card.section_count} sections` : "parsed file",
    card.review_count ? `${card.review_count} review items` : "ready",
  ].join(" · ");
}

function sameStringArray(left: string[], right: string[]) {
  return left.length === right.length && left.every((item, index) => item === right[index]);
}

function buildAnswerRunSteps(
  activeChatEntry: ChatHistoryEntry | undefined,
  result: QueryResult | null,
  isRunning: boolean,
  sessionHandoff: SessionHandoff | null
): AnswerRunStep[] {
  const backendSteps = result?.answer_run?.steps;
  if (backendSteps?.length) {
    return backendSteps.map((step) => ({
      id: step.step_id,
      label: step.label,
      detail: step.summary || answerRunOutputDetail(step.outputs),
      status: normalizeAnswerRunStatus(step.status),
      meta: answerRunOutputMeta(step.outputs),
      thoughts: answerRunThoughts(step),
      rawOutputs: step.outputs ?? {},
    }));
  }
  const hasQuestion = Boolean(activeChatEntry?.question || isRunning);
  const hasResult = Boolean(result);
  const hasContext = Boolean(sessionHandoff);
  const failed = activeChatEntry?.status === "error";
  return [
    {
      id: "input",
      label: "输入",
      detail: hasQuestion ? "已接收用户问题" : "等待问题",
      status: hasQuestion ? "done" : "waiting",
      thoughts: hasQuestion ? ["保留原始问题作为本轮检索、证据校验和回答生成的共同锚点。"] : [],
      rawOutputs: { question: activeChatEntry?.question ?? "" },
    },
    {
      id: "context",
      label: "上下文装配",
      detail: hasContext ? "已锁定当前 PEP source scope" : "等待 source handoff",
      status: hasContext || hasResult ? "done" : isRunning ? "running" : "waiting",
      thoughts: hasContext ? ["当前回答优先消费选中文档 handoff，避免沿用旧 source 或全局 wiki 引用。"] : [],
      rawOutputs: { source_label: sessionHandoff?.source.file_name, chunk_count: sessionHandoff?.retrieval.preview_chunks.length ?? 0 },
    },
    {
      id: "plan",
      label: "推理规划",
      detail: hasResult ? "已选择回答结构与证据策略" : "准备识别 intent 和 evidence needs",
      status: hasResult ? "done" : isRunning ? "running" : "waiting",
      thoughts: hasResult ? ["先判断问题要的是操作办法、概念解释、引用定位还是对比，再选择检索路线。"] : [],
      rawOutputs: {},
    },
    {
      id: "execute",
      label: "执行",
      detail: hasResult ? `${result?.citations.length ?? 0} 条引用已返回` : "等待检索与证据组装",
      status: hasResult ? "done" : isRunning ? "running" : "waiting",
      thoughts: hasResult ? ["检索结果先转成 evidence package，再做 source scope、anchor 和 quote 校验。"] : [],
      rawOutputs: { evidence_count: result?.structured_matches?.[0]?.evidence_items?.length ?? 0, citation_count: result?.citations.length ?? 0 },
    },
    {
      id: "generate",
      label: "生成",
      detail: failed ? "生成失败，查看错误消息" : hasResult ? `${result?.confidence ?? ""} confidence answer` : "等待生成回答",
      status: failed ? "warning" : hasResult ? "done" : isRunning ? "running" : "waiting",
      thoughts: hasResult ? ["最终回答只使用通过 citation validation 的证据，并把可点击引用保留在正文旁。"] : [],
      rawOutputs: { confidence: result?.confidence },
    },
    {
      id: "memory",
      label: "记忆回写",
      detail: hasResult ? "可 pin 到 Session Note" : "等待回答完成",
      status: hasResult ? "done" : "waiting",
      thoughts: hasResult ? ["当前结果可手动 pin 到 Session Note，持久化 memory store 留给下一阶段。"] : [],
      rawOutputs: { pinnable: Boolean(result) },
    },
  ];
}

function answerRunThoughts(step: AnswerRunStepPayload) {
  const outputs = step.outputs ?? {};
  if (step.step_id === "input") {
    const question = typeof outputs.question === "string" ? outputs.question : "";
    return [
      question ? `收到问题：${shortText(question, 72)}` : "收到用户问题。",
      "后续步骤都围绕同一个问题、同一个 source scope 和同一批 citation 校验结果展开。",
    ];
  }
  if (step.step_id === "context") {
    const sourceLabel = typeof outputs.source_label === "string" ? outputs.source_label : "当前文档";
    const documentCount = typeof outputs.document_count === "number" ? outputs.document_count : 0;
    const chunkCount = typeof outputs.chunk_count === "number" ? outputs.chunk_count : 0;
    return [
      `锁定 source：${sourceLabel}`,
      `${documentCount} 份解析文档、${chunkCount} 个 section chunks 进入本轮上下文。`,
    ];
  }
  if (step.step_id === "planning") {
    const route = typeof outputs.route_id === "string" ? outputs.route_id : "session_rag";
    const routeSummary = typeof outputs.route_summary === "string" ? outputs.route_summary : "选择 evidence-first 检索路线。";
    const answerShape = typeof outputs.answer_shape === "string" ? outputs.answer_shape : "adaptive_answer";
    const questionExpanded = outputs.question_expanded === true;
    return [
      `问题被归入 ${route}，回答形态为 ${answerShape}。`,
      routeSummary,
      questionExpanded ? "为提高召回，把用户问题扩展为流程文档、操作顺序、阶段关系、交付和评审依据等检索信号。" : "保持原问题检索，避免额外扩展带来噪音。",
    ];
  }
  if (step.step_id === "execution") {
    const evidenceCount = typeof outputs.evidence_count === "number" ? outputs.evidence_count : 0;
    const citationCount = typeof outputs.citation_count === "number" ? outputs.citation_count : 0;
    const missingCount = typeof outputs.missing_evidence_count === "number" ? outputs.missing_evidence_count : 0;
    const toolThoughts = toolCallThoughts(outputs);
    return [
      ...toolThoughts,
      `保留 ${evidenceCount} 条 evidence，生成 ${citationCount} 条可定位引用。`,
      missingCount ? `${missingCount} 个证据缺口进入后续提示。` : "当前 route 没有发现必须提示的证据缺口。",
    ].slice(0, 6);
  }
  if (step.step_id === "generation") {
    const composer = typeof outputs.composer === "string" ? outputs.composer : "answer_composer";
    const confidence = typeof outputs.confidence === "string" ? outputs.confidence : "unknown";
    const usedLlm = outputs.used_llm === true;
    return [
      `${usedLlm ? "LLM composer" : "Deterministic composer"} 基于已校验证据生成答案。`,
      `composer: ${composer}，confidence: ${confidence}。`,
      "正文中的 citation label 会映射到右侧 Reference Viewer，便于展开 quote 和定位字段。",
    ];
  }
  if (step.step_id === "memory") {
    return ["回答和 reference 可以 pin 到 Session Note。", "持久化 session memory store 仍在下一阶段。"];
  }
  return step.summary ? [step.summary] : [];
}

function toolCallThoughts(outputs: Record<string, unknown>) {
  const toolCalls = Array.isArray(outputs.tool_calls) ? outputs.tool_calls : [];
  return toolCalls
    .map((item) => {
      if (!isRecord(item) || typeof item.tool !== "string") {
        return "";
      }
      const purpose = typeof item.purpose === "string" ? item.purpose : "执行工具。";
      return `${item.tool}：${purpose}`;
    })
    .filter(Boolean)
    .slice(0, 3);
}

function normalizeAnswerRunStatus(status: string): AnswerRunStatus {
  if (status === "running" || status === "done" || status === "warning" || status === "deferred") {
    return status;
  }
  return "waiting";
}

function answerRunSummary(steps: AnswerRunStep[]) {
  const firstActive = steps.find((step) => step.status === "running" || step.status === "warning") ?? steps.find((step) => step.status === "waiting");
  const completedCount = steps.filter((step) => step.status === "done").length;
  const status = firstActive?.status ?? (completedCount ? "done" : "waiting");
  const route = steps.flatMap((step) => step.meta ?? []).find((item) => item.startsWith("route:"));
  const citations = steps.flatMap((step) => step.meta ?? []).find((item) => item.startsWith("citations:"));
  const evidenceState = status === "running" || status === "waiting" ? "正在装配证据链" : completedCount ? "证据链已装配" : "";
  const text = [routeSummaryText(route), citationSummaryText(citations), evidenceState].filter(Boolean).join(" · ");
  return {
    status,
    text: text || (firstActive ? firstActive.detail : completedCount ? "已完成证据检索和回答生成" : "等待问题"),
  };
}

function answerRunTraceItems(steps: AnswerRunStep[], isRunning: boolean): AnswerRunTraceItem[] {
  const stepById = new Map(steps.map((step) => [step.id, step]));
  const inputStep = findAnswerRunStep(stepById, "input");
  const contextStep = findAnswerRunStep(stepById, "context");
  const planningStep = findAnswerRunStep(stepById, "planning", "plan");
  const executionStep = findAnswerRunStep(stepById, "execution", "execute");
  const generationStep = findAnswerRunStep(stepById, "generation", "generate");
  const inputOutputs = stepOutputs(inputStep);
  const contextOutputs = stepOutputs(contextStep);
  const planningOutputs = stepOutputs(planningStep);
  const executionOutputs = stepOutputs(executionStep);
  const generationOutputs = stepOutputs(generationStep);
  const question = typeof inputOutputs.question === "string" ? inputOutputs.question : "";
  const sourceLabel = typeof contextOutputs.source_label === "string" ? contextOutputs.source_label : "当前 source";
  const documentCount = typeof contextOutputs.document_count === "number" ? contextOutputs.document_count : undefined;
  const chunkCount = typeof contextOutputs.chunk_count === "number" ? contextOutputs.chunk_count : undefined;
  const route = routeLabelFromRoute(planningOutputs.route_id);
  const queryRewrite = isRecord(planningOutputs.query_rewrite) ? planningOutputs.query_rewrite : null;
  const routeTerms = queryRewrite && Array.isArray(queryRewrite.route_terms)
    ? queryRewrite.route_terms.filter((item): item is string => typeof item === "string")
    : [];
  const rewriteReason = queryRewrite && typeof queryRewrite.reason === "string" ? queryRewrite.reason : "";
  const evidenceCount = typeof executionOutputs.evidence_count === "number" ? executionOutputs.evidence_count : 0;
  const citationCount = typeof executionOutputs.citation_count === "number" ? executionOutputs.citation_count : 0;
  const missingCount = typeof executionOutputs.missing_evidence_count === "number" ? executionOutputs.missing_evidence_count : 0;
  const toolPlan = isRecord(executionOutputs.tool_plan) ? executionOutputs.tool_plan : isRecord(planningOutputs.tool_plan) ? planningOutputs.tool_plan : null;
  const executedTools = toolPlanExecutedNames(toolPlan);
  const answerPlan = isRecord(generationOutputs.answer_plan) ? generationOutputs.answer_plan : null;
  const answerPlanSlots = answerPlanSlotLabels(answerPlan);
  const composer = typeof generationOutputs.composer === "string" ? generationOutputs.composer : "answer_composer";
  const model = typeof generationOutputs.model_profile === "string" ? generationOutputs.model_profile : "";
  const confidence = typeof generationOutputs.confidence === "string" ? generationOutputs.confidence : "";
  const llmError = typeof generationOutputs.llm_error === "string" ? generationOutputs.llm_error : "";
  const traceItems: AnswerRunTraceItem[] = [];
  if (question || isRunning) {
    traceItems.push({
      label: "问题",
      detail: question ? shortText(question, 96) : "正在接收用户问题。",
      status: inputStep?.status ?? (isRunning ? "running" : "waiting"),
    });
  }
  if (documentCount !== undefined || chunkCount !== undefined || sourceLabel) {
    traceItems.push({
      label: "资料范围",
      detail: `${shortText(sourceLabel, 86)}${documentCount !== undefined ? `；${documentCount} 份文档` : ""}${chunkCount !== undefined ? `；${chunkCount} 个 chunk` : ""}`,
      status: contextStep?.status ?? (isRunning ? "running" : "waiting"),
    });
  }
  if (planningOutputs.route_id) {
    traceItems.push({
      label: "意图路由",
      detail: `${route}${rewriteReason ? `；${shortText(rewriteReason, 90)}` : ""}`,
      status: planningStep?.status ?? (isRunning ? "running" : "waiting"),
    });
  }
  if (routeTerms.length) {
    traceItems.push({
      label: "检索改写",
      detail: routeTerms.slice(0, 6).join(" · "),
      status: planningStep?.status ?? (isRunning ? "running" : "waiting"),
    });
  }
  if (executedTools.length) {
    traceItems.push({
      label: "工具执行",
      detail: executedTools.slice(0, 5).join(" -> "),
      status: executionStep?.status ?? (isRunning ? "running" : "waiting"),
    });
  }
  if (evidenceCount || citationCount || missingCount) {
    traceItems.push({
      label: "证据组织",
      detail: `召回 ${evidenceCount} 条 evidence，保留 ${citationCount} 条引用${missingCount ? `，${missingCount} 个缺证点` : ""}。`,
      status: executionStep?.status ?? (isRunning ? "running" : "waiting"),
    });
  }
  if (answerPlanSlots.length) {
    traceItems.push({
      label: "答案规划",
      detail: answerPlanSlots.join(" · "),
      status: generationStep?.status ?? (isRunning ? "running" : "waiting"),
    });
  }
  if (generationStep) {
    traceItems.push({
      label: "生成与质量",
      detail: `${composer}${model ? ` · ${modelProfileLabel(model)}` : ""}${confidence ? ` · ${confidence}` : ""}${llmError ? `；fallback: ${shortText(llmError, 86)}` : ""}`,
      status: generationStep.status,
    });
  }
  return traceItems;
}

function toolPlanExecutedNames(toolPlan: Record<string, unknown> | null) {
  const executed = toolPlan && Array.isArray(toolPlan.executed) ? toolPlan.executed : [];
  return executed
    .map((item) => (isRecord(item) && typeof item.tool === "string" ? item.tool : ""))
    .filter(Boolean);
}

function answerPlanSlotLabels(answerPlan: Record<string, unknown> | null) {
  const slots = answerPlan && Array.isArray(answerPlan.slots) ? answerPlan.slots : [];
  return slots
    .map((item) => {
      if (!isRecord(item) || typeof item.label !== "string") return "";
      const citations = Array.isArray(item.citation_ids) ? item.citation_ids.length : 0;
      return citations ? `${item.label}(${citations})` : `${item.label}(缺证)`;
    })
    .filter(Boolean)
    .slice(0, 5);
}

function answerRunFactItems(steps: AnswerRunStep[]) {
  const stepById = new Map(steps.map((step) => [step.id, step]));
  const planningOutputs = stepOutputs(findAnswerRunStep(stepById, "planning", "plan"));
  const executionOutputs = stepOutputs(findAnswerRunStep(stepById, "execution", "execute"));
  const generationOutputs = stepOutputs(findAnswerRunStep(stepById, "generation", "generate"));
  const facts: string[] = [];
  if (planningOutputs.route_id) {
    facts.push(`route: ${routeLabelFromRoute(planningOutputs.route_id)}`);
  }
  const citationValidation = isRecord(executionOutputs.citation_validation) ? executionOutputs.citation_validation : null;
  const validCount = citationValidation && typeof citationValidation.valid_count === "number" ? citationValidation.valid_count : executionOutputs.citation_count;
  if (typeof validCount === "number") {
    facts.push(`citations: ${validCount}`);
  }
  if (typeof generationOutputs.model_profile === "string") {
    facts.push(`model: ${modelProfileLabel(generationOutputs.model_profile)}`);
  }
  if (typeof generationOutputs.confidence === "string") {
    facts.push(`confidence: ${generationOutputs.confidence}`);
  }
  return facts.slice(0, 4);
}

function findAnswerRunStep(stepById: Map<string, AnswerRunStep>, ...ids: string[]) {
  for (const id of ids) {
    const step = stepById.get(id);
    if (step) {
      return step;
    }
  }
  return undefined;
}

function answerRunToolNames(outputs: Record<string, unknown>) {
  const toolCalls = Array.isArray(outputs.tool_calls) ? outputs.tool_calls : [];
  return toolCalls
    .map((item) => (isRecord(item) && typeof item.tool === "string" ? item.tool : ""))
    .filter(Boolean)
    .slice(0, 5);
}

function routeSummaryText(route?: string) {
  const value = route?.replace(/^route:\s*/, "") ?? "";
  if (value === "process_operation") {
    return "流程操作路线";
  }
  if (value === "process_overview") {
    return "流程总览路线";
  }
  if (value) {
    return "证据检索路线";
  }
  return "";
}

function citationSummaryText(citations?: string) {
  const kept = citations?.match(/kept\s+(\d+)/i)?.[1];
  return kept ? `${kept} 条引用已校验` : "";
}

function answerRunThoughtLines(steps: AnswerRunStep[], isRunning: boolean) {
  const structured = structuredThoughtLines(steps);
  const lines = structured.length ? structured : steps
    .flatMap((step) => (step.thoughts?.length ? step.thoughts : [step.detail]))
    .map((item) => item.trim())
    .filter(Boolean);
  const uniqueLines = Array.from(new Set(lines));
  if (uniqueLines.length) {
    return uniqueLines.slice(0, 12);
  }
  return [isRunning ? "正在识别问题意图、锁定 source scope，并准备检索可引用证据。" : "已完成本轮证据检索、引用校验和回答生成。"];
}

function structuredThoughtLines(steps: AnswerRunStep[]) {
  const stepById = new Map(steps.map((step) => [step.id, step]));
  const inputOutputs = stepOutputs(stepById.get("input"));
  const contextOutputs = stepOutputs(stepById.get("context"));
  const planningOutputs = stepOutputs(stepById.get("planning"));
  const executionOutputs = stepOutputs(stepById.get("execution"));
  const generationOutputs = stepOutputs(stepById.get("generation"));
  const selfCheck = isRecord(generationOutputs.self_check) ? generationOutputs.self_check : null;
  const lines: string[] = [];
  const question = typeof inputOutputs.question === "string" ? inputOutputs.question : "";
  const sourceLabel = typeof contextOutputs.source_label === "string" ? contextOutputs.source_label : "当前 source";
  const chunkCount = typeof contextOutputs.chunk_count === "number" ? contextOutputs.chunk_count : 0;
  const routeLabel = selfCheck && typeof selfCheck.route_label === "string" ? selfCheck.route_label : routeLabelFromRoute(planningOutputs.route_id);
  const retrievalQuestion = typeof planningOutputs.retrieval_question === "string" ? planningOutputs.retrieval_question : "";
  const evidenceCount = typeof executionOutputs.evidence_count === "number" ? executionOutputs.evidence_count : 0;
  const citationCount = typeof executionOutputs.citation_count === "number" ? executionOutputs.citation_count : 0;
  const missingCount = typeof executionOutputs.missing_evidence_count === "number" ? executionOutputs.missing_evidence_count : 0;
  const citationValidation = isRecord(executionOutputs.citation_validation) ? executionOutputs.citation_validation : null;

  if (question) {
    lines.push(`先把问题界定为“${shortText(question, 54)}”，本轮只围绕这个问题组织证据。`);
  }
  lines.push(`锁定当前 source：${shortText(sourceLabel, 72)}；可检索 section chunks：${chunkCount || "待确认"}。`);
  lines.push(`意图路线：${routeLabel}；回答要覆盖“适用边界、操作顺序、交付/评审依据、引用定位”。`);
  if (retrievalQuestion && retrievalQuestion !== question) {
    lines.push(`检索改写：补入流程主干、operation steps、phase relation、deliverables、review evidence 等信号。`);
  }
  lines.push(`候选证据：召回 ${evidenceCount} 条 evidence，筛到 ${citationCount} 条可点击引用。`);
  evidencePreviewLines(executionOutputs).forEach((item) => lines.push(item));
  if (citationValidation) {
    const valid = typeof citationValidation.valid_count === "number" ? citationValidation.valid_count : citationCount;
    const skipped = typeof citationValidation.skipped_count === "number" ? citationValidation.skipped_count : 0;
    lines.push(`引用校验：${valid} 条保留，${skipped} 条排除；检查 document、anchor、quote 与 source scope。`);
  }
  if (missingCount) {
    lines.push(`完整性自检：仍有 ${missingCount} 个证据缺口，答案需要把边界说清。`);
  }
  qualityNotes(selfCheck).forEach((item) => lines.push(item));
  return lines;
}

function stepOutputs(step?: AnswerRunStep) {
  return step?.rawOutputs ?? {};
}

function routeLabelFromRoute(routeValue: unknown) {
  if (routeValue === "process_operation") return "流程操作办法";
  if (routeValue === "process_overview") return "流程总览解释";
  if (routeValue === "definition_lookup") return "定义解释";
  if (routeValue === "reference_lookup") return "引用定位";
  if (routeValue === "table_lookup") return "表格查询";
  if (routeValue === "bu_comparison") return "多文档对比";
  if (routeValue === "gap_check") return "证据缺口检查";
  if (routeValue === "summary_request") return "文档总结";
  if (routeValue === "role_action_guidance") return "角色行动指引";
  if (routeValue === "stage_transition_work") return "阶段转换工作";
  if (routeValue === "deliverable_detail") return "交付物内容与责任";
  if (routeValue === "tailoring_policy") return "裁剪与评审边界";
  return "证据检索问答";
}

function evidencePreviewLines(outputs: Record<string, unknown>) {
  const preview = Array.isArray(outputs.evidence_preview) ? outputs.evidence_preview : [];
  return preview.slice(0, 3).map((item, index) => {
    if (!isRecord(item)) {
      return "";
    }
    const citationId = typeof item.citation_id === "string" ? item.citation_id : `c${index + 1}`;
    const sectionTitle = typeof item.section_title === "string" ? item.section_title : "命中章节";
    const quotePreview = typeof item.quote_preview === "string" ? item.quote_preview : "";
    return `证据 ${citationId}：${shortText(sectionTitle, 48)}，片段“${shortText(quotePreview, 70)}”。`;
  }).filter(Boolean);
}

function qualityNotes(selfCheck: Record<string, unknown> | null) {
  const notes = selfCheck && Array.isArray(selfCheck.quality_notes) ? selfCheck.quality_notes : [];
  return notes
    .map((item) => (typeof item === "string" ? item : ""))
    .filter(Boolean)
    .slice(0, 4)
    .map((item) => `自检：${item}`);
}

function answerRunOutputDetail(outputs?: Record<string, unknown>) {
  if (!outputs) {
    return "等待步骤输出";
  }
  const pieces = [
    typeof outputs.intent_type === "string" ? outputs.intent_type : "",
    typeof outputs.evidence_count === "number" ? `${outputs.evidence_count} evidence` : "",
    typeof outputs.citation_count === "number" ? `${outputs.citation_count} refs` : "",
    typeof outputs.confidence === "string" ? `${outputs.confidence} confidence` : "",
  ].filter(Boolean);
  return pieces.join(" · ") || "步骤已完成";
}

function answerRunOutputMeta(outputs?: Record<string, unknown>) {
  if (!outputs) {
    return [];
  }
  const meta: string[] = [];
  if (typeof outputs.route_id === "string") {
    meta.push(`route: ${outputs.route_id}`);
  }
  if (typeof outputs.retrieval_question === "string") {
    meta.push(`query: ${shortText(outputs.retrieval_question, 96)}`);
  }
  if (Array.isArray(outputs.tool_calls)) {
    const toolNames = outputs.tool_calls
      .map((item) => (isRecord(item) && typeof item.tool === "string" ? item.tool : ""))
      .filter(Boolean);
    if (toolNames.length) {
      meta.push(`tools: ${toolNames.join(" -> ")}`);
    }
  }
  const citationValidation = outputs.citation_validation;
  if (isRecord(citationValidation)) {
    const kept = typeof citationValidation.valid_count === "number" ? citationValidation.valid_count : 0;
    const skipped = typeof citationValidation.skipped_count === "number" ? citationValidation.skipped_count : 0;
    meta.push(`citations: kept ${kept}, skipped ${skipped}`);
  }
  if (typeof outputs.composer === "string") {
    meta.push(`composer: ${outputs.composer}`);
  }
  if (typeof outputs.model_profile === "string") {
    meta.push(`model: ${outputs.model_profile}`);
  }
  if (typeof outputs.llm_error === "string" && outputs.llm_error) {
    meta.push(`fallback: ${shortText(outputs.llm_error, 96)}`);
  }
  return meta;
}

function parseRichAnswerBlocks(text: string): RichAnswerBlock[] {
  const blocks: RichAnswerBlock[] = [];
  let paragraph: string[] = [];
  let bullets: string[] = [];
  let numbers: string[] = [];
  let numberStart: number | undefined;

  const flushParagraph = () => {
    if (paragraph.length) {
      blocks.push({ type: "paragraph", text: paragraph.join(" ") });
      paragraph = [];
    }
  };
  const flushBullets = () => {
    if (bullets.length) {
      blocks.push({ type: "ul", items: bullets });
      bullets = [];
    }
  };
  const flushNumbers = () => {
    if (numbers.length) {
      blocks.push({ type: "ol", items: numbers, start: numberStart });
      numbers = [];
      numberStart = undefined;
    }
  };
  const flushAll = () => {
    flushParagraph();
    flushBullets();
    flushNumbers();
  };

  text.split(/\r?\n/).forEach((line) => {
    const trimmed = line.trim();
    if (!trimmed) {
      flushAll();
      return;
    }
    const markdownHeading = trimmed.match(/^(#{2,3})\s+(.+)$/);
    const boldHeading = trimmed.match(/^\*\*(.+?)\*\*[:：]?$/);
    const compactHeading = trimmed.match(/^([^。.!?！？]{2,28})[:：]$/);
    if (markdownHeading || boldHeading || compactHeading) {
      flushAll();
      const headingText = markdownHeading?.[2] ?? boldHeading?.[1] ?? compactHeading?.[1] ?? trimmed;
      blocks.push({ type: "heading", text: headingText, level: markdownHeading?.[1] === "###" ? 3 : 2 });
      return;
    }
    const bullet = trimmed.match(/^[-*]\s+(.+)$/);
    if (bullet) {
      flushParagraph();
      flushNumbers();
      bullets.push(bullet[1]);
      return;
    }
    const numbered = trimmed.match(/^\d+[.)]\s+(.+)$/);
    if (numbered) {
      flushParagraph();
      flushBullets();
      if (!numbers.length) {
        const parsedStart = Number.parseInt(trimmed, 10);
        numberStart = Number.isFinite(parsedStart) ? parsedStart : undefined;
      }
      numbers.push(numbered[1]);
      return;
    }
    flushBullets();
    flushNumbers();
    paragraph.push(trimmed);
  });
  flushAll();
  return blocks;
}

function renderRichAnswerBlock(
  block: RichAnswerBlock,
  index: number,
  citationById: Map<string, Citation>,
  onSelectCitation: (id: string) => void
) {
  if (block.type === "heading") {
    return <h4 className={`rich-answer-heading level-${block.level}`} key={`heading-${index}`}>{renderInlineAnswer(block.text, citationById, onSelectCitation)}</h4>;
  }
  if (block.type === "paragraph") {
    return <p className="rich-answer-paragraph" key={`paragraph-${index}`}>{renderInlineAnswer(block.text, citationById, onSelectCitation)}</p>;
  }
  if (block.type === "ul") {
    return (
      <ul className="rich-answer-list" key={`ul-${index}`}>
        {block.items.map((item, itemIndex) => (
          <li key={`${item}-${itemIndex}`}>{renderInlineAnswer(item, citationById, onSelectCitation)}</li>
        ))}
      </ul>
    );
  }
  return (
    <ol className="rich-answer-list ordered" start={block.start} key={`ol-${index}`}>
      {block.items.map((item, itemIndex) => (
        <li key={`${item}-${itemIndex}`}>{renderInlineAnswer(item, citationById, onSelectCitation)}</li>
      ))}
    </ol>
  );
}

function renderInlineAnswer(
  text: string,
  citationById: Map<string, Citation>,
  onSelectCitation: (id: string) => void
): ReactNode[] {
  return text.split(/(\[c\d+\]|\*\*[^*]+\*\*)/g).map((part, index) => {
    const id = part.replace("[", "").replace("]", "");
    const citation = citationById.get(id);
    if (citation) {
      return (
        <button
          className="citation-button readable-inline-citation compact"
          key={`${part}-${index}`}
          type="button"
          title={`${citationTitle(citation)} · ${citationMeta(citation)}`}
          aria-label={`打开引用 ${id}：${citationTitle(citation)}，${citationMeta(citation)}`}
          onClick={() => onSelectCitation(id)}
        >
          {inlineCitationLabel(citation)}
        </button>
      );
    }
    const bold = part.match(/^\*\*(.+)\*\*$/);
    if (bold) {
      return <strong key={`${part}-${index}`}>{bold[1]}</strong>;
    }
    return <span key={`${part}-${index}`}>{part}</span>;
  });
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return Boolean(value && typeof value === "object" && !Array.isArray(value));
}

function shortText(value: string, maxLength: number) {
  return value.length > maxLength ? `${value.slice(0, maxLength - 1)}…` : value;
}

function citationTitle(citation: Citation) {
  const locator = citationPageLabel(citation) || citation.anchor_label || citation.fragment_id || "source";
  const section = citation.page_title || citation.section_id || citation.file_name || "Reference";
  return `${citation.citation_id} · ${locator} · ${section}`;
}

function citationMeta(citation: Citation) {
  const pageLabel = citationPageLabel(citation);
  const anchorLabel = citation.anchor_label && citation.anchor_label !== pageLabel ? citation.anchor_label : "";
  const pieces = [citation.file_name, pageLabel, anchorLabel || citation.fragment_id].filter(Boolean);
  return pieces.join(" · ") || "source anchor pending";
}

function citationDetailRows(citation: Citation): [string, string][] {
  const rows: [string, string][] = [
    ["文件", citation.file_name || citation.document_id || "source pending"],
    ["章节", citation.page_title || citation.section_id || "section pending"],
    ["锚点", citationMeta(citation)],
  ];
  if (citation.source_context?.chunk_id) {
    rows.push(["chunk", citation.source_context.chunk_id]);
  }
  if (citation.source_context?.anchor_label) {
    rows.push(["context anchor", citation.source_context.anchor_label]);
  }
  if (citation.document_id) {
    rows.push(["document_id", citation.document_id]);
  }
  if (citation.fragment_id) {
    rows.push(["fragment", citation.fragment_id]);
  }
  const anchorRows = citation.anchors
    ? Object.entries(citation.anchors)
        .filter(([, value]) => value !== undefined && value !== null && value !== "")
        .slice(0, 4)
        .map(([key, value]) => [`anchor.${key}`, formatAnchorValue(value)] as [string, string])
    : [];
  rows.push(...anchorRows);
  return rows;
}

function citationContextSegments(citation: Citation): { label: string; text: string; kind: "before" | "current" | "after" }[] {
  const context = citation.source_context;
  if (!context) {
    return [];
  }
  return [
    { label: "引用前文", text: context.context_before ?? "", kind: "before" as const },
    { label: "命中上下文", text: context.context_text ?? "", kind: "current" as const },
    { label: "引用后文", text: context.context_after ?? "", kind: "after" as const },
  ].filter((item) => item.text.trim().length > 0);
}

function formatAnchorValue(value: unknown) {
  if (Array.isArray(value)) {
    return value.map((item) => String(item)).join(" / ");
  }
  if (isRecord(value)) {
    return Object.entries(value).map(([key, item]) => `${key}:${String(item)}`).join(" · ");
  }
  return String(value);
}

function inlineCitationLabel(citation: Citation) {
  return citation.citation_id;
}

function citationPageLabel(citation: Citation) {
  const source = `${citation.anchor_label || ""} ${citation.fragment_id || ""}`;
  const match = source.match(/(?:page|p\.?|页)\s*([0-9]+)/i);
  return match ? `p.${match[1]}` : "";
}

function structuredMatchKey(item: StructuredMatch) {
  return item.package_id || item.question || item.evidence_items?.[0]?.evidence_id || item.document_id || "structured-match";
}

function structuredMatchTitle(item: StructuredMatch) {
  return item.title || item.question || item.evidence_items?.[0]?.section_title || "Answer evidence package";
}

function structuredMatchMeta(item: StructuredMatch) {
  if (item.evidence_items) {
    const missingCount = item.missing_evidence?.length ?? 0;
    return `${item.strategy_used || "session retrieval"} · ${item.evidence_items.length} evidence · ${missingCount} gaps`;
  }
  return `${item.business_type || "review package"} · ${item.relation_count ?? 0} relations · ${item.object_count ?? 0} objects`;
}

function treeNodeMeta(node: SessionTreeNode) {
  const pieces = [
    node.anchor_label,
    node.section_id,
    node.fragment_count !== undefined ? `${node.fragment_count} fragments` : "",
    node.chunk_count !== undefined ? `${node.chunk_count} chunks` : "",
  ].filter(Boolean);
  return pieces.join(" · ") || node.node_type;
}

function reviewQueueCount(sessionHandoff: SessionHandoff | null) {
  return reviewQueueItems(sessionHandoff).length;
}

function reviewQueueItems(sessionHandoff: SessionHandoff | null): ReviewQueueItem[] {
  if (!sessionHandoff) {
    return [];
  }
  const reviewItems = sessionHandoff.quality.review_items ?? [];
  const visualItems = sessionHandoff.quality.visual_review_items ?? [];
  return [
    ...reviewItems.map((item, index) => ({
      id: item.review_id || `${item.eval_id}-${index}`,
      group: "Parser",
      title: item.message || item.eval_id,
      detail: item.reference || reviewDetailsSummary(item.details),
      status: item.status,
      severity: item.severity || "medium",
      target: reviewTarget(item.details),
    })),
    ...visualItems.map((item) => ({
      id: item.review_id,
      group: "Visual",
      title: item.caption || item.reason || item.source_id,
      detail: [item.reason, item.recommended_tool ? `tool:${item.recommended_tool}` : "", item.page ? `p.${item.page}` : ""]
        .filter(Boolean)
        .join(" · "),
      status: item.status,
      severity: "medium",
      target: item.source_id,
    })),
  ];
}

function reviewDetailsSummary(details?: Record<string, unknown>) {
  if (!details) {
    return "需要人工确认";
  }
  const keys = Object.keys(details);
  if (!keys.length) {
    return "需要人工确认";
  }
  return keys.slice(0, 3).join(" / ");
}

function reviewTarget(details?: Record<string, unknown>) {
  if (!details) {
    return "";
  }
  const levelJumpSections = details.level_jump_sections;
  if (Array.isArray(levelJumpSections) && levelJumpSections.length) {
    return String(levelJumpSections[0]);
  }
  const sourceIds = details.source_ids;
  if (Array.isArray(sourceIds) && sourceIds.length) {
    return String(sourceIds[0]);
  }
  return "";
}

function collectWarningSectionIds(sessionHandoff: SessionHandoff | null) {
  const sectionIds = new Set<string>();
  sessionHandoff?.quality.review_items?.forEach((item) => {
    ["level_jump_sections", "rootless_child_sections"].forEach((key) => {
      const value = item.details?.[key];
      if (Array.isArray(value)) {
        value.forEach((sectionId) => sectionIds.add(String(sectionId)));
      }
    });
  });
  return sectionIds;
}

function compactHandoffForInspector(sessionHandoff: SessionHandoff, activeChatResult: QueryResult | null) {
  return {
    schema_version: sessionHandoff.schema_version,
    document_id: sessionHandoff.document_id,
    source: sessionHandoff.source,
    tree: {
      root_id: sessionHandoff.tree.root_id,
      item_count: sessionHandoff.tree.items.length,
      selected_preview: sessionHandoff.tree.items.slice(0, 8),
    },
    graph: {
      node_count: sessionHandoff.graph.nodes.length,
      edge_count: sessionHandoff.graph.edges.length,
      edge_types: Array.from(new Set(sessionHandoff.graph.edges.map((edge) => edge.relation_type))),
    },
    retrieval: {
      default_retriever: sessionHandoff.retrieval.default_retriever,
      available_retrievers: sessionHandoff.retrieval.available_retrievers,
      chunk_count: sessionHandoff.retrieval.chunk_count,
      preview_count: sessionHandoff.retrieval.preview_chunks.length,
    },
    chat: sessionHandoff.chat,
    quality: sessionHandoff.quality,
    current_answer: activeChatResult
      ? {
          confidence: activeChatResult.confidence,
          used_llm: activeChatResult.used_llm,
          citation_count: activeChatResult.citations.length,
          trace: activeChatResult.trace,
        }
      : null,
  };
}

function previewChunkKey(chunk: Record<string, unknown>, index: number) {
  return String(chunk.chunk_id || chunk.section_id || `preview-${index}`);
}

function previewChunkTitle(chunk: Record<string, unknown>) {
  return String(chunk.section_title || chunk.chunk_type || chunk.section_id || "Preview chunk");
}

function previewChunkMeta(chunk: Record<string, unknown>) {
  const sourceRefs = Array.isArray(chunk.source_refs) ? chunk.source_refs : [];
  const firstRef = sourceRefs[0] as Record<string, unknown> | undefined;
  return [String(chunk.chunk_type || "chunk"), String(firstRef?.anchor_label || firstRef?.fragment_id || "source pending")]
    .filter(Boolean)
    .join(" · ");
}

function previewChunkQuote(chunk: Record<string, unknown>) {
  const quote = String(chunk.quote || chunk.text || "");
  return quote ? quote.slice(0, 220) : "暂无摘录。";
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

