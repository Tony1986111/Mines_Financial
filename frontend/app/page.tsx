"use client";

import { useEffect, useRef, useState } from "react";
import ChatMessage, { type Message } from "@/components/ChatMessage";
import GraphPanel, { type GraphNodeEvent } from "@/components/GraphPanel";
import MermaidGraphModal from "@/components/MermaidGraphModal";
import MemoryModal from "@/components/MemoryModal";
import { type ProgressCardData } from "@/components/ProgressCard";
import { createThread, deleteThread, fetchGraphMermaid, fetchProgress, fetchThreadHistory, fetchThreads, saveProgress, streamMessage, type ChartSpec, type SourceRef } from "@/lib/api";

// ── Session persistence ────────────────────────────────────────────────────────

const ACTIVE_THREAD_KEY = "active_thread_id";

// ── Thread history (localStorage) ─────────────────────────────────────────────

interface StoredThread {
  id: string;
  label: string;
  updatedAt: number;
  messages: Message[];
  graphEvents?: GraphNodeEvent[];
}

function loadThreads(): StoredThread[] {
  try { return JSON.parse(localStorage.getItem("chat_threads") ?? "[]"); }
  catch { return []; }
}

function saveThread(id: string, label: string, messages: Message[], graphEvents: GraphNodeEvent[]) {
  const threads = loadThreads().filter(t => t.id !== id);
  threads.unshift({ id, label, updatedAt: Date.now(), messages, graphEvents });
  localStorage.setItem("chat_threads", JSON.stringify(threads.slice(0, 30)));
}

function relativeTime(ts: number): string {
  const s = Math.floor((Date.now() - ts) / 1000);
  if (s < 60) return "just now";
  if (s < 3600) return `${Math.floor(s / 60)}m ago`;
  if (s < 86400) return `${Math.floor(s / 3600)}h ago`;
  return `${Math.floor(s / 86400)}d ago`;
}

// ── Progress card helpers ──────────────────────────────────────────────────────

// Always invisible — internal plumbing the user doesn't need to see
const HIDDEN_NODES = new Set(["memory", "aggregate", "guardrails"]);

// Normalise single / array / null into an array for uniform handling
function toCards(v: ProgressCardData | ProgressCardData[] | null): ProgressCardData[] {
  if (v === null) return [];
  return Array.isArray(v) ? v : [v];
}

/**
 * Map a node event to zero or more progress cards.
 *
 * Key insight: with stream_mode=["updates","values"], LangGraph only emits
 * "updates" AFTER a node finishes, so node_start and node_done arrive
 * back-to-back in the same HTTP chunk. React batches both setMessages calls
 * and the "running" card never renders visibly.
 *
 * Fix: pre-announce the next long-running stage from the preceding node's
 * done event, so the "Searching…" card is in the DOM for the full duration
 * of the actual retrieval/agent work:
 *   - retrieve_decision done → add retrieval_agent running card
 *   - dynamic_tool_selector done → add news_agent / calculator_agent running cards
 */
function nodeEventToCard(
  node: string,
  status: "running" | "done",
  state?: Record<string, unknown>,
): ProgressCardData | ProgressCardData[] | null {
  if (HIDDEN_NODES.has(node)) return null;

  // ── Running state ────────────────────────────────────────────────────────────
  if (status === "running") {
    if (node === "dynamic_tool_selector") return null; // handled via done pre-announcement
    const texts: Record<string, string> = {
      retrieve_decision: "Analysing question type…",
      retrieval_agent:   "Searching financial reports…",
      news_agent:        "Searching latest news…",
      calculator_agent:  "Calculating financial metrics…",
      answer:            "Generating answer…",
    };
    const text = texts[node];
    return text ? { id: node, status: "running", variant: "status", text } : null;
  }

  // ── Done state ───────────────────────────────────────────────────────────────

  if (node === "retrieve_decision") {
    if (state?.needs_retrieval === false) {
      return { id: node, status: "done", variant: "direct", text: "Answering directly from memory, no report lookup needed." };
    }
    // Pre-announce retrieval: this card is visible for the entire duration of
    // the retrieval subgraph (several seconds) before node_done("retrieval_agent")
    // replaces it with the result card.
    return { id: "retrieval_agent", status: "running", variant: "status", text: "Searching financial reports…" };
  }

  if (node === "dynamic_tool_selector") {
    // Pre-announce whichever agents were freshly selected this turn.
    // Uses selected_agents (set fresh each turn) to avoid the stale
    // needs_calculation flag that persists across checkpoints.
    const agents = (state?.selected_agents as string[] | undefined) ?? [];
    const cards: ProgressCardData[] = [];
    if (agents.includes("news_agent")) {
      cards.push({ id: "news_agent", status: "running", variant: "status", text: "Searching latest news…" });
    }
    if (agents.includes("calculator_agent")) {
      cards.push({ id: "calculator_agent", status: "running", variant: "status", text: "Calculating financial metrics…" });
    }
    return cards.length > 0 ? cards : null;
  }

  if (node === "retrieval_agent") {
    const docs =
      ((state?.retrieval_result as { documents?: unknown[] } | undefined)?.documents) ?? [];
    const count = docs.length;
    const breakdown: Record<string, number> = {};
    for (const doc of docs as Record<string, unknown>[]) {
      const company = String(doc.company ?? "Unknown");
      const fy = String(doc.fy ?? "");
      const key = fy ? `${company} ${fy}` : company;
      breakdown[key] = (breakdown[key] ?? 0) + 1;
    }
    const bodyLines = Object.entries(breakdown).map(([k, v]) => `${k} (${v})`);
    return {
      id: node, status: "done", variant: "result", icon: "📄",
      title: `Found ${count} relevant passage${count !== 1 ? "s" : ""}`,
      bodyLines: bodyLines.length > 0 ? bodyLines : undefined,
    };
  }

  if (node === "news_agent") {
    const hasNews =
      typeof state?.news_context === "string" &&
      (state.news_context as string).trim().length > 0;
    return {
      id: node, status: "done", variant: "result", icon: "📰",
      title: hasNews ? "Found relevant news articles" : "No recent news found",
    };
  }

  if (node === "calculator_agent") {
    const calcResult = state?.calc_result as string | undefined;
    return {
      id: node, status: "done", variant: "result", icon: "🔢",
      title: "Calculation result",
      bodyLines: calcResult ? [calcResult] : undefined,
    };
  }

  if (node === "compress_context") {
    const messages = (state?.messages as { type: string; content: string }[] | undefined) ?? [];
    const summaryMsg = messages.find(
      m => typeof m.content === "string" && m.content.startsWith("[Earlier conversation compressed]:")
    );
    if (!summaryMsg) return null;
    const summary = summaryMsg.content.replace("[Earlier conversation compressed]:", "").trim();
    return {
      id: node, status: "done", variant: "result", icon: "🗜️",
      title: "Context compressed — click to view summary",
      expandBody: summary,
    };
  }

  if (node === "fallback") {
    return {
      id: node, status: "done", variant: "fallback",
      text: "⚠️ No data can be found from the available annual reports.",
    };
  }

  return null;
}

