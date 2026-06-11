"use client";

interface ChatHeaderProps {
  threadId: string | null;
  awaitingClarification: boolean;
  progressActive: boolean;
  progressStage: string;
  onOpenSidebar: () => void;
  onOpenMemory: () => void;
  onOpenMermaidGraph: () => void;
  onOpenMobileGraph: () => void;
}

export default function ChatHeader({
  threadId,
  awaitingClarification,
  progressActive,
  progressStage,
  onOpenSidebar,
  onOpenMemory,
  onOpenMermaidGraph,
  onOpenMobileGraph,
}: ChatHeaderProps) {
  return (
    <header className="min-h-12 md:h-12 bg-[#f4f8fd]/95 dark:bg-[#091524]/95 border-b border-[#cddcea] dark:border-[#162840] flex flex-wrap md:flex-nowrap items-center px-3 md:px-5 py-2 md:py-0 gap-2 md:gap-3 shrink-0 backdrop-blur-sm">
      <button
        onClick={onOpenSidebar}
        className="md:hidden p-1.5 rounded-lg text-[#7a9ab8] hover:bg-[#e8f0fa] dark:hover:bg-[#0d1c2e] transition-colors shrink-0"
        aria-label="Open menu"
      >
        <svg width="18" height="18" viewBox="0 0 18 18" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round">
          <line x1="2" y1="5" x2="16" y2="5" />
          <line x1="2" y1="9" x2="16" y2="9" />
          <line x1="2" y1="13" x2="16" y2="13" />
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
          onClick={onOpenMemory}
          className="rounded-lg border border-[#b8d0e8] dark:border-[#1e3858] bg-white dark:bg-[#0d1c2e] px-2.5 py-1.5 md:px-3 text-xs font-semibold text-[#1a4a8a] dark:text-[#7eb3e8] shadow-sm transition-all hover:bg-[#e8f0fa] dark:hover:bg-[#12243c] hover:border-[#1a4a8a]/50 dark:hover:border-[#5a8fc8]/40 shrink-0"
        >
          <span className="md:hidden">memory</span>
          <span className="hidden md:inline">Memory</span>
        </button>
        <button
          onClick={onOpenMermaidGraph}
          className="md:hidden rounded-lg border border-[#b8d0e8] dark:border-[#1e3858] bg-white dark:bg-[#0d1c2e] px-2.5 py-1.5 text-xs font-semibold text-[#1a4a8a] dark:text-[#7eb3e8] shadow-sm transition-all hover:bg-[#e8f0fa] dark:hover:bg-[#12243c] hover:border-[#1a4a8a]/50 dark:hover:border-[#5a8fc8]/40 shrink-0"
        >
          graph
        </button>
        <button
          onClick={onOpenMobileGraph}
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
          onClick={onOpenMermaidGraph}
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
  );
}
