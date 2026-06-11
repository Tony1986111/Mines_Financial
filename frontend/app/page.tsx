"use client";

import { useEffect, useRef, useState } from "react";
import AppSidebar from "@/components/AppSidebar";
import ChatComposer from "@/components/ChatComposer";
import ChatEmptyState from "@/components/ChatEmptyState";
import ChatHeader from "@/components/ChatHeader";
import ChatMessage from "@/components/ChatMessage";
import GraphPanel from "@/components/GraphPanel";
import MermaidGraphModal from "@/components/MermaidGraphModal";
import MemoryModal from "@/components/MemoryModal";
import ResizeHandle from "@/components/ResizeHandle";
import { useChatStream } from "@/hooks/useChatStream";
import { useResizablePanels } from "@/hooks/useResizablePanels";
import { useTheme } from "@/hooks/useTheme";
import { useThreads, type StreamBuffer } from "@/hooks/useThreads";
import { fetchGraphMermaid } from "@/lib/api";
import { MOBILE_PROGRESS_LABELS } from "@/lib/progressEvents";
import type { Message } from "@/types/chat";
import type { GraphNodeEvent } from "@/types/graph";

// ── Component ─────────────────────────────────────────────────────────────────

export default function Home() {
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [streamingThreadId, setStreamingThreadId] = useState<string | null>(null);
  const [streamingLabel, setStreamingLabel] = useState<string>("");
  const [awaitingClarification, setAwaitingClarification] = useState(false);
  const [error, setError] = useState<string | null>(null);
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

  const bottomRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);
  const streamBufferRef = useRef<StreamBuffer | null>(null);
  const { isDark, toggleTheme } = useTheme();
  const { leftWidth, rightWidth, startDrag } = useResizablePanels();

  const {
    threadId,
    threadIdRef,
    backendOk,
    threads,
    setThreads,
    handleReturnToActive,
    handleNewConversation,
    handleSelectThread,
    handleDeleteThread,
  } = useThreads({
    inputRef,
    streamBufferRef,
    setMessages,
    setGraphEvents,
    setLoading,
    setTypewriterIdx,
    setAwaitingClarification,
    setError,
    setMobileSidebarOpen,
  });

  const { handleSubmit } = useChatStream({
    threadId,
    threadIdRef,
    streamBufferRef,
    inputRef,
    input,
    messages,
    graphEvents,
    loading,
    awaitingClarification,
    setInput,
    setMessages,
    setGraphEvents,
    setLoading,
    setStreamingThreadId,
    setStreamingLabel,
    setTypewriterIdx,
    setAwaitingClarification,
    setError,
    setThreads,
  });

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, loading]);

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
      <AppSidebar
        open={mobileSidebarOpen}
        width={leftWidth}
        backendOk={backendOk}
        threadId={threadId}
        threads={threads}
        streamingThreadId={streamingThreadId}
        streamingLabel={streamingLabel}
        isDark={isDark}
        onClose={() => setMobileSidebarOpen(false)}
        onNewConversation={handleNewConversation}
        onSelectThread={handleSelectThread}
        onDeleteThread={handleDeleteThread}
        onReturnToActive={handleReturnToActive}
        onToggleTheme={toggleTheme}
      />

      <ResizeHandle side="left" onMouseDown={(e) => startDrag("left", e)} />

      {/* ── Main ────────────────────────────────────────────── */}
      <main className="flex flex-col flex-1 min-w-0 bg-[#eef4fb] dark:bg-[#060c14]">

        <ChatHeader
          threadId={threadId}
          awaitingClarification={awaitingClarification}
          progressActive={progressActive}
          progressStage={progressStage}
          onOpenSidebar={() => setMobileSidebarOpen(true)}
          onOpenMemory={() => setMemoryOpen(true)}
          onOpenMermaidGraph={openMermaidGraph}
          onOpenMobileGraph={() => setMobileGraphOpen(true)}
        />

        {/* Messages */}
        <div className="flex-1 overflow-y-auto px-5 py-4 md:px-6 md:py-5">
          {messages.length === 0 && !loading && !error && (
            <ChatEmptyState
              onSelectSuggestion={(suggestion) => {
                setInput(suggestion);
                inputRef.current?.focus();
              }}
            />
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

        <ChatComposer
          value={input}
          placeholder={placeholder}
          disabled={loading || !threadId || !backendOk}
          canSubmit={!loading && Boolean(input.trim()) && Boolean(threadId) && backendOk}
          inputRef={inputRef}
          onChange={setInput}
          onSubmit={handleSubmit}
        />
      </main>

      <ResizeHandle
        side="right"
        visible={graphPanelVisible}
        onMouseDown={(e) => startDrag("right", e)}
      />

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