// ── Source recovery from embedded Sources: section ────────────────────────────

// When a message was saved before sources were tracked separately (or when
// reconstructed from backend history), parse the "Sources:\n[N] Label" block
// that answer_node appends to the content string to rebuild a minimal sources array.
function extractSourcesFromContent(content: string): SourceRef[] {
  const match = content.match(/\n\nSources:\n([\s\S]+)$/);
  if (!match) return [];
  const sources: SourceRef[] = [];
  for (const line of match[1].trim().split("\n")) {
    const m = line.match(/^\[(\d+)\]\s+(.+)$/);
    if (m) sources.push({ label: m[2].trim(), preview: "" });
  }
  return sources;
}

// Ensure every assistant message has a sources array (even if minimal).
function enrichMessages(msgs: Message[]): Message[] {
  return msgs.map(m => {
    if (m.role !== "assistant") return m;
    if (m.sources && m.sources.length > 0) return m;
    const extracted = extractSourcesFromContent(m.content);
    return extracted.length > 0 ? { ...m, sources: extracted } : m;
  });
}

// ── Suggestions ───────────────────────────────────────────────────────────────

const SUGGESTIONS: { category: string; icon: string; items: string[] }[] = [
  {
    category: "Single Metric",
    icon: "📊",
    items: [
      "What was BHP's FY2024 revenue?",
      "What dividends did RIO report in FY2024?",
      "What was NST's net profit after tax in FY2025?",
    ],
  },
  {
    category: "Comparison",
    icon: "⚖️",
    items: [
      "Compare BHP and RIO FY2024 profit.",
      "Rank BHP, RIO, FMG, MIN and NST by FY2024 EBITDA.",
      "Compare revenue growth of Fortescue and Rio Tinto over FY2023, FY2024 and FY2025.",
    ],
  },
  {
    category: "Calculation",
    icon: "🔢",
    items: [
      "How much did FMG revenue grow from FY2023 to FY2024?",
      "What was BHP's average EBITDA across FY2023, FY2024 and FY2025?",
      "Calculate MIN's debt-to-cash ratio for FY2024.",
    ],
  },
  {
    category: "News & Trends",
    icon: "📰",
    items: [
      "What is the latest news about FMG iron ore projects?",
      "Compare RIO's FY2024 results with its latest market outlook.",
      "What is Fortescue's capital expenditure trend?",
    ],
  },
];

const MOBILE_PROGRESS_LABELS: Record<string, string> = {
  compress_context: "Compressing",
  memory: "Memory",
  retrieve_decision: "Routing",
  dynamic_tool_selector: "Selecting tools",
  clarify: "Clarifying",
  retrieval_agent: "Searching reports",
  news_agent: "Searching news",
  calculator_agent: "Calculating",
  aggregate: "Combining",
  guardrails: "Checking",
  fallback: "Fallback",
  answer: "Answering",
};

// ── Component ─────────────────────────────────────────────────────────────────

