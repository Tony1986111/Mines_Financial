"use client";

import type { CSSProperties } from "react";
import { relativeTime, type StoredThread } from "@/lib/threadStorage";

interface AppSidebarProps {
  open: boolean;
  width: number;
  backendOk: boolean;
  threadId: string | null;
  threads: StoredThread[];
  streamingThreadId: string | null;
  streamingLabel: string;
  isDark: boolean;
  onClose: () => void;
  onNewConversation: () => void;
  onSelectThread: (thread: StoredThread) => void;
  onDeleteThread: (id: string) => void;
  onReturnToActive: () => void;
  onToggleTheme: () => void;
}

export default function AppSidebar({
  open,
  width,
  backendOk,
  threadId,
  threads,
  streamingThreadId,
  streamingLabel,
  isDark,
  onClose,
  onNewConversation,
  onSelectThread,
  onDeleteThread,
  onReturnToActive,
  onToggleTheme,
}: AppSidebarProps) {
  return (
    <>
      {open && (
        <div
          className="fixed inset-0 z-40 bg-black/40 md:hidden"
          onClick={onClose}
        />
      )}

      <aside
        className={`mobile-sidebar-shell bg-[#f4f8fd] dark:bg-[#091524] border-r border-[#cddcea] dark:border-[#162840] flex flex-col overflow-hidden
          fixed inset-y-0 left-0 z-50 transition-transform duration-300
          md:relative md:inset-auto md:z-auto md:shrink-0 md:transition-none
          ${open ? "translate-x-0" : "-translate-x-full md:translate-x-0"}`}
        style={{ "--sidebar-width": `${width}px` } as CSSProperties}
      >
        <div className="px-4 pt-5 pb-4 border-b border-[#cddcea] dark:border-[#162840]">
          <div className="flex items-center gap-2.5">
            <span className="text-lg">⛏️</span>
            <span className="font-bold text-sm tracking-tight text-[#0a1e38] dark:text-[#dce8f8]">ASX Mining</span>
            <button
              onClick={onClose}
              className="ml-auto flex h-8 w-8 items-center justify-center rounded-lg text-sm text-[#7a9ab8] transition-colors hover:bg-[#e8f0fa] hover:text-[#0a1e38] dark:text-[#3d5878] dark:hover:bg-[#0d1c2e] dark:hover:text-[#c4d8f0] md:hidden"
              aria-label="Close menu"
            >
              ✕
            </button>
          </div>
          <p className="text-[11px] text-[#7a9ab8] dark:text-[#3d5878] mt-0.5 font-mono">Financial Report Q&A</p>
        </div>

        <div className="px-4 py-3 border-b border-[#cddcea] dark:border-[#162840] space-y-2.5">
          <div className="flex items-center gap-2">
            <span className={`w-1.5 h-1.5 rounded-full ${backendOk ? "bg-emerald-500" : "bg-red-500"}`} />
            <span className="text-[11px] text-[#7a9ab8] dark:text-[#3d5878]">{backendOk ? "Backend connected" : "Disconnected"}</span>
          </div>
          <button
            onClick={onNewConversation}
            className="w-full text-xs bg-[#1a4a8a] hover:bg-[#20579e] active:bg-[#143870] text-white rounded-lg py-2 px-3 transition-all flex items-center gap-1.5 font-semibold tracking-wide shadow-sm shadow-[#1a4a8a]/25"
          >
            <span className="text-base leading-none font-light">+</span> New Conversation
          </button>
        </div>

        <div className="flex-1 overflow-y-auto">
          <div className="px-4 pt-3 pb-1">
            <p className="text-[9px] uppercase tracking-[0.15em] text-[#7a9ab8] dark:text-[#3d5878] font-bold">History</p>
          </div>

          {streamingThreadId && (
            <div
              className={`relative flex items-stretch border-l-2 border-emerald-500 bg-emerald-50 dark:bg-emerald-900/20 ${
                streamingThreadId !== threadId
                  ? "cursor-pointer hover:bg-emerald-100 dark:hover:bg-emerald-900/30 transition-colors"
                  : ""
              }`}
              onClick={() => streamingThreadId !== threadId && onReturnToActive()}
            >
              <div className="flex-1 px-4 py-2.5 min-w-0">
                <div className="flex items-center gap-1.5 mb-0.5">
                  <span className="w-1.5 h-1.5 rounded-full bg-emerald-500 shrink-0 animate-pulse" />
                  <span className="text-[9px] font-bold uppercase tracking-wide text-emerald-600 dark:text-emerald-400">
                    In progress
                  </span>
                </div>
                <p className="text-[11px] text-emerald-800 dark:text-emerald-300 truncate leading-snug font-medium">
                  {streamingLabel || "Responding..."}
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
                onClick={() => onSelectThread(t)}
                className="flex-1 text-left px-4 py-2.5 min-w-0"
              >
                <p className="text-[11px] text-[#0a1e38] dark:text-[#c4d8f0] truncate leading-snug pr-5 font-medium">
                  {t.label || "Untitled conversation"}
                </p>
                <p className="text-[10px] text-[#94b0cc] dark:text-[#3d5878] mt-0.5 font-mono">{relativeTime(t.updatedAt)}</p>
              </button>
              <button
                onClick={() => onDeleteThread(t.id)}
                title="Delete thread"
                className="absolute right-2 top-1/2 -translate-y-1/2 w-6 h-6 md:w-5 md:h-5 rounded flex items-center justify-center text-[#94b0cc] dark:text-[#3d5878] hover:text-red-500 dark:hover:text-red-400 hover:bg-red-50 dark:hover:bg-red-400/10 opacity-100 md:opacity-0 md:group-hover:opacity-100 transition-all text-[10px]"
              >
                ✕
              </button>
            </div>
          ))}
        </div>

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
            onClick={onToggleTheme}
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
    </>
  );
}