export default function Home() {
  const [threadId, setThreadId] = useState<string | null>(null);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [streamingThreadId, setStreamingThreadId] = useState<string | null>(null);
  const [streamingLabel, setStreamingLabel] = useState<string>("");

  // Tracks displayed threadId synchronously for stream callbacks
  const threadIdRef = useRef<string | null>(null);
  // Buffers the in-progress conversation so navigating away doesn't corrupt it
  const streamBufferRef = useRef<{
    threadId: string;
    messages: Message[];
    graphEvents: GraphNodeEvent[];
  } | null>(null);
  const [awaitingClarification, setAwaitingClarification] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [backendOk, setBackendOk] = useState(true);
  const [threads, setThreads] = useState<StoredThread[]>([]);
  const [isDark, setIsDark] = useState(false);
  const [mobileSidebarOpen, setMobileSidebarOpen] = useState(false);
  const [mobileGraphOpen, setMobileGraphOpen] = useState(false);
  const [memoryOpen, setMemoryOpen] = useState(false);
  const [mermaidOpen, setMermaidOpen] = useState(false);
  const [mermaidDiagram, setMermaidDiagram] = useState<string | null>(null);
  const [mermaidLoading, setMermaidLoading] = useState(false);
  const [mermaidError, setMermaidError] = useState<string | null>(null);

  // Graph panel state
  const [graphEvents, setGraphEvents] = useState<GraphNodeEvent[]>([]);
  const [graphPanelVisible, setGraphPanelVisible] = useState(true);

  // Index of the last assistant message that gets typewriter animation
  const [typewriterIdx, setTypewriterIdx] = useState<number | null>(null);

  // Resizable sidebar widths
  const [leftWidth, setLeftWidth] = useState(256);
  const [rightWidth, setRightWidth] = useState(288);
  const dragging = useRef<{ side: "left" | "right"; startX: number; startWidth: number } | null>(null);

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Load persisted sidebar widths
  useEffect(() => {
    const lw = parseInt(localStorage.getItem("sidebar_left_width") ?? "");
    const rw = parseInt(localStorage.getItem("sidebar_right_width") ?? "");
    if (!isNaN(lw) && lw >= 160) setLeftWidth(lw);
    if (!isNaN(rw) && rw >= 200) setRightWidth(rw);
  }, []);

  // Drag-to-resize mouse handlers (single effect, uses ref so deps stay empty)
  useEffect(() => {
    function onMouseMove(e: MouseEvent) {
      if (!dragging.current) return;
      const { side, startX, startWidth } = dragging.current;
      if (side === "left") {
        setLeftWidth(Math.max(160, Math.min(480, startWidth + e.clientX - startX)));
      } else {
        setRightWidth(Math.max(200, Math.min(560, startWidth - (e.clientX - startX))));
      }
    }

    function onMouseUp(e: MouseEvent) {
      if (!dragging.current) return;
      const { side, startX, startWidth } = dragging.current;
      if (side === "left") {
        const w = Math.max(160, Math.min(480, startWidth + e.clientX - startX));
        localStorage.setItem("sidebar_left_width", String(w));
      } else {
        const w = Math.max(200, Math.min(560, startWidth - (e.clientX - startX)));
        localStorage.setItem("sidebar_right_width", String(w));
      }
      dragging.current = null;
      document.body.style.cursor = "";
      document.body.style.userSelect = "";
    }

    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
    return () => {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };
  }, []);

  function startDrag(side: "left" | "right", e: React.MouseEvent) {
    dragging.current = { side, startX: e.clientX, startWidth: side === "left" ? leftWidth : rightWidth };
    document.body.style.cursor = "col-resize";
    document.body.style.userSelect = "none";
    e.preventDefault();
  }

  // Init theme + thread list
  useEffect(() => {
    const saved = localStorage.getItem("theme") ?? "light";
    setIsDark(saved === "dark");

    const localThreads = loadThreads();
    setThreads(localThreads);

    fetchThreads().then(backendThreads => {
      if (backendThreads.length === 0) return;
      // Re-read localStorage at resolve time to avoid stale-closure race:
      // if the user sends a message while fetchThreads is in-flight, the
      // mount-time localMap snapshot won't have the new thread's messages.
      const freshLocalMap = new Map(loadThreads().map(t => [t.id, t]));
      const merged: StoredThread[] = backendThreads.map(bt => {
        const local = freshLocalMap.get(bt.id);
        return {
          id: bt.id,
          label: bt.label || local?.label || "Untitled",
          updatedAt: bt.updated_at ? new Date(bt.updated_at).getTime() : (local?.updatedAt ?? 0),
          messages: local?.messages ?? [],
          graphEvents: local?.graphEvents,
        };
      });
      setThreads(merged);
    });

    const savedThreadId = sessionStorage.getItem(ACTIVE_THREAD_KEY);
    if (savedThreadId) {
      setThreadId(savedThreadId);
      const savedThread = localThreads.find(t => t.id === savedThreadId);
      if (savedThread && savedThread.messages.length > 0) {
        setMessages(enrichMessages(savedThread.messages));
        setGraphEvents(savedThread.graphEvents ?? []);
      }
    } else {
      createThread()
        .then(id => {
          setThreadId(id);
          sessionStorage.setItem(ACTIVE_THREAD_KEY, id);
        })
        .catch(() => {
          setBackendOk(false);
          setError("Cannot connect to backend. Run: uv run uvicorn app:app --reload");
        });
    }
  }, []);

  useEffect(() => {
    threadIdRef.current = threadId;
  }, [threadId]);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

  function handleReturnToActive() {
    if (!streamBufferRef.current) return;
    const { threadId: tid, messages: msgs, graphEvents: evts } = streamBufferRef.current;
    setThreadId(tid);
    sessionStorage.setItem(ACTIVE_THREAD_KEY, tid);
    setMessages(msgs);
    setGraphEvents(evts);
    setLoading(true);
  }

  function toggleTheme() {
    const next = isDark ? "light" : "dark";
    setIsDark(!isDark);
    localStorage.setItem("theme", next);
    document.documentElement.classList.toggle("dark", next === "dark");
  }

  async function openMermaidGraph() {
    setMermaidOpen(true);
    if (mermaidDiagram || mermaidLoading) return;

    setMermaidLoading(true);
    setMermaidError(null);
    try {
      const diagram = await fetchGraphMermaid();
      setMermaidDiagram(diagram);
    } catch (err) {
      setMermaidError(err instanceof Error ? err.message : "Failed to load LangGraph workflow");
    } finally {
      setMermaidLoading(false);
    }
  }

  async function handleNewConversation() {
    try {
      const id = await createThread();
      setThreadId(id);
      sessionStorage.setItem(ACTIVE_THREAD_KEY, id);
      setMessages([]);
      setGraphEvents([]);
      setTypewriterIdx(null);
      setAwaitingClarification(false);
      setError(null);
      setBackendOk(true);
      inputRef.current?.focus();
    } catch {
      setError("Cannot connect to backend.");
    }
  }

  async function handleSelectThread(t: StoredThread) {
    // Returning to the in-progress streaming thread
    if (t.id === streamBufferRef.current?.threadId) {
      handleReturnToActive();
      return;
    }

    // Navigating away from the streaming thread — clear loading display only
    if (streamBufferRef.current) {
      setLoading(false);
    }

    setMobileSidebarOpen(false);
    setThreadId(t.id);
    sessionStorage.setItem(ACTIVE_THREAD_KEY, t.id);
    setGraphEvents(t.graphEvents ?? []);
    setTypewriterIdx(null);
    setAwaitingClarification(false);
    setError(null);

    if (t.messages.length > 0) {
      setMessages(enrichMessages(t.messages));
    } else {
      // No local messages — reconstruct from backend checkpoint + persisted progress
      const [history, progressTurns] = await Promise.all([
        fetchThreadHistory(t.id),
        fetchProgress(t.id),
      ]);
      const progressMap = new Map(progressTurns.map(p => [p.turn_index, p.cards as ProgressCardData[]]));
      const msgs: Message[] = [];
      let turnIdx = 0;
      for (const m of history) {
        msgs.push({ role: m.role as Message["role"], content: m.content });
        if (m.role === "user") {
          const cards = progressMap.get(turnIdx);
          if (cards && cards.length > 0) {
            msgs.push({ role: "progress", content: "", cards });
          }
          turnIdx++;
        }
      }
      setMessages(enrichMessages(msgs));
      // Cache locally so next click is instant
      if (msgs.length > 0) {
        saveThread(t.id, t.label, msgs, []);
        setThreads(loadThreads());
      }
    }

    inputRef.current?.focus();
  }

  async function handleDeleteThread(id: string) {
    setThreads(prev => prev.filter(t => t.id !== id));
    const remaining = loadThreads().filter(t => t.id !== id);
    localStorage.setItem("chat_threads", JSON.stringify(remaining));

    if (id === threadId) {
      setMessages([]);
      setGraphEvents([]);
      setTypewriterIdx(null);
      setAwaitingClarification(false);
      setError(null);
      sessionStorage.removeItem(ACTIVE_THREAD_KEY);
      try {
        const newId = await createThread();
        setThreadId(newId);
        sessionStorage.setItem(ACTIVE_THREAD_KEY, newId);
      } catch { /* ignore */ }
    }

    deleteThread(id).catch(() => {});
  }

  async function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    if (!input.trim() || !threadId || loading) return;

    const userMessage = input.trim();
    const submittedThreadId = threadId!;
    setInput("");
    setError(null);
    const next: Message[] = [...messages, { role: "user", content: userMessage }];
    setMessages(next);
    setLoading(true);
    setStreamingThreadId(submittedThreadId);
    setStreamingLabel(userMessage.slice(0, 60));
    setGraphEvents([]);
    setTypewriterIdx(null);

    // Init the stream buffer for this conversation
    streamBufferRef.current = { threadId: submittedThreadId, messages: next, graphEvents: [] };

    // Route setMessages/setGraphEvents through the buffer so navigating away
    // doesn't corrupt the displayed historical thread view.
    function bufMessages(updater: (prev: Message[]) => Message[]) {
      if (streamBufferRef.current?.threadId === submittedThreadId) {
        streamBufferRef.current.messages = updater(streamBufferRef.current.messages);
      }
      if (threadIdRef.current === submittedThreadId) {
        setMessages(updater);
      }
    }
    function bufGraphEvents(updater: (prev: GraphNodeEvent[]) => GraphNodeEvent[]) {
      if (streamBufferRef.current?.threadId === submittedThreadId) {
        streamBufferRef.current.graphEvents = updater(streamBufferRef.current.graphEvents);
      }
      if (threadIdRef.current === submittedThreadId) {
        setGraphEvents(updater);
      }
    }

    // Track progress cards locally — avoids stale closure issues with useState
    let currentCards: ProgressCardData[] = [];
    let progressAdded = false;
    const progressIdx = next.length; // index where the progress message will sit

    function flushProgressMessage() {
      if (!progressAdded && currentCards.length > 0) {
        progressAdded = true;
        bufMessages(prev => [
          ...prev,
          { role: "progress", content: "", cards: [...currentCards] },
        ]);
      } else if (progressAdded) {
        bufMessages(prev => {
          const arr = [...prev];
          if (arr[progressIdx]?.role === "progress") {
            arr[progressIdx] = { role: "progress", content: "", cards: [...currentCards] };
          }
          return arr;
        });
      }
    }

    try {
      let finalAnswer = "";
      let finalChartData: ChartSpec[] = [];
      let finalSources: SourceRef[] = [];
      let finalConfidence = "";
      let interrupted = false;
      let clarificationQuestion: string | null = null;
      let streamError: string | null = null;

      await streamMessage(
        threadId,
        userMessage,
        awaitingClarification,
        (event) => {
          if (event.type === "node_start") {
            bufGraphEvents(prev => [
              ...prev.filter(e => !(e.node === event.node && e.status === "running")),
              { node: event.node, status: "running" },
            ]);
            const newCards = toCards(nodeEventToCard(event.node, "running"));
            if (newCards.length > 0) {
              currentCards = [
                ...currentCards.filter(c => !newCards.some(nc => nc.id === c.id)),
                ...newCards,
              ];
              flushProgressMessage();
            }

          } else if (event.type === "node_done") {
            bufGraphEvents(prev => [
              ...prev.filter(e => !(e.node === event.node && e.status === "running")),
              { node: event.node, status: "done", state: event.state },
            ]);
            const newCards = toCards(nodeEventToCard(event.node, "done", event.state));
            // Remove: running card for this node + any running/done card whose id a new card will take over
            const replaceIds = new Set([event.node, ...newCards.map(c => c.id)]);
            currentCards = currentCards.filter(c => {
              if (c.status === "running" && replaceIds.has(c.id)) return false;
              if (newCards.some(nc => nc.id === c.id)) return false;
              return true;
            });
            currentCards = [...currentCards, ...newCards];
            flushProgressMessage();

          } else if (event.type === "interrupt") {
            interrupted = true;
            clarificationQuestion = event.question;
          } else if (event.type === "done") {
            finalAnswer = event.answer;
            finalChartData = event.chart_data ?? [];
            finalSources = event.sources ?? [];
            finalConfidence = event.confidence ?? "";
          } else if (event.type === "error") {
            streamError = event.detail;
          }
        },
      );

      setAwaitingClarification(false);

      // Build the permanent progress message (or omit if no cards arrived)
      const progressMsg: Message | null = currentCards.length > 0
        ? { role: "progress", content: "", cards: currentCards }
        : null;

      const base = [...next, ...(progressMsg ? [progressMsg] : [])];
      let updated = next as Message[];

      if (streamError) {
        setError(streamError);
        updated = base;
      } else if (interrupted && clarificationQuestion) {
        setAwaitingClarification(true);
        updated = [...base, { role: "assistant", content: clarificationQuestion }];
        setTypewriterIdx(updated.length - 1);
      } else if (finalAnswer) {
        updated = [...base, { role: "assistant", content: finalAnswer, chartData: finalChartData, sources: finalSources, confidence: finalConfidence }];
        setTypewriterIdx(updated.length - 1);
      } else {
        setError("No answer generated. Check LangSmith traces or try again.");
        updated = base;
      }

      bufMessages(() => updated);
      const label = next.find(m => m.role === "user")?.content ?? userMessage;
      saveThread(submittedThreadId, label.slice(0, 60), updated, streamBufferRef.current?.graphEvents ?? []);
      if (currentCards.length > 0) {
        const turnIndex = next.filter(m => m.role === "user").length - 1;
        saveProgress(submittedThreadId, turnIndex, currentCards);
      }
      setThreads(loadThreads());

    } catch (err) {
      if (threadIdRef.current === submittedThreadId) {
        setError(err instanceof Error ? err.message : "Unknown error");
      }
    } finally {
      streamBufferRef.current = null;
      setStreamingThreadId(null);
      setStreamingLabel("");
      if (threadIdRef.current === submittedThreadId) {
        setLoading(false);
        inputRef.current?.focus();
      }
    }
  }

  const placeholder = awaitingClarification
    ? "Answer the question above..."
    : "Ask about ASX mining financials...";

  // Show loading dots only when loading but no progress message has appeared yet
  const lastMsg = messages[messages.length - 1];
  const showLoadingDots = loading && (!lastMsg || lastMsg.role !== "progress");
  const runningEvent = [...graphEvents].reverse().find(e => e.status === "running");
  const latestEvent = graphEvents[graphEvents.length - 1];
  const progressStage = runningEvent
    ? (MOBILE_PROGRESS_LABELS[runningEvent.node] ?? runningEvent.node)
    : latestEvent
    ? (MOBILE_PROGRESS_LABELS[latestEvent.node] ?? latestEvent.node)
    : "all stages";
  const progressActive = Boolean(runningEvent);

  return (
    <div className="app-shell flex h-screen overflow-hidden">

      {/* Mobile sidebar backdrop */}
      {mobileSidebarOpen && (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          onClick={() => setMobileSidebarOpen(false)}
        />
      )}

      {/* ── Sidebar ─────────────────────────────────────────── */}
      <aside
        className={`mobile-sidebar-shell bg-[#f4f8fd] dark:bg-[#091524] border-r border-[#cddcea] dark:border-[#162840] flex flex-col overflow-hidden
          fixed inset-y-0 left-0 z-50 transition-transform duration-300
          md:relative md:inset-auto md:z-auto md:shrink-0 md:transition-none
          ${mobileSidebarOpen ? "translate-x-0" : "-translate-x-full md:translate-x-0"}`}
        style={{ "--sidebar-width": `${leftWidth}px` } as React.CSSProperties}
      >

        {/* Logo */}
        <div className="px-4 pt-5 pb-4 border-b border-[#cddcea] dark:border-[#162840]">
          <div className="flex items-center gap-2.5">
            <span className="text-lg">⛏️</span>
            <span className="font-bold text-sm tracking-tight text-[#0a1e38] dark:text-[#dce8f8]">ASX Mining</span>
            <button
              onClick={() => setMobileSidebarOpen(false)}
              className="ml-auto flex h-8 w-8 items-center justify-center rounded-lg text-sm text-[#7a9ab8] transition-colors hover:bg-[#e8f0fa] hover:text-[#0a1e38] dark:text-[#3d5878] dark:hover:bg-[#0d1c2e] dark:hover:text-[#c4d8f0] md:hidden"
              aria-label="Close menu"
            >
              ✕
            </button>
          </div>
          <p className="text-[11px] text-[#7a9ab8] dark:text-[#3d5878] mt-0.5 font-mono">Financial Report Q&A</p>
        </div>

        {/* Status + New conversation */}
        <div className="px-4 py-3 border-b border-[#cddcea] dark:border-[#162840] space-y-2.5">
          <div className="flex items-center gap-2">
            <span className={`w-1.5 h-1.5 rounded-full ${backendOk ? "bg-emerald-500" : "bg-red-500"}`} />
            <span className="text-[11px] text-[#7a9ab8] dark:text-[#3d5878]">{backendOk ? "Backend connected" : "Disconnected"}</span>
          </div>
          <button
            onClick={handleNewConversation}
            className="w-full text-xs bg-[#1a4a8a] hover:bg-[#20579e] active:bg-[#143870] text-white rounded-lg py-2 px-3 transition-all flex items-center gap-1.5 font-semibold tracking-wide shadow-sm shadow-[#1a4a8a]/25"
          >
            <span className="text-base leading-none font-light">+</span> New Conversation
          </button>
        </div>

        {/* Thread history */}
        <div className="flex-1 overflow-y-auto">
          <div className="px-4 pt-3 pb-1">
            <p className="text-[9px] uppercase tracking-[0.15em] text-[#7a9ab8] dark:text-[#3d5878] font-bold">History</p>
          </div>

          {/* Live thread — pinned at top during streaming */}
          {streamingThreadId && (
            <div
              className={`relative flex items-stretch border-l-2 border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20 ${
                streamingThreadId !== threadId
                  ? "cursor-pointer hover:bg-emerald-100 dark:hover:bg-emerald-900/30 transition-colors"
                  : ""
              }`}
              onClick={() => streamingThreadId !== threadId && handleReturnToActive()}
            >
              <div className="flex-1 px-4 py-2.5 min-w-0">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0 animate-pulse" />
                  <span className="text-[9px] font-bold uppercase tracking-wide text-emerald-600 dark:text-emerald-400">
                    In progress
                  </span>
                </div>
                <p className="text-[11px] text-emerald-800 dark:text-emerald-300 truncate leading-snug font-medium">
                  {streamingLabel || "Responding…"}
                </p>
              </div>
            </div>
          )}

          {threads.length === 0 && !streamingThreadId && (
            <p className="px-4 py-2 text-[11px] text-[#7a9ab8] dark:text-[#3d5878] italic">No past conversations</p>
          )}
          {threads.filter(t => t.id !== streamingThreadId).map((t) => (
            <div
              key={t.id}
              className={`relative group flex items-stretch hover:bg-[#e8f0fa] dark:hover:bg-[#0d1c2e] transition-colors border-l-2 ${
                t.id === threadId
                  ? "bg-[#e2ecf7] dark:bg-[#0d1c2e] border-[#1a4a8a] dark:border-[#c4880c]"
                  : "border-transparent"
              }`}
            >
              <button
                onClick={() => handleSelectThread(t)}
                className="flex-1 text-left px-4 py-2.5 min-w-0"
              >
                <p className="text-[11px] text-[#0a1e38] dark:text-[#c4d8f0] truncate leading-snug pr-5 font-medium">
                  {t.label || "Untitled conversation"}
                </p>
                <p className="text-[10px] text-[#94b0cc] dark:text-[#3d5878] mt-0.5 font-mono">{relativeTime(t.updatedAt)}</p>
              </button>
              <button
                onClick={() => handleDeleteThread(t.id)}
                title="Delete thread"
                className="absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 md:w-5 md:h-5 rounded flex items-center justify-center text-[#94b0cc] dark:text-[#3d5878] hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-400/10 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-all text-[10px]"
              >
                ✕
              </button>
            </div>
          ))}
        </div>

        {/* Companies + Theme toggle */}
        <div className="px-4 py-4 border-t border-[#cddcea] dark:border-[#162840] space-y-3">
          <div>
            <p className="text-[9px] uppercase tracking-[0.15em] text-[#7a9ab8] dark:text-[#3d5878] font-bold mb-2">Covered</p>
            <div className="flex flex-wrap gap-1">
              {["BHP", "RIO", "FMG", "MIN", "NST"].map(c => (
                <span key={c} className="text-[10px] font-mono font-semibold tracking-wide bg-[#fef6e4] dark:bg-[#1a1004] border border-[#e8c86a] dark:border-[#3d2800] text-[#966000] dark:text-[#c4880c] rounded px-1.5 py-0.5">
                  {c}
                </span>
              ))}
            </div>
          </div>
          <button
            onClick={toggleTheme}
            className="w-full flex items-center gap-2 text-[11px] text-[#7a9ab8] dark:text-[#3d5878] hover:text-[#0a1e38] dark:hover:text-[#c4d8f0] transition-colors py-1"
          >
            <span className="text-base">{isDark ? "☀️" : "🌙"}</span>
            {isDark ? "Switch to Light Mode" : "Switch to Dark Mode"}
          </button>
          {threadId && (
            <div className="md:hidden rounded-lg border border-[#cddcea] bg-white px-2.5 py-2 dark:border-[#162840] dark:bg-[#0d1c2e]">
              <p className="text-[9px] uppercase tracking-[0.15em] text-[#7a9ab8] dark:text-[#3d5878] font-bold mb-1">Thread ID</p>
              <p className="select-all break-all font-mono text-[10px] leading-relaxed text-[#5a7a9a] dark:text-[#7a9ab8]">{threadId}</p>
            </div>
          )}
        </div>
      </aside>

      {/* ── Left resize handle ──────────────────────────────── */}
      <div
        onMouseDown={(e) => startDrag("left", e)}
        className="hidden md:block w-1 shrink-0 cursor-col-resize group relative hover:bg-[#1a4a8a]/10 dark:hover:bg-[#c4880c]/10 transition-colors"
        title="Drag to resize"
      >
        <div className="absolute inset-y-0 left-0 w-px bg-[#cddcea] dark:bg-[#162840] group-hover:bg-[#1a4a8a] dark:group-hover:bg-[#c4880c] transition-colors" />
      </div>

      {/* ── Main ────────────────────────────────────────────── */}
      <main className="flex flex-col flex-1 min-w-0 bg-[#eef4fb] dark:bg-[#060c14]">

        {/* Header */}
        <header className="min-h-12 md:h-12 bg-[#f4f8fd]/95 dark:bg-[#091524]/95 border-b border-[#cddcea] dark:border-[#162840] flex flex-wrap md:flex-nowrap items-center px-3 md:px-5 py-2 md:py-0 gap-2 md:gap-3 shrink-0 backdrop-blur-sm">
          <button
            onClick={() => setMobileSidebarOpen(true)}
            className="md:hidden p-1.5 rounded-lg text-[#7a9ab8] hover:bg-[#e8f0fa] dark:hover:bg-[#0d1c2e] transition-colors shrink-0"
            aria-label="Open menu"
          >
            <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
              <line x1="2" y1="5" x2="16" y2="5"/><line x1="2" y1="9" x2="16" y2="9"/><line x1="2" y1="13" x2="16" y2="13"/>
            </svg>
          </button>
          <h1 className="min-w-0 max-w-[calc(100vw-7rem)] text-sm font-bold tracking-tight text-[#0a1e38] dark:text-[#c4d8f0] truncate md:max-w-none">Financial Report Chat</h1>
          {awaitingClarification && (
            <span className="text-[10px] text-amber-700 dark:text-amber-400 bg-amber-50 dark:bg-amber-400/10 border border-amber-300 dark:border-amber-400/20 rounded-full px-2.5 py-0.5 font-semibold">
              Awaiting clarification
            </span>
          )}
          <div className="flex w-full min-w-0 items-center gap-1.5 md:ml-auto md:w-auto md:justify-end md:gap-3">
            <button
              onClick={() => setMemoryOpen(true)}
              className="rounded-lg border border-[#b8d0e8] dark:border-[#1e3858] bg-white dark:bg-[#0d1c2e] px-2.5 py-1.5 md:px-3 text-xs font-semibold text-[#1a4a8a] dark:text-[#7eb3e8] shadow-sm transition-all hover:bg-[#e8f0fa] dark:hover:bg-[#12243c] hover:border-[#1a4a8a]/50 dark:hover:border-[#5a8fc8]/40 shrink-0"
            >
              <span className="md:hidden">memory</span>
              <span className="hidden md:inline">Memory</span>
            </button>
            <button
              onClick={openMermaidGraph}
              className="md:hidden rounded-lg border border-[#b8d0e8] dark:border-[#1e3858] bg-white dark:bg-[#0d1c2e] px-2.5 py-1.5 text-xs font-semibold text-[#1a4a8a] dark:text-[#7eb3e8] shadow-sm transition-all hover:bg-[#e8f0fa] dark:hover:bg-[#12243c] hover:border-[#1a4a8a]/50 dark:hover:border-[#5a8fc8]/40 shrink-0"
            >
              graph
            </button>
            <button
              onClick={() => setMobileGraphOpen(true)}
              className={`ml-auto md:hidden flex min-w-0 max-w-[48vw] items-center gap-1.5 rounded-lg border px-2.5 py-1.5 text-xs font-semibold shadow-sm transition-all shrink ${
                progressActive
                  ? "border-emerald-400/50 bg-emerald-50 text-emerald-700 dark:border-emerald-500/30 dark:bg-emerald-950/30 dark:text-emerald-300"
                  : "border-[#b8d0e8] bg-white text-[#1a4a8a] hover:bg-[#e8f0fa] hover:border-[#1a4a8a]/50 dark:border-[#1e3858] dark:bg-[#0d1c2e] dark:text-[#7eb3e8] dark:hover:bg-[#12243c] dark:hover:border-[#5a8fc8]/40"
              }`}
            >
              {progressActive && (
                <span className="h-1.5 w-1.5 shrink-0 rounded-full bg-emerald-500 animate-pulse" />
              )}
              <span className="shrink-0">progress</span>
              <span className="min-w-0 truncate text-[10px] font-medium opacity-75">
                {progressStage}
              </span>
            </button>
            <button
              onClick={openMermaidGraph}
              className="hidden md:inline-block rounded-lg border border-[#b8d0e8] dark:border-[#1e3858] bg-white dark:bg-[#0d1c2e] px-3 py-1.5 text-xs font-semibold text-[#1a4a8a] dark:text-[#7eb3e8] shadow-sm transition-all hover:bg-[#e8f0fa] dark:hover:bg-[#12243c] hover:border-[#1a4a8a]/50 dark:hover:border-[#5a8fc8]/40 shrink-0"
            >
              LangGraph Workflow
            </button>
            {threadId && (
              <span className="hidden select-all truncate font-mono text-[10px] text-[#94b0cc] dark:text-[#3d5878] sm:flex sm:items-center sm:gap-1">
                <span className="font-sans not-italic text-[#7a9ab8] dark:text-[#3d5878]">Thread ID:</span>
                {threadId}
              </span>
            )}
          </div>
        </header>

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-4 md:px-6 md:py-5">
          {messages.length === 0 && !loading && !error && (
            <div className="min-h-full flex flex-col items-center justify-center gap-4 py-3 md:gap-8 md:py-0">
              <div className="text-center">
                <p className="text-3xl mb-2 md:text-4xl md:mb-4">⛏️</p>
                <p className="font-bold text-base tracking-tight text-[#0a1e38] dark:text-[#dce8f8] md:text-lg">Ask about ASX mining financials</p>
                <p className="text-xs text-[#7a9ab8] dark:text-[#3d5878] mt-1 md:text-sm md:mt-1.5">Revenue · Profit · EBITDA · Capex · Dividends</p>
              </div>
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-2.5 md:gap-4 w-full max-w-3xl">
                {SUGGESTIONS.map(group => (
                  <div key={group.category} className="flex flex-col gap-1 md:gap-1.5">
                    <p className="flex items-center gap-1.5 text-[10px] font-semibold text-[#5a7a9a] uppercase tracking-wider mb-0.5 px-1 md:text-[11px]">
                      <span>{group.icon}</span>
                      {group.category}
                    </p>
                    {group.items.map(s => (
                      <button
                        key={s}
                        onClick={() => { setInput(s); inputRef.current?.focus(); }}
                        className="text-left text-xs text-[#1a4a8a] dark:text-[#7aade8] bg-white dark:bg-[#0d1c2e] hover:bg-[#e8f0fa] dark:hover:bg-[#111e30] border border-[#cddcea] dark:border-[#162840] hover:border-[#b0c8e0] dark:hover:border-[#1e3858] rounded-lg px-3 py-2 transition-all shadow-sm hover:shadow-md md:rounded-xl md:px-3.5 md:py-2.5 md:text-sm"
                      >
                        <span className="flex items-center gap-2">
                          <span className="text-[#c4880c] text-xs font-bold leading-none shrink-0">→</span>
                          <span className="leading-snug">{s}</span>
                        </span>
                      </button>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}

          {messages.map((msg, i) => (
            <ChatMessage
              key={i}
              message={msg}
              typewriter={i === typewriterIdx && msg.role === "assistant"}
            />
          ))}

          {/* Loading dots — only shown before the first progress card appears */}
          {showLoadingDots && (
            <div className="flex gap-3 mb-4">
              <div className="w-7 h-7 rounded-full bg-gradient-to-br from-[#1e5cba] to-[#1a4a8a] shrink-0 flex items-center justify-center text-[10px] font-bold text-white mt-0.5 ring-1 ring-white/10">
                AI
              </div>
              <div className="bg-white dark:bg-[#0d1c2e] border border-[#cddcea] dark:border-[#162840] rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm self-start">
                <span className="flex gap-1.5 items-center">
                  {[0, 160, 320].map(d => (
                    <span key={d} className="w-1.5 h-1.5 bg-[#7a9ab8] dark:bg-[#3d5878] rounded-full animate-bounce" style={{ animationDelay: `${d}ms` }} />
                  ))}
                </span>
              </div>
            </div>
          )}

          {error && (
            <div className="flex justify-center my-3">
              <div className="text-xs text-red-600 dark:text-red-400 bg-red-50 dark:bg-red-400/10 border border-red-200 dark:border-red-400/20 rounded-xl px-4 py-2.5 max-w-lg text-center font-medium">
                {error}
              </div>
            </div>
          )}
          <div ref={bottomRef} />
        </div>

        {/* Input */}
        <div className="border-t border-[#cddcea] dark:border-[#162840] bg-[#f4f8fd] dark:bg-[#091524] px-3 pt-3 pb-[max(0.75rem,env(safe-area-inset-bottom))] md:p-4">
          <form onSubmit={handleSubmit} className="flex gap-2">
            <input
              ref={inputRef}
              type="text"
              value={input}
              onChange={e => setInput(e.target.value)}
              placeholder={placeholder}
              disabled={loading || !threadId || !backendOk}
              className="min-w-0 flex-1 bg-white dark:bg-[#0d1c2e] border border-[#cddcea] dark:border-[#162840] hover:border-[#b0c8e0] dark:hover:border-[#1e3858] focus:border-[#1a4a8a] dark:focus:border-[#4a7fc8] focus:ring-1 focus:ring-[#1a4a8a]/15 dark:focus:ring-[#4a7fc8]/15 rounded-xl px-3 py-2.5 text-sm text-[#0a1e38] dark:text-[#c4d8f0] placeholder-[#94b0cc] dark:placeholder-[#3d5878] focus:outline-none disabled:opacity-40 transition-all shadow-sm md:px-4"
            />
            <button
              type="submit"
              disabled={loading || !input.trim() || !threadId || !backendOk}
              className="bg-[#1a4a8a] hover:bg-[#20579e] active:bg-[#143870] disabled:opacity-40 text-white rounded-xl px-4 py-2.5 text-sm font-semibold transition-all shrink-0 shadow-sm shadow-[#1a4a8a]/25 disabled:shadow-none md:px-5"
            >
              Send
            </button>
          </form>
          <p className="text-[10px] text-[#94b0cc] dark:text-[#3d5878] mt-2 text-center font-mono">
            Answers based on FY2023–FY2025 annual reports only.
          </p>
        </div>
      </main>

      {/* ── Right resize handle ─────────────────────────────── */}
      {graphPanelVisible && (
        <div
          onMouseDown={(e) => startDrag("right", e)}
          className="hidden md:block w-1 shrink-0 cursor-col-resize group relative hover:bg-[#1a4a8a]/10 dark:hover:bg-[#c4880c]/10 transition-colors"
          title="Drag to resize"
        >
          <div className="absolute inset-y-0 right-0 w-px bg-[#cddcea] dark:bg-[#162840] group-hover:bg-[#1a4a8a] dark:group-hover:bg-[#c4880c] transition-colors" />
        </div>
      )}

      {/* ── Graph Panel ─────────────────────────────────────── */}
      <div className="hidden md:contents">
        <GraphPanel
          events={graphEvents}
          visible={graphPanelVisible}
          width={rightWidth}
          onToggle={() => setGraphPanelVisible(v => !v)}
        />
      </div>

      {/* Mobile Graph Progress overlay */}
      {mobileGraphOpen && (
        <div className="fixed inset-0 z-50 md:hidden overflow-hidden">
          <GraphPanel
            events={graphEvents}
            visible={true}
            width={9999}
            onToggle={() => setMobileGraphOpen(false)}
          />
        </div>
      )}

      <MemoryModal open={memoryOpen} onClose={() => setMemoryOpen(false)} />

      <MermaidGraphModal
        open={mermaidOpen}
        diagram={mermaidDiagram}
        loading={mermaidLoading}
        error={mermaidError}
        isDark={isDark}
        onClose={() => setMermaidOpen(false)}
      />
    </div>
  );
}
